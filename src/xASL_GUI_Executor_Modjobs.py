from PySide2.QtWidgets import *
from PySide2.QtGui import Qt, QFont
from PySide2.QtCore import Signal
from src.xASL_GUI_HelperClasses import DandD_FileExplorer2LineEdit, DandD_FileExplorer2ListWidget
from src.xASL_GUI_HelperFuncs_DirOps import *
import pandas as pd
from functools import partial
from pathlib import Path
from pprint import pprint
from json import load, dump


class xASL_GUI_ModSidecars(QWidget):
    """
    Class designated to altering JSON sidecars
    """

    def __init__(self, parent=None):
        # Main Standard Setup
        super(xASL_GUI_ModSidecars, self).__init__(parent=parent)
        self.parent = parent
        self.setWindowFlag(Qt.Window)
        self.setWindowTitle("Explore ASL - Modify JSON sidecars")
        self.setMinimumSize(400, 720)
        self.root_dir = Path(self.parent.le_modjob.text())
        self.mainlay = QVBoxLayout(self)

        # Grp 1 - Editing Jsons from a csv config file
        self.grp_fromfile = QGroupBox("Specify config from a CSV file", checkable=True, checked=True)
        self.grp_fromfile.clicked.connect(partial(self.ctrl_which_option, widget=self.grp_fromfile))
        self.grp_fromfile.clicked.connect(self.is_ready)
        self.formlay_fromfile = QFormLayout(self.grp_fromfile)
        self.hlay_fromfile = QHBoxLayout()
        self.le_fromfile = DandD_FileExplorer2LineEdit(acceptable_path_type="File",
                                                       supported_extensions=[".csv", ".tsv"])
        self.le_fromfile.setClearButtonEnabled(True)
        self.le_fromfile.textChanged.connect(self.is_ready)
        self.btn_fromfile = QPushButton("...", clicked=self.select_file)
        self.hlay_fromfile.addWidget(self.le_fromfile)
        self.hlay_fromfile.addWidget(self.btn_fromfile)
        self.formlay_fromfile.addRow(self.hlay_fromfile)

        # Grp 2 - Editing Jsons from a list of subjects and the indicated key + value
        self.grp_fromlist = QGroupBox("Specify subject list", checkable=True, checked=False)
        self.grp_fromlist.clicked.connect(partial(self.ctrl_which_option, widget=self.grp_fromlist))
        self.grp_fromlist.clicked.connect(self.is_ready)
        self.formlay_fromlist = QFormLayout(self.grp_fromlist)
        self.lab_subs = QLabel("Drag and drop the directories of the subjects\n"
                               "whose json sidecars should be altered")
        self.lst_subs = DandD_FileExplorer2ListWidget()
        self.lst_subs.itemsAdded.connect(self.le_fromfile.clear)
        self.lst_subs.itemsAdded.connect(self.is_ready)
        self.btn_clearsubjects = QPushButton("Clear the above list", clicked=self.lst_subs.clear)
        self.btn_clearsubjects.clicked.connect(self.is_ready)
        self.le_key = QLineEdit(placeholderText="Specify the name of the field to be changed", clearButtonEnabled=True)
        self.le_key.textChanged.connect(self.is_ready)
        self.le_value = QLineEdit(placeholderText="Specify the value, if applicable", clearButtonEnabled=True)
        for widget in [self.lab_subs, self.lst_subs, self.btn_clearsubjects, self.le_key, self.le_value]:
            self.formlay_fromlist.addRow(widget)

        # Grp 3 - Other Settings
        self.grp_runsettings = QGroupBox("Run Settings")
        self.formlay_runsettings = QFormLayout(self.grp_runsettings)
        self.cmb_actiontype = QComboBox()
        self.cmb_actiontype.addItems(["Add/Edit a field", "Remove a field"])
        self.cmb_actiontype.currentIndexChanged.connect(self.is_ready)
        self.chk_asl = QCheckBox(checked=True)
        self.chk_asl.stateChanged.connect(self.is_ready)
        self.chk_m0 = QCheckBox(checked=False)
        self.chk_m0.stateChanged.connect(self.is_ready)
        self.chk_t1 = QCheckBox(checked=False)
        self.chk_t1.stateChanged.connect(self.is_ready)
        self.btn_run = QPushButton("Alter JSON sidecars", clicked=self.alter_json_sidecars)
        self.btn_run.setEnabled(False)
        for widget, desc in zip([self.cmb_actiontype,
                                 self.chk_asl, self.chk_m0, self.chk_t1, self.btn_run],
                                ["Which action to perform",
                                 "Do this for ASL JSONs", "Do this for M0 JSONs", "Do this for T1 JSONs", ""]):
            self.formlay_runsettings.addRow(widget) if desc == "" else self.formlay_runsettings.addRow(desc, widget)

        # Put it all together
        for grp in [self.grp_fromfile, self.grp_fromlist, self.grp_runsettings]:
            self.mainlay.addWidget(grp)

    def ctrl_which_option(self, widget):
        if widget == self.grp_fromlist:
            self.grp_fromfile.setChecked(False)
        elif widget == self.grp_fromfile:
            self.grp_fromlist.setChecked(False)

    def select_file(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select the CSV Config File", self.parent.config["DefaultRootDir"],
                                              "Comma/Tab-Separated Values (*.csv | *.tsv)")
        if file == "":
            return
        self.le_fromfile.setText(str(Path(file)))

    def is_ready(self):
        if any([all([not self.chk_asl.isChecked(), not self.chk_t1.isChecked(), not self.chk_m0.isChecked()]),
                self.grp_fromfile.isChecked() and self.le_fromfile.text() in ["~", "/", ".", ""],
                self.grp_fromfile.isChecked() and not Path(self.le_fromfile.text()).exists(),
                self.grp_fromlist.isChecked() and self.lst_subs.count() == 0,
                self.grp_fromlist.isChecked() and self.le_key.text() == ""]):
            self.btn_run.setEnabled(False)
        else:
            self.btn_run.setEnabled(True)

    def alter_json_sidecars(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)

        # Ascertain which types of scans to search for regardless of method
        which_scans = []
        for scan_type, widget in zip(["asl", "t1", "m0"], [self.chk_asl, self.chk_t1, self.chk_m0]):
            if widget.isChecked():
                which_scans.append(scan_type)
        del scan_type, widget

        # User wishes to alter sidecars using a pre-configured csv file
        if self.grp_fromfile.isChecked():
            for scan_type in which_scans:
                alter_sidecars(root_dir=self.root_dir, subjects=self.le_fromfile.text(), which_scan=scan_type,
                               action="remove" if self.cmb_actiontype.currentText() == "Remove a field" else "alter")
        # User wishes to alter sidecars using the drag & drop list
        else:
            # Get the list of subjects
            subs = []
            for idx in range(self.lst_subs.count()):
                sub_name = self.lst_subs.item(idx).text()
                if (self.root_dir / sub_name).exists():
                    subs.append(sub_name)
            if len(subs) == 0:
                QApplication.restoreOverrideCursor()
                QMessageBox.warning(self, self.parent.exec_errs["SubjectsNotFound"][0],
                                    self.parent.exec_errs["SubjectsNotFound"][1], QMessageBox.Ok)
                return

            for scan_type in which_scans:
                alter_sidecars(root_dir=self.root_dir, subjects=subs, which_scan=scan_type,
                               action="remove" if self.cmb_actiontype.currentText() == "Remove a field" else "alter",
                               key=self.le_key.text(), value=interpret_value(self.le_value.text()))
        # Afterwards...
        QMessageBox.information(self, "Finished json sidecar operation",
                                "Completed the requested json sidecar operation on the indicated subjects",
                                QMessageBox.Ok)
        QApplication.restoreOverrideCursor()
        return


