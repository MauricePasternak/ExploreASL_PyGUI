from pydantic import BaseModel, Field, validator, root_validator, ValidationError
from typing import Any, List, Union, Optional
from pathlib import Path
# from pprint import pprint
from more_itertools import peekable
import re
import src.xASL_utils_FileIO as _fileIO

DEFAULTS = {
    "name": "My Study",
    "DROOT": "",
    "subject_regexp": r"^sub\d{3}$",
    "EXPLOREASL_TYPE": "LOCAL_UNCOMPILED",
    "MyPath": "",
    "MCRPath": "",
    "settings.M0_conventionalProcessing": 0,
    "M0": "separate_scan",
    "M0_GMScaleFactor": 1,
    "M0PositionInASL4D": [],
    "DummyScanPositionInASL4D": [],
    "BackgroundSuppressionNumberPulses": 0,
    "BackgroundSuppressionPulseTime": [],
    "PresaturationTime": 1800,
    "readout_dim": "3D",
    "Vendor": "Siemens",
    "Sequence": "3D_GRASE",
    "LabelingType": "PASL",
    "InitialPLD": 1800,
    "LabelingDuration": 800,
    "SliceReadoutTime": 37,
    "bUseBasilQuantification": False,
    "Lambda": 0.9,
    "T2art": 50,
    "TissueT1": 1650,
    "nCompartments": 1,
    "ApplyQuantification": [1, 1, 1, 1, 1],
    "SaveCBF4D": False,
    "Quality": 1,
    "DELETETEMP": 1,
    "SkipIfNoFlair": 0,
    "SkipIfNoASL": 1,
    "SkipIfNoM0": 0,
    "bRunModule_LongReg": 0,
    "bRunModule_DARTEL": 0,
    "settings.SegmentSPM12": 0,
    "bHammersCAT12": 0,
    "bFixResolution": False,
    "motion_correction": 1,
    "SpikeRemovalThreshold": 0.01,
    "bRegistrationContrast": 2,
    "bAffineRegistration": 0,
    "bDCTRegistration": 0,
    "bRegisterM02ASL": 1,
    "bUseMNIasDummyStructural": 0,
    "bPVCNativeSpace": 0,
    "bPVCGaussianMM": 0,
    "PVCNativeSpaceKernel": [5, 5, 1],
    "MakeNIfTI4DICOM": False,
    "bMasking": [1, 1, 1, 1, 1],
    "Atlases": ["TotalGM", "TotalWM"],
}

KEY2FORMALNAME = {
    "name": "Study Name",
    "subject_regexp": "Subject Regexp",
    "MCRPath": "MATLAB Compiled Runtime Folder",
    "MyPath": "ExploreASL Directory",
    "MyPathCompiled": "Compiled ExploreASL Directory",
    "M0": "Type of M0 Image",
    "M0_GMScaleFactor": "M0 Scaling Factor",
    "M0PositionInASL4D": "M0 Location in ASL",
    "DummyScanPositionInASL4D": "Dummies Locations in ASL",
    "readout_dim": "ASL Readout Dimension",
    "Vendor": "Vendor",
    "Sequence": "ASL Image Sequence",
    "bUseBasilQuantification": "Use BASIL Algorithm",
    "ApplyQuantification": "Adjust Quantification Steps",
    "Quality": "Processing Quality",
    "DELETETEMP": "Delete Temporary Files",
    "SkipIfNoFlair": "Skip Subjects without FLAIR",
    "SkipIfNoASL": "Skip Subjects without ASL",
    "SkipIfNoM0": "Skip Subjects without M0",
    "bRunModule_LongReg": "Run Longitudinal Registration",
    "bRunModule_DARTEL": "Run DARTEL Pipeline",
    "bHammersCAT12": "Output Hammers Volume Info",
    "bFixResolution": "Resample for CAT12",
    "motion_correction": "Apply Motion Correction",
    "SpikeRemovalThreshold": "Threshold for Motion Spike",
    "bRegistrationContrast": "Source of Contrast for Registration",
    "bAffineRegistration": "Use followup Affine Transformation",
    "bDCTRegistration": "Use followup DCT Transformation",
    "bRegisterM02ASL": "Register M0 --> ASL",
    "bUseMNIasDummyStructural": "Use MNI Template as backup T1w",
    "bPVCNativeSpace": "Perform PVC on Native Space",
    "PVCNativeSpaceKernel": "PVC Kernel Size",
    "bPVCGaussianMM": "PVC Kernel Type",
    "MakeNIfTI4DICOM": "Make CBF ready for DICOM",
    "D.ROOT": "Study Folder",
    "dataset.exclusion": "Excluded Subjects",
    "Q.BackgroundSuppressionNumberPulses": "Number of Suppressions",
    "Q.BackgroundSuppressionPulseTime": "Suppression Pulse Timings",
    "Q.PresaturationTime": "Presaturation Time",
    "Q.LabelingType": "ASL Labeling Strategy",
    "Q.InitialPLD": "Post-labeling delay",
    "Q.LabelingDuration": "Labeling Duration",
    "Q.SliceReadoutTime": "Slice Readout Time",
    "Q.Lambda": "Lambda",
    "Q.T2art": "T2* of Arterial Blood",
    "Q.TissueT1": "T1 of Grey Matter",
    "Q.nCompartments": "Number of Compartments",
    "Q.SaveCBF4D": "Save CBF Timeseries",
    "S.bMasking": "Control Masking Steps",
    "S.Atlases": "Atlases for ROI Analysis",
    "settings.M0_conventionalProcessing": "Type of M0 Processing",
    "settings.SegmentSPM12": "Segmentation Pipeline",
    "__root__": "__root__"
}

