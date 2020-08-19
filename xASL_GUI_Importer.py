from PySide2.QtWidgets import *
from PySide2.QtGui import *
from PySide2.QtCore import *
from xASL_GUI_HelperClasses import DandD_FileExplorer2LineEdit
from xASL_GUI_ASL2BIDS import get_dicom_directories, asl2bids_onedir, create_import_summary
from glob import iglob
from tdda import rexpy
from pprint import pprint
from collections import OrderedDict
from more_itertools import divide
import json
import os
import shutil
import re
import sys
import platform
import subprocess


class Importer_WorkerSignals(QObject):
    """
    Class for handling the signals sent by an ExploreASL worker
    """
    signal_send_summaries = Signal(list)  # Signal sent by worker to process the summaries of imported files
    signal_send_errors = Signal(list)  # Signal sent by worker to indicate the file where something has failed


class Importer_Worker(QRunnable):
    """
    Worker thread for running the import for a particular group.
    """

    def __init__(self, dcm_dirs, config):
        self.dcm_dirs = dcm_dirs
        self.import_config = config
        super().__init__()
        self.signals = Importer_WorkerSignals()
        print(f"Initialized Worker with args {self.dcm_dirs}\n{self.import_config}")
        self.import_summaries = []
        self.failed_runs = []

    # This is called by the threadpool during threadpool.start(worker)
    def run(self):
        for dicom_dir in self.dcm_dirs:
            result, last_job, import_summary = asl2bids_onedir(dcm_dir=dicom_dir, config=self.import_config)
            if result:
                self.import_summaries.append(import_summary)
            else:
                self.failed_runs.append((dicom_dir, last_job))

        self.signals.signal_send_summaries.emit(self.import_summaries)
        if len(self.failed_runs) > 0:
            self.signals.signal_send_errors.emit(self.failed_runs)


