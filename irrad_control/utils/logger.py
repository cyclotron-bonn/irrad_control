import sys
import logging
from PyQt5 import QtCore


log_levels = dict(logging._levelToName)
log_levels.update({k: v for (v, k) in log_levels.items()})


class LoggingStream(QtCore.QObject):
    """
    Class to handle the stdout stream which is used to do thread safe logging
    since QtWidgets are not thread safe and therefore one can not directly log to GUIs
    widgets when performing tasks on different thread than Qt main application thread
    """

    _stdout = None
    _stderr = None
    messageWritten = QtCore.pyqtSignal(str)

    def flush(self):
        pass

    def fileno(self):
        return -1

    def write(self, msg):
        if not self.signalsBlocked():
            self.messageWritten.emit(str(msg))  # Python 3, was unicode before

    @staticmethod
    def stdout():
        if not LoggingStream._stdout:
            LoggingStream._stdout = LoggingStream()
            sys.stdout = LoggingStream._stdout
        return LoggingStream._stdout

    @staticmethod
    def stderr():
        if not LoggingStream._stderr:
            LoggingStream._stderr = LoggingStream()
            sys.stderr = LoggingStream._stderr
        return LoggingStream._stderr


class CustomHandler(logging.Handler):
    """
    Implements a logging handler which allows redirecting log thread-safe
    """

    def __init__(self, parent):
        super(CustomHandler, self).__init__()

        # Set format
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    def emit(self, record):
        msg = self.format(record)
        if msg:
            LoggingStream.stdout().write(msg)
