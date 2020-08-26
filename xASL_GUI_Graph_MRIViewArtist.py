from PySide2.QtWidgets import *
from PySide2.QtGui import *
from PySide2.QtCore import *
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import seaborn as sns
import numpy as np
from nilearn import image
import os
import json
from glob import glob


class xASL_GUI_MRIViewArtist(QWidget):
    """
    Main Widget class to handle drawing operations around seaborn's scatterplot class as well as MRI slices
    """

    def __init__(self, parent):
        super().__init__(parent=parent)
        self.mainlay = QHBoxLayout(self)
        self.parent_cw = parent
        self.manager = parent.fig_manager

        # Key Variables
        self.analysis_dir = self.parent_cw.le_analysis_dir.text()
        with open(os.path.join(self.analysis_dir, "DataPar.json")) as parms_reader:
            parms = json.load(parms_reader)
            self.subject_regex = parms["subject_regexp"].strip("$^")

        self.qcbf_files = glob(os.path.join(self.analysis_dir, "Population", "qCBF_*.nii"))
        self.t1_files = glob(os.path.join(self.analysis_dir, "Population", "rT1_*.nii"))

        self.scatter_fig = plt.figure(num=0)
        self.scatter_canvas = FigureCanvas(self.scatter_fig)

        self.axial_fig, (self.axial_asl, self.axial_t1) = plt.subplots(nrows=1, ncols=2)
        self.axial_canvas = FigureCanvas(self.axial_fig)

        self.coronal_fig, (self.coronal_asl, self.coronal_t1) = plt.subplots(nrows=1, ncols=2)
        self.coronal_canvas = FigureCanvas(self.coronal_fig)

        self.vlay_mrifigs = QVBoxLayout()
        self.vlay_mrifigs.addWidget(self.axial_canvas)
        self.vlay_mrifigs.addWidget(self.coronal_canvas)
        self.mainlay.addWidget(self.scatter_canvas)
        self.mainlay.addLayout(self.vlay_mrifigs)



