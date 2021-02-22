import json
from os import cpu_count, environ
from itertools import chain
from time import sleep
from datetime import datetime
from more_itertools import peekable
from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from src.xASL_GUI_HelperClasses import DandD_FileExplorer2LineEdit
from src.xASL_GUI_Executor_ancillary import *
from src.xASL_GUI_AnimationClasses import xASL_ImagePlayer
from src.xASL_GUI_Executor_Modjobs import (xASL_GUI_RerunPrep, xASL_GUI_TSValter,
                                           xASL_GUI_ModSidecars, xASL_GUI_MergeDirs)
from src.xASL_GUI_HelperFuncs_WidgetFuncs import (set_widget_icon, make_droppable_clearable_le, set_formlay_options,
                                                  robust_qmsg, robust_getdir)
from pprint import pprint
from collections import defaultdict
import subprocess
from shutil import rmtree, which
from pathlib import Path
from functools import partial
from platform import system
import signal
from psutil import Process, NoSuchProcess, wait_procs, Popen
import re
import logging


class ExploreASL_WorkerSignals(QObject):
    """
    Class for handling the signals sent by an ExploreASL worker
    """
    started_processing = Signal()
    finished_processing = Signal()  # Signal sent by worker to watcher to help indicate it when to stop watching
    stdout_processing_error = Signal(dict)  # Signal sent by a worker to update the main stdout errors dict
    stderr_processing_error = Signal(dict)  # Signal sent by a worker to update the main stderr errors dict
    encountered_fatal_error = Signal()  # Signal sent by worker to raise a dialogue informing the user of an error

    received_pause = Signal(str)  # Signal sent by a worker to inform the textoutput that it has been paused
    received_resume = Signal(str)  # Signal sent by a worker to inform the textoutput that it has resumed


