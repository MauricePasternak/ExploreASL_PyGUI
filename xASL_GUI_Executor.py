from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import os
import sys
import json
from platform import platform


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

        self.UI_Setup_Layouts_and_Groups()
        self.UI_Setup_TaskScheduler()

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
        self.lab_coresinfo = QLabel(f"CPU Count: A total of {os.cpu_count()} processors are avaliable on this machine",
                                    self.grp_taskschedule)
        self.coresleft = os.cpu_count() - 2
        self.lab_coresleft = QLabel(f"You are permitted to set up to {self.coresleft} more core(s)")
        self.cont_nstudies = QWidget(self.grp_taskschedule)
        self.hlay_nstudies = QHBoxLayout(self.cont_nstudies)
        self.lab_nstudies = QLabel(f"Indicate the number of studies you wish to process:", self.cont_nstudies)
        self.cmb_nstudies = QComboBox(self.cont_nstudies)
        self.nstudies_options = list(map(str, range(1, os.cpu_count() + 1)))
        self.cmb_nstudies.addItems(self.nstudies_options)
        self.cmb_nstudies.currentTextChanged.connect(self.UI_Setup_TaskScheduler_FormUpdate)
        self.hlay_nstudies.addWidget(self.lab_nstudies)
        self.hlay_nstudies.addWidget(self.cmb_nstudies)

        self.cont_tasks = QWidget(self.grp_taskschedule)
        self.formlay_tasks = QFormLayout(self.cont_tasks)
        self.formlay_tasks.addRow("Number of Cores to Allocate |", QLabel("Path to Analysis Directory"))
        self.UI_Setup_TaskScheduler_FormUpdate(1)

        self.vlay_taskschedule.addWidget(self.lab_coresinfo)
        self.vlay_taskschedule.addWidget(self.lab_coresleft)
        self.vlay_taskschedule.addWidget(self.cont_nstudies)
        self.vlay_taskschedule.addWidget(self.cont_tasks)
        self.vlay_taskschedule.addStretch(2)

    def UI_Setup_TaskScheduler_FormUpdate(self, n):
        n = int(n)
        diff = n - self.formlay_tasks.rowCount() + 1
        print(diff)

        if diff > 0:
            for ii in range(diff):
                inner_hbox = QHBoxLayout()
                inner_le = QLineEdit(self.cont_tasks, placeholderText="Select the path to the analysis directory")
                inner_btn = QPushButton("...", self.cont_tasks, clicked=self.set_analysis_dir)
                inner_hbox.addWidget(inner_le)
                inner_hbox.addWidget(inner_btn)
                inner_combo = QComboBox(self.cont_tasks)
                inner_combo.addItems(list(map(str, range(1, os.cpu_count() - 2))))
                self.formlay_tasks.addRow(inner_combo, inner_hbox)


        else:
            for ii in range(diff * -1):
                self.formlay_tasks.removeRow(self.formlay_tasks.rowCount() - 1)


    def set_analysis_dir(self):
        pass


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    maker = xASL_ParmsMaker()
    maker.show()
    sys.exit(app.exec())
