from PySide2.QtWidgets import *
from PySide2.QtGui import *
from PySide2.QtCore import *
import seaborn as sns
from xASL_GUI_Graph_MRIViewArtist import xASL_GUI_MRIViewArtist
from xASL_GUI_HelperClasses import DandD_Graphing_ListWidget2LineEdit
import json
import os

class xASL_GUI_MRIViewManager(QWidget):

    def __init__(self, parent):
        super().__init__(parent=parent)
        self.parent_cw = parent
        self.artist = self.parent_cw.fig_artist
        self.mainlay = QVBoxLayout(self)

        with open(os.path.join(self.parent_cw.config["ScriptsDir"], "JSON_LOGIC",
                               "GraphingParameters.json")) as freader:
            parms = json.load(freader)
            self.all_dtypes = parms["all_dtypes"]
            self.numeric_dtypes = parms["numeric_dtypes"]
            self.categorical_dtypes = ["object", "category"]
            self.palettenames = parms["palettenames"]
            self.default_palette_idx = self.palettenames.index("Set1")

        self.UI_Setup_Tabs()
        self.UI_Setup_ScatterParameters()

    def UI_Setup_Tabs(self):
        self.tab_pltsettings = QTabWidget()
        self.cont_scatterparms, self.cont_mriparms = QWidget(), QWidget()
        self.tab_pltsettings.addTab(self.cont_scatterparms, "Scatterplot Parameters")
        self.tab_pltsettings.addTab(self.cont_mriparms, "MRI Viewer Parameters")

        self.formlay_scatterparms = QFormLayout(self.cont_scatterparms)
        self.formlay_mriparms = QFormLayout(self.cont_mriparms)
        self.mainlay.addWidget(self.tab_pltsettings)

    def UI_Setup_ConnectManager2Artist(self):
        self.artist: xASL_GUI_MRIViewArtist = self.parent_cw.fig_artist
        if self.artist is not None:
            pass
        else:
            print("UI_Setup_Connections; the artist had a value of None")

    def UI_Setup_ScatterParameters(self):
        self.le_x = DandD_Graphing_ListWidget2LineEdit(self.parent_cw, self.numeric_dtypes)
        self.le_x.setPlaceholderText("Drag & Drop the X-axis Variable")
        self.le_y = DandD_Graphing_ListWidget2LineEdit(self.parent_cw, self.numeric_dtypes)
        self.le_y.setPlaceholderText("Drag & Drop the Y-axis Variable")
        self.le_hue = DandD_Graphing_ListWidget2LineEdit(self.parent_cw, ["object", "category"])
        self.le_hue.setPlaceholderText("Drag & Drop the Hue Grouping Variable")
        self.axes_arg_x = self.le_x.text
        self.axes_arg_y = self.le_y.text
        self.axes_arg_hue = self.le_hue.text
        self.size_grouper = DandD_Graphing_ListWidget2LineEdit(self.parent_cw, self.all_dtypes)
        self.size_grouper.setPlaceholderText("(Optional) Drag & Drop the Markersize-Grouping Variable")
        self.style_grouper = DandD_Graphing_ListWidget2LineEdit(self.parent_cw, ["object", "category"])
        self.style_grouper.setPlaceholderText("(Optional) Drag & Drop the Markerstyle-Grouping Variable")
        self.cmb_palette = self.UI_Setup_PaletteCombobox()
        self.spinbox_markersize = QDoubleSpinBox(maximum=100, minimum=0, value=40, singleStep=1)

        self.axes_kwargs = {"x": self.le_x.text, "y": self.le_y.text, "size": self.size_grouper.text,
                            "style": self.style_grouper.text, "palette": self.cmb_palette.currentText,
                            "s": self.spinbox_markersize.value}
        for description, widget in zip(["X Axis Variable", "Y Axis variable", "Hue Grouping Variable",
                                        "Size Grouping Variable", "Marker Style Grouping Variable", "Marker size",
                                        "Palette"],
                                       [self.le_x, self.le_y, self.le_hue, self.size_grouper, self.style_grouper,
                                        self.spinbox_markersize, self.cmb_palette]):
            self.formlay_scatterparms.addRow(description, widget)

    ##########################################################
    # Functions for SetupUI convenience and codeline reduction
    ##########################################################
    # Convenience function to generate the combobox that will respond to palette changes
    def UI_Setup_PaletteCombobox(self):
        cmb_palette = QComboBox()
        cmb_palette.addItems(self.palettenames)
        cmb_palette.setMaxVisibleItems(10)
        cmb_palette.setEditable(True)
        cmb_palette.setCurrentIndex(self.default_palette_idx)
        if len(self.parent_cw.loader.long_data) > 2000:
            cmb_palette.setAutoCompletion(False)
        return cmb_palette