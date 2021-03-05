from PySide2.QtGui import QIcon, Qt
from PySide2.QtCore import QSize
from PySide2.QtWidgets import (QDoubleSpinBox, QSpinBox, QComboBox, QLineEdit, QCheckBox, QHBoxLayout, QPushButton,
                               QVBoxLayout, QScrollArea, QWidget, QFormLayout, QFileDialog, QMessageBox)
from src.xASL_GUI_HelperClasses import (DandD_Graphing_ListWidget2LineEdit, DandD_FileExplorer2LineEdit)
from typing import Tuple, Union, List
from pathlib import Path
from os import sep
from platform import system
from more_itertools import peekable, interleave_longest
import re


def set_formlay_options(formlay: QFormLayout,
                        field_growth: Union[str, QFormLayout.FieldGrowthPolicy] = QFormLayout.ExpandingFieldsGrow,
                        formside_alignment: Union[Tuple[str],
                                                  Tuple[Qt.Alignment]] = (Qt.AlignLeft, Qt.AlignTop),
                        labelside_alignment: Union[str, Qt.Alignment] = Qt.AlignLeft,
                        row_wrap_policy: Union[str, QFormLayout.RowWrapPolicy] = QFormLayout.WrapLongRows,
                        vertical_spacing: int = None,
                        horizontal_spacing: int = None) -> None:
    """
    Convenience function for setting the options for a QFormLayout

    Parameters
        • formlay: the QFormLayout widget to be altered
        • field_growth: string or FieldGrowthPolicy. For string options, acceptable strings are:
            - "at_size_hint"
            - "expanding_fields_grow"
            - "all_nonfixed_grow"
        • formside_alignment: string or Qt.Alignment. For string options, acceptable strings are:
            - "left"
            - "right"
            - "top"
            - "bottom"
            - "vcenter"
        • labelside_alignment: string or Qt.Alignment. For string options, acceptable strings are:
            - "left"
            - "right"
            - "top"
            - "bottom"
            - "vcenter
        • row_wrap_policy: string or QFormLayout RowWrapPolicy. For string options, acceptable strings are:
            - "dont_wrap" (Fields are always beside Labels)
            - "wrap_long" (Labels column has enough spacing to accomodate the widest label)
            - "wrap_all" (Labels are above their Fields)
        • vertical_spacing: the vertical spacing between rows, in pixels
        • horizontal_spacing: the horizontal spacing within a row, in pixels

    Returns
        • None
    """
    field_dict = {"at_size_hint": QFormLayout.FieldsStayAtSizeHint,
                  "expanding_fields_grow": QFormLayout.ExpandingFieldsGrow,
                  "all_nonfixed_grow": QFormLayout.AllNonFixedFieldsGrow}
    align_dict = {"left": Qt.AlignLeft, "right": Qt.AlignRight, "top": Qt.AlignTop, "bottom": Qt.AlignBottom,
                  "vcenter": Qt.AlignVCenter}
    wrap_dict = {"dont_wrap": QFormLayout.DontWrapRows,
                 "wrap_long": QFormLayout.WrapLongRows,
                 "wrap_all": QFormLayout.WrapAllRows}

    formside_bits = None
    labelside_bits = None
    for label in labelside_alignment:
        bit = align_dict[label] if isinstance(label, str) else label
        if labelside_bits is None:
            labelside_bits = bit
        else:
            labelside_bits |= bit
    for form in formside_alignment:
        bit = align_dict[form] if isinstance(form, str) else form
        if formside_bits is None:
            formside_bits = bit
        else:
            formside_bits |= bit

    if isinstance(field_growth, str):
        formlay.setFieldGrowthPolicy(field_dict[field_growth])
    else:
        formlay.setFieldGrowthPolicy(field_growth)

    formlay.setFormAlignment(formside_bits)
    formlay.setLabelAlignment(labelside_bits)

    if isinstance(row_wrap_policy, str):
        formlay.setRowWrapPolicy(wrap_dict[row_wrap_policy])
    else:
        formlay.setRowWrapPolicy(row_wrap_policy)

    if vertical_spacing is not None:
        formlay.setVerticalSpacing(vertical_spacing)
    if horizontal_spacing is not None:
        formlay.setHorizontalSpacing(horizontal_spacing)


def set_widget_icon(widget, config: dict, icon_name: str, size: tuple = None) -> None:
    """
    Convenience function for setting a widget to contain an icon of a particular size

    Parameters
        • widget: the widget for which an icon should be set
        • config: the config instance, so that the appropriate filepath stored may be accessed
        • icon_name: the basename of the icon
        • size: tuple of width by height, in pixels

    Returns
        • None
    """
    icon_path = Path(config["ProjectDir"]) / "media" / icon_name
    widget.setIcon(QIcon(str(icon_path)))
    if size is not None:
        widget.setIconSize(QSize(*size))


