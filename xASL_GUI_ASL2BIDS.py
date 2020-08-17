import os
import shutil
import random
import subprocess
from glob import glob
from nipype.interfaces.dcm2nii import Dcm2niix
from pprint import pprint
from nilearn import image
import nibabel as nib
import pydicom
import json
import re
import sys


def get_dicom_directories(config: dict):
    """
    Convenience function for globbing the dicom directories from the config file
    :param config: the configuration file that specifies the directory structure
    :return: dcm_firs: the list of filepaths to directories containing the dicom files
    """
    raw_dir = config["RawDir"]
    n_levels = ["*"] * len(config["Directory Structure"])
    dcm_dirs = glob(os.path.join(raw_dir, *n_levels))
    return dcm_dirs


def get_manufacturer(dcm_dir: str):
    """
    Returns the string suggesting which manufacturer the dicoms in the provided dicom directory belong to.
    :param dcm_dir: the absolute path to the directory containing the dicoms to be converted.
    :return: returns the string "Siemens", "Philips", or "GE". Otherwise returns None.
    """
    dcm_files = [item for item in glob(os.path.join(dcm_dir, "*.dcm"))]
    if len(dcm_files) == 0:
        return None

    dcm_data = pydicom.read_file(dcm_files[0])
    detected_manufac = []
    manufac_tags = [(0x0008, 0x0070), (0x0019, 0x0010)]
    for tag in manufac_tags:
        try:
            detected_manufac.append(f"{dcm_data[tag].value}".upper())
        except KeyError:
            detected_manufac.append("")

    if any(["SIEMENS" in result for result in detected_manufac]):
        return "Siemens"
    elif any(["PHILIPS" in result for result in detected_manufac]):
        return "Philips"
    elif any(["GE" in result for result in detected_manufac]):
        return "GE"
    else:
        return


def get_dicom_value(data: pydicom.Dataset, tags: list, default=None):
    """
    Convenience function for retrieving the value of a dicom tag. Otherwise, returns the indicated default
    :param data: the dicom data as a Pydicom Dataset
    :param tags: a list of tuples, each tuple usually being 2 elements (0x####, 0x####). 4 element tuples are used
    to delve into nested dicom structures
    :param default: the default value to return if nothing can be found
    :return: value: the first valid value associated with the tag
    """
    detected_values = []
    for tag in tags:
        # For tags that are nested
        if len(tag) == 4:
            try:
                detected_values.append(f"{data[tag[0:2]][0][tag[3:]].value}")
            except KeyError:
                detected_values.append(None)
        # For base level tags
        else:
            try:
                detected_values.append(f"{data[tag].value}")
            except KeyError:
                detected_values.append(None)

    for value in detected_values:
        if value is not None:
            if isinstance(value, str):
                if value.isdigit():
                    return float(value)
            return value

    return default


def get_additional_dicom_parms(dcm_dir: str):
    """
    Retrieves some additional important dicom headers that dcm2niix may not capture and which may be important for
    processing
    :param dcm_dir: absolute path to the dicom directory, where the first dicom will be used to determine parameters
    :return: additional_dcm_info: a dict of the additional parameters as keys and their values as the dict values.
    """

    dcm_files = [item for item in glob(os.path.join(dcm_dir, "*.dcm"))]
    if len(dcm_files) == 0:
        return None

    dcm_data = pydicom.read_file(dcm_files[0])
    tags_dict = {"AcquisitionMatrix": [(0x0018, 0x1310)],
                 "NumberOfAverages": [(0x0018, 0x0083)],
                 "RescaleSlope": [(0x0028, 0x1053), (0x2005, 0x110A)],
                 "RescaleIntercept": [(0x0028, 0x1052)],
                 "MRScaleSlope": [(0x2005, 0x120E), (0x2005, 0x100E)],
                 "SpectrallySelectedSuppression": [(0x2005, 0x110F, 0x0018, 0x9025)]
                 }
    additional_dcm_info = {}
    for (key, value), default in zip(tags_dict.items(), [None, 1, 1, 0, 1, None]):
        result = get_dicom_value(dcm_data, value, default)

        # Additional processing for specific keys
        if key == "AcquisitionMatrix" and result is not None:
            result = result.strip('[]').split(", ")[0]
            result = int(result)

        additional_dcm_info[key] = result

    return additional_dcm_info


