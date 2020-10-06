import sys
import logging
import unittest
import time

from PyQt5 import QtWidgets

from irrad_control.main import IrradControlWin


class TestMain(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        # Make QApplication which starts event loop in order to create widgets
        cls.test_app = QtWidgets.QApplication(sys.argv)

        # Create complete window which can be accessed after launch
        cls.irrad_window = IrradControlWin()

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
