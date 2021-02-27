from PySide2.QtWidgets import QLabel
from PySide2.QtGui import QMovie, Qt
from PySide2.QtCore import QByteArray, QSize


class xASL_ImagePlayer(QLabel):
    def __init__(self, filename, size=(50, 50), parent=None):
        super(xASL_ImagePlayer, self).__init__(parent=parent)
        self.counter = 0
        self.setContentsMargins(0, 0, 0, 0)
        self.setAlignment(Qt.AlignLeft)

        # Load the file into a QMovie with the appropriate size
        self.movie = QMovie(str(filename), QByteArray(), self)
        self.movie.setScaledSize(QSize(*size))
        self.movie.setCacheMode(QMovie.CacheAll)
        self.movie.setSpeed(100)

        self.setMovie(self.movie)
        self.movie.start()
        self.movie.stop()
