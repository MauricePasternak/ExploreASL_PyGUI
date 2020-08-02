import json
import os
import re
import sys
from glob import glob
from itertools import chain
from time import sleep

import matlab
import matlab.engine
from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from xASL_GUI_HelperClasses import DandD_FileExplorer2LineEdit
from pprint import pprint


class ExploreASL_WorkerSignals(QObject):
    """
    Class for handling the signals sent by an ExploreASL worker
    """
    finished_processing = Signal()  # Signal sent by worker to watcher to help indicate it when to stop watching
    encountered_fatal_error = Signal(str)  # Signal sent by worker to raise a dialogue informing the user of an error


class ExploreASL_Worker(QRunnable):
    """
    Worker thread for running lauching an ExploreASL MATLAB session with the given arguments
    """

    def __init__(self, *args):
        self.args = args
        super().__init__()
        self.signals = ExploreASL_WorkerSignals()
        print(f"Initialized Worker with args {self.args}")

    # This is called by the threadpool during threadpool.start(worker)
    def run(self):
        exploreasl_path, par_path, process_data, skip_pause, iworker, nworkers, imodules = self.args
        print("Inside run")
        eng = matlab.engine.start_matlab()
        eng.cd(exploreasl_path)
        imodules = matlab.int8(imodules)
        try:
            result = eng.ExploreASL_Master(par_path, process_data, skip_pause, iworker, nworkers, imodules)
            print(result)
        except matlab.engine.EngineError as e:
            print(e)
            self.signals.encountered_fatal_error.emit(f"{e}")

        self.signals.finished_processing.emit()
        print("A worker has finished processing")

    #     print(f"Inside execute on processor {os.getpid()}")
    #
    # # Generate the string that the command line will feed into the complied MATLAB session
    # func_line = f"('{par_path}', " \
    #             f"{process_data}, " \
    #             f"{skip_pause}, " \
    #             f"{iworker}, " \
    #             f"{nworkers}, " \
    #             f"[{' '.join([str(item) for item in imodules])}])"
    #
    # # For troubleshooting and visualization
    # print(f"Func line: {func_line}")
    #
    # # Compile and run MATLAB session from command line
    # result = subprocess.call(
    #     ["matlab",
    #      "-nodesktop",
    #      "-r",
    #      f"cd('{exploreasl_path}'); ExploreASL_Master{func_line}"]
    # )