def get_structure_components(dcm_dir: str, config: dict):
    """
    Returns the essential subject, session, and scan names of the currently-assessed dicom directory.
    :param dcm_dir: the absolute path to the directory containing the dicoms to be converted
    :param config: a dict with essentials details the raw directory structure and mappings of aliases
    :return: returns the current subject, session, and scan names in their alias form
    """
    subject, session, scan = None, None, None
    dirname = dcm_dir
    for dir_type in reversed(config["Directory Structure"]):
        if dir_type == "Subject":
            dirname, basename = os.path.split(dirname)
            subject = basename
        elif dir_type == "Session":
            dirname, basename = os.path.split(dirname)
            session = basename
        elif dir_type == "Scan":
            dirname, basename = os.path.split(dirname)
            scan = basename
        else:
            dirname, _ = os.path.split(dirname)

    scan_translator = {value: key for key, value in config["Scan Aliases"].items()}
    scan_dst_name = scan_translator[scan]

    if session is not None:
        session_translator = config["Ordered Session Aliases"]
        session_dst_name = session_translator[session]
    else:
        session_dst_name = None

    return subject, session_dst_name, scan_dst_name


def get_dst_dirname(raw_dir: str, subject: str, session: str, scan: str):
    """
    Creates the essential destination directory for nifti and json files to be created in during the conversion process
    :param raw_dir: the absolute path to the raw folder directory
    :param subject: the string representing the current subject
    :param session: the string representing the current session
    :param scan: the string representing the scan. Is either ASL4D, T1, M0, FLAIR, or WMH_SEGM
    :return: a string representation of the output directory for dcm2niix to create nifti files in
    """
    analysis_dir = os.path.join(os.path.dirname(raw_dir), "analysis")
    if session is None:
        if scan not in ["T1", "FLAIR", "WHM_SEGM"]:
            dst_dir = os.path.join(analysis_dir, subject, "perf", "TEMP")
        else:
            dst_dir = os.path.join(analysis_dir, subject, "anat", "TEMP")
    else:
        if scan != ["T1", "FLAIR", "WHM_SEGM"]:
            dst_dir = os.path.join(analysis_dir, subject, session, "perf", "TEMP")
        else:
            dst_dir = os.path.join(analysis_dir, subject, session, "anat", "TEMP")

    os.makedirs(dst_dir, exist_ok=True)
    return dst_dir


def run_dcm2niix(temp_dir: str, dcm_dir: str, subject: str, session, scan: str):
    """
    Runs the dcm2niix program as a subprocess and generates the appropriate nifti and json files
    :param temp_dir: the TEMP dst where nifti and json files will be deposited
    :param dcm_dir: the directory where the dicoms of interest are being held
    :param subject: the string representing the current subject
    :param session: the string representing the current session alias
    :param scan: the string representing the scan. It is either ASL4D, T1, M0, FLAIR, or WMH_SEGM
    :return status: whether the operation was a success or not
    """
    if session is None:
        output_filename_format = f"{subject}_{scan}_%s"
    else:
        output_filename_format = f"{subject}_{session}_{scan}_%s"

    # Must ensure that no files currently exist within the destination
    try:
        if len(os.listdir(temp_dir)) > 0:
            for path in os.listdir(temp_dir):
                fullpath = os.path.join(temp_dir, path)
                if os.path.isfile(fullpath):
                    os.remove(fullpath)
                elif os.path.isdir(fullpath):
                    os.removedirs(fullpath)
                else:
                    continue
    except FileNotFoundError:
        return False

    # Prepare and run the converter
    converter = Dcm2niix()
    converter.inputs.source_dir = dcm_dir
    converter.inputs.output_dir = temp_dir
    converter.inputs.compress = "n"
    converter.inputs.out_filename = output_filename_format
    return_code = subprocess.run(converter.cmdline.split(" "))
    print(f"Return code: {return_code.returncode}")
    if return_code.returncode == 0:
        return True
    else:
        return False


