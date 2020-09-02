from ExploreASL_GUI.xASL_GUI_MainWin import xASL_MainWin
from PySide2.QtWidgets import *
import os
import sys
import json
import platform
import subprocess
import re

if __name__ == '__main__':
    app = QApplication(sys.argv)
    current_dir = os.getcwd()
    project_dir = current_dir
    json_logic_dir = os.path.join(current_dir, "JSON_LOGIC")
    scripts_dir = os.path.join(current_dir, "ExploreASL_GUI")

    regex = re.compile("'(.*)'")
    # Get the appropriate default style based on the user's operating system
    if platform.system() == "Windows":  # Windows
        app.setStyle("Fusion")
    elif platform.system() == "Darwin":  # Mac
        app.setStyle("macintosh")
    elif platform.system() == "Linux":  # Linux
        app.setStyle("Fusion")
    else:
        QMessageBox().warning(QWidget(),
                              "Unsupported Operating System",
                              f"The operating system identified as: {platform.system()} "
                              f"is not compatible with this program. "
                              f"Please run this program on any of the following:\n"
                              f"- Windows 10\n-Mactintosh\n-Linux using Ubuntu Kernel",
                              QMessageBox.Ok)
        sys.exit()

    if not os.path.exists(json_logic_dir):
        QMessageBox().warning(QWidget(),
                              "No JSON_LOGIC directory found",
                              f"The program directory structure is compromised. No JSON_LOGIC directory was located"
                              f"in {project_dir}",
                              QMessageBox.Ok)
        sys.exit()

    # Check if the master config file exists; if it doesn't, the app will initialize one on the first startup
    if os.path.exists(os.path.join(json_logic_dir, "ExploreASL_GUI_masterconfig.json")):
        with open(os.path.join(json_logic_dir, "ExploreASL_GUI_masterconfig.json")) as master_config_reader:
            master_config = json.load(master_config_reader)
    else:
        master_config = {"ExploreASLRoot": "",  # The filepath to the ExploreASL directory
                         "DefaultRootDir": current_dir,  # The default root for the navigator to watch from
                         "ScriptsDir": scripts_dir,  # The location of where this script is launched from
                         "ProjectDir": project_dir,  # The location of the ExploreASL_GUI main dir
                         "Platform": f"{platform.system()}",
                         "DeveloperMode": False  # Whether to launch the app in developer mode or not
                         }
        result = subprocess.run(["matlab", "-nosplash", "-nodesktop", "-batch", "matlabroot"],
                                capture_output=True, text=True)
        if result.returncode == 0:
            match = regex.search(result.stdout)
            if match:
                master_config["MATLABROOT"] = match.group(1)
            else:
                QMessageBox().warning(QWidget(),
                                      "No MATLAB directory found",
                                      "No path to the MATLAB root directory could be located on this device. "
                                      "If MATLAB is installed on this device and this message is displaying, "
                                      "please contact your system administration and check whether MATLAB is "
                                      "listed in your system's PATH variable.",
                                      QMessageBox.Ok)
                sys.exit()
        else:
            QMessageBox().warning(QWidget(),
                                  "No MATLAB directory found",
                                  "No path to the MATLAB root directory could be located on this device. "
                                  "If MATLAB is installed on this device and this message is displaying, "
                                  "please contact your system administration and check whether MATLAB is "
                                  "listed in your system's PATH variable.",
                                  QMessageBox.Ok)
            sys.exit()

    # Memory cleanup
    del regex, current_dir

    # If all was successful, launch the GUI
    os.chdir(scripts_dir)
    main_win = xASL_MainWin(master_config)
    main_win.show()
    sys.exit(app.exec_())