TRANSLATOR = {
    "Vendor": {"General Electric": "GE_product",
               "Philips": "Philips",
               "Siemens": "Siemens"},
    "Sequence": {"3D Spiral": "3D_spiral",
                 "3D GRaSE": "3D_GRASE",
                 "2D EPI": "2D_EPI"},
    "readout_dim": {"2D": "2D",
                    "3D": "3D"},
    "bRegistrationContrast": {"Control -> T1w": 0,
                              "CBF -> pseudoCBF": 1,
                              "Automatic": 2,
                              "Forced CBF --> pseudoCBF": 3},
    "bAffineRegistration": {"Enabled": 1,
                            "Disabled": 0,
                            "Based on CoV of PWI": 2},
    "bDCTRegistration": {"Enabled": 1,
                         "Disabled": 0,
                         "Enabled + UsePVC": 2},
    "LabelingType": {"Pulsed ASL": "PASL",
                     "Continuous ASL": "CASL",
                     "Pseudo-continuous ASL": "PCASL"},
    "EXPLOREASL_TYPE": {"Local ExploreASL Directory": "LOCAL_UNCOMPILED",
                        "Local ExploreASL Compiled": "LOCAL_COMPILED"},
    "SegmentSPM12": {"SPM12": 1,
                     "CAT12": 0},
    "M0_conventionalProcessing": {"Use Standard Processing": 1,
                                  "Use Enhanced Processing": 0},
    "Quality": {"Low": 0, "High": 1}
}

INVERSE_TRANSLATOR = {outer_key: {val: inner_key for inner_key, val in inner_translator.items()}
                      for outer_key, inner_translator in TRANSLATOR.items()
                      }


def try_except(default):
    def decorator(function):
        def wrapper(*args, **kwargs):
            try:
                result = function(*args, **kwargs)
                return result
            except Exception:
                return default

        return wrapper

    return decorator


def is_digit(val):
    try:
        float(val)
        return True
    except (ValueError, TypeError):
        return False


def multiple_replace(string, rep_dict):
    pattern = re.compile("|".join([re.escape(k) for k in sorted(rep_dict, key=len, reverse=True)]), flags=re.DOTALL)
    return pattern.sub(lambda x: rep_dict[x.group(0)], string)


class DatasetFieldsLenient(BaseModel):
    exclusion: Any = []

    @validator("exclusion")
    @classmethod
    def validation_excluded(cls, val, field):
        if not isinstance(val, list):
            return field.default
        for element in val:
            if not isinstance(element, str):
                return field.default
        return val


class DatasetFieldsStrict(BaseModel):
    exclusion: List[str]

    @validator("exclusion")
    @classmethod
    def validation_excluded(cls, val):
        if not isinstance(val, list):
            raise ValueError("This field must be a list of subject names that should be excluded")
        for element in val:
            if not isinstance(element, str):
                raise ValueError("At least one or more elements of this field were not subject names")
        return val


class SettingsFieldStrict(BaseModel):
    M0_conventionalProcessing: Union[int, bool, str] = 0
    SegmentSPM12: Union[int, bool, str] = 0

    @validator("M0_conventionalProcessing", "SegmentSPM12")
    @classmethod
    def appropriate_choices(cls, val, field):
        if isinstance(val, bool):
            return int(val)
        if isinstance(val, str):
            val = int(val) if val.isdigit() else val
        label2value = TRANSLATOR[field.name]
        if val in label2value.keys():
            return label2value[val]
        elif val in label2value.values():
            return val
        else:
            raise ValueError(f"An illegal value was provided for this field")


class SettingsFieldLenient(BaseModel):
    M0_conventionalProcessing: Any = 0
    SegmentSPM12: Any = 0

    @validator("M0_conventionalProcessing", "SegmentSPM12")
    @classmethod
    def binary_choice_as_integer(cls, val, field):
        if isinstance(val, bool):
            return int(val)
        elif isinstance(val, int):
            if val not in {0, 1}:
                return DEFAULTS[field]
            return val
        elif isinstance(val, str):
            if all([val.isdigit(), int(val) in {1, 2}]):
                return int(val)
            else:
                return DEFAULTS[field]
        else:
            return DEFAULTS[field]


