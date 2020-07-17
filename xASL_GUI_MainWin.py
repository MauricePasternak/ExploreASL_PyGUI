from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from xASL_GUI_ParmsMaker import xASL_ParmsMaker, DirectoryDragDrop_ListWidget
import os
import sys
import json
from platform import platform


# Explore ASL Main Window
# by Maurice Pasternak @ 2020
# %%%%%%%%%%%%%%%%%%%%%%%%%%%
# Quick Preface of function nomenclature for future developers
# %%%%%%%%%%%%%%%%%%%%%%%%%%%
# UI_   --> the function is associated with building the visual interface of the GUI or connecting widgets with each
#           other; there should be minimal setting of functional attributes, processing, etc. being done here
# get_  --> the function is associated with retrieving a value
# set_  --> the function is associated with setting a value; fields and attributes are manipulated in the process
# load_ --> the function is associated with retrieving data from a file; fields and attributes may or may not be set
#           in the process
# save_ --> the function is associated with saving parameters and variable to a file
# show_ --> the function is associated with making certain widgets or widget elements visible
# on_off_ --> the function is associated purely with enabling/disabling widgets or their elements
#
# Some helpful prefix shortcuts to know:
#  act = Action; btn = PushButton; cmb = ComboBox; cont = Widget/container; dock = DockWidget; formlay = Form Layout
#  hlay = horizontal Layout; le = LineEdit; lst = ListWidget;
#  spinbox = DoubleSpinBox; vlay = vertical Layout


