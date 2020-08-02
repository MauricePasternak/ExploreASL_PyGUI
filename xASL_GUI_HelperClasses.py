from PySide2.QtWidgets import QLineEdit, QAbstractItemView
from PySide2.QtCore import Qt
from platform import platform
import os


class DandD_ListWidget2LineEdit(QLineEdit):
    """
    Modified QLineEdit to support accepting text drops from a QListWidget or QAbstractItemModel derivatives
    """

    def __init__(self, PostProc_widget, dtype_list, parent=None):
        # print(dtype_list)
        super().__init__(parent)
        self.permitted_dtypes = dtype_list
        self.setAcceptDrops(True)
        self.PostProc_widget = PostProc_widget

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
            data_dtypes = {col: str(name) for col, name in self.PostProc_widget.long_data.dtypes.to_dict().items()}
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
    """
    Modified QLineEdit to support accepting text drops from a file explorer
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

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
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    dir_string = str(url.toLocalFile())
                    if '/' in dir_string and "windows" in platform().lower():
                        dir_string = dir_string.replace("/", "\\")
                    self.setText(dir_string)
                    return  # Only return the first local url instance if this was a from a multi-selection
        else:
            event.ignore()


class DandD_FileExplorerFile2LineEdit(QLineEdit):
    """
    Modified QLineEdit to support accepting text drops from a file explorer specifically for files, not directories.
    Has a required field to specify the filetypes it allows (specify a list of extensions, period included).
    """

    def __init__(self, supported_extensions, parent=None):
        super().__init__(parent)
        self.supported_extensions: list = supported_extensions
        self.setAcceptDrops(True)

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
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    path_string = str(url.toLocalFile())
                    if '/' in path_string and "windows" in platform().lower():
                        path_string = path_string.replace("/", "\\")

                    # print(f"Path: {path_string}\n"
                    #       f"Exists?: {os.path.exists(path_string)}\n"
                    #       f"Is file? {os.path.isfile(path_string)}\n"
                    #       f"Supported extensions: {self.supported_extensions}\n"
                    #       f"Detected extensions: {os.path.splitext(path_string)[1]}")

                    if all([os.path.exists(path_string),
                            os.path.isfile(path_string),
                            os.path.splitext(path_string)[1] in self.supported_extensions
                            ]):
                        self.setText(path_string)
                        return  # Only return the first local url instance if this was a from a multi-selection
        else:
            event.ignore()