class DataFieldsStrict(BaseModel):
    ROOT: str = ""

    @validator("ROOT")
    @classmethod
    def validate_ROOT(cls, val):
        path = _fileIO.pathcheck_aspath(val)
        if not path or not _fileIO.pathcheck_valid_dir(path):
            raise ValueError("The study directory indicated is not a valid directory path.")
        return str(path)


class DataFieldsLenient(BaseModel):
    ROOT: Any = ""

    @validator("ROOT")
    @classmethod
    def validate_ROOT(cls, val, field):
        path = _fileIO.pathcheck_aspath(val)
        if not path or not _fileIO.pathcheck_valid_dir(path):
            return DEFAULTS[field.name]
        return str(path)


class QuantitativeFieldsStrict(BaseModel):
    BackgroundSuppressionNumberPulses: int
    BackgroundSuppressionPulseTime: Union[str, List[Union[int, float]]]
    LabelingType: str
    Initial_PLD: Union[int, float]
    LabelingDuration: Union[int, float]
    SliceReadoutTime: Union[int, float]
    Lambda: Union[int, float] = Field(gt=0, le=1)
    T2art: Union[int, float]
    TissueT1: Union[int, float]
    nCompartments: int
    SaveCBF4D: Union[bool, int]

    @validator("BackgroundSuppressionPulseTime")
    @classmethod
    def validate_bsup_vector(cls, val, values):
        if values["BackgroundSuppressionNumberPulses"] == 0 and len(val) > 0:
            raise ValueError(f"You have indicated that there are zero suppression pulses yet provided the timings "
                             f"for {len(val)} pulses")

        if isinstance(val, str):
            val = val.strip().strip("[]")
            if re.search(r"[^,^\s\d]", val):
                raise ValueError("Only numbers, spaces, and commas are allowed.")
            val = val.split(",")
            try:
                val = [int(round(float(x.strip()), 0)) for x in val]
            except ValueError:
                raise ValueError("The list of background suppression timings must be comma-separated numbers.")
            return val
        else:
            return val

    @validator("nCompartments")
    @classmethod
    def n_compartments_validate(cls, val):
        if val not in {1, 2}:
            raise ValueError("The indicated number of compartments for quantification must be either 1 or 2")
        return val

    @validator("SaveCBF4D")
    @classmethod
    def binary_choice_as_boolean(cls, val):
        if isinstance(val, bool):
            return val
        elif isinstance(val, int):
            return bool(val)
        else:
            raise ValueError(f"This field must be either supplied as a 0, 1, or a boolean True/False.")

    @validator("LabelingType")
    @classmethod
    def appropriate_choices(cls, val, field):
        if isinstance(val, str):
            val = int(val) if val.isdigit() else val
        label2value = TRANSLATOR[field.name]
        if val in label2value.keys():
            return label2value[val]
        elif val in label2value.values():
            return val
        else:
            raise ValueError(f"An illegal value was provided for this field")


class QuantitativeFieldsLenient(BaseModel):
    BackgroundSuppressionNumberPulses: Any = 0
    BackgroundSuppressionPulseTime: Any = []
    LabelingType: Any = "PASL"
    Initial_PLD: Any = 1800
    LabelingDuration: Any = 800
    SliceReadoutTime: Any = 37
    Lambda: Any = 0.9
    T2art: Any = 50
    TissueT1: Any = 1650
    nCompartments: Any = 1
    SaveCBF4D: Any = False

    @validator("nCompartments")
    @classmethod
    def validate_n_compartments(cls, val, field):
        if val not in {1, 2}:
            return DEFAULTS[field.name]
        return val

    @validator("LabelingType")
    @classmethod
    def appropriate_choices(cls, val, field):
        if isinstance(val, str):
            val = int(val) if val.isdigit() else val
        label2value = TRANSLATOR[field.name]
        if val in label2value.keys():
            return label2value[val]
        elif val in label2value.values():
            return val
        else:
            return DEFAULTS[field.name]

    @validator("SaveCBF4D")
    @classmethod
    def binary_choice_as_boolean(cls, val, field):
        if isinstance(val, bool):
            return val
        elif isinstance(val, (int, float)):
            return bool(val)
        else:
            return DEFAULTS[field.name]

    @validator("BackgroundSuppressionNumberPulses", "Initial_PLD", "LabelingDuration", "SliceReadoutTime", "Lambda",
               "T2art", "TissueT1", "nCompartments")
    @classmethod
    def is_number(cls, val, field):
        if not any([isinstance(val, (int, float))]):
            return DEFAULTS[field.name]
        return val

    @validator("BackgroundSuppressionPulseTime")
    @classmethod
    def is_field_of_integers(cls, val, field):
        if not isinstance(val, list):
            return DEFAULTS[field.name]
        for element in val:
            if not isinstance(element, int):
                return DEFAULTS[field.name]
        return val


