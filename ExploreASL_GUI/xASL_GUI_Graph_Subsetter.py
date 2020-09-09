from PySide2.QtWidgets import QWidget, QLabel, QComboBox, QFormLayout, QVBoxLayout, QMessageBox
from PySide2.QtGui import Qt, QFont
from PySide2.QtCore import Signal
# from ExploreASL_GUI.xASL_GUI_Plotting import xASL_Plotting
import pandas as pd


# noinspection PyAttributeOutsideInit
class xASL_GUI_Subsetter(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlag(Qt.Window)
        self.setWindowTitle("Subset the data")
        self.font_format = QFont()
        self.font_format.setPointSize(16)
        self.parent_cw = parent

        # This will be used to keep track of columns that have already been added to the subset form layout
        self.current_rows = {}

        # Main Setup
        self.Setup_UI_MainWidgets()

    def Setup_UI_MainWidgets(self):
        self.mainlay = QVBoxLayout(self)
        self.formlay_headers = QFormLayout()
        self.formlay_subsets = QFormLayout()
        self.lab_inform_reload = QLabel("Changes will not take place until you re-load the data")
        self.lab_inform_reload.setFont(self.font_format)
        self.formlay_headers.addRow(QLabel("Column Names"), QLabel("\t\tSubset on"))

        self.mainlay.addLayout(self.formlay_headers)
        self.mainlay.addLayout(self.formlay_subsets)
        self.mainlay.addWidget(self.lab_inform_reload)

    # Updates the current fields that are permitted to be subset.
    def update_subsetable_fields(self, df):
        """
        Updates the known fields that may be subsetted
        @param df: The dataframe being loaded in
        """
        # Always start off with a clearing of the contents
        self.clear_contents()

        colnames = df.columns
        for name in colnames:
            # Skip any column based on criteria
            if any([name in self.current_rows.keys(),  # skip if already encountered
                    str(df[name].dtype) not in ["object", "category"],  # skip if not categorical
                    name in ["SUBJECT", "SubjectNList"]  # skip some unnecessary defaults with too many categories
                    ]):
                continue

            # Otherwise, create a combobox, add it to the form layout, and add the method to the current text as a
            # value, as this will be used to
            cmb = QComboBox()
            cmb.addItems(["Select a subset"] + df[name].unique().tolist())
            self.formlay_subsets.addRow(name, cmb)
            self.current_rows[name] = cmb.currentText

    # Convenience function for purging everything in the event that either the analysis directory changes or the
    # supplementary data file provided is changed
    def clear_contents(self):
        # Clear the dict
        self.current_rows.clear()
        # Clear the rows of the format layout
        for ii in range(self.formlay_subsets.rowCount()):
            self.formlay_subsets.removeRow(0)

    # The active function that will subset the data; takes in a dataframe and subsets it
    def subset_data(self, long_df):
        for key, call in self.current_rows.items():
            if call() != "Select a subset":
                print(f"Subsetting {key} on {call()}")
                long_df = long_df.loc[long_df[key] == call(), :]

        return long_df


class xASL_GUI_Datatype_Indicator(QWidget):
    """
    Class meant to assist users with defining the datatype of their covariates
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlag(Qt.Window)
        self.setWindowTitle("Clarify Covariate Datatypes")
        self.setMinimumWidth(400)
        self.parent_cw = parent

        self.off_limits = {"Side of the Brain", "CBF", "Anatomical Area", "LongitudinalTimePoint",
                           "AcquisitionTime", "GM_vol", "WM_vol", "CSF_vol", "GM_ICVRatio", "GMWM_ICVRatio",
                           "WMH_vol", "WMH_count", "SUBJECT", "Site", "SubjectNList"}
        self.covariate_cols = {}
        self.dtypes_to_general = {
            "object": "categorical",
            "category": "categorical",
            "bool": "categorical",
            "float": "numerical",
            "float16": "numerical",
            "float32": "numerical",
            "float64": "numerical",
            "int": "numerical",
            "int8": "numerical",
            "int16": "numerical",
            "int32": "numerical",
            "int64": "numerical"}

        # Main Setup
        self.Setup_UI_MainWidgets()

    def Setup_UI_MainWidgets(self):
        self.mainlay = QVBoxLayout(self)
        self.formlay_dtypes = QFormLayout()
        self.formlay_dtypes.addRow(QLabel("Column Names"), QLabel("\t\tDatatype"))
        self.mainlay.addLayout(self.formlay_dtypes)

    def update_known_covariates(self, df):
        """
        Updates the known covariates and their datatypes during a dataload
        """
        # Always start off with a clearing of the contents
        self.clear_contents()

        # If the lineedit for the covariates dataframe file is empty during a dataload, clear everything
        if self.parent_cw.le_demographics_file.text() == '':
            return

        # Otherwise, update the widget
        recorded_datatypes = [self.dtypes_to_general[str(dtype)] for dtype in df.dtypes.tolist()]
        self.covariate_cols = dict(zip(df.columns.tolist(), recorded_datatypes))
        for colname, dtype in self.covariate_cols.items():
            if colname in self.off_limits:
                continue

            cmb = ClassAwareCombobox(column_name=colname)
            cmb.setCurrentIndex(cmb.findText(dtype))
            cmb.signal_sendupdateddtype.connect(self.update_datatype)
            self.formlay_dtypes.addRow(colname, cmb)

    def update_datatype(self, colname: str, newtype: str):
        print(f"update_datatype received a signal to update the datatype of column {colname} to dtype: {newtype}")
        if len(self.parent_cw.loader.long_data[colname].unique()) > 12 and newtype == "categorical":
            choice = QMessageBox().warning(self.parent_cw,
                                           "Confirm intended conversion",
                                           "You are converting a numerical into a categorical with more than 12 levels "
                                           "resulting from the conversion. This may cause instabilities when plotting. "
                                           "Proceed?",
                                           QMessageBox.Yes, QMessageBox.No)
            if choice == QMessageBox.Yes:
                newtype = {"numerical": "float32", "categorical": "category"}[newtype]
                self.parent_cw.loader.long_data[colname] = self.parent_cw.loader.long_data[colname].astype(newtype)
            else:
                return
        else:
            newtype = {"numerical": "float32", "categorical": "category"}[newtype]
            self.parent_cw.loader.long_data[colname] = self.parent_cw.loader.long_data[colname].astype(newtype)

    # Convenience function for purging everything in the event that either the analysis directory changes or the
    # supplementary data file provided is changed
    def clear_contents(self):
        # Clear the dicts
        self.covariate_cols.clear()
        # Clear the rows of the format layout
        for ii in range(self.formlay_dtypes.rowCount() - 1):
            self.formlay_dtypes.removeRow(1)


class ClassAwareCombobox(QComboBox):
    signal_sendupdateddtype = Signal(str, str)

    def __init__(self, column_name, parent=None):
        super(ClassAwareCombobox, self).__init__(parent=parent)
        self.associated_column = column_name
        self.addItems(["numerical", "categorical"])
        self.currentTextChanged.connect(self.inform_update)

    def inform_update(self, new_text):
        self.signal_sendupdateddtype.emit(self.associated_column, new_text)
