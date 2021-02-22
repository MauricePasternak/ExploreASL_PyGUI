from PySide2.QtWidgets import *
from PySide2.QtGui import *
from PySide2.QtCore import QSize
from src.xASL_GUI_HelperClasses import DandD_FileExplorer2ListWidget
from src.xASL_GUI_Executor_ancillary import is_earlier_version
from src.xASL_GUI_HelperFuncs_WidgetFuncs import (make_scrollbar_area, make_droppable_clearable_le, set_formlay_options,
                                                  robust_getdir, robust_getfile, robust_qmsg)
import json
import re
from pathlib import Path
from tdda import rexpy
from more_itertools import peekable
from functools import partial
from shutil import which
from typing import List, Union
from platform import system


class xASL_Parms(QMainWindow):
    def __init__(self, parent_win=None):
        # Parent window is fed into the constructor to allow for communication with parent window devices
        super().__init__(parent=parent_win)
        self.config = self.parent().config
        with open(Path(self.config["ProjectDir"]) / "JSON_LOGIC" / "ErrorsListing.json") as parms_err_reader:
            self.parms_errs = json.load(parms_err_reader)
        with open(Path(self.config["ProjectDir"]) / "JSON_LOGIC" / "ToolTips.json") as parms_tips_reader:
            self.parms_tips = json.load(parms_tips_reader)["ParmsMaker"]
        # Window Size and initial visual setup
        self.cw = QWidget(self)
        self.setCentralWidget(self.cw)
        self.mainlay = QVBoxLayout(self.cw)
        self.setLayout(self.mainlay)
        self.setWindowTitle("Explore ASL - Define Study Parameters")

        # Buttons for executing the fundamental functions
        btn_font = QFont()
        btn_font.setPointSize(16)
        self.btn_make_parms = QPushButton("Create DataPar file", self.cw, clicked=self.saveparms2json)
        self.btn_load_parms = QPushButton("Load existing DataPar file", self.cw, clicked=self.loadjson2parms)
        for btn, pic_file in zip([self.btn_make_parms, self.btn_load_parms],
                                 ["export_clipart_80x80.png", "import_clipart_80x80.png"]):
            btn.setFont(btn_font)
            btn.setMinimumHeight(50)
            btn.setIcon(QIcon(str(Path(self.config["ProjectDir"]) / "media" / pic_file)))
            btn.setIconSize(QSize(50, 50))

        # TabWidget Setup and containers
        self.tab_main = QTabWidget(self.cw)
        self.mainlay.addWidget(self.tab_main)
        self.cont_basic = QWidget()
        self.cont_advanced = QWidget()
        self.cont_proc_settings = QWidget()
        self.tab_main.addTab(self.cont_basic, "Basic Settings")
        self.tab_main.addTab(self.cont_advanced, "Sequence && Quantification Settings")
        self.tab_main.addTab(self.cont_proc_settings, "Processing && Masking Settings")
        self.tab_main.adjustSize()

        self.mainlay.addWidget(self.btn_make_parms)
        self.mainlay.addWidget(self.btn_load_parms)

        # Misc Players
        self.import_error_logger = []
        self.asl_json_sidecar_data = {}
        self.can_update_slicereadouttime = False

        self.UI_Setup_Basic()
        self.UI_Setup_Advanced()
        self.UI_Setup_ProcessingSettings()
        # With all widgets set, give them tooltips
        for widget_name, tiptext in self.parms_tips.items():
            getattr(self, widget_name).setToolTip(tiptext)

        # After all UI is set up, make certain connections
        self.resize(self.minimumSizeHint())

        # Additional MacOS actions
        if system() == "Darwin":
            self.btn_load_parms.setMinimumHeight(60)
            self.btn_make_parms.setMinimumHeight(60)

    def UI_Setup_Basic(self):
        self.formlay_basic = QFormLayout(self.cont_basic)
        self.current_easl_type = "Local ExploreASL Directory"
        self.cmb_easl_type = self.make_cmb_and_items(["Local ExploreASL Directory", "Local ExploreASL Compiled"])
        self.cmb_easl_type.currentTextChanged.connect(self.switch_easldir_opts)

        # The ExploreASL directory possibilities
        self.hlay_mrc_dir, self.le_mrc_dir, self.btn_mrc_dir = make_droppable_clearable_le(
            btn_connect_to=self.set_mcr_dir, default="")
        self.hlay_easl_mcr, self.le_easl_mcr, self.btn_easl_mcr = make_droppable_clearable_le(
            btn_connect_to=self.set_exploreasl_mcr, default="")
        self.hlay_easl_dir, self.le_easl_dir, self.btn_easl_dir = make_droppable_clearable_le(
            btn_connect_to=self.set_exploreasl_dir, default='')

        # The path to the study directory
        self.le_studyname = QLineEdit(text="My Study")
        self.chk_overwrite_for_bids = QCheckBox(checked=False)
        self.hlay_study_dir, self.le_study_dir, self.btn_study_dir = make_droppable_clearable_le(
            btn_connect_to=self.set_study_dir, default='')
        self.le_study_dir.setPlaceholderText("Indicate the analysis directory filepath here")

        self.le_subregex = QLineEdit(text='\\d+')
        self.le_subregex.setVisible(False)
        self.chk_showregex_field = QCheckBox(text="Show Current Regex", checked=False)
        self.chk_showregex_field.stateChanged.connect(self.le_subregex.setVisible)

        self.lst_included_subjects = DandD_FileExplorer2ListWidget()
        self.lst_included_subjects.itemsAdded.connect(self.update_regex)
        self.lst_included_subjects.setMinimumHeight(self.config["ScreenSize"][1] // 5)
        self.btn_included_subjects = QPushButton("Clear Subjects", clicked=self.clear_included)
        self.lst_excluded_subjects = DandD_FileExplorer2ListWidget()
        self.lst_excluded_subjects.setMinimumHeight(self.config["ScreenSize"][1] // 10)
        self.btn_excluded_subjects = QPushButton("Clear Excluded", clicked=self.lst_excluded_subjects.clear)
        self.cmb_vendor = self.make_cmb_and_items(["Siemens", "Philips", "GE", "GE_WIP"])
        self.cmb_sequencetype = self.make_cmb_and_items(["3D GRaSE", "2D EPI", "3D Spiral"])
        self.cmb_sequencetype.currentTextChanged.connect(self.update_readout_dim)
        self.cmb_labelingtype = self.make_cmb_and_items(["Pulsed ASL", "Pseudo-continuous ASL", "Continuous ASL"])
        self.cmb_labelingtype.currentTextChanged.connect(self.autocalc_slicereadouttime)
        self.lab_spin_m0_isseparate = QLabel(text="M0 Single Value")
        self.spinbox_m0_isseparate = QDoubleSpinBox(minimum=1, maximum=1E12, value=1E6)
        self.cmb_m0_isseparate = self.make_cmb_and_items(["Proton density scan (M0) was acquired",
                                                          "Use mean control ASL as M0 mimic",
                                                          "Use a single value as the M0"])
        self.cmb_m0_isseparate.currentTextChanged.connect(self.enable_m0value_field)
        self.cmb_m0_isseparate.currentTextChanged.connect(self.m0_pos_in_asl_ctrlfunc)
        self.cmb_m0_posinasl = self.make_cmb_and_items(
            ["M0 exists as a separate scan", "M0 is the first ASL control-label pair",
             "M0 is the first ASL scan volume", "M0 is the second ASL scan volume"])
        self.cmb_quality = self.make_cmb_and_items(["Low", "High"])
        self.cmb_quality.setCurrentIndex(1)

        for desc, widget in zip(["ExploreASL Type", "ExploreASL Directory", "Name of Study", "Analysis Directory",
                                 "Dataset is in BIDS format?", self.chk_showregex_field,
                                 "Subjects to Assess\n(Drag && Drop Directories)", "",
                                 "Subjects to Exclude\n(Drag && Drop Directories)", "",
                                 "Vendor", "Sequence Type",
                                 "Labelling Type", "M0 was acquired?", "Single M0 Value",
                                 "M0 Position in ASL", "Quality"],
                                [self.cmb_easl_type, self.hlay_easl_dir, self.le_studyname, self.hlay_study_dir,
                                 self.chk_overwrite_for_bids, self.le_subregex,
                                 self.lst_included_subjects, self.btn_included_subjects,
                                 self.lst_excluded_subjects, self.btn_excluded_subjects,
                                 self.cmb_vendor, self.cmb_sequencetype, self.cmb_labelingtype,
                                 self.cmb_m0_isseparate, self.spinbox_m0_isseparate,
                                 self.cmb_m0_posinasl, self.cmb_quality]):
            self.formlay_basic.addRow(desc, widget)
            if system() == "Darwin":
                try:
                    widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                except AttributeError:
                    continue

        self.spinbox_m0_isseparate.setEnabled(False)
        # MacOS specific additional actions
        if system() == "Darwin":
            set_formlay_options(self.formlay_basic, row_wrap_policy="dont_wrap", vertical_spacing=5)
            self.lst_included_subjects.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def UI_Setup_Advanced(self):
        # First, set up the groupboxes and add them to the advanced tab layout
        self.vlay_advanced = QVBoxLayout(self.cont_advanced)
        self.grp_seqparms = QGroupBox(title="Sequence Parameters")
        self.grp_quantparms = QGroupBox(title="Quantification Parameters")
        self.grp_m0parms = QGroupBox(title="M0 Parameters")
        self.grp_envparms = QGroupBox(title="Environment Parameters")
        for grp in [self.grp_seqparms, self.grp_quantparms, self.grp_m0parms, self.grp_envparms]:
            self.vlay_advanced.addWidget(grp)

        # Set up the Sequence Parameters
        self.vlay_seqparms, self.scroll_seqparms, self.cont_seqparms = make_scrollbar_area(self.grp_seqparms)
        self.formlay_seqparms = QFormLayout(self.cont_seqparms)
        self.cmb_nsup_pulses = self.make_cmb_and_items(["0", "2", "4", "5"], 1)
        self.le_sup_pulse_vec = QLineEdit(placeholderText="Vector of timings, in seconds, of suppression pulses")
        self.cmb_readout_dim = self.make_cmb_and_items(["3D", "2D"])
        self.spinbox_initialpld = QDoubleSpinBox(maximum=2500, minimum=0, value=1800)
        self.spinbox_initialpld.valueChanged.connect(self.autocalc_slicereadouttime)
        self.spinbox_labdur = QDoubleSpinBox(maximum=2000, minimum=0, value=800)
        self.spinbox_labdur.valueChanged.connect(self.autocalc_slicereadouttime)
        self.hlay_slice_readout = QHBoxLayout()
        self.cmb_slice_readout = self.make_cmb_and_items(["Use Indicated Value", "Use Shortest TR"])
        self.spinbox_slice_readout = QDoubleSpinBox(maximum=1000, minimum=0, value=37)
        self.hlay_slice_readout.addWidget(self.cmb_slice_readout)
        self.hlay_slice_readout.addWidget(self.spinbox_slice_readout)
        for description, widget in zip(["Number of Suppression Pulses", "Suppression Timings", "Readout Dimension",
                                        "Initial Post-Labeling Delay (ms)", "Labeling Duration (ms)",
                                        "Slice Readout Time (ms)"],
                                       [self.cmb_nsup_pulses, self.le_sup_pulse_vec, self.cmb_readout_dim,
                                        self.spinbox_initialpld,
                                        self.spinbox_labdur, self.hlay_slice_readout]):
            self.formlay_seqparms.addRow(description, widget)
            if system() == "Darwin":
                try:
                    widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                except AttributeError:
                    continue

        # Set up the Quantification Parameters
        self.vlay_quantparms, self.scroll_quantparms, self.cont_quantparms = make_scrollbar_area(self.grp_quantparms)
        self.formlay_quantparms = QFormLayout(self.cont_quantparms)
        self.spinbox_lambda = QDoubleSpinBox(maximum=1, minimum=0, value=0.9, singleStep=0.01)
        self.spinbox_artt2 = QDoubleSpinBox(maximum=100, minimum=0, value=50, singleStep=0.1)
        self.spinbox_bloodt1 = QDoubleSpinBox(maximum=2000, minimum=0, value=1650, singleStep=0.1)
        self.spinbox_tissuet1 = QDoubleSpinBox(maximum=2000, minimum=0, value=1240, singleStep=0.1)
        self.cmb_ncomparts = self.make_cmb_and_items(["1", "2"], 0)
        self.chk_quant_applyss_asl = QCheckBox(checked=True)
        self.chk_quant_applyss_m0 = QCheckBox(checked=True)
        self.chk_quant_pwi2label = QCheckBox(checked=True)
        self.chk_quant_quantifym0 = QCheckBox(checked=True)
        self.chk_quant_divbym0 = QCheckBox(checked=True)
        self.chk_save_cbf4d = QCheckBox(checked=False)
        for description, widget in zip(["Lambda", "Arterial T2*", "Blood T1", "Tissue T1", "Number of Compartments",
                                        "Apply Scaling to ASL", "Apply Scaling to M0", "Convert PWI to Label",
                                        "Quantify M0", "Divide by M0", "Save CBF as Timeseries"],
                                       [self.spinbox_lambda, self.spinbox_artt2, self.spinbox_bloodt1,
                                        self.spinbox_tissuet1, self.cmb_ncomparts, self.chk_quant_applyss_asl,
                                        self.chk_quant_applyss_m0, self.chk_quant_pwi2label, self.chk_quant_quantifym0,
                                        self.chk_quant_divbym0, self.chk_save_cbf4d]):
            self.formlay_quantparms.addRow(description, widget)
            if system() == "Darwin":
                try:
                    widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                except AttributeError:
                    continue

        # Set up the remaining M0 Parameters
        self.vlay_m0parms, self.scroll_m0parms, self.cont_m0parms = make_scrollbar_area(self.grp_m0parms)
        self.scroll_m0parms.setMinimumHeight(self.config["ScreenSize"][1] // 16)
        self.formlay_m0parms = QFormLayout(self.cont_m0parms)
        self.cmb_m0_algorithm = self.make_cmb_and_items(["New Image Processing", "Standard Processing"], 0)
        self.spinbox_gmscale = QDoubleSpinBox(maximum=100, minimum=0.01, value=1, singleStep=0.01)
        for description, widget in zip(["M0 Processing Algorithm", "GM Scale Factor"],
                                       [self.cmb_m0_algorithm, self.spinbox_gmscale]):
            self.formlay_m0parms.addRow(description, widget)
            if system() == "Darwin":
                try:
                    widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                except AttributeError:
                    continue

        # Set up the Environment Parameters
        self.vlay_envparms, self.scroll_envparms, self.cont_envparms = make_scrollbar_area(self.grp_envparms)
        self.scroll_envparms.setMinimumHeight(self.config["ScreenSize"][1] // 17.5)
        self.formlay_envparms = QFormLayout(self.cont_envparms)
        (self.hlay_fslpath, self.le_fslpath,
         self.btn_fslpath) = make_droppable_clearable_le(btn_connect_to=self.set_fslpath)
        fsl_filepath = which("fsl")
        if fsl_filepath is not None:
            self.le_fslpath.setText(str(Path(fsl_filepath)))
        self.chk_outputcbfmaps = QCheckBox(checked=False)
        for desc, widget in zip(["Path to FSL bin directory", "Output CBF native space maps?"],
                                [self.hlay_fslpath, self.chk_outputcbfmaps]):
            self.formlay_envparms.addRow(desc, widget)
            if system() == "Darwin":
                try:
                    widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                except AttributeError:
                    continue

        # Additional MacOS settings:
        if system() == "Darwin":
            for formlay, vspacing in zip([self.formlay_seqparms, self.formlay_quantparms, self.formlay_m0parms,
                                          self.formlay_envparms],
                                         [5, 5, 5, 5]):
                set_formlay_options(formlay, row_wrap_policy="dont_wrap", vertical_spacing=vspacing)
            self.cmb_slice_readout.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def UI_Setup_ProcessingSettings(self):
        self.vlay_procsettings = QVBoxLayout(self.cont_proc_settings)

        self.grp_genpparms = QGroupBox(title="General Processing Parameters")
        self.grp_strpparms = QGroupBox(title="Structural Processing Parameters")
        self.grp_aslpparms = QGroupBox(title="ASL Processing Parameters")
        self.grp_maskparms = QGroupBox(title="Masking Parameters")
        for grp in [self.grp_genpparms, self.grp_strpparms, self.grp_aslpparms, self.grp_maskparms]:
            self.vlay_procsettings.addWidget(grp)

        # Set up the General Processing Parameters
        self.vlay_genpparms, self.scroll_genpparms, self.cont_genpparms = make_scrollbar_area(self.grp_genpparms)
        self.formlay_genpparms = QFormLayout(self.cont_genpparms)
        self.chk_removespikes = QCheckBox(checked=True)
        self.spinbox_spikethres = QDoubleSpinBox(maximum=1, minimum=0, value=0.01, singleStep=0.01)
        self.chk_motioncorrect = QCheckBox(checked=True)
        self.chk_deltempfiles = QCheckBox(checked=True)
        self.chk_skipnoflair = QCheckBox(checked=False)
        self.chk_skipnoasl = QCheckBox(checked=True)
        self.chk_skipnom0 = QCheckBox(checked=False)
        for desc, widget in zip(["Remove Spikes", "Spike Removal Threshold", "Correct for Motion",
                                 "Delete Temporary Files", "Skip Subjects without FLAIR",
                                 "Skip Subjects without ASL", "Skip subjects without M0"],
                                [self.chk_removespikes, self.spinbox_spikethres, self.chk_motioncorrect,
                                 self.chk_deltempfiles, self.chk_skipnoflair, self.chk_skipnoasl,
                                 self.chk_skipnom0]):
            self.formlay_genpparms.addRow(desc, widget)
            if system() == "Darwin":
                try:
                    widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                except AttributeError:
                    continue

        # Set up the Structural Processing Parameters
        self.vlay_strpparms, self.scroll_strpparms, self.cont_strpparms = make_scrollbar_area(self.grp_strpparms)
        self.formlay_strpparms = QFormLayout(self.cont_strpparms)
        self.cmb_segmethod = self.make_cmb_and_items(["CAT12", "SPM12"], 0)
        self.chk_runlongreg = QCheckBox(checked=False)
        self.chk_run_dartel = QCheckBox(checked=False)
        self.chk_hammersroi = QCheckBox(checked=False)
        self.chk_fixcat12res = QCheckBox(checked=False)

        for desc, widget in zip(["Segmentation Method", "Run DARTEL Module", "Longitudinal Registration", "Hammers ROI",
                                 "Fix CAT12 Resolution"],
                                [self.cmb_segmethod, self.chk_run_dartel, self.chk_runlongreg, self.chk_hammersroi,
                                 self.chk_fixcat12res]):
            self.formlay_strpparms.addRow(desc, widget)
            if system() == "Darwin":
                try:
                    widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                except AttributeError:
                    continue

        # Set up the ASL Processing Parameters
        self.vlay_aslpparms, self.scroll_aslpparms, self.cont_aslpparms = make_scrollbar_area(self.grp_aslpparms)
        self.formlay_aslpparms = QFormLayout(self.cont_aslpparms)

        self.cmb_imgcontrast = self.make_cmb_and_items(["Automatic", "Control --> T1w", "CBF --> pseudoCBF",
                                                        "Force CBF --> pseudoCBF"], 0)
        self.cmb_affineregbase = self.make_cmb_and_items(["Based on PWI CoV", "Enabled", "Disabled"])
        self.cmb_dctreg = self.make_cmb_and_items(["Disabled", "Enabled + no PVC", "Enabled + PVC"])
        self.chk_regm0toasl = QCheckBox(checked=True)
        self.chk_usemniasdummy = QCheckBox(checked=False)
        self.chk_nativepvc = QCheckBox(checked=False)
        self.chk_gaussianpvc = QCheckBox(checked=False)
        self.hlay_pvckernel = QHBoxLayout()
        self.spinbox_pvckernel_1 = QSpinBox(minimum=1, maximum=20, value=5)
        self.spinbox_pvckernel_2 = QSpinBox(minimum=1, maximum=20, value=5)
        self.spinbox_pvckernel_3 = QSpinBox(minimum=1, maximum=20, value=1)
        for spinbox in [self.spinbox_pvckernel_1, self.spinbox_pvckernel_2, self.spinbox_pvckernel_3]:
            self.hlay_pvckernel.addWidget(spinbox)
        for desc, widget in zip(["Image Contrast used for",
                                 "Use Affine Registration", "Use DCT Registration", "Register M0 to ASL",
                                 "Use MNI as Dummy Template", "Perform Native PVC", "Gaussian Kernel for PVC",
                                 "PVC Kernel Dimensions"],
                                [self.cmb_imgcontrast,
                                 self.cmb_affineregbase, self.cmb_dctreg, self.chk_regm0toasl, self.chk_usemniasdummy,
                                 self.chk_nativepvc, self.chk_gaussianpvc, self.hlay_pvckernel]):
            self.formlay_aslpparms.addRow(desc, widget)
            if system() == "Darwin":
                try:
                    widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                except AttributeError:
                    continue

        # Set up the Masking Parameters
        self.vlay_maskparms, self.scroll_maskparms, self.cont_maskparms = make_scrollbar_area(self.grp_maskparms)
        self.formlay_maskparms = QFormLayout(self.cont_maskparms)
        self.chk_suscepmask = QCheckBox(checked=True)
        self.chk_subjectvasmask = QCheckBox(checked=True)
        self.chk_subjecttismask = QCheckBox(checked=True)
        self.chk_wholebrainmask = QCheckBox(checked=True)
        for desc, widget in zip(["Susceptibility Mask", "Vascular Mask", "Tissue Mask", "Wholebrain Mask"],
                                [self.chk_suscepmask, self.chk_subjectvasmask, self.chk_subjecttismask,
                                 self.chk_wholebrainmask]):
            self.formlay_maskparms.addRow(desc, widget)
            if system() == "Darwin":
                try:
                    widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                except AttributeError:
                    continue

        # Additional MacOS settings:
        if system() == "Darwin":
            for formlay, vspacing in zip([self.formlay_genpparms, self.formlay_strpparms, self.formlay_aslpparms,
                                          self.formlay_maskparms],
                                         [5, 5, 5, 5]):
                set_formlay_options(formlay, row_wrap_policy="dont_wrap", vertical_spacing=vspacing)

            self.spinbox_pvckernel_1.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            self.spinbox_pvckernel_2.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            self.spinbox_pvckernel_3.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    ################################
    # Json Sidecar Related Functions
    ################################
    def update_readout_dim(self, text):
        if text == "2D EPI":
            self.cmb_readout_dim.setCurrentIndex(1)
        else:
            self.cmb_readout_dim.setCurrentIndex(0)

    def autocalc_slicereadouttime(self):
        if not self.can_update_slicereadouttime or self.cmb_labelingtype.currentText() in ["Pseudo-continuous ASL",
                                                                                           "Continuous ASL"]:
            return

        tr = self.asl_json_sidecar_data["RepetitionTime"] * 1000
        labdur = self.spinbox_labdur.value()
        ini_pld = self.spinbox_initialpld.value()
        nslices = self.asl_json_sidecar_data["NumberOfSlices"]
        readouttime = round((tr - labdur - ini_pld) / nslices, 2)

        self.spinbox_slice_readout.setValue(readouttime)

    def overwrite_bids_fields(self):
        self.flag_impossible_m0 = False
        bad_jsons = []

        if self.config["DeveloperMode"]:
            print("Overwriting BIDS ASL json sidecar fields\n")

        analysis_dir = Path(self.le_study_dir.text())
        if not (analysis_dir / "dataset_description.json").exists():
            robust_qmsg(self, title=self.parms_errs["BIDSoverwriteforNonBIDS"][0],
                        body=self.parms_errs["BIDSoverwriteforNonBIDS"][1])
            return

        asl_jsons = peekable(analysis_dir.rglob("*_asl.json"))
        # If json sidecars cannot be found, exit early
        if not asl_jsons:
            robust_qmsg(self, title=self.parms_errs["NoJsonSidecars"][0], body=self.parms_errs["NoJsonSidecars"][1])
            return

        for asl_sidecar in asl_jsons:
            # Load in the data
            with open(asl_sidecar) as asl_sidecar_reader:
                asl_sidecar_data = json.load(asl_sidecar_reader)

            # M0 key behavior
            # Priority 1 - if there is an M0 present, use its path as the value
            possible_m0_json = Path(str(asl_sidecar).replace("_asl.json", "_m0scan.json"))
            relative_path = "/".join(str(possible_m0_json).replace('\\', '/').split('/')[-2:])

            if possible_m0_json.exists():
                asl_sidecar_data["M0"] = relative_path.replace("_m0scan.json", "_m0scan.nii")
            # Priority 2 - if the M0 is present within the asl nifti, as indicated by the user, go with that
            elif self.cmb_m0_isseparate.currentText() == "Proton density scan (M0) was acquired":

                if self.cmb_m0_posinasl.currentText() in ["M0 is the first ASL control-label pair",
                                                          "M0 is the first ASL scan volume",
                                                          "M0 is the second ASL scan volume"]:
                    asl_sidecar_data["M0"] = True
                else:
                    self.flag_impossible_m0 = True
                    bad_jsons.append(asl_sidecar)

            elif self.cmb_m0_isseparate.currentText() == "Use mean control ASL as M0 mimic":
                asl_sidecar_data["M0"] = False

            else:
                self.flag_impossible_m0 = True
                bad_jsons.append(asl_sidecar)

            # LabelingType
            asl_sidecar_data["LabelingType"] = {"Pulsed ASL": "PASL",
                                                "Pseudo-continuous ASL": "PCASL",
                                                "Continuous ASL": "CASL"
                                                }[self.cmb_labelingtype.currentText()]

            # Post Label Delay
            asl_sidecar_data["PostLabelingDelay"] = self.spinbox_initialpld.value() / 1000

            # Label Duration
            if self.cmb_labelingtype.currentText() in ["Pseudo-continuous ASL", "Continuous ASL"]:
                asl_sidecar_data["LabelingDuration"] = self.spinbox_labdur.value() / 1000

            # Background Suppression
            if self.cmb_nsup_pulses.currentText() == "0":
                asl_sidecar_data["BackgroundSuppression"] = False
            else:
                asl_sidecar_data["BackgroundSuppression"] = True

            # PulseSequenceType
            asl_sidecar_data["PulseSequenceType"] = {"3D Spiral": "3D_spiral",
                                                     "3D GRaSE": "3D_GRASE",
                                                     "2D EPI": "2D_EPI"}[self.cmb_sequencetype.currentText()]

            with open(asl_sidecar, 'w') as asl_sidecar_writer:
                json.dump(asl_sidecar_data, asl_sidecar_writer, indent=3)

        if self.flag_impossible_m0:
            bad_jsons = "; ".join([asl_json.stem for asl_json in bad_jsons])
            robust_qmsg(self, title=self.parms_errs["ImpossibleM0"][0],
                        body=self.parms_errs["ImpossibleM0"][1] + f"{bad_jsons}")

    ################
    # Misc Functions
    ################

    # Super inefficient...perhaps a better alternative exists?
    def switch_easldir_opts(self, option):
        print(f"{self.switch_easldir_opts.__name__} has received option: {option}")
        # Avoid false errors
        if self.current_easl_type == option:
            return
        # Otherwise, switch layout as needed
        if self.current_easl_type == "Local ExploreASL Directory" and option == "Local ExploreASL Compiled":
            row, _ = self.formlay_basic.getLayoutPosition(self.hlay_easl_dir)
            self.formlay_basic.removeRow(row)
            self.hlay_easl_mcr, self.le_easl_mcr, self.btn_easl_mcr = make_droppable_clearable_le(
                btn_connect_to=self.set_exploreasl_mcr, default="")
            self.hlay_mrc_dir, self.le_mrc_dir, self.btn_mrc_dir = make_droppable_clearable_le(
                btn_connect_to=self.set_mcr_dir, default="")
            self.formlay_basic.insertRow(row, "ExploreASL Runtime Directory", self.hlay_easl_mcr)
            self.formlay_basic.insertRow(row, "MATLAB Runtime Directory", self.hlay_mrc_dir)
            self.current_easl_type = "Local ExploreASL Compiled"

            # Tooltips
            self.le_easl_mcr.setToolTip(self.parms_tips["le_easl_mcr"])
            self.le_mrc_dir.setToolTip(self.parms_tips["le_mrc_dir"])

        elif self.current_easl_type == "Local ExploreASL Compiled" and option == "Local ExploreASL Directory":
            row, _ = self.formlay_basic.getLayoutPosition(self.hlay_mrc_dir)
            self.formlay_basic.removeRow(row)
            self.formlay_basic.removeRow(row)
            self.hlay_easl_dir, self.le_easl_dir, self.btn_easl_dir = make_droppable_clearable_le(
                btn_connect_to=self.set_exploreasl_dir, default='')
            self.formlay_basic.insertRow(row, "ExploreASL Directory", self.hlay_easl_dir)
            self.current_easl_type = "Local ExploreASL Directory"

            # Tooltips
            self.le_easl_dir.setToolTip(self.parms_tips["le_easl_dir"])

    # Controls the behavior of the M0 comboboxes
    def m0_pos_in_asl_ctrlfunc(self):
        if self.cmb_m0_isseparate.currentText() != "Proton density scan (M0) was acquired":
            self.cmb_m0_posinasl.setCurrentIndex(0)
            self.cmb_m0_posinasl.setEnabled(False)
        else:
            self.cmb_m0_posinasl.setEnabled(True)

    # Activates the spinbox for single-value M0 division if specified
    def enable_m0value_field(self, text):
        if text == "Use a single value as the M0":
            self.spinbox_m0_isseparate.setEnabled(True)
        else:
            self.spinbox_m0_isseparate.setEnabled(False)

    # Clears the currently-included subjects list and resets the regex
    def clear_included(self):
        self.lst_included_subjects.clear()
        self.le_subregex.clear()

    # Updates the current recognized regex
    def update_regex(self):
        n_subjects = self.lst_included_subjects.count()
        if n_subjects == 0:
            return
        subject_list = [self.lst_included_subjects.item(idx).text() for idx in range(n_subjects)]
        extractor = rexpy.Extractor(subject_list)
        extractor.extract()
        inferred_regex = extractor.results.rex[0]
        del extractor
        if inferred_regex:
            self.le_subregex.setText(inferred_regex)

    #########################################
    # LineEdit-setting and checking Functions
    #########################################
    def set_mcr_dir(self):
        errs = ["Invalid Matlab Runtime Directory", "The indicated directory must be of the name v## and contain the"
                                                    "glnxa64 library"]
        robust_getdir(self, "Path to MATLAB Runtime Directory", self.config["DefaultRootDir"],
                      {"basename_fits_regex": ["v\\d{2,3}", errs], "rcontains": ["glnxa64", errs]},
                      lineedit=self.le_mrc_dir)

    def set_exploreasl_mcr(self):
        errs = ["Invalid ExploreASL Compiled Runtime Directory",
                "The indicated directory must be the compiled directory containing the xASL_latest file"]
        robust_getdir(self, "Path to local ExploreASL compiled runtime", self.config["DefaultRootDir"],
                      {"child_file_exists": ["xASL_latest", errs]}, self.le_easl_mcr)

    def set_exploreasl_dir(self):
        errs = [self.parms_errs["InvalidExploreASLDir"][0], self.parms_errs["InvalidExploreASLDir"][1]]
        s, path = robust_getdir(self, "Path to local ExploreASL directory", self.config["DefaultRootDir"],
                                {"child_file_exists": ["ExploreASL_Master.m", errs]})
        if s:
            self.le_easl_dir.setText(str(path))

    def set_study_dir(self):
        robust_getdir(self, "Path to study directory", self.config["DefaultRootDir"],
                      requirements=None, lineedit=self.le_study_dir)

    def set_fslpath(self):
        robust_getdir(self, "Path to FSL 'bin' Directory", self.config["DefaultRootDir"],
                      {"child_dir_exists": ["fsl", self.parms_errs["InvalidFSLDirectory"]]}, lineedit=self.le_fslpath)

    #######################################################################
    # Main Functions for this module - saving to json and loading from json
    #######################################################################
    def saveparms2json(self):
        # Defensive programming first
        forbidden = ["", ".", "/", "~"]
        # First check, the study directory specified must be a legitimate directory filepath
        study_dir = Path(self.le_study_dir.text()).resolve()
        if any([self.le_study_dir.text() in forbidden, not study_dir.exists(), not study_dir.is_dir()]):
            robust_qmsg(self, title=self.parms_errs["InvalidStudyDirectory"][0],
                        body=self.parms_errs["InvalidStudyDirectory"][1], variables=[f"{str(study_dir)}"])
            return
        # Next, the regex field has to be something reasonable
        if self.le_subregex.text() in ["", "^$", "^", "$", "/", "\\"]:
            robust_qmsg(self, title=self.parms_errs["InvalidRegex"][0], body=self.parms_errs["InvalidRegex"][1],
                        variables=[f"{self.le_subregex.text()}"])
            return
        json_parms = {}
        # Finally, the nature of the current ExploreASL types must be valid
        if self.current_easl_type == "Local ExploreASL Directory":
            easl_dir = Path(self.le_easl_dir.text()).resolve()
            pathforchecking = easl_dir
            if any([self.le_easl_dir.text() in forbidden, not easl_dir.is_dir(), not easl_dir.exists()]):
                robust_qmsg(self, title=self.parms_errs["InvalidExploreASLDir"][0],
                            body=self.parms_errs["InvalidExploreASLDir"][1])
                return
            json_parms["MyPath"] = self.le_easl_dir.text()
            json_parms["EXPLOREASL_TYPE"] = "LOCAL_UNCOMPILED"
        elif self.current_easl_type == "Local ExploreASL Compiled":
            path_path = ""
            for str_path, err_str in zip([self.le_mrc_dir.text(), self.le_easl_mcr.text()],
                                         ["InvalidMCRDir", "InvalidCompiledExploreASLDir"]):
                path_path = Path(str_path).resolve()
                if any([str_path in forbidden, not path_path.is_dir(), not path_path.exists()]):
                    robust_qmsg(self, title=self.parms_errs[err_str][0],
                                body=self.parms_errs[err_str][1])
                    return
            pathforchecking = path_path

            json_parms["MyPath"] = self.le_easl_mcr.text()
            json_parms["MCRPath"] = self.le_mrc_dir.text()
            json_parms["EXPLOREASL_TYPE"] = "LOCAL_COMPILED"
        else:
            raise ValueError(f"Unexpected value for current_easl_type: {self.current_easl_type}")

        # Compatibility
        str_bsup = "BackgroundSuppressionNumberPulses" if not is_earlier_version(pathforchecking, 140, False) \
            else "BackGrSupprPulses"
        if is_earlier_version(pathforchecking, threshold_higher=150, higher_eq=False):
            str_pvcker = "PVCorrectionNativeSpaceKernel"
            str_dopvc = "bPVCorrectionNativeSpace"
            str_pvcgaus = "bPVCorrectionGaussianMM"
        else:
            str_pvcker = "PVCNativeSpaceKernel"
            str_dopvc = "bPVCNativeSpace"
            str_pvcgaus = "bPVCGaussianMM"

        json_parms.update({
            "name": self.le_studyname.text(),
            "D": {"ROOT": self.le_study_dir.text()},
            "subject_regexp": self.le_subregex.text(),
            "exclusion": [self.lst_excluded_subjects.item(row).text() for row in
                          range(self.lst_excluded_subjects.count())],
            "M0_conventionalProcessing":
                {"New Image Processing": 0, "Standard Processing": 1}[self.cmb_m0_algorithm.currentText()],
            "M0": {"Proton density scan (M0) was acquired": "separate_scan",
                   "Use mean control ASL as M0 mimic": "UseControlAsM0",
                   "Use a single value as the M0": self.spinbox_m0_isseparate.value()}
            [self.cmb_m0_isseparate.currentText()],
            "M0_GMScaleFactor": float(self.spinbox_gmscale.value()),
            "M0PositionInASL4D": {"M0 is the first ASL control-label pair": "[1 2]",
                                  "M0 is the first ASL scan volume": 1,
                                  "M0 is the second ASL scan volume": 2,
                                  "M0 exists as a separate scan": None,
                                  }[self.cmb_m0_posinasl.currentText()],

            # Sequence Parameters
            "readout_dim": self.cmb_readout_dim.currentText(),
            "Vendor": self.cmb_vendor.currentText(),
            "Sequence": {"3D Spiral": "3D_spiral", "3D GRaSE": "3D_GRASE", "2D EPI": "2D_EPI"}
            [self.cmb_sequencetype.currentText()],

            # General Processing Parameters
            "Quality": {"High": 1, "Low": 0}[self.cmb_quality.currentText()],
            "DELETETEMP": int(self.chk_deltempfiles.isChecked()),
            "SkipIfNoFlair": int(self.chk_skipnoflair.isChecked()),
            "SkipIfNoM0": int(self.chk_skipnom0.isChecked()),
            "SkipIfNoASL": int(self.chk_skipnoasl.isChecked()),

            # Structural Processing Parameters
            "SegmentSPM12": {"SPM12": 1, "CAT12": 0}[self.cmb_segmethod.currentText()],
            "bRunModule_LongReg": int(self.chk_runlongreg.isChecked()),
            "bRunModule_DARTEL": int(self.chk_run_dartel.isChecked()),
            "bHammersCAT12": int(self.chk_hammersroi.isChecked()),
            "bFixResolution": int(self.chk_fixcat12res.isChecked()),

            # ASL Processing Parameters
            "SPIKE_REMOVAL": int(self.chk_removespikes.isChecked()),
            "SpikeRemovalThreshold": float(self.spinbox_spikethres.value()),
            "motion_correction": int(self.chk_motioncorrect.isChecked()),

            "bRegistrationContrast": {"Automatic": 2, "Control --> T1w": 0, "CBF --> pseudoCBF": 1,
                                      "Force CBF --> pseudoCBF": 3}[self.cmb_imgcontrast.currentText()],
            "bAffineRegistration": {"Based on PWI CoV": 2, "Enabled": 1, "Disabled": 0}
            [self.cmb_affineregbase.currentText()],
            "bDCTRegistration": {"Disabled": 0, "Enabled + no PVC": 1, "Enabled + PVC": 2}
            [self.cmb_dctreg.currentText()],
            "bRegisterM02ASL": int(self.chk_removespikes.isChecked()),
            "bUseMNIasDummyStructural": int(self.chk_usemniasdummy.isChecked()),
            str_dopvc: int(self.chk_nativepvc.isChecked()),
            str_pvcgaus: int(self.chk_gaussianpvc.isChecked()),
            str_pvcker: self.prep_pvc_kernel_vec(),

            # Environment Parameters
            "FSLdirectory": self.le_fslpath.text(),
            "MakeNIfTI4DICOM": int(self.chk_outputcbfmaps.isChecked()),

            # Quantification Parameters
            "ApplyQuantification": self.prep_quantparms(),
            "Q": {
                str_bsup: int(self.cmb_nsup_pulses.currentText()),
                "BackgroundSuppressionPulseTime": self.prep_suppression_vec(),
                "LabelingType": {"Pulsed ASL": "PASL",
                                 "Pseudo-continuous ASL": "CASL",
                                 "Continuous ASL": "CASL"
                                 }[self.cmb_labelingtype.currentText()],
                "Initial_PLD": float(self.spinbox_initialpld.value()),
                "LabelingDuration": float(self.spinbox_labdur.value()),
                "SliceReadoutTime": float(self.spinbox_slice_readout.value()),
                "Lambda": float(self.spinbox_lambda.value()),
                "T2art": float(self.spinbox_artt2.value()),
                "TissueT1": float(self.spinbox_tissuet1.value()),
                "nCompartments": int(self.cmb_ncomparts.currentText())
            },
            # Masking Parameters
            "S": {
                "bMasking": self.prep_masking_vec()
            }
        })

        # Compatibility issue with "M0PositionInASL4D"
        if json_parms["EXPLOREASL_TYPE"] == "LOCAL_UNCOMPILED":
            if all([is_earlier_version(easl_dir=Path(self.le_easl_dir.text()), threshold_higher=150),
                    json_parms.get("M0PositionInASL4D") is None]):
                del json_parms["M0PositionInASL4D"]

        try:
            with open(study_dir / "DataPar.json", 'w') as w:
                json.dump(json_parms, w, indent=3)

            # Also, if this is BIDS, write to the root level asl.json
            if (study_dir / "asl.json").exists():
                asl_parms = {
                    "LabelingType": json_parms["Q"]["LabelingType"],
                    "PostLabelingDelay": json_parms["Q"]["Initial_PLD"],
                    "BackgroundSuppression": json_parms["Q"]["BackGrSupprPulses"] == 0}
                with open(study_dir / "asl.json", 'w') as asl_json_writer:
                    json.dump(asl_parms, asl_json_writer, indent=3)
        except FileNotFoundError:
            robust_qmsg(self, title=self.parms_errs["FileNotFound"][0], body=self.parms_errs["FileNotFound"][1],
                        variables=f"{self.le_study_dir.text()}")
            return

        # Also, overwrite asl_json sidecars if the dataset has been imported as BIDS format
        if self.chk_overwrite_for_bids.isChecked():
            self.overwrite_bids_fields()

        robust_qmsg(self, msg_type="information", title="DataPar.json successfully saved",
                    body=f"The parameter file was successfully saved to:\n{self.le_study_dir.text()}")

    def loadjson2parms(self):
        self.import_error_logger.clear()

        # Defensive Programming
        # The loaded JSON must be a valid json file with the correct syntax
        status, json_filepath = robust_getfile("Select the JSON parameters file", self.config["DefaultRootDir"],
                                               "Json files (*.json)", permitted_suffixes=[".json"])
        if not status:
            return
        try:
            with open(json_filepath, 'r') as reader:
                parms: dict = json.load(reader)
        except json.decoder.JSONDecodeError as datapar_json_e:
            robust_qmsg(self, title=self.parms_errs["BadParFile"][0],
                        body=self.parms_errs["BadParFile"][1] + f"{datapar_json_e}")
            return

        # Compatibility with name changes over ExploreASL Versions; this will be deprecated after a few version
        # advancements
        try:
            bsup_str = "BackgroundSuppressionNumberPulses" if not is_earlier_version(parms["D"]["ROOT"], 140, False) \
                else "BackGrSupprPulses"
            if is_earlier_version(parms["MyPath"], threshold_higher=150, higher_eq=False):
                str_pvcker = "PVCorrectionNativeSpaceKernel"
                str_dopvc = "bPVCorrectionNativeSpace"
                str_pvcgaus = "bPVCorrectionGaussianMM"
            else:
                str_pvcker = "PVCNativeSpaceKernel"
                str_dopvc = "bPVCNativeSpace"
                str_pvcgaus = "bPVCGaussianMM"
        except KeyError:
            bsup_str = "BackgroundSuppressionNumberPulses"
            str_pvcker = "PVCNativeSpaceKernel"
            str_dopvc = "bPVCNativeSpace"
            str_pvcgaus = "bPVCGaussianMM"

        # Preliminary Functions to run
        self.get_easl_paths(loaded_parms=parms)  # Ensure the correct easl setup is in play first!

        # Main Setting
        json_setter = {
            "name": self.le_studyname.setText,
            "D": {"ROOT": self.le_study_dir.setText},
            "subject_regexp": self.le_subregex.setText,
            "exclusion": self.lst_excluded_subjects.addItems,
            "M0_conventionalProcessing": partial(self.main_setter, action="cmb_setCurrentIndex_translate",
                                                 widget=self.cmb_m0_algorithm,
                                                 args={0: "New Image Processing", 1: "Standard Processing"}),
            "M0": self.get_m0,
            "M0_GMScaleFactor": self.spinbox_gmscale.setValue,
            "M0PositionInASL4D": partial(self.main_setter, action="cmb_setCurrentIndex_translate",
                                         widget=self.cmb_m0_posinasl,
                                         args={"[1 2]": "M0 is the first ASL control-label pair",
                                               1: "M0 is the first ASL scan volume",
                                               2: "M0 is the second ASL scan volume",
                                               None: "M0 exists as a separate scan"
                                               }),

            # Sequence Parameters
            "readout_dim": partial(self.main_setter, action="cmb_setCurrentIndex_simple", widget=self.cmb_readout_dim),
            "Vendor": partial(self.main_setter, action="cmb_setCurrentIndex_simple", widget=self.cmb_vendor),
            "Sequence": partial(self.main_setter, action="cmb_setCurrentIndex_translate", widget=self.cmb_sequencetype,
                                args={"3D_spiral": "3D Spiral", "3D_GRASE": "3D GRaSE", "2D_EPI": "2D EPI"}),

            # General Processing Parameters
            "Quality": partial(self.main_setter, action="cmb_setCurrentIndex_translate", widget=self.cmb_quality,
                               args={0: "Low", 1: "High"}),
            "DELETETEMP": self.chk_deltempfiles.setChecked,
            "SkipIfNoFlair": self.chk_skipnoflair.setChecked,
            "SkipIfNoM0": self.chk_skipnom0.setChecked,
            "SkipIfNoASL": self.chk_skipnoasl.setChecked,

            # Structural Processing Parameters
            "SegmentSPM12": partial(self.main_setter, action="cmb_setCurrentIndex_translate", widget=self.cmb_segmethod,
                                    args={1: "SPM12", 0: "CAT12"}),
            "bRunModule_LongReg": self.chk_runlongreg.setChecked,
            "bRunModule_DARTEL": self.chk_run_dartel.setChecked,
            "bHammersCAT12": self.chk_hammersroi.setChecked,
            "bFixResolution": self.chk_fixcat12res.setChecked,

            # ASL Processing Parameters
            "SPIKE_REMOVAL": self.chk_removespikes.setChecked,
            "SpikeRemovalThreshold": self.spinbox_spikethres.setValue,
            "motion_correction": self.chk_motioncorrect.setChecked,

            "bRegistrationContrast": partial(self.main_setter, action="cmb_setCurrentIndex_translate",
                                             widget=self.cmb_imgcontrast,
                                             args={2: "Automatic", 0: "Control --> T1w", 1: "CBF --> pseudoCBF",
                                                   3: "Force CBF --> pseudoCBF"}),
            "bAffineRegistration": partial(self.main_setter, action="cmb_setCurrentIndex_translate",
                                           widget=self.cmb_affineregbase,
                                           args={0: "Disabled", 1: "Enabled", 2: "Based on PWI CoV"}),
            "bDCTRegistration": partial(self.main_setter, action="cmb_setCurrentIndex_translate",
                                        widget=self.cmb_dctreg,
                                        args={0: "Disabled", 1: "Enabled + no PVC", 2: "Enabled + PVC"}),
            "bRegisterM02ASL": self.chk_regm0toasl.setChecked,
            "bUseMNIasDummyStructural": self.chk_usemniasdummy.setChecked,
            str_dopvc: self.chk_nativepvc.setChecked,
            str_pvcgaus: self.chk_gaussianpvc.setChecked,
            str_pvcker: self.get_pvc_kernel_vec,

            # Environment Parameters
            "MakeNIfTI4DICOM": self.chk_outputcbfmaps.setChecked,
            "FSLdirectory": self.le_fslpath.setText,

            # Quantification Parameters
            "ApplyQuantification": self.get_quantparms,
            "Q": {
                bsup_str: partial(self.main_setter, action="cmb_setCurrentIndex_simple",
                                  widget=self.cmb_nsup_pulses),
                "BackgroundSuppressionPulseTime": self.get_suppression_vec,
                "LabelingType": partial(self.main_setter, action="cmb_setCurrentIndex_translate",
                                        widget=self.cmb_labelingtype,
                                        args={"PASL": "Pulsed ASL", "CASL": "Pseudo-continuous ASL",
                                              "PCASL": "Pseudo-continuous ASL"}),
                "Initial_PLD": self.spinbox_initialpld.setValue,
                "LabelingDuration": self.spinbox_labdur.setValue,
                "SliceReadoutTime": self.spinbox_slice_readout.setValue,
                "Lambda": self.spinbox_lambda.setValue,
                "T2art": self.spinbox_artt2.setValue,
                "TissueT1": self.spinbox_tissuet1.setValue,
                "nCompartments": partial(self.main_setter, action="cmb_setCurrentIndex_simple",
                                         widget=self.cmb_ncomparts)
            },
            # Masking Parameters
            "S": {
                "bMasking": self.get_masking_vec
            }
        }

        to_bool = {
            # General Proc Parms
            "DELETETEMP", "SPIKE_REMOVAL", "SkipIfNoFlair", "SkipIfNoM0", "SkipIfNoASL", "PWI_DARTEL", "BILAT_FILTER",
            # Structural Proc Parms
            "T1_DARTEL", "bRunModule_LongReg", "bRunModule_DARTEL", "bHammersCAT12", "bFixResolution",
            # ASL Proc Parms
            "motion_correction", "bRegisterM02ASL", "bUseMNIasDummyStructural", "bPVCorrectionNativeSpace",
            "bPVCorrectionGaussianMM",
            # Quantification Parms
            "SaveCBF4D"
        }
        to_ignore = {"MyPath", "EXPLOREASL_TYPE", "MCRPath"}

        for key, call in parms.items():
            if key in to_ignore:
                continue
            try:
                if isinstance(call, dict):
                    for subkey, subcall in call.items():
                        try:
                            json_setter[key][subkey](subcall)
                        except TypeError as te:
                            print(f"TypeError encountered with key {key} and subkey {subkey}")
                            print(te)
                        except KeyError as ke:
                            print(f"TypeError encountered with key {key} and subkey {subkey}")
                            print(ke)
                else:
                    if key in to_bool:
                        json_setter[key](bool(call))
                    else:
                        try:
                            json_setter[key](call)
                        except KeyError as ke:
                            print(f"KeyError encountered with key {key}")
                            print(ke)

            except TypeError as te:
                print(f"TypeError encountered with key: {key}")
                print(f"Content of TypeError: {te}")

        # Followup functions to perform
        self.fill_subject_list(loaded_parms=parms)  # Fill the list and exclusion widgets

        if len(self.import_error_logger) > 0:
            errors = "\n -".join(self.import_error_logger)
            robust_qmsg(self, title=self.parms_errs["ImportErrors"][0], body=self.parms_errs[1] + errors)

    @staticmethod
    def main_setter(value, widget, action, args=None):
        """
        Convenience setter function for setting widgets to the approprivate values during json loading

        :param value: The input coming from the json value being read in
        :param widget: The widget that will be influenced
        :param action: A string denoting what kind of argument this is so as to facilitate an appropriate response
        :param args: For comboboxes, a mapping of the json key to a string item within the combobox
        """
        if action == "le_setText_commajoin":  # Lineedit; arguments is a list
            if isinstance(value, list) and len(value) > 1:
                widget.setText(", ".join(value))
            else:
                widget.setText(value[0])
        elif action == "le_setText_simple":  # Lineedit; arguments is a string
            widget.setText(value)
        elif action == "cmb_setCurrentIndex_translate":  # Combobox; arguments is a string requiring a translator
            index = widget.findText(str(args[value]))
            if index == -1:
                return False
            widget.setCurrentIndex(index)
        elif action == "cmb_setCurrentIndex_simple":  # Combobox; arguments is a string present as combobox option
            index = widget.findText(str(value))
            if index == -1:
                return False
            widget.setCurrentIndex(index)
        elif action == "chk_setChecked_simple":  # QCheckBox; arguments is a bool
            widget.setChecked(value)

    #############################################
    # Convenience methods for translation to json
    #############################################
    def prep_mypath(self):
        if self.current_easl_type == "Local ExploreASL Directory":
            return self.le_easl_dir.text()
        elif self.current_easl_type == "Local ExploreASL Compiled":
            return self.le_easl_mcr.text()

    def prep_quantparms(self):
        quant_wids = [self.chk_quant_applyss_asl, self.chk_quant_applyss_m0, self.chk_quant_pwi2label,
                      self.chk_quant_quantifym0, self.chk_quant_divbym0]
        return [int(widget.isChecked()) for widget in quant_wids]

    # noinspection PyTypeChecker
    def prep_suppression_vec(self):
        str_timings = self.le_sup_pulse_vec.text()
        if str_timings == "":
            return []
        num_timings: List[str] = str_timings.split(",")
        idx: int
        for idx, timing in enumerate(num_timings.copy()):
            timing = timing.strip()
            isdigit_flag = self.isDigit(timing)
            if not isdigit_flag:
                return []
            num_timings[idx] = float(timing)
        return num_timings

    def prep_pvc_kernel_vec(self):
        return [self.spinbox_pvckernel_1.value(), self.spinbox_pvckernel_2.value(), self.spinbox_pvckernel_3.value()]

    def prep_masking_vec(self):
        return [int(self.chk_suscepmask.isChecked()), int(self.chk_subjectvasmask.isChecked()),
                int(self.chk_subjecttismask.isChecked()), int(self.chk_wholebrainmask.isChecked())]

    @staticmethod
    def isDigit(val: str):
        try:
            float(val)
            return True
        except ValueError:
            return False

    ###############################################
    # Convenience methods for translation from json
    ###############################################
    def get_m0(self, m0_val: Union[str, int, float]):
        if isinstance(m0_val, str):
            translator = {"separate_scan": "Proton density scan (M0) was acquired",
                          "UseControlAsM0": "Use mean control ASL as M0 mimic"}
            idx = self.cmb_m0_isseparate.findText(translator[m0_val])
            self.cmb_m0_isseparate.setCurrentIndex(idx)

        elif isinstance(m0_val, (int, float)):
            idx = self.cmb_m0_isseparate.findText("Use a single value as the M0")
            self.cmb_m0_isseparate.setCurrentIndex(idx)
            self.spinbox_m0_isseparate.setValue(m0_val)
        else:
            return

    def get_quantparms(self, quant_vector: list):
        if any([len(quant_vector) != 5,
                not all([str(val).isdigit() for val in quant_vector]),
                not all([int(val) in [0, 1] for val in quant_vector])
                ]):
            self.import_error_logger.append("Quantification Settings")
            return
        quant_wids = [self.chk_quant_applyss_asl, self.chk_quant_applyss_m0, self.chk_quant_pwi2label,
                      self.chk_quant_quantifym0, self.chk_quant_divbym0]
        for wiget, val in zip(quant_wids, quant_vector):
            wiget.setChecked(bool(val))

    def get_suppression_vec(self, suppr_vec: List[float]):
        if len(suppr_vec) == 0:
            self.le_sup_pulse_vec.setText("")
        if any([not all([self.isDigit(str(x)) for x in suppr_vec])]):
            self.import_error_logger.append("Suppression Timings Vector")
            self.le_sup_pulse_vec.setText("")
            return
        str_suppr_vec = ", ".join([str(suppr_val) for suppr_val in suppr_vec])
        self.le_sup_pulse_vec.setText(str_suppr_vec)

    def get_pvc_kernel_vec(self, pvc_vec):
        try:
            if any([len(pvc_vec) != 3,
                    not all([str(x).isdigit() for x in pvc_vec])
                    ]):
                self.import_error_logger.append("PVC Kernel Dimensions")
                return
        except ValueError:
            self.import_error_logger.append("PVC Kernel Dimensions - Value Error")
            return
        for widget, val in zip([self.spinbox_pvckernel_1, self.spinbox_pvckernel_2, self.spinbox_pvckernel_3], pvc_vec):
            widget.setValue(val)

    def get_masking_vec(self, masking_vec: list):
        try:
            if any([len(masking_vec) != 4,
                    not all([str(x).isdigit() for x in masking_vec])
                    ]):
                self.import_error_logger.append("Masking Vector")
                return
        except ValueError:
            self.import_error_logger.append("Masking Vector - Value Error")
            return
        for widget, val in zip([self.chk_suscepmask, self.chk_subjectvasmask, self.chk_subjecttismask,
                                self.chk_wholebrainmask], masking_vec):
            widget.setChecked(bool(val))

    def fill_subject_list(self, loaded_parms: dict):
        try:
            analysis_dir = Path(loaded_parms["D"]["ROOT"]).resolve()
            if any([not analysis_dir.exists(), not analysis_dir.is_dir(),
                    loaded_parms["D"]["ROOT"] in [".", "", "/"]]):
                return
            if loaded_parms["subject_regexp"] == "":
                return
            regex: re.Pattern = re.compile(loaded_parms["subject_regexp"])
            includedsubs = [path.name for path in analysis_dir.iterdir()
                            if all([path.name not in ["lock", "Population"],  # Filter out default directories
                                    regex.search(path.name),  # Must match the indicated regex
                                    path.name not in loaded_parms["exclusion"],  # Cannot be an excluded subject
                                    path.is_dir()  # Must be a directory
                                    ])]
            print(f"{includedsubs=}")
            if len(includedsubs) > 0:
                self.lst_included_subjects.clear()
                self.lst_included_subjects.addItems(includedsubs)

            excludedsubs = loaded_parms["exclusion"]
            print(f'{excludedsubs=}')
            if len(excludedsubs) > 0:
                self.lst_excluded_subjects.clear()
                self.lst_excluded_subjects.addItems(excludedsubs)

        except KeyError as subload_kerr:
            print(f"{self.fill_subject_list.__name__} received a KeyError: {subload_kerr}")
            return

    def get_easl_paths(self, loaded_parms: dict):
        try:
            easl_type = loaded_parms["EXPLOREASL_TYPE"]
            if easl_type == "LOCAL_UNCOMPILED":
                self.cmb_easl_type.setCurrentIndex(self.cmb_easl_type.findText("Local ExploreASL Directory"))
                self.le_easl_dir.setText(str(loaded_parms["MyPath"]))
            elif easl_type == "LOCAL_COMPILED":
                self.cmb_easl_type.setCurrentIndex(self.cmb_easl_type.findText("Local ExploreASL Compiled"))
                self.le_easl_mcr.setText(str(loaded_parms["MyPath"]))
                self.le_mrc_dir.setText(str(loaded_parms["MCRPath"]))
            else:
                pass

        except KeyError as easlpaths_kerr:
            print(f"{self.get_easl_paths.__name__} received a KeyError: {easlpaths_kerr}")
            return

    ############################################
    # Convenience methods for generating widgets
    ############################################

    @staticmethod
    def make_cmb_and_items(items, default=None):
        cmb = QComboBox()
        cmb.addItems(items)
        if default is not None:
            cmb.setCurrentIndex(default)
        return cmb
