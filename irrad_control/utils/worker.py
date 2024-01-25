import traceback
import threading


# If we can import PyQt6, we want a QtWorker as well as a ThreadWorker
_QT_WORKER = True
try:
    from PyQt6 import QtCore
except ModuleNotFoundError:
    _QT_WORKER = False


if _QT_WORKER:

    class QtWorkerSignals(QtCore.QObject):

        finished = QtCore.pyqtSignal()
        exception = QtCore.pyqtSignal(Exception, str)
        timeout = QtCore.pyqtSignal()


    class QtWorker(QtCore.QRunnable):
        """
        Implements a worker on which functions can be executed for multi-threading within Qt.
        The worker is an instance of QRunnable, which can be started and handled automatically by Qt and its QThreadPool.
        """

        def __init__(self, func, *args, **kwargs):
            super(QtWorker, self).__init__()

            # Main function which will be executed on this thread
            self.func = func
            # Arguments of main function
            self.args = args
            # Keyword arguments of main function
            self.kwargs = kwargs

            # Needs to be done this way since QRunnable cannot emit signals; QObject needed
            self.signals = QtWorkerSignals()

            # Timer to inform that a timeout occurred
            self.timer = QtCore.QTimer()
            self.timer.setSingleShot(True)
            self.timeout = None

        def set_timeout(self, timeout):
            self.timeout = int(timeout)

        @QtCore.pyqtSlot()
        def run(self):
            """
            Runs the function func with given arguments args and keyword arguments kwargs.
            If errors or exceptions occur, a signal sends the exception to main thread.
            """

            # Start timer if needed
            if self.timeout is not None:
                self.timer.timeout.connect(self.signals.timeout.emit())
                self.timer.start(self.timeout)

            try:
                if self.args and self.kwargs:
                    self.func(*self.args, **self.kwargs)
                elif self.args:
                    self.func(*self.args)
                elif self.kwargs:
                    self.func(**self.kwargs)
                else:
                    self.func()

            except Exception as e:
                # Format traceback and send
                trc_bck = traceback.format_exc()
                # Emit exception signal
                self.signals.exception.emit(e, trc_bck)

            self.signals.finished.emit()


class ThreadWorker(threading.Thread):
    """
    Sub-class of threading.Thread which stores any exception which occurs during the Thread's 'run'-method.
    """
    
    def __init__(self, *args, **kwargs):

        # Name thread according to function which is executed
        if 'name' not in kwargs:
            if 'target' in kwargs and kwargs['target'] is not None:
                kwargs['name'] = kwargs['target'].__name__

        super(ThreadWorker, self).__init__(*args, **kwargs)

        # Init attributes holding exception and formatted traceback string
        self.exception = self.traceback_str = None

    def run(self):
        """Wraps original run method to store exceptions and traceback"""

        try:
            super(ThreadWorker, self).run()
        except Exception as e:
            self.exception, self.traceback_str = e, traceback.format_exc()
