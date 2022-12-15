import time
from PyQt5 import QtWidgets, QtCore
from collections import defaultdict

from setuptools import setup

# Pacakage imports
import irrad_control.gui.widgets.control_widgets as ic_cntrl_wdgts
from irrad_control.gui.widgets import NoBackgroundScrollArea


class IrradControlTab(QtWidgets.QWidget):
    """Control widget for the irradiation control software"""

    sendCmd = QtCore.pyqtSignal(dict)
    stageInfo = QtCore.pyqtSignal(dict)
    enableDAQRec = QtCore.pyqtSignal(str, bool)

    def __init__(self, setup, parent=None):
        super(IrradControlTab, self).__init__(parent)

        # Setup related
        self.setup = setup  # Store setup of server(s)

        # Make layout
        self.setLayout(QtWidgets.QVBoxLayout())

        # One tab per server
        self.tabs = QtWidgets.QTabWidget()
        self.layout().addWidget(self.tabs)

        self._beam_down_timer = {}
        self._beam_down = {}

        # Tab widgets
        self.tab_widgets = defaultdict(dict)

        for server in self.setup:
            self._init_tab(server=server)
            self.enable_control(server=server, enable=False)

    def _init_tab(self, server):

        # R/O device
        ro_device = None if 'readout' not in self.setup[server] else self.setup[server]['readout']['device']

        # Get widgets
        motorstage_widget = ic_cntrl_wdgts.MotorStageControlWidget(server=server)
        scan_widget = ic_cntrl_wdgts.ScanControlWidget(server=server, daq_setup=self.setup[server]['daq'])
        daq_widget = ic_cntrl_wdgts.DAQControlWidget(server=server, ro_device=ro_device)
        status_widget = ic_cntrl_wdgts.StatusInfoWidget()

        # Connect command signals
        motorstage_widget.sendCmd.connect(lambda cmd: self.send_cmd(**cmd))
        scan_widget.sendCmd.connect(lambda cmd: self.send_cmd(**cmd))
        daq_widget.sendCmd.connect(lambda cmd: self.send_cmd(**cmd))
        daq_widget.enableDAQRec.connect(lambda s, b: self.enableDAQRec.emit(s, b))

        # Split tab in quadrants
        splitter = QtWidgets.QSplitter()
        splitter.setOrientation(QtCore.Qt.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter_upper = QtWidgets.QSplitter()
        splitter_upper.setOrientation(QtCore.Qt.Horizontal)
        splitter_upper.setChildrenCollapsible(False)
        splitter_lower = QtWidgets.QSplitter()
        splitter_lower.setOrientation(QtCore.Qt.Horizontal)
        splitter_lower.setChildrenCollapsible(False)

        # Make quadrants
        splitter_upper.addWidget(motorstage_widget)
        splitter_upper.addWidget(scan_widget)
        splitter_lower.addWidget(daq_widget)
        splitter_lower.addWidget(status_widget)

        # Add to splitter
        splitter.addWidget(splitter_upper)
        splitter.addWidget(splitter_lower)

        # Add this to tab
        self.tabs.addTab(NoBackgroundScrollArea(widget=splitter), self.setup[server]['name'])

        # Add to container
        self.tab_widgets[server]['motorstage'] = motorstage_widget
        self.tab_widgets[server]['scan'] = scan_widget
        self.tab_widgets[server]['daq'] = daq_widget
        self.tab_widgets[server]['status'] = status_widget

        # Appearance
        self.show()

        splitter_upper.setSizes([self.width(), self.width()])
        splitter_lower.setSizes([self.width(), self.width()])
        splitter.setSizes([self.height(), self.height()])

    def enable_control(self, server, enable=True):
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == self.setup[server]['name']:
                self.tabs.widget(i).setEnabled(enable)


    def send_cmd(self, hostname, target, cmd, cmd_data=None):
        """Function emitting signal with command dict which is send to *server* in main"""
        self.sendCmd.emit({'hostname': hostname, 'target': target, 'cmd': cmd, 'cmd_data': cmd_data})

    def check_no_beam(self, server, beam_current):

        # If this server has no minimum scan current set
        if self.tab_widgets[server]['scan'].scan_params['min_current'] > 0:

            if beam_current < self.tab_widgets[server]['scan'].scan_params['min_current']:

                self._beam_down_timer[server] = time.time()

                if server not in self._beam_down or not self._beam_down[server]:
                    self.send_cmd(hostname=server, target='__scan__', cmd='handle_event', cmd_data={'kwargs': {'event': 'beam_down'}})
                    self._beam_down[server] = True

            else:
                if server in self._beam_down and self._beam_down[server]:
                    if time.time() - self._beam_down_timer[server] > 1.0:
                        self.send_cmd(hostname=server, target='__scan__', cmd='handle_event', cmd_data={'kwargs': {'event': 'beam_ok'}})
                        self._beam_down[server] = False
    
    def check_finish(self, server, eta_n_scans):
        
        if eta_n_scans == 0 and self.tab_widgets[server]['scan'].auto_finish_scan:
            self.send_cmd(hostname=server, target='__scan__', cmd='handle_event', cmd_data={'kwargs': {'event': 'finish'}})


    def scan_status(self, server, status='started'):
        # Set everything read-only when scan starts
        for t, w in self.tab_widgets[server].items():
            w.set_read_only(read_only=True)
        # Always have scan interactino stuff enabled
        if status == 'started':
            self.tab_widgets[server]['scan'].widgets['scan_interaction_container'].setEnabled(True)
            self.tab_widgets[server]['scan'].widgets['scan_interaction_container'].set_read_only(False)
        else:
            self.tab_widgets[server]['scan'].widgets['scan_interaction_container'].setEnabled(False)
            self.tab_widgets[server]['scan'].widgets['scan_interaction_container'].set_read_only(True)
            
    def update_rec_state(self, server, state):
        self.tab_widgets[server]['daq'].update_rec_state(state)