# noinspection PyCallingNonCallable,PyAttributeOutsideInit
class xASL_Executor(QMainWindow):
    cont_nstudies: QWidget

    def __init__(self, parent_win=None):
        # Parent window is fed into the constructor to allow for communication with parent window devices
        super().__init__(parent=parent_win)
        if parent_win is not None:
            self.config = self.parent().config
        else:
            with open("ExploreASL_GUI_masterconfig.json") as f:
                self.config = json.load(f)

        # Window Size and initial visual setup
        self.setMinimumSize(1080, 480)
        self.cw = QWidget(self)
        self.setCentralWidget(self.cw)
        self.mainlay = QHBoxLayout(self.cw)
        self.setLayout(self.mainlay)
        self.setWindowTitle("Explore ASL - Executor")
        self.setWindowIcon(QIcon(os.path.join(os.getcwd(), "media", "ExploreASL_logo.png")))
        # Main run button must be defined early, since connections will be dynamically made to it
        self.threadpool = QThreadPool()
        self.btn_runExploreASL = QPushButton("Run Explore ASL", self.cw, clicked=self.run_Explore_ASL)
        self.btn_runExploreASL.setEnabled(False)
        # Create a "debt" variable that will be used to reactivate the ExploreASL button; will decrement when a process
        # begins, and increment back towards zero when said process ends. At zero, the button will be re-activated
        self.total_process_dbt = 0

        self.UI_Setup_Layouts_and_Groups()
        self.UI_Setup_TaskScheduler()
        self.UI_Setup_TextFeedback_and_Executor()

    def UI_Setup_Layouts_and_Groups(self):
        self.vlay_left, self.vlay_right = QVBoxLayout(self.cw), QVBoxLayout(self.cw)
        self.grp_taskschedule, self.grp_textoutput = QGroupBox("Task Scheduler", self.cw), QGroupBox("Output", self.cw)
        self.vlay_left.addWidget(self.grp_taskschedule)
        self.vlay_right.addWidget(self.grp_textoutput)
        self.mainlay.addLayout(self.vlay_left)
        self.mainlay.addLayout(self.vlay_right)

    # Left side setup; define the number of studies
    def UI_Setup_TaskScheduler(self):
        self.vlay_taskschedule = QVBoxLayout(self.grp_taskschedule)
        self.lab_coresinfo = QLabel(
            f"CPU Count: A total of {os.cpu_count() // 2} processors are available on this machine",
            self.grp_taskschedule)
        self.ncores_left = os.cpu_count() // 2
        self.lab_coresleft = QLabel(f"You are permitted to set up to {self.ncores_left} more core(s)")
        self.cont_nstudies = QWidget(self.grp_taskschedule)
        self.hlay_nstudies = QHBoxLayout(self.cont_nstudies)
        self.lab_nstudies = QLabel(f"Indicate the number of studies you wish to process:", self.cont_nstudies)
        self.cmb_nstudies = QComboBox(self.cont_nstudies)
        self.nstudies_options = ["Select"] + list(map(str, range(1, (os.cpu_count() // 2 + 1))))
        self.cmb_nstudies.addItems(self.nstudies_options)
        self.cmb_nstudies.currentTextChanged.connect(self.UI_Setup_TaskScheduler_FormUpdate)
        self.cmb_nstudies.currentTextChanged.connect(self.set_ncores_left)
        self.cmb_nstudies.currentTextChanged.connect(self.is_ready_to_run)
        self.hlay_nstudies.addWidget(self.lab_nstudies)
        self.hlay_nstudies.addWidget(self.cmb_nstudies)

        self.cont_filler = QWidget(self.grp_taskschedule)
        self.formlay_filler = QFormLayout(self.cont_filler)
        self.formlay_filler.addRow("Number of Cores to Allocate ||", QLabel("Filepaths to Analysis Directories"))

        self.cont_tasks = QWidget(self.grp_taskschedule)
        self.formlay_tasks = QFormLayout(self.cont_tasks)

        self.cont_progbars = QWidget(self.grp_taskschedule)
        self.formlay_progbars = QFormLayout(self.cont_progbars)

        # Need python lists to keep track of row additions/removals; findChildren's ordering is incorrect
        self.formlay_lineedits_list = []
        self.formlay_buttons_list = []
        self.formlay_cmbs_ncores_list = []
        self.formlay_cmbs_runopts_list = []
        self.formlay_nrows = 0
        self.formlay_progbars_list = []

        self.vlay_taskschedule.addWidget(self.lab_coresinfo)
        self.vlay_taskschedule.addWidget(self.lab_coresleft)
        self.vlay_taskschedule.addWidget(self.cont_nstudies)
        self.vlay_taskschedule.addWidget(self.cont_filler)
        self.vlay_taskschedule.addWidget(self.cont_tasks)
        self.vlay_taskschedule.addWidget(self.cont_progbars)
        self.vlay_taskschedule.addStretch(2)

        self.cmb_nstudies.setCurrentIndex(1)

    # Right side setup; this will have a text editor to display feedback coming from ExploreASL or any future watchers
    # that are installed. Also, the Run buttons will be set up here.
    def UI_Setup_TextFeedback_and_Executor(self):
        self.vlay_textoutput = QVBoxLayout(self.grp_textoutput)
        self.textedit_textoutput = QTextEdit(self.grp_textoutput)
        self.textedit_textoutput.setPlaceholderText("Processing Progress will appear within this window")

        self.vlay_textoutput.addWidget(self.textedit_textoutput)
        self.vlay_right.addWidget(self.btn_runExploreASL)

    # Rare exception of a UI function that is also technically a setter; this will dynamically alter the number of
    # rows present in the task scheduler form layout to allow for ExploreASL analysis of multiple studies at once
    def UI_Setup_TaskScheduler_FormUpdate(self, n_studies):
        if n_studies == "Select": return  # Don't do anything if the user selects Select again by accident
        n_studies = int(n_studies)
        diff = n_studies - self.formlay_nrows  # The difference between the current n_rows and n_studies

        # Addition of rows
        if diff > 0:
            for ii in range(diff):
                self.formlay_nrows += 1
                inner_cmb = QComboBox()
                inner_cmb.setMinimumWidth(140)
                inner_cmb.addItems(list(map(str, range(1, os.cpu_count() // 2 + 1))))
                inner_cmb.currentTextChanged.connect(self.set_ncores_left)
                inner_cmb.currentTextChanged.connect(self.set_ncores_selectable)
                inner_cmb.currentTextChanged.connect(self.set_nstudies_selectable)
                inner_le = DandD_FileExplorer2LineEdit()
                inner_le.setPlaceholderText("Select the analysis directory to your study")
                inner_le.textChanged.connect(self.is_ready_to_run)
                inner_btn = RowAwareQPushButton(self.formlay_nrows, "...")
                inner_btn.row_idx_signal.connect(self.set_analysis_directory)
                inner_cmb_procopts = QComboBox()
                inner_cmb_procopts.addItems(["Structural", "ASL", "Both", "Population"])
                inner_cmb_procopts.setCurrentIndex(2)
                inner_hbox = QHBoxLayout()
                inner_hbox.addWidget(inner_le)
                inner_hbox.addWidget(inner_btn)
                inner_hbox.addWidget(inner_cmb_procopts)
                inner_progbar = QProgressBar(orientation=Qt.Horizontal, value=0, maximum=100, minimum=0)

                # Update format layouts through addition of the appropriate row
                self.formlay_tasks.addRow(inner_cmb, inner_hbox)
                self.formlay_progbars.addRow(f"Study {inner_btn.row_idx}", inner_progbar)

                # Add widgets to their respective containers
                self.formlay_cmbs_ncores_list.append(inner_cmb)
                self.formlay_lineedits_list.append(inner_le)
                self.formlay_buttons_list.append(inner_btn)
                self.formlay_cmbs_runopts_list.append(inner_cmb_procopts)
                self.formlay_progbars_list.append(inner_progbar)

        # Removal of rows
        elif diff < 0:
            for ii in range(abs(diff)):
                row_to_remove = self.formlay_nrows - 1

                # Update format layouts through removal of the appropriate row
                self.formlay_tasks.removeRow(row_to_remove)
                self.formlay_progbars.removeRow(row_to_remove)

                # Remove widgets from their respective containers starting from the latest addition
                self.formlay_cmbs_ncores_list.pop()
                self.formlay_lineedits_list.pop()
                self.formlay_buttons_list.pop()
                self.formlay_cmbs_runopts_list.pop()
                self.formlay_progbars_list.pop()
                self.formlay_nrows -= 1

        # Adjust the number of cores selectable in each of the comboboxes
        self.set_ncores_left()
        self.set_ncores_selectable()
        self.set_nstudies_selectable()
        self.is_ready_to_run()

    # Function responsible for adjusting the label of how many cores are still accessible
    def set_ncores_left(self):
        self.ncores_left = os.cpu_count() // 2 - sum([int(cmb.currentText()) for cmb in self.formlay_cmbs_ncores_list])
        if self.ncores_left > 0:
            self.lab_coresleft.setText(f"You are permitted to set up to {self.ncores_left} more core(s)")
        elif self.ncores_left == 0:
            self.lab_coresleft.setText(f"No more cores are avaliable for allocation")
        else:
            self.lab_coresleft.setText(f"Something went terribly wrong")

    # Function responsible for adjusting the choices avaliable within each of the comboboxes of a given task row
    def set_ncores_selectable(self):
        self.ncores_left = os.cpu_count() // 2 - sum([int(cmb.currentText()) for cmb in self.formlay_cmbs_ncores_list])
        cores_left = self.ncores_left
        for box in self.formlay_cmbs_ncores_list:
            current_selection = int(box.currentText())
            max_cores_allowed = current_selection + cores_left
            for idx in range(box.count()):
                val_at_idx = int(box.itemText(idx))
                if val_at_idx <= max_cores_allowed:
                    box.model().item(idx).setEnabled(True)
                else:
                    box.model().item(idx).setEnabled(False)

    # Function responsible for adjusting the number of studies still permitted (assuming 1 core will be initially
    # allocated to it)
    def set_nstudies_selectable(self):
        self.ncores_left = os.cpu_count() // 2 - sum([int(cmb.currentText()) for cmb in self.formlay_cmbs_ncores_list])
        current_n_studies = int(self.cmb_nstudies.currentText())
        max_studies_allowed = current_n_studies + self.ncores_left
        for idx in range(self.cmb_nstudies.count()):
            val_at_idx = self.cmb_nstudies.itemText(idx)
            if not val_at_idx.isdigit():
                continue
            val_at_idx = int(val_at_idx)
            if val_at_idx <= max_studies_allowed:
                self.cmb_nstudies.model().item(idx).setEnabled(True)
            else:
                self.cmb_nstudies.model().item(idx).setEnabled(False)

    # Sets the text within each of the lineedit widgets of the task scheduler rows
    # noinspection PyCallByClass
    @Slot(int)
    def set_analysis_directory(self, row_idx):
        dir_path = QFileDialog.getExistingDirectory(self.cw,
                                                    "Select the analysis directory of your study",
                                                    self.parent().config["DefaultRootDir"],
                                                    QFileDialog.ShowDirsOnly)
        self.formlay_lineedits_list[row_idx - 1].setText(dir_path)

    # Define whether the run Explore ASL button should be enabled
    def is_ready_to_run(self):
        # print("Checking runnability integrity")
        checks = []
        for le in self.formlay_lineedits_list:
            directory = le.text()
            if os.path.exists(directory):
                if all([os.path.isdir(directory), len(glob(os.path.join(directory, "*Par*.json")))]):
                    checks.append(True)
                else:
                    checks.append(False)
            else:
                checks.append(False)

        if all(checks):
            self.btn_runExploreASL.setEnabled(True)
        else:
            self.btn_runExploreASL.setEnabled(False)

    # Based on signal outout, this receives messages from watchers and outputs text feedback to the user
    @Slot(str)
    def update_text(self, msg):
        self.textedit_textoutput.append(msg)

    # This slot receives a
    @Slot(int, int)
    def update_progressbar(self, val_to_inc_by, study_idx):
        print(f"update_progressbar received a signal from watcher {study_idx} to increase the progressbar value by"
              f"{val_to_inc_by}")
        selected_progbar: QProgressBar = self.formlay_progbars_list[study_idx]
        print(
            f"The progressbar's value before update: {selected_progbar.value()} "
            f"out of maximum {selected_progbar.maximum()}")
        selected_progbar.setValue(selected_progbar.value() + val_to_inc_by)
        print(
            f"The progressbar's value after update: {selected_progbar.value()} "
            f"out of maximum {selected_progbar.maximum()}")

    @Slot()
    def reactivate_runbtn(self):
        self.total_process_dbt += 1
        print(f"reactivate_runbtn received a signal and incremented the debt. "
              f"The debt at this time is: {self.total_process_dbt}")
        if self.total_process_dbt == 0:
            self.btn_runExploreASL.setEnabled(True)

    # This is the main function; prepares arguments; spawns workers; feeds in arguments to the workers during their
    # initialization; then begins the programs
    def run_Explore_ASL(self):
        print("%" * 40)
        translator = {"Structural": [1], "ASL": [2], "Both": [1, 2], "Population": [3]}
        self.workers = []
        self.watchers = []
        # Outer for loop; loops over the studies
        for study_idx, (box, path, run_opts, progressbar) in enumerate(zip(self.formlay_cmbs_ncores_list,
                                                                           self.formlay_lineedits_list,
                                                                           self.formlay_cmbs_runopts_list,
                                                                           self.formlay_progbars_list)):

            #########################################
            # INNER FOR LOOP - For a particular study
            #########################################
            # Create a container to keep a block of workers in for a particular study
            # Also create a debt counter to be fed to the watcher so that it can eventually disengage
            inner_worker_block = []
            debt = 0

            # %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
            # Step 1 - Prepare the workers for that study
            # Inner for loop: loops over the range of the num of cores within a study. Each core will be an iWorker
            for ii in range(box.count()):
                if ii < int(box.currentText()):
                    worker = ExploreASL_Worker(
                        self.parent().config["ExploreASLRoot"],  # The exploreasl filepath
                        glob(os.path.join(path.text(), "*Par*.json"))[0].replace('\\', '/'),  # The filepath to parms
                        1,  # Process the data
                        1,  # Skip the pause
                        ii + 1,  # iWorker
                        int(box.currentText()),  # nWorkers
                        translator[run_opts.currentText()]  # Processing options
                    )

                    inner_worker_block.append(worker)
                    debt -= 1
                    self.total_process_dbt -= 1

            # Add the block to the main workers argument
            self.workers.append(inner_worker_block)
            # %%%%%%%%%%%%%%%%%%%%%%
            # Step 2 - Make preparations to feed the appropriate arguments to the watcher
            parms_file = glob(os.path.join(path.text(), "*Par*.json"))[0]
            with open(parms_file) as f:
                parms = json.load(f)
                str_regex: str = parms["subject_regexp"]
                regex = re.compile(str_regex)
                sess_names = parms["SESSIONS"]
                if str_regex.startswith("^") or str_regex.endswith('$'):
                    str_regex = str_regex.strip('^$')

            # %%%%%%%%%%%%%%%%%%%%%%%%%
            # Step 3 - Create all lock directories in advance; this will give the watcher full oversight
            self.initialize_all_lock_dirs(analysis_dir=path.text(),
                                          regex=regex,
                                          run_options=run_opts.currentText(),
                                          session_names=sess_names)

            # %%%%%%%%%%%%%%%%%%%%%%%%%
            # Step 4 - Calculate the anticipated workload based on missing .STATUS files; adjust the progressbar's
            # maxvalue from that
            workload = self.calculate_anticipated_workload(parms, run_opts.currentText())
            if not workload:
                return
            progressbar.reset()
            progressbar.setMaximum(workload)
            progressbar.setMinimum(0)
            progressbar.setValue(0)
            del workload

            # %%%%%%%%%%%%%%%%%%%%%%%%%%%
            # Step 5 - Create a Watcher for that study
            watcher = ExploreASL_Watcher(target=path.text(),  # the analysis directory
                                         regex=str_regex,  # the regex used to recognize subjects
                                         watch_debt=debt,  # the debt used to determine when to stop watching
                                         study_idx=study_idx  # the identifier used to know which progressbar to signal
                                         )

            # %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
            # Step 6 - Set up watcher connections
            # Connect the watcher to signal to the text output
            watcher.signals.update_text_output_signal.connect(self.update_text)
            # Connect the watcher to signal to the progressbar
            watcher.signals.update_progbar_signal.connect(self.update_progressbar)

            # Finally, add the watcher to the container
            self.watchers.append(watcher)

            # %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
            # Step 7 - Set up worker connections
            # Worker connections setup within a study
            for worker in inner_worker_block:
                # Connect the finished signal to the watcher debt to help it understand when it should stop watching
                worker.signals.finished_processing.connect(watcher.increment_debt)
                # Connect the finished signal to the run btn reactivator so that the run button may be reactivated
                # via debt repayment counter
                worker.signals.finished_processing.connect(self.reactivate_runbtn)

        ######################################
        # THIS IS NOW OUTSIDE OF THE FOR LOOPS

        # self.watchers is nested at this point; we need to flatten it
        self.workers = list(chain(*self.workers))

        # Launch all threads in one go
        for runnable in self.workers + self.watchers:
            self.threadpool.start(runnable)

        # Disable for now after pressing; bad idea to accidentally allow a second click as it may cause system shutdown
        self.btn_runExploreASL.setEnabled(False)

    # Creates lock dirs where necessary in anticipation for assigning a watcher to the root lock directory
    @staticmethod
    def initialize_all_lock_dirs(analysis_dir, regex, run_options, session_names):
        """
        Convenience function for creating the lock directories in advance of a run such that a file system watcher
        could effectively be set at the root and detect any downstream changes
        :param analysis_dir: the root analysis directory of the study ex. User\\Study_Name\\analysis
        :param regex: the regex used to identify subjects
        :param run_options: the type of run (ex. ASL, Structural, Both, Population)
        :param session_names: the expected session names that should be encountered (ex. ASL_1, ASL_2, etc.)
        :return: Does not return anything
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
    @staticmethod
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

            for subject in study_subjects:
                has_flair_img = os.path.exists(os.path.join(analysis_directory, subject, "FLAIR.nii"))
                current_status_files = os.listdir(os.path.join(analysis_directory,
                                                               "lock", "xASL_module_Structural", subject,
                                                               "xASL_module_Structural"))
                if has_flair_img:
                    workload = default_workload + flair_workload
                else:
                    workload = default_workload

                # Filter out any anticipated status files that are already present in the lock dirs
                filtered_workload = set(workload).difference(set(current_status_files))
                numerical_representation = sum([workload_translator[stat_file] for stat_file in filtered_workload])
                structuralmod_dict[subject] = numerical_representation

            return structuralmod_dict

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
            for subject in study_subjects:
                for session in session_names:
                    current_status_files = os.listdir(os.path.join(analysis_directory, "lock", "xASL_module_ASL",
                                                                   subject, f"xASL_module_ASL_{session}"))
                    workload = default_workload
                    # Filter out any anticipated status files that are already present in the lock dirs
                    filtered_workload = set(workload).difference(set(current_status_files))
                    numerical_representation = sum([workload_translator[stat_file] for stat_file in filtered_workload])
                    aslmod_dict[subject][session] = numerical_representation

            return aslmod_dict

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
            current_status_files = os.listdir(os.path.join(analysis_directory, "lock", "xASL_module_Population",
                                                           "xASL_module_Population"))
            workload = default_workload
            filtered_workload = set(workload).difference(set(current_status_files))
            numerical_representation = sum([workload_translator[stat_file] for stat_file in filtered_workload])
            return numerical_representation

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
            struct_dict = get_structural_workload(analysis_dir, subjects, struct_dict)
            asl_dict = get_asl_workload(analysis_dir, subjects, sess_names, asl_dict)
            # pprint(struct_dict)
            # pprint(asl_dict)

            struct_totalworkload = sum(struct_dict.values())
            asl_totalworkload = {subject: sum(asl_dict[subject].values()) for subject in subjects}
            asl_totalworkload = sum(asl_totalworkload.values())
            print(f"Structural Calculated Workload: {struct_totalworkload}")
            print(f"ASL Calculated Workload: {asl_totalworkload}")
            return struct_totalworkload + asl_totalworkload

        elif run_options == "ASL":
            asl_dict = get_asl_workload(analysis_dir, subjects, sess_names, asl_dict)
            # pprint(asl_dict)
            asl_totalworkload = {subject: sum(asl_dict[subject].values()) for subject in subjects}
            asl_totalworkload = sum(asl_totalworkload.values())
            print(asl_totalworkload)
            return asl_totalworkload

        elif run_options == "Structural":
            struct_dict = get_structural_workload(analysis_dir, subjects, struct_dict)
            # pprint(struct_dict)
            struct_totalworkload = sum(struct_dict.values())
            print(struct_totalworkload)
            return struct_totalworkload

        elif run_options == "Population":
            pop_totalworkload = get_population_workload(analysis_dir)
            print(pop_totalworkload)
            return pop_totalworkload

        else:
            print("THIS SHOULD NEVER PRINT AS YOU HAVE SELECTED AN IMPOSSIBLE WORKLOAD OPTION")


class ExploreASL_WatcherSignals(QObject):
    """
    Defines the signals avaliable from a running watcher thread.
    """
    update_progbar_signal = Signal(int, int)
    update_text_output_signal = Signal(str)
    update_debt_signal = Signal(int)


# noinspection PyCallingNonCallable
class ExploreASL_Watcher(QRunnable):
    """
    Modified file system watcher. Will monitor the appearance of STATUS files within the lock dirs of the analysis
    directory. If it detects a STATUS file, it will emit signals to
    1) update the progress bars
    2) inform the text editor view of which STATUS file was made so as to give user feedback
    3) alter the process_debt variable such that the Run button may be re-enabled when the "run debt" is paid off
    """

    def __init__(self, target, regex, watch_debt, study_idx):
        super().__init__()
        self.signals = ExploreASL_WatcherSignals()
        self.dir_to_watch = os.path.join(target, "lock")
        self.session_regex = re.compile(regex)
        self.module_regex = re.compile('module_(ASL|Structural|Population)')
        self.watch_debt = watch_debt
        self.study_idx = study_idx

        self.pop_mod_started = False
        self.struct_mod_started = False
        self.asl_mod_started = False

        self.sessions_seen_struct = []
        self.sessions_seen_asl = []

        self.observer = Observer()
        self.event_handler = ExploreASL_EventHandler()
        self.event_handler.signals.inform_file_creation.connect(self.process_message)
        self.observer.schedule(event_handler=self.event_handler,
                               path=self.dir_to_watch,
                               recursive=True)
        self.stuct_status_file_translator = {
            "010_LinearReg_T1w2MNI.status": "T1w-image rigid-body registration to MNI population center",
            "060_Segment_T1w.status": "CAT12/SPM12 T1w-image segmentation",
            "080_Resample2StandardSpace.status": "T1w-image reslicing into MNI/common space",
            "090_GetVolumetrics.status": "GM, WM, & CSF volume calculation",
            "100_VisualQC_Structural.status": "image quality-control",
            "999_ready.status": "all submodules"
        }
        self.asl_status_file_translator = {
            "020_RealignASL.status": "motion correction and spike removal",
            "030_RegisterASL.status": "ASL series rigid-body registration to the T1w image",
            "040_ResampleASL.status": "ASL series reslicing to MNI space and mean control image creation",
            "050_PreparePV.status": "preparation of partial volume maps",
            "060_ProcessM0.status": "M0 image processing",
            "070_Quantification.status": "CBF quantification",
            "080_CreateAnalysisMask.status": "CBF threshold mask creation",
            "090_VisualQC_ASL.status": "image quality-control",
            "999_ready.status": "all submodules"
        }

        self.workload_translator = {
            # STRUCTURAL
            "010_LinearReg_T1w2MNI.status": 1,
            "020_LinearReg_FLAIR2T1w.status": 2,
            "030_Resample_FLAIR2T1w.status": 1,
            "040_Segment_FLAIR.status": 3,
            "050_LesionFilling.status": 1,
            "060_Segment_T1w.status": 10,
            "070_GetWMHvol.status": 1,
            "080_Resample2StandardSpace.status": 2,
            "090_GetVolumetrics.status": 1,
            "100_VisualQC_Structural.status": 1,
            # ASL
            "020_RealignASL.status": 1,
            "030_RegisterASL.status": 2,
            "040_ResampleASL.status": 1,
            "050_PreparePV.status": 1,
            "060_ProcessM0.status": 1,
            "070_Quantification.status": 2,
            "080_CreateAnalysisMask.status": 1,
            "090_VisualQC_ASL.status": 1,
            # POPULATION
            "010_CreatePopulationTemplates.status": 1,
            "020_CreateAnalysisMask.status": 1,
            "030_CreateBiasfield.status": 1,
            "040_GetDICOMStatistics.status": 1,
            "050_GetVolumeStatistics.status": 1,
            "060_GetMotionStatistics.status": 1,
            "070_GetROIstatistics.status": 20,
            "080_SortBySpatialCoV.status": 1,
            "090_DeleteAndZip.status": 1,
            "999_ready.status": 0
        }

        print(f"Initialized a watcher for the directory {self.dir_to_watch} and will communicate with the progressbar"
              f"at Python idx: {self.study_idx}")

    # Processes the information sent from the event hander and emits signals to update widgets in the main Executor
    @Slot(str)
    def process_message(self, created_path):
        print("\t" * 10 + f"PREPARE MSG HAS RECEIVED A MESSAGE: {created_path}")
        detected_session = self.session_regex.search(created_path)
        detected_module = self.module_regex.search(created_path)
        msg = None
        workload_val = None

        if os.path.isdir(created_path):  # Lock dir
            if detected_module.group(1) == "Structural" and not detected_session.group() in self.sessions_seen_struct:
                self.sessions_seen_struct.append(detected_session.group())
                msg = f"Structural Module has started for session: {detected_session.group()}"
            elif detected_module.group(1) == "ASL" and not detected_session.group() in self.sessions_seen_asl:
                self.sessions_seen_asl.append(detected_session.group())
                msg = f"ASL Module has started for session: {detected_session.group()}"
            elif detected_module.group(1) == "Population" and not self.pop_mod_started:
                self.pop_mod_started = True
                msg = f"Population Module has started"
            else:
                pass

        elif os.path.isfile(created_path):  # Status file
            basename = os.path.basename(created_path)
            if detected_module.group(1) == "Structural" and detected_session:
                msg = f"Completed {self.stuct_status_file_translator[basename]} in the Structural module " \
                      f"for session: {detected_session.group()}"
            elif detected_module.group(1) == "ASL" and detected_session:
                msg = f"Completed {self.asl_status_file_translator[basename]} in the ASL module " \
                      f"for session: {detected_session.group()}"
            elif detected_module.group(1) == "Population":
                msg = f"Completed {basename} in the Population module"

            workload_val = self.workload_translator[basename]

        else:
            print("Neither a file nor a directory was detected")

        # Emit the message to inform the user of the most recent progress
        if msg:
            self.signals.update_text_output_signal.emit(msg)

        # Emit the workload value associated with the completion of that status file as well as the study idx so that
        # the appropriate progressbar is updated
        if workload_val:
            self.signals.update_progbar_signal.emit(workload_val, self.study_idx)

    # Must use slots system, as it is thread-safe
    @Slot()
    def increment_debt(self):
        self.watch_debt += 1

    def run(self):
        self.observer.start()
        print("\t" * 10 + "THE OBSERVER HAS STARTED")
        while self.watch_debt < 0:
            sleep(10)
        print("THE OBSERVER HAS STOPPED")
        self.observer.stop()
        self.observer.join()
        print(f"QRUNNABLE WATCHER FOR {self.dir_to_watch} is shutting down")
        return


class ExploreASL_EventHanderSignals(QObject):
    """
    Defines the signals used by the EventHandler class
    """
    inform_file_creation = Signal(str)


class ExploreASL_EventHandler(FileSystemEventHandler):
    """
    The real watcher behind the scenes
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.signals = ExploreASL_EventHanderSignals()

    def on_created(self, event):
        self.signals.inform_file_creation.emit(event.src_path)


class RowAwareQPushButton(QPushButton):
    """
    A subset of QPushButton that has awareness of which row within Task Scheduler it is located in at all times. This
    is a convenience measure for easily communicating to self.set_analysis_directory and knowing which lineedit to
    alter.
    """
    row_idx_signal = Signal(int)

    def __init__(self, row_idx, text, parent=None):
        super().__init__(text=text, parent=parent)
        self.row_idx = row_idx

    def mousePressEvent(self, e):
        self.row_idx_signal.emit(self.row_idx)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    maker = xASL_ParmsMaker()
    maker.show()
    sys.exit(app.exec())