def connect_widget_to_signal(widget, target_signal: callable) -> None:
    """
    Convenience function for connecting a widget to a signal; useful in for loops

    Parameters
        • widget: the widget to connect
        • target_signal: the signal to connect to

    Returns
        • None
    """
    if isinstance(widget, QComboBox):
        widget.currentTextChanged.connect(target_signal)
    elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
        widget.valueChanged.connect(target_signal)
    elif isinstance(widget, (DandD_Graphing_ListWidget2LineEdit, QLineEdit)):
        widget.textChanged.connect(target_signal)
    elif isinstance(widget, QCheckBox):
        widget.clicked.connect(target_signal)
    else:
        print(f'{widget} could not be connected')


# noinspection PyUnresolvedReferences
def disconnect_widget_and_reset(widget, target_signal, default) -> None:
    """
    Convenience function for disconnecting a widget from a signal and resetting the widget back to a default value
    without triggering those previous connections

    Parameters
        • widget: the widget to disconnect
        • target_signal: the signal to disconnect from
        • default: the default value to change to afterwards

    Returns
        • None
    """
    if isinstance(widget, QComboBox):
        widget.currentTextChanged.disconnect(target_signal)
        widget.setCurrentIndex(default)
    elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
        widget.valueChanged.disconnect(target_signal)
        widget.setValue(default)
    elif isinstance(widget, (DandD_Graphing_ListWidget2LineEdit, QLineEdit)):
        widget.textChanged.disconnect(target_signal)
        widget.setText(default)
    elif isinstance(widget, QCheckBox):
        widget.clicked.disconnect(target_signal)
        widget.setChecked(default)
    else:
        print(f'{widget} could not be connected')


def make_droppable_clearable_le(le_connect_to: callable = None,
                                btn_connect_to: callable = None,
                                layout_type: str = "hlay",
                                default: str = '',
                                **kwargs) -> Tuple[Union[QVBoxLayout, QHBoxLayout], DandD_FileExplorer2LineEdit,
                                                   QPushButton]:
    """
    Function for creating a typical QLineEdit-QPushButton pair encapsulated within a QHBoxLayout or QVBoxlayout.

    Parameters
        • le_connect_to: the function that the lineedit's textChanged signal should connect to, if any
        • btn_connect_to: the function that the pushbutton's clicked signal should connect to, if any
        • layout_type: a string denoting the layout type the lineedit should be placed in. One of "hlay" or "vlay".
        • default: the default text that should be present in the lineedit
        • kwargs: additional keywords that are fed into DandD_FileExplorer2LineEdit

    Returns
        • A tuple of QLayout, DandD_FileExplorer2LineEdit, QPushButton
    """
    var_layout = {"hlay": QHBoxLayout, "vlay": QVBoxLayout}[layout_type.lower()]()
    le = DandD_FileExplorer2LineEdit(**kwargs)
    le.setText(default)
    le.setClearButtonEnabled(True)
    if le_connect_to is not None:
        le.textChanged.connect(le_connect_to)
    btn = QPushButton("...", )
    if btn_connect_to is not None:
        btn.clicked.connect(btn_connect_to)
    var_layout.addWidget(le)
    var_layout.addWidget(btn)
    return var_layout, le, btn


def make_scrollbar_area(parent, orientation: str = "v",
                        margins: Tuple[int, int, int, int] = (0, 0, 0, 0)) -> Tuple[QVBoxLayout, QScrollArea, QWidget]:
    """
    Function for creating a QVBoxLayout within which is placed a QScrollArea set to a QWidget container

    Parameters
        • parent: The parent widget of the layout to be returned
        • orietation: A string of "v" or "h" for QVBoxLayout and QHboxLayout, respectively.
        • margins: The margins to set around the layout. Tuple of (left, top, right, bottom) as integers.

    Returns
        • A tuple of the QLayout, QScrollArea, QWidget

    """
    o_dict = {"v": QVBoxLayout, "h": QHBoxLayout}
    vlay, scrollarea, container = o_dict[orientation](parent), QScrollArea(), QWidget()
    vlay.setContentsMargins(*margins)
    scrollarea.setWidget(container)
    scrollarea.setWidgetResizable(True)
    vlay.addWidget(scrollarea)
    return vlay, scrollarea, container