class xASL_GUI_RerunPrep(QWidget):
    """
    Class designated to delete STATUS and other files such that a re-run of a particular module may be possible
    """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.parent = parent
        self.root_dir = Path(self.parent.le_modjob.text())
        self.setWindowFlag(Qt.Window)
        self.setWindowTitle("Explore ASL - Re-run setup")
        self.setMinimumSize(400, 720)
        self.mainlay = QVBoxLayout(self)
        self.directory_struct = dict()
        self.directory_struct["lock"] = self.get_path_directory_structure(self.root_dir / "lock")

        self.lock_tree = QTreeWidget(self)
        self.lock_tree.setToolTip(self.parent.exec_tips["Modjob_RerunPrep"]["lock_tree"])
        self.fill_tree(self.lock_tree.invisibleRootItem(), self.directory_struct)
        self.lock_tree.expandToDepth(2)
        self.lock_tree.itemChanged.connect(self.change_check_state)
        self.lock_tree.setHeaderLabel("Select the directories that should be redone")

        self.btn = QPushButton("Remove selected .status files", self, clicked=self.remove_status_files)
        self.btn.setMinimumHeight(50)
        font = QFont()
        font.setPointSize(14)
        self.btn.setFont(font)

        self.mainlay.addWidget(self.lock_tree)
        self.mainlay.addWidget(self.btn)

    def get_path_directory_structure(self, rootdir: Path):
        directory = {}
        for path in sorted(rootdir.iterdir()):
            if path.is_dir():
                directory[path.name] = self.get_path_directory_structure(path)
            else:
                directory[path.name] = None
        return directory

    def fill_tree(self, parent, d):
        if isinstance(d, dict):
            for key, value in d.items():
                it = QTreeWidgetItem()
                it.setText(0, key)
                if isinstance(value, dict):
                    parent.addChild(it)
                    it.setCheckState(0, Qt.Unchecked)
                    self.fill_tree(it, value)
                else:
                    parent.addChild(it)
                    it.setCheckState(0, Qt.Unchecked)

    @staticmethod
    def change_check_state(item: QTreeWidgetItem, col: int):
        if item.checkState(col):
            for idx in range(item.childCount()):
                item_child = item.child(idx)
                item_child.setCheckState(0, Qt.Checked)
        else:
            for idx in range(item.childCount()):
                item_child = item.child(idx)
                item_child.setCheckState(0, Qt.Unchecked)

    def return_filepaths(self):
        all_status = self.lock_tree.findItems(".status", (Qt.MatchEndsWith | Qt.MatchRecursive), 0)
        selected_status: List[QTreeWidgetItem] = [status for status in all_status if status.checkState(0)]
        filepaths: List[Path] = []

        for status in selected_status:
            filepath: List[str] = [status.text(0)]
            parent = status.parent()
            while parent.text(0) != "lock":
                filepath.insert(0, parent.text(0))
                parent = parent.parent()
            filepath.insert(0, "lock")
            filepaths.append(self.root_dir.joinpath(*filepath))

        return filepaths, selected_status

    def remove_status_files(self):
        filepaths, treewidgetitems = self.return_filepaths()
        if self.parent.config["DeveloperMode"]:
            print(f"REMOVING THE FOLLOWING STATUS FILES:")
            pprint(filepaths)

        for filepath in filepaths:
            filepath.unlink(missing_ok=True)

        # Clear the tree
        self.lock_tree.clear()
        # Refresh the file structure
        self.directory_struct.clear()
        self.directory_struct["lock"] = self.get_path_directory_structure(self.root_dir / "lock")
        # Refresh the tree
        self.fill_tree(self.lock_tree.invisibleRootItem(), self.directory_struct)
        self.lock_tree.expandToDepth(2)
        self.lock_tree.itemChanged.connect(self.change_check_state)

        QMessageBox.information(self.parent,
                                f"Re-run setup complete",
                                f"Successfully deleted the indicated .status files for the study:\n"
                                f"{self.root_dir}",
                                QMessageBox.Ok)