def clean_niftis_in_temp(temp_dir: str, subject: str, session: str, scan: str):
    """
    Concatenates the niftis, deletes the previous ones, and moves the concatenated one out of the temp dir
    :param temp_dir: the absolute filepath to the TEMP directory where the niftis are present
    :param subject: the string representing the current subject
    :param session: the string representing the current session alias
    :param scan: the string representing the scan. It is either ASL4D, T1, M0, FLAIR, or WMH_SEGM
    :return: status: whether the operation was a success or not; the import summary parameters, and the filepath to the
    new nifti created
    """
    niftis = glob(os.path.join(temp_dir, "*.nii"))
    regex = re.compile(r"(_(\d+).nii)")
    reorganized_niftis = []
    # Must rename the niftis to zero_pad the end to avoid bad concatenation
    for starting_nifti in niftis:
        match = regex.search(starting_nifti)
        if not match:
            continue
        series_ending, series_number = match.groups()
        padded_series_number = series_number.zfill(3)
        padded_series_ending = series_ending.replace(series_number, padded_series_number)
        padded_nifti = starting_nifti.replace(series_ending, padded_series_ending)
        if not os.path.exists(padded_nifti):
            os.replace(starting_nifti, padded_nifti)
        reorganized_niftis.append(padded_nifti)

    # In case they were not sorted before, sort them now
    reorganized_niftis = sorted(reorganized_niftis, key=lambda x: regex.search(x).group(1))

    # Prep the import summary data
    import_summary = dict.fromkeys(["subject", "visit", "session", "scan", "filename",
                                    "dx", "dy", "dz", "nx", "ny", "nz", "nt"])

    # Must process niftis differently depending on the scan and the number present after conversion
    # Scenario: ASL4D
    if len(reorganized_niftis) > 1 and scan == "ASL4D":
        nii_objs = [nib.load(nifti) for nifti in reorganized_niftis]
        final_nifti_obj = nib.funcs.concat_images(nii_objs)
        print(final_nifti_obj.header.get_zooms())
        print(final_nifti_obj.shape)

    # Scenario: multiple M0; will take their mean as final
    elif len(reorganized_niftis) > 1 and scan == "M0":
        nii_objs = [nib.load(nifti) for nifti in reorganized_niftis]
        final_nifti_obj = image.mean_img(nii_objs)

    # Scenario: single M0
    elif len(reorganized_niftis) == 1 and scan == "M0":
        final_nifti_obj = nib.load(reorganized_niftis[0])

    # Scenario: one of the structural types
    elif len(reorganized_niftis) == 1 and scan in ["T1", "FLAIR", "WMH_SEGM"]:
        final_nifti_obj = nib.load(reorganized_niftis[0])

    # Otherwise, something went wrong and the operation should stop
    else:
        return False, import_summary

    # Take the oppurtunity to get more givens for the import summary
    zooms = final_nifti_obj.header.get_zooms()
    shape = final_nifti_obj.shape
    import_summary["subject"], import_summary["session"], import_summary["scan"] = subject, session, scan
    import_summary["filename"] = scan + ".nii"

    if len(zooms) == 4:
        import_summary["dx"], import_summary["dy"], import_summary["dz"] = zooms[0:3]
    else:
        import_summary["dx"], import_summary["dy"], import_summary["dz"] = zooms

    if len(shape) == 4:
        import_summary["nx"], import_summary["ny"], \
        import_summary["nz"], import_summary["nt"] = shape
    else:
        import_summary["nx"], import_summary["ny"], \
        import_summary["nz"], import_summary["nt"] = shape[0], shape[1], shape[2], 1

    # Different action depending on whether there is a session-level directory or not
    if session is not None:
        final_nifti_filename = os.path.join(os.path.dirname(temp_dir), f"{subject}_{session}_{scan}.nii")
    else:
        final_nifti_filename = os.path.join(os.path.dirname(temp_dir), f"{subject}_{scan}.nii")
    nib.save(final_nifti_obj, final_nifti_filename)
    return True, import_summary, final_nifti_filename