# noinspection PyCallingNonCallable
class xASL_GUI_Importer(QMainWindow):
    def __init__(self, parent_win=None):
        # Parent window is fed into the constructor to allow for communication with parent window devices
        super().__init__(parent=parent_win)
        if parent_win is not None:
            self.config = self.parent().config
        else:
            with open("ExploreASL_GUI_masterconfig.json") as config_reader:
                self.config = json.load(config_reader)

        # Misc and Default Attributes
        self.labfont = QFont()
        self.labfont.setPointSize(16)
        self.rawdir = ''
        self.folderhierarchy = ['', '', '']
        self.tokenordering = ['', '', '']
        self.subject_regex = None
        self.session_regex = None
        self.scan_regex = None
        self.session_aliases = OrderedDict()
        self.scan_aliases = dict.fromkeys(["ASL4D", "T1", "M0", "FLAIR", "WMH_SEGM"])
        self.cmb_sessionaliases_dict = {}
        self.threadpool = QThreadPool()
        self.import_summaries = []
        self.failed_runs = []

        # Window Size and initial visual setup
        self.setMinimumSize(600, 720)
        self.resize(540, 720)
        self.setWindowTitle("ExploreASL ASL2BIDS Importer")
        self.cw = QWidget(self)
        self.setCentralWidget(self.cw)
        self.mainlay = QVBoxLayout(self.cw)
        self.mainsplit = QSplitter(Qt.Vertical, self.cw)
        self.cw.setLayout(self.mainlay)
        self.mainlay.addWidget(self.mainsplit)

        self.Setup_UI_UserSpecifyDirStuct()
        self.Setup_UI_UserSpecifyScanAliases()
        self.Setup_UI_UserSpecifySessionAliases()

        self.btn_run_importer = QPushButton("Run ASL2BIDS", self.cw, clicked=self.run_importer)
        self.btn_run_importer.setFont(self.labfont)
        self.btn_run_importer.setFixedHeight(50)
        self.mainsplit.addWidget(self.btn_run_importer)

        self.mainsplit.setSizes([150, 250, 300, 50])

    def Setup_UI_UserSpecifyDirStuct(self):
        self.grp_dirstruct = QGroupBox("Specify Directory Structure", self.cw)
        self.grp_dirstruct.setMaximumHeight(225)
        self.vlay_dirstruct = QVBoxLayout(self.grp_dirstruct)

        # First specify the root directory
        self.formlay_rootdir = QFormLayout()
        self.hlay_rootdir = QHBoxLayout()
        self.le_rootdir = DandD_FileExplorer2LineEdit(self.grp_dirstruct)
        self.le_rootdir.setPlaceholderText("Drag and drop your study's raw directory here")
        self.le_rootdir.setReadOnly(True)
        self.le_rootdir.textChanged.connect(self.set_rootdir_variable)
        self.btn_rootdir = QPushButton("...", self.grp_dirstruct, clicked=self.set_import_root_directory)
        self.hlay_rootdir.addWidget(self.le_rootdir)
        self.hlay_rootdir.addWidget(self.btn_rootdir)
        self.formlay_rootdir.addRow("Raw Root Directory", self.hlay_rootdir)

        # Next specify the QLabels that can be dragged to have their text copied elsewhere
        self.hlay_placeholders = QHBoxLayout()
        self.lab_holdersub = DraggableLabel("Subject", self.grp_dirstruct)
        self.lab_holdersess = DraggableLabel("Session", self.grp_dirstruct)
        self.lab_holderscan = DraggableLabel("Scan", self.grp_dirstruct)
        self.lab_holderdummy = DraggableLabel("Dummy", self.grp_dirstruct)
        for lab in [self.lab_holdersub, self.lab_holdersess, self.lab_holderscan, self.lab_holderdummy]:
            self.hlay_placeholders.addWidget(lab)

        # Next specify the QLineEdits that will be receiving the dragged text
        self.hlay_receivers = QHBoxLayout()
        self.lab_rootlabel = QLabel("raw", self)
        self.lab_rootlabel.setFont(self.labfont)
        self.levels = {}
        for idx, (level, func) in enumerate(zip(["Level1", "Level2", "Level3", "Level4", "Level5"],
                                                [self.get_nth_level_dirs] * 5)):
            le = DandD_Label2LineEdit(self, self.grp_dirstruct, idx)
            le.modified_text.connect(self.get_nth_level_dirs)
            le.textChanged.connect(self.update_sibling_awareness)
            self.levels[level] = le

        self.hlay_receivers.addWidget(self.lab_rootlabel)
        if platform.system() == "Windows":
            separator = '\\'
        else:
            separator = '/'
        lab_sep = QLabel(separator, self.grp_dirstruct)
        lab_sep.setFont(self.labfont)
        self.hlay_receivers.addWidget(lab_sep)
        for ii, level in enumerate(self.levels.values()):
            level.setFont(self.labfont)
            self.hlay_receivers.addWidget(level)
            if ii < 4:
                lab_sep = QLabel(separator, self.grp_dirstruct)
                lab_sep.setFont(self.labfont)
                self.hlay_receivers.addWidget(lab_sep)

        # Include the button that will clear the current structure for convenience
        self.btn_clear_receivers = QPushButton("Clear the fields", self.grp_dirstruct, clicked=self.clear_receivers)

        # Organize layouts
        self.vlay_dirstruct.addLayout(self.formlay_rootdir, 1)
        self.vlay_dirstruct.addLayout(self.hlay_placeholders, 2)
        self.vlay_dirstruct.addLayout(self.hlay_receivers, 2)
        self.vlay_dirstruct.addWidget(self.btn_clear_receivers, 2)

        self.mainsplit.addWidget(self.grp_dirstruct)

    def Setup_UI_UserSpecifyScanAliases(self):
        # Next specify the scan aliases
        self.grp_scanaliases = QGroupBox("Specify Scan Aliases", self.cw)
        self.cmb_scanaliases_dict = dict.fromkeys(["ASL4D", "T1", "M0", "FLAIR", "WMH_SEGM"])
        self.formlay_scanaliases = QFormLayout(self.grp_scanaliases)
        for description, scantype in zip(["ASL scan alias:\n(Mandatory)", "T1 scan alias:\n(Mandatory)",
                                          "M0 scan alias:\n(Optional)", "FLAIR scan alias:\n(Optional)",
                                          "WHM Segmentation image alias:\n(Optional)"],
                                         self.cmb_scanaliases_dict.keys()):
            cmb = QComboBox(self.grp_scanaliases)
            cmb.addItems(["Select an alias"])
            cmb.currentTextChanged.connect(self.update_scan_aliases)
            self.cmb_scanaliases_dict[scantype] = cmb
            self.formlay_scanaliases.addRow(description, cmb)

        self.mainsplit.addWidget(self.grp_scanaliases)

    def Setup_UI_UserSpecifySessionAliases(self):
        # Define the groupbox and its main layout
        self.grp_sessionaliases = QGroupBox("Specify Session Aliases and Ordering", self.cw)
        self.vlay_sessionaliases = QVBoxLayout(self.grp_sessionaliases)
        self.scroll_sessionaliases = QScrollArea(self.grp_sessionaliases)
        self.cont_sessionaliases = QWidget()
        self.scroll_sessionaliases.setWidget(self.cont_sessionaliases)
        self.scroll_sessionaliases.setWidgetResizable(True)

        # Arrange widgets and layouts
        self.le_sessionaliases_dict = dict()
        self.formlay_sessionaliases = QFormLayout(self.cont_sessionaliases)
        self.vlay_sessionaliases.addWidget(self.scroll_sessionaliases)
        self.mainsplit.addWidget(self.grp_sessionaliases)

    def clear_receivers(self):
        for le in self.levels.values():
            le.clear()

    # Purpose of this function is to set the directory of the root path lineedit based on the adjacent pushbutton
    @Slot()
    def set_import_root_directory(self):
        dir_path = QFileDialog.getExistingDirectory(QFileDialog(),
                                                    "Select the raw directory of your study",
                                                    self.parent().config["DefaultRootDir"],
                                                    QFileDialog.ShowDirsOnly)
        if os.path.exists(dir_path):
            self.le_rootdir.setText(dir_path)

    # Purpose of this function is to change the value of the rawdir attribute based on the current text
    @Slot()
    def set_rootdir_variable(self):
        self.rawdir = self.le_rootdir.text()

    # Checks if any of subjects, sessions, or scans needs resetting
    def check_if_reset_needed(self):
        used_directories = [le.text() for le in self.levels.values()]
        # If subjects is not in the currently-specified structure and the regex has been already set
        if "Subject" not in used_directories and self.subject_regex is not None:
            self.subject_regex = None

        # If sessions is not in the currently-specified structure and the regex has been already set
        if "Session" not in used_directories and self.session_regex is not None:
            self.session_regex = None
            self.session_aliases.clear()
            self.reset_session_alias_cmbs()  # This clears the sessionaliases dict and the widgets

        if "Scan" not in used_directories and self.scan_regex is not None:
            self.scan_regex = None
            self.scan_aliases = dict.fromkeys(["ASL4D", "T1", "M0", "FLAIR", "WMH_SEGM"])
            self.reset_scan_alias_cmbs(basenames=[])

    def get_nth_level_dirs(self, dir_type: str, level: int):
        """
        :param dir_type: whether this is a subject, session, or scan
        :param level: which lineedit, in python index terms, emitted this signal
        """
        # Requirements to proceed
        if any([self.rawdir == '',  # Raw dir must be specified
                not os.path.exists(self.rawdir),  # Raw dir must exist
                os.path.basename(self.rawdir) != 'raw',  # Raw dir's basename must be raw
                ]):
            return

        # Check if a reset is needed
        self.check_if_reset_needed()

        # If this was a clearing, the dir_type will be an empty string and the function should exit after any resetting
        # has been performed
        if dir_type == '':
            return

        # Get the directories at the depth according to which lineedit's text was changed
        dir_tuple = ["*"] * (level + 1)
        path = os.path.join(self.rawdir, *dir_tuple)
        try:
            directories, basenames = zip(*[(directory, os.path.basename(directory)) for directory in iglob(path)
                                           if os.path.isdir(directory)])
        except ValueError:
            QMessageBox.warning(self,
                                "Impossible directory depth",
                                "The directory depth you've indicated does not have directories present at that level."
                                " Cancelling operation.",
                                QMessageBox.Ok)
            self.clear_nth_level_lineedit(level)
            return

        # Do not proceed if no directories were found and clear the linedit that emitted the textChanged signal
        if len(directories) == 0:
            idx = list(self.levels.keys())[level]
            print(f"idx: {idx}")
            self.levels[idx].clear()
            return

        # Otherwise, make the appropriate adjustment depending on which label was dropped in
        if dir_type == "Subject":
            self.subject_regex = self.inferregex(list(basenames))
            print(f"Subject regex: {self.subject_regex}")
            del directories, basenames

        elif dir_type == "Session":
            self.session_regex = self.inferregex(list(set(basenames)))
            print(f"Session regex: {self.session_regex}")
            self.update_session_aliases(basenames=list(set(basenames)))
            del directories, basenames

        elif dir_type == "Scan":
            self.scan_regex = self.inferregex(list(set(basenames)))
            print(f"Scan regex: {self.scan_regex}")
            self.reset_scan_alias_cmbs(basenames=list(set(basenames)))
            del directories, basenames

        elif dir_type == "Dummy":
            del directories, basenames
            return

        else:
            del directories, basenames
            print("Error. This should never print")
            return

    def clear_nth_level_lineedit(self, level):
        list(self.levels.values())[level].clear()

    # Purpose of this function is to reset all the comboboxes of the scans section and repopulate them with new options
    def reset_scan_alias_cmbs(self, basenames):
        # print(f"INSIDE RESET SCAN ALIAS CMBS with basenames: {basenames}")
        for key, cmb in self.cmb_scanaliases_dict.items():
            # print(f"Setting for key: {key} and cmb {cmb}")
            cmb.currentTextChanged.disconnect(self.update_scan_aliases)
            cmb.clear()
            cmb.addItems(["Select an alias"] + basenames)
            cmb.currentTextChanged.connect(self.update_scan_aliases)

    # Convenience function for resetting all the lineedits for the session aliases
    def reset_session_alias_cmbs(self):
        for idx in range(self.formlay_sessionaliases.rowCount()):
            self.formlay_sessionaliases.removeRow(0)
        self.le_sessionaliases_dict.clear()
        self.cmb_sessionaliases_dict.clear()

    # Purpose of this function is to update the global attribute for the scan aliases as the comboboxes are selected
    def update_scan_aliases(self):
        print("INSIDE UPDATE_SCAN_ALIASES")
        for key, value in self.cmb_scanaliases_dict.items():
            if value.currentText() != "Select an alias":
                self.scan_aliases[key] = value.currentText()
            else:
                self.scan_aliases[key] = None

    # Purpose of this function is to update the lineedits of the sessions section and repopulate
    def update_session_aliases(self, basenames):
        # If this is an update, remove the previous widgets and clear the dict
        if len(self.le_sessionaliases_dict) > 0:
            self.reset_session_alias_cmbs()

        # Generate the new dict, populate the format layout, and add the lineedits to the dict
        self.le_sessionaliases_dict = dict.fromkeys(basenames)
        self.cmb_sessionaliases_dict = dict.fromkeys(basenames)

        for ii, key in enumerate(self.le_sessionaliases_dict):
            hlay = QHBoxLayout()
            cmb = QComboBox()
            nums_to_add = [str(num) for num in range(1, len(self.le_sessionaliases_dict) + 1)]
            cmb.addItems(nums_to_add)
            cmb.setCurrentIndex(ii)
            le = QLineEdit()
            le.setPlaceholderText("(Optional) Specify the alias for this session")
            hlay.addWidget(le)
            hlay.addWidget(cmb)

            self.formlay_sessionaliases.addRow(key, hlay)
            self.le_sessionaliases_dict[key] = le
            self.cmb_sessionaliases_dict[key] = cmb

    # Convenience function for returning the regex string, provided a list of directories
    @staticmethod
    def inferregex(dirs):
        extractor = rexpy.Extractor(dirs)
        extractor.extract()
        regex = extractor.results.rex[0]
        return regex

    # Convenience function for updating
    @Slot()
    def update_sibling_awareness(self):
        current_texts = [le.text() for le in self.levels.values()]
        for le in self.levels.values():
            le.sibling_awareness = current_texts

    def is_ready_import(self):
        pass

    def set_widgets_on_or_off(self, state):
        self.btn_run_importer.setEnabled(state)
        for le in self.levels.values():
            le.setEnabled(state)


    # Returns the directory structure in preparation of running the import
    def get_directory_structure(self):
        dirnames = [le.text() for le in self.levels.values()]
        valid_dirs = []
        encountered_nonblank = False
        # Iterate backwards to remove false
        for name in reversed(dirnames):
            # Cannot have blank lines existing between the important directories
            if name == '' and encountered_nonblank:
                QMessageBox.warning(QMessageBox(),
                                    "Invalid directory structure entered",
                                    "You must indicate filler directories occuring between"
                                    "\nSubject/Session/Scan directories using the Dummy label provided",
                                    QMessageBox.Ok)
                return False, []
            elif name == '' and not encountered_nonblank:
                continue
            else:
                encountered_nonblank = True
                valid_dirs.append(name)

        # Sanity check for false user input
        if any(["Subject" not in valid_dirs,
                "Scan" not in valid_dirs]):
            QMessageBox.warning(self,
                                "Invalid directory structure entered",
                                "A minimum of Session and Scan directories must be present in your study for"
                                "ExploreASL to import data correctly.")
            return False, []

        valid_dirs = list(reversed(valid_dirs))
        # print(valid_dirs)
        return True, valid_dirs

    # Sanity check for false user input in specifying scan aliases
    def get_scan_aliases(self):
        try:
            if any([self.scan_aliases["ASL4D"] is None,
                    self.scan_aliases["T1"] is None]):
                QMessageBox.warning(self,
                                    "Invalid scan aliases entered",
                                    "At minimum, the aliases corresponding to the ASL and T1-weighted scans "
                                    "should be specified",
                                    QMessageBox.Ok)
                return False, None
        except KeyError as e:
            print(f'ENCOUNTERED KEYERROR: {e}')
            return False, None

        # Filter out scans that have None to avoid problems down the line
        scan_aliases = {key: value for key, value in self.scan_aliases.items() if value is not None}

        return True, scan_aliases

    # Returns the dictionary
    def get_session_aliases(self):

        session_aliases = OrderedDict()

        # If the session aliases dict is empty, simply return the empty dict, as sessions are not mandatory to outline
        if len(self.cmb_sessionaliases_dict) == 0:
            return True, session_aliases

        # First, make sure that every number is unique:
        current_orderset = [cmb.currentText() for cmb in self.cmb_sessionaliases_dict.values()]
        if len(current_orderset) != len(set(current_orderset)):
            QMessageBox.warning(self,
                                "Invalid sessions alias ordering entered",
                                "Please check for accidental doublings",
                                QMessageBox.Ok)

        basename_keys = list(self.le_sessionaliases_dict.keys())
        aliases = list(le.text() for le in self.le_sessionaliases_dict.values())
        orders = list(cmb.currentText() for cmb in self.cmb_sessionaliases_dict.values())

        print(f"basename_keys: {basename_keys}")
        print(f"aliases: {aliases}")
        print(f"orders: {orders}")

        for num in range(1, len(orders) + 1):
            idx = orders.index(str(num))
            current_alias = aliases[idx]
            current_basename = basename_keys[idx]
            if current_alias == '':
                session_aliases[current_basename] = f"ASL_{num}"
            else:
                session_aliases[current_basename] = current_alias

        return True, session_aliases

    def get_import_parms(self):
        import_parms = {}.fromkeys(["Regex", "Directory Structure", "Scan Aliases", "Ordered Session Aliases"])
        # Get the directory structure, the scan aliases, and the session aliases
        directory_status, valid_directories = self.get_directory_structure()
        scanalias_status, scan_aliases = self.get_scan_aliases()
        sessionalias_status, session_aliases = self.get_session_aliases()
        if any([self.subject_regex == '',  # Subject regex must be established
                self.scan_regex == '',  # Scan regex must be established
                not directory_status,  # Getting the directory structure must have been successful
                not scanalias_status,  # Getting the scan aliases must have been successful
                not sessionalias_status  # Getting the session aliases must have been successful
                ]): return None

        # Otherwise, green light to create the import parameters
        import_parms["RawDir"] = self.le_rootdir.text()
        import_parms["Regex"] = [self.subject_regex, self.session_regex, self.scan_regex]
        import_parms["Directory Structure"] = valid_directories
        import_parms["Scan Aliases"] = scan_aliases
        import_parms["Ordered Session Aliases"] = session_aliases

        # Save a copy of the import parms to the raw directory in question
        with open(os.path.join(self.le_rootdir.text(), "ImportConfig.json"), 'w') as w:
            json.dump(import_parms, w, indent=3)

        return import_parms

    @Slot(list)
    def create_import_summary_file(self, signalled_summaries):

        self.import_summaries.extend(signalled_summaries)
        self.n_import_workers -= 1

        if self.n_import_workers > 0 or self.import_parms is None:
            return

        # Re-enable widgets
        self.set_widgets_on_or_off(state=True)

        # Create the import summary
        create_import_summary(import_summaries=self.import_summaries, config=self.import_parms)

    @Slot(list)
    def create_failed_runs_summary_file(self, failed_runs):
        self.failed_runs.extend(failed_runs)

        if self.n_import_workers > 0 or self.import_parms is None:
            return

        analysis_dir = os.path.join(os.path.dirname(self.import_parms["RawDir"]), "analysis")
        with open(os.path.join(analysis_dir, "import_summary_failed.json")) as failed_writer:
            json.dump(dict(failed_runs), failed_writer, indent=3)


    def run_importer(self):
        # Set (or reset if this is another run) the essential variables
        self.n_import_workers = 0
        self.import_parms = None
        workers = []

        # Disable the run button to prevent accidental re-runs
        self.set_widgets_on_or_off(state=False)

        # Ensure the dcm2niix path is visible
        os.chdir(os.path.join(self.config["ScriptsDir"], f"DCM2NIIX_{platform.system()}"))

        # Get the import parameters
        self.import_parms = self.get_import_parms()
        if self.import_parms is None:
            return

        # Get the dicom directories
        dicom_dirs = get_dicom_directories(config=self.import_parms)

        # Create workers
        dicom_dirs = list(divide(4, dicom_dirs))
        for ddirs in dicom_dirs:
            worker = Importer_Worker(ddirs, self.import_parms)
            worker.signals.signal_send_summaries.connect(self.create_import_summary_file)
            worker.signals.signal_send_errors.connect(self.create_failed_runs_summary_file)
            workers.append(worker)
            self.n_import_workers += 1

        # Launch them
        for worker in workers:
            self.threadpool.start(worker)