class xASL_MainWin(QMainWindow):
    def __init__(self, config=None):
        # Load in the master config file if it exists; otherwise, make it
        if config is None:
            self.get_config()
        else:
            self.config = config
        super().__init__()
        # Window Size and initial visual setup
        self.setMinimumSize(1080, 480)
        self.cw = QWidget(self)
        self.setCentralWidget(self.cw)
        # Main Icon setup
        self.icon_main = QIcon(QPixmap("media/ExploreASL_logo.jpg"))
        self.setWindowIcon(self.icon_main)
        # Main Layout Setup
        self.mainlay = QHBoxLayout(self.cw)
        self.setWindowTitle("Explore ASL GUI")

        # Set up each of the subcomponents of the main window program
        self.UI_Setup_Navigator()
        self.UI_Setup_MenuBar()
        self.UI_Setup_MainSelections()
        self.UI_Setup_Connections()

        # Pre-initialize the main players
        self.parmsmaker = xASL_ParmsMaker(self, self.config)

    # This dockable navigator will contain the most essential parameters and will be repeatedly accessed by other
    # subwidgets within the program; should also be dockable within any of them.
    def UI_Setup_Navigator(self):
        # Initialize the navigator and essential characteristics
        self.dock_navigator = QDockWidget("Explore ASL Navigator", self)
        self.dock_navigator.setFeatures(QDockWidget.AllDockWidgetFeatures)
        self.dock_navigator.setMinimumSize(360, 480)
        self.dock_navigator.setWindowIcon(self.icon_main)
        # The main container and the main layout of the dock
        self.cont_navigator = QWidget(self.dock_navigator)
        self.vlay_navigator = QVBoxLayout(self.cont_navigator)
        self.cont_navigator.setLayout(self.vlay_navigator)
        # Finish up initial dock setup
        self.dock_navigator.setWidget(self.cont_navigator)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_navigator)
        # Essential Widgets
        # First, form layout for most important fields such as the ExploreASL directory
        self.formlay_navigator = QFormLayout(self.cont_navigator)
        self.hlay_exploreasl_dir = QHBoxLayout(self.cont_navigator)
        self.le_exploreasl_dir = QLineEdit(self.config["ExploreASLRoot"], self.cont_navigator)
        self.btn_exploreasl_dir = QPushButton("...", self.cont_navigator, clicked=self.set_exploreasl_dir)
        self.hlay_exploreasl_dir.addWidget(self.le_exploreasl_dir)
        self.hlay_exploreasl_dir.addWidget(self.btn_exploreasl_dir)
        self.hlay_currentanalysis_dir = QHBoxLayout(self.cont_navigator)
        self.le_currentanalysis_dir = QLineEdit(f"{os.getcwd()}", self.cont_navigator)
        self.btn_currentanalysis_dir = QPushButton("...", self.cont_navigator, clicked=self.set_analysis_dir)
        self.hlay_currentanalysis_dir.addWidget(self.le_currentanalysis_dir)
        self.hlay_currentanalysis_dir.addWidget(self.btn_currentanalysis_dir)
        self.formlay_navigator.addRow("Explore ASL Directory", self.hlay_exploreasl_dir)
        self.formlay_navigator.addRow("Current Analysis Directory", self.hlay_currentanalysis_dir)
        # Add all essential widgets to the dock's main layout
        self.vlay_navigator.addLayout(self.formlay_navigator)

    # Setup the standard Menu
    def UI_Setup_MenuBar(self):
        # Main menubar and main submenus setup
        self.menubar_main = QMenuBar(self)
        menu_names = ["File", "Edit", "Settings"]
        self.menu_file, self.menu_edit, self.menu_settings = [self.menubar_main.addMenu(name) for name in menu_names]
        # Setup the actions of the File menu
        self.menu_file.addAction("Show Navigator", self.dock_navigator.show)
        self.menu_file.addAction("Save Master Config", self.save_config)
        self.menu_file.addAction("Select Analysis Directory", self.set_analysis_dir)
        # Setup the actions of the Edit menu
        # Setup the actions of the Settings menu
        self.setMenuBar(self.menubar_main)

    # Setup the main selection
    def UI_Setup_MainSelections(self):
        self.vlay_left = QVBoxLayout(self)
        self.vlay_right = QVBoxLayout(self)
        for layout in [self.vlay_left, self.vlay_right]: self.mainlay.addLayout(layout)
        expanding_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        font_policy = QFont("Sans Serif", 24)
        font_policy.setBold(True)
        self.btn_open_runexploreasl = QToolButton(self.cw)
        self.btn_open_parmsmaker = QToolButton(self.cw)
        self.btn_open_importer = QToolButton(self.cw)
        self.btn_open_postanalysis = QToolButton(self.cw)
        self.main_btns = [self.btn_open_importer, self.btn_open_runexploreasl,
                          self.btn_open_parmsmaker, self.btn_open_postanalysis]
        imgs = ["media/importer_icon.svg", "media/parmsmaker_icon.svg",
                "media/run_exploreasl_icon.svg", "media/postrun_analysis_icon.svg"]
        txt_labels = ["Import DCM to NIFTI", "Create Parameters File",
                      "Process Data", "Post-Run Analysis"]
        for btn, img, text in zip(self.main_btns, imgs, txt_labels):
            btn.setSizePolicy(expanding_policy)
            btn.setIcon(QIcon(img))
            btn.setIconSize(QSize(175, 175))
            btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            btn.setText(text)
            btn.setFont(font_policy)

        self.vlay_left.addWidget(self.btn_open_importer)
        self.vlay_left.addWidget(self.btn_open_parmsmaker)
        self.vlay_right.addWidget(self.btn_open_runexploreasl)
        self.vlay_right.addWidget(self.btn_open_postanalysis)

    def UI_Setup_Connections(self):
        actions = [self.show_Importer, self.show_ParmsMaker,
                   self.show_RunExploreASLWin, self.show_PostAnalysis]
        for btn, action in zip(self.main_btns, actions):
            btn.clicked.connect(action)

    # Lauch the RunExploreASL window
    def show_RunExploreASLWin(self):
        pass

    # Launch the ParmsMaker window
    def show_ParmsMaker(self):
        self.parmsmaker.show()

    # Launch the Importer window
    def show_Importer(self):
        pass

    # Launch the Post-Analysis window
    def show_PostAnalysis(self):
        pass

    # Convenience function for saving to the master configuration file; accepts argument to save in a different
    # master configuration file (for developers flexibility; not for regular users)
    def save_config(self, other_config=None):
        if other_config is None:
            with open("ExploreASL_GUI_masterconfig.json", "w") as w:
                json.dump(self.config, w, indent=1)
        else:
            with open(other_config, "w") as w:
                json.dump(self.config, w, indent=1)

    # Convenience function for retrieving the master configuration file; accepts argument to load in a different
    # master configuration file (for future developers' flexibility; not for regular users)
    def load_config(self, other_config):
        if other_config is None:
            if os.path.exists(os.path.join(os.getcwd(), "ExploreASL_GUI_masterconfig.json")):
                with open("ExploreASL_GUI_masterconfig.json", 'r') as f:
                    self.config = json.load(f)
            else:
                self.config = {"ExploreASLRoot": "",
                               "DeveloperMode": False}
                self.save_config(self.other_config)
        else:
            with open(other_config, 'r') as f:
                self.config = json.load(f)

    # Sets the analysis directory the user is interested in
    def set_analysis_dir(self):
        result = QFileDialog.getExistingDirectory(self,
                                                  "Select the ExploreASL root directory",  # Window title
                                                  os.getcwd(),  # Default dir
                                                  QFileDialog.ShowDirsOnly)  # Display options
        if result:
            if '/' in result and platform() == "Windows":
                result = result.replace("/", "\\")
            self.le_currentanalysis_dir.setText(result)

    # Sets the ExploreASL directory of the user and updates the config to reflect the change
    def set_exploreasl_dir(self):
        result: str = QFileDialog.getExistingDirectory(self,
                                                       "Select the study analysis directory",  # Window title
                                                       os.getcwd(),  # Default dir
                                                       QFileDialog.ShowDirsOnly)  # Display options
        if result:
            if '/' in result and platform() == "Windows":
                result = result.replace("/", "\\")
            self.le_exploreasl_dir.setText(result)
            self.config["ExploreASLRoot"] = result
            self.save_config()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    with open("ExploreASL_GUI_masterconfig.json") as reader:
        master_config = json.load(reader)
    main_win = xASL_MainWin(master_config)
    main_win.show()
    sys.exit(app.exec())
