import os
from glob import glob
import re
from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *

# Creates lock dirs where necessary in anticipation for assigning a watcher to the root lock directory
def initialize_all_lock_dirs(analysis_dir, regex, run_options, session_names):
    """
    Convenience function for creating the lock directories in advance of a run such that a file system watcher
    could effectively be set at the root and detect any downstream changes
    :param analysis_dir: the root analysis directory of the study ex. User\\Study_Name\\analysis
    :param regex: the regex used to identify subjects
    :param run_options: the type of run (ex. ASL, Structural, Both, Population)
    :param session_names: the expected session names that should be encountered (ex. ASL_1, ASL_2, etc.)
    :return: Does not return anything
    """

    def dirnames_for_asl(analysis_directory, study_sessions, within_session_names):
        dirnames = [os.path.join(analysis_directory, "lock", f"xASL_module_ASL", sess, f"xASL_module_ASL_{name}")
                    for sess in study_sessions for name in within_session_names]
        return dirnames

    def dirnames_for_structural(analysis_directory, study_sessions):
        dirnames = [
            os.path.join(analysis_directory, "lock", f"xASL_module_Structural", sess, "xASL_module_Structural")
            for sess in study_sessions]
        return dirnames

    def dirnames_for_population(analysis_directory):
        return [os.path.join(analysis_directory, "lock", "xASL_module_Population", "xASL_module_Population")]

    print(f"Generating the appropriate lock dirs for {analysis_dir}")
    sessions = [session for session in os.listdir(analysis_dir) if regex.search(session)]

    # Prepare the list of names of lockdirs to expect to create based on the run options, session names and detected
    # sessions in the analysis root directory
    if run_options == "Both":
        struc_dirs = dirnames_for_structural(analysis_dir, sessions)
        asl_dirs = dirnames_for_asl(analysis_dir, sessions, session_names)
        lock_dirs = struc_dirs + asl_dirs
    elif run_options == "ASL":
        lock_dirs = dirnames_for_asl(analysis_dir, sessions, session_names)
    elif run_options == "Structural":
        lock_dirs = dirnames_for_structural(analysis_dir, sessions)
    elif run_options == "Population":
        lock_dirs = dirnames_for_population(analysis_dir)
    else:
        raise ValueError("Impossible outcome in initialize_all_lock_dirs")

    # Create empty directories where applicable
    for lock_dir in lock_dirs:
        if not os.path.exists(lock_dir):
            os.makedirs(lock_dir)


