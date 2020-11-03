import subprocess as sp
from getpass import getpass
import os
import sys
from platform import system


def Linux_Uninstall():
    print("Implementing the Linux Install")
    print(f"The uninstaller was launched from {os.getcwd()}")

    # Get the root directory
    explore_asl_root = os.path.dirname(os.path.abspath(__file__))
    print(f"explore_asl_root = {explore_asl_root}\n")
    if os.path.basename(explore_asl_root) != "ExploreASL_GUI":
        print(f"The uninstaller was determined to no longer be located in the root ExploreASL_GUI folder.\n"
              f"Check if you have accidentally renamed the root folder.\n"
              f"Exiting process.")
        sys.exit(1)

    # Get rid of the .desktop file
    password = getpass("To remove the .desktop file from /usr/local/applications and all the ExploreASL_GUI "
                       "directories, your sudo password is required: ")
    proc = sp.Popen(f"sudo -S rm /usr/share/applications/ExploreASL_GUI.desktop; sudo rm -rf {explore_asl_root}",
                    shell=True, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE, universal_newlines=True)
    proc.communicate(password)
    print(f"Result code of removing the desktop file from /usr/local/applications: "
          f"{proc.returncode} (0 means successful)")
    if proc.returncode != 0:
        sys.exit(proc.returncode)
    else:
        print("ExploreASL_GUI has successfully uninstalled. Exiting.")
        sys.exit(0)


if __name__ == '__main__':
    if system() == "Linux":
        Linux_Uninstall()
    else:
        print("This install script is meant for use on a Linux machine")
        sys.exit(1)
