from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import os
import sys
import json
from platform import platform
from glob import glob


class xASL_Executor(QMainWindow):
    def __init__(self, parent_win):
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
        self.setWindowIcon(QIcon(QPixmap("media/ExploreASL_logo.jpg")))
        # Main run button must be defined early, since connections will be dynamically made to it
        self.btn_runExploreASL = QPushButton("Run Explore ASL", self.cw, clicked=self.run_Explore_ASL)
        self.btn_runExploreASL.setEnabled(False)

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
        self.lab_coresinfo = QLabel(f"CPU Count: A total of {os.cpu_count()} processors are available on this machine",
                                    self.grp_taskschedule)
        self.ncores_left = os.cpu_count()
        self.lab_coresleft = QLabel(f"You are permitted to set up to {self.ncores_left} more core(s)")
        self.cont_nstudies = QWidget(self.grp_taskschedule)
        self.hlay_nstudies = QHBoxLayout(self.cont_nstudies)
        self.lab_nstudies = QLabel(f"Indicate the number of studies you wish to process:", self.cont_nstudies)
        self.cmb_nstudies = QComboBox(self.cont_nstudies)
        self.nstudies_options = ["Select"] + list(map(str, range(1, os.cpu_count() + 1)))
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
        # Need python lists to keep track of row additions/removals; findChildren's ordering is incorrect
        self.formlay_lineedits_list = []
        self.formlay_buttons_list = []
        self.formlay_comboboxes_list = []
        self.formlay_comboboxes_proc_list = []
        self.formlay_nrows = 0

        self.vlay_taskschedule.addWidget(self.lab_coresinfo)
        self.vlay_taskschedule.addWidget(self.lab_coresleft)
        self.vlay_taskschedule.addWidget(self.cont_nstudies)
        self.vlay_taskschedule.addWidget(self.cont_filler)
        self.vlay_taskschedule.addWidget(self.cont_tasks)
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
        if n_studies == "Select": return
        n_studies = int(n_studies)
        diff = n_studies - self.formlay_nrows  # The difference between the current n_rows and n_studies
        # print(f"n: {n_studies}\t diff: {diff}")
        # Addition of rows
        if diff > 0:
            for ii in range(diff):
                self.formlay_nrows += 1
                inner_cmb = QComboBox()
                inner_cmb.setMinimumWidth(140)
                inner_cmb.addItems(list(map(str, range(1, os.cpu_count() + 1))))
                inner_cmb.currentTextChanged.connect(self.set_ncores_left)
                inner_cmb.currentTextChanged.connect(self.set_ncores_selectable)
                inner_cmb.currentTextChanged.connect(self.set_nstudies_selectable)
                inner_le = QLineEdit(placeholderText="Select the analysis directory to your study")
                inner_le.textChanged.connect(self.is_ready_to_run)
                inner_btn = RowAwareQPushButton(self.formlay_nrows, "...")
                inner_btn.row_idx_signal.connect(self.set_analysis_directory)
                inner_cmb_procopts = QComboBox()
                inner_cmb_procopts.addItems(["Structural", "ASL", "Both"])
                inner_cmb_procopts.setCurrentIndex(2)
                inner_hbox = QHBoxLayout()
                inner_hbox.addWidget(inner_le)
                inner_hbox.addWidget(inner_btn)
                inner_hbox.addWidget(inner_cmb_procopts)
                self.formlay_tasks.addRow(inner_cmb, inner_hbox)
                self.formlay_comboboxes_list.append(inner_cmb)
                self.formlay_lineedits_list.append(inner_le)
                self.formlay_buttons_list.append(inner_btn)
                self.formlay_comboboxes_proc_list.append(inner_cmb_procopts)

            # print(f"LE: {[le.text() for le in self.formlay_lineedits_list]}\n"
            #       f"BTNS: {[btn.text() for btn in self.formlay_buttons_list]}")
            # print(f"Formlay nrows {self.formlay_nrows}")

        # Removal of rows
        elif diff < 0:
            for ii in range(abs(diff)):
                row_to_remove = self.formlay_nrows - 1
                # print(f"Removing row {row_to_remove}")
                self.formlay_tasks.removeRow(row_to_remove)
                self.formlay_comboboxes_list.pop()
                self.formlay_lineedits_list.pop()
                self.formlay_buttons_list.pop()
                self.formlay_comboboxes_proc_list.pop()
                self.formlay_nrows -= 1
            # print(f"LE: {[le.text() for le in self.formlay_lineedits_list]}\n"
            #       f"BTNS: {[btn.text() for btn in self.formlay_buttons_list]}")
            # print(f"Formlay nrows {self.formlay_nrows}")

        # Adjust the number of cores selectable in each of the comboboxes
        self.set_ncores_left()
        self.set_ncores_selectable()
        self.set_nstudies_selectable()

    # Function responsible for adjusting the label of how many cores are still accessible
    def set_ncores_left(self):
        self.ncores_left = os.cpu_count() - sum([int(cmb.currentText()) for cmb in self.formlay_comboboxes_list])
        if self.ncores_left > 0:
            self.lab_coresleft.setText(f"You are permitted to set up to {self.ncores_left} more core(s)")
        elif self.ncores_left == 0:
            self.lab_coresleft.setText(f"No more cores are avaliable for allocation")
        else:
            self.lab_coresleft.setText(f"Something went terribly wrong")

    # Function responsible for adjusting the choices avaliable within each of the comboboxes of a given task row
    def set_ncores_selectable(self):
        self.ncores_left = os.cpu_count() - sum([int(cmb.currentText()) for cmb in self.formlay_comboboxes_list])
        cores_left = self.ncores_left
        for box in self.formlay_comboboxes_list:
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
        self.ncores_left = os.cpu_count() - sum([int(cmb.currentText()) for cmb in self.formlay_comboboxes_list])
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
    @pyqtSlot(int)
    def set_analysis_directory(self, row_idx):
        dir_path = QFileDialog.getExistingDirectory(self.cw,
                                                    "Select the analysis directory of your study",
                                                    self.parent().config["DefaultAnalysisDir"],  # Default dir to start
                                                    QFileDialog.ShowDirsOnly)
        self.formlay_lineedits_list[row_idx - 1].setText(dir_path)

    # Define whether the run Explore ASL button should be enabled
    def is_ready_to_run(self):
        for le in self.formlay_lineedits_list:
            directory = le.text()
            print(os.path.exists(directory))
            print(os.path.isdir(directory))
            if os.path.exists(directory):
                if all([os.path.isdir(directory), len(glob(os.path.join(directory, "*Par*.json")))]):
                    self.btn_runExploreASL.setEnabled(True)
                else:
                    self.btn_runExploreASL.setEnabled(False)

    # This is the main function
    def run_Explore_ASL(self):
        pass


class RowAwareQPushButton(QPushButton):
    row_idx_signal = pyqtSignal(int)

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
