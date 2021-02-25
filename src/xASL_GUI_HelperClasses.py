from PySide2.QtWidgets import (QLineEdit, QAbstractItemView, QListWidget, QPushButton, QHBoxLayout, QComboBox,
                               QDoubleSpinBox, QFormLayout)
from PySide2.QtCore import Qt, Signal, QModelIndex, QSize
from PySide2.QtGui import QFont, QIcon
import os
from pathlib import Path
from collections import deque


# Credit to ekhumoro @ stackoverflow for initial clarification of how to set this up
# https://stackoverflow.com/questions/66232460/pyside2-how-to-re-implement-qformlayout-takerow
class xASL_FormLayout(QFormLayout):
    def __init__(self, has_cache: bool = True, maxlen: int = None, *args, **kwargs):
        super(xASL_FormLayout, self).__init__(*args, **kwargs)
        self.has_cache = has_cache
        if self.has_cache:
            self.cache = deque(maxlen=maxlen) if maxlen is not None else deque()

    def takeRow(self, row: int):
        label_item = self.itemAt(row, QFormLayout.LabelRole)
        field_item = self.itemAt(row, QFormLayout.FieldRole)
        label = None
        # IMPORTANT: Get refs before removal
        if label_item is not None:
            label = label_item.widget()
        try:
            field = field_item.layout()
            is_layout = True
        except AttributeError:
            field = field_item.widget()
            is_layout = False
        # Remove widgets
        if label_item is not None:
            self.removeItem(label_item)
        self.removeItem(field_item)
        self.removeRow(row)
        # Set their parents to None to make them disappear
        if label_item is not None:
            label.setParent(None)
        if is_layout:
            index = field.count()
            while index > 0:
                child = field.itemAt(index - 1).widget()
                child.setParent(None)
                index -= 1

        field.setParent(None)

        # Save to the cache from the ability to be restored
        if self.has_cache:
            self.cache.append((label, field))
        return label, field

    def restoreRow(self, insert_idx: int, fifo: bool = True):
        if not self.has_cache:
            return
        if (-1 * self.rowCount()) < insert_idx < 0:
            insert_idx = self.rowCount() + 1 + insert_idx
        to_insert = self.cache.pop() if fifo else self.cache.popleft()
        if to_insert[0] is not None:
            self.insertRow(insert_idx, to_insert[0], to_insert[1])
        else:
            self.insertRow(insert_idx, to_insert[1])


