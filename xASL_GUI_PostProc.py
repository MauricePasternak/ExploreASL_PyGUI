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


# noinspection PyAttributeOutsideInit,PyCallingNonCallable
class xASL_PostProc(QMainWindow):
    def __init__(self, parent_win=None):
        # Parent window is fed into the constructor to allow for communication with parent window devices
        super().__init__(parent=parent_win)

        # Window Size and initial visual setup
        self.setMinimumSize(1920, 1000)
        self.cw = QWidget(self)
        self.setCentralWidget(self.cw)
        self.mainlay = QVBoxLayout()
        self.cw.setLayout(self.mainlay)
        self.setWindowTitle("Explore ASL - Post Processing Visualization")
        self.setWindowIcon(QIcon(os.path.join(os.getcwd(), "media", "ExploreASL_logo.png")))

        self.canvas_generate(None)

        # Initialize blank givens
        self.fig_manager = None
        self.fig_wid = None
        self.axes_wid = None
        self.loaded_wide_data = pd.DataFrame()
        self.loaded_long_data = pd.DataFrame()
        self.plotstylenames = ['Solarize_Light2', '_classic_test_patch', 'bmh', 'classic', 'dark_background', 'fast',
                               'fivethirtyeight', 'ggplot', 'grayscale', 'seaborn', 'seaborn-bright',
                               'seaborn-colorblind', 'seaborn-dark', 'seaborn-dark-palette', 'seaborn-darkgrid',
                               'seaborn-deep', 'seaborn-muted', 'seaborn-notebook', 'seaborn-paper', 'seaborn-pastel',
                               'seaborn-poster', 'seaborn-talk', 'seaborn-ticks', 'seaborn-white', 'seaborn-whitegrid',
                               'tableau-colorblind10']

        # Main Widgets setup
        self.UI_Setup_Docker()

    def UI_Setup_Docker(self):
        self.dock = QDockWidget("Data Visualization Settings", self.cw)
        self.dock.setMinimumWidth(480)
        self.dock.setFeatures(QDockWidget.AllDockWidgetFeatures)
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
        self.btn_subset_data = QPushButton("Subset Data", self.grp_directories, clicked=self.show_subsetter)
        self.btn_subset_data.setEnabled(False)
        self.btn_load_in_data = QPushButton("Load Data", self.grp_directories, clicked=self.load_exploreasl_data)
        self.formlay_directories.addRow("Analysis Directory", self.le_analysis_dir)
        self.formlay_directories.addRow("Ancillary Study Dataframe", self.le_demographics_file)
        self.formlay_directories.addRow("Which Atlas to Utilize", self.cmb_atlas_selection)
        self.formlay_directories.addRow("Which Partial-Volume Stats to View", self.cmb_pvc_selection)
        self.formlay_directories.addRow("Which Statistic to View", self.cmb_stats_selection)
        self.formlay_directories.addRow(self.btn_subset_data)
        self.formlay_directories.addRow(self.btn_load_in_data)

        # Setup the subsetter and have it remain sensitive to changes in directory
        self.subsetter = xASL_GUI_Subsetter(self)
        self.le_analysis_dir.textChanged.connect(self.subsetter.clear_contents)
        self.le_demographics_file.textChanged.connect(self.subsetter.clear_contents)

        # Setup the main Variable Viewer
        self.grp_varview = QGroupBox("Variables", self.cont_maindock)
        self.vlay_varview = QVBoxLayout(self.grp_varview)
        self.lst_varview = QListWidget(self.grp_varview)
        self.lst_varview.setFixedHeight(250)
        self.lst_varview.setDragEnabled(True)
        self.vlay_varview.addWidget(self.lst_varview)

        # Setup the start of Plotting Settings
        self.grp_pltsettings = QGroupBox("Plotting Settings", self.cont_maindock)
        self.vlay_pltsettings = QVBoxLayout(self.grp_pltsettings)
        self.cmb_figuretypeselection = QComboBox(self.grp_pltsettings)
        self.cmb_figuretypeselection.addItems(["Select an option", "Facet Grid"])
        self.cmb_figuretypeselection.setEnabled(False)
        self.tab_pltsettings = QTabWidget(self.grp_pltsettings)

        self.cont_pltsettings_univlvlparms = QWidget(self.grp_pltsettings)
        self.cont_pltsettings_figlvlparms = QWidget(self.grp_pltsettings)
        self.cont_pltsettings_axeslvlparms = QWidget(self.grp_pltsettings)

        self.vlay_pltsetting_figlvlparms = QVBoxLayout(self.cont_pltsettings_figlvlparms)
        self.vlay_pltsettings_axeslvlparms = QVBoxLayout(self.cont_pltsettings_axeslvlparms)

        self.tab_pltsettings.addTab(self.cont_pltsettings_univlvlparms, "Common Parameters")
        self.tab_pltsettings.addTab(self.cont_pltsettings_figlvlparms, "Figure Parameters")
        self.tab_pltsettings.addTab(self.cont_pltsettings_axeslvlparms, "Axes Parameters")
        self.tab_pltsettings.setMaximumHeight(400)

        self.vlay_pltsettings.addWidget(self.cmb_figuretypeselection)
        self.vlay_pltsettings.addWidget(self.tab_pltsettings)

        # Add the groups to the main vertical layout
        self.vlay_maindock.addWidget(self.grp_directories)
        self.vlay_maindock.addWidget(self.grp_varview)
        self.vlay_maindock.addWidget(self.grp_pltsettings)
        self.vlay_maindock.addStretch()

        # This has to go at the end due to order of initialization
        self.UI_Setup_CommonParameters()
        self.cmb_figuretypeselection.currentTextChanged.connect(self.set_current_figure_manager)

    # These parameters are universal to all plots and can therefore be set up here
    def UI_Setup_CommonParameters(self):
        # Format layout must be the first item declared
        self.formlay_commonparms = QFormLayout(self.cont_pltsettings_univlvlparms)

        # Set up the overall plot style
        self.cmb_plotstyle = QComboBox(self.cont_pltsettings_univlvlparms)
        self.cmb_plotstyle.addItems(self.plotstylenames)
        self.formlay_commonparms.addRow("Overall Plot Style", self.cmb_plotstyle)

        # Set up the padding
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
                                                [0.91, 0.057, 0.055, 0.95, 0.2, 0.2]):
            widget.setValue(default)
            widget.setRange(0, 1)
            widget.setSingleStep(0.01)
            widget.valueChanged.connect(self.plotupdate_padding)
            self.formlay_commonparms.addRow(description, widget)

        # Set up the text options
        self.le_xlab_override = QLineEdit(self.cont_pltsettings_univlvlparms)
        self.le_ylab_override = QLineEdit(self.cont_pltsettings_univlvlparms)
        self.le_title_override = QLineEdit(self.cont_pltsettings_univlvlparms)
        self.le_xlab_override.setPlaceholderText("Overwrite existing X-axis label")
        self.le_ylab_override.setPlaceholderText("Overwrite existing Y-axis label")
        self.le_title_override.setPlaceholderText("Overwrite existing Title")
        for description, widget in zip(["X-Axis Label", "Y-Axis Label", "Title"],
                                       [self.le_xlab_override, self.le_ylab_override, self.le_title_override]):
            widget.textChanged.connect(self.plotupdate_labels)
            self.formlay_commonparms.addRow(description, widget)

    def show_subsetter(self):
        self.subsetter.show()
        print("show_subsetter was executed")

    def plotupdate_plotstyle(self):
        pass

    # When called, this updates the major axes labels options
    def plotupdate_labels(self):
        if self.le_xlab_override != '':
            plt.xlabel(self.le_xlab_override.text())
        if self.le_ylab_override.text() != '':
            plt.ylabel(self.le_ylab_override.text())
        if self.le_title_override.text() != '':
            plt.suptitle(self.le_title_override.text())
        self.canvas.draw()

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

            # Clear and replace the figure parameters widget for the figure parameters tab. The new figure parameters
            # widget is specific to the currently-assigned manager
            self.clear_figparms()
            self.fig_wid = self.fig_manager.cont_figparms
            self.vlay_pltsetting_figlvlparms.addWidget(self.fig_wid)

            # Must also clear the axes widget for the axes parameters tab
            self.clear_axesparms()

        else:
            self.canvas_full_clear()
            self.canvas_generate(None)
            self.plotupdate_padding()

            # Delete the figure manager just in case
            if self.fig_manager:
                del self.fig_manager
                self.fig_manager = None

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

            # Create the FacetGrid; take note that if the grid type is a regression plot, then the palette argument
            # is fed into the grid call instead of the axes contructor
            if not self.cmb_figuretypeselection.currentText() == "Regression Plot":
                self.grid = sns.FacetGrid(data=self.long_data, **constructor)
                self.mainfig = self.grid.fig
            else:
                self.grid = sns.FacetGrid(data=self.long_data, palette=self.fig_manager.cmb_palette.currentText(),
                                          **constructor)
                self.mainfig = self.grid.fig

        self.canvas = FigureCanvas(self.mainfig)
        self.nav = NavigationToolbar(self.canvas, self.canvas)
        self.mainlay.addWidget(self.nav)
        self.mainlay.addWidget(self.canvas)
        # self.canvas.draw()  # May not be necessary, since canvas_generate is usually followed up with
        # plotupdate_padding, which has the canvas draw at that time

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
        # If x or y axes arguments are still in their non-callable form (i.e string type), don't proceed
        if any([isinstance(self.fig_manager.axes_arg_x, str), isinstance(self.fig_manager.axes_arg_y, str)]):
            return

        # If x and y axes arguments are blank, don't proceed
        if any([self.fig_manager.axes_arg_x() == '', self.fig_manager.axes_arg_y() == '']):
            return

        # Account for a user typing the palette name, accidentally triggering this function, don't proceed
        if any([not self.fig_manager.cmb_palette,
                self.fig_manager.cmb_palette.currentText() not in self.fig_manager.palettenames]):
            return

        # Clear all axes
        axes = self.grid.axes
        for ax in axes.flat:
            ax.clear()

        # Otherwise, proceed
        func = self.fig_manager.plotting_func
        x, y, hue = self.fig_manager.axes_arg_x(), self.fig_manager.axes_arg_y(), self.fig_manager.axes_arg_hue()

        axes_constructor = {}
        for kwarg, call in self.fig_manager.axes_kwargs.items():
            if call() == "":
                axes_constructor[kwarg] = None
            else:
                axes_constructor[kwarg] = call()

        # Account for a user not selecting a palette
        if axes_constructor['palette'] in ['', "None", "Default Blue", "No Palette"]:
            axes_constructor['palette'] = None

        pprint(axes_constructor)
        if hue == '':
            self.grid = self.grid.map(func, x, y, data=self.long_data, **axes_constructor)
        else:
            self.grid = self.grid.map(func, x, y, hue, data=self.long_data, **axes_constructor)

        # Tell the canvas to update
        self.canvas.draw()

    # Loads in data as a pandas dataframe
    def load_exploreasl_data(self):
        # %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
        # First Section - Load in the ExploreASL Stats directory data
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
                df.drop(0, axis=0, inplace=True)  # First row is unnecessary
                df = df.loc[:, [col for col in df.columns if "Unnamed" not in col]]
                dfs.append(df)
            df: pd.DataFrame = pd.concat(dfs, axis=1)
            df = df.T.drop_duplicates().T

            # %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
            # Second Section - Fix the ExploreASL native data dtypes
            self.dtype_guide = {"SUBJECT": "object", "LongitudinalTimePoint": "category", "SubjectNList": "category",
                                "Site": "category", "AcquisitionTime": "float64", "GM_vol": "float64",
                                "WM_vol": "float64", "CSF_vol": "float64", "GM_ICVRatio": "float64",
                                "GMWM_ICVRatio": "float64"}
            for col in df.columns:
                if col in self.dtype_guide.keys():
                    df[col] = df[col].astype(self.dtype_guide[col])
                else:
                    df[col] = df[col].astype("float64")
            self.loaded_wide_data = df
            self.backup_data = df.copy()

            # %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
            # Third Section - If there is any ancillary data specified, load it in
            if all([os.path.exists(self.le_demographics_file.text()),
                    os.path.isfile(self.le_demographics_file.text()),
                    os.path.splitext(self.le_demographics_file.text())[1] in [".tsv", ".csv", ".xlsx"]
                    ]):
                result = self.load_ancillary_data(df)
                if result is not None:
                    self.loaded_wide_data = result
                # If the merging failed, default to just using the ExploreASL datasets. In a future update, add some
                # sort of user feedback that this went wrong
                else:
                    self.loaded_wide_data = self.backup_data

            # %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
            # Fourth Section - Convert the wide format data into a long format
            vars_to_keep_constant = [col for col in self.loaded_wide_data.columns if not any([col.endswith("_B"),
                                                                                              col.endswith("_L"),
                                                                                              col.endswith("_R")])]
            vars_to_melt = [col for col in self.loaded_wide_data.columns if col not in vars_to_keep_constant]
            self.loaded_long_data = self.loaded_wide_data.melt(id_vars=vars_to_keep_constant,
                                                               value_vars=vars_to_melt,
                                                               var_name="Atlas Location",
                                                               value_name="CBF")
            self.loaded_long_data["CBF"] = self.loaded_long_data["CBF"].astype("float64")
            atlas_location = self.loaded_long_data.pop("Atlas Location")
            atlas_loc_df: pd.DataFrame = atlas_location.str.extract("(.*)_(B|L|R)", expand=True)
            atlas_loc_df.rename(columns={0: "Anatomical Area", 1: "Side of the Brain"}, inplace=True)
            atlas_loc_df["Side of the Brain"] = atlas_loc_df["Side of the Brain"].apply(lambda x: {"B": "Bilateral",
                                                                                                   "R": "Right",
                                                                                                   "L": "Left"}[x])
            atlas_loc_df = atlas_loc_df.astype("category")
            self.loaded_long_data: pd.DataFrame = pd.concat([self.loaded_long_data, atlas_loc_df], axis=1)
            self.loaded_long_data.infer_objects()
            self.current_dtypes = self.loaded_long_data.dtypes
            self.current_dtypes = {col: str(str_name) for col, str_name in
                                   zip(self.current_dtypes.index, self.current_dtypes.values)}
            self.lst_varview.addItems(self.loaded_long_data.columns.tolist())

            # The user may have loaded in new data and the subsetter's fields should reflect that
            self.subsetter.update_subsetable_fields()

            # %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
            # Fifth Section - (Upcoming) Subset the data accordingly if the criteria is set

            self.loaded_long_data = self.subsetter.subset_data(self.loaded_long_data)

            # %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
            # Sixth Section - Housekeeping and Finishing touches
            # Alter this when Section 5 is completed; long_data is the "good copy" of the data that will be plotted
            self.long_data = self.loaded_long_data
            self.cmb_figuretypeselection.setEnabled(True)  # Data is loaded; figure selection settings can be enabled
            self.btn_subset_data.setEnabled(True)  # Data is loaded; subsetting is allowed

            # In case any of this was done again (data was already loaded once before), we must account for what may
            # have already been plotted or set; everything must be cleared. This should be as easy as setting the
            # figureselection to the first index, as plots & settings can only exist if its current index is non-zero,
            # and setting it to zero has the benefit of clearing everything else already
            if self.cmb_figuretypeselection.currentIndex() != 0:
                self.cmb_figuretypeselection.setCurrentIndex(0)



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
            QMessageBox().warning(self,
                                  "Unsupported File Type",
                                  "This program only accepts the following filetypes:\n"
                                  "Comma-separated values (*.csv)\n"
                                  "Tab-separated values (*.tsv)\n"
                                  "Microsoft Excel spreadsheets (*.xlsx)",
                                  QMessageBox.Ok)
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
        return merged