class DraggableLabel(QLabel):
    """
    Modified QLabel to support dragging out the text content
    """

    def __init__(self, text='', parent=None):
        super(DraggableLabel, self).__init__(parent)
        self.setText(text)
        self.setStyleSheet("border-style: solid;"
                           "border-width: 2px;"
                           "border-color: black;"
                           "border-radius: 10px;"
                           "background-color: white;")
        font = QFont()
        font.setPointSize(16)
        self.setFont(font)
        self.setMinimumHeight(75)
        self.setMaximumHeight(100)
        self.setAlignment(Qt.AlignCenter)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.pos()

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            return
        if (event.pos() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            return
        drag = QDrag(self)
        mimedata = QMimeData()
        mimedata.setText(self.text())
        drag.setMimeData(mimedata)
        drag.setHotSpot(event.pos())
        drag.exec_(Qt.CopyAction | Qt.MoveAction)


class DandD_Label2LineEdit(QLineEdit):
    """
    Modified QLineEdit to support accepting text drops from a QLabel with Drag enabled
    """

    modified_text = Signal(str, int)

    def __init__(self, superparent, parent=None, identification=None):
        super().__init__(parent)

        self.setAcceptDrops(True)
        self.setReadOnly(True)
        self.superparent = superparent  # This is the Importer Widget itself
        self.sibling_awareness = ['', '', '', '', '']
        self.id = identification
        self.textChanged.connect(self.modifiedtextChanged)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasText():
            if all([event.mimeData().text() not in self.sibling_awareness,
                    self.superparent.le_rootdir.text() != '']) or event.mimeData().text() == "Dummy":
                event.accept()

        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if event.mimeData().hasText():
            if all([event.mimeData().text() not in self.sibling_awareness,
                    self.superparent.le_rootdir.text() != '']) or event.mimeData().text() == "Dummy":
                event.accept()
                event.setDropAction(Qt.CopyAction)
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasText():
            if all([event.mimeData().text() not in self.sibling_awareness,
                    self.superparent.le_rootdir.text() != '']) or event.mimeData().text() == "Dummy":
                event.accept()
                self.setText(event.mimeData().text())
        else:
            event.ignore()

    def modifiedtextChanged(self):
        self.modified_text.emit(self.text(), self.id)
