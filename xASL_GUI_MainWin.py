from PySide2.QtWidgets import *
from PySide2.QtGui import *
from PySide2.QtCore import *
from xASL_GUI_ParmsMaker import xASL_ParmsMaker, DirectoryDragDrop_ListWidget
from xASL_GUI_Executor import xASL_Executor
from xASL_GUI_PostProc import xASL_PostProc
import os
import sys
import json
import platform
import subprocess


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


# noinspection PyAttributeOutsideInit
class xASL_MainWin(QMainWindow):
    def __init__(self, config=None):
        super().__init__()
        # Load in the master config file if it exists; otherwise, make it
        print(platform.system())
        if config is None:
            self.load_config()
        else:
            self.config = config
        self.load_tooltips()
        # Window Size and initial visual setup
        self.setMinimumSize(1080, 480)
        self.cw = QWidget(self)
        self.setCentralWidget(self.cw)
        # Main Icon setup
        self.icon_main = QIcon(os.path.join(os.getcwd(), "media", "ExploreASL_logo.png"))
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
        self.parmsmaker = xASL_ParmsMaker(self)
        self.executor = xASL_Executor(self)
        self.postproc = xASL_PostProc(self)

    # This dockable navigator will contain the most essential parameters and will be repeatedly accessed by other
    # subwidgets within the program; should also be dockable within any of them.
    def UI_Setup_Navigator(self):
        # Initialize the navigator and essential characteristics
        self.dock_navigator = QDockWidget("Explore ASL Navigator", self)
        self.dock_navigator.setFeatures(QDockWidget.AllDockWidgetFeatures)
        self.dock_navigator.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.dock_navigator.setMinimumSize(480, 480)
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
        self.le_currentanalysis_dir = QLineEdit(
            f"{os.getcwd() if self.config['DefaultRootDir'] is None else self.config['DefaultRootDir']}",
            self.cont_navigator)
        self.btn_currentanalysis_dir = QPushButton("...", self.cont_navigator, clicked=self.set_analysis_dir)
        self.hlay_currentanalysis_dir.addWidget(self.le_currentanalysis_dir)
        self.hlay_currentanalysis_dir.addWidget(self.btn_currentanalysis_dir)
        self.chk_makedefault_analysisdir = QCheckBox(self.cont_navigator)
        self.chk_makedefault_analysisdir.setChecked(True)
        self.formlay_navigator.addRow("Explore ASL Directory", self.hlay_exploreasl_dir)
        self.formlay_navigator.addRow("Current Analysis Directory", self.hlay_currentanalysis_dir)
        self.formlay_navigator.addRow("Set selected analysis directory as default?", self.chk_makedefault_analysisdir)
        # Next, the main player will be a treeview with a FileSystemModel
        self.treev_navigator = QTreeView(self.cont_navigator)
        self.filemodel_navigator = QFileSystemModel(self.cont_navigator)
        self.filemodel_navigator.setRootPath(self.config["DefaultRootDir"])
        self.treev_navigator.setModel(self.filemodel_navigator)
        self.treev_navigator.setRootIndex(self.filemodel_navigator.index(self.config["DefaultRootDir"]))
        self.treev_navigator.header().resizeSection(0, 250)
        self.treev_navigator.setDragEnabled(True)
        self.treev_navigator.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.treev_navigator.setSortingEnabled(True)
        self.treev_navigator.sortByColumn(1, Qt.AscendingOrder)
        # Add all essential widgets to the dock's main layout
        self.vlay_navigator.addLayout(self.formlay_navigator)
        self.vlay_navigator.addWidget(self.treev_navigator)

    # Setup the standard Menu
    def UI_Setup_MenuBar(self):
        # Main menubar and main submenus setup
        self.menubar_main = QMenuBar(self)
        menu_names = ["File", "Edit", "Settings", "About"]
        self.menu_file, self.menu_edit, self.menu_settings, self.menu_about = [self.menubar_main.addMenu(name) for name
                                                                               in menu_names]
        # Setup the actions of the File menu
        self.menu_file.addAction("Show Navigator", self.dock_navigator.show)
        self.menu_file.addAction("Save Master Config", self.save_config)
        self.menu_file.addAction("Select Analysis Directory", self.set_analysis_dir)
        self.menu_file.addAction("About ExploreASL", self.show_AboutExploreASL)
        # Setup the actions of the Edit menu
        # Setup the actions of the Settings menu
        self.setMenuBar(self.menubar_main)

    # Setup the main selection
    def UI_Setup_MainSelections(self):
        self.vlay_left = QVBoxLayout(self)
        self.vlay_right = QVBoxLayout(self)
        for layout in [self.vlay_left, self.vlay_right]:
            self.mainlay.addLayout(layout)
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
                   self.show_Executor, self.show_PostAnalysis]
        for btn, action in zip(self.main_btns, actions):
            btn.clicked.connect(action)

    # Lauch the Executor window
    def show_Executor(self):
        self.executor.show()

    # Launch the ParmsMaker window
    def show_ParmsMaker(self):
        self.parmsmaker.show()

    # Launch the Importer window
    def show_Importer(self):
        pass

    # Launch the Post-Analysis window
    def show_PostAnalysis(self):
        self.postproc.show()

    # Launch the "About Explore ASL" window
    def show_AboutExploreASL(self):
        pass

    # Convenience function for saving to the master configuration file
    def save_config(self):
        with open("ExploreASL_GUI_masterconfig.json", "w") as w:
            json.dump(self.config, w, indent=1)

    # Convenience function for retrieving the master configuration file; accepts argument to load in a different
    # master configuration file (for future developers' flexibility; not for regular users)
    def load_config(self):
        if os.path.exists(os.path.join(os.getcwd(), "ExploreASL_GUI_masterconfig.json")):
            with open("ExploreASL_GUI_masterconfig.json", 'r') as f:
                self.config = json.load(f)
        # First time startup
        else:
            self.config = {"ExploreASLRoot": "",  # The filepath to the ExploreASL directory
                           "DefaultRootDir": f"{os.getcwd()}",  # The default root for the navigator to watch from
                           "ScriptsDir": f"{os.getcwd()}",  # The location of where this script is launched from
                           "Platform": f"{platform.system()}",
                           "DeveloperMode": False}  # Whether to launch the app in developer mode or not
            self.save_config()

    def load_tooltips(self):
        if os.path.exists(os.path.join(os.getcwd(), "xASL_GUI_Tooltips.json")):
            with open("xASL_GUI_Tooltips.json") as f:
                self.tooltips = json.load(f)

    # Sets the analysis directory the user is interested in
    # noinspection PyCallByClass
    def set_analysis_dir(self):
        result = QFileDialog.getExistingDirectory(self,
                                                  "Select analysis directory to view",  # Window title
                                                  self.config["DefaultRootDir"],  # Default dir
                                                  QFileDialog.ShowDirsOnly)  # Display options
        if result:
            if '/' in result and platform.system() == "Windows":
                result = result.replace("/", "\\")
            # Change the display and have the navigator adjust according
            self.le_currentanalysis_dir.setText(result)
            self.filemodel_navigator.setRootPath(result)
            self.treev_navigator.setRootIndex(self.filemodel_navigator.index(result))
            self.treev_navigator.sortByColumn(1, Qt.AscendingOrder)

            # Update user config to have a new default analysis dir to refer to in on future startups
            if self.chk_makedefault_analysisdir.isChecked():
                self.config["DefaultRootDir"] = result
                self.save_config()

    # Sets the ExploreASL directory of the user and updates the config to reflect the change
    def set_exploreasl_dir(self):
        result: str = QFileDialog.getExistingDirectory(self,
                                                       "Select the study analysis directory",  # Window title
                                                       os.getcwd(),  # Default dir
                                                       QFileDialog.ShowDirsOnly)  # Display options
        if result:
            if '/' in result and platform.system() == "Windows":
                result = result.replace("/", "\\")
            self.le_exploreasl_dir.setText(result)
            self.config["ExploreASLRoot"] = result
            self.save_config()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    # Get the appropriate default style based on the user's operating system
    if platform.system() == "Windows":  # Windows
        app.setStyle("Fusion")
    elif platform.system() == "Darwin":  # Mac
        app.setStyle("macintosh")
    elif platform.system() == "Linux":  # Linux
        app.setStyle("Fusion")
    else:
        print("This program does not support your operating system")
        sys.exit()

    app.setWindowIcon(QIcon(os.path.join(os.getcwd(), "media", "ExploreASL_logo.jpg")))
    # Check if the master config file exists; if it doesn't, the app will initialize one on the first startup
    if os.path.exists(os.path.join(os.getcwd(), "ExploreASL_GUI_masterconfig.json")):
        with open("ExploreASL_GUI_masterconfig.json") as reader:
            master_config = json.load(reader)
            main_win = xASL_MainWin(master_config)
    else:
        main_win = xASL_MainWin(None)
    main_win.show()
    sys.exit(app.exec_())
