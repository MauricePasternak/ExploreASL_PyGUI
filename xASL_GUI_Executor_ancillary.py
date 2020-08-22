import os
from glob import iglob
import re
from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *
from xASL_GUI_HelperClasses import DandD_FileExplorerFile2LineEdit
import pandas as pd
import platform
from itertools import chain
from pprint import pprint
from functools import reduce


# Creates lock dirs where necessary in anticipation for assigning a watcher to the root lock directory
def initialize_all_lock_dirs(analysis_dir, regex, run_options, session_names):
    """
    Convenience function for creating the lock directories in advance of a run such that a file system watcher
    could effectively be set at the root and detect any downstream changes
    :param analysis_dir: the root analysis directory of the study ex. User\\Study_Name\\analysis
    :param regex: the regex used to identify subjects
    :param run_options: the type of run (ex. ASL, Structural, Both, Population)
    :param session_names: the expected session names that should be encountered (ex. ASL_1, ASL_2, etc.)
    """

    def dirnames_for_asl(analysis_directory, study_sessions, within_session_names):
        dirnames = [os.path.join(analysis_directory, "lock", f"xASL_module_ASL", sess, f"xASL_module_ASL_{name}")
                    for sess in study_sessions for name in within_session_names]
        return dirnames

    def dirnames_for_structural(analysis_directory, study_sessions):
        dirnames = [
            os.path.join(analysis_directory, "lock", f"xASL_module_Structural", sess, "xASL_module_Structural")
            for sess in study_sessions]
        return dirnames

    def dirnames_for_population(analysis_directory):
        return [os.path.join(analysis_directory, "lock", "xASL_module_Population", "xASL_module_Population")]

    print(f"Generating the appropriate lock dirs for {analysis_dir}")
    sessions = [session for session in os.listdir(analysis_dir) if regex.search(session)]

    # Prepare the list of names of lockdirs to expect to create based on the run options, session names and detected
    # sessions in the analysis root directory
    if run_options == "Both":
        struc_dirs = dirnames_for_structural(analysis_dir, sessions)
        asl_dirs = dirnames_for_asl(analysis_dir, sessions, session_names)
        lock_dirs = struc_dirs + asl_dirs
    elif run_options == "ASL":
        lock_dirs = dirnames_for_asl(analysis_dir, sessions, session_names)
    elif run_options == "Structural":
        lock_dirs = dirnames_for_structural(analysis_dir, sessions)
    elif run_options == "Population":
        lock_dirs = dirnames_for_population(analysis_dir)
    else:
        raise ValueError("Impossible outcome in initialize_all_lock_dirs")

    # Create empty directories where applicable
    for lock_dir in lock_dirs:
        if not os.path.exists(lock_dir):
            os.makedirs(lock_dir)