class MaskingFieldsStrict(BaseModel):
    bMasking: Optional[List[int]]
    Atlases: List[str]

    @validator("bMasking")
    @classmethod
    def validate_quantvector(cls, val):
        if all([isinstance(val, int), val in [0, 1]]):
            return [val] * 4
        if not all([isinstance(val, list), len(val) == 4]):
            raise TypeError("This field must be a list of integers that are either 1 or 0")
        for element in val:
            if element not in {0, 1}:
                raise ValueError("One or more elements in this field was not an integer")
        return val

    @validator("Atlases")
    @classmethod
    def is_field_of_particularstrings(cls, val):
        for element in val:
            if element not in {"TotalGM", "TotalWM", "DeepWM", "MNI_Structural", "Hammers", "HOcort_CONN", "HOsub_CONN",
                               "Mindboggle_OASIS_DKT31_CMA"}:
                raise ValueError(f"One or more elements in this field are not valid atlas names")
        return val


class MaskingFieldsLenient(BaseModel):
    bMasking: Any = [1, 1, 1, 1, 1]
    Atlases: Any = ["TotalGM", "TotalWM"],

    @validator("bMasking")
    @classmethod
    def validate_quantvector(cls, val, field):
        if all([isinstance(val, int), val in [0, 1]]):
            return [val] * 4
        if not all([isinstance(val, list), len(val) == 4]):
            return DEFAULTS[field.name]
        for element in val:
            if element not in {0, 1}:
                return DEFAULTS[field.name]
        return val

    @validator("Atlases")
    @classmethod
    def is_field_of_particularstrings(cls, val, field):
        if not isinstance(val, list):
            return DEFAULTS[field.name]
        for element in val:
            if element not in {"TotalGM", "TotalWM", "DeepWM", "Hammers", "MNI_Structural", "HOcort_CONN", "HOsub_CONN",
                               "Mindboggle_OASIS_DKT31_CMA"}:
                return DEFAULTS[field.name]
        return val