def clean_jsons_in_temp(temp_dir: str, subject: str, session: str, scan: str):
    """
    Concatenates the niftis, deletes the previous ones, and moves the concatenated one out of the temp dir
    :param temp_dir: the absolute filepath to the TEMP directory where the niftis are present
    :param subject: the string representing the current subject
    :param session: the string representing the current session alias
    :param scan: the string representing the scan. It is either ASL4D, T1, M0, FLAIR, or WMH_SEGM
    :return: status: whether the operation was a success or not; filepath to the final json created
    """
    jsons = glob(os.path.join(temp_dir, "*.json"))
    if len(jsons) == 0:
        return False, None
    if session is not None:
        final_json_filename = os.path.join(os.path.dirname(temp_dir), f"{subject}_{session}_{scan}.json")
    else:
        final_json_filename = os.path.join(os.path.dirname(temp_dir), f"{subject}_{scan}.json")
    try:
        os.rename(jsons[0], final_json_filename)
    except FileExistsError:
        os.replace(jsons[0], final_json_filename)

    return True, final_json_filename


def update_json_sidecar(json_file: str, dcm_parms: dict):
    """
    Updates the json sidecar for ASL4D and M0 scans to include additional DICOM parameters not extracted by dcm2niix
    :param json_file: the absolute filepath to the json sidecar
    :param dcm_parms: a dict of the additional extracted DICOM headers that should be added to the json
    :return: status: whether the operation was a success or not
    """
    with open(json_file) as reader:
        parms: dict = json.load(reader)

    parms.update(dcm_parms)

    with open(json_file, 'w') as w:
        json.dump(parms, w, indent=3)

    return True


def asl2bids(config: dict):
    """
    The main function wrapping all functionality. Provided a config file, all dicoms from the raw directory will be
    imported into ASL-BIDS format.
    :param config: the configuration file containing the essential parameters for importing
    :return: status: whether the operation was a success or not
    """
    # Get the directories
    dcm_directories = get_dicom_directories(config=config)

    for dcm_dir in dcm_directories:
        # Get the subject, session, and scan for that directory
        subject, session, scan = get_structure_components(dcm_dir=dcm_dir, config=config)

        # Retrieve the additional DICOM parameters
        addtional_dcm_parms = get_additional_dicom_parms(dcm_dir=dcm_dir)

        # Generate the directories for dumping dcm2niix output
        temp_dst_dir = get_dst_dirname(raw_dir=config["RawDir"], subject=subject, session=session, scan=scan)

        # Run the main program
        successful_run = run_dcm2niix(temp_dir=temp_dst_dir, dcm_dir=dcm_dir,
                                      subject=subject, session=session, scan=scan)
        if not successful_run:
            print(f"FAILURE ENCOUNTERED AT THE DCM2NIIX STEP")
            continue

        # Clean the niftis in the TEMP directory
        successful_run, nifti_parms, nifti_filepath = clean_niftis_in_temp(temp_dir=temp_dst_dir, subject=subject,
                                                                           session=session, scan=scan)
        if not successful_run:
            print(f"FAILURE ENCOUNTERED AT CLEANING THE NIFTIs IN THE TEMP FOLDER")
            continue

        # Clean the jsons in the TEMP directory
        successful_run, json_filepath = clean_jsons_in_temp(temp_dir=temp_dst_dir, subject=subject, session=session,
                                                            scan=scan)
        if not successful_run:
            print(f"FAILURE ENCOUNTERED AT CLEANING THE JSONS IN THE TEMP FOLDER")
            continue

        # For ASL4D and M0 scans, the JSON sidecar from dcm2niix must include additional parameters
        successful_run = update_json_sidecar(json_file=json_filepath, dcm_parms=addtional_dcm_parms)
        if not successful_run:
            print(f"FAILURE ENCOUNTERED AT CORRECTION THE JSON SIDECAR STEP")
            continue

        # Finally, delete the TEMP folder
        shutil.rmtree(temp_dst_dir, ignore_errors=True)

if __name__ == '__main__':
    with open(r'C:\Users\Maurice\Documents\GENFI\3D_Mace\raw\ImportConfig.json') as f:
        import_config = json.load(f)

    dicom_directory = r'C:\Users\Maurice\Documents\GENFI\3D_Mace\raw\C9ORF003_11\ASL'
    raw_directory = r'C:\Users\Maurice\Documents\GENFI\3D_Mace\raw'
    path_to_exe = r'C:\Users\Maurice\dcm2niix.exe'
    sys.path.append(path_to_exe)
    summary = {}


    asl2bids(import_config)

