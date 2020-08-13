import os
import json
from PySide2.QtGui import QIcon
from PySide2.QtCore import QSize


def set_widget_icon(widget, config, icon_name, size=None):
    """
    Convenience function for setting a widget to contain an icon of a particular size
    :param widget: the widget for which an icon should be set
    :param config: the config instance, so that the appropriate filepath stored may be accessed
    :param icon_name: the basename of the icon
    :param size: tuple of width by height, in pixels
    """
    icon_path = os.path.join(config["ScriptsDir"], "media", icon_name)
    widget.setIcon(QIcon(icon_path))
    if size is not None:
        widget.setIconSize(QSize(*size))
