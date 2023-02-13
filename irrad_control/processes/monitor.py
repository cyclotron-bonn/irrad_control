import os
import sys
from PyQt5 import QtWidgets, QtCore, QtGui

from irrad_control.processes.gui import IrradGUI
from irrad_control.gui.tabs import IrradMonitorTab
from irrad_control.gui.widgets.setup_widgets import SessionSetup
from irrad_control.gui.utils import fill_combobox_items
from irrad_control.gui.widgets.util_widgets import GridContainer
from irrad_control.utils.tools import load_yaml
from irrad_control.ions import get_ions
from irrad_control import config_path


class MonitorGUI(IrradGUI):
    """
    GUI for just monitoring e.g. adjustments of the beam by operators or simply observing beam / environmental parameters.
    Subclass of *IrradGUI* with limited functionality.

    Parameters
    ----------
    IrradGUI : _type_
        _description_
    """
    def __init__(self, setup=None, parent=None):
        super().__init__(parent)
        
        self.setup = setup

        self.ions = get_ions()

        # Process the setup and ensure it is a setup dict
        self._process_setup()

        # Make minimal window for interaction with user
        self._init_input_ui()

    def _process_setup(self):
        
        # No setup has been provided, look for default setup file 
        if self.setup is None:
            default_monitor_setup_path = os.path.join(config_path, 'monitor_setup.yaml')
            
            if not os.path.isfile(default_monitor_setup_path):
                raise RuntimeError(f"No setup is provided and no default 'monitor_setup.yaml' exists in {config_path}.")
            
            self.setup = load_yaml(path=default_monitor_setup_path)
        
        elif isinstance(self.setup, str) and os.path.isfile(self.setup):
            self.setup = load_yaml(path=self.setup)

        elif isinstance(self.setup, dict):
            pass

        else:
            raise RuntimeError("Setup file could not be found or setup dict is invalid!")
        
        # Quick check
        assert all(x in self.setup for x in ('host', 'server', 'session')), f"Monitor setup incomplete: {self.setup}"
    
    def _init_input_ui(self):

        self.minimal_input_window = QtWidgets.QMainWindow()
        self.minimal_input_window.setWindowTitle("Input monitor GUI data")
        # Make this window blocking parent window
        self.minimal_input_window.setWindowModality(QtCore.Qt.ApplicationModal)
        screen = QtWidgets.QDesktopWidget().screenGeometry()
        self.minimal_input_window.resize(int(0.5 * screen.width()), int(0.5 * screen.height()))

        main_widget = QtWidgets.QWidget()
        main_widget.setLayout(QtWidgets.QVBoxLayout())
        self.minimal_input_window.setCentralWidget(main_widget)

        tab_widget = QtWidgets.QTabWidget()

        # Loop over servers in setup
        for server in self.setup['server']:

            server_name = self.setup['sever'][server]['name']

            # Monitor specific inputs
            monitor_widget = GridContainer('Monitor input')

            # Ion type
            label_ion = QtWidgets.QLabel('Ion type:')
            combo_ion = QtWidgets.QComboBox()
            fill_combobox_items(combo_ion, self.ions)
            # Update ion type
            combo_ion.currentTextChanged.connect(lambda ion, s=server: self.setup['server'][s]['daq'].update({'ion': ion}))

            # Energy
            label_energy = QtWidgets.QLabel('Kinetic energy:')
            spbx_energy = QtWidgets.QDoubleSpinBox()
            spbx_energy.setDecimals(3)
            spbx_energy.setSuffix(' MeV')
            # Update energy, energy at dut and calibration
            for con in [lambda ene, s=server: 
                        self.setup['server'][s]['daq'].update({'ekin_initial': ene,
                                                               'ekin': self.ions[self.setup['server'][s]['daq']['ion']].ekin_at_dut(ene)}),
                        lambda ene, s=server: 
                        self.setup['server'][s]['daq']['lambda'].update(self.ions[self.setup['server'][s]['daq']['ion']].calibration(at_energy=ene, to_dict=True))]:
            
                spbx_energy.valueChanged.connect(con)

            # Add widgets
            monitor_widget.add_widget(widget=[label_ion, combo_ion])
            monitor_widget.add_widget(widget=[label_energy, spbx_energy])

            tab_widget.addTab(monitor_widget, server_name)

        main_widget.layout().addWidget(tab_widget)

        # Session input
        session_widget = SessionSetup('Session input')
        session_widget.setupChanged.connect(lambda stp: self.setup['session'].update(stp))
        main_widget.layout().addWidget(session_widget)
        
        # Button start
        btn_start = QtWidgets.QPushButton('Start monitor')
        btn_start.clicked.connect(lambda _: self._init_setup(setup=self.setup))
        btn_start.clicked.connect(lambda _, mw=main_widget: mw.setEnabled(False))
        btn_start.clicked.connect(self.minimal_input_window.close)
        btn_start.clicked.connect(self.show)
        main_widget.layout().addStretch()
        main_widget.layout().addWidget(btn_start)
        self.minimal_input_window.show()

    def _init_tabs(self):
        """
        Initializes the tabs for the monitor window
        """
        # Add tab_widget and widgets for the different analysis steps
        self.tab_order = ('Control',)

        for tab in self.tab_order:
            tw = QtWidgets.QWidget()
            self.tabs.addTab(tw, tab)

    def update_tabs(self):

        self.monitor_tab = IrradMonitorTab(setup=self.setup['server'], parent=self.tabs, plot_path=self.setup['session']['outfolder'])

        # Make temporary dict for updated tabs
        tmp_tw = {'Monitor': self.monitor_tab}

        for tab in self.tab_order:
            # Remove old tab, insert updated tab at same index and set status
            self.tabs.removeTab(self.tab_order.index(tab))
            self.tabs.insertTab(self.tab_order.index(tab), tmp_tw[tab], tab)


def run():
    app = QtWidgets.QApplication(sys.argv)
    font = QtGui.QFont()
    font.setPointSize(12)
    app.setFont(font)
    gui = MonitorGUI()
    gui.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    run()