# Must be called after the lock dirs have been created; this function will attempt to calculate all the status files
# that should be created in the run process
def calculate_anticipated_workload(parmsdict, run_options):
    """
    Convenience function for calculating the anticipated workload
    :param parmsdict: the parameter file of the study; given parameters such as the regex are used from this
    :param run_options: "Structural", "ASL", "Both" or "Population"; which module is being run
    :return: workload; a numerical representation of the cumulative value of all status files made; these will be
    used to determine the appropriate maximum value for the progressbar
    """

    def get_structural_workload(analysis_directory, study_subjects, structuralmod_dict):
        workload_translator = {
            "010_LinearReg_T1w2MNI.status": 1, "020_LinearReg_FLAIR2T1w.status": 2,
            "030_Resample_FLAIR2T1w.status": 1, "040_Segment_FLAIR.status": 3, "050_LesionFilling.status": 1,
            "060_Segment_T1w.status": 10, "070_GetWMHvol.status": 1, "080_Resample2StandardSpace.status": 2,
            "090_GetVolumetrics.status": 1, "100_VisualQC_Structural.status": 1, "999_ready.status": 0
        }
        default_workload = ["010_LinearReg_T1w2MNI.status", "060_Segment_T1w.status",
                            "080_Resample2StandardSpace.status", "090_GetVolumetrics.status",
                            "100_VisualQC_Structural.status", "999_ready.status"]
        flair_workload = ["020_LinearReg_FLAIR2T1w.status", "030_Resample_FLAIR2T1w.status",
                          "040_Segment_FLAIR.status", "050_LesionFilling.status", "070_GetWMHvol.status"]
        status_files = []
        for subject in study_subjects:
            has_flair_img = os.path.exists(os.path.join(analysis_directory, subject, "FLAIR.nii"))
            directory = os.path.join(analysis_directory, "lock", "xASL_module_Structural", subject,
                                     "xASL_module_Structural")
            current_status_files = os.listdir(directory)
            if has_flair_img:
                workload = default_workload + flair_workload
            else:
                workload = default_workload

            # Filter out any anticipated status files that are already present in the lock dirs
            filtered_workload = set(workload).difference(set(current_status_files))
            # Append the filepaths; these will be used after analysis to check for incompleted STATUS workloads
            status_files.append([os.path.join(directory, status_file) for status_file in filtered_workload])
            numerical_representation = sum([workload_translator[stat_file] for stat_file in filtered_workload])
            structuralmod_dict[subject] = numerical_representation

        # Flatten the nested list that is status_files
        status_files = list(chain(*status_files))

        return structuralmod_dict, status_files

    def get_asl_workload(analysis_directory, study_subjects, session_names, aslmod_dict):
        workload_translator = {
            "020_RealignASL.status": 1, "030_RegisterASL.status": 2, "040_ResampleASL.status": 1,
            "050_PreparePV.status": 1, "060_ProcessM0.status": 1, "070_Quantification.status": 2,
            "080_CreateAnalysisMask.status": 1, "090_VisualQC_ASL.status": 1, "999_ready.status": 0
        }
        default_workload = ["020_RealignASL.status", "030_RegisterASL.status", "040_ResampleASL.status",
                            "050_PreparePV.status", "060_ProcessM0.status", "070_Quantification.status",
                            "080_CreateAnalysisMask.status", "090_VisualQC_ASL.status", "999_ready.status"]

        # Must iterate through both the subject level listing AND the session level (ASL_1, ASL_2, etc.) listing
        status_files = []
        for subject in study_subjects:
            for session in session_names:
                directory = os.path.join(analysis_directory, "lock", "xASL_module_ASL", subject,
                                         f"xASL_module_ASL_{session}")
                current_status_files = os.listdir(directory)
                workload = default_workload
                # Filter out any anticipated status files that are already present in the lock dirs
                filtered_workload = set(workload).difference(set(current_status_files))
                # Append the filepaths; these will be used after analysis to check for incompleted STATUS workloads
                status_files.append([os.path.join(directory, status_file) for status_file in filtered_workload])
                # Calculate the numerical representation of the STATUS files workload
                numerical_representation = sum([workload_translator[stat_file] for stat_file in filtered_workload])
                aslmod_dict[subject][session] = numerical_representation

        # Flatten the nested list that is status_files
        status_files = list(chain(*status_files))

        return aslmod_dict, status_files

    def get_population_workload(analysis_directory):
        workload_translator = {
            "010_CreatePopulationTemplates.status": 1, "020_CreateAnalysisMask.status": 1,
            "030_CreateBiasfield.status": 1, "040_GetDICOMStatistics.status": 1,
            "050_GetVolumeStatistics.status": 1, "060_GetMotionStatistics.status": 1,
            "070_GetROIstatistics.status": 20, "080_SortBySpatialCoV.status": 1, "090_DeleteAndZip.status": 1,
            "999_ready.status": 0
        }
        default_workload = ["010_CreatePopulationTemplates.status", "020_CreateAnalysisMask.status",
                            "030_CreateBiasfield.status", "040_GetDICOMStatistics.status",
                            "050_GetVolumeStatistics.status", "060_GetMotionStatistics.status",
                            "070_GetROIstatistics.status", "080_SortBySpatialCoV.status",
                            "090_DeleteAndZip.status", "999_ready.status"]

        directory = os.path.join(analysis_directory, "lock", "xASL_module_Population", "xASL_module_Population")
        current_status_files = os.listdir(directory)

        workload = default_workload
        filtered_workload = set(workload).difference(set(current_status_files))
        status_files = [os.path.join(directory, status_file) for status_file in filtered_workload]
        numerical_representation = sum([workload_translator[stat_file] for stat_file in filtered_workload])
        # No need for flattening the status_files for this one; not nested
        return numerical_representation, status_files

    # First get all the subjects
    analysis_dir: str = parmsdict["D"]["ROOT"]
    regex = re.compile(parmsdict["subject_regexp"])
    sess_names: list = parmsdict["SESSIONS"]
    subjects = [subject for subject in os.listdir(analysis_dir) if
                all([regex.search(subject),  # regex must fit
                     os.path.isdir(os.path.join(analysis_dir, subject)),  # must be a directory
                     subject not in ["Population", "lock"]  # can't accidentally be the non-subject directories
                     ])]

    # Use a dict to keep track of everything
    struct_dict = {subject: 0 for subject in subjects}
    asl_dict = {subject: {} for subject in subjects}

    # Update the dicts as appropriate
    if run_options == "Both":
        struct_dict, struct_status = get_structural_workload(analysis_dir, subjects, struct_dict)
        asl_dict, asl_status = get_asl_workload(analysis_dir, subjects, sess_names, asl_dict)

        struct_totalworkload = sum(struct_dict.values())
        asl_totalworkload = {subject: sum(asl_dict[subject].values()) for subject in subjects}
        asl_totalworkload = sum(asl_totalworkload.values())
        print(f"Structural Calculated Workload: {struct_totalworkload}")
        print(f"ASL Calculated Workload: {asl_totalworkload}")
        # Return the numerical sum of the workload and the combined list of the expected status files
        return struct_totalworkload + asl_totalworkload, struct_status + asl_status

    elif run_options == "ASL":
        asl_dict, asl_status = get_asl_workload(analysis_dir, subjects, sess_names, asl_dict)
        # pprint(asl_dict)
        asl_totalworkload = {subject: sum(asl_dict[subject].values()) for subject in subjects}
        asl_totalworkload = sum(asl_totalworkload.values())
        print(f"ASL Calculated Workload: {asl_totalworkload}")
        # Return the numerical sum of the workload and the list of expected status files
        return asl_totalworkload, asl_status

    elif run_options == "Structural":
        struct_dict, struct_status = get_structural_workload(analysis_dir, subjects, struct_dict)
        # pprint(struct_dict)
        struct_totalworkload = sum(struct_dict.values())
        print(f"Structural Calculated Workload: {struct_totalworkload}")
        # Return the numerical sum of the workload and the list of expected status files
        return struct_totalworkload, struct_status

    elif run_options == "Population":
        pop_totalworkload, pop_status = get_population_workload(analysis_dir)
        print(f"Population Calculated Workload: {pop_totalworkload}")
        # Return the numerical sum of the workload and the list of expected status files
        return pop_totalworkload, pop_status

    else:
        print("THIS SHOULD NEVER PRINT AS YOU HAVE SELECTED AN IMPOSSIBLE WORKLOAD OPTION")


