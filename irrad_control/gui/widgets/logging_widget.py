from PyQt6 import QtWidgets, QtGui
from irrad_control.utils.logger import log_levels


class LoggingWidget(QtWidgets.QWidget):
    """
    Implements a widget to display log messages, categorized into different log levels.
    Each log levels messages are displayed in a scrolling text edit in its own tab.
    """

    def __init__(self, level='NOTSET', parent=None):
        super(LoggingWidget, self).__init__(parent)

        # Layout
        self.setLayout(QtWidgets.QVBoxLayout())

        # Tabs
        self.tabs = QtWidgets.QTabWidget()

        # Add to layout
        self.layout().addWidget(self.tabs)

        # Orientation of tabs on the left side; "West" == 2
        self.tabs.setTabPosition(QtWidgets.QTabWidget.TabPosition.North)

        # All available tabs and their priority
        self.log_tabs = [log_levels[lvl] for lvl in sorted([n_lvl for n_lvl in log_levels if isinstance(n_lvl, int)])]

        self._loglevel = self._get_level_name(level)

        # QPlainTextWidgets used for writing log to
        self.log_consoles = {}

        # Style for icons
        self._style = QtWidgets.QApplication.style()

        # Connect
        self.tabs.currentChanged.connect(lambda idx: self._clear_icon(idx))

        # Init user interface
        self._init_ui()

    def _clear_icon(self, tab_idx):
        self.tabs.setTabIcon(tab_idx, self._get_icon('CLEAR'))

    def _get_icon(self, level):

        # Icons
        log_icons = {'DEBUG': self._style.StandardPixmap.SP_MessageBoxInformation,
                     'INFO': self._style.StandardPixmap.SP_MessageBoxInformation,
                     'WARNING': self._style.StandardPixmap.SP_MessageBoxWarning,
                     'ERROR': self._style.StandardPixmap.SP_MessageBoxCritical,
                     'NOTSET': self._style.StandardPixmap.SP_MessageBoxQuestion}

        if level in log_icons:
            return self._style.standardIcon(log_icons[level])

        return QtGui.QIcon()

    def _init_ui(self):

        for tab in self.log_tabs:
            if log_levels[tab] >= log_levels[self._loglevel]:
                self.log_consoles[tab] = QtWidgets.QPlainTextEdit()
                self.log_consoles[tab].setReadOnly(True)
                self.tabs.addTab(self.log_consoles[tab], tab)

        # Go to current log level
        self.tabs.setCurrentIndex(self.tabs.indexOf(self.log_consoles[self._loglevel]))

    def _check_level(self, log):
        # Loop over all logging levels and check which is in log message
        _levels = [lvl for lvl in self.log_tabs if lvl in log.upper()]

        # None of the available levels found, e.g. CRITICAL or NOTSET; log to ERROR and give ? as icon
        if len(_levels) != 1:
            return 'NOTSET'

        return _levels[0]

    @staticmethod
    def _get_level_name(level):

        # Check if the level we're changing to exists
        if level not in log_levels:
            raise KeyError("{} not a know logging level. Known levels are: {}".format(level, ', '.join([str(lvl) for lvl in log_levels])))

        # Deduce whether we're looking at level string or numeric level
        if isinstance(level, int):
            tmp_lvl = log_levels[level]
        else:
            tmp_lvl = str(level)

        return tmp_lvl

    def write_log(self, log):
        """
        Writes log to respective text edit of log tab. At this point in the application,
        the log is expected to be formatted by the respective logging handler.
        """

        # Check the log level
        level = self._check_level(log)

        # Check if we're logging this level
        if level in self.log_consoles:

            self.log_consoles[level].appendPlainText(log)

            log_idx = self.tabs.indexOf(self.log_consoles[level])

            if self.tabs.currentIndex() != log_idx:
                self.tabs.setTabIcon(log_idx, self._get_icon(level))

    def change_level(self, level):
        """
        Change the logging level. Add or remove tabs / log consoles accordingly.
        """

        # If we're not changing to a new level, do nothing
        if level == self._loglevel:
            return

        self._loglevel = self._get_level_name(level)

        # Remove tab if new log level is higher than old
        if log_levels[self.tabs.tabText(0)] < log_levels[self._loglevel]:

            while log_levels[self.tabs.tabText(0)] < log_levels[self._loglevel]:
                _tab = self.tabs.tabText(0)
                self.tabs.removeTab(0)
                del self.log_consoles[_tab]
        # Add tabs
        else:
            # Make list of tabs to add
            tabs_to_add = [lvl for lvl in self.log_tabs if log_levels[lvl] >= log_levels[self._loglevel] and lvl not in self.log_consoles]

            # Add in reversed order since we're inserting at 0
            for tab in reversed(tabs_to_add):
                self.log_consoles[tab] = QtWidgets.QPlainTextEdit()
                self.log_consoles[tab].setReadOnly(True)
                self.tabs.insertTab(0, self.log_consoles[tab], tab)
