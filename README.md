# THIS REPOSITORY IS NO LONGER MAINTAINED [PLEASE VISIT THE NEW VERSION OF THE GUI HERE](https://github.com/MauricePasternak/ExploreASLJS)

# Explore ASL GUI

> Complementary GUI to assist Arterial Spin Labelling analysis by ExploreASL



---

[![License: LGPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
![Version](https://img.shields.io/badge/Version-0.2.9-yellow)
![PythonVersions](https://img.shields.io/badge/Python-3.8-green)

## Graphics and Examples

> Drag and Drop your variables of interest, then view the subject to which a datapoint corresponds!

![MRI_Viewer_movie](https://github.com/MauricePasternak/ExploreASL_GUI/blob/master/github_media/MRI_viewer.gif)

---
## Table of Contents
- [Installation](#installation)
- [Features](#features)
- [Team](#exploreasl-team)
- [Support](#support)
- [FAQ](#faq)
- [License](#license)

---
## Installation

### For Developers

Pre-requisites:

- Ensure both git, python3.8, and pip3 are present on your system.

- Linux developers may face some quirks with QT variables. In particular `"Could not load the Qt platform plugin "xcb" in "" even though it was found."` is a common error. The following dependencies are recommended to avoid some common quirks encountered:

      sudo apt-get install python3.8 git libxcb-xinerama0 libpq-dev build-dep python-matplotlib python3-dev python3-pip python3-venv python3-wheel && pip3 install wheel

Steps:

1) In your directory of choice, clone this github repository via command:

       git clone https://github.com/MauricePasternak/ExploreASL_GUI.git

   Alternatively, download the zip folder and extract it to your desired destination.

2) Via command line, enter the ExploreASL_GUI directory. Inside, create the necessary Python 3.8 virtual environment

       python3.8 -m venv venv

3) Install necessary packages via:

       pip3 install -r requirements.txt

4) Activate the virtual environment.**

   On Windows this is through:

       \venv\Scripts\activate.bat

   On Linux & macOS this is through:

       source venv/bin/activate

5) Run the main script via:

       python3.8 xASL_GUI_Run.py

**It is necessary to re-activate the virtual environment each time the shell originally activating it is shut down. [Windows](https://www.youtube.com/watch?v=APOPm01BVrk&ab_channel=CoreySchafer) or [Linux/macOS](https://www.youtube.com/watch?v=Kg1Yvry_Ydk&ab_channel=CoreySchafer) Users unfamiliar with Python virtual environments are advised to familiarize themselves with these concepts before following through with the above steps.

### For Non-developers

Starting with the upcoming version 0.2.9, releases for Windows, MacOS, and Linux will be posted in the [Releases](https://github.com/MauricePasternak/ExploreASL_GUI/releases) section of this respository.

---
## Features

### Main Widgets

The graphical user interface is split into 4 main modules existing as separate windows linked together by a central file explorer hub from which they can be launched:

![Image of MainWindow](https://github.com/MauricePasternak/ExploreASL_GUI/blob/master/github_media/Windows/MainWindow.png)

The first module most users will utilize is the Importer Module. The user defines the root directory of their dataset and which eventually contains dicom files at terminal directories within the folder structure. This module then converts the dicoms therein into nifti volumes within a BIDS-compliant data structure, [utilizing Chris Rorden's dcm2niix executable in the process](https://github.com/rordenlab/dcm2niix):

![Image of Importer](https://github.com/MauricePasternak/ExploreASL_GUI/blob/master/github_media/Windows/Importer.png)

Sometimes directories may have multiple pieces of information on the same directory level. An additional submodule, Folder Unpack, can pry apart such directories into their separate components. For example a directory level with syntax subject_visit may be expanded into SUBJECT/subject/VISIT/visit, where SUBJECT and VISIT may be user-specified parent folders containing all the described names (i.e. subjects, scans, etc.)

![Image of Dehybridizer](https://github.com/MauricePasternak/ExploreASL_GUI/blob/master/github_media/Windows/Dehybridizer.png)

The main ExploreASL program has over 55 adjustable parameters to account for ASL acquisition variability. Defining these parameters is simplified through the ParmsMaker Module and the resulting DataPar.json file is automatically saved to the indicated study directory. In addition, existing DataPar.json files can be re-loaded, edited, and then re-saved back into the study directory.

![Image of ParmsMaker](https://github.com/MauricePasternak/ExploreASL_GUI/blob/master/github_media/Windows/ParmsMaker.png)

Once data is imported and parameters defined, the user will be prepared to run the main program. The Executor Module allows for multi-processing analysis of multiple studies and/or multiple subjects per study simultaneously. The user is free to pause, resume, or terminate studies independently of one another. If errors occur, the module also creates a Run_Log file with a timestamp. Inside, relevant information taken from the ExploreASL program may help with diagnosing errors and bugs.

![Image of Executor](https://github.com/MauricePasternak/ExploreASL_GUI/blob/master/github_media/Windows/Executor.png)

Finally, with the data analyzed, the user may feel free to visualize the processed dataset. The Post Processing & Visualization Module allows for users to interactively drag & drop all loaded data to generate publication-quality plots and load in both functional & structural MRI scans based on user clicks on specific datapoints.

![Image of PostProc](https://github.com/MauricePasternak/ExploreASL_GUI/blob/master/github_media/Windows/PostProc.png)

### Modification Jobs

Multiple modification jobs are avaliable to allow or re-runs, tweaks prior to a re-run, or otherwise assistance with meta-analysis between studies.

Progress in ExploreASL is handled through the creation of .status files that indicate the completion of critical steps. This GUI eases the user specification of .status files to remove, allowing only those particular steps to be repeated.

![Image of Modjob Rerun](https://github.com/MauricePasternak/ExploreASL_GUI/blob/master/github_media/Windows/Modjob_Rerun.png)

Users may wish to include additional covariates during the creation of biasfields when the Population Module is re-run. An SQL-like one-sided merge is performed that allows automatic & hassle-free addition of thousands of rows of metadata as opposed to careful user copy & pasting.

![Image of Modjob AlterTSV](https://github.com/MauricePasternak/ExploreASL_GUI/blob/master/github_media/Windows/Modjob_AlterTSV.png)

Although the DICOM --> NIFTI import process covers most expected ASL flavors, it is feasible that certain subjects & scans may require very specific settings indicated in the JSON files corresponding to each image volume. It is possible to specify which JSONs require specific key-value pairs to be introduced either through user drag & dropping of subject directories or through a comma-separated-values configuration file.

Finally, with the data analyzed, the user may feel free to visualize the processed dataset. The Post Processing & Visualization Module allows for users to interactively drag & drop all loaded data to generate publication-quality plots and load in both functional & structural MRI scans based on user clicks on specific datapoints.

![Image of Modjob ModJSONSidecars](https://github.com/MauricePasternak/ExploreASL_GUI/blob/master/github_media/Windows/Modjob_ModJSONSidecars.png)

Users may with to which to merge multiple analysis directories (i.e. to perform the Population Module for meta-analysis purposes). To avoid the tedious task of copy-pasting potentially thousands of files and directories, the GUI can accomplish this with the user only needing to specify the destination and the directories to merge. Symlinks are supported to save disk space.

![Image of Modjob MergeDirs](https://github.com/MauricePasternak/ExploreASL_GUI/blob/master/github_media/Windows/Modjob_MergeDirs.png)

From start to finish, this GUI is designed to streamline the processing and eventual publication of arterial spin labelling image data.

This program is intended solely for research purposes and **should not** be used in any way, shape, or form for clinical application or in a clinical setting.

---
## Creator

For more information on the GUI, troubleshooting, and suggestions for improvements, please don't hesitate to contact:
- Maurice Pasternak; maurice.pasternak@utoronto.ca

---
## ExploreASL Team

For questions or concerns with the underlying ExploreASL program, the following individuals compromise the development team and may be contacted:

- Henk-Jan Mutsaerts; HenkJanMutsaerts@Gmail.com (ExploreASL creator)
- Jan Petr; j.petr@hzdr.de (ExploreASL creator)
- Michael Stritt; stritt.michael@gmail.com
- Paul Groot; p.f.c.groot@amsterdamumc.nl
- Pieter Vandemaele; pieter.vandemaele@gmail.com
- Maurice Pasternak; maurice.pasternak@utoronto.ca
- Luigi Lorenzini; l.lorenzini@amsterdamumc.nl
- Sandeep Ganji; Sandeep.g.bio@gmail.com

---
## Support

For GUI-related questions, please don't hesitate to drop an email at: maurice.pasternak@utoronto.ca

For more information on the main program, click on the following: [CLICK ME!](https://sites.google.com/view/exploreasl)

For the Github page of main program that this GUI interfaces with, click on the following: [CLICK ME!](https://github.com/ExploreASL/ExploreASL)

---
## FAQ

### About the GUI

> **Q: What operating systems is your program compatible with?**

A: The underlying toolkit utilized in the creation of this program is PySide2, a Python wrapper around the cross-platform C++ software Qt. As such, the program should be compatible with the most common operating systems, including:
- Windows 10
- Mac OS X: 10.14 (Mojave), 10.15 (Catalina), and 10.16 (BigSur)
- Linux 20.04 LTS (tested; earlier versions such as 18.04 may be unstable)

> **Q: Do I need MATLAB in order to run this program?**

A: In certain cases, you do not need a full installation. Instead, you'd require a smaller MATLAB Runtime (2019A), and the compiled ExploreASL program. At the time of this version (0.2.9 pre-release), the compiled ExploreASL versions only exist for:
- Windows 10
- Linux 20.04 LTS

> **Q: Does the GUI support running Docker images at the current time?**

A: No. But this is now in the works as a feature to be added in.

> **Q: The number of cores listed in your Executor module is off. My machine has ___ cores but you list ___ instead.**

A: This is primarily an issue on older and/or lower-binned CPUs that do not have hyper-threading (Intel) or simultaneous multi-threading (AMD) enabled, as the GUI follows the old adage "better safe than sorry". The number of available logical cores available is divided by a factor of 2. For CPUs with hyperthreading, this is a non-issue, as the resulting number will be equal to the number of physical cores. This is acceptable because the foundation behind ExploreASL - SPM12, is itself capable of utilizing both logical cores within each assigned physical core. For machines within these threading technologies, the factor-of-2 reduction will only allow usage of half the physical cores. Again, this provides additional safety that the user's machine will unlikely crash due to workload.

> **Q: What are the recommended system requirements for this GUI?**

A: Most functionality apart from Executor does not require immense resources. Running in a multi-processing manner with the Executor Module, on the other hand, should be used with the following guidelines:
- 3.5 GB of RAM per active core allocated towards a study. **DO NOT** allocate too many cores towards a study/studies if your RAM capacity is insufficient. The program will become slow and unresponsive, as your computer will run out of memory.
- An acceptable cooler for your CPU, as it will be going at it for ~15 minutes per single subject visit at "High" quality setting for both Structural and ASL modules. For a study of 120 visits split among all cores in a 6-core machine, that amounts to ~5 hours of heavy workload. Assuming the user wishes to utilize their machine to the fullest extent without overheating, a recommended top-end air-cooler is the [NH-D15 Chromax Black](https://noctua.at/en/nh-d15-chromax-black) for 6-16 physical core CPUs.
- As file writing/reading occurs in the course of the analysis, having an SSD or NVMe-SSD over a traditional hard drive can allow for reduced processing time.

### Within-GUI questions

> **Q: My study directory exists, and the DataPar.json file is formatted correctly within it. The run button is still greyed-out for some reason.**

A: The following are common reasons why this may be happening:
- You have selected the Population module to run in one of the studies and allocated more than 1 core towards that study. At the current time, the Population module supports only one processor core being assigned to it.
- You have allocated more cores to the study than there are runnable subjects. For example, it makes no sense to allocate 12 processor cores towards a study with only 10 subjects, as 2 cores will essentially be left hanging. This is especially common when users attempt to run the TestDataSet which features only 1 subject.

> **Q: I did not have MATLAB ready when I first booted up the GUI, so it couldn't detect the MATLAB version. I now have MATLAB on my computer. How can I have the GUI recognize this change?**

A: In the main window's menu, you'll find File --> Specify path to MATLAB executable. The program will prompt the user for the filepath to the matlab command. The following are common places to look for the matlab command:
- On Windows; C:\Program Files\MATLAB\\{MATLAB_VERSION}\bin
- On MacOS; /Applications/MATAB_{MATLAB_VERSION}.app/bin
- On Linux; /usr/local/MATLAB/bin

> **Q: I have more than one MATLAB installation on my machine, and on startup the GUI registered the version I don't want used for analysis. How can I make it use the version I want?**

A: Use the main window's menu: File --> Specify path to MATLAB executable. The program will prompt the user for the filepath to the matlab command. Go far enough into the folder structure such that `R####a` or `R####b` (where #### is the release year of the version, such as 2019) is indicated in the filepath. That version will be specifically re-registered for use by the GUI.

> **Q: I have a formidable computer with dozens of cores, and I got a Segmentation Violation Detected error in the "ExploreASL run - errors.txt" file. What does this mean?**

A: It's not a fault of the GUI or ExploreASL itself. It's a fault of MATLAB and how its glnax64 library plays with the current kernel/version of your operating system, leading to a crash when a significant number of cores are used for an extended period of time. You can simply press "Run ExploreASL" again. The program will pick up approximately from where it left off thanks to the .status file system.

> **Q: Is it safe to stop a study being run?**

A: No, the type of termination done here is a full-stop termination. Although unlikely, it is possible that the processing is killed in the middle of a crucial file transfer operation, thereby corrupting NIFTI images. If you are forced to terminate a study at anything other than the first few seconds grace period, it is advisable to consider the data potentially compromised.

> **Q: Is it safe to pause a study being run?**

A: Unlike termination, pausing studies should be safe. The program will simply pick off where it paused when the user chooses to resume programming.

---

## License

[![License: LGPL v3](https://img.shields.io/badge/License-LGPLv3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)

- **[LGPL license](https://www.gnu.org/licenses/lgpl-3.0-standalone.html)**