# Called after processing is done to compare the present status files against the files that were expected to be created
# at the time the run was initialized
def calculate_missing_STATUS(analysis_dir, expected_status_files):
    postrun_status_files = iglob(os.path.join(analysis_dir, 'lock', "**", "*.status"), recursive=True)
    incomplete = [file for file in expected_status_files if file not in postrun_status_files]
    if len(incomplete) == 0:
        return True, incomplete
    else:
        return False, incomplete


def interpret_statusfile_errors(incomplete_files, translators: dict):
    """
    Interprets the step in the ExploreASL pipeline for which particular subjects/sessions/etc. must have failed and
    returns these interpretations as messages for each of the modules
    :param incomplete_files: the list of status files that were not generated in the pipeline
    :param translators: the translators (from JSON_LOGIC directory) used to convert filenames to their descriptions for
    generating the correct error message
    :return: 3 lists of interpreted error messages, one for each ExploreASL module
    """
    if platform.system() == "Windows":
        delimiter = '\\\\'
    else:
        delimiter = '/'

    # Prepare containers and translators
    struct_dict = {}
    asl_dict = {}
    pop_list = []
    asl_msgs = []
    struct_msgs = []
    pop_msgs = []
    stuct_status_file_translator = translators["Structural_Module_Filename2Description"]
    asl_status_file_translator = translators["ASL_Module_Filename2Description"]
    population_file_translator = translators["Population_Module_Filename2Description"]

    # Prepare regex detectors
    asl_regex = re.compile(f"(?:.*){delimiter}lock{delimiter}xASL_module_(?:Structural|ASL){delimiter}(.*){delimiter}"
                           f"xASL_module_(?:Structural|ASL)_?(.*)?{delimiter}(.*\\.status)")
    pop_regex = re.compile(f"(?:.*){delimiter}lock{delimiter}xASL_module_Population{delimiter}"
                           f"xASL_module_Population{delimiter}(.*\\.status)")

    # Use the regex to extract subject, session, filename fields from the status filepaths, then organize the status
    # file basenames into the appropriate dictionary structure
    for file in incomplete_files:
        asl_match = asl_regex.search(file)
        pop_match = pop_regex.search(file)
        if asl_match:
            subject, session, file = asl_match.groups()
            # Structural
            if session == "":
                struct_dict.setdefault(subject, [])
                struct_dict[subject].append(file)
            # ASL
            else:
                asl_dict.setdefault(subject, {})
                asl_dict[subject].setdefault(session, [])
                asl_dict[subject][session].append(file)
        # Population
        elif pop_match:
            file = pop_match.group(1)
            pop_list.append(file)
        else:
            return

    # For each of the dictionaries corresponding to an ExploreASL module, sort the basenames and create the appropriate
    # error message for that subject/session
    if len(asl_dict) > 0:
        for subject, inner_1 in asl_dict.items():
            for session, files in inner_1.items():
                sorted_files = sorted(files)
                msg = f"Subject: {subject}; Session: {session}; Failed in the ASL module prior to: " \
                      f"{asl_status_file_translator[sorted_files[0]]}; " \
                      f"STATUS file failed to be created: {sorted_files[0]}"
                asl_msgs.append(msg)

    if len(struct_dict) > 0:
        for subject, files in struct_dict.items():
            sorted_files = sorted(files)
            msg = f"Subject: {subject}; Failed in the Structural module prior to: " \
                  f"{stuct_status_file_translator[sorted_files[0]]}; " \
                  f"STATUS file failed to be created: {sorted_files[0]}"
            struct_msgs.append(msg)

    if len(pop_list) > 0:
        pop_msgs = [population_file_translator[sorted(pop_list)][0]]

    return struct_msgs, asl_msgs, pop_msgs