# Must be called after the lock dirs have been created; this function will attempt to calculate all the status files
# that should be created in the run process
def calculate_anticipated_workload(parmsdict, run_options):
    """
    Convenience function for calculating the anticipated workload
    :param parmsdict: the parameter file of the study; given parameters such as the regex are used from this
    :param run_options: "Structural", "ASL", "Both" or "Population"; which module is being run
    :return: workload; a numerical representation of the cumulative value of all status files made; these will be
    used to determine the appropriate maximum value for the progressbar
    """

    def get_structural_workload(analysis_directory, study_subjects, structuralmod_dict):
        workload_translator = {
            "010_LinearReg_T1w2MNI.status": 1, "020_LinearReg_FLAIR2T1w.status": 2,
            "030_Resample_FLAIR2T1w.status": 1, "040_Segment_FLAIR.status": 3, "050_LesionFilling.status": 1,
            "060_Segment_T1w.status": 10, "070_GetWMHvol.status": 1, "080_Resample2StandardSpace.status": 2,
            "090_GetVolumetrics.status": 1, "100_VisualQC_Structural.status": 1, "999_ready.status": 0
        }
        default_workload = ["010_LinearReg_T1w2MNI.status", "060_Segment_T1w.status",
                            "080_Resample2StandardSpace.status", "090_GetVolumetrics.status",
                            "100_VisualQC_Structural.status", "999_ready.status"]
        flair_workload = ["020_LinearReg_FLAIR2T1w.status", "030_Resample_FLAIR2T1w.status",
                          "040_Segment_FLAIR.status", "050_LesionFilling.status", "070_GetWMHvol.status"]

        for subject in study_subjects:
            has_flair_img = os.path.exists(os.path.join(analysis_directory, subject, "FLAIR.nii"))
            current_status_files = os.listdir(os.path.join(analysis_directory,
                                                           "lock", "xASL_module_Structural", subject,
                                                           "xASL_module_Structural"))
            if has_flair_img:
                workload = default_workload + flair_workload
            else:
                workload = default_workload

            # Filter out any anticipated status files that are already present in the lock dirs
            filtered_workload = set(workload).difference(set(current_status_files))
            numerical_representation = sum([workload_translator[stat_file] for stat_file in filtered_workload])
            structuralmod_dict[subject] = numerical_representation

        return structuralmod_dict

    def get_asl_workload(analysis_directory, study_subjects, session_names, aslmod_dict):
        workload_translator = {
            "020_RealignASL.status": 1, "030_RegisterASL.status": 2, "040_ResampleASL.status": 1,
            "050_PreparePV.status": 1, "060_ProcessM0.status": 1, "070_Quantification.status": 2,
            "080_CreateAnalysisMask.status": 1, "090_VisualQC_ASL.status": 1, "999_ready.status": 0
        }
        default_workload = ["020_RealignASL.status", "030_RegisterASL.status", "040_ResampleASL.status",
                            "050_PreparePV.status", "060_ProcessM0.status", "070_Quantification.status",
                            "080_CreateAnalysisMask.status", "090_VisualQC_ASL.status", "999_ready.status"]

        # Must iterate through both the subject level listing AND the session level (ASL_1, ASL_2, etc.) listing
        for subject in study_subjects:
            for session in session_names:
                current_status_files = os.listdir(os.path.join(analysis_directory, "lock", "xASL_module_ASL",
                                                               subject, f"xASL_module_ASL_{session}"))
                workload = default_workload
                # Filter out any anticipated status files that are already present in the lock dirs
                filtered_workload = set(workload).difference(set(current_status_files))
                numerical_representation = sum([workload_translator[stat_file] for stat_file in filtered_workload])
                aslmod_dict[subject][session] = numerical_representation

        return aslmod_dict

    def get_population_workload(analysis_directory):
        workload_translator = {
            "010_CreatePopulationTemplates.status": 1, "020_CreateAnalysisMask.status": 1,
            "030_CreateBiasfield.status": 1, "040_GetDICOMStatistics.status": 1,
            "050_GetVolumeStatistics.status": 1, "060_GetMotionStatistics.status": 1,
            "070_GetROIstatistics.status": 20, "080_SortBySpatialCoV.status": 1, "090_DeleteAndZip.status": 1,
            "999_ready.status": 0
        }
        default_workload = ["010_CreatePopulationTemplates.status", "020_CreateAnalysisMask.status",
                            "030_CreateBiasfield.status", "040_GetDICOMStatistics.status",
                            "050_GetVolumeStatistics.status", "060_GetMotionStatistics.status",
                            "070_GetROIstatistics.status", "080_SortBySpatialCoV.status",
                            "090_DeleteAndZip.status", "999_ready.status"]
        current_status_files = os.listdir(os.path.join(analysis_directory, "lock", "xASL_module_Population",
                                                       "xASL_module_Population"))
        workload = default_workload
        filtered_workload = set(workload).difference(set(current_status_files))
        numerical_representation = sum([workload_translator[stat_file] for stat_file in filtered_workload])
        return numerical_representation

    # First get all the subjects
    analysis_dir: str = parmsdict["D"]["ROOT"]
    regex = re.compile(parmsdict["subject_regexp"])
    sess_names: list = parmsdict["SESSIONS"]
    subjects = [subject for subject in os.listdir(analysis_dir) if
                all([regex.search(subject),  # regex must fit
                     os.path.isdir(os.path.join(analysis_dir, subject)),  # must be a directory
                     subject not in ["Population", "lock"]  # can't accidentally be the non-subject directories
                     ])]

    # Use a dict to keep track of everything
    struct_dict = {subject: 0 for subject in subjects}
    asl_dict = {subject: {} for subject in subjects}

    # Update the dicts as appropriate
    if run_options == "Both":
        struct_dict = get_structural_workload(analysis_dir, subjects, struct_dict)
        asl_dict = get_asl_workload(analysis_dir, subjects, sess_names, asl_dict)
        # pprint(struct_dict)
        # pprint(asl_dict)

        struct_totalworkload = sum(struct_dict.values())
        asl_totalworkload = {subject: sum(asl_dict[subject].values()) for subject in subjects}
        asl_totalworkload = sum(asl_totalworkload.values())
        print(f"Structural Calculated Workload: {struct_totalworkload}")
        print(f"ASL Calculated Workload: {asl_totalworkload}")
        return struct_totalworkload + asl_totalworkload

    elif run_options == "ASL":
        asl_dict = get_asl_workload(analysis_dir, subjects, sess_names, asl_dict)
        # pprint(asl_dict)
        asl_totalworkload = {subject: sum(asl_dict[subject].values()) for subject in subjects}
        asl_totalworkload = sum(asl_totalworkload.values())
        print(asl_totalworkload)
        return asl_totalworkload

    elif run_options == "Structural":
        struct_dict = get_structural_workload(analysis_dir, subjects, struct_dict)
        # pprint(struct_dict)
        struct_totalworkload = sum(struct_dict.values())
        print(struct_totalworkload)
        return struct_totalworkload

    elif run_options == "Population":
        pop_totalworkload = get_population_workload(analysis_dir)
        print(pop_totalworkload)
        return pop_totalworkload

    else:
        print("THIS SHOULD NEVER PRINT AS YOU HAVE SELECTED AN IMPOSSIBLE WORKLOAD OPTION")


class xASL_GUI_RerunPrep(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.parent = parent
        self.target_dir = self.parent.le_modjob.text()


