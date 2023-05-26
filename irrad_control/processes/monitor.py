import os
import sys
import logging
from PyQt5 import QtWidgets, QtCore, QtGui

from irrad_control.processes.gui import IrradGUI
from irrad_control.gui.tabs import IrradMonitorTab
from irrad_control.gui.widgets.setup_widgets import SessionSetup
from irrad_control.gui.utils import fill_combobox_items
from irrad_control.gui.widgets.util_widgets import GridContainer
from irrad_control.utils.tools import load_yaml
from irrad_control.ions import get_ions
from irrad_control import config_path, tmp_path


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

            server_name = self.setup['server'][server]['name']

            # Monitor specific inputs
            monitor_widget = GridContainer('Monitor input')

            # Ion type
            label_ion = QtWidgets.QLabel('Ion type:')
            combo_ion = QtWidgets.QComboBox()
            fill_combobox_items(combo_ion, self.ions)

            # Energy
            label_energy = QtWidgets.QLabel('Kinetic energy:')
            spbx_energy = QtWidgets.QDoubleSpinBox()
            spbx_energy.setDecimals(3)
            spbx_energy.setSuffix(' MeV')

            # Connections
            
            # Update ion type
            for con in [lambda ion, s=server: self.setup['server'][s]['daq'].update({'ion': ion}),
                        lambda ion, spx=spbx_energy: spx.setRange(*self.ions[ion].ekin_range())]:
                combo_ion.currentTextChanged.connect(con)
             
            # Update energy, energy at dut and calibration
            for con in [lambda ene, s=server: 
                        self.setup['server'][s]['daq'].update({'ekin_initial': ene,
                                                               'ekin': self.ions[self.setup['server'][s]['daq']['ion']].ekin_at_dut(ene)}),
                        lambda ene, s=server: 
                        self.setup['server'][s]['daq'].update({'lambda': self.ions[self.setup['server'][s]['daq']['ion']].calibration(at_energy=ene, as_dict=True)})]:
            
                spbx_energy.valueChanged.connect(con)

            # Emit ion once to set correct energy ranges
            combo_ion.currentTextChanged.emit(combo_ion.currentText())

            # Add widgets
            monitor_widget.add_widget(widget=[label_ion, combo_ion])
            monitor_widget.add_widget(widget=[label_energy, spbx_energy])

            tab_widget.addTab(monitor_widget, server_name)

        main_widget.layout().addWidget(tab_widget)

        # Session input
        session_widget = SessionSetup('Session input')
        session_widget.setupChanged.connect(lambda stp: self.setup['session'].update(stp))
        session_widget.widgets['logging_combo'].currentTextChanged.connect(lambda lvl: self.log_widget.change_level(lvl))
        session_widget.widgets['folder_edit'].setText(tmp_path)  # default to tmp dir
        main_widget.layout().addWidget(session_widget)
        
        # Button start
        btn_start = QtWidgets.QPushButton('Start monitor')

        for con in [lambda _, mw=main_widget: mw.setEnabled(False),
                    self.minimal_input_window.close,
                    self.show,
                    lambda _: self._init_setup(setup=self.setup),
                    lambda _: self.info_dock.setVisible(False),
                    lambda _: self.daq_dock.setVisible(False)]:

            btn_start.clicked.connect(con)
        
        main_widget.layout().addStretch()
        main_widget.layout().addWidget(btn_start)
        self.minimal_input_window.show()

    def _init_tabs(self):
        """
        Initializes the tabs for the monitor window
        """
        # Add tab_widget and widgets for the different analysis steps
        self.tab_order = ('Monitor',)

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

    def _started_daq_proc(self, hostname):
        """A DQAProcess has been sucessfully started on *hostname*"""
        
        self._started_daq_proc_hostnames.append(hostname)

        # Enable Control and Monitor tabs for this
        if hostname in self.setup['server']:
            self.monitor_tab.enable_monitor(server=hostname)

        # All servers have launched successfully
        if all(s in self._started_daq_proc_hostnames for s in self.setup['server']):
            # The interpreter has also succesfully started
            if 'localhost' in self._started_daq_proc_hostnames:

                # The application has started succesfully
                logging.info("All servers and the converter have started successfully!")
                self.pdiag.setLabelText('Application launched successfully!')
                self.tabs.setCurrentIndex(self.tabs.indexOf(self.monitor_tab))
                QtCore.QTimer.singleShot(1500, self.pdiag.close)

    def handle_data(self, data):

        server = data['meta']['name']

        # Check whether data is interpreted
        if data['meta']['type'] == 'raw':
            self.daq_info_widget.update_raw_data(data)
            self.monitor_tab.plots[server]['raw_plot'].set_data(meta=data['meta'], data=data['data'])

        # Check whether data is interpreted
        elif data['meta']['type'] == 'beam':
            self.daq_info_widget.update_beam_current(data)
            self.monitor_tab.plots[server]['pos_plot'].set_data(data)
            self.monitor_tab.plots[server]['current_plot'].set_data(meta=data['meta'], data=data['data']['current'])
            self.monitor_tab.plots[server]['see_current_plot'].set_data(meta=data['meta'], data=data['data']['see'])

            self.monitor_tab.plots[server]['sey_plot'].set_data(data['data']['see']['sey'])
            if 'frac_h' in data['data']['see']:
                self.monitor_tab.plots[server]['sem_h_plot'].set_data(data['data']['see']['frac_h'])
            if 'frac_v' in data['data']['see']:
                self.monitor_tab.plots[server]['sem_v_plot'].set_data(data['data']['see']['frac_v'])

        elif data['meta']['type'] == 'hist':
            if 'beam_position_idxs' in data['data']:
                self.monitor_tab.plots[server]['pos_plot'].update_hist(data['data']['beam_position_idxs'])
            if 'see_horizontal_idx' in data['data']:
                self.monitor_tab.plots[server]['sem_h_plot'].update_hist(data['data']['see_horizontal_idx'])
            if 'see_vertical_idx' in data['data']:
                self.monitor_tab.plots[server]['sem_v_plot'].update_hist(data['data']['see_vertical_idx'])
            if 'sey_idx' in data['data']:
                self.monitor_tab.plots[server]['sey_plot'].update_hist(data['data']['sey_idx'])

        elif data['meta']['type'] == 'temp_arduino':

            self.monitor_tab.plots[server]['temp_arduino_plot'].set_data(meta=data['meta'], data=data['data'])

        elif data['meta']['type'] == 'temp_daq_board':
            self.monitor_tab.plots[server]['temp_daq_board_plot'].set_data(meta=data['meta'], data=data['data'])

        elif data['meta']['type'] == 'dose_rate':
            self.monitor_tab.plots[server]['dose_rate_plot'].set_data(meta=data['meta'], data=data['data'])

    def handle_reply(self, reply_dict):

        reply = reply_dict['reply']
        _type = reply_dict['type']
        sender = reply_dict['sender']
        hostname = reply_dict['hostname']
        reply_data = None if 'data' not in reply_dict else reply_dict['data']

        if _type == 'STANDARD':

            if sender == 'server':

                if reply == 'start':
                    logging.info("Successfully started server on at IP {} with PID {}".format(hostname, reply_data))
                    self._started_daq_proc(hostname=hostname)

                elif reply == 'shutdown':

                    logging.info("Server at {} confirmed shutdown".format(hostname))

            elif sender == 'IrradDAQBoard':

                if reply == 'set_ifs':
                    cmd_data = {'server': hostname,
                                'ifs': reply_data['callback']['result'],
                                'group': reply_data['call']['kwargs']['group']}
                    self.send_cmd(hostname='localhost', target='interpreter', cmd='update_group_ifs', cmd_data=cmd_data)
                    self.send_cmd(hostname='localhost', target='interpreter', cmd='record_data', cmd_data=(hostname, True))

            elif sender == 'interpreter':

                if reply == 'start':
                    logging.info("Successfully started interpreter on {} with PID {}".format(hostname, reply_data))
                    self._started_daq_proc(hostname=hostname)

                if reply == 'record_data':
                    server, state = reply_data
                    self.daq_info_widget.update_rec_state(server=server, state=state)

                if reply == 'shutdown':

                    logging.info("Interpreter confirmed shutdown")

            # Debug
            msg = "Standard {} reply received: '{}' with data '{}'".format(sender, reply, reply_data)
            logging.debug(msg)

        elif _type == 'ERROR':
            msg = "{} error occurred: '{}' with data '{}'".format(sender, reply, reply_data)
            logging.error(msg)
            if self.info_dock.isHidden():
                self.info_dock.setVisible(True)

        else:
            logging.info("Received reply '{}' from '{}' with data '{}'".format(reply, sender, reply_data))

    def _validate_no_scan(self):
        return True


def run():
    app = QtWidgets.QApplication(sys.argv)
    font = QtGui.QFont()
    font.setPointSize(13)  # Make font size chonky for the not-so-young operators ;)
    app.setFont(font)
    gui = MonitorGUI()
    sys.exit(app.exec())


if __name__ == '__main__':
    run()