class xASL_GUI_RerunPrep(QWidget):
    """
    Class designated to delete STATUS and other files such that a re-run of a particular module may be possible
    """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.parent = parent
        self.target_dir = self.parent.le_modjob.text()
        self.setWindowFlag(Qt.Window)
        self.setWindowTitle("Explore ASL - Re-run setup")
        self.setMinimumSize(400, 720)
        self.mainlay = QVBoxLayout(self)
        self.dir_struct = self.get_directory_structure(os.path.join(self.target_dir, "lock"))

        self.lock_tree = QTreeWidget(self)
        self.fill_tree(self.lock_tree.invisibleRootItem(), self.dir_struct)
        self.lock_tree.expandToDepth(2)
        self.lock_tree.itemChanged.connect(self.change_check_state)
        self.lock_tree.setHeaderLabel("Select the directories that should be redone")

        self.btn = QPushButton("Remove selected .status files \nto allow for re-run in the main widget", self,
                               clicked=self.remove_status_files)
        self.btn.setMinimumHeight(50)
        font = QFont()
        font.setPointSize(12)
        self.btn.setFont(font)

        self.mainlay.addWidget(self.lock_tree)
        self.mainlay.addWidget(self.btn)

    @staticmethod
    def get_directory_structure(rootdir):
        """
        Creates a nested dictionary that represents the folder structure of rootdir
        """
        directory = {}
        rootdir = rootdir.rstrip(os.sep)
        start = rootdir.rfind(os.sep) + 1
        for path, dirs, files in os.walk(rootdir):
            folders = path[start:].split(os.sep)
            subdir = dict.fromkeys(files)
            parent = reduce(dict.get, folders[:-1], directory)
            parent[folders[-1]] = subdir
        return directory

    def fill_tree(self, parent, d):
        if isinstance(d, dict):
            for key, value in d.items():
                it = QTreeWidgetItem()
                it.setText(0, key)
                if isinstance(value, dict):
                    parent.addChild(it)
                    it.setCheckState(0, Qt.Unchecked)
                    self.fill_tree(it, value)
                else:
                    parent.addChild(it)
                    it.setCheckState(0, Qt.Unchecked)

    @staticmethod
    def change_check_state(item: QTreeWidgetItem, col: int):
        if item.checkState(col):
            for idx in range(item.childCount()):
                item_child = item.child(idx)
                item_child.setCheckState(0, Qt.Checked)
        else:
            for idx in range(item.childCount()):
                item_child = item.child(idx)
                item_child.setCheckState(0, Qt.Unchecked)

    def return_filepaths(self):
        all_status = self.lock_tree.findItems(".status", (Qt.MatchEndsWith | Qt.MatchRecursive), 0)
        selected_status = [status for status in all_status if status.checkState(0)]
        filepaths = []

        for status in selected_status:
            filepath = [status.text(0)]
            parent = status.parent()
            while parent.text(0) != "lock":
                filepath.insert(0, parent.text(0))
                parent = parent.parent()
            filepath.insert(0, "lock")
            filepaths.append(os.path.join(self.target_dir, *filepath))

        return filepaths, selected_status

    def remove_status_files(self):
        filepaths, treewidgetitems = self.return_filepaths()
        print(f"Removing: {filepaths}")
        for filepath, widget in zip(filepaths, treewidgetitems):
            os.remove(filepath)

        # Clear the tree
        self.lock_tree.clear()
        # Refresh the file structure
        self.dir_struct = self.get_directory_structure(os.path.join(self.target_dir, "lock"))
        # Refresh the tree
        self.fill_tree(self.lock_tree.invisibleRootItem(), self.dir_struct)
        self.lock_tree.expandToDepth(2)
        self.lock_tree.itemChanged.connect(self.change_check_state)