class ExploreASL_Worker(QRunnable):
    """
    Worker thread for running lauching an ExploreASL MATLAB session with the given arguments
    """

    def __init__(self, worker_parms, iworker, nworkers, imodules, worker_env):
        super().__init__()
        # Main Attributes
        self.worker_parms: dict = worker_parms
        self.easl_scenario = self.worker_parms["EXPLOREASL_TYPE"]
        self.analysis_dir: str = self.worker_parms["D"]["ROOT"].rstrip("/\\")
        self.par_path = str(next(Path(self.analysis_dir).glob("DataPar*.json")))
        self.iworker = iworker
        self.nworkers = nworkers
        self.imodules = imodules
        self.worker_env = worker_env

        # Control Attributes
        self.terminate_attempted = False
        self.is_paused = False
        self.proc_gone, self.proc_alive = [], []

        # Parsing Attributes
        self.regex_errstart = re.compile(r"ERROR: Job iteration terminated!")
        self.regex_errend = re.compile(r"CONT: but continue with next iteration!")
        self.regex_findtarget = re.compile(r"ASL_module_(ASL|Structural|Population)"
                                           r"(?:%%%([^#%&{}\\<>*?/$!'\":@+`|=]+))?"
                                           r"(?:%%%([^#%&{}\\<>*?/$!'\":@+`|=]+))?\b")
        self.is_collecting_stdout_err = False
        self.detected_errs = []

        # Set up the Logging-related Attributes
        try:
            study_name: str = self.worker_parms["name"]
        except KeyError:
            study_name: str = f"Unspecified Study Name"
        self.logger = logging.Logger(name=study_name, level=logging.DEBUG)
        basename = f"tmp_RunWorker_{str(self.iworker).zfill(3)}.log"
        self.handler = logging.FileHandler(filename=Path(self.par_path).parent / basename, mode='w')
        self.handler.setFormatter(logging.Formatter(fmt="%(asctime)s - %(name)s - %(levelname)s\n%(message)s"))
        self.handler.setLevel(logging.DEBUG)
        self.logger.addHandler(self.handler)

        # Other Worker Attributes
        self.signals = ExploreASL_WorkerSignals()
        self.is_running = False
        self.print_and_log(f"%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n"
                           f"Initialized Worker with the following givens:\n"
                           f"\tExploreASL Type: {self.easl_scenario}\n"
                           f"\tDataPar Path: {self.par_path}\n"
                           f"\tIWorker: {self.iworker}\n"
                           f"\tNWorkers: {self.nworkers}\n"
                           f"\tIModules: {self.imodules}", msg_type="info")

    # noinspection RegExpRedundantEscape
    def run(self):
        ##################################################
        # PREPARE ARGUMENTS AND RUN THE UNDERLYING PROGRAM
        ##################################################
        self.print_and_log(f"Worker {self.iworker}: Beginning Run", msg_type="info")
        self.print_and_log(f"Worker {self.iworker}: ExploreASL Type = {self.easl_scenario}", msg_type="info")
        if self.easl_scenario == "LOCAL_UNCOMPILED":
            mpath = self.worker_parms["WORKER_MATLAB_CMD_PATH"]
            exploreasl_path = self.worker_parms["MyPath"]
            process_data = 1
            skip_pause = 1

            # Generate the string that the command line will feed into the complied MATLAB session
            func_line = f"('{self.par_path}', {process_data}, {skip_pause}, {self.iworker}, {self.nworkers}, " \
                        f"[{' '.join([str(item) for item in self.imodules])}])"
            matlab_cmd = "matlab" if which("matlab") is not None else mpath
            if self.worker_parms["WORKER_MATLAB_VER"] >= 2019:
                cmd_path = [f"{matlab_cmd}",
                            "-nodesktop",
                            "-nosplash",
                            "-batch",
                            f"cd('{exploreasl_path}'); ExploreASL_Master{func_line}; exit"]
            else:
                cmd_path = [f"{matlab_cmd}",
                            "-nosplash",
                            "-nodisplay",
                            "-r",
                            f"cd('{exploreasl_path}'); ExploreASL_Master{func_line}; exit"]

            # Prepare the Subprocess
            self.print_and_log(f"Worker {self.iworker}: Preparing subprocess with the following commands:\n"
                               f"{cmd_path}", msg_type="info")
            self.proc = Popen(cmd_path, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        elif self.easl_scenario == "LOCAL_COMPILED":
            process_data = 1
            skip_pause = 1
            compiled_easl_path = self.worker_parms["MyPath"]

            # Generate the string that the command line will feed into the complied MATLAB session
            func_line = f"{self.par_path} {process_data} {skip_pause} {self.iworker} {self.nworkers} " \
                        f"[{' '.join([str(item) for item in self.imodules])}])"

            # Command Line format and launch script extension differs between operating systems
            glob_pat = "*.sh" if system() in ["Linux", "Darwin"] else "*.exe"
            matlab_runtime_path = f" {self.worker_parms['MCRPath']}" if system() in ["Linux", "Darwin"] else ""

            # Ensure the easl launch script actually has executable permissions
            compiled_easl_script = next(Path(compiled_easl_path).glob(glob_pat))
            compiled_easl_script.chmod(0o775)
            compiled_easl_script = str(compiled_easl_script)

            # Off it goes
            cmd_line = f"{compiled_easl_script} {matlab_runtime_path} {func_line}"
            self.print_and_log(f"Worker {self.iworker}: Preparing subprocess with the following commands:\n"
                               f"{cmd_line}", msg_type="info")
            self.proc = Popen(cmd_line, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              env=self.worker_env)
        else:
            pass

        # TODO When ExploreASL given a good latch-on point, the worker can switch to listening in on errors from the
        #  STDOUT stream of ExploreASL
        err_container, module, subject, run, n_collected = [], None, None, None, 0
        while True:
            output = self.proc.stdout.readline()

            # Break out once the process has finished or been killed
            if output == '' and self.proc.poll() is not None:
                break

            # If there is no relevant output but the process is still alive, try to minimize workload intensivity
            if not output:
                sleep(0.5)
                continue

            # Otherwise, different regexes are applied to understand what is happening
            # If the line defines a new target
            output = output.strip()
            if self.regex_findtarget.search(output):
                module, subject, run = self.regex_findtarget.search(output).groups()

            # If the line is the start of an error message, activate collecting mode
            elif self.regex_errstart.search(output):
                self.is_collecting_stdout_err = True

            # If the line is the end of an error message or too many lines have been collected, log the error and
            # reset things

            elif self.regex_errend.search(output) or n_collected > 50:
                msg = '\n'.join(err_container)
                if module == "Population":
                    self.print_and_log(f"Worker {self.iworker} detected an error "
                                       f"in the Population Module:\n{msg}")
                elif module == "Structural":
                    self.print_and_log(f"Worker {self.iworker} detected an error for Subject {subject} "
                                       f"in the Structural Module:\n{msg}")
                elif module == "ASL":
                    self.print_and_log(f"Worker {self.iworker} detected an error for Subject {subject}, Run {run} "
                                       f"in the ASL Module:\n{msg}")
                else:
                    pass
                err_container.clear()
                self.is_collecting_stdout_err = False
                n_collected = 0

            if self.is_collecting_stdout_err:
                err_container.append(output)
                n_collected += 1

        self.is_running = True
        stdout, stderr = self.proc.communicate()
        self.print_and_log(f"Worker {self.iworker}: has received return code {self.proc.returncode}", msg_type="info")
        self.is_running = False
        if self.terminate_attempted:
            self.print_and_log(f"Following Attempt to Terminate, the following givens were determined:\n"
                               f"{self.proc_gone=}\n{self.proc_alive=}", msg_type="warning")

        worker_analysis_dir = re.search(r'.*analysis', self.par_path).group()
        stdout_error_dict = {}
        stderr_error_dict = {}

        ####################################################
        # ATTEMPT TO CATCH STDOUT ERRORS FOR TROUBLESHOOTING
        ####################################################
        self.print_and_log(f"Worker {self.iworker}: Preparing to parse for any ExploreASL Errors", msg_type="info")
        if self.imodules == [3]:  # Population module
            stdout_error_regex = re.compile(r"ERROR: Job iteration terminated![\n\s]+ans ="
                                            r"([\n\s\w'\/()|;,><=%^&*$#!@~`:.\[\]]+)"
                                            r"CONT: but continue with next iteration")
            captured_stdout_errors = stdout_error_regex.findall(stdout)
            if len(captured_stdout_errors) == 1:
                self.print_and_log(f"Worker {self.iworker}: Found STDOUT errors from ExploreASL output",
                                   msg_type="info")
                stdout_error_dict[worker_analysis_dir] = {"Population": captured_stdout_errors[0]}
                self.signals.stdout_processing_error.emit(stdout_error_dict)
            else:
                self.print_and_log(f"Worker {self.iworker}: Did not find any STDOUT errors from ExploreASL output",
                                   msg_type="info")

        else:  # Anything other than the Population module
            subject_regex_str = self.worker_parms["subject_regexp"].strip("^$")
            stdout_error_regex = re.compile(
                r"\(" + subject_regex_str + r"\)" +
                r"(?:.*)"
                r"ERROR: Job iteration terminated![\n\s]+ans ="
                r"([\n\s\w'\/()|;,><=%^&*$#!@~`:.\[\]]+)"
                r"CONT: but continue with next iteration", re.DOTALL)

            captured_stdout_errors = stdout_error_regex.findall(stdout)
            if len(captured_stdout_errors) > 0:
                self.print_and_log(f"Worker {self.iworker}: Found STDOUT errors from ExploreASL output",
                                   msg_type="info")
                captured_stdout_errors = dict(captured_stdout_errors)
                stdout_error_dict[worker_analysis_dir] = captured_stdout_errors
                self.signals.stdout_processing_error.emit(stdout_error_dict)
            else:
                self.print_and_log(f"Worker {self.iworker}: Did not find any STDOUT errors from ExploreASL output",
                                   msg_type="info")

        #################################
        # SEND THE APPROPRIATE END SIGNAL
        #################################
        if self.proc.returncode == 0:
            self.print_and_log(f"Worker {self.iworker}: Has finished and is emitting a DONE signal", "info")
            self.signals.finished_processing.emit()
        else:
            self.print_and_log(f"Worker {self.iworker}: Has finished and is emitting an ERROR signal", "error")
            stderr_error_dict[str(Path(self.par_path).parent)] = stderr
            self.signals.stderr_processing_error.emit(stderr_error_dict)
            self.signals.encountered_fatal_error.emit()

        ###############
        # FINAL CLEANUP
        ###############
        self.logger.removeHandler(self.handler)
        del self.handler
        del self.logger

    def print_and_log(self, msg: str, msg_type: str = "error"):
        try:
            if msg_type in {"info", "warning", "error"}:
                getattr(self.logger, msg_type)(msg)
            print(msg)
        except AttributeError as attr_err:
            print(f"Worker{self.iworker} received an attribute error in {self.print_and_log.__name__}\n:{attr_err}")

    @Slot()
    def terminate_run(self):
        # First attempt to wake all processes back up
        if self.is_paused:
            self.pause_resume_proc_tree(pid=self.proc.pid, pause=False, include_parent=True)

        self.terminate_attempted = True
        self.print_and_log(f"Worker {self.iworker}: Received a TERMINATE signal. Stopping all child processes now",
                           msg_type="warning")
        if self.is_running and self.proc.poll() is None:
            self.proc_gone, self.proc_alive = self.kill_proc_tree(pid=self.proc.pid, include_parent=True)

    @Slot()
    def pause_run(self):
        self.print_and_log(f"Worker {self.iworker}: Received a Request to Pause all Work. Attempting to pause all "
                           f"child processes now", msg_type="info")
        self.pause_resume_proc_tree(pid=self.proc.pid, pause=True, include_parent=True)
        print(f"{self.proc.is_running()=}")
        self.is_paused = True
        self.signals.received_pause.emit(f"Worker {self.iworker} of {self.nworkers} for study {str(self.analysis_dir)} "
                                         f"is now pausing")

    @Slot()
    def resume_run(self):
        self.print_and_log(f"Worker {self.iworker}: Received a Request to Resume all Work. Attempting to wake up all "
                           f"child processes now", msg_type="info")
        self.pause_resume_proc_tree(pid=self.proc.pid, pause=False, include_parent=True)
        self.is_paused = False
        self.signals.received_resume.emit(f"Worker {self.iworker} of {self.nworkers} for study {str(self.analysis_dir)}"
                                          f" is now resuming")

    @staticmethod
    def kill_proc_tree(pid, sig=signal.SIGTERM, include_parent=True, timeout=None, on_terminate=None):
        """Kill a process tree (including grandchildren) with signal "sig" and return a (gone, still_alive) tuple.
        "on_terminate", if specified, is a callback function which is called as soon as a child terminates.
        """
        parent = Process(pid)
        children = parent.children(recursive=True)
        if include_parent:
            children.append(parent)
        for p in children:
            try:
                p.send_signal(sig)
            except NoSuchProcess:
                pass
        gone, alive = wait_procs(children, timeout=timeout, callback=on_terminate)
        return gone, alive

    @staticmethod
    def pause_resume_proc_tree(pid, pause: bool, include_parent=True):
        """Pause a process tree (including grandchildren)
        """
        parent = Process(pid)
        children = parent.children(recursive=True)
        if include_parent:
            children.append(parent)
        p: Process
        for p in children:
            try:
                if pause:
                    p.suspend()
                else:
                    p.resume()
            except NoSuchProcess:
                pass


# noinspection PyCallingNonCallable,PyAttributeOutsideInit,PyCallByClass
class xASL_Executor(QMainWindow):
    cont_nstudies: QWidget

    def __init__(self, parent_win):
        # Parent window is fed into the constructor to allow for communication with parent window devices
        super().__init__(parent=parent_win)
        self.config = self.parent().config

        # Window Size and initial visual setup
        self.setMinimumSize(self.config["ScreenSize"][0] // 2, self.config["ScreenSize"][1] // 2)
        self.resize(self.config["ScreenSize"][0] // 2, self.config["ScreenSize"][1] // 2)
        self.cw = QWidget(self)
        self.setCentralWidget(self.cw)
        self.mainlay = QHBoxLayout(self.cw)
        self.setLayout(self.mainlay)
        self.setWindowTitle("Explore ASL - Run Analysis")
        self.setWindowIcon(QIcon(str(Path(self.config["ProjectDir"]) / "media" / "ExploreASL_logo.png")))

        # Other instance variables
        self.threadpool = QThreadPool()
        self.processing_movieplayer = xASL_ImagePlayer(Path(self.config["ProjectDir"]) / "media" / "processing.gif")

        # MISC VARIABLES
        self.red_palette = QPalette()
        self.red_palette.setColor(QPalette.Highlight, Qt.red)
        self.green_palette = QPalette()
        self.green_palette.setColor(QPalette.Highlight, Qt.green)
        self.total_process_dbt = 0
        with open(Path(self.config["ProjectDir"]) / "JSON_LOGIC" / "ExecutorTranslators.json") as translator_reader:
            self.exec_translators = json.load(translator_reader)
        with open(Path(self.config["ProjectDir"]) / "JSON_LOGIC" / "ErrorsListing.json") as exec_err_reader:
            self.exec_errs = json.load(exec_err_reader)
        with open(Path(self.config["ProjectDir"]) / "JSON_LOGIC" / "ToolTips.json") as exec_tips_reader:
            self.exec_tips = json.load(exec_tips_reader)["Executor"]
        self.UI_Setup_Layouts_and_Groups()
        self.UI_Setup_TaskScheduler()
        self.UI_Setup_TextFeedback_and_Executor()
        self.UI_Setup_ProcessModification()

    def UI_Setup_Layouts_and_Groups(self):
        self.splitter_leftside = QSplitter(Qt.Vertical, self.cw)
        self.splitter_rightside = QSplitter(Qt.Vertical, self.cw)

        # Group Boxes
        self.grp_taskschedule = QGroupBox(title="Task Scheduler")
        self.grp_textoutput = QGroupBox(title="Output")
        self.grp_procmod = QGroupBox(title="Process Modifier")

        # Run Button
        self.frame_runExploreASL = QFrame()
        self.frame_runExploreASL.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.frame_runExploreASL.setLineWidth(0)
        self.vlay_frame_runExploreASL = QVBoxLayout(self.frame_runExploreASL)
        self.btn_runExploreASL = QPushButton("Run Explore ASL", clicked=self.run_Explore_ASL)
        self.btn_runExploreASL.setEnabled(False)
        run_icon_font = QFont()
        run_icon_font.setPointSize(24)
        self.btn_runExploreASL.setFont(run_icon_font)
        set_widget_icon(self.btn_runExploreASL, self.config, "run_icon.svg", (75, 75))
        self.btn_runExploreASL.setMinimumHeight(80)
        self.btn_runExploreASL.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.vlay_frame_runExploreASL.addWidget(self.btn_runExploreASL)

        # Add main players to the appropriate splitters
        self.splitter_leftside.addWidget(self.grp_taskschedule)
        self.splitter_leftside.addWidget(self.grp_procmod)
        self.splitter_rightside.addWidget(self.grp_textoutput)
        self.splitter_rightside.addWidget(self.frame_runExploreASL)

        # Adjust splitter spacing, handle width, and display
        self.splitter_rightside.setSizes([self.height() - 100, 100])
        self.splitter_leftside.setSizes([self.height() - 200, 200])
        self.splitter_rightside.setHandleWidth(25)
        self.splitter_leftside.setHandleWidth(25)
        handle_path = str(Path(self.config["ProjectDir"]) / "media" / "3_dots_horizontal.svg")
        if system() == "Windows":
            handle_path = handle_path.replace("\\", "/")
        handle_style = 'QSplitter::handle {image: url(' + handle_path + ');}'
        self.splitter_rightside.setStyleSheet(handle_style)
        self.splitter_leftside.setStyleSheet(handle_style)

        self.mainlay.addWidget(self.splitter_leftside)
        self.mainlay.addWidget(self.splitter_rightside)

    # Left side setup; define the number of studies
    def UI_Setup_TaskScheduler(self):
        self.vlay_scrollholder = QVBoxLayout(self.grp_taskschedule)
        self.scroll_taskschedule = QScrollArea()
        self.cont_taskschedule = QWidget()
        self.scroll_taskschedule.setWidget(self.cont_taskschedule)
        self.scroll_taskschedule.setWidgetResizable(True)
        self.vlay_scrollholder.addWidget(self.scroll_taskschedule)

        self.vlay_taskschedule = QVBoxLayout(self.cont_taskschedule)
        self.lab_coresinfo = QLabel(text=f"CPU Count: A total of {cpu_count() // 2} "
                                         f"processors are available on this machine")
        self.ncores_left = cpu_count() // 2
        self.lab_coresleft = QLabel(text=f"You are permitted to set up to {self.ncores_left} more core(s)")
        self.cont_nstudies = QWidget()
        self.hlay_nstudies = QHBoxLayout(self.cont_nstudies)
        self.lab_nstudies = QLabel(text=f"Indicate the number of studies you wish to process:")
        self.cmb_nstudies = QComboBox(self.cont_nstudies)
        self.nstudies_options = ["Select"] + list(map(str, range(1, (cpu_count() // 2 + 1))))
        self.cmb_nstudies.addItems(self.nstudies_options)
        self.cmb_nstudies.currentTextChanged.connect(self.UI_Setup_TaskScheduler_FormUpdate)
        self.cmb_nstudies.currentTextChanged.connect(self.set_ncores_left)
        self.cmb_nstudies.currentTextChanged.connect(self.is_ready_to_run)
        self.hlay_nstudies.addWidget(self.lab_nstudies)
        self.hlay_nstudies.addWidget(self.cmb_nstudies)

        self.cont_tasks = QWidget(self.grp_taskschedule)
        self.formlay_tasks = QFormLayout(self.cont_tasks)

        self.cont_progbars = QWidget(self.grp_taskschedule)
        self.formlay_progbars = QFormLayout(self.cont_progbars)
        if system() == "Darwin":
            set_formlay_options(self.formlay_progbars)
            self.vlay_taskschedule.setSpacing(0)

        # Need python lists to keep track of row additions/removals; findChildren's ordering is incorrect
        self.formlay_lineedits_list = []
        self.formlay_buttons_list = []
        self.formlay_cmbs_ncores_list = []
        self.formlay_cmbs_runopts_list = []
        self.formlay_nrows = 0
        self.formlay_progbars_list = []
        self.formlay_stopbtns_list = []
        self.formlay_pausebtns_list = []
        self.formlay_resumebtns_list = []

        for widget in [self.lab_coresinfo, self.lab_coresleft, self.cont_nstudies, self.cont_tasks, self.cont_progbars]:
            self.vlay_taskschedule.addWidget(widget)
        self.vlay_taskschedule.addStretch(2)
        self.cmb_nstudies.setCurrentIndex(1)

    # Right side setup; this will have a text editor to display feedback coming from ExploreASL or any future watchers
    # that are installed. Also, the Run buttons will be set up here.
    def UI_Setup_TextFeedback_and_Executor(self):
        self.vlay_textoutput = QVBoxLayout(self.grp_textoutput)
        self.textedit_textoutput = QTextEdit(self.grp_textoutput)
        self.textedit_textoutput.setPlaceholderText("Processing Progress will appear within this window")
        self.textedit_textoutput.setFontPointSize(8 if system() != "Darwin" else 10)
        self.vlay_textoutput.addWidget(self.textedit_textoutput)

    # Rare exception of a UI function that is also technically a setter; this will dynamically alter the number of
    # rows present in the task scheduler form layout to allow for ExploreASL analysis of multiple studies at once
    def UI_Setup_TaskScheduler_FormUpdate(self, n_studies):
        if n_studies == "Select":
            return  # Don't do anything if the user selects Select again by accident
        n_studies = int(n_studies)
        diff = n_studies - self.formlay_nrows  # The difference between the current n_rows and n_studies

        # Addition of rows
        if diff > 0:
            for ii in range(diff):
                self.formlay_nrows += 1

                # Combobox to specify the number of cores to allocate
                inner_cmb_ncores = QComboBox()
                inner_cmb_ncores.setMinimumWidth(140)
                inner_cmb_ncores.setToolTip(self.exec_tips["inner_cmb_ncores"])
                inner_cmb_ncores.addItems(list(map(str, range(1, cpu_count() // 2 + 1))))
                inner_cmb_ncores.currentTextChanged.connect(self.set_ncores_left)
                inner_cmb_ncores.currentTextChanged.connect(self.set_ncores_selectable)
                inner_cmb_ncores.currentTextChanged.connect(self.set_nstudies_selectable)
                inner_cmb_ncores.currentTextChanged.connect(self.is_ready_to_run)

                # Lineedit to specify
                inner_le = DandD_FileExplorer2LineEdit(acceptable_path_type="Directory")
                inner_le.setToolTip(self.exec_tips["inner_le"])
                inner_le.setClearButtonEnabled(True)
                inner_le.setPlaceholderText("Select the analysis directory to your study")
                inner_le.textChanged.connect(self.is_ready_to_run)
                inner_btn_browsedirs = RowAwareQPushButton(self.formlay_nrows, "...")
                inner_btn_browsedirs.row_idx_signal.connect(self.set_analysis_directory)

                # Combobox to specify when module to run
                inner_cmb_procopts = QComboBox()
                inner_cmb_procopts.setToolTip(self.exec_tips["inner_cmb_procopts"])
                inner_cmb_procopts.addItems(["Structural", "ASL", "Both", "Population"])
                inner_cmb_procopts.setCurrentIndex(2)
                inner_cmb_procopts.currentTextChanged.connect(self.is_ready_to_run)

                # Stop Button
                stop_icon_path = Path(self.config["ProjectDir"]) / "media" / "stop_processing.png"
                inner_btn_stop = QPushButton(QIcon(str(stop_icon_path)), "", enabled=False)
                inner_btn_stop.setToolTip("Stop this study being run")

                # Pause Button
                pause_icon_path = Path(self.config["ProjectDir"]) / "media" / "pause_processing.png"
                inner_btn_pause = QPushButton(QIcon(str(pause_icon_path)), "", enabled=False)
                inner_btn_pause.setToolTip("Pause this study being run")

                # Resume Button
                resume_icon_path = Path(self.config["ProjectDir"]) / "media" / "resume_processing.png"
                inner_btn_resume = QPushButton(QIcon(str(resume_icon_path)), "", enabled=False)
                inner_btn_resume.setToolTip("Resume this paused study")

                # HBoxLayout for the control btns
                inner_hbox_ctrls = QHBoxLayout()
                inner_hbox_ctrls.addWidget(inner_btn_resume)
                inner_hbox_ctrls.addWidget(inner_btn_pause)
                inner_hbox_ctrls.addWidget(inner_btn_stop)

                # Signals and Slots for the ctrl btns
                inner_btn_resume.clicked.connect(partial(self.one_btn_blocks_other, calling_btn=inner_btn_resume,
                                                         receiver_btn=inner_btn_pause))
                inner_btn_resume.clicked.connect(self.processing_movieplayer.movie.start)
                inner_btn_pause.clicked.connect(partial(self.one_btn_blocks_other, calling_btn=inner_btn_pause,
                                                        receiver_btn=inner_btn_resume))
                inner_btn_pause.clicked.connect(self.processing_movieplayer.movie.stop)

                # Package it all in another FormLayout
                inner_grp = QGroupBox(title=f"Study {inner_btn_browsedirs.row_idx}")
                inner_formlay = QFormLayout(inner_grp)
                if system() == "Darwin":
                    set_formlay_options(inner_formlay, vertical_spacing=0)
                    for widget in [inner_cmb_ncores, inner_le, inner_cmb_procopts, inner_btn_stop,
                                   inner_btn_pause, inner_btn_resume
                                   ]:
                        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                inner_formlay.addRow("Assigned Number of Cores", inner_cmb_ncores)
                inner_hbox = QHBoxLayout()
                inner_hbox.addWidget(inner_le)
                inner_hbox.addWidget(inner_btn_browsedirs)
                inner_formlay.addRow("Path to Analysis Folder", inner_hbox)
                inner_formlay.addRow("Which Modules to Run", inner_cmb_procopts)
                inner_formlay.addRow("Control Processing", inner_hbox_ctrls)

                # Add progressbars
                inner_progbar = QProgressBar(orientation=Qt.Horizontal, value=0, maximum=100, minimum=0)
                inner_progbar.setPalette(self.green_palette)

                # Update format layouts through addition of the appropriate row
                # self.formlay_tasks.addRow(inner_cmb_ncores, inner_hbox)
                self.formlay_tasks.addRow(inner_grp)
                self.formlay_progbars.addRow(f"Study {inner_btn_browsedirs.row_idx}", inner_progbar)

                # Add widgets to their respective containers
                self.formlay_cmbs_ncores_list.append(inner_cmb_ncores)
                self.formlay_lineedits_list.append(inner_le)
                self.formlay_buttons_list.append(inner_btn_browsedirs)
                self.formlay_cmbs_runopts_list.append(inner_cmb_procopts)
                self.formlay_progbars_list.append(inner_progbar)
                self.formlay_stopbtns_list.append(inner_btn_stop)
                self.formlay_pausebtns_list.append(inner_btn_pause)
                self.formlay_resumebtns_list.append(inner_btn_resume)

        # Removal of rows
        elif diff < 0:
            for ii in range(abs(diff)):
                row_to_remove = self.formlay_nrows - 1

                # Update format layouts through removal of the appropriate row
                self.formlay_tasks.removeRow(row_to_remove)
                self.formlay_progbars.removeRow(row_to_remove)

                # Remove widgets from their respective containers starting from the latest addition
                self.formlay_cmbs_ncores_list.pop()
                self.formlay_lineedits_list.pop()
                self.formlay_buttons_list.pop()
                self.formlay_cmbs_runopts_list.pop()
                self.formlay_progbars_list.pop()
                self.formlay_stopbtns_list.pop()

                self.formlay_pausebtns_list.pop()
                self.formlay_resumebtns_list.pop()

                self.formlay_nrows -= 1

        # Adjust the number of cores selectable in each of the comboboxes
        self.set_ncores_left()
        self.set_ncores_selectable()
        self.set_nstudies_selectable()
        self.is_ready_to_run()

    # Left side setup; launches additional windows for specialized jobs such as modifying participants.tsv, preparing
    # a study for re-run in certain subjects, etc.
    def UI_Setup_ProcessModification(self):
        self.vlay_procmod = QVBoxLayout(self.grp_procmod)
        self.formlay_promod = QFormLayout()

        # Set up the widgets in this section
        self.cmb_modjob = QComboBox(self.grp_procmod)
        self.cmb_modjob.addItems(["Re-run a study", "Alter participants.tsv",
                                  "Change Json Sidecars", "Merge Study Directories"])
        self.cmb_modjob.setToolTip(self.exec_tips["cmb_modjob"])
        (self.hlay_modjob,
         self.le_modjob,
         self.btn_modjob) = make_droppable_clearable_le(btn_connect_to=self.set_modjob_analysis_dir,
                                                        acceptable_path_type="Directory")
        self.le_modjob.setPlaceholderText("Drag & Drop analysis directory here")
        self.le_modjob.setToolTip(self.exec_tips["inner_le"])
        self.btn_runmodjob = QPushButton("Modify for Re-run", self.grp_procmod, clicked=self.run_modjob)

        modjob_icon_font = QFont()
        modjob_icon_font.setPointSize(24)
        self.btn_runmodjob.setFont(modjob_icon_font)
        set_widget_icon(self.btn_runmodjob, self.config, "run_modjob_icon.svg", (75, 75))
        self.btn_runmodjob.setMinimumHeight(80)
        self.btn_runmodjob.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)

        # Add the widgets to the form layout
        self.formlay_promod.addRow("Which modification job to run", self.cmb_modjob)
        self.formlay_promod.addRow("Path to analysis dir to modify", self.hlay_modjob)
        self.vlay_procmod.addLayout(self.formlay_promod)
        self.vlay_procmod.addWidget(self.btn_runmodjob)

        if system() == "Darwin":
            set_formlay_options(self.formlay_promod, vertical_spacing=0)
            self.btn_runmodjob.setMinimumHeight(90)
            for widget in [self.cmb_modjob, self.le_modjob]:
                widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    # Runs the selected modification widget
    # noinspection PyCallByClass
    def run_modjob(self):
        selected_job = self.cmb_modjob.currentText()
        root_path = Path(self.le_modjob.text()).resolve()
        modjob_widget = None
        if selected_job == "Alter participants.tsv":
            if any([self.le_modjob.text() == '', not (root_path / "participants.tsv").exists()]):
                robust_qmsg(self, title=self.exec_errs["ParticipantsTSVNotFound"][0],
                            body=self.exec_errs["ParticipantsTSVNotFound"][1])
                return
            modjob_widget = xASL_GUI_TSValter(self)
        elif selected_job == "Re-run a study":
            if any([self.le_modjob.text() == '', not (root_path / "lock").exists()]):
                robust_qmsg(self, title=self.exec_errs["LockDirSystemNotFound"][0],
                            body=self.exec_errs["LockDirSystemNotFound"][1])
                return
            modjob_widget = xASL_GUI_RerunPrep(self)
        elif selected_job == "Change Json Sidecars":
            if any([self.le_modjob.text() == "", not root_path.is_dir(), not root_path.exists()]):
                robust_qmsg(self, title=self.exec_errs["InvalidStudyDirectory"][0],
                            body=self.exec_errs["InvalidStudyDirectory"][1], variables=[str(root_path)])
                return
            modjob_widget = xASL_GUI_ModSidecars(self)
        elif selected_job == "Merge Study Directories":
            modjob_widget = xASL_GUI_MergeDirs(self, str(Path.home()))

        if modjob_widget is not None:
            modjob_widget.show()

    ##########################
    # TASK SCHEDULER FUNCTIONS
    ##########################
    # Function responsible for adjusting the label of how many cores are still accessible
    def set_ncores_left(self):
        self.ncores_left = cpu_count() // 2 - sum([int(cmb.currentText()) for cmb in self.formlay_cmbs_ncores_list])
        if self.ncores_left > 0:
            self.lab_coresleft.setText(f"You are permitted to set up to {self.ncores_left} more core(s)")
        elif self.ncores_left == 0:
            self.lab_coresleft.setText(f"No more cores are avaliable for allocation")
        else:
            self.lab_coresleft.setText(f"Something went terribly wrong")

    # Function responsible for adjusting the choices avaliable within each of the comboboxes of a given task row
    def set_ncores_selectable(self):
        self.ncores_left = cpu_count() // 2 - sum([int(cmb.currentText()) for cmb in self.formlay_cmbs_ncores_list])
        cores_left = self.ncores_left
        for box in self.formlay_cmbs_ncores_list:
            current_selection = int(box.currentText())
            max_cores_allowed = current_selection + cores_left
            for idx in range(box.count()):
                val_at_idx = int(box.itemText(idx))
                if val_at_idx <= max_cores_allowed:
                    box.model().item(idx).setEnabled(True)
                else:
                    box.model().item(idx).setEnabled(False)

    # Function responsible for adjusting the number of studies still permitted (assuming 1 core will be initially
    # allocated to it)
    def set_nstudies_selectable(self):
        self.ncores_left = cpu_count() // 2 - sum([int(cmb.currentText()) for cmb in self.formlay_cmbs_ncores_list])
        current_n_studies = int(self.cmb_nstudies.currentText())
        max_studies_allowed = current_n_studies + self.ncores_left
        for idx in range(self.cmb_nstudies.count()):
            val_at_idx = self.cmb_nstudies.itemText(idx)
            if not val_at_idx.isdigit():
                continue
            val_at_idx = int(val_at_idx)
            if val_at_idx <= max_studies_allowed:
                self.cmb_nstudies.model().item(idx).setEnabled(True)
            else:
                self.cmb_nstudies.model().item(idx).setEnabled(False)

    # This slot is responsible for setting the correct analysis directory to a given task row's lineedit correcting
    @Slot(int)
    def set_analysis_directory(self, row_idx):
        """
        :param row_idx: The index of the row from the pushbutton calling this slot. It is a non-pythonic index, so it
        must be reduced by 1 to index properly
        """
        s, d = robust_getdir(self, "Select the Analysis Directory", self.config["DefaultRootDir"],
                             requirements={"contains": ["DataPar*.json", self.exec_errs["DataPar File Not Found_Alt"]]})
        if s:
            self.formlay_lineedits_list[row_idx - 1].setText(str(d))

    def set_modjob_analysis_dir(self):
        robust_getdir(self, "Select the Analysis Directory", self.config["DefaultRootDir"], lineedit=self.le_modjob)

    # Define whether the run Explore ASL button should be enabled
    def is_ready_to_run(self):
        # First check: all lineedits must have an appropriate analysis directory with a par file
        for le in self.formlay_lineedits_list:
            if le.text() in {"", ".", "\\", "/", "~"}:
                self.btn_runExploreASL.setEnabled(False)
                return
            filepath = Path(le.text().replace("~", str(Path.home()))).resolve()
            if not all([filepath.exists(), filepath.is_dir(), peekable(filepath.glob("DataPar*.json"))]):
                self.btn_runExploreASL.setEnabled(False)
                return

        for cmb_cores, le_analysisdir, cmb_runopt in zip(self.formlay_cmbs_ncores_list,
                                                         self.formlay_lineedits_list,
                                                         self.formlay_cmbs_runopts_list):
            # Second check: for any study that has its module set as Population, the number of cores must be 1
            if cmb_runopt.currentText() == "Population" and cmb_cores.currentText() != "1":
                self.btn_runExploreASL.setEnabled(False)
                return

            # Third check: the number of cores selected cannot exceed the number of subjects
            if cmb_runopt.currentText() != "Population":
                filepath = Path(le_analysisdir.text().replace("~", str(Path.home()))).resolve()
                datapar_path = peekable(filepath.glob("DataPar*.json"))
                if not datapar_path:
                    self.btn_runExploreASL.setEnabled(False)
                    return
                with open(next(datapar_path)) as datapar_reader:
                    try:
                        regex = json.load(datapar_reader)["subject_regexp"]
                    except KeyError:
                        self.btn_runExploreASL.setEnabled(False)
                        return
                    except json.decoder.JSONDecodeError as json_err:
                        robust_qmsg(self, title=self.exec_errs["BadDataParFileJson"][0],
                                    body=self.exec_errs['BadDataParFileJson'][1] + str(json_err))
                        le_analysisdir.clear()
                        self.btn_runExploreASL.setEnabled(False)
                        return

                n_subjects = sum([True if re.search(regex, path.name) else False for path in filepath.iterdir()])
                if n_subjects < int(cmb_cores.currentText()):
                    self.btn_runExploreASL.setEnabled(False)
                    return

        self.btn_runExploreASL.setEnabled(True)

    ###################################
    # CONCURRENT AND POST-RUN FUNCTIONS
    ###################################
    def post_run_main(self):
        """
        Main wrapper function for all post-run followup
        """
        # Re-activate all relevant widgets
        self.set_widgets_activation_states(True)
        # Stop the movie
        self.end_movie()
        # Check if all expected operations took place
        self.post_run_statusfile_and_error_assessment()
        # Take care of temporary log files
        self.post_run_handle_log_files()
        # Check the progressbars
        for progbar in self.formlay_progbars_list:
            if progbar.value() != progbar.maximum():
                progbar.setPalette(self.red_palette)

    def post_run_handle_log_files(self):
        study_dir: Path
        for study_dir in self.expected_status_files.keys():
            tmp_worker_files = sorted(study_dir.glob("tmp_RunWorker_*.log"))
            if len(tmp_worker_files) == 0:
                continue
            content = []
            for tmp_file in tmp_worker_files:
                with open(tmp_file) as tmp_reader:
                    content.append(tmp_reader.read())
                tmp_file.unlink(missing_ok=True)
            to_write = "\n\n".join(content)
            err_write_date_str = datetime.now().strftime("%a-%b-%d-%Y_%H-%M-%S")
            with open(study_dir / f"Run_Log_{err_write_date_str}.log", "w") as log_writer:
                log_writer.write(to_write)

    def post_run_statusfile_and_error_assessment(self):
        """
        1) Assesses any stdout errors that were captured during the run. That is, processes that finish successfully
        with code 0 may have still experienced errors that stopped an iteration. These must be captured.
        2) Assesses any stderr errors that were captured during the run. That is, processes that did not finish
        correctly (i.e MATLAB crashed)
        3) Assess the STATUS files that were generated against the expected files
        4) Joins all the aforementioned together in an error file for that study
        """
        # stdout_errordict_list is a list whose elements are dicts whose keys are string paths to analysis directories
        # and whose values are a list of regex-captured ExploreASL error messages
        # stderr_errordict_list is a list whose elements are dicts whose keys are string paths to analysis directories
        # and whose values are the string stderr message that was captured for that analysis directory

        master_stdout_err_dict = defaultdict(list)
        master_stderr_err_dict = defaultdict(list)
        # First, assess the status of the stdout_errordicts_list
        if len(self.stdout_errordicts_list) > 0:
            # Must convert from a list of dicts to a dict of lists
            for stdout_errordict in self.stdout_errordicts_list:
                for study_path, study_errors in stdout_errordict.items():
                    master_stdout_err_dict[study_path].append(study_errors)

        # Same deal for the stderr_errordicts_list
        if len(self.stderr_errordicts_list) > 0:
            # Must convert from a list of dicts to a dict of lists
            for stderr_errordict in self.stderr_errordicts_list:
                for study_path, study_errors in stderr_errordict.items():
                    master_stderr_err_dict[study_path].append(study_errors)

        # Next, assess the status files
        postrun_diagnosis = {}  # Dict whose keys are Path objects of analysis dirs and values are Path .status files
        study_dir: Path
        expected_files: List[Path]
        for study_dir, expected_files in self.expected_status_files.items():
            all_completed, incomplete_status_files = calculate_missing_STATUS(study_dir, expected_files)

            if self.config["DeveloperMode"] and len(incomplete_status_files) > 0:
                print(f"INCOMPLETE STATUS FILES FOR STUDY DIR: {study_dir}:")
                pprint(incomplete_status_files)

            if all_completed:
                continue
            else:
                postrun_diagnosis[study_dir] = incomplete_status_files

        # If at least one study had an issue, print out a warning and generate a log file in that study directory
        if len(postrun_diagnosis) > 0:
            study_dir: Path
            incomplete_files: List[Path]
            for study_dir, incomplete_files in postrun_diagnosis.items():
                all_module_msgs: List[List[str]] = interpret_statusfile_errors(study_dir, incomplete_files,
                                                                               self.exec_translators)
                structmod_msgs, aslmod_msgs, popmod_msgs = all_module_msgs

                specific_stdout_msg = []
                # Extract the specific error messages
                if str(study_dir) in list(master_stdout_err_dict.keys()):
                    study_errs = master_stdout_err_dict[str(study_dir)]
                    for err_dict in study_errs:
                        for subject, err in err_dict.items():
                            specific_stdout_msg.append(f"{subject}:\n{err.strip()}\n\n")

                specific_stderr_msg = []
                # Extract the specific stderr messages
                if str(study_dir) in list(master_stderr_err_dict.keys()):
                    study_errs = master_stderr_err_dict[str(study_dir)]
                    for std_err_msg in study_errs:
                        specific_stderr_msg.append(std_err_msg)

                msg = ["The following could not be completed during the run:\n"] + \
                      ["\n########################", "\nIn the Structural Module:\n"] + \
                      [file + '\n' for file in structmod_msgs] + \
                      ["\n########################", "\nIn the ASL Module:\n"] + \
                      [file + '\n' for file in aslmod_msgs] + \
                      ["\n########################", "\nIn the Population Module:\n"] + \
                      [file + '\n' for file in popmod_msgs] + \
                      ["\n########################", "\nSpecific Stdout Errors:\n"] + specific_stdout_msg + \
                      ["\n########################", "\nSpecific Stderr Errors:\n"] + specific_stderr_msg

                err_write_date_str = datetime.now().strftime("%a-%b-%d-%Y %H-%M-%S")
                try:
                    with open(study_dir / f"{err_write_date_str} ExploreASL run - errors.txt", 'w') as writer:
                        writer.writelines(msg)
                except OSError:
                    pass
            dirs_string = "\n".join([str(analysis_dir) for analysis_dir in postrun_diagnosis.keys()])
            robust_qmsg(self, title=self.exec_errs["UnsuccessfulExploreASLrun"][0],
                        body=self.exec_errs["UnsuccessfulExploreASLrun"][1], variables=[dirs_string])
        else:
            robust_qmsg(self, msg_type="information", title="Successful ExploreASL",
                        body="All expected operations took place\nMany thanks for using ExploreASL. If this has been "
                             "helpful in your study please don't forget to cite this program in your manuscript.")

    @staticmethod
    def one_btn_blocks_other(calling_btn: QPushButton, receiver_btn: QPushButton):
        calling_btn.setEnabled(False)
        receiver_btn.setEnabled(True)

    # Based on signal outout, this receives messages from watchers and outputs text feedback to the user
    @Slot(str)
    def update_text(self, msg):
        self.textedit_textoutput.append(msg)

    @Slot(dict)
    def update_stdout_error_dicts(self, stdout_error_dict: dict):
        self.stdout_errordicts_list.append(stdout_error_dict)
        if self.config["DeveloperMode"]:
            print("update_stdout_error_dicts got a signal")

    @Slot(dict)
    def update_stderr_error_dicts(self, stderr_error_dict):
        self.stderr_errordicts_list.append(stderr_error_dict)
        if self.config["DeveloperMode"]:
            print("update_stderr_error_dicts got a signal")

    # This slot is responsible for updating the progressbar based on signals set from the watcher
    @Slot(int, int)
    def update_progressbar(self, val_to_inc_by, study_idx):
        """
        :param val_to_inc_by: the value of the .STATUS file that was just completed
        :param study_idx: the index of the progressbar contained within formlay_progbars_list to be selected
        """
        selected_progbar: QProgressBar = self.formlay_progbars_list[study_idx]
        if self.config["DeveloperMode"]:
            print(
                f"update_progressbar received a signal from watcher {study_idx} to increase the progressbar value by "
                f"{val_to_inc_by}")
            print(f"The progressbar's value before update: {selected_progbar.value()} "
                  f"out of maximum {selected_progbar.maximum()}")
        selected_progbar.setValue(selected_progbar.value() + val_to_inc_by)
        if self.config["DeveloperMode"]:
            print(f"The progressbar's value after update: {selected_progbar.value()} "
                  f"out of maximum {selected_progbar.maximum()}")

    # This slot is responsible for re-activating the Run ExploreASL button
    @Slot()
    def update_process_debt_and_check_done(self):
        """
        Receives a signal that a process has finished, regardless of whether it was a success or crash, updates the
        total debt accordingly, and launches the post-run function if the debt is cleared
        """
        self.total_process_dbt += 1
        if self.config["DeveloperMode"]:
            print(f"update_process_debt_and_check_done received a signal and incremented the debt. "
                  f"The debt at this time is: {self.total_process_dbt}")

        # If the debt is cleared, proceed to the post-run assessments and widget processing
        if self.total_process_dbt == 0:
            self.post_run_main()

    # Convenience function; deactivates all widgets associated with running exploreASL
    def set_widgets_activation_states(self, state: bool):
        self.btn_runExploreASL.setEnabled(state)
        self.cmb_nstudies.setEnabled(state)

        zipper = zip(self.formlay_cmbs_ncores_list, self.formlay_lineedits_list, self.formlay_buttons_list,
                     self.formlay_cmbs_runopts_list, self.formlay_stopbtns_list, self.formlay_pausebtns_list,
                     self.formlay_resumebtns_list)
        for core_cmb, le, browse_btn, runopt_cmb, stop_btn, pause_btn, resume_btn in zipper:
            core_cmb.setEnabled(state)
            le.setEnabled(state)
            browse_btn.setEnabled(state)
            runopt_cmb.setEnabled(state)
            stop_btn.setEnabled(not state)

            # Slightly different behaviors for the other btns
            if not state:  # A run has started
                if not pause_btn.isEnabled():
                    pause_btn.setEnabled(not state)
                resume_btn.setEnabled(False)

            else:  # A run has ended
                pause_btn.setEnabled(not state)
                resume_btn.setEnabled(not state)

    # Convenience function; adds a gif indicating processing below the textoutput and starts the gif
    def begin_movie(self):
        """
        Convenience function; adds a gif indicating processing below the textoutput and starts the gif
        """
        self.processing_movieplayer.movie.start()
        self.processing_movieplayer.setVisible(True)
        self.vlay_textoutput.addWidget(self.processing_movieplayer)

    # Convenience function; removes the gif below the textoutput and stops the gif
    def end_movie(self):
        """
        Convenience function; removes the gif below the textoutput and stops the gif
        """
        self.processing_movieplayer.movie.stop()
        self.processing_movieplayer.setVisible(False)
        self.vlay_textoutput.removeWidget(self.processing_movieplayer)

    ###################
    # PRE-RUN QC CHECKS
    ###################
    def runcheck_matlab_ver(self):
        # Immediately abandon this if the MATLAB version is not compatible with batch commands
        mlab_ver = self.config.get("MATLAB_VER", None)
        mlab_path = self.config.get("MATLAB_CMD_PATH", None)
        if mlab_ver is None or not isinstance(mlab_ver, str):
            robust_qmsg(self, title=self.exec_errs["Unknown MATLAB VERSION"][0],
                        body=self.exec_errs["Unknown MATLAB VERSION"][1])
            return False, None

        # Immediately abandone this if the MATLAB command path is not known
        if mlab_path is None or not Path(mlab_path).resolve().exists():
            robust_qmsg(self, title=self.exec_errs["Unknown MATLAB CMD_PATH"][0],
                        body=self.exec_errs["Unknown MATLAB CMD_PATH"][1])
            return False, None

        try:
            mlab_ver = int(re.search(r"R(\d{4})[ab]", mlab_ver).group(1))
            # Immediately abandon this if the MATLAB version is too old
            if mlab_ver < 2016:
                robust_qmsg(self, title=self.exec_errs["Incompatible MATLAB Version"][0],
                            body=self.exec_errs["Incompatible MATLAB Version"][1], variables=[str(mlab_ver)])
                return False, None
            # Or if too old for Windows due to the lack of the -nodisplay option
            if system() == "Windows" and not mlab_ver >= 2019:
                robust_qmsg(self, title=self.exec_errs["Incompatible MATLAB Version"][0],
                            body=self.exec_errs["Incompatible MATLAB Version"][1], variables=[str(mlab_ver)])
                return False, None
        # Or if something went wrong getting the version
        except AttributeError:
            robust_qmsg(self, title=self.exec_errs["Unknown MATLAB VERSION"][0],
                        body=self.exec_errs["Unknown MATLAB VERSION"][1])
            return False, None
        return True, mlab_ver

    ###################################################################################################################
    #                                              THE MAIN RUN FUNCTION
    ###################################################################################################################
    def run_Explore_ASL(self):
        if self.config["DeveloperMode"]:
            print("%" * 60)
        translator = {"Structural": [1], "ASL": [2], "Both": [1, 2], "Population": [3]}
        self.loggers = []
        self.workers = []
        self.watchers = []
        self.total_process_dbt = 0
        self.expected_status_files = {}
        self.stdout_errordicts_list = []
        self.stderr_errordicts_list = []

        # Disable widgets
        # self.set_widgets_activation_states(False)

        # Clear the textoutput each time
        self.textedit_textoutput.clear()

        # Outer for loop; loops over the studies
        for study_idx, (box, path, run_opts, progressbar, stop_btn, pause_btn, resume_btn) in enumerate(
                zip(self.formlay_cmbs_ncores_list,  # Comboboxes for number of cores
                    self.formlay_lineedits_list,  # Lineedits for analysis directory path
                    self.formlay_cmbs_runopts_list,  # Comboboxes for the modules to run
                    self.formlay_progbars_list,  # Progressbars for the study
                    self.formlay_stopbtns_list,  # Stop Buttons for that study

                    self.formlay_pausebtns_list,
                    self.formlay_resumebtns_list,

                    )):

            #########################################
            # INNER FOR LOOP - For a particular study
            #########################################
            # Create a container to keep a block of workers in for a particular study
            # Also create a debt counter to be fed to the watcher so that it can eventually disengage
            inner_worker_block = []
            debt = 0
            # %%%%%%%%%%%%%%%%%%%%%%
            # Step 1 - For the study, load in the parameters

            forbidden = {"", ".", "/", "\\", "~"}
            if path.text() in forbidden:
                robust_qmsg(self, title=self.exec_errs["Forbidden Study Character"][0],
                            body=self.exec_errs["Forbidden Study Character"][1], variables=[path.text()])
                # self.set_widgets_activation_states(True)
                return

            ana_path = Path(path.text().replace("~", str(Path.home()))).resolve()
            try:
                parms_file = next(ana_path.glob("DataPar*.json"))
            except StopIteration:
                robust_qmsg(self, title=self.exec_errs["DataPar File Not Found"][0],
                            body=self.exec_errs["DataPar File Not Found"][1], variables=[str(ana_path)])
                # self.set_widgets_activation_states(True)
                return

            # Load in the DataPar.json file and Extract essential parameters
            try:
                # First load in the file
                with open(parms_file) as f:
                    parms: dict = json.load(f)

                str_regex: str = parms["subject_regexp"].strip("^$")
                regex: re.Pattern = re.compile(str_regex)
                easl_scenario: str = parms["EXPLOREASL_TYPE"]
                excluded_subjects: list = parms["exclusion"]
                root_in_parms: str = parms["D"]["ROOT"]

            except json.decoder.JSONDecodeError as json_read_error:
                robust_qmsg(self, title=self.exec_errs["BadDataParFileJson"][0],
                            body=self.exec_errs["BadDataParFileJson"][1],
                            variables=[str(ana_path), f"{json_read_error}"])
                # self.set_widgets_activation_states(True)
                return
            except KeyError as parms_keyerror:
                robust_qmsg(self, title=self.exec_errs["BadDataParFileKeys"][0],
                            body=self.exec_errs["BadDataParFileKeys"][1],
                            variables=[str(ana_path), f"{parms_keyerror}"])
                # self.set_widgets_activation_states(True)
                return

            # Check that the parms file's D.ROOT matches the lineedit's resolved filepath
            if root_in_parms != str(ana_path):
                robust_qmsg(self, title=self.exec_errs["NoStartExploreASL"][0],
                            body=self.exec_errs["NoStartExploreASL"][1], variables=[str(ana_path)])
                # self.set_widgets_activation_states(True)
                return

            # Regex check for subject hits
            hits = []
            for subject_path in ana_path.iterdir():
                if any([subject_path.name in {"lock", "Population"}, subject_path.is_file(),
                        subject_path.name in excluded_subjects]):
                    continue
                hits.append(bool(regex.search(subject_path.name)))
            if not any(hits):
                robust_qmsg(self, title=self.exec_errs["NoStartExploreASL"][0],
                            body=self.exec_errs["NoStartExploreASL"][1], variables=[str(ana_path)])
                # self.set_widgets_activation_states(True)
                return

            # Perform the appropriate checks depending on the ExploreASL Scenario (local, compiled, docker, etc.)
            if easl_scenario == "LOCAL_UNCOMPILED":
                # If it is a local version, then the MATLAB version and the path to the MATLAB command must be legit
                can_proceed, int_mlab_ver = self.runcheck_matlab_ver()
                if not can_proceed:
                    # self.set_widgets_activation_states(True)
                    return
                else:
                    parms["WORKER_MATLAB_VER"] = int_mlab_ver
                    parms["WORKER_MATLAB_CMD_PATH"] = self.config["MATLAB_CMD_PATH"]
            elif easl_scenario == "LOCAL_COMPILED":
                pass
            else:
                robust_qmsg(self, title=self.exec_errs["Unsupported ExploreASL Scenario"][0],
                            body=self.exec_errs["Unsupported ExploreASL Scenario"][1], variables=[str(ana_path)])
                # self.set_widgets_activation_states(True)
                return

            # %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
            # Step 2 - Prepare the environment for that study
            worker_env = environ.copy()
            if easl_scenario == "LOCAL_UNCOMPILED":
                pass
            elif easl_scenario == "LOCAL_COMPILED":
                # First, get the Runtime path
                runtime_path = parms.get("MCRPath", None)
                if runtime_path is None:
                    robust_qmsg(self, title=self.exec_errs["Unknown MATLAB Runtime"][0],
                                body=self.exec_errs["Unknown MATLAB Runtime"][1])
                    # self.set_widgets_activation_states(True)
                    return
                runtime_path = Path(runtime_path).resolve()

                system_dict = {"Windows": ["PATH", ";", "win64"],
                               "Linux": ["LD_LIBRARY_PATH", ":", "glnax64"],
                               "Darwin": ["DYLD_LIBRARY_PATH", ":", "maci64"]}
                x = system()
                try:
                    current_paths = worker_env.get(system_dict[x][0], "")
                    if isinstance(current_paths, list, tuple):
                        current_paths = "".join(current_paths)
                    located_paths = [path for path in runtime_path.rglob(system_dict[x][2]) if
                                     all([path.is_dir(), str(path not in current_paths)])]
                    paths2add = system_dict[x][1].join(located_paths)
                    current_paths += paths2add
                    worker_env[system_dict[x][0]] = current_paths
                except KeyError:
                    # self.set_widgets_activation_states(True)
                    return

            # %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
            # Step 3 - Prepare the workers for that study
            # Inner for loop: loops over the range of the num of cores within a study. Each core will be an iWorker
            for ii in range(box.count()):
                if ii < int(box.currentText()):
                    worker = ExploreASL_Worker(
                        worker_parms=parms,
                        iworker=ii + 1,  # iWorker
                        nworkers=int(box.currentText()),  # nWorkers
                        imodules=translator[run_opts.currentText()],  # Which modules Structural, ASL, Both, Population
                        worker_env=worker_env
                    )

                    inner_worker_block.append(worker)
                    debt -= 1
                    self.total_process_dbt -= 1

            # Add the block to the main workers argument
            self.workers.append(inner_worker_block)

            # %%%%%%%%%%%%%%%%%%%%%%%%%
            # Step 4 - Calculate the anticipated workload based on missing .STATUS files; adjust the progressbar's
            # maxvalue from that
            # This now ALSO makes the lock dirs that do not exist
            # TODO Check how this calculating anticipated workload works with the new compiled system
            workload, expected_status_files = calculate_anticipated_workload(parmsdict=parms,
                                                                             run_options=run_opts.currentText(),
                                                                             translators=self.exec_translators)

            # Also delete any directories called "locked" in the study
            locked_dirs = peekable(ana_path.rglob("locked"))
            if locked_dirs:
                if self.config["DeveloperMode"]:
                    print(f"Detected locked direcorties in {ana_path} prior to starting ExploreASL. Removing.")
                for lock_dir in locked_dirs:
                    try:
                        lock_dir.rmdir()
                    except OSError as lock_err:  # Just in case a user tampers with the lock directory
                        print(f"{lock_err}...but proceeding to recursive delete")
                        rmtree(path=lock_dir, ignore_errors=True)

            # Abort if no viable workload was detected
            if not workload or len(expected_status_files) == 0:
                robust_qmsg(self, title=self.exec_errs["NoWorkloadDetected"][0],
                            body=self.exec_errs["NoWorkloadDetected"][1], variables=[str(ana_path)])
                # self.set_widgets_activation_states(True)
                return

            # progressbar.reset_colnames()
            progressbar.setMaximum(workload)
            progressbar.setMaximum(workload)
            progressbar.setMinimum(0)
            progressbar.setValue(0)
            progressbar.setPalette(self.green_palette)
            del workload

            # Save the expected status files to the dict container; these will be iterated over after workers are done
            self.expected_status_files[ana_path] = expected_status_files
            if self.config["DeveloperMode"]:
                print(f"EXPECTED STATUS FILES TO BE GENERATED FOR STUDY: {str(ana_path)}")
                pprint(expected_status_files)

            # %%%%%%%%%%%%%%%%%%%%%%%%%%%
            # Step 5 - Create a Watcher for that study
            watcher = ExploreASL_Watcher(target=path.text(),  # the analysis directory
                                         regex=str_regex,  # the regex used to recognize subjects
                                         watch_debt=debt,  # the debt used to determine when to stop watching
                                         study_idx=study_idx,
                                         # the identifier used to know which progressbar to signal
                                         translators=self.exec_translators,
                                         config=self.config,
                                         anticipated_paths=set(expected_status_files),
                                         datapar_dict=parms
                                         )
            self.textedit_textoutput.append(f"Setting a Watcher thread on {str(ana_path)}")

            # %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
            # Step 6 - Set up watcher connections
            # Connect the watcher to signal to the text output
            watcher.signals.update_text_output_signal.connect(self.update_text)
            # Connect the watcher to signal to the progressbar
            watcher.signals.update_progbar_signal.connect(self.update_progressbar)

            # Finally, add the watcher to the container
            self.watchers.append(watcher)

            # %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
            # Step 7 - Set up worker connections
            # Worker connections setup within a study
            for idx, worker in enumerate(inner_worker_block):
                # Connect the finished signal to the watcher debt to help it understand when it should stop watching
                worker.signals.finished_processing.connect(watcher.increment_debt)
                worker.signals.encountered_fatal_error.connect(watcher.increment_debt)
                # Connect the finished signal to the run btn reactivator so that the run button may be reactivated
                # via debt repayment counter
                worker.signals.finished_processing.connect(self.update_process_debt_and_check_done)
                worker.signals.encountered_fatal_error.connect(self.update_process_debt_and_check_done)
                # Connect the error encountered signal to the slot that updates the executor's track record of the
                # accounted for errors
                worker.signals.stdout_processing_error.connect(self.update_stdout_error_dicts)
                worker.signals.stderr_processing_error.connect(self.update_stderr_error_dicts)
                # Connect the stop button for that study to its terminator function
                stop_btn.clicked.connect(worker.terminate_run)

                # Pause and Resume Signals
                pause_btn.clicked.connect(worker.pause_run)
                worker.signals.received_pause.connect(self.textedit_textoutput.append)

                resume_btn.clicked.connect(worker.resume_run)
                worker.signals.received_resume.connect(self.textedit_textoutput.append)

                self.textedit_textoutput.append(
                    f"Preparing Worker {idx + 1} of {len(inner_worker_block)} for study:\n{ana_path}")

        ######################################
        # THIS IS NOW OUTSIDE OF THE FOR LOOPS

        # self.watchers is nested at this point; we need to flatten it
        self.workers = list(chain(*self.workers))

        # Launch all threads in one go
        for runnable in self.workers + self.watchers:
            self.threadpool.start(runnable)

        self.set_widgets_activation_states(False)

        self.begin_movie()


class ExploreASL_WatcherSignals(QObject):
    """
    Defines the signals avaliable from a running watcher thread.
    """
    update_progbar_signal = Signal(int, int)
    update_text_output_signal = Signal(str)
    update_debt_signal = Signal(int)


# noinspection PyCallingNonCallable
class ExploreASL_Watcher(QRunnable):
    """
    Modified file system watcher. Will monitor the appearance of STATUS files within the lock dirs of the analysis
    directory. If it detects a STATUS file, it will emit signals to:
    1) update the progress bars
    2) inform the text editor view of which STATUS file was made so as to give user feedback
    3)
    """

    def __init__(self, target, regex, watch_debt, study_idx, translators, config, anticipated_paths: set,
                 datapar_dict: dict):
        super().__init__()
        self.signals = ExploreASL_WatcherSignals()
        self.dir_to_watch = Path(target) / "lock"
        self.anticipated_paths: set = anticipated_paths
        self.datapar_dict = datapar_dict

        # Regexes
        self.subject_regex = re.compile(regex)
        self.module_regex = re.compile('module_(ASL|Structural|Population)')
        delimiter = "\\\\" if system() == "Windows" else "/"
        self.asl_struct_regex = re.compile(
            f"(?:.*){delimiter}lock{delimiter}xASL_module_(?:Structural|ASL){delimiter}(.*){delimiter}"
            f"xASL_module_(?:Structural|ASL)_?(.*)?{delimiter}(.*\\.status)")
        self.pop_regex = re.compile(f"(?:.*){delimiter}lock{delimiter}xASL_module_Population{delimiter}"
                                    f"xASL_module_Population{delimiter}(.*\\.status)")

        self.watch_debt = watch_debt
        self.study_idx = study_idx
        self.config = config

        self.pop_mod_started = False
        self.struct_mod_started = False
        self.asl_mod_started = False

        self.msgs_seen: set = set()

        self.observer = Observer()
        self.event_handler = ExploreASL_EventHandler()
        self.event_handler.signals.inform_file_creation.connect(self.process_message)
        self.observer.schedule(event_handler=self.event_handler,
                               path=str(self.dir_to_watch),
                               recursive=True)

        if all([is_earlier_version(easl_dir=self.datapar_dict["MyPath"], threshold_higher=120, higher_eq=False),
                len(list(self.dir_to_watch.parent.glob("*/*FLAIR*"))) == 0
                ]):
            self.struct_status_file_translator = translators["Structural_Module_Filename2Description_PRE120_NOFLAIR"]
        else:
            self.struct_status_file_translator: dict = translators["Structural_Module_Filename2Description"]
        if is_earlier_version(easl_dir=self.datapar_dict["MyPath"], threshold_higher=140, higher_eq=False):
            self.asl_status_file_translator: dict = translators["ASL_Module_Filename2Description_PRE140"]
        else:
            self.asl_status_file_translator: dict = translators["ASL_Module_Filename2Description"]

        self.pop_status_file_translator: dict = translators["Population_Module_Filename2Description"]
        self.workload_translator: dict = translators["ExploreASL_Filename2Workload"]
        if self.config["DeveloperMode"]:
            print(
                f"Initialized a watcher for the directory {self.dir_to_watch} "
                f"and will communicate with the progressbar at Python idx: {self.study_idx}")

    def determine_skip(self, which_dict, created_status_path: Path, subject=None, run=None):
        msgs_to_return = []
        # Choose the appropriate translator dictionary first and create an iterator out of it
        if which_dict == "ASL":
            iterator = iter(self.asl_status_file_translator.items())
        elif which_dict == "Structural":
            iterator = iter(self.struct_status_file_translator.items())
        else:
            iterator = iter(self.pop_status_file_translator.items())

        # First, exhaust the iterator until the current file is reached
        next_file, next_description = next(iterator)
        while next_file != created_status_path.name:
            next_file, next_description = next(iterator)

        # Then, keep appending msgs until a nonexistant file is reached
        for statusfile_key, description in iterator:
            if created_status_path.with_name(statusfile_key).exists():
                created_time = datetime.fromtimestamp(created_status_path.with_name(statusfile_key).stat().st_ctime)
                # Omit recently-created files that may appear out of a race condition
                if (datetime.now() - created_time).seconds < 10:
                    continue

                if which_dict == "ASL":
                    msgs_to_return.append(f"Skipping {description} for subject {subject} ; run {run}")
                elif which_dict == "Structural":
                    msgs_to_return.append(f"Skipping {description} for subject {subject}")
                elif which_dict == "Population":
                    msgs_to_return.append(f"Skipping {description}")
            else:
                break

        return msgs_to_return

    # Processes the information sent from the event hander and emits signals to update widgets in the main Executor
    @Slot(str)
    def process_message(self, created_path):
        if self.config["DeveloperMode"]:
            print(f"Watcher process_message received message: {created_path}")

        if created_path in self.msgs_seen:
            return
        else:
            self.msgs_seen.add(created_path)

        detected_subject = self.subject_regex.search(created_path)
        detected_module = self.module_regex.search(created_path)

        created_path = Path(created_path)
        msg = None
        workload_val = None
        files_to_skip = []

        if created_path.is_dir():  # Lock dir
            n_statfile = len(list(created_path.parent.glob("*.status")))
            if detected_module.group(1) == "Structural" and n_statfile < len(self.struct_status_file_translator.keys()):
                msg = f"Structural Module has started for subject: {detected_subject.group()}"
            elif detected_module.group(1) == "ASL" and n_statfile < len(self.asl_status_file_translator.keys()):
                msg = f"ASL Module has started for subject: {detected_subject.group()}"
            elif detected_module.group(1) == "Population" and not self.pop_mod_started:
                self.pop_mod_started = True
                msg = f"Population Module has started"
            else:
                pass

        elif created_path.is_file():  # Status file
            if detected_module.group(1) == "Structural" and detected_subject:
                msg = f"Completed {self.struct_status_file_translator[created_path.name]} in the Structural module " \
                      f"for subject: {detected_subject.group()}"
                # files_to_skip = self.determine_skip(which_dict="Structural", created_status_path=created_path,
                #                                     subject=detected_subject.group())
            elif detected_module.group(1) == "ASL" and detected_subject:
                run = self.asl_struct_regex.search(str(created_path)).group(2)
                msg = f"Completed {self.asl_status_file_translator[created_path.name]} in the ASL module " \
                      f"for subject: {detected_subject.group()} ; run: {run}"
                # files_to_skip = self.determine_skip(which_dict="ASL", created_status_path=created_path,
                #                                     subject=detected_subject.group(), run=run)
            elif detected_module.group(1) == "Population":
                msg = f"Completed {self.pop_status_file_translator[created_path.name]} in the Population module"
                files_to_skip = self.determine_skip(which_dict="Population", created_status_path=created_path)

            workload_val = self.workload_translator[created_path.name]

        else:
            print(f"Neither a file nor a directory was detected: {str(created_path)=}")

        # Emit the message to inform the user of the most recent progress
        if msg:
            self.signals.update_text_output_signal.emit(msg)
            # print(f"{files_to_skip=}")
            if len(files_to_skip) > 0:
                for file_msg in files_to_skip:
                    self.signals.update_text_output_signal.emit(file_msg)

        # Avoid emitting workload values for anything that was not an anticipated path
        if created_path not in self.anticipated_paths:
            return

        # Emit the workload value associated with the completion of that status file as well as the study idx so that
        # the appropriate progressbar is updated
        if workload_val:
            self.signals.update_progbar_signal.emit(workload_val, self.study_idx)

    # Must use slots system, as it is thread-safe
    @Slot()
    def increment_debt(self):
        self.watch_debt += 1

    def run(self):
        self.observer.start()
        if self.config["DeveloperMode"]:
            print(f"THE WATCHER FOR {self.dir_to_watch} HAS STARTED")
        while self.watch_debt < 0:
            sleep(10)
        self.observer.stop()
        self.observer.join()
        if self.config["DeveloperMode"]:
            print(f"THE WATCHER FOR {self.dir_to_watch} IS SHUTTING DOWN")
        return


class ExploreASL_EventHanderSignals(QObject):
    """
    Defines the signals used by the EventHandler class
    """
    inform_file_creation = Signal(str)


class ExploreASL_EventHandler(FileSystemEventHandler):
    """
    The real watcher behind the scenes
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.signals = ExploreASL_EventHanderSignals()

    def on_created(self, event):
        self.signals.inform_file_creation.emit(event.src_path)


class RowAwareQPushButton(QPushButton):
    """
    A subset of QPushButton that has awareness of which row within Task Scheduler it is located in at all times. This
    is a convenience measure for easily communicating to self.set_analysis_directory and knowing which lineedit to
    alter.
    """
    row_idx_signal = Signal(int)

    def __init__(self, row_idx, text, parent=None):
        super().__init__(text=text, parent=parent)
        self.row_idx = row_idx

    def mousePressEvent(self, e):
        self.row_idx_signal.emit(self.row_idx)