def robust_qmsg(parent=None, msg_type="warning", title: str = "", body: Union[str, List[str]] = "",
                variables: Union[str, List[str]] = None) -> None:
    """
    Convenience function for printing out a QMessageBox, optionally with variables interleaved with strings to produce
    a conherent final message.

    Parameters
        • parent:  the parent to assign this QMessageBox to
        • msg_type: a string denoting the type of QMessageBox that should be displayed. One of "warning" (default),
        "information", or "critical"
        • title: a string denoting the title of the QMessageBox
        • body: a string or list of strings denoting the content of the QMessageBox. If a list of strings, the function
        expects variables to also be a list of strings which will interleave with body to form the final message.
        • variables: a string or list of strings denoting the additional variables to interleave into the main
        messages's content

    Returns
        • None


    """
    msg_box = QMessageBox()
    if system() == "Darwin":
        msg_box.setDefaultButton(QMessageBox.Ok)
    if parent is None:
        parent = QWidget()
    if isinstance(body, list) and isinstance(variables, list):
        content = "".join(interleave_longest(body, variables))
    elif isinstance(body, str) and isinstance(variables, str):
        content = body + variables
    elif isinstance(body, str) and isinstance(variables, list):
        content = body + "\n".join(variables)
    elif isinstance(body, str) and variables is None:
        content = body
    else:
        raise ValueError(f"{robust_qmsg.__name__} received incompatible arguments. body was of type {type(body)} and "
                         f"variables was of type {type(variables)}")

    getattr(msg_box, msg_type)(parent, title, content, QMessageBox.Ok)
    return


def robust_getfile(dialogue_caption: str = "", default_dir: Union[Path, str] = Path.home(),
                   dialogue_filter: str = "", permitted_suffixes: List[str] = None,
                   qmsgs: bool = True) -> (bool, Path):
    """
    Convenience function for retrieving a valid Path object from a QFileDialogue

    Parameters
        • dialogue caption: the title of the dialogue window that should be displayed
        • default_dir: the default directory that the QFileDialogue should start at. By default, it will be the
        operating system's home directory
        • dialogue filter: a string detailing the filter applied towards which files will be visible in the file
        dialogue. By default, no filter is applied.
        • permitted_suffixes: a list of strings denoting which filepath extensions must be satisfied. By default, no
        restrictions are applied.
        • qmsgs: a boolean of whether to show warning messages when a condition is not met (default) or silently fail.

    Returns
        • a boolean of whether all conditions were met
        • either a Path object of the filepath selected or None if conditions were not met

    """
    permitted_suffixes = [] if permitted_suffixes is None else permitted_suffixes
    dialogue = QFileDialog()
    dialogue.setFileMode(QFileDialog.ExistingFile)
    filepath, _ = dialogue.getOpenFileName(QFileDialog(), dialogue_caption, str(default_dir), dialogue_filter)
    if filepath == "":
        return False, None
    path = Path(filepath).resolve()
    if not path.exists():
        if qmsgs:
            robust_qmsg(QMessageBox(), title="Non-existent Path Specified",
                        body=["The path you have specified:\n", "\ndoes not exist"], variables=[str(path)])
        return False, None
    if not path.is_file():
        if qmsgs:
            robust_qmsg(QMessageBox(), title="Path is not a file",
                        body=["The path you have specified:\n", "\nis not a file"], variables=[str(path)])
        return False, None
    if path.suffix not in permitted_suffixes and len(permitted_suffixes) > 0:
        if qmsgs:
            robust_qmsg(QMessageBox(), title="File is not among the expected types",
                        body=["The path you have specified:\n", f"\nis not among the accepted filetypes:\n"],
                        variables=[str(path), " or ".join(ftype for ftype in permitted_suffixes)])
        return False, None
    return True, path


