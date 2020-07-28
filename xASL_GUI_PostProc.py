from PySide2.QtWidgets import *
from PySide2.QtGui import *
from PySide2.QtCore import *
from xASL_GUI_HelperClasses import DandD_ListWidget2LineEdit
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
        if parent_win is not None:
            self.config = self.parent().config
        else:
            with open("ExploreASL_GUI_masterconfig.json") as f:
                self.config = json.load(f)

        # Load in the JSON for most of the important graph settings
        with open("xASL_GUI_GraphSettings.json") as f:
            self.graph_settings: dict = json.load(f)

        # This variable relates the main type of plot argument to the seaborn function it will feed arguments into
        self.plot_guide = {
            "Relational Gridplot": sns.relplot,
            "Categorical Gridplot": sns.catplot,
            "Linear Models Gridplot": sns.lmplot
        }
        # This variable relates the "widget" keyword argument in the graph settings JSON to the builder functions for
        # the widgets that appear
        self.widget_creation_guide = {
            "d&d_lineedit": self.create_clearable_lineedit,
            "combobox": self.create_plotting_combobox,
            "checkbox": self.create_plotting_checkbox,
            "doublespinbox": self.create_plotting_doublespinbox,
            "spinbox": self.create_plotting_spinbox,
        }
        # These variables are dicts for preparing constructors
        self.plot_contructor_args = {}

        # Window Size and initial visual setup
        self.setMinimumSize(1920, 1080)
        self.cw = QWidget(self)
        self.setCentralWidget(self.cw)
        self.mainlay = QVBoxLayout(self.cw)
        self.cw.setLayout(self.mainlay)
        self.setWindowTitle("Explore ASL - Post Processing Visualization")
        self.setWindowIcon(QIcon(os.path.join(os.getcwd(), "media", "ExploreASL_logo.png")))
        # self.mainfig = Figure()
        # self.canvas = FigureCanvas(self.mainfig)
        # self.nav = NavigationToolbar(self.canvas, self.canvas)
        # self.mainlay.addWidget(self.nav)
        # self.mainlay.addWidget(self.canvas)

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
        self.le_analysis_dir = QLineEdit(self.parent().config["DefaultRootDir"], self.grp_directories)
        self.cmb_atlas_selection = QComboBox(self.grp_directories)
        self.cmb_atlas_selection.addItems(["MNI", "Hammers"])
        self.cmb_pvc_selection = QComboBox(self.grp_directories)
        self.cmb_pvc_selection.addItems(["Without Partial Volume Correction", "With Partial Volume Correction"])
        self.cmb_stats_selection = QComboBox(self.grp_directories)
        self.cmb_stats_selection.addItems(["Mean", "Median", "Coefficient of Variation"])
        self.btn_load_in_data = QPushButton("Load Data", self.grp_directories, clicked=self.load_data)
        self.formlay_directories.addRow("Analysis Directory", self.le_analysis_dir)
        self.formlay_directories.addRow("Which Atlas to Utilize", self.cmb_atlas_selection)
        self.formlay_directories.addRow("Which Partial-Volume Stats to View", self.cmb_pvc_selection)
        self.formlay_directories.addRow("Which Statistic to View", self.cmb_stats_selection)
        self.formlay_directories.addRow(self.btn_load_in_data)

        # Setup the main Variable Viewer
        self.grp_varview = QGroupBox("Variables", self.cont_maindock)
        self.vlay_varview = QVBoxLayout(self.grp_varview)
        self.lst_varview = QListWidget(self.grp_varview)
        self.lst_varview.setMaximumHeight(400)
        self.lst_varview.setDragEnabled(True)
        self.vlay_varview.addWidget(self.lst_varview)

        # Setup the start of Plotting Settings
        self.grp_pltsettings = QGroupBox("Plotting Settings", self.cont_maindock)
        self.vlay_pltsettings = QVBoxLayout(self.grp_pltsettings)
        self.cmb_pltsettings = QComboBox(self.grp_pltsettings)
        self.cmb_pltsettings.addItems(["Select an option"] + list(self.graph_settings.keys()))
        self.cmb_pltsettings.setEnabled(False)
        self.cont_pltsettings = QWidget(self.grp_pltsettings)
        self.formlay_pltsettings = QFormLayout(self.cont_pltsettings)
        self.vlay_pltsettings.addWidget(self.cmb_pltsettings)
        self.vlay_pltsettings.addWidget(self.cont_pltsettings)

        # Add the groups to the main vertical layout
        self.vlay_maindock.addWidget(self.grp_directories)
        self.vlay_maindock.addWidget(self.grp_varview)
        self.vlay_maindock.addWidget(self.grp_pltsettings)
        self.vlay_maindock.addStretch()

        # This has to go at the end due to order of initialization
        self.cmb_pltsettings.currentTextChanged.connect(self.UI_Setup_AxesSettings)

    def UI_Setup_AxesSettings(self, plot_kind):
        # Clear the formlayout each time a plot is switched
        for ii in range(self.formlay_pltsettings.rowCount()):
            self.formlay_pltsettings.removeRow(0)

        # Clear the plot guide who will be holding links between arguments and widget values
        self.plot_contructor_args.clear()

        # Stop early if selecting "Select an option"
        if self.cmb_pltsettings.currentText() == "Select an option":
            return

        # Otherwise, start indexing out the sub_dicts that will be required
        self.selected_plot = self.graph_settings[plot_kind]
        figure_type = self.selected_plot["Figure Type"]

        if figure_type == "Grid":
            self.UI_Setup_GridPlot()

    # Scenario where the selected plot is of a gridtype (relplot, catplot, lmplot)
    def UI_Setup_GridPlot(self):

        # First, we must set up or clear the "standard arguments" dict;
        # will contain arguments that can be represented by data primitives such as bool, int, string, etc.;
        # dict-like args will be set up separately
        self.standard_args = {}

        # Iterate over the "standard args" dict to set up widgets and establish connections between the widgets and the
        # keyword arguments
        for keyword, subargs in self.selected_plot["standard args"].items():
            self.standard_args.setdefault(keyword, {})

            # Create the widgets
            widget_code = subargs["widget"]
            row_wid = None  # Widget to add to the format layout
            widgets = self.widget_creation_guide[subargs["widget"]](subargs)

            # Create associations between the widget's method and the keyword argument; also, extract the relevant
            # widget out of the widgets variable
            if widget_code == 'd&d_lineedit':
                row_wid, le, _ = widgets
                self.standard_args[keyword]["link"] = le.text
                self.standard_args[keyword]["needs_translator"] = False
            elif widget_code == 'combobox':
                row_wid = widgets
                self.standard_args[keyword]["link"] = row_wid.currentText
                self.standard_args[keyword]["needs_translator"] = True
                self.standard_args[keyword]["translator"] = subargs["translator"]
            elif widget_code == "doublespinbox" or widget_code == 'spinbox':
                row_wid = widgets
                self.standard_args[keyword]["link"] = row_wid.value
                self.standard_args[keyword]["needs_translator"] = False
            elif widget_code == 'checkbox':
                row_wid = widgets
                self.standard_args[keyword]["link"] = row_wid.isChecked
                self.standard_args[keyword]["needs_translator"] = False

            # Add the extracted widget to the formlayout
            if row_wid is not None:
                self.formlay_pltsettings.addRow(subargs["name"], row_wid)

        # Next, we must take care of all the dict-like arguments
        if "other args" in self.selected_plot.keys():

            # Simiarl to before but keep in mind whether the other arguments are of a "nested" variety, or
            # whether they exist as separate widgets (example, setting the figure title or labels, which is done outside
            # of the constructor).
            for kwarglike_argument, parms in self.selected_plot["other args"].items():
                if parms["type"] == "nested":
                    placeholder = {}
                    placeholder.setdefault(kwarglike_argument, {})

                    for keyword, subargs in parms["args"].items():
                        placeholder[kwarglike_argument][keyword] = {}

                        # Create the widgets
                        widget_code = subargs["widget"]
                        row_wid = None
                        widgets = self.widget_creation_guide[subargs["widget"]](subargs)

                        # Create associations between the widget's method and the keyword argument; also, extract the relevant
                        # widget out of the widgets variable
                        if widget_code == 'd&d_lineedit':
                            row_wid, le, _ = widgets
                            placeholder[kwarglike_argument][keyword]["link"] = le.text
                            placeholder[kwarglike_argument][keyword]["needs_translator"] = False
                        elif widget_code == "combobox":
                            row_wid = widgets
                            placeholder[kwarglike_argument][keyword]["link"] = row_wid.currentText
                            placeholder[kwarglike_argument][keyword]["needs_translator"] = True
                            placeholder[kwarglike_argument][keyword]["translator"] = subargs["translator"]
                        elif widget_code == "doublespinbox" or widget_code == "spinbox":
                            row_wid = widgets
                            placeholder[kwarglike_argument][keyword]["link"] = row_wid.value
                            placeholder[kwarglike_argument][keyword]["needs_translator"] = False
                        elif widget_code == "checkbox":
                            row_wid = widgets
                            placeholder[kwarglike_argument][keyword]["link"] = row_wid.isChecked
                            placeholder[kwarglike_argument][keyword]["needs_translator"] = False

                        if row_wid is not None:
                            self.formlay_pltsettings.addRow(subargs["name"], row_wid)

                    # pprint(placeholder)
                    # Update the contructor if this is a nested type of other argument
                    self.standard_args.update(placeholder)

        # Regardless if there were other arguments or not, add in the "update plot" button at the very end
        # pprint(self.standard_args)
        self.formlay_pltsettings.addRow(QPushButton("Update Plot", clicked=self.update_plot))
        self.formlay_pltsettings.addRow(QPushButton("Destory Plot", clicked=self.destroy_plot))

    # Self-explanatory; updates the current figure
    def update_plot(self):
        # First we must convert all the associations into the actual present values by calling the stores methods
        constructor = self.set_plotting_constructor()
        # pprint(constructor)

        g = self.plot_guide[self.cmb_pltsettings.currentText()](data=self.long_data, **constructor)

        # Destroy the previous canvas and navtoolbar
        self.mainlay.removeWidget(self.nav)
        self.mainlay.removeWidget(self.canvas)
        # plt.clf()
        # del self.canvas
        # del self.nav

        # Create the new canvas and place it in there
        self.canvas = FigureCanvas(g.fig)
        self.nav = NavigationToolbar(self.canvas, self.canvas)
        self.mainlay.addWidget(self.nav)
        self.mainlay.addWidget(self.canvas)
        self.canvas.updateGeometry()
        QApplication.instance().processEvents()

    def destroy_plot(self):

        self.canvas.draw_idle()
        print("Cleared plot and trying to create another")
        self.canvas.draw_idle()

    # Creates a constructor dictionary for creating the desired plot
    def set_plotting_constructor(self):
        constructor = {}

        for primary_kwarg, parms in self.standard_args.items():
            # Check if this is a nested dict; if it isn't proceed as normal
            if "link" in parms.keys():
                if not parms["needs_translator"]:
                    argument = parms["link"]()
                    constructor[primary_kwarg] = parms["link"]()
                else:
                    argument = parms["translator"][parms["link"]()]

                if argument == "":
                    argument = None

                constructor[primary_kwarg] = argument

            # Otherwise, this is a 1-level nested dictionary
            else:
                constructor[primary_kwarg] = {}
                for secondary_kwarg, s_parms in parms.items():
                    if not s_parms["needs_translator"]:
                        argument = s_parms["link"]()
                    else:
                        argument = s_parms["translator"][s_parms["link"]()]

                    if argument == "":
                        argument = None

                    constructor[primary_kwarg][secondary_kwarg] = argument

        return constructor

    def create_clearable_lineedit(self, subargs):
        hbox = QHBoxLayout()
        le = DandD_ListWidget2LineEdit(self.current_dtypes, subargs["dtype"])
        btn = QPushButton("Clear", clicked=le.clear)
        hbox.addWidget(le)
        hbox.addWidget(btn)
        return hbox, le, btn

    def create_plotting_combobox(self, subargs):
        cmb = QComboBox()
        cmb.addItems(subargs["default"])
        return cmb

    def create_plotting_doublespinbox(self, subargs):
        dblspin = QDoubleSpinBox()
        dblspin.setValue(subargs["default"])
        dblspin.setRange(subargs["min"], subargs["max"])
        dblspin.setSingleStep(subargs["step"])
        return dblspin

    def create_plotting_spinbox(self, subargs):
        spin = QSpinBox()
        spin.setValue(subargs["default"])
        spin.setRange(subargs["min"], subargs["max"])
        spin.setSingleStep(subargs["step"])
        return spin

    def create_plotting_checkbox(self, subargs):
        chkbox = QCheckBox()
        if subargs["default"]:
            chkbox.setChecked(True)
        else:
            chkbox.setChecked(False)
        return chkbox

    # Loads in data as a pandas dataframe
    def load_data(self):
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
                           "Site": "category", "AcquisitionTime": "int", "GM_vol": "float64",
                           "WM_vol": "float64", "CSF_vol": "float64", "GM_ICVRatio": "float64",
                           "GMWM_ICVRatio": "float64"}
            for col in df.columns:
                if col in dtype_guide.keys():
                    df[col] = df[col].astype(dtype_guide[col])
                else:
                    df[col] = df[col].astype("float64")
            self.data = df
            # %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
            # FUTURE SECTION HERE FOR MERGING WITH A PROVIDED SUBJECT DATAFRAME
            # %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

            # also generate the long version of the data
            id_vars = [col for col in df.columns if not any([col.endswith("_B"),
                                                             col.endswith("_L"),
                                                             col.endswith("_R")])]
            value_vars = [col for col in df.columns if any([col.endswith("_B"),
                                                            col.endswith("_L"),
                                                            col.endswith("_R")])]
            self.long_data: pd.DataFrame = df.melt(id_vars=id_vars,
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


