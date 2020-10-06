import sys
import logging
import unittest

from PyQt5 import QtWidgets, QtCore

from irrad_control import network_config
from irrad_control.main import IrradControlWin


class TestMain(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        # Make QApplication which starts event loop in order to create widgets
        cls.test_app = QtWidgets.QApplication(sys.argv)

        # Remove all IPs
        for nc in list(network_config['server']['all'].keys()):
            del network_config['server']['all'][nc]

        # Add pingable IP
        network_config['server']['all']['8.8.8.8'] = 'Google1'
        network_config['server']['all']['8.8.4.4'] = 'Google2'
        network_config['server']['all']['8.8.4.123'] = 'ThisShouldNotBeAvailable'
        network_config['server']['default'] = '8.8.8.8'

        # Create complete window which can be accessed after launch
        cls.irrad_window = IrradControlWin()
        cls.irrad_window.show()

        # Check if pingable server '8.8.8.8' was found
        cls.irrad_window.setup_tab.irrad_setup.setup_widgets['network'].serverIPsFound.connect(cls.test_app.exit)

        # Execute app; After server finding returns, main window is setup and can be tested
        cls.test_app.exec_()

    @classmethod
    def tearDownClass(cls):
        pass

    def test_setup_tab_finding_servers(self):

        # Create test state
        self.irrad_window.setup_tab.irrad_setup.setup_widgets['selection'].widgets['8.8.8.8']['checkbox'].setChecked(True)

        # Check that all available IPs have been found
        self.assertTrue(all(i in self.irrad_window.setup_tab.irrad_setup.setup_widgets['network'].available_servers for i in ('8.8.8.8', '8.8.4.4')))

        # Check that not available IPs have not been found
        self.assertFalse('8.8.4.123' in self.irrad_window.setup_tab.irrad_setup.setup_widgets['network'].available_servers)

        # Check that default server has been selected
        self.assertTrue(self.irrad_window.setup_tab.irrad_setup.setup_widgets['selection'].widgets[network_config['server']['default']]['checkbox'].isChecked())

    def test_setup_tab_server_tab_creation(self):

        # Create test state
        for ip in self.irrad_window.setup_tab.irrad_setup.setup_widgets['selection'].widgets:
            self.irrad_window.setup_tab.irrad_setup.setup_widgets['selection'].widgets[ip]['checkbox'].setChecked('8.8.8.8' == ip)

        # Check if we have 1 tabs
        self.assertTrue(self.irrad_window.setup_tab.server_setup.tabs.count() == 1)
        self.assertTrue(self.irrad_window.setup_tab.server_setup.tabs.tabText(0) == 'Google1')

        # Remove default tab
        self.irrad_window.setup_tab.irrad_setup.setup_widgets['selection'].widgets[network_config['server']['default']]['checkbox'].setChecked(False)

        # Check if we have 0 tab
        self.assertTrue(self.irrad_window.setup_tab.server_setup.tabs.count() == 0)

        for ip in self.irrad_window.setup_tab.irrad_setup.setup_widgets['selection'].widgets:
            self.irrad_window.setup_tab.irrad_setup.setup_widgets['selection'].widgets[ip]['checkbox'].setChecked(True)

        # Check if we have 2 tabs
        self.assertTrue(self.irrad_window.setup_tab.server_setup.tabs.count() == 2)

    def test_setup_tab_server_tab_behaviour(self):

        # Create test state
        self.irrad_window.setup_tab.irrad_setup.setup_widgets['selection'].widgets['8.8.8.8']['checkbox'].setChecked(True)
        for cb in self.irrad_window.setup_tab.server_setup.setup_widgets['8.8.8.8']['device'].widgets:
            self.irrad_window.setup_tab.server_setup.setup_widgets['8.8.8.8']['device'].widgets[cb].setChecked(True)

        for v in (True, False):
            for hw in ('adc', 'temp'):

                self.irrad_window.setup_tab.server_setup.setup_widgets['8.8.8.8']['device'].widgets[hw].setChecked(v)

                self.assertTrue(self.irrad_window.setup_tab.server_setup.setup_widgets['8.8.8.8'][hw].isVisible() == v)

        # Now only stage should be checked and overall state should be setup
        self.assertTrue(self.irrad_window.setup_tab.isSetup)

        # Now state should be not set up anymore
        self.irrad_window.setup_tab.server_setup.setup_widgets['8.8.8.8']['device'].widgets['stage'].setChecked(False)

        self.assertFalse(self.irrad_window.setup_tab.isSetup)

        # Now state should be not set up anymore
        self.irrad_window.setup_tab.server_setup.setup_widgets['8.8.8.8']['device'].widgets['stage'].setChecked(True)

    def test_setup_tab_behaviour(self):

        # Create testing state
        for ip in self.irrad_window.setup_tab.irrad_setup.setup_widgets['selection'].widgets:
            self.irrad_window.setup_tab.irrad_setup.setup_widgets['selection'].widgets[ip]['checkbox'].setChecked(ip == '8.8.8.8')
        for cb in self.irrad_window.setup_tab.server_setup.setup_widgets['8.8.8.8']['device'].widgets:
            self.irrad_window.setup_tab.server_setup.setup_widgets['8.8.8.8']['device'].widgets[cb].setChecked(cb == 'stage')

        self.assertTrue(self.irrad_window.setup_tab.isSetup)
        self.assertTrue(self.irrad_window.setup_tab.btn_ok.isEnabled())

        self.irrad_window.setup_tab.irrad_setup.setup_widgets['selection'].widgets['8.8.8.8']['checkbox'].setChecked(False)

        self.assertFalse(self.irrad_window.setup_tab.isSetup)
        self.assertFalse(self.irrad_window.setup_tab.btn_ok.isEnabled())


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMain)
    unittest.TextTestRunner(verbosity=2).run(suite)