def dir_check(directory: Union[Path, str], parent=None, requirements: dict = None,
              qmsgs: bool = False) -> (bool, Union[None, Path]):
    """
    Convenience function for checking whether a given path has fulfilled certain requirements

    Parameters
        • directory: The directory whose validity should be assessed
        • parent: The parent widget to which any QMessageBoxes should be attached to
        • requirements: A dict whose keys are any of the following:
                - "child_file_exists" (The directory has a file with the indicated name)
                - "child_dir_exists" (The directory has a subdirectory with the indicated name)
                - "basename_equals" (The directory's name is the indicated name)
                - "basename_fits_regex" (The directory's name fits some regex pattern)
                - "child_fits_regex" (At least one child in the directory fits some regex)
                - "contains" (The directory has an immediate glob pattern that fits some requirement)
                - "rcontains" (The directory has a fitting glob pattern for some downstream path)
                The values of this dict must be a list whose first element is the requirement that must be met
                and whose second element is a list of strings to feed the QMessageBox error.
        • qmsgs: A boolean of whether this QMessages should show up if a requirements condition is not met.

    Example of requirements
    {"child_file_exists": ["Foo.jpeg", ["Invalid Directory", "The directory did not contain the expected filepath"],
    "rcontains": ["*.png", ["Invalid Directory", "The directory did not contain any png files"]
    }

    Returns
        • Whether the operation was a success
        • The directory as a Path object (if successful; None otherwise)

    """
    if isinstance(directory, str):
        directory = Path(directory).resolve()

    # At minimum, check if it is an existing directory
    if not all([directory.is_dir(), directory.exists()]):
        return False, None

    if parent is None:
        parent = QMessageBox()

    if requirements:
        for req_key, req_vals in requirements.items():
            # The immediate child file must exist inside the indicated directory
            if req_key == "child_file_exists":
                if any([not (directory / req_vals[0]).exists(), not (directory / req_vals[0]).is_file()]):
                    if qmsgs:
                        QMessageBox.warning(parent, req_vals[1][0], req_vals[1][1], QMessageBox.Ok)
                    return False, None
            # The immediate child directory must exist inside the indicated directory
            elif req_key == "child_dir_exists":
                if any([not (directory / req_vals[0]).exists(), not (directory / req_vals[0]).is_dir()]):
                    if qmsgs:
                        QMessageBox.warning(parent, req_vals[1][0], req_vals[1][1], QMessageBox.Ok)
                    return False, None
            # The directory's name must exist among the indicated candidates
            elif req_key == "basename_equals":
                if any([directory.name not in req_vals[0]]):
                    if qmsgs:
                        QMessageBox.warning(parent, req_vals[1][0], req_vals[1][1], QMessageBox.Ok)
                    return False, None
            # The directory's name must fit some regex
            elif req_key == "basename_fits_regex":
                pattern = re.compile(req_vals[0])
                if not pattern.search(directory.name):
                    if qmsgs:
                        QMessageBox.warning(parent, req_vals[1][0], req_vals[1][1], QMessageBox.Ok)
                    return False, None
            # The a child in the directory fits some regex
            elif req_key == "child_fits_regex":
                pattern = re.compile(req_vals[0])
                hits = [pattern.search(str(path)) for path in directory.iterdir()]
                if any([not any(hits)]):
                    if qmsgs:
                        QMessageBox.warning(parent, req_vals[1][0], req_vals[1][1], QMessageBox.Ok)
                    return False, None
            # The directory immediately contains some glob pattern
            elif req_key == "contains":
                if not peekable(directory.glob(req_vals[0])):
                    if qmsgs:
                        QMessageBox.warning(parent, req_vals[1][0], req_vals[1][1], QMessageBox.Ok)
                    return False, None
            # The directory contains some glob pattern in its tree
            elif req_key == "rcontains":
                if isinstance(req_vals[0], (list, tuple)):
                    req_vals[0] = sep.join(req_vals[0])
                if not peekable(directory.rglob(req_vals[0])):
                    if qmsgs:
                        QMessageBox.warning(parent, req_vals[1][0], req_vals[1][1], QMessageBox.Ok)
                    return False, None
            else:
                raise ValueError(f"{dir_check.__name__} received an incorrect formatting for the requirements argument")

    return True, directory

def robust_getdir(parent=None, dialog_caption: str = "", default_dir: Union[str, Path] = Path.home(),
                  requirements: dict = None, qmsgs: bool = True, lineedit=None) -> (bool, Union[None, Path]):
    """
    Meta-function for returning a directory from a QFileDialogue.

    Parameters
        • parent: The parent widget to which the QFileDialogue and QMessageBox should be attached to
        • dialog_caption: The QFileDialogue caption as a string
        • default_dir: The directory the QFileDialogue should start out in
        • requirements: A dict whose keys are any of the following:
                - "child_file_exists" (The directory has a file with the indicated name)
                - "child_dir_exists" (The directory has a subdirectory with the indicated name)
                - "basename_equals" (The directory's name is the indicated name)
                - "basename_fits_regex" (The directory's name fits some regex pattern)
                - "child_fits_regex" (At least one child in the directory fits some regex)
                - "contains" (The directory has an immediate glob pattern that fits some requirement)
                - "rcontains" (The directory has a fitting glob pattern for some downstream path)
                The values of this dict must be a list whose first element is the requirement that must be met
                and whose second element is a list of strings to feed the QMessageBox error.
        • qmsgs: A boolean of whether this QMessages should show up if a requirements condition is not met.
        • lineedit: A QLineEdit whose text should be set to the new directory

    Example of requirements
    {"child_file_exists": ["Foo.jpeg", ["Invalid Directory", "The directory did not contain the expected filepath"],
    "rcontains": ["*.png", ["Invalid Directory", "The directory did not contain any png files"]
    }

    Returns
        • Whether the operation was a success
        • The directory as a Path object (if successful; None otherwise)

    """
    if parent is None:
        parent = QFileDialog()

    directory = QFileDialog.getExistingDirectory(parent, dialog_caption, str(default_dir), QFileDialog.ShowDirsOnly)
    if directory == "":  # User cancels the operation
        return False, None

    is_valid, directory = dir_check(parent=parent, directory=directory, requirements=requirements, qmsgs=qmsgs)
    if not is_valid:
        return False, None

    if lineedit is not None:
        lineedit.setText(str(directory))

    return True, directory
