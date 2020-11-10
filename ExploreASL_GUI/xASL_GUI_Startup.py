from ExploreASL_GUI.xASL_GUI_MainWin import xASL_MainWin
from PySide2.QtWidgets import QApplication, QMessageBox, QWidget, QDialog
from PySide2.QtGui import QIcon
from platform import system
from shutil import which
from glob import glob
import os
import sys
import json
import subprocess
import re


def startup():
    app = QApplication(sys.argv)
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(scripts_dir)
    json_logic_dir = os.path.join(project_dir, "JSON_LOGIC")
    dcm2niix_dir = os.path.join(project_dir, "External", "DCM2NIIX")
    regex = re.compile("'(.*)'")
    # Get the appropriate default style based on the user's operating system
    if system() == "Windows":  # Windows
        app.setStyle("Fusion")
    elif system() == "Darwin":  # Mac
        app.setStyle("macintosh")
    elif system() == "Linux":  # Linux
        app.setStyle("Fusion")
    else:
        QMessageBox().warning(QWidget(),
                              "Unsupported Operating System",
                              f"The operating system identified as: {system()} "
                              f"is not compatible with this program. "
                              f"Please run this program on any of the following:\n"
                              f"- Windows 10\n-Mactintosh\n-Linux using Ubuntu Kernel",
                              QMessageBox.Ok)
        sys.exit(1)

    if not os.path.exists(json_logic_dir):
        QMessageBox().warning(QWidget(),
                              "No JSON_LOGIC directory found",
                              f"The program directory structure is compromised. No JSON_LOGIC directory was located"
                              f"in {project_dir}",
                              QMessageBox.Ok)
        sys.exit(1)

    # Get the screen credentials
    screen = app.primaryScreen()
    screen_size = screen.availableSize()

    # Check if the master config file exists; if it doesn't, the app will initialize one on the first startup
    if os.path.exists(os.path.join(json_logic_dir, "ExploreASL_GUI_masterconfig.json")):
        print("Loading masterconfig file.")
        with open(os.path.join(json_logic_dir, "ExploreASL_GUI_masterconfig.json")) as master_config_reader:
            master_config = json.load(master_config_reader)

        # Update the ProjectDir and ScriptsDir variables in the event the user moves the location of this folder
        # First, make sure the Startup.py is located in the ExploreASL_GUI folder
        if project_dir != master_config["ProjectDir"]:

            # Yell at the user in the event that they messed around with the folder naming scheme
            if os.path.basename(project_dir) != "ExploreASL_GUI":
                QMessageBox().warning(QWidget(),
                                      "Project structure compromised",
                                      f"The detected project root path: {project_dir}\n"
                                      f"is not the expected ExploreASL_GUI directory.\n"
                                      f"Please check if you have not renamed any folders or files.",
                                      QMessageBox.Ok)
                sys.exit(1)
            # Otherwise, if internal structure is still the same but the root is in a different location,
            # update accordingly
            else:
                master_config["ProjectDir"] = project_dir
                master_config["ScriptsDir"] = os.path.join(project_dir, "ExploreASL_GUI")

    # Otherwise, this is a first time startup and additional things need to be checked
    else:
        master_config = {"ExploreASLRoot": "",  # The filepath to the ExploreASL directory
                         "DefaultRootDir": project_dir,  # The default root for the navigator to watch from
                         "ScriptsDir": scripts_dir,  # The location of where this script is launched from
                         "ProjectDir": project_dir,  # The location of the ExploreASL_GUI main dir
                         "Platform": f"{system()}",
                         "ScreenSize": (screen_size.width(), screen_size.height()),  # Screen dimensions
                         "DeveloperMode": True  # Whether to launch the app in developer mode or not
                         }

        # We must also check for the MATLAB version present on the machine
        # Two common possibilities on Linux:
        # 1) the PATH registered is /usr/local/MATLAB/[VERSION]/bin
        # 2) the PATH registered is /usr/bin
        # Try option 1 first to get the version, opt for looking around /usr/local if Option 2 comes around
        print("First time startup. Please be patient as the matlab version is detected\n"
              "Attempting shutil method first")

        # Is matlab even on PATH?
        result = which("matlab")
        if result is not None:
            # If matlab was found on PATH, see if the version number can be extracted from it as per possibility #1
            # On Windows, this should always work. On Linux...*sigh*
            regex = re.compile(r".*R\d{4}[ab]")
            match = regex.search(result)
            if match:
                master_config["MATLABROOT"] = match.group()
                print(f"shutil method was a success and located: {match.group()}")

            # Not a success, see if the version number can be extracted from possibility #2
            elif not match and '/usr/' in result:
                version_is_located = False
                print(f"User clearly has the matlab command in {result}, but the version number could not be "
                      f"ascertained. Attempting to locate around '/usr/local/")
                for search_pattern in ["/usr/local/matlab**/bin", "/usr/local/**/MATLAB/*/bin"]:
                    local_result = glob(search_pattern, recursive=True)
                    if len(local_result) != 0:
                        local_match = regex.search(local_result[0])
                        if local_match:
                            master_config["MATLABROOT"] = local_match.group()
                            version_is_located = True
                            break

                if not version_is_located:
                    QMessageBox().warning(QWidget(),
                                          "No MATLAB Version could be determined",
                                          "MATLAB was detected on this system, but its location is unconventional\n"
                                          "and the version number could not be detected",
                                          QMessageBox.Ok)
                    sys.exit(1)

            # Neither a success with possibility #1 or #2
            else:
                QMessageBox.warning(QWidget(),
                                    "No MATLAB Version could be determined",
                                    "MATLAB was detected on this system, but its location is unconventional\n"
                                    "and the version number could not be detected",
                                    QMessageBox.Ok)
                sys.exit(1)

            # Assuming the above was successful, dcm2niix may not have executable permission; add execute permissions
            if system() == "Linux":
                print("Checking for execute permissions on dcm2niix")
                target = os.path.join(dcm2niix_dir, "DCM2NIIX_Linux", "dcm2niix")
                if not os.access(target, os.X_OK):
                    os.chmod(target, 0o775)
                    print("dcm2niix was modified to have execute permissions")
                else:
                    print("dcm2niix already had execute permissions. No changes made.")
                del target

        # Otherwise, try the old subprocess methods
        else:
            print("shutil method unsuccessful in locating a path. Attempting backup subprocess method")
            result = subprocess.run(["matlab", "-nosplash", "-nodesktop", "-batch", "matlabroot"],
                                    capture_output=True, text=True)
            if result.returncode == 0:
                match = regex.search(result.stdout)
                if match:
                    master_config["MATLABROOT"] = match.group(1)
                    print(f"subprocess method was a success and located: {match.group(1)}")
                else:
                    QMessageBox().warning(QWidget(),
                                          "No MATLAB directory found",
                                          "No path to the MATLAB root directory could be located on this device. "
                                          "If MATLAB is installed on this device and this message is displaying, "
                                          "please contact your system administration and check whether MATLAB is "
                                          "listed in your system's PATH variable.",
                                          QMessageBox.Ok)
                    sys.exit(1)
            else:
                QMessageBox().warning(QWidget(),
                                      "No MATLAB directory found",
                                      "No path to the MATLAB root directory could be located on this device. "
                                      "If MATLAB 2019 or later is installed on this device and this message is still "
                                      "displaying, please contact your system administration and check whether MATLAB"
                                      "is in your system's PATH variable. Otherwise, if your MATLAB version is not "
                                      "2019a or later, then this GUI is incompatible with your version of MATLAB",
                                      QMessageBox.Ok)
                sys.exit(1)

    # Memory cleanup
    del regex, dcm2niix_dir, json_logic_dir, project_dir

    # If all was successful, launch the GUI
    app.setWindowIcon(QIcon(os.path.join(master_config["ProjectDir"], "media", "ExploreASL_logo.ico")))
    os.chdir(scripts_dir)
    main_win = xASL_MainWin(master_config)
    main_win.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    startup()
