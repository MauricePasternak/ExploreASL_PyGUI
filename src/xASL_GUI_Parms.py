from PySide2.QtWidgets import *
from PySide2.QtGui import *
from PySide2.QtCore import QSize
from src.xASL_GUI_HelperClasses import DandD_FileExplorer2LineEdit, DandD_FileExplorer2ListWidget
import json
from pathlib import Path
from tdda import rexpy
from more_itertools import peekable
from functools import partial
from shutil import which


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
        self.setWindowTitle("Explore ASL - Parameter File Maker")

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
        self.tab_main.addTab(self.cont_basic, "Basic Settings")
        self.tab_main.addTab(self.cont_advanced, "Advanced Settings")
        self.mainlay.addWidget(self.btn_make_parms)
        self.mainlay.addWidget(self.btn_load_parms)

        # Misc Players
        self.import_error_logger = []
        self.asl_json_sidecar_data = {}
        self.can_update_slicereadouttime = False

        self.UI_Setup_Basic()
        self.UI_Setup_Advanced()

        # After all UI is set up, make certain connections
        self.le_study_dir.textChanged.connect(self.update_asl_json_sidecar_data)
        self.resize(self.minimumSizeHint())

    def UI_Setup_Basic(self):
        self.formlay_basic = QFormLayout(self.cont_basic)
        self.hlay_easl_dir, self.le_easl_dir, self.btn_easl_dir = self.make_droppable_clearable_le(
            btn_connect_to=self.set_exploreasl_dir,
            default='')
        self.le_easl_dir.setToolTip(self.parms_tips["le_easl_dir"])
        self.le_studyname = QLineEdit(text="My Study")
        self.le_studyname.setToolTip(self.parms_tips["le_studyname"])
        self.chk_overwrite_for_bids = QCheckBox(checked=True)
        self.chk_overwrite_for_bids.setToolTip(self.parms_tips["chk_overwrite_for_bids"])
        self.hlay_study_dir, self.le_study_dir, self.btn_study_dir = self.make_droppable_clearable_le(
            btn_connect_to=self.set_study_dir,
            default='')
        self.le_study_dir.setToolTip(self.parms_tips["le_study_dir"])
        self.le_study_dir.setPlaceholderText("Indicate the analysis directory filepath here")
        self.le_subregex = QLineEdit(text='\\d+')
        self.lst_included_subjects = DandD_FileExplorer2ListWidget()
        self.lst_included_subjects.itemsAdded.connect(self.update_regex)
        self.lst_included_subjects.setToolTip(self.parms_tips["lst_included_subjects"])
        self.lst_included_subjects.setMinimumHeight(self.config["ScreenSize"][1] // 5)
        self.btn_included_subjects = QPushButton("Clear Subjects", clicked=self.clear_included)
        self.lst_excluded_subjects = DandD_FileExplorer2ListWidget()
        self.lst_excluded_subjects.setToolTip(self.parms_tips["lst_excluded_subjects"])
        self.lst_excluded_subjects.setMinimumHeight(self.config["ScreenSize"][1] // 10)
        self.btn_excluded_subjects = QPushButton("Clear Excluded", clicked=self.clear_excluded)
        self.le_run_names = QLineEdit(text="ASL_1",
                                      placeholderText="Indicate run names, each separated by a comma and space")
        self.le_run_names.setToolTip(self.parms_tips["le_run_names"])
        self.le_run_options = QLineEdit(placeholderText="Indicate option names, each separated by a comma and space")
        self.le_run_options.setToolTip(self.parms_tips["le_run_options"])
        self.cmb_vendor = self.make_cmb_and_items(["Siemens", "Philips", "GE", "GE_WIP"])
        self.cmb_vendor.setToolTip(self.parms_tips["cmb_vendor"])
        self.cmb_sequencetype = self.make_cmb_and_items(["3D GRaSE", "2D EPI", "3D Spiral"])
        self.cmb_sequencetype.setToolTip(self.parms_tips["cmb_sequencetype"])
        self.cmb_sequencetype.currentTextChanged.connect(self.update_readout_dim)
        self.cmb_labelingtype = self.make_cmb_and_items(["Pulsed ASL", "Pseudo-continuous ASL", "Continuous ASL"])
        self.cmb_labelingtype.setToolTip(self.parms_tips["cmb_labelingtype"])
        self.cmb_labelingtype.currentTextChanged.connect(self.autocalc_slicereadouttime)
        self.cmb_m0_isseparate = self.make_cmb_and_items(["Proton density scan (M0) was acquired",
                                                          "Use mean control ASL as proton density mimic"])
        self.cmb_m0_isseparate.setToolTip(self.parms_tips["cmb_m0_isseparate"])
        self.cmb_m0_posinasl = self.make_cmb_and_items(
            ["M0 exists as a separate scan", "M0 is the first ASL control-label pair",
             "M0 is the first ASL scan volume", "M0 is the second ASL scan volume"])
        self.cmb_m0_posinasl.setToolTip(self.parms_tips["cmb_m0_posinasl"])
        self.cmb_quality = self.make_cmb_and_items(["Low", "High"])
        self.cmb_quality.setCurrentIndex(1)
        self.cmb_quality.setToolTip(self.parms_tips["cmb_quality"])

        for desc, widget in zip(["ExploreASL Directory", "Name of Study", "Analysis Directory",
                                 "Dataset is in BIDS format?",
                                 "Subjects to Assess\n(Drag and Drop Directories)",
                                 "Subjects to Exclude\n(Drag and Drop Directories)",
                                 "Run Names", "Run Options", "Vendor", "Sequence Type", "Labelling Type",
                                 "M0 was acquired?", "M0 Position in ASL", "Quality"],
                                [self.hlay_easl_dir, self.le_studyname, self.hlay_study_dir,
                                 self.chk_overwrite_for_bids,
                                 self.lst_included_subjects, self.lst_excluded_subjects,
                                 self.le_run_names, self.le_run_options, self.cmb_vendor, self.cmb_sequencetype,
                                 self.cmb_labelingtype, self.cmb_m0_isseparate, self.cmb_m0_posinasl,
                                 self.cmb_quality]):
            self.formlay_basic.addRow(desc, widget)
        self.formlay_basic.insertRow(5, "", self.btn_included_subjects)
        self.formlay_basic.insertRow(7, "", self.btn_excluded_subjects)

    def UI_Setup_Advanced(self):
        # First, set up the groupboxes and add them to the advanced tab layout
        self.vlay_advanced = QVBoxLayout(self.cont_advanced)
        self.grp_seqparms = QGroupBox(title="Sequence Parameters")
        self.grp_quantparms = QGroupBox(title="Quantification Parameters")
        self.grp_m0parms = QGroupBox(title="M0 Parameters")
        self.grp_procparms = QGroupBox(title="Processing Parameters")
        self.grp_envparms = QGroupBox(title="Environment Parameters")
        for grp in [self.grp_seqparms, self.grp_quantparms, self.grp_m0parms, self.grp_procparms, self.grp_envparms]:
            self.vlay_advanced.addWidget(grp)

        # Set up the Sequence Parameters
        self.vlay_seqparms, self.scroll_seqparms, self.cont_seqparms = self.make_scrollbar_area(self.grp_seqparms)
        self.formlay_seqparms = QFormLayout(self.cont_seqparms)
        self.cmb_nsup_pulses = self.make_cmb_and_items(["0", "2", "4", "5"], 1)
        self.cmb_nsup_pulses.setToolTip(self.parms_tips["cmb_nsup_pulses"])
        self.cmb_readout_dim = self.make_cmb_and_items(["3D", "2D"])
        self.cmb_readout_dim.setToolTip(self.parms_tips["cmb_readout_dim"])
        self.spinbox_initialpld = QDoubleSpinBox(maximum=2500, minimum=0, value=1800)
        self.spinbox_initialpld.valueChanged.connect(self.autocalc_slicereadouttime)
        self.spinbox_initialpld.setToolTip(self.parms_tips["spinbox_initialpld"])
        self.spinbox_labdur = QDoubleSpinBox(maximum=2000, minimum=0, value=800)
        self.spinbox_labdur.valueChanged.connect(self.autocalc_slicereadouttime)
        self.spinbox_labdur.setToolTip(self.parms_tips["spinbox_labdur"])
        self.hlay_slice_readout = QHBoxLayout()
        self.cmb_slice_readout = self.make_cmb_and_items(["Use Indicated Value", "Use Shortest TR"])
        self.spinbox_slice_readout = QDoubleSpinBox(maximum=1000, minimum=0, value=37)
        self.spinbox_slice_readout.setToolTip(self.parms_tips["spinbox_slice_readout"])
        self.hlay_slice_readout.addWidget(self.cmb_slice_readout)
        self.hlay_slice_readout.addWidget(self.spinbox_slice_readout)
        for description, widget in zip(["Number of Suppression Pulses", "Readout Dimension",
                                        "Initial Post-Labeling Delay (ms)", "Labeling Duration (ms)",
                                        "Slice Readout Time (ms)"],
                                       [self.cmb_nsup_pulses, self.cmb_readout_dim, self.spinbox_initialpld,
                                        self.spinbox_labdur, self.hlay_slice_readout]):
            self.formlay_seqparms.addRow(description, widget)

        # Set up the Quantification Parameters
        (self.vlay_quantparms, self.scroll_quantparms,
         self.cont_quantparms) = self.make_scrollbar_area(self.grp_quantparms)
        self.formlay_quantparms = QFormLayout(self.cont_quantparms)
        self.spinbox_lambda = QDoubleSpinBox(maximum=1, minimum=0, value=0.9, singleStep=0.01)
        self.spinbox_lambda.setToolTip(self.parms_tips["spinbox_lambda"])
        self.spinbox_artt2 = QDoubleSpinBox(maximum=100, minimum=0, value=50, singleStep=0.1)
        self.spinbox_artt2.setToolTip(self.parms_tips["spinbox_artt2"])
        self.spinbox_bloodt1 = QDoubleSpinBox(maximum=2000, minimum=0, value=1650, singleStep=0.1)
        self.spinbox_bloodt1.setToolTip(self.parms_tips["spinbox_bloodt1"])
        self.spinbox_tissuet1 = QDoubleSpinBox(maximum=2000, minimum=0, value=1240, singleStep=0.1)
        self.spinbox_tissuet1.setToolTip(self.parms_tips["spinbox_tissuet1"])
        self.cmb_ncomparts = self.make_cmb_and_items(["1", "2"], 0)
        self.cmb_ncomparts.setToolTip(self.parms_tips["cmb_ncomparts"])
        self.le_quantset = QLineEdit(text="1 1 1 1 1")
        self.le_quantset.setToolTip(self.parms_tips["le_quantset"])
        for description, widget in zip(["Lambda", "Arterial T2*", "Blood T1",
                                        "Tissue T1", "Number of Compartments", "Quantification Settings"],
                                       [self.spinbox_lambda, self.spinbox_artt2, self.spinbox_bloodt1,
                                        self.spinbox_tissuet1, self.cmb_ncomparts, self.le_quantset]):
            self.formlay_quantparms.addRow(description, widget)

        # Set up the remaining M0 Parameters
        self.vlay_m0parms, self.scroll_m0parms, self.cont_m0parms = self.make_scrollbar_area(self.grp_m0parms)
        self.scroll_m0parms.setMinimumHeight(self.config["ScreenSize"][1] // 16)
        self.formlay_m0parms = QFormLayout(self.cont_m0parms)
        self.cmb_m0_algorithm = self.make_cmb_and_items(["New Image Processing", "Standard Processing"], 0)
        self.cmb_m0_algorithm.setToolTip(self.parms_tips["cmb_m0_algorithm"])
        self.spinbox_gmscale = QDoubleSpinBox(maximum=100, minimum=0.01, value=1, singleStep=0.01)
        self.spinbox_gmscale.setToolTip(self.parms_tips["spinbox_gmscale"])
        for description, widget in zip(["M0 Processing Algorithm", "GM Scale Factor"],
                                       [self.cmb_m0_algorithm, self.spinbox_gmscale]):
            self.formlay_m0parms.addRow(description, widget)

        # Set up the Processing Parameters
        self.vlay_procparms, self.scroll_procparms, self.cont_procparms = self.make_scrollbar_area(self.grp_procparms)
        self.formlay_procparms = QFormLayout(self.cont_procparms)
        self.chk_removespikes = QCheckBox(checked=True)
        self.spinbox_spikethres = QDoubleSpinBox(maximum=1, minimum=0, value=0.01, singleStep=0.01)
        self.chk_motioncorrect = QCheckBox(checked=True)
        self.chk_deltempfiles = QCheckBox(checked=True)
        self.chk_skipnoflair = QCheckBox(checked=False)
        self.chk_skipnoasl = QCheckBox(checked=True)
        self.chk_skipnom0 = QCheckBox(checked=False)
        self.chk_uset1dartel = QCheckBox(checked=True)
        self.chk_usepwidartel = QCheckBox(checked=False)
        self.chk_usebilatfilter = QCheckBox(checked=False)
        self.cmb_segmethod = self.make_cmb_and_items(["CAT12", "SPM12"], 0)
        self.cmb_imgcontrast = self.make_cmb_and_items(["Automatic", "Control --> T1w", "CBF --> pseudoCBF",
                                                        "Force CBF --> pseudoCBF"], 0)
        self.cmb_affineregbase = self.make_cmb_and_items(["Based on PWI CoV", "Enabled", "Disabled"])
        self.cmb_dctreg = self.make_cmb_and_items(["Disabled", "Enabled + no PVC", "Enabled + PVC"])
        self.chk_regm0toasl = QCheckBox(checked=True)
        self.chk_usemniasdummy = QCheckBox(checked=False)
        for description, widget in zip(["Remove Spikes", "Spike Removal Threshold", "Correct for Motion",
                                        "Delete Temporary Files", "Skip Subjects without FLAIR",
                                        "Skip Subjects without ASL", "Skip subjects without M0", "Use T1 DARTEL",
                                        "Use PWI DARTEL", "Use Bilateral Filter", "Segmentation Method",
                                        "Image Contrast used for", "Use Affine Registration", "Use DCT Registration",
                                        "Register M0 to ASL",
                                        "Use MNI as Dummy Template"],
                                       [self.chk_removespikes, self.spinbox_spikethres, self.chk_motioncorrect,
                                        self.chk_deltempfiles, self.chk_skipnoflair, self.chk_skipnoasl,
                                        self.chk_skipnom0, self.chk_uset1dartel, self.chk_usepwidartel,
                                        self.chk_usebilatfilter, self.cmb_segmethod, self.cmb_imgcontrast,
                                        self.cmb_affineregbase, self.cmb_dctreg, self.chk_regm0toasl,
                                        self.chk_usemniasdummy]):
            self.formlay_procparms.addRow(description, widget)

        # Set up the Environment Parameters
        self.vlay_envparms, self.scroll_envparms, self.cont_envparms = self.make_scrollbar_area(self.grp_envparms)
        self.scroll_envparms.setMinimumHeight(self.config["ScreenSize"][1] // 17.5)
        self.formlay_envparms = QFormLayout(self.cont_envparms)
        (self.hlay_fslpath, self.le_fslpath,
         self.btn_fslpath) = self.make_droppable_clearable_le(btn_connect_to=self.set_fslpath)
        self.le_fslpath.setToolTip(self.parms_tips["le_fslpath"])
        fsl_filepath = which("fsl")
        if fsl_filepath is not None:
            self.le_fslpath.setText(str(Path(fsl_filepath)))
        self.chk_outputcbfmaps = QCheckBox(checked=False)
        for desc, widget in zip(["Path to FSL bin directory", "Output CBF native space maps?"],
                                [self.hlay_fslpath, self.chk_outputcbfmaps]):
            self.formlay_envparms.addRow(desc, widget)

    ################################
    # Json Sidecar Related Functions
    ################################
    def update_asl_json_sidecar_data(self, analysis_dir_text):
        """
        Receives a signal from the le_study_dir lineedit and will accordingly update several fields
        @param analysis_dir_text: the text updated from the analysis directory
        """

        # First set of checks
        if analysis_dir_text == "":
            return

        analysis_dir_text = Path(analysis_dir_text)
        if any([not analysis_dir_text.exists(), not analysis_dir_text.is_dir(), analysis_dir_text.name != "analysis"]):
            return

        if self.config["DeveloperMode"]:
            print(f"Detected an update to the specified analysis directory. Attempting to find asl json sidecars and "
                  f"infer appropriate field values from within.\n")

        # Retrieve any asl json sidecar
        asl_sides_legacy = peekable(analysis_dir_text.rglob("ASL4D.json"))
        asl_sides_bids = peekable(analysis_dir_text.rglob("*_asl.json"))

        # Disengage if there is no luck finding any sidecar
        if not asl_sides_legacy:
            if not asl_sides_bids:
                return
            else:
                asl_sidecar = next(asl_sides_bids)
        else:
            asl_sidecar = next(asl_sides_legacy)
        try:
            with open(asl_sidecar) as sidecar_reader:
                self.asl_json_sidecar_data = json.load(sidecar_reader)
        except json.decoder.JSONDecodeError as json_e:
            QMessageBox.warning(self.parent(), self.parms_errs["JsonImproperFormat"][0],
                                self.parms_errs["JsonImproperFormat"][1] + str(json_e), QMessageBox.Ok)
            return

        # First, check if this is bids
        if (analysis_dir_text / "dataset_description.json").exists():
            self.chk_overwrite_for_bids.setChecked(True)
            print(f"Detected that {analysis_dir_text} is a BIDS directory")
        else:
            self.chk_overwrite_for_bids.setChecked(False)
            print(f"Detected that {analysis_dir_text} is not in BIDS format")

        # Next, the vendor
        try:
            idx = self.cmb_vendor.findText(self.asl_json_sidecar_data["Manufacturer"])
            if idx != -1:
                self.cmb_vendor.setCurrentIndex(idx)
        except KeyError:
            if self.config["DeveloperMode"]:
                print(f"INFO in update_asl_json_sidecar_data. The field: Manufacturer was not present in the "
                      f"detected asl json sidecar.\n")

        # Next, the readout dimension
        try:
            idx = self.cmb_readout_dim.findText(self.asl_json_sidecar_data["MRAcquisitionType"])
            if idx != -1:
                self.cmb_readout_dim.setCurrentIndex(idx)
        except KeyError:
            if self.config["DeveloperMode"]:
                print(f"INFO in update_asl_json_sidecar_data. The field: MRAcquisitionType was not present in the "
                      f"detected asl json sidecar.\n")

        # Next the inversion time (i.e Post-Label Duration)
        try:
            value = self.asl_json_sidecar_data["InversionTime"]
            self.spinbox_initialpld.setValue(value * 1000)
        except KeyError:
            if self.config["DeveloperMode"]:
                print(f"INFO in update_asl_json_sidecar_data. The field: InversionTime was not present in the "
                      f"detected asl json sidecar.\n")

        # Next get a few essentials for auto-calculating the SliceReadoutTime
        try:
            has_tr = "RepetitionTime" in self.asl_json_sidecar_data
            has_nslices = "NumberOfSlices" in self.asl_json_sidecar_data
            if has_tr and has_nslices:
                self.can_update_slicereadouttime = True
            else:
                self.can_update_slicereadouttime = False
        except KeyError:
            pass

        # Retrieve any M0 json sidecar
        m0_sides_legacy = peekable(analysis_dir_text.rglob("M0.json"))
        m0_sides_bids = peekable(analysis_dir_text.rglob("*_m0scan.json"))

        # Disengage if there is no luck finding any m0 sidecar
        if not m0_sides_legacy:
            if not m0_sides_bids:
                self.chk_overwrite_for_bids.setChecked(False)
                return
            else:
                m0_sidecar = next(m0_sides_bids)
                # Activate the checkbox to overwrite sidecar data
                self.chk_overwrite_for_bids.setChecked(True)
        else:
            m0_sidecar = next(m0_sides_legacy)
            # Deactivate the checkbox to overwrite sidecar data
            self.chk_overwrite_for_bids.setChecked(False)

        if m0_sidecar:
            idx = self.cmb_m0_isseparate.findText("Proton density scan (M0) was acquired")
            if idx != -1:
                self.cmb_m0_isseparate.setCurrentIndex(idx)

            # If there was an M0 sidecar, it stands to reason there was also background suppression and that field
            # should be set appropriately
            try:
                manufac = self.asl_json_sidecar_data["Manufacturer"]
                acq_type = self.asl_json_sidecar_data["MRAcquisitionType"]
                if manufac == "GE":
                    idx = self.cmb_nsup_pulses.findText('5')
                elif manufac == "Philips" and acq_type == "2D":
                    idx = self.cmb_nsup_pulses.findText("2")
                elif manufac == "Philips" and acq_type == "3D":
                    idx = self.cmb_nsup_pulses.findText("4")
                elif manufac == "Siemens":
                    idx = self.cmb_nsup_pulses.findText("2")
                else:
                    if self.config["DeveloperMode"]:
                        print(f"Information: In update_asl_json_sidecar_data. An M0 json sidecar was detected, but its "
                              f"Manufacturer field was not present, preventing the appropriate setting for the number "
                              f"of background suppression pulses to be established.\n")
                    return
                self.cmb_nsup_pulses.setCurrentIndex(idx)

                # If it is 2D, it must be 2D EPI
                if acq_type == "2D":
                    idx = self.cmb_sequencetype.findText("2D EPI")
                    self.cmb_sequencetype.setCurrentIndex(idx)

            except KeyError:
                pass

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
            QMessageBox().warning(self.parent(), self.parms_errs["BIDSoverwriteforNonBIDS"][0],
                                  self.parms_errs["BIDSoverwriteforNonBIDS"][1], QMessageBox.Ok)
            return

        asl_jsons = peekable(analysis_dir.rglob("*_asl.json"))
        # If json sidecars cannot be found, exit early
        if not asl_jsons:
            QMessageBox().warning(self.parent(), self.parms_errs["NoJsonSidecars"][0],
                                  self.parms_errs["NoJsonSidecars"][1], QMessageBox.Ok)
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

            elif self.cmb_m0_isseparate.currentText() == "Use mean control ASL as proton density mimic":
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
            QMessageBox().warning(self.parent(), self.parms_errs["ImpossibleM0"][0],
                                  self.parms_errs["ImpossibleM0"][1] + f"{bad_jsons}", QMessageBox.Ok)

    ################
    # Misc Functions
    ################
    # Clears the currently-included subjects list and resets the regex
    def clear_included(self):
        self.lst_included_subjects.clear()
        self.le_subregex.clear()

    # Clears the currently-excluded subjects list
    def clear_excluded(self):
        self.lst_study_parms_exclusions.clear()

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

    def get_directory(self, caption):
        directory = QFileDialog.getExistingDirectory(self.parent(), caption, self.config["DefaultRootDir"],
                                                     QFileDialog.ShowDirsOnly)
        if directory == "":
            return False, ""
        return True, directory

    def set_exploreasl_dir(self):
        status, easl_filepath = self.get_directory("Select ExploreASL directory")
        if not status:
            return
        easl_filepath = Path(easl_filepath)
        if (easl_filepath / "ExploreASL_Master.m").exists():
            self.le_easl_dir.setText(str(easl_filepath))
        else:
            QMessageBox().warning(self, self.parms_errs["InvalidExploreASLDir"][0],
                                  self.parms_errs["InvalidExploreASLDir"][1], QMessageBox.Ok)

    def set_study_dir(self):
        status, analysisdir_filepath = self.get_directory("Select the study's analysis directory")
        if not status:
            return
        analysisdir_filepath = Path(analysisdir_filepath)
        if any([not analysisdir_filepath.exists(), not analysisdir_filepath.is_dir()]):
            QMessageBox().warning(self, self.parms_errs["InvalidDirectory"][0],
                                  self.parms_errs["InvalidDirectory"][1], QMessageBox.Ok)
            return
        else:
            self.le_study_dir.setText(str(analysisdir_filepath))

    def set_fslpath(self):
        status, fsl_filepath = self.get_directory("Select the path to the fsl bin direction")
        if not status:
            return
        fsl_filepath = Path(fsl_filepath)
        if any([not (fsl_filepath / "fsl").exists(), fsl_filepath.name != "bin"]):
            QMessageBox().warning(self, self.parms_errs["InvalidFSLDirectory"][0],
                                  self.parms_errs["InvalidFSLDirectory"][1], QMessageBox.Ok)
            return
        else:
            self.le_fslpath.setText(str(fsl_filepath))

    #######################################################################
    # Main Functions for this module - saving to json and loading from json
    #######################################################################
    def saveparms2json(self):
        # Defensive programming first
        study_dir = Path(self.le_study_dir.text())
        if any([self.le_study_dir.text() == '', not study_dir.exists(), not study_dir.is_dir()]):
            QMessageBox().warning(self.parent(), self.parms_errs["InvalidStudyDirectory"][0],
                                  self.parms_errs["InvalidStudyDirectory"][1], QMessageBox.Ok)
            return

        json_parms = {
            "MyPath": self.le_easl_dir.text(),
            "name": self.le_studyname.text(),
            "D": {"ROOT": self.le_study_dir.text()},
            "subject_regexp": self.le_subregex.text(),
            "SESSIONS": self.prep_run_names(),
            "session": {"options": self.prep_run_options()},
            "exclusion": [self.lst_excluded_subjects.item(row).text() for row in
                          range(self.lst_excluded_subjects.count())],
            "M0_conventionalProcessing":
                {"New Image Processing": 0, "Standard Processing": 1}[self.cmb_m0_algorithm.currentText()],
            "M0": {"Proton density scan (M0) was acquired": "separate_scan",
                   "Use mean control ASL as proton density mimic": "UseControlAsM0"}
            [self.cmb_m0_isseparate.currentText()],
            "M0_GMScaleFactor": float(self.spinbox_gmscale.value()),
            "readout_dim": self.cmb_readout_dim.currentText(),
            "Vendor": self.cmb_vendor.currentText(),
            "Sequence": {"3D Spiral": "3D_spiral", "3D GRaSE": "3D_GRASE", "2D EPI": "2D_EPI"}
            [self.cmb_sequencetype.currentText()],
            "Quality": {"High": 1, "Low": 0}[self.cmb_quality.currentText()],
            "DELETETEMP": int(self.chk_deltempfiles.isChecked()),
            "SPIKE_REMOVAL": int(self.chk_removespikes.isChecked()),
            "SpikeRemovalThreshold": float(self.spinbox_spikethres.value()),
            "SkipIfNoFlair": int(self.chk_skipnoflair.isChecked()),
            "SkipIfNoM0": int(self.chk_skipnom0.isChecked()),
            "SkipIfNoASL": int(self.chk_skipnoasl.isChecked()),
            "T1_DARTEL": int(self.chk_uset1dartel.isChecked()),
            "PWI_DARTEL": int(self.chk_usepwidartel.isChecked()),
            "BILAT_FILTER": int(self.chk_usebilatfilter.isChecked()),
            "motion_correction": int(self.chk_motioncorrect.isChecked()),
            "SegmentSPM12": {"SPM12": 1, "CAT12": 0}[self.cmb_segmethod.currentText()],
            "bRegistrationContrast": {"Automatic": 2, "Control --> T1w": 0, "CBF --> pseudoCBF": 1,
                                      "Force CBF --> pseudoCBF": 3}[self.cmb_imgcontrast.currentText()],
            "bAffineRegistration": {"Based on PWI CoV": 2, "Enabled": 1, "Disabled": 0}
            [self.cmb_affineregbase.currentText()],
            "bDCTRegistration": {"Disabled": 0, "Enabled + no PVC": 1, "Enabled + PVC": 2}
            [self.cmb_dctreg.currentText()],
            "bRegisterM02ASL": int(self.chk_removespikes.isChecked()),
            "bUseMNIasDummyStructural": int(self.chk_usemniasdummy.isChecked()),
            "ApplyQuantification": self.prep_quantparms(),
            "FSLdirectory": self.le_fslpath.text(),
            "MakeNIfTI4DICOM": int(self.chk_outputcbfmaps.isChecked()),
            "Q": {
                "BackGrSupprPulses": int(self.cmb_nsup_pulses.currentText()),
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
            }
        }

        if self.cmb_m0_posinasl.currentText() != "M0 exists as a separate scan":
            parms_m0_pos_translate = {"M0 is the first ASL control-label pair": "[1 2]",
                                      "M0 is the first ASL scan volume": 1,
                                      "M0 is the second ASL scan volume": 2}
            json_parms["M0PositionInASL4D"] = parms_m0_pos_translate[self.cmb_m0_posinasl.currentText()]
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
            QMessageBox().warning(self, self.parms_errs["FileNotFound"][0],
                                  self.parms_errs["FileNotFound"][1] + f"{self.le_study_dir.text()}", QMessageBox.Ok)
            return

        # Also, overwrite asl_json sidecars if the dataset has been imported as BIDS format
        if self.chk_overwrite_for_bids.isChecked():
            self.overwrite_bids_fields()

        QMessageBox().information(self,
                                  "DataPar.json successfully saved",
                                  f"The parameter file was successfully saved to:\n"
                                  f"{self.le_study_dir.text()}",
                                  QMessageBox.Ok)

    def loadjson2parms(self):
        self.import_error_logger.clear()
        json_filepath, _ = QFileDialog.getOpenFileName(QFileDialog(), "Select the JSON parameters file",
                                                       self.config["DefaultRootDir"], "Json files (*.json)")
        if json_filepath == '':
            return
        json_filepath = Path(json_filepath)
        if any([not json_filepath.exists(), not json_filepath.is_file(), json_filepath.suffix != ".json"]):
            QMessageBox().warning(self, self.parms_errs["IncorrectFile"][0],
                                  self.parms_errs["IncorrectFile"][1], QMessageBox.Ok)
            return
        try:
            with open(json_filepath, 'r') as reader:
                parms: dict = json.load(reader)
        except json.decoder.JSONDecodeError as datapar_json_e:
            QMessageBox().warning(self.parent(), self.parms_errs["BadParFile"][0],
                                  self.parms_errs["BadParFile"][1] + f"{datapar_json_e}", QMessageBox.Ok)
            return

        json_setter = {
            "MyPath": self.le_easl_dir.setText,
            "name": self.le_studyname.setText,
            "D": {"ROOT": self.le_study_dir.setText},
            "subject_regexp": self.le_subregex.setText,
            "SESSIONS": partial(self.main_setter, action="le_setText_commajoin", widget=self.le_run_names),
            "session": {
                "options": partial(self.main_setter, action="le_setText_commajoin", widget=self.le_run_options)},
            "exclusion": self.lst_excluded_subjects.addItems,
            "M0_conventionalProcessing": partial(self.main_setter, action="cmb_setCurrentIndex_translate",
                                                 widget=self.cmb_m0_algorithm,
                                                 translator={0: "New Image Processing", 1: "Standard Processing"}),
            "M0": partial(self.main_setter, action="cmb_setCurrentIndex_translate", widget=self.cmb_m0_isseparate,
                          translator={"separate_scan": "Proton density scan (M0) was acquired",
                                      "UseControlAsM0": "Use mean control ASL as proton density mimic"}),
            "M0_GMScaleFactor": self.spinbox_gmscale.setValue,
            "M0PositionInASL4D": partial(self.main_setter, action="cmb_setCurrentIndex_translate",
                                         widget=self.cmb_m0_posinasl,
                                         translator={"[1 2]": "M0 is the first ASL control-label pair",
                                                     1: "M0 is the first ASL scan volume",
                                                     2: "M0 is the second ASL scan volume"}),
            "readout_dim": partial(self.main_setter, action="cmb_setCurrentIndex_simple", widget=self.cmb_readout_dim),
            "Vendor": partial(self.main_setter, action="cmb_setCurrentIndex_simple", widget=self.cmb_vendor),
            "Sequence": partial(self.main_setter, action="cmb_setCurrentIndex_translate", widget=self.cmb_sequencetype,
                                translator={"3D_spiral": "3D Spiral", "3D_GRASE": "3D GRaSE", "2D_EPI": "2D EPI"}),
            "Quality": partial(self.main_setter, action="cmb_setCurrentIndex_translate", widget=self.cmb_quality,
                               translator={0: "Low", 1: "High"}),
            "DELETETEMP": self.chk_deltempfiles.setChecked,
            "SPIKE_REMOVAL": self.chk_removespikes.setChecked,
            "SpikeRemovalThreshold": self.spinbox_spikethres.setValue,
            "SkipIfNoFlair": self.chk_skipnoflair.setChecked,
            "SkipIfNoM0": self.chk_skipnom0.setChecked,
            "SkipIfNoASL": self.chk_skipnoasl.setChecked,
            "T1_DARTEL": self.chk_uset1dartel.setChecked,
            "PWI_DARTEL": self.chk_usepwidartel.setChecked,
            "BILAT_FILTER": self.chk_usebilatfilter.setChecked,
            "motion_correction": self.chk_motioncorrect.setChecked,
            "SegmentSPM12": partial(self.main_setter, action="cmb_setCurrentIndex_translate", widget=self.cmb_segmethod,
                                    translator={1: "SPM12", 0: "CAT12"}),
            "bRegistrationContrast": partial(self.main_setter, action="cmb_setCurrentIndex_translate",
                                             widget=self.cmb_imgcontrast,
                                             translator={2: "Automatic", 0: "Control --> T1w", 1: "CBF --> pseudoCBF",
                                                         3: "Force CBF --> pseudoCBF"}),
            "bAffineRegistration": partial(self.main_setter, action="cmb_setCurrentIndex_translate",
                                           widget=self.cmb_affineregbase,
                                           translator={0: "Disabled", 1: "Enabled", 2: "Based on PWI CoV"}),
            "bDCTRegistration": partial(self.main_setter, action="cmb_setCurrentIndex_translate",
                                        widget=self.cmb_dctreg,
                                        translator={0: "Disabled", 1: "Enabled + no PVC", 2: "Enabled + PVC"}),
            "bRegisterM02ASL": self.chk_regm0toasl.setChecked,
            "bUseMNIasDummyStructural": self.chk_usemniasdummy.setChecked,
            "MakeNIfTI4DICOM": self.chk_outputcbfmaps.setChecked,
            "ApplyQuantification": self.get_quantparms,
            "FSLdirectory": self.le_fslpath.setText,
            "Q": {
                "BackGrSupprPulses": partial(self.main_setter, action="cmb_setCurrentIndex_simple",
                                             widget=self.cmb_nsup_pulses),
                "LabelingType": partial(self.main_setter, action="cmb_setCurrentIndex_translate",
                                        widget=self.cmb_labelingtype,
                                        translator={"PASL": "Pulsed ASL", "CASL": "Pseudo-continuous ASL",
                                                    "PCASL": "Pseudo-continuous ASL"}),
                "Initial_PLD": self.spinbox_initialpld.setValue,
                "LabelingDuration": self.spinbox_labdur.setValue,
                "SliceReadoutTime": self.spinbox_slice_readout.setValue,
                "Lambda": self.spinbox_lambda.setValue,
                "T2art": self.spinbox_artt2.setValue,
                "TissueT1": self.spinbox_tissuet1.setValue,
                "nCompartments": partial(self.main_setter, action="cmb_setCurrentIndex_simple",
                                         widget=self.cmb_ncomparts)
            }
        }

        to_bool = ["DELETETEMP", "SPIKE_REMOVAL", "SkipIfNoFlair", "SkipIfNoM0", "SkipIfNoASL", "T1_DARTEL",
                   "PWI_DARTEL", "BILAT_FILTER", "motion_correction", "bRegisterM02ASL", "bUseMNIasDummyStructural"]

        for key, call in parms.items():
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
                            print(f"TypeError encountered with key {key}")
                            print(ke)

            except TypeError as te:
                print(f"TypeError encountered with key: {key}")
                print(te)

        if len(self.import_error_logger) > 0:
            errors = "\n -".join(self.import_error_logger)
            QMessageBox().warning(self,
                                  "Errors were encountered importing certain values",
                                  f"The following fields could not be properly imported:\n -{errors}",
                                  QMessageBox.Ok)

    @staticmethod
    def main_setter(argument, widget, action, translator=None):
        if action == "le_setText_commajoin":  # Lineedit; arguments is a list
            if isinstance(argument, list) and len(argument) > 1:
                widget.setText(", ".join(argument))
            else:
                widget.setText(argument[0])
        elif action == "le_setText_simple":  # Lineedit; arguments is a string
            widget.setText(argument)
        elif action == "cmb_setCurrentIndex_translate":  # Combobox; arguments is a string requiring a translator
            index = widget.findText(str(translator[argument]))
            if index == -1:
                return False
            widget.setCurrentIndex(index)
        elif action == "cmb_setCurrentIndex_simple":  # Combobox; arguments is a string present as combobox option
            index = widget.findText(str(argument))
            if index == -1:
                return False
            widget.setCurrentIndex(index)
        elif action == "chk_setChecked_simple":  # QCheckBox; arguments is a bool
            widget.setChecked(argument)

    #############################################
    # Convenience methods for translation to json
    #############################################
    def prep_run_names(self):
        if "," not in self.le_run_names.text():
            return [self.le_run_names.text()]
        else:
            return self.le_run_names.text().split(", ")

    def prep_run_options(self):
        if "," not in self.le_run_options.text():
            return [self.le_run_options.text()]
        else:
            return self.le_run_options.text().split(", ")

    def prep_quantparms(self):
        parms_logvec = self.le_quantset.text().split(" ")
        if all([len(parms_logvec) == 5,  # Must be 5 1s or 0s
                all([x in ['1', '0'] for x in parms_logvec])]):  # Check that all are 1s or 0s
            return [int(option) for option in parms_logvec]
        else:
            QMessageBox().warning(self,
                                  "Incorrect Input for Quantification Settings",
                                  "Must be a series of five 1s or 0s separated by single spaces",
                                  QMessageBox.Ok)

    ###############################################
    # Convenience methods for translation from json
    ###############################################
    def get_m0_posinasl(self, value):
        translator = {"[1 2]": "M0 is the first ASL control-label pair", 1: "M0 is the first ASL scan volume",
                      2: "M0 is the second ASL scan volume"}
        text = translator[value]
        index = self.cmb_m0_posinasl.findText(text)
        if index == -1:
            self.import_error_logger.append("M0 Position in ASL")
            return
        self.cmb_m0_posinasl.setCurrentIndex(index)

    def get_imgconstrast(self, value):
        translator = {2: "Automatic", 0: "Control --> T1w", 1: "CBF --> pseudoCBF", 3: "Force CBF --> pseudoCBF"}
        text = translator[value]
        index = self.cmb_imgcontrast.findText(text)
        if index == -1:
            self.import_error_logger.append("Image Contrast used for")
            return
        self.cmb_imgcontrast.setCurrentIndex(index)

    def get_quantparms(self, value):
        if any([len(value) != 5, sum([str(val).isdigit() for val in value]) != 5]):
            self.import_error_logger.append("Quantification Settings")
            return
        str_value = " ".join([str(val) for val in value])
        self.le_quantset.setText(str_value)

    ############################################
    # Convenience methods for generating widgets
    ############################################

    @staticmethod
    def make_droppable_clearable_le(le_connect_to=None, btn_connect_to=None, default=''):
        """
        Convenience function for creating a lineedit-button pair within a HBoxlayout
        @param le_connect_to: Optional; the function that the linedit's textChanged signal should connect to
        @param btn_connect_to: Optional; the function that the button's clicked signal should connect to
        @param default: the default text to specify
        @return: HBoxlayout, DandD_FileExplorer2LineEdit, QPushButton, in that order
        """
        hlay = QHBoxLayout()
        le = DandD_FileExplorer2LineEdit()
        le.setText(default)
        le.setClearButtonEnabled(True)
        if le_connect_to is not None:
            le.textChanged.connect(le_connect_to)
        btn = QPushButton("...", )
        if btn_connect_to is not None:
            btn.clicked.connect(btn_connect_to)
        hlay.addWidget(le)
        hlay.addWidget(btn)
        return hlay, le, btn

    @staticmethod
    def make_cmb_and_items(items, default=None):
        cmb = QComboBox()
        cmb.addItems(items)
        if default is not None:
            cmb.setCurrentIndex(default)
        return cmb

    @staticmethod
    def make_scrollbar_area(grpwidget: QGroupBox):
        vlay, scrollarea, container = QVBoxLayout(grpwidget), QScrollArea(), QWidget()
        vlay.setContentsMargins(0, 0, 0, 0)
        scrollarea.setWidget(container)
        scrollarea.setWidgetResizable(True)
        vlay.addWidget(scrollarea)
        return vlay, scrollarea, container
