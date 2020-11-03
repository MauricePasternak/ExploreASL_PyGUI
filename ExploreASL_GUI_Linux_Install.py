import os
import sys
import subprocess as sp
from platform import system
from getpass import getpass


def Linux_Install():
    print("Implementing the Linux Install")
    print(f"The installer was launched from {os.getcwd()}")

    # Get the root directory
    explore_asl_root = os.path.dirname(os.path.abspath(__file__))
    print(f"explore_asl_root = {explore_asl_root}\n")
    if os.path.basename(explore_asl_root) != "ExploreASL_GUI":
        print(f"The installer was determined to no longer be located in the root ExploreASL_GUI folder.\n"
              f"Check if you have accidentally renamed the root folder.\n"
              f"Exiting process.")
        sys.exit(1)

    password = getpass("Before proceeding, this installation process requires your sudo password for "
                       "two essential steps:\n"
                       "1) To install any required dependencies (i.e. python3.8, pip3, python-wheel, etc.)\n"
                       "2) To allow your program to be launched as an application "
                       "(i.e. move a .desktop file to /usr/local/applications)\n"
                       "Please enter your sudo password: ")

    # Install dependencies as necessary
    dependency_commands = "sudo -S apt-get install python3.8 libpq-dev python3-dev python3-pip python3-venv python3-wheel && pip3 install wheel"
    dependency_proc = sp.Popen(dependency_commands, shell=True, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE)
    dependency_proc.communicate(password.encode())
    print(f"Return code of installing dependencies: {dependency_proc.returncode} (0 means successful)")
    if dependency_proc.returncode != 0:
        sys.exit(dependency_proc.returncode)

    # Make the venv directory if it does not exist
    if not os.path.isdir(os.path.join(explore_asl_root, "venv")):
        print("Making the venv directory...")
        os.mkdir(os.path.join(explore_asl_root, 'venv'))

    # Create the venv
    packages_path = os.path.join(explore_asl_root, "venv", "lib", "python3.8", "site-packages")
    if not os.path.exists(packages_path):
        venvcreate_result = sp.run(f"python3.8 -m venv {explore_asl_root}/venv; ", shell=True, text=True)
        print(f"Return code of creating a new environment: {venvcreate_result.returncode} (0 means successful)")
        if venvcreate_result.returncode != 0:
            sys.exit(venvcreate_result.returncode)
    else:
        print("Venv was already created. Continuing...")

    # Activate the venv, then install the packages
    bin_path = os.path.join(explore_asl_root, "venv", "bin")
    activate_command = f". {explore_asl_root}/venv/bin/activate"
    wheel_command = "pip3 install wheel"
    packages_install_command = f"pip3 install -r {explore_asl_root}/requirements.txt"
    if not os.path.isdir(bin_path):
        print("The venv/bin path does not exist!")
        sys.exit(1)
    if not os.path.isfile(os.path.join(explore_asl_root, "requirements.txt")):
        print(f"Could not find the requirements.txt file within {explore_asl_root}")
        sys.exit(1)
    if not os.path.exists(os.path.join(explore_asl_root, "venv", "lib", "python3.8", "site-packages", "nilearn")):
        venvactandinstall_result = sp.run(f"{activate_command} && {wheel_command} && {packages_install_command}",
                                          shell=True, text=True)
        print(f"Result code of activating the env and installing packages {venvactandinstall_result.returncode} "
              f"(0 means successful)")
        if venvactandinstall_result.returncode != 0:
            sys.exit(venvactandinstall_result.returncode)
    else:
        print("Packages already exist in venv site-packages. Continuing...")

    # Prepare the shell launcher
    shell_launcher = os.path.join(explore_asl_root, "xASL_GUI_run.sh")
    if not os.path.exists(shell_launcher):
        with open(shell_launcher, 'w') as shell_writer:
            to_write = f"""#!/bin/bash
. {explore_asl_root}/venv/bin/activate
cd {explore_asl_root}
python3.8 {explore_asl_root}/xASL_GUI_run.py
"""
            shell_writer.write(to_write)
        os.chmod(shell_launcher, 0o744)
    else:
        print(f"{shell_launcher} already exists. Continuing...")

    # Prepare the .desktop file
    desktop_file = os.path.join(explore_asl_root, "ExploreASL_GUI.desktop")
    if not os.path.exists(desktop_file):
        with open(desktop_file, "w") as desktop_writer:
            to_write = f"""[Desktop Entry]
Version=0.2.5
Name=ExploreASL_GUI
Comment=ExploreASL_GUI is an accompanying graphical user interface for ExploreASL workflows
Exec={shell_launcher}
Icon={explore_asl_root}/media/ExploreASL_logo.png
Terminal=false
Type=Application
Categories=Utility;Development;
"""
            desktop_writer.write(to_write)
    else:
        print(f"{desktop_file} already exists. Continuing...")

    # Move the .desktop file into /usr/share/applications
    proc = sp.Popen(f"sudo -S mv {desktop_file} /usr/share/applications/ExploreASL_GUI.desktop", shell=True,
                    stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE, universal_newlines=True)
    proc.communicate(password)
    print(f"Result code of moving the desktop file to /usr/local/applications: {proc.returncode} (0 means successful)")
    if proc.returncode != 0:
        sys.exit(proc.returncode)

    print("Installation complete. If you are seeing this message, everything should be a success")
    sys.exit(0)


if __name__ == '__main__':
    if system() == "Linux":
        Linux_Install()
    else:
        print("This installer script is meant for Linux systems")
        sys.exit(1)