class DataParSchemaStrict(BaseModel):
    # Study Parameters
    name: str
    EXPLOREASL_TYPE: str
    MCRPath: Union[str, Path]
    MyPath: Union[str, Path]
    dataset: DatasetFieldsStrict
    D: DataFieldsStrict
    subject_regexp: str
    MakeNIfTI4DICOM: Union[int, bool]
    bUseBasilQuantification: Union[int, bool]
    bFixResolution: Union[int, bool]

    # M0 Parameters
    M0: Union[int, float, str]
    M0_GMScaleFactor: Union[int, float]
    M0PositionInASL4D: Union[str, None, int, List[int]]
    DummyScanPositionInASL4D: Union[str, None, List[int]]

    # Sequence Parameters
    Vendor: str
    Sequence: str
    readout_dim: str

    # Quantification Parameters
    ApplyQuantification: List[int]

    # General Processing Parameters
    Quality: Union[int, bool]
    DELETETEMP: Union[int, bool]
    SkipIfNoFlair: Union[int, bool]
    SkipIfNoASL: Union[int, bool]
    SkipIfNoM0: Union[int, bool]

    # Structural Processing Parameters
    bRunModule_LongReg: Union[int, bool]
    bRunModule_DARTEL: Union[int, bool]

    # ASL Processing Parameters
    motion_correction: Union[int, bool]
    SpikeRemovalThreshold: Union[int, float]
    bRegistrationContrast: Union[str, int]
    bAffineRegistration: Union[int, bool]
    bDCTRegistration: Union[int, bool]
    bRegisterM02ASL: Union[int, bool]
    bUseMNIasDummyStructural: Union[int, bool]
    bPVCNativeSpace: Union[int, bool]
    bPVCGaussianMM: Union[int, bool]
    PVCNativeSpaceKernel: List[int]

    # Quantitiative and Masking Fields
    Q: QuantitativeFieldsStrict
    S: MaskingFieldsStrict

    settings: SettingsFieldStrict

    @validator("MCRPath")
    @classmethod
    def validate_runtimepath(cls, val, values):
        if values["EXPLOREASL_TYPE"] == "LOCAL_UNCOMPILED" and val in {None, ""}:
            return ""

        if values["EXPLOREASL_TYPE"] == "LOCAL_UNCOMPILED" and val not in {None, ""}:
            raise ValueError(f"If your type of ExploreASL directory is from the Github respository, "
                             f"you cannot specify a MATLAB Compiled Runtime path. Please leave this field blank.")
        path = _fileIO.pathcheck_aspath(val)
        if not path:
            raise ValueError("This field was found to no longer exist")

        if not _fileIO.pathcheck_valid_dir(path):
            raise ValueError("This field needs to point to a directory.")

        if not _fileIO.pathcheck_basename_regex(path, "v\\d{2,3}"):
            raise ValueError("This is not a valid MATLAB Compiled Runtime. "
                             "This folder should contain a child folder called v96 or v97")

        return str(path)

    @validator("MyPath")
    @classmethod
    def validate_MyPath(cls, val, values):

        if not val or not isinstance(val, (Path, str)):
            raise ValueError("An invalid value was supplied for this field")

        # ExploreASL from Github
        if values["EXPLOREASL_TYPE"] == "LOCAL_UNCOMPILED":
            path = _fileIO.pathcheck_aspath(val)
            if not path:
                raise ValueError("This field was found to no longer exist")

            if not _fileIO.pathcheck_valid_dir(path):
                raise ValueError("This field needs to point to a directory.")

            if not _fileIO.pathcheck_child_fits_regex(path, "ExploreASL_Master.m"):
                raise ValueError("ExploreASL Directory was compromised as it did not contain a master script.")
            return str(path)

        # Note: If working with the compiled ExploreASL, the MyPath variable must point to a possibly-not-yet-existing
        # location along the lines of ./xASL_latest/xASL_latest_mcr/xASL_latest ; The first xASL_latest is the folder
        # that contains the run_xASL_latest script. The section will contain ExploreASL.m ; this MyPath key must point
        # to the latter
        elif values["EXPLOREASL_TYPE"] == "LOCAL_COMPILED":
            initial_path = Path(val)
            # Scenario 1: User has indicated the later xASL_latest folder which does not exist yet
            try:
                if all([
                    # These custom basename methods work with non-existent paths
                    _fileIO.pathcheck_basename_regex(initial_path, "xASL_.*"),
                    _fileIO.pathcheck_basename_regex(initial_path.parent, "xASL_.*_mcr"),
                    _fileIO.pathcheck_filechild_exists(initial_path.parent.parent, "xASL_latest.ctf")
                ]):
                    return str(initial_path)
            except (ValueError, AttributeError):
                raise ValueError("An invalid value or corrupt series of characters was supplied for this field")

            # Otherwise, need to proceed as if verifying a legitimate file
            path = _fileIO.pathcheck_aspath(initial_path)
            if not path:
                raise ValueError("This field was found to no longer exist")

            if not _fileIO.pathcheck_valid_dir(path):
                raise ValueError("This field needs to point to a directory.")

            # First try to find out if the ExploreASL_Master.m file can be derived
            match = peekable(path.rglob("ExploreASL_Master.m"))
            if match:
                path = next(match).parent
                if not _fileIO.pathcheck_basename_regex(path.parent, "xASL_.*_mcr"):
                    raise ValueError("The ExploreASL directory you have specified is likely the uncompiled version "
                                     "(i.e. straight from Github) but have selected the type of ExploreASL directory "
                                     "as compiled.")
                else:
                    return str(path)

            # Scenario 2: User has indicated the early xASL_latest folder and has not yet run the run_xASL_latest.sh
            if all([
                not _fileIO.pathcheck_filechild_exists(path, "ExploreASL_Master.m"),
                _fileIO.pathcheck_filechild_exists(path, "run_xASL_latest.sh") or
                _fileIO.pathcheck_filechild_exists(path, "xASL_latest.exe"),
                _fileIO.pathcheck_filechild_exists(path, "xASL_latest.ctf")
            ]):
                path = path / "xASL_latest_mcr" / "xASL_latest"
                return str(path)

            # Scenario 3: User has indicated the latter xASL_latest folder was exists by this point
            elif all([
                _fileIO.pathcheck_basename_regex(path, "xASL_.*"),
                _fileIO.pathcheck_basename_regex(path.parent, "xASL_.*_mcr"),
                _fileIO.pathcheck_filechild_exists(path, "ExploreASL_Master.m"),
            ]):
                return str(path)

            else:
                raise ValueError("Could not locate a valid compiled ExploreASL")

        else:
            raise ValueError("Cannot determine legitimacy of the path in the absence of ExploreASL type context.")

    @validator("subject_regexp")
    @classmethod
    def validate_regexp(cls, val, values):
        try:
            study_dir_path = _fileIO.pathcheck_aspath(values["D"].ROOT)
        except KeyError:
            raise ValueError("Could not assess subject matches to a non-existent study directory")
        # Study directory is already incorrect, don't proceed further
        if not study_dir_path:
            return val
        if not _fileIO.pathcheck_childdir_fits_regex(study_dir_path, val):
            raise ValueError("Could not match any subjects in the indicated study directory")
        return val

    @validator("M0")
    @classmethod
    def validate_M0(cls, val):
        if isinstance(val, str):
            if val in {"separate_scan", "UseControlAsM0"}:
                return val
            raise ValueError("Invalid value provided for the kind of M0 image present in this study.")
        elif isinstance(val, (int, float)):
            return val
        else:
            raise ValueError("Invalid value provided for the type of M0 image. Either indicate that it is a separate"
                             "scan, indicate to use the mean control ASL as a substitute or provide a single number.")

    @validator("M0PositionInASL4D")
    @classmethod
    def validate_M0Position(cls, val, values):
        if all([values.get("M0") == "separate_scan", not isinstance(val, list), val]):
            raise ValueError(f"You have implicitly specified that there is an M0 within the series while also "
                             f"specifying that the M0 is/are located in a separate file")
        return val

    @validator("DummyScanPositionInASL4D")
    @classmethod
    def validate_dummyposinASL(cls, val):
        if val is None:
            return []
        if isinstance(val, list):
            if any([not str(x).isdigit() for x in val]):
                raise ValueError(f"A list of comma-separated integers must be provided for this field.")
            return val
        elif isinstance(val, str):
            val = val.strip().strip("[]")
            match = re.search(r"[^,^\s\d]", val)
            if match:
                raise ValueError("Only numbers, commas, and spaces are allowed for this field.")
            try:
                val = [int(x) for x in val.split(",")]
                return val
            except ValueError:
                raise ValueError("This field could not be separated into individual numbers. "
                                 "Have you misplaced a comma somewhere?")

    @validator("readout_dim")
    @classmethod
    def dim_matches_sequence(cls, val, values):
        if val not in {"3D", "2D"}:
            raise ValueError("Readout Dimension must be indicated as either 3D or 2D")
        if values["Sequence"] in {"3D_spiral", "3D_GRASE"}:
            return "3D"
        elif values["Sequence"] == "2D_EPI":
            return "2D"
        else:
            raise ValueError(f"The provided readout dimension: {val} ...is not compatible with the indicated Sequence: "
                             f"{values['Sequence']}")

    @validator("ApplyQuantification")
    @classmethod
    def validate_quantvector(cls, val):
        if not all([isinstance(val, list), len(val) == 5]):
            raise TypeError("This field must be a list of integers that are either 1 or 0")
        for element in val:
            if element not in {0, 1}:
                raise ValueError("One or more elements in this field was not an integer")
        return val

    @validator("PVCNativeSpaceKernel")
    @classmethod
    def validate_pvckernel(cls, val):
        if not all([isinstance(val, list), len(val) == 3]):
            raise TypeError("This field must be a list of 3 odd integers")
        for element in val:
            if any([not isinstance(element, int), element < 1, element % 2 == 0]):
                raise ValueError("One or more elements in this field were not a positive odd number")
        return val

    @validator("Quality", "DELETETEMP", "SkipIfNoFlair", "SkipIfNoASL",
               "SkipIfNoM0", "bRunModule_LongReg", "bRunModule_DARTEL", "motion_correction", "bRegisterM02ASL",
               "bUseMNIasDummyStructural", "bPVCNativeSpace", "bPVCGaussianMM", pre=True)
    @classmethod
    def binary_choice_as_integer(cls, val):
        if isinstance(val, bool):
            return int(val)
        elif isinstance(val, int):
            if val not in {0, 1}:
                raise ValueError(f"This field, if provided as a number, must be either 0 or 1")
            return val
        else:
            raise ValueError(f"This field must be either supplied as a 0, 1, or a boolean True/False.")

    @validator("MakeNIfTI4DICOM", "bUseBasilQuantification", "bFixResolution")
    @classmethod
    def binary_choice_as_boolean(cls, val):
        if isinstance(val, bool):
            return val
        elif isinstance(val, int):
            return bool(val)
        else:
            raise ValueError(f"This field must be either supplied as a 0, 1, or a boolean True/False.")

    @validator("Vendor", "Sequence", "bRegistrationContrast", "bAffineRegistration", "bDCTRegistration",
               "EXPLOREASL_TYPE")
    @classmethod
    def appropriate_choices(cls, val, field):
        if isinstance(val, str):
            val = int(val) if val.isdigit() else val
        label2value = TRANSLATOR[field.name]
        if val in label2value.keys():
            return label2value[val]
        elif val in label2value.values():
            return val
        else:
            raise ValueError(f"An illegal value was provided for this field")

    @root_validator(pre=False)
    @classmethod
    def validate_bsup_npulse(cls, values):
        try:
            q_vals = values["Q"]
            if all([q_vals.BackgroundSuppressionNumberPulses > 0,
                    values.get("M0") == "UseControlAsM0",
                    len(q_vals.BackgroundSuppressionPulseTime) == 0
                    ]):
                raise ValueError(f"A vector of background suppression timings is required when you have indicated "
                                 f"that a control ASL will be used as a stand-in M0 as well as there being 1 or more "
                                 f"background suppression pulses present.")
        except KeyError:
            raise ValueError(f"Quantitative field values in this form were compromised.")
        return values


