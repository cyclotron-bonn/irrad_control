import sys
import logging
import unittest
import time

from PyQt5 import QtWidgets

from irrad_control.gui.tabs import IrradSetupTab
from irrad_control import network_config

# Remove all IPs
for nc in list(network_config['server']['all'].keys()):
    del network_config['server']['all'][nc]

# Add pingable IP
network_config['server']['all']['8.8.8.8'] = 'Google1'
network_config['server']['all']['8.8.4.4'] = 'Google2'
network_config['server']['all']['8.8.4.123'] = 'ThisShouldNotBeAvailable'
network_config['server']['default'] = '8.8.8.8'


class TestSetup(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        # Make QApplication which starts event loop in order to create widgets
        cls.test_app = QtWidgets.QApplication(sys.argv)

        # Main widget to parent all other widgets
        cls.main_widget = QtWidgets.QTabWidget()

        # Create complete window which can be accessed after launch
        cls.setup_tab = IrradSetupTab(cls.main_widget)

        time.sleep(10)  # Workaround for threaded server finding

    @classmethod
    def tearDownClass(cls):
        pass

    def test_setup_tab_finding_servers(self):

        # Add found servers to the widgets
        self.setup_tab.irrad_setup.setup_widgets['selection'].add_selection(self.setup_tab.irrad_setup.setup_widgets['network'].available_servers)
        self.setup_tab.irrad_setup.setup_widgets['selection'].widgets[network_config['server']['default']]['checkbox'].setChecked(True)

        # Check that all available IPs have been found
        self.assertTrue(all(i in self.setup_tab.irrad_setup.setup_widgets['network'].available_servers for i in ('8.8.8.8', '8.8.4.4')))

        # Check that not available IPs have not been found
        self.assertFalse('8.8.4.123' in self.setup_tab.irrad_setup.setup_widgets['network'].available_servers)

        # Check that default server has been selected
        self.assertTrue(self.setup_tab.irrad_setup.setup_widgets['selection'].widgets[network_config['server']['default']]['checkbox'].isChecked())

    def test_setup_tab_server_tab_creation(self):

        # Create test state
        self.setup_tab.handle_server({'select': True, 'ip': '8.8.8.8', 'name': 'Google1'})

        # Check if we have 1 tab with the correct name
        self.assertTrue(self.setup_tab.server_setup.tabs.count() == 1)
        self.assertTrue(self.setup_tab.server_setup.tabs.tabText(0) == 'Google1')

        # Remove default tab
        self.setup_tab.handle_server({'select': False, 'ip': '8.8.8.8', 'name': 'Google1'})

        # Check if we have 0 tab
        self.assertTrue(self.setup_tab.server_setup.tabs.count() == 0)

        for ip, name in network_config['server']['all'].items():
            self.setup_tab.handle_server({'select': True, 'ip': ip, 'name': name})

        # Check if we have 3 tabs
        self.assertTrue(self.setup_tab.server_setup.tabs.count() == 3)

        self.assertListEqual(sorted(list(network_config['server']['all'].values())),
                             sorted(list(self.setup_tab.server_setup.tabs.tabText(i) for i in range(3))))

    def test_setup_tab_server_tab_behaviour(self):

        # Create test state
        for ip, name in network_config['server']['all'].items():
            self.setup_tab.handle_server({'select': ip == '8.8.8.8', 'ip': ip, 'name': name})

        for cb in self.setup_tab.server_setup.setup_widgets['8.8.8.8']['device'].widgets:
            self.setup_tab.server_setup.setup_widgets['8.8.8.8']['device'].widgets[cb].setChecked(cb == 'stage')

        # Now only stage should be checked and overall state should be setup
        self.assertTrue(self.setup_tab.isSetup)

        # Now state should be not set up anymore
        self.setup_tab.server_setup.setup_widgets['8.8.8.8']['device'].widgets['stage'].setChecked(False)

        self.assertFalse(self.setup_tab.isSetup)

    def test_setup_tab_behaviour(self):

        # Create testing state
        self.setup_tab.irrad_setup.setup_widgets['selection'].add_selection(self.setup_tab.irrad_setup.setup_widgets['network'].available_servers)
        self.setup_tab.irrad_setup.setup_widgets['selection'].widgets['8.8.8.8']['checkbox'].setChecked(True)

        for ip, name in network_config['server']['all'].items():
            self.setup_tab.handle_server({'select': ip == '8.8.8.8', 'ip': ip, 'name': name})

        for cb in self.setup_tab.server_setup.setup_widgets['8.8.8.8']['device'].widgets:
            self.setup_tab.server_setup.setup_widgets['8.8.8.8']['device'].widgets[cb].setChecked(cb == 'stage')

        self.assertTrue(self.setup_tab.isSetup)
        self.assertTrue(self.setup_tab.btn_ok.isEnabled())

        self.setup_tab.irrad_setup.setup_widgets['selection'].widgets['8.8.8.8']['checkbox'].setChecked(False)

        self.assertFalse(self.setup_tab.isSetup)
        self.assertFalse(self.setup_tab.btn_ok.isEnabled())


if __name__ == '__main__':
    pass
    # logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")
    # suite = unittest.TestLoader().loadTestsFromTestCase(TestSetup)
    # unittest.TextTestRunner(verbosity=2).run(suite)