# noinspection PyAttributeOutsideInit
class xASL_GUI_Subsetter(QWidget):
    def __init__(self, parent=None):
        super(xASL_GUI_Subsetter, self).__init__(parent)
        self.setWindowFlag(Qt.Window)
        self.setWindowTitle("Subset the data")
        self.font_format = QFont()
        self.font_format.setPointSize(16)

        # This will be used to keep track of columns that have already been added to the subset form layout
        self.current_rows = {}

        # Main Setup
        self.Setup_UI_MainWidgets()

    def Setup_UI_MainWidgets(self):
        self.mainlay = QVBoxLayout(self)
        self.formlay_headers = QFormLayout()
        self.formlay_subsets = QFormLayout()
        self.lab_inform_reload = QLabel("Changes will not take place until you re-load the data")
        self.lab_inform_reload.setFont(self.font_format)
        self.formlay_headers.addRow(QLabel("Column Names"), QLabel("\t\tSubset on"))

        self.mainlay.addLayout(self.formlay_headers)
        self.mainlay.addLayout(self.formlay_subsets)
        self.mainlay.addWidget(self.lab_inform_reload)

    # Updates the current fields that are permitted to be subset.
    def update_subsetable_fields(self):
        df = self.parent().loaded_long_data
        colnames = df.columns
        for name in colnames:
            # print(f"Name: {name} \t dtype: {str(df[name].dtype)}")
            # Skip any column based on criteria
            if any([name in self.current_rows.keys(),  # skip if already encountered
                    str(df[name].dtype) not in ["object", "category"],  # skip if not categorical
                    name in ["SUBJECT", "SubjectNList"]  # skip some unnecessary defaults with too many categories
                    ]):
                continue

            # Otherwise, create a combobox, add it to the form layout, and add the method to the current text as a
            # value, as this will be used to
            cmb = QComboBox()
            cmb.addItems(["Select a subset"] + df[name].unique().tolist())
            self.formlay_subsets.addRow(name, cmb)
            self.current_rows[name] = cmb.currentText

    # Convenience function for purging everything in the event that either the analysis directory changes or the
    # supplementary data file provided is changed
    def clear_contents(self):
        # Clear the dict
        self.current_rows.clear()
        # Clear the rows of the format layout
        for ii in range(self.formlay_subsets.rowCount()):
            self.formlay_subsets.removeRow(0)

    # The active function that will subset the data; takes in a dataframe and subsets it
    def subset_data(self, long_df):
        for key, call in self.current_rows.items():
            if call() != "Select a subset":
                print(f"Subsetting {key} on {call()}")
                long_df = long_df.loc[long_df[key] == call(), :]

        return long_df