class DataParSchemaLenient(BaseModel):
    # Study Parameters
    name: Any = "My Study"
    EXPLOREASL_TYPE: Any = "LOCAL_UNCOMPILED"
    MCRPath: Any = ""
    MyPath: Any = ""
    dataset: DatasetFieldsLenient = DatasetFieldsLenient()
    D: DataFieldsLenient = DataFieldsLenient()
    subject_regexp: Any = r"^sub_\d{3}$"
    MakeNIfTI4DICOM: Any = False
    bUseBasilQuantification: Any = False
    bFixResolution: Any = False

    # M0 Parameters
    M0: Any = "separate_scan"
    M0_GMScaleFactor: Any = 1
    M0PositionInASL4D: Any = []
    DummyScanPositionInASL4D: Any = []

    # Sequence Parameters
    Vendor: Any = "Siemens"
    Sequence: Any = "3D_GRASE"
    readout_dim: Any = "3D"

    # Quantification Parameters
    ApplyQuantification: Any = [1, 1, 1, 1, 1]

    # General Processing Parameters
    Quality: Any = 1
    DELETETEMP: Any = 1
    SkipIfNoFlair: Any = 0
    SkipIfNoASL: Any = 0
    SkipIfNoM0: Any = 0

    # Structural Processing Parameters
    bRunModule_LongReg: Any = 0
    bRunModule_DARTEL: Any = 0

    # ASL Processing Parameters
    motion_correction: Any = 0
    SpikeRemovalThreshold: Any = 0.01
    bRegistrationContrast: Any = 2
    bAffineRegistration: Any = 0
    bDCTRegistration: Any = 0
    bRegisterM02ASL: Any = 1
    bUseMNIasDummyStructural: Any = 0
    bPVCNativeSpace: Any = 0
    bPVCGaussianMM: Any = 0
    PVCNativeSpaceKernel: Any = [5, 5, 1]

    # Quantitiative and Masking Fields
    Q: QuantitativeFieldsLenient = QuantitativeFieldsLenient()
    S: MaskingFieldsLenient = MaskingFieldsLenient()
    settings: SettingsFieldLenient = SettingsFieldLenient()

    @validator("MCRPath")
    @classmethod
    def validate_runtimepath(cls, val, values, field):
        if values["EXPLOREASL_TYPE"] == "LOCAL_UNCOMPILED" and val in {None, ""}:
            return field.default
        if values["EXPLOREASL_TYPE"] == "LOCAL_UNCOMPILED" and val not in {None, ""}:
            return field.default

        path = _fileIO.pathcheck_aspath(val)
        if not path:
            return field.default
        if not _fileIO.pathcheck_basename_regex(path, "v\\d{2,3}"):
            return field.default
        return str(path)

    @validator("MyPath")
    @classmethod
    def validate_MyPath(cls, val, values, field):
        if not val or not isinstance(val, (Path, str)):
            return field.default

        # ExploreASL from Github
        if values["EXPLOREASL_TYPE"] == "LOCAL_UNCOMPILED":
            path = _fileIO.pathcheck_aspath(val)
            if not path:
                return field.default

            if not _fileIO.pathcheck_valid_dir(path):
                return field.default

            if not _fileIO.pathcheck_child_fits_regex(path, "ExploreASL_Master.m"):
                return field.default
            return str(path)

        # Note: If working with the compiled ExploreASL, the MyPath variable must point to a possibly-not-yet-existing
        # location along the lines of ./xASL_latest/xASL_latest_mcr/xASL_latest ; The first xASL_latest is the folder
        # that contains the run_xASL_latest script. The section will contain ExploreASL.m ; this MyPath key must point
        # to the latter
        elif values["EXPLOREASL_TYPE"] == "LOCAL_COMPILED":
            initial_path = Path(val)
            # Scenario 1: User has indicated the later xASL_latest folder which does not exist yet
            try:
                if all([
                    # These custom basename methods work with non-existent paths
                    _fileIO.pathcheck_basename_regex(initial_path, "xASL_.*"),
                    _fileIO.pathcheck_basename_regex(initial_path.parent, "xASL_.*_mcr"),
                    _fileIO.pathcheck_filechild_exists(initial_path.parent.parent, "xASL_latest.ctf")
                ]):
                    return str(initial_path)
            except (ValueError, AttributeError):
                return field.default

            # Otherwise, need to proceed as if verifying a legitimate file
            path = _fileIO.pathcheck_aspath(initial_path)
            if not path:
                return field.default

            if not _fileIO.pathcheck_valid_dir(path):
                return field.default

            # First try to find out if the ExploreASL_Master.m file can be derived
            match = peekable(path.rglob("ExploreASL_Master.m"))
            if match:
                path = next(match).parent
                if not _fileIO.pathcheck_basename_regex(path.parent, "xASL_.*_mcr"):
                    return field.default
                else:
                    return str(path)

            # Scenario 2: User has indicated the early xASL_latest folder and has not yet run the run_xASL_latest.sh
            if all([
                not _fileIO.pathcheck_filechild_exists(path, "ExploreASL_Master.m"),
                _fileIO.pathcheck_filechild_exists(path, "run_xASL_latest.sh") or
                _fileIO.pathcheck_filechild_exists(path, "xASL_latest.exe"),
                _fileIO.pathcheck_filechild_exists(path, "xASL_latest.ctf")
            ]):
                path = path / "xASL_latest_mcr" / "xASL_latest"
                return str(path)

            # Scenario 3: User has indicated the latter xASL_latest folder was exists by this point
            elif all([
                _fileIO.pathcheck_basename_regex(path, "xASL_.*"),
                _fileIO.pathcheck_basename_regex(path.parent, "xASL_.*_mcr"),
                _fileIO.pathcheck_filechild_exists(path, "ExploreASL_Master.m"),
            ]):
                return str(path)

            else:
                return field.default

        else:
            return field.default

    @validator("subject_regexp")
    @classmethod
    def validate_regexp(cls, val, values, field):
        study_dir_path = _fileIO.pathcheck_aspath(values["D"].ROOT)
        # Study directory is already incorrect, don't proceed further
        if not study_dir_path:
            return field.default
        if not _fileIO.pathcheck_childdir_fits_regex(study_dir_path, val):
            return field.default
        return val

    @validator("M0")
    @classmethod
    def validate_M0(cls, val, field):
        if isinstance(val, str):
            if val in {"separate_scan", "UseControlAsM0"}:
                return val
            return field.default
        elif is_digit(val):
            return float(val)
        else:
            return field.default

    @validator("M0PositionInASL4D")
    @classmethod
    def validate_M0Position(cls, val, values, field):
        if val is None:
            return field.default
        if all([values.get("M0") == "separate_scan", not isinstance(val, list), val]):
            return field.default
        return val

    @validator("DummyScanPositionInASL4D")
    @classmethod
    def validate_dummyposinASL(cls, val, field):
        if val is None:
            return []
        if isinstance(val, list):
            if any([not str(x).isdigit() for x in val]):
                return field.default
            return val
        elif isinstance(val, str):
            val = val.strip().strip("[]")
            match = re.search(r"[^,^\s\d]", val)
            if match:
                return field.default
            try:
                val = [int(x) for x in val.split(",")]
                return val
            except ValueError:
                return field.default

    @try_except(DEFAULTS["readout_dim"])
    @validator("readout_dim")
    @classmethod
    def dim_matches_sequence(cls, val, values, field):
        if val not in {"3D", "2D"}:
            return field.default
        if values["Sequence"] in {"3D_spiral", "3D_GRASE"}:
            return "3D"
        elif values["Sequence"] == "2D_EPI":
            return "2D"
        else:
            return field.default

    @validator("ApplyQuantification")
    @classmethod
    def validate_quantvector(cls, val):
        if not all([isinstance(val, list), len(val) == 5]):
            raise TypeError("This field must be a list of integers that are either 1 or 0")
        for element in val:
            if element not in {0, 1}:
                raise ValueError("One or more elements in this field was not an integer")
        return val

    @validator("PVCNativeSpaceKernel")
    @classmethod
    def validate_pvckernel(cls, val, field):
        if not all([isinstance(val, list), len(val) == 3]):
            return field.default
        for element in val:
            if any([not isinstance(element, int), element < 1, element % 2 == 0]):
                return field.default
        return val

    @validator("Quality", "DELETETEMP", "SkipIfNoFlair", "SkipIfNoASL",
               "SkipIfNoM0", "bRunModule_LongReg", "bRunModule_DARTEL", "motion_correction", "bRegisterM02ASL",
               "bUseMNIasDummyStructural", "bPVCNativeSpace", "bPVCGaussianMM", pre=True)
    @classmethod
    def binary_choice_as_integer(cls, val, field):
        if isinstance(val, bool):
            return int(val)
        elif isinstance(val, int):
            if val not in {0, 1}:
                return field.default
            return val
        else:
            raise field.default

    @validator("MakeNIfTI4DICOM", "bUseBasilQuantification", "bFixResolution")
    @classmethod
    def binary_choice_as_boolean(cls, val, field):
        if isinstance(val, bool):
            return val
        elif isinstance(val, int):
            return bool(val)
        else:
            return field.default

    @validator("Vendor", "Sequence", "bRegistrationContrast", "bAffineRegistration", "bDCTRegistration",
               "EXPLOREASL_TYPE")
    @classmethod
    def appropriate_choices(cls, val, field):
        if isinstance(val, str):
            val = int(val) if val.isdigit() else val
        label2value = TRANSLATOR[field.name]
        if val in label2value.keys():
            return label2value[val]
        elif val in label2value.values():
            return val
        else:
            return field.default


def parse_errors(errors: ValidationError.errors):
    replacer = {"integer": "number", "float": "number", "str type expected": "Wrong kind of value"}
    msgs = ['The following errors were encountered for the supplied information:']
    general_msgs = set()
    seen_locations = set()
    counter = 1
    for error in errors:
        location = ".".join([x for x in error["loc"] if not str(x).isdigit()])
        formal_name = KEY2FORMALNAME.get(location)
        if not formal_name or formal_name in seen_locations:
            continue

        if formal_name != "__root__":
            seen_locations.add(formal_name)
            final_message = multiple_replace(error["msg"], replacer)
            msgs.append(f"{counter}) {formal_name}: {final_message}")
            counter += 1
        else:
            general_msgs.add(error["msg"])

    if general_msgs:
        msgs.append("Related Errors:")
        for msg in general_msgs:
            msgs.append(msg)

    return msgs
