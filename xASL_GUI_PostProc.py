from PySide2.QtWidgets import *
from PySide2.QtGui import *
from PySide2.QtCore import *
from xASL_GUI_HelperClasses import DandD_ListWidget2LineEdit, DandD_FileExplorer2LineEdit, \
    DandD_FileExplorerFile2LineEdit
from xASL_GUI_FacetPlot import xASL_GUI_FacetGridOrganizer
import os
import sys
import json
from glob import glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import seaborn as sns
from pprint import pprint

pd.set_option("display.max_columns", 10)
pd.set_option("display.width", 400)


# noinspection PyAttributeOutsideInit
class xASL_PostProc(QMainWindow):
    def __init__(self, parent_win=None):
        # Parent window is fed into the constructor to allow for communication with parent window devices
        super().__init__(parent=parent_win)

        # Window Size and initial visual setup
        self.setMinimumSize(1920, 1000)
        self.cw = QWidget(self)
        self.setCentralWidget(self.cw)
        self.mainlay = QVBoxLayout(self.cw)
        self.cw.setLayout(self.mainlay)
        self.setWindowTitle("Explore ASL - Post Processing Visualization")
        self.setWindowIcon(QIcon(os.path.join(os.getcwd(), "media", "ExploreASL_logo.png")))

        self.canvas_generate(None)

        self.fig_wid = None
        self.axes_wid = None

        # Main Widgets setup
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
        self.le_analysis_dir = DandD_FileExplorer2LineEdit(self.grp_directories)
        self.le_analysis_dir.setText(self.parent().config["DefaultRootDir"])
        self.le_demographics_file = DandD_FileExplorerFile2LineEdit([".tsv", ".csv", ".xlsx"], self.grp_directories)
        self.le_demographics_file.setPlaceholderText("Drag & Drap a supporting .tsv/.csv/.xlsx file")
        self.cmb_atlas_selection = QComboBox(self.grp_directories)
        self.cmb_atlas_selection.addItems(["MNI", "Hammers"])
        self.cmb_pvc_selection = QComboBox(self.grp_directories)
        self.cmb_pvc_selection.addItems(["Without Partial Volume Correction", "With Partial Volume Correction"])
        self.cmb_stats_selection = QComboBox(self.grp_directories)
        self.cmb_stats_selection.addItems(["Mean", "Median", "Coefficient of Variation"])
        self.btn_load_in_data = QPushButton("Load Data", self.grp_directories, clicked=self.load_exploreasl_data)
        self.formlay_directories.addRow("Analysis Directory", self.le_analysis_dir)
        self.formlay_directories.addRow("Ancillary Study Dataframe", self.le_demographics_file)
        self.formlay_directories.addRow("Which Atlas to Utilize", self.cmb_atlas_selection)
        self.formlay_directories.addRow("Which Partial-Volume Stats to View", self.cmb_pvc_selection)
        self.formlay_directories.addRow("Which Statistic to View", self.cmb_stats_selection)
        self.formlay_directories.addRow(self.btn_load_in_data)

        # Setup the main Variable Viewer
        self.grp_varview = QGroupBox("Variables", self.cont_maindock)
        self.vlay_varview = QVBoxLayout(self.grp_varview)
        self.lst_varview = QListWidget(self.grp_varview)
        self.lst_varview.setFixedHeight(300)
        self.lst_varview.setDragEnabled(True)
        self.vlay_varview.addWidget(self.lst_varview)

        # Setup the start of Plotting Settings
        self.grp_pltsettings = QGroupBox("Plotting Settings", self.cont_maindock)
        self.vlay_pltsettings = QVBoxLayout(self.grp_pltsettings)
        self.cmb_pltsettings = QComboBox(self.grp_pltsettings)
        self.cmb_pltsettings.addItems(["Select an option", "Facet Grid"])
        self.cmb_pltsettings.setEnabled(False)
        self.tab_pltsettings = QTabWidget(self.grp_pltsettings)

        self.cont_pltsettings_univlvlparms = QWidget(self.grp_pltsettings)
        self.cont_pltsettings_figlvlparms = QWidget(self.grp_pltsettings)
        self.cont_pltsettings_axeslvlparms = QWidget(self.grp_pltsettings)

        self.vlay_pltsetting_figlvlparms = QVBoxLayout(self.cont_pltsettings_figlvlparms)
        self.vlay_pltsettings_axeslvlparms = QVBoxLayout(self.cont_pltsettings_axeslvlparms)

        self.tab_pltsettings.addTab(self.cont_pltsettings_univlvlparms, "Common Parameters")
        self.tab_pltsettings.addTab(self.cont_pltsettings_figlvlparms, "Figure Parameters")
        self.tab_pltsettings.addTab(self.cont_pltsettings_axeslvlparms, "Axes Parameters")
        self.tab_pltsettings.setMinimumHeight(350)

        self.vlay_pltsettings.addWidget(self.cmb_pltsettings)
        self.vlay_pltsettings.addWidget(self.tab_pltsettings)

        # Add the groups to the main vertical layout
        self.vlay_maindock.addWidget(self.grp_directories)
        self.vlay_maindock.addWidget(self.grp_varview)
        self.vlay_maindock.addWidget(self.grp_pltsettings)
        self.vlay_maindock.addStretch()

        # This has to go at the end due to order of initialization
        self.UI_Setup_CommonParameters()
        self.cmb_pltsettings.currentTextChanged.connect(self.set_current_figure_manager)

    # These parameters are universal to all plots and can therefore be set up here
    def UI_Setup_CommonParameters(self):
        # Set up the padding
        self.formlay_commonparms = QFormLayout(self.cont_pltsettings_univlvlparms)
        self.cont_pltsettings_univlvlparms.setLayout(self.formlay_commonparms)
        self.spinbox_toppad = QDoubleSpinBox(self.cont_pltsettings_univlvlparms)
        self.spinbox_bottompad = QDoubleSpinBox(self.cont_pltsettings_univlvlparms)
        self.spinbox_leftpad = QDoubleSpinBox(self.cont_pltsettings_univlvlparms)
        self.spinbox_rightpad = QDoubleSpinBox(self.cont_pltsettings_univlvlparms)
        self.spinbox_wspace = QDoubleSpinBox(self.cont_pltsettings_univlvlparms)
        self.spinbox_hspace = QDoubleSpinBox(self.cont_pltsettings_univlvlparms)
        for description, widget, default in zip(["Top Padding", "Bottom Padding", "Left Padding", "Right Padding",
                                                 "Horizontal Inter-Facet Spacing", "Vertical Inter-Facet Spacing"],
                                                [self.spinbox_toppad, self.spinbox_bottompad, self.spinbox_leftpad,
                                                 self.spinbox_rightpad, self.spinbox_wspace, self.spinbox_hspace],
                                                [0.91, 0.057, 0.055, 0.989, 0.2, 0.2]):
            widget.setValue(default)
            widget.setRange(0, 1)
            widget.setSingleStep(0.01)
            widget.valueChanged.connect(self.plotupdate_padding)
            self.formlay_commonparms.addRow(description, widget)

    # When called, this updates the padding to whatever is the current value in the padding doublespinboxes
    def plotupdate_padding(self):
        print("Adjusting padding")
        plt.subplots_adjust(left=self.spinbox_leftpad.value(),
                            bottom=self.spinbox_bottompad.value(),
                            right=self.spinbox_rightpad.value(),
                            top=self.spinbox_toppad.value(),
                            wspace=self.spinbox_wspace.value(),
                            hspace=self.spinbox_hspace.value())
        self.canvas.draw()

    # Controls the current type of figure and its arguments in the Figure Parameters Tab
    # by necessity, it must also clear the contents of whatever is in the axes table
    def set_current_figure_manager(self, fig_type):
        if fig_type == "Facet Grid":
            # Must first clear the current canvas and set one in that is prepared with a facet grid
            self.canvas_full_clear()
            self.canvas_generate("Facet Grid Default")
            self.plotupdate_padding()
            self.fig_manager = xASL_GUI_FacetGridOrganizer(self)
            self.fig_manager.change_figparms_updateplot.connect(self.plotupdate_facetgrid_figurecall_plot)
            self.fig_manager.change_axesparms_updateplot.connect(self.plotupdate_facetgrid_axescall_plot)
            self.fig_manager.change_axesparms_widget.connect(self.update_axesparms)


            # Clear and replace the figure widget for the figure parameters tab
            self.clear_figparms()
            self.fig_wid = self.fig_manager.cont_figparms
            self.vlay_pltsetting_figlvlparms.addWidget(self.fig_wid)

            # # Must also clear the axes widget for the axes parameters tab
            self.clear_axesparms()

        else:
            self.canvas_full_clear()
            self.canvas_generate(None)
            self.plotupdate_padding()

            # Clear the figure widget tab
            self.clear_figparms()
            self.clear_axesparms()

    # Convenience Function - clears the Figure Parameters Tab
    def clear_figparms(self):
        if self.fig_wid is not None:
            self.vlay_pltsetting_figlvlparms.removeWidget(self.fig_wid)
            self.fig_wid.setParent(None)
            del self.fig_wid
            self.fig_wid = None

    # Convenience Function - clears the Axes Parameters Tab
    def clear_axesparms(self):
        print("Clearing Axes Parms")
        if self.axes_wid is not None:
            self.vlay_pltsettings_axeslvlparms.removeWidget(self.axes_wid)
            self.axes_wid.setParent(None)
            del self.axes_wid
            self.axes_wid = None

    # Convenience Function - updates the "Axes Parameters" tab with the new tab that must have been prepared
    @Slot()
    def update_axesparms(self):
        print("update_axesparms received a signal")
        self.axes_wid = self.fig_manager.cont_axesparms
        self.vlay_pltsettings_axeslvlparms.addWidget(self.axes_wid)

    # Convenience Function - clears the canvas
    def canvas_full_clear(self):
        plt.clf()
        plt.close(self.mainfig)
        self.mainlay.removeWidget(self.canvas)
        self.mainlay.removeWidget(self.nav)
        del self.nav
        del self.mainfig
        del self.canvas

    # Called after a clear to restore a blank/default canvas with the appropriate figure manager
    def canvas_generate(self, action):
        if action is None:
            self.mainfig = Figure()
        # In "Facet Grid Default" a simple placeholder canvas is set
        elif action == 'Facet Grid Default':
            self.grid = sns.FacetGrid(data=self.long_data)
            self.mainfig = self.grid.fig
        # In "Facet Grid Figure Call", a change in the figure parms is forcing an update
        elif action == "Facet Grid Figure Call":
            # First create the constructor, then feed it into the Facetgrid class
            constructor = {}
            for kwarg, call in self.fig_manager.fig_kwargs.items():
                if call() == "":
                    constructor[kwarg] = None
                else:
                    constructor[kwarg] = call()
            # pprint(constructor)
            self.grid = sns.FacetGrid(data=self.long_data, **constructor)
            self.mainfig = self.grid.fig

        self.canvas = FigureCanvas(self.mainfig)
        self.nav = NavigationToolbar(self.canvas, self.canvas)
        self.mainlay.addWidget(self.nav)
        self.mainlay.addWidget(self.canvas)
        self.canvas.draw()

    # Called by updates from the Figure Parameters
    @Slot()
    def plotupdate_facetgrid_figurecall_plot(self):
        # First clear the canvas
        self.canvas_full_clear()
        # Then generate the new canvas with the updated facetgrid and figure
        self.canvas_generate("Facet Grid Figure Call")
        # Then see if the axes can be updated, and if so, update them
        self.plotupdate_facetgrid_axes()
        self.plotupdate_padding()


    # Called by updates from the Axes Parameters
    @Slot()
    def plotupdate_facetgrid_axescall_plot(self):
        self.plotupdate_facetgrid_axes()

    # Convenience function
    def plotupdate_facetgrid_axes(self):
        # If x and y axes arguments are blank, don't pursue additional updating
        if any([self.fig_manager.axes_arg_x() == '', self.fig_manager.axes_arg_y() == '']):
            return

        # Clear all axes
        axes = self.grid.axes
        for ax in axes.flat:
            ax.clear()

        # Otherwise, proceed
        func = self.fig_manager.plotting_func
        x, y, hue = self.fig_manager.axes_arg_x(), self.fig_manager.axes_arg_y(), self.fig_manager.axes_arg_hue()
        axes_constructor = {kwarg: call() for kwarg, call in self.fig_manager.axes_kwargs.items()}
        # pprint(axes_constructor)
        if hue == '':
            self.grid = self.grid.map(func, x, y, **axes_constructor)
        else:
            self.grid = self.grid.map(func, x, y, hue, **axes_constructor)

        # Tell the canvas to update
        self.canvas.draw()



    # Loads in data as a pandas dataframe
    def load_exploreasl_data(self):
        if os.path.exists(os.path.join(self.le_analysis_dir.text(), "Population", "Stats")):
            stats_dir = os.path.join(self.le_analysis_dir.text(), "Population", "Stats")
            atlas = {"MNI": "MNI_structural", "Hammers": "Hammers"}[self.cmb_atlas_selection.currentText()]
            pvc = {"With Partial Volume Correction": "PVC2",
                   "Without Partial Volume Correction": "PVC0"}[self.cmb_pvc_selection.currentText()]
            stat = {"Mean": "mean", "Median": "median",
                    "Coefficient of Variation": "CoV"}[self.cmb_stats_selection.currentText()]
            # Get the relevant files
            gm_file = glob(os.path.join(stats_dir, f'{stat}_*_TotalGM*{pvc}.tsv'))
            wm_file = glob(os.path.join(stats_dir, f'{stat}_*_DeepWM*{pvc}.tsv'))
            atlas_file = glob(os.path.join(stats_dir, f'{stat}_*_{atlas}*{pvc}.tsv'))
            # Exit if not all files can be found
            for file in [gm_file, wm_file, atlas_file]:
                if len(file) == 0: return
            # Clearing of appropriate widgets to accomodate new data
            self.lst_varview.clear()
            # Extract each as a dataframe and merge them
            dfs = []
            for file in [gm_file, wm_file, atlas_file]:
                df = pd.read_csv(file[0], sep='\t')
                df.drop(0, axis=0, inplace=True)
                df = df.iloc[:, 0:len(df.columns) - 1]
                dfs.append(df)
            df: pd.DataFrame = pd.concat(dfs, axis=1)
            df = df.T.drop_duplicates().T

            # Fix datatypes:
            dtype_guide = {"SUBJECT": "object", "LongitudinalTimePoint": "category", "SubjectNList": "category",
                           "Site": "category", "AcquisitionTime": "float64", "GM_vol": "float64",
                           "WM_vol": "float64", "CSF_vol": "float64", "GM_ICVRatio": "float64",
                           "GMWM_ICVRatio": "float64"}
            for col in df.columns:
                if col in dtype_guide.keys():
                    df[col] = df[col].astype(dtype_guide[col])
                else:
                    df[col] = df[col].astype("float64")
            self.data = df
            self.backup_data = df.copy()

            # Load in ancillary data
            if all([os.path.exists(self.le_demographics_file.text()),
                    os.path.isfile(self.le_demographics_file.text()),
                    os.path.splitext(self.le_demographics_file.text())[1] in [".tsv", ".csv", ".xlsx"]
                    ]):
                result = self.load_ancillary_data(df)
                if result is not None:
                    self.data = result
                # If the merging failed, default to just using the ExploreASL datasets. In a future update, add some
                # sort of user feedback that this went wrong
                else:
                    self.data = self.backup_data

            # also generate the long version of the data
            id_vars = [col for col in self.data.columns if not any([col.endswith("_B"),
                                                                    col.endswith("_L"),
                                                                    col.endswith("_R")])]
            value_vars = [col for col in self.data.columns if col not in id_vars]
            self.long_data: pd.DataFrame = self.data.melt(id_vars=id_vars,
                                                          value_vars=value_vars,
                                                          var_name="Atlas Location",
                                                          value_name="CBF")
            self.long_data["CBF"] = self.long_data["CBF"].astype("float64")
            atlas_location: pd.Series = self.long_data.pop("Atlas Location")
            atlas_loc_df: pd.DataFrame = atlas_location.str.extract("(.*)_(B|L|R)", expand=True)
            atlas_loc_df.rename(columns={0: "Anatomical Area", 1: "Side of the Brain"}, inplace=True)
            atlas_loc_df["Side of the Brain"] = atlas_loc_df["Side of the Brain"].apply(lambda x: {"B": "Bilateral",
                                                                                                   "R": "Right",
                                                                                                   "L": "Left"}[x])
            atlas_loc_df = atlas_loc_df.astype("category")
            self.long_data: pd.DataFrame = pd.concat([self.long_data, atlas_loc_df], axis=1)
            self.long_data.infer_objects()
            self.current_dtypes = self.long_data.dtypes
            self.current_dtypes = {col: str(str_name) for col, str_name in
                                   zip(self.current_dtypes.index, self.current_dtypes.values)}
            self.lst_varview.addItems(self.long_data.columns.tolist())
            self.cmb_pltsettings.setEnabled(True)

    def load_ancillary_data(self, exasl_df):
        # Load in the other dataframe, with flexibility for filetype
        file = self.le_demographics_file.text()
        filetype = os.path.splitext(file)[1]
        if filetype == '.tsv':
            demo_df = pd.read_csv(file, sep='\t')
        elif filetype == '.csv':
            demo_df = pd.read_csv(file)
        elif filetype == '.xlsx':
            demo_df = pd.read_excel(file)
        else:
            print("An unsupported filetype was given")
            return None
        # Abort if the pertinent "SUBJECT" column is not in the read columns. In a future update, add support for user
        # specification of which column to interpret as the SUBJECT column
        if "SUBJECT" not in demo_df.columns:
            return None
        merged = pd.merge(left=demo_df, right=exasl_df, how='inner', on='SUBJECT', sort=True)
        if len(merged) == 0:
            return None
        sub_in_merge, sub_in_demo, sub_in_exasl = set(merged["SUBJECT"].tolist()), set(
            demo_df["SUBJECT"].tolist()), set(exasl_df["SUBJECT"].tolist())
        diff_in_demo = sub_in_demo.difference(sub_in_merge)
        diff_in_exasl = sub_in_exasl.difference(sub_in_merge)
        if any([len(diff_in_demo) > 0, len(diff_in_exasl) > 0]):
            QMessageBox().information(self,
                                      "Merge successful, but differences were found:\n",
                                      f"You provided a file with {len(sub_in_demo)} subjects.\n"
                                      f"ExploreASL's output had {len(sub_in_exasl)} subjects.\n"
                                      f"During the merge {len(diff_in_demo)} subjects present in the file "
                                      f"had to be excluded.\n"
                                      f"During the merge {len(diff_in_exasl)} subjects present in ExploreASL's output "
                                      f"had to be excluded",
                                      QMessageBox.Ok)
        print(merged)

        return merged
