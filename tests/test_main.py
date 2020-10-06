import sys
import logging
import unittest
import time

from PyQt5 import QtWidgets, QtCore

from irrad_control.main import IrradControlWin


class TestIrradWin(IrradControlWin):
    """Test class that does not try to access the screen"""

    def _init_ui(self):
        """
        Initializes the user interface and displays "Hello"-message
        """

        # Create main layout
        self.main_widget = QtWidgets.QWidget()
        self.main_layout = QtWidgets.QVBoxLayout(self.main_widget)
        self.setCentralWidget(self.main_widget)

        # Add QTabWidget for tab_widget
        self.tabs = QtWidgets.QTabWidget()

        # Main splitter
        self.main_splitter = QtWidgets.QSplitter()
        self.main_splitter.setOrientation(QtCore.Qt.Vertical)
        self.main_splitter.setChildrenCollapsible(False)

        # Sub splitter for log and displaying raw data as it comes in
        self.sub_splitter = QtWidgets.QSplitter()
        self.sub_splitter.setOrientation(QtCore.Qt.Horizontal)
        self.sub_splitter.setChildrenCollapsible(False)

        # Add to main layout
        self.main_splitter.addWidget(self.tabs)
        self.main_splitter.addWidget(self.sub_splitter)
        self.main_layout.addWidget(self.main_splitter)

        # Init widgets and add to main windowScatterPlotItem
        self._init_menu()
        self._init_tabs()
        self._init_log_dock()

        self.sub_splitter.setSizes([int(1. / 3. * self.width()), int(2. / 3. * self.width())])
        self.main_splitter.setSizes([int(0.8 * self.height()), int(0.2 * self.height())])


class TestMain(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        # Make QApplication which starts event loop in order to create widgets
        cls.test_app = QtWidgets.QApplication(sys.argv)

        # Create complete window which can be accessed after launch
        cls.irrad_window = TestIrradWin()

        time.sleep(10)  # Workaround for threaded launch

    @classmethod
    def tearDownClass(cls):
        pass

    def test_main_window_tabs(self):

        self.assertListEqual(list(self.irrad_window.tab_order), list(self.irrad_window.tabs.tabText(i) for i in range(self.irrad_window.tabs.count())))


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMain)
    unittest.TextTestRunner(verbosity=2).run(suite)
