from PySide2.QtWidgets import QLabel
from PySide2.QtGui import QMovie, Qt, QResizeEvent
from PySide2.QtCore import QByteArray, QSize, Signal, Slot


class xASL_ImagePlayer(QLabel):
    def __init__(self, filepath, parent=None, h_offset=0, v_offset=5):
        """
        A modified QLabel which features a GIF movie that can be played

            Parameters:
                • filepath: The filepath to the .gif file which will be played
                • parent: The parent of this widget
                • h_offset: When resizing based on a buddy widget, the additional horizontal size that should be given
                • v_offset: When resizing based on a buddy widget, the additional vertical size that should be given

        """
        super(xASL_ImagePlayer, self).__init__(parent=parent)
        self.h_offset, self.v_offset = h_offset, v_offset
        self.setContentsMargins(0, 0, 0, 0)
        self.setAlignment(Qt.AlignLeft)

        # Load the file into a QMovie with the appropriate size
        self.movie = QMovie(str(filepath), QByteArray(), self)
        self.movie.setCacheMode(QMovie.CacheAll)
        self.movie.setSpeed(100)

        self.setMovie(self.movie)
        self.ping()

    def ping(self):
        self.movie.start()
        self.movie.stop()
        self.movie.jumpToFrame(0)

    @Slot(int, int)
    def listen_resize(self, width, height):
        self.movie.setScaledSize(QSize(width + self.h_offset, height + self.v_offset))
        self.ping()


class xASL_Lab(QLabel):
    inform_buddy = Signal(int, int)

    def __init__(self, buddy=None, *args, **kwargs):
        """
        A modified QLabel whose resizeEvent informs another widget with a listen_resize slot who will be informed of
        how the label's size has changed. This is particularly useful when items are placed into layouts and change
        size as a result, with the change needing to be communicated over.

            Parameters:
                • buddy: the widget who possesses a listen_resize slot to which this label will be connected to

        """
        super(xASL_Lab, self).__init__(*args, **kwargs)
        if hasattr(buddy, "listen_resize"):
            self.inform_buddy.connect(buddy.listen_resize)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super(xASL_Lab, self).resizeEvent(event)
        self.inform_buddy.emit(self.width(), self.height())

    @Slot(int, int)
    def listen_resize(self, width, height):
        self.resize(width, height)
