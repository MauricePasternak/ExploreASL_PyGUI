from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import os
import sys
import json
from glob import glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import seaborn as sns


class xASL_PostProc(QMainWindow):
    def __init__(self, parent_win=None):
        # Parent window is fed into the constructor to allow for communication with parent window devices
        super().__init__(parent=parent_win)
        if parent_win is not None:
            self.config = self.parent().config
        else:
            with open("ExploreASL_GUI_masterconfig.json") as f:
                self.config = json.load(f)

        # Window Size and initial visual setup
        self.setMinimumSize(1920, 1080)
        self.mainplot = MatplotlibWidget(self)
        self.setCentralWidget(self.mainplot)
        self.mainlay = QHBoxLayout(self.mainplot)
        self.setLayout(self.mainlay)
        self.setWindowTitle("Explore ASL - Parameter File Maker")
        self.setWindowIcon(QIcon(QPixmap("media/ExploreASL_logo.jpg")))

        self.UI_Setup_Docker()

    def UI_Setup_Docker(self):
        self.dock = QDockWidget("Plot settings", self)
        self.dock.setMinimumWidth(480)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock)
        self.cont_maindock = QWidget(self.dock)
        self.vlay_maindock = QVBoxLayout(self.cont_maindock)
        self.dock.setWidget(self.cont_maindock)
        # Set up the directory settings - what analysis folder
        self.grp_directories = QGroupBox("Directory settings", self.cont_maindock)
        self.formlay_directories = QFormLayout(self.grp_directories)
        self.le_analysis_dir = QLineEdit(self.parent().config["DefaultRootDir"], self.grp_directories)
        self.le_analysis_dir.textChanged.connect(self.set_formlay_options)
        self.cmb_atlas_selection = QComboBox(self.grp_directories)
        self.cmb_atlas_selection.addItems(["MNI", "Hammers"])
        self.cmb_pvc_selection = QComboBox(self.grp_directories)
        self.cmb_pvc_selection.addItems(["With Partial Volume Correction", "Without Partial Volume Correction"])
        self.cmb_stats_selection = QComboBox(self.grp_directories)
        self.cmb_stats_selection.addItems(["Mean", "Median", "Coefficient of Variation"])

        self.formlay_directories.addRow("Analysis Directory", self.le_analysis_dir)
        self.formlay_directories.addRow("Which Atlas to Utilize", self.cmb_atlas_selection)
        self.formlay_directories.addRow("Which Partial-Volume Stats to View", self.cmb_pvc_selection)
        self.formlay_directories.addRow("Which Statistic to View", self.cmb_stats_selection)


        self.vlay_maindock.addWidget(self.grp_directories)

    def set_formlay_options(self):
        if os.path.exists(os.path.join(self.le_analysis_dir.text(), "Population", "Stats")):
            atlas = {"MNI": "MNI_Structural", "Hammers": "Hammers"}[self.cmb_atlas_selection.currentText()]
            pvc = {"With Partial Volume Correction": "PVC2",
                   "Without Partial Volume Correction": "PVC0"}[self.cmb_pvc_selection.currentText()]
            stat = {"Mean": "mean", "Median": "median",
                    "Coefficient of Variation": "CoV"}[self.cmb_stats_selection.currentText()]


class MatplotlibWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        fig = plt.Figure(figsize=(7, 5), dpi=65, facecolor=(1, 1, 1), edgecolor=(0, 0, 0))
        self.canvas = FigureCanvas(fig)
        self.toolbar = NavigationToolbar(self.canvas, self)
        lay = QVBoxLayout(self)
        lay.addWidget(self.toolbar)
        lay.addWidget(self.canvas)

    def gui_draw(self):
        tips = sns.load_dataset("tips")