# noinspection PyAttributeOutsideInit
class xASL_GUI_TSValter(QWidget):
    """
    Class designated to alter the contents of participants.tsv
    """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.parent = parent
        self.target_dir = self.parent.le_modjob.text()
        self.setWindowFlag(Qt.Window)
        self.setWindowTitle("Alter participants.tsv contents")
        self.mainlay = QVBoxLayout(self)
        # First section, the loading of the covariate file
        self.formlay_covfile = QFormLayout()
        self.hlay_covfile = QHBoxLayout()
        self.le_covfile = DandD_FileExplorerFile2LineEdit([".tsv", ".xlsx", ".csv"], self)
        self.le_covfile.textChanged.connect(self.load_covariates_data)
        self.btn_covfile = QPushButton("...", self)
        self.hlay_covfile.addWidget(self.le_covfile)
        self.hlay_covfile.addWidget(self.btn_covfile)
        self.formlay_covfile.addRow("Covariates File", self.hlay_covfile)
        # Second section, the Drag and Drop listviews
        self.hlay_dandcols = QHBoxLayout()
        self.vlay_covcols = QVBoxLayout()
        self.lab_covcols = QLabel("Covariates", self)
        self.list_covcols = ColnamesDragDrop_ListWidget(self)
        self.vlay_covcols.addWidget(self.lab_covcols)
        self.vlay_covcols.addWidget(self.list_covcols)

        self.vlay_tsvcols = QVBoxLayout()
        self.lab_tsvcols = QLabel("TSV Variables", self)
        self.list_tsvcols = ColnamesDragDrop_ListWidget(self)
        self.vlay_tsvcols.addWidget(self.lab_tsvcols)
        self.vlay_tsvcols.addWidget(self.list_tsvcols)

        self.hlay_dandcols.addLayout(self.vlay_covcols)
        self.hlay_dandcols.addLayout(self.vlay_tsvcols)
        # Third section, just the main button
        self.btn_altertsv = QPushButton("Commit changes", self, clicked=self.commit_changes)

        self.mainlay.addLayout(self.formlay_covfile)
        self.mainlay.addLayout(self.hlay_dandcols)
        self.mainlay.addWidget(self.btn_altertsv)

        # Once the widget UI is set up, load in the tsv data
        self.load_tsv_data()

    def load_tsv_data(self):
        tsv_file = os.path.join(self.target_dir, "participants.tsv")
        tsv_df = pd.read_csv(tsv_file, sep='\t')
        tsv_df.drop(labels=[col for col in tsv_df.columns if "Unnamed" in col], axis=1, inplace=True)
        self.tsv_df = tsv_df

        # Set the listwidget to contain the column names here
        tsv_colnames = self.tsv_df.columns.tolist()
        self.list_tsvcols.clear()
        self.list_tsvcols.addItems(tsv_colnames)

    def load_covariates_data(self, cov_filepath: str):
        # First Set of checks: filepath integrity
        try:
            if any([cov_filepath == '',  # The provided text can't be blank (to avoid false execution post-clearing)
                    not os.path.exists(cov_filepath),  # The provided filepath must exist
                    cov_filepath[-4:] not in ['.tsv', '.csv', '.xlsx']
                    ]):
                return
        except FileNotFoundError:
            return

        # Load in the data
        if cov_filepath.endswith('.tsv'):
            df = pd.read_csv(cov_filepath, sep='\t')
        elif cov_filepath.endswith('.csv'):
            df = pd.read_csv(cov_filepath)
        else:
            df = pd.read_excel(cov_filepath)

        # Second set of checks: data integrity
        if any([len(df) != len(self.tsv_df)  # Dataframe must be the same length for proper concatenation
                ]):
            return

        self.cov_df = df

        # Set the listwidget to contain the column names here
        cov_colnames = self.cov_df.columns.tolist()
        self.list_covcols.clear()
        self.list_covcols.addItems(cov_colnames)

        # Also reset the tsv columns
        self.list_tsvcols.clear()
        self.list_tsvcols.addItems(self.tsv_df.columns.tolist())

    def commit_changes(self):
        commit_df = pd.DataFrame()

        for idx in range(self.list_tsvcols.count()):
            colname = self.list_tsvcols.item(idx).text()
            if colname not in self.tsv_df.columns:
                commit_df[colname] = self.cov_df[colname].values
            else:
                commit_df[colname] = self.tsv_df[colname].values

        os.replace(src=os.path.join(self.target_dir, "participants.tsv"),
                   dst=os.path.join(self.target_dir, "participants_old.tsv"))

        commit_df.to_csv(path_or_buf=os.path.join(self.target_dir, "participants.tsv"),
                         sep='\t',
                         na_rep='n/a',
                         index=False)


class ColnamesDragDrop_ListWidget(QListWidget):
    """
    Class meant to drag and drop items between themselves
    """
    alert_regex = Signal()  # This will be called in the ParmsMaker superclass to update its regex

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)  # this was the magic line
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.addItems(["Foo", "Bar"])
        self.colnames = []

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat('application/x-qabstractitemmodeldatalist'):
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasFormat('application/x-qabstractitemmodeldatalist'):
            event.setDropAction(Qt.MoveAction)
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        if event.mimeData().hasFormat('application/x-qabstractitemmodeldatalist'):
            event.accept()
            for item in event.source().selectedItems():
                self.addItem(item.text())
        else:
            event.ignore()