# noinspection PyAttributeOutsideInit
class xASL_GUI_TSValter(QWidget):
    """
    Class designated to alter the contents of participants.tsv
    """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.parent = parent
        self.config = parent.config
        self.target_dir = self.parent.le_modjob.text()
        self.setWindowFlag(Qt.Window)
        self.setWindowTitle("Alter participants.tsv contents")
        self.mainlay = QVBoxLayout(self)

        # Misc variables
        self.default_tsvcols = []
        self.default_covcols = []

        # First section, the loading of the covariate file
        self.formlay_covfile = QFormLayout()
        self.hlay_covfile = QHBoxLayout()
        self.le_covfile = DandD_FileExplorer2LineEdit(acceptable_path_type="File",
                                                      supported_extensions=[".tsv", ".xlsx", ".csv"])
        self.le_covfile.textChanged.connect(self.load_covariates_data)
        self.btn_covfile = QPushButton("...", self)
        self.hlay_covfile.addWidget(self.le_covfile)
        self.hlay_covfile.addWidget(self.btn_covfile)
        self.formlay_covfile.addRow("Covariates File", self.hlay_covfile)

        # Second section, the Drag and Drop listviews
        self.hlay_dandcols = QHBoxLayout()
        self.vlay_covcols = QVBoxLayout()
        self.lab_covcols = QLabel(text="Covariates")
        self.list_covcols = QListWidget(self)
        self.list_covcols.setDragEnabled(True)  # This will have covariate names dragged from it
        self.list_covcols.setDefaultDropAction(Qt.MoveAction)
        self.vlay_covcols.addWidget(self.lab_covcols)
        self.vlay_covcols.addWidget(self.list_covcols)

        self.vlay_tsvcols = QVBoxLayout()
        self.lab_tsvcols = QLabel(text="TSV Variables")
        self.list_tsvcols = ColnamesDragDrop_ListWidget(self)
        self.list_tsvcols.setAcceptDrops(True)  # This will have covariate names dropped into it
        self.vlay_tsvcols.addWidget(self.lab_tsvcols)
        self.vlay_tsvcols.addWidget(self.list_tsvcols)

        self.hlay_dandcols.addLayout(self.vlay_covcols)
        self.hlay_dandcols.addLayout(self.vlay_tsvcols)

        # Third section, just the main buttons
        self.btn_altertsv = QPushButton("Commit changes", clicked=self.commit_changes)
        self.btn_reset = QPushButton("Reset to original participants.tsv", clicked=self.reset_changes)

        self.mainlay.addLayout(self.formlay_covfile)
        self.mainlay.addLayout(self.hlay_dandcols)
        self.mainlay.addWidget(self.btn_altertsv)
        self.mainlay.addWidget(self.btn_reset)

        # Once the widget UI is set up, load in the tsv data
        self.load_tsv_data()

    def reset_changes(self):
        # If changes have already been committed, remove the current participants_orig.tsv and rename the _orig backup
        # back into participants.tsv, thereby restoring things to normal
        part_orig_path = Path(self.target_dir) / "participants_orig.tsv"
        part_path = part_orig_path.with_name("participants.tsv")
        if part_orig_path.exists():
            part_path.unlink(missing_ok=True)
            part_orig_path.rename(part_path)

        # Restore the lists
        self.list_covcols.clear()
        self.list_covcols.addItems(self.default_covcols)
        self.load_tsv_data()

    def load_tsv_data(self):
        part_path = Path(self.target_dir) / "particiants.tsv"
        tsv_df = pd.read_csv(part_path, sep='\t')
        tsv_df.drop(labels=[col for col in tsv_df.columns if "Unnamed" in col], axis=1, inplace=True)
        self.tsv_df = tsv_df

        # Set the listwidget to contain the column names here
        tsv_colnames = self.tsv_df.columns.tolist()

        # Re-define the loaded data as the new defaults
        self.default_tsvcols = tsv_colnames

        # In case this is a re-load, clear the previous items in this list an try again
        self.list_tsvcols.clear()
        self.list_tsvcols.addItems(tsv_colnames)

    def load_covariates_data(self, cov_filepath: str):
        if cov_filepath == "":
            return

        cov_filepath = Path(cov_filepath)

        # Prevent loading of the participants.tsv file itself as covariates
        if cov_filepath.name in ["participants.tsv", "participants_orig.tsv"]:
            self.le_covfile.clear()
            return

        # Note to self: no further QC checks needed because the le_covfile is a DandDFileExplorer2LineEdit;
        # this will already have the "File" and supported_extensions addressed

        # Load in the data
        if cov_filepath.name.endswith('.tsv'):
            df = pd.read_csv(cov_filepath, sep='\t')
        elif cov_filepath.name.endswith('.csv'):
            df = pd.read_csv(cov_filepath)
        else:
            df = pd.read_excel(cov_filepath)

        # Second set of checks: Dataframe must be the same length for proper concatenation
        if len(df) != len(self.tsv_df):
            QMessageBox().warning(self, "Incompatible Dataframes",
                                  f"The number of entires of the covariates dataframe: {len(df)}\n"
                                  f"did not equal the number of entries in participants.tsv: {len(self.tsv_df)}",
                                  QMessageBox.Ok)
            self.le_covfile.clear()
            return

        # Drop any columns already found in the participants.tsv df
        for col in df.columns:
            if col in self.tsv_df.columns.tolist():
                df.drop(labels=col, axis=1, inplace=True)

        self.cov_df = df

        # Set the listwidget to contain the column names here
        cov_colnames = self.cov_df.columns.tolist()
        self.list_covcols.clear()
        self.list_covcols.addItems(cov_colnames)
        self.default_covcols = cov_colnames

        # Also reset the tsv columns
        self.list_tsvcols.clear()
        print(f"default tsv cols: {self.default_tsvcols}")
        self.list_tsvcols.addItems(self.default_tsvcols)

    def commit_changes(self):
        commit_df = pd.DataFrame()

        # Iterate over the labels in the tsv listwidget.
        for idx in range(self.list_tsvcols.count()):
            colname = self.list_tsvcols.item(idx).text()

            # Check which dataframe it is in, then add that dataframe's column contents to the commit_df
            if colname not in self.tsv_df.columns:
                commit_df[colname] = self.cov_df[colname].values
            else:
                commit_df[colname] = self.tsv_df[colname].values

        # If the _orig backup hasn't been made from the original, make it at this point in time.
        part_orig_path = Path(self.target_dir) / "participants_orig.tsv"
        part_path = part_orig_path.with_name("participants.tsv")
        if not part_orig_path.exists():
            try:
                part_path.replace(part_orig_path)
            except OSError:
                QMessageBox().warning(self,
                                      "Could not create a backup participants_orig.tsv from the original",
                                      "It is likely that participants.tsv is opened in another program. "
                                      "Please close that program and try committing again.",
                                      QMessageBox.Ok)
                return

        # Overwrite participants.tsv
        try:
            commit_df.to_csv(path_or_buf=part_path, sep='\t', index=False)
        except OSError:
            QMessageBox().warning(self,
                                  "Could not commit changes to participants.tsv",
                                  "It is likely that the file is opened in another program. "
                                  "Please close that program and try committing again.",
                                  QMessageBox.Ok)


class ColnamesDragDrop_ListWidget(QListWidget):
    """
    Class meant to drag and drop items between themselves
    """
    alert_regex = Signal()  # This will be called in the ParmsMaker superclass to update its regex

    def __init__(self, parent=None):
        super().__init__(parent)
        # self.setDragDropMode(QAbstractItemView.DragDrop)
        # self.setDefaultDropAction(Qt.MoveAction)  # this was the magic line
        # self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.colnames = []

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat('application/x-qabstractitemmodeldatalist'):
            print(event.mimeData().text())
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasFormat('application/x-qabstractitemmodeldatalist'):
            event.setDropAction(Qt.MoveAction)
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        if event.mimeData().hasFormat('application/x-qabstractitemmodeldatalist'):
            event.accept()
            for item in event.source().selectedItems():
                self.addItem(item.text())
        else:
            event.ignore()
