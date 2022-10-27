import sys
import logging
import unittest

from PyQt5 import QtWidgets, QtCore

from irrad_control.processes.gui import IrradGUI


class TestMain(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        # Make QApplication which starts event loop in order to create widgets
        cls.test_app = QtWidgets.QApplication(sys.argv)

        # Create complete window which can be accessed after launch
        cls.irrad_window = IrradGUI()
        cls.irrad_window.show()

        # Execute app
        cls.test_app.exec()

        # Allow 5 seconds for testing
        QtCore.QTimer.singleShot(5000, cls.test_app.exit)

    @classmethod
    def tearDownClass(cls):
        pass

    def test_setup_main_state(self):

        # Check if we have 3 tabs: ('Setup', 'Control', 'Monitor')
        assert self.irrad_window.tabs.count() == 3

        # Check if we have setup enabled, nothing else tabs: ('Setup', 'Control', 'Monitor')
        assert self.irrad_window.tabs.isTabEnabled(0)
        assert not self.irrad_window.tabs.isTabEnabled(1)
        assert not self.irrad_window.tabs.isTabEnabled(2)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMain)
    unittest.TextTestRunner(verbosity=2).run(suite)