class DandD_Graphing_ListWidget2LineEdit(QLineEdit):
    """
    Modified QLineEdit to support accepting text drops from a QListWidget or QAbstractItemModel derivatives
    """

    def __init__(self, postproc_widget, dtype_list, parent=None):
        # print(dtype_list)
        super().__init__(parent)
        self.permitted_dtypes = dtype_list
        self.setAcceptDrops(True)
        self.setClearButtonEnabled(True)
        self.PostProc_widget = postproc_widget

    def dragEnterEvent(self, event) -> None:
        # print(event.mimeData().formats())
        if event.mimeData().hasFormat("application/x-qabstractitemmodeldatalist"):
            event.accept()
        else:
            event.ignore()
            print("dragEnterEvent ignored")

    def dragMoveEvent(self, event) -> None:
        # print(event.mimeData().formats())
        if event.mimeData().hasFormat("application/x-qabstractitemmodeldatalist"):
            event.setDropAction(Qt.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        if all([event.mimeData().hasFormat("application/x-qabstractitemmodeldatalist"),
                isinstance(event.source(), QAbstractItemView)]):
            # Get the text that has been dragged
            ix: QModelIndex = event.source().currentIndex()
            colname = ix.data()

            # Get the current data types of the loaded data
            data_dtypes = {col: str(name) for col, name in
                           self.PostProc_widget.loader.long_data.dtypes.to_dict().items()}
            # print(f"The dtypes of the current dataframe are: {data_dtypes}")
            # print(f"For column: {colname}, the detected datatype was: {data_dtypes[colname]}")
            # print(f"The permitted dtypes for this widget are: {self.permitted_dtypes}")
            if data_dtypes[colname] in self.permitted_dtypes:
                event.accept()
                self.setText(colname)
            else:
                event.ignore()
        else:
            event.ignore()


class DandD_FileExplorer2LineEdit(QLineEdit):
    def __init__(self, parent=None, acceptable_path_type: str = "Both", supported_extensions: list = None, **kwargs):
        """
        Modified QLineEdit to support accepting text drops from a file explorer

        :param parent: The parent widget of this modified QLineEdit
        :param acceptable_path_type: The type of filepath this QLineEdit will accept:
            - "File"
            - "Directory"
            - "Both"
        :param supported_extensions: a list of the filetypes that this lineedit will accept (i.e ".csv" , ".txt" )
        :param kwargs: other keyword arguments that would be fed into the QLineEdit constructor
        """
        super().__init__(parent, **kwargs)
        self.setAcceptDrops(True)
        self.path_type = acceptable_path_type
        if supported_extensions is None or supported_extensions == "All":
            self.supported_ext = []
        else:
            self.supported_ext = supported_extensions

        # Quality Control
        if acceptable_path_type not in ["File", "Directory", "Both"]:
            raise ValueError("acceptable_path_type must be one of: 'File', 'Directory', or 'Both'")

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    if not os.path.exists(url.toLocalFile()):
                        continue
                    else:
                        path_string = str(url.toLocalFile())

                    # Scenario 1: Accept all filetypes
                    if self.path_type == "Both" and os.path.exists(path_string):
                        event.accept()
                        return

                    # Scenario 2: Accept only Files
                    elif self.path_type == "File" and os.path.isfile(path_string):
                        if len(self.supported_ext) == 0:
                            event.accept()
                            return
                        else:
                            if os.path.splitext(path_string)[1] in self.supported_ext:
                                event.accept()
                                return
                            else:
                                event.ignore()
                                return

                    # Scenario 3: Accept only Direcories
                    elif self.path_type == "Directory" and os.path.isdir(path_string):
                        event.accept()
                        return

                    else:
                        event.ignore()
                # Is not a local file
                else:
                    event.ignore()
            event.ignore()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.accept()
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    path = Path(str(url.toLocalFile()))

                    # Scenario 1: Accept all filetypes
                    if self.path_type == "Both" and path.exists():
                        self.setText(str(path))
                        return

                    # Scenario 2: Accept only Files
                    elif self.path_type == "File" and path.is_file():
                        if len(self.supported_ext) == 0:
                            self.setText(str(path))
                            return
                        else:
                            if path.suffix in self.supported_ext:
                                self.setText(str(path))
                                return
                            else:
                                event.ignore()

                    # Scenario 3: Accept only Direcories
                    elif self.path_type == "Directory" and path.is_dir():
                        self.setText(str(path))
                        return
                    else:
                        event.ignore()
        else:
            event.ignore()


class DandD_FileExplorer2ListWidget(QListWidget):
    """
    Class meant to accept MULTIPLE directory inputs and add them to the underlying QListWidget
    """
    itemsAdded = Signal()  # Signal that is sent whenever items are successfully added to the widget

    def __init__(self, parent=None, overwrite_on_drop=False):
        """
        Modified QListWidget intended to receive multiple
        """
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._overwrite_on_drop = overwrite_on_drop

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.accept()
            subject_directories = []
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    subject_directories.append(Path(str(url.toLocalFile())))
            # Only filter for the basenames of directories; also, avoid bringing in unnecessary directories like lock
            basenames = {directory.name for directory in subject_directories if directory.is_dir()
                         and directory.name not in ['lock', "Population"]}
            # Avoid double-dipping the names
            current_names = {self.item(idx).text() for idx in range(self.count())}
            if self._overwrite_on_drop:
                self.clear()
            self.addItems(sorted(basenames.difference(current_names)))
            self.itemsAdded.emit()
        else:
            event.ignore()


class xASL_PushButton(QPushButton):
    """
    Convenience Class in making a QPushButton
    """

    def __init__(self, parent=None, text: str = None, func: callable = None, fixed_height: int = None,
                 fixed_width: int = None, font: QFont = None, icon: QIcon = None, icon_size: QSize = None,
                 enabled: bool = None):
        super(xASL_PushButton, self).__init__()
        if parent:
            self.setParent(parent)
        if text:
            self.setText(text)
        if func:
            self.clicked.connect(func)
        if fixed_width:
            self.setFixedWidth(fixed_width)
        if fixed_height:
            self.setFixedHeight(fixed_height)
        if font:
            self.setFont(font)
        if icon and icon_size:
            self.setIcon(icon)
            self.setIconSize(icon_size)
        if enabled is not None:
            self.setEnabled(enabled)


class xASL_HBoxTwoWidgets(QHBoxLayout):
    def __init__(self, parent=None, left_wid=DandD_FileExplorer2LineEdit, right_wid=QPushButton,
                 left_kwargs: dict = None, right_kwargs=None,
                 left_method: str = None, right_method=None,
                 connect_left_to: callable = None, connect_right_to: callable = None):
        t = {"cmb": QComboBox, "le": DandD_FileExplorer2LineEdit, "spin": QDoubleSpinBox, "btn": QPushButton}
        super(xASL_HBoxTwoWidgets, self).__init__(parent=parent)

        if left_kwargs is None:
            left_kwargs = dict()
        if right_kwargs is None:
            right_kwargs = dict()
        self.l_widget = left_wid(**left_kwargs) if not isinstance(left_wid, str) else t[left_wid](**left_kwargs)
        self.r_widget = right_wid(**right_kwargs) if not isinstance(right_wid, str) else t[right_wid](**right_kwargs)
        if connect_left_to is not None and left_method is not None:
            getattr(self.l_widget, left_method).connect(connect_left_to)
        if connect_right_to is not None and right_method is not None:
            getattr(self.r_widget, right_method).connect(connect_right_to)

        self.addWidget(self.l_widget)
        self.addWidget(self.r_widget)

    def return_widgets(self):
        return self.l_widget, self.r_widget

    def setVisible(self, visible: bool):
        self.l_widget.setVisible(visible)
        self.r_widget.setVisible(visible)

    def setEnabled(self, enabled: bool):
        self.l_widget.setEnabled(enabled)
        self.r_widget.setEnabled(enabled)

    def fully_disappear(self):
        self.setVisible(False)
        self.setEnabled(False)

    def fully_reappear(self):
        self.setVisible(True)
        self.setEnabled(True)

    def connect_left(self, left_method: str, left_target: callable):
        getattr(self.l_widget, left_method).connect(left_target)

    def connect_right(self, right_method: str, right_target: callable):
        getattr(self.r_widget, right_method).connect(right_target)

    def disconnect_left(self, left_method: str):
        getattr(self.l_widget, left_method).disconnect()

    def disconnect_right(self, right_method: str):
        getattr(self.r_widget, right_method).disconnect()
