import time
from PyQt5 import QtWidgets, QtCore
from collections import defaultdict

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
        motorstage_widget = ic_cntrl_wdgts.MotorStageControlWidget(server=server, enable=any(x in self.setup[server]['devices'] for x in ('ScanStage', 'SetupTableStage', 'ExternalCupStage')))
        scan_widget = ic_cntrl_wdgts.ScanControlWidget(server=server, daq_setup=self.setup[server]['daq'], enable='ScanStage' in self.setup[server]['devices'] and ro_device is not None)
        daq_widget = ic_cntrl_wdgts.DAQControlWidget(server=server, ro_device=ro_device, enable=ro_device is not None or 'RadiationMonitor' in self.setup[server]['devices'])
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
   
    def check_finish(self, server, eta_n_scans):
        if eta_n_scans == 0 and self.tab_widgets[server]['scan'].auto_finish_scan:
            self.send_cmd(hostname=server, target='__scan__', cmd='handle_interaction', cmd_data={'kwargs': {'interaction': 'finish'}})


    def scan_status(self, server, status='started'):
        read_only = status == 'started'
        # Set read-only state according to 'status'
        for t, w in self.tab_widgets[server].items():
            w.set_read_only(read_only=read_only)
        
        # Always have scan interactino stuff and status enabled
        self.tab_widgets[server]['scan'].widgets['scan_interaction_container'].setEnabled(True)
        self.tab_widgets[server]['scan'].widgets['scan_interaction_container'].set_read_only(False)
        self.tab_widgets[server]['status'].set_read_only(False)
        self.tab_widgets[server]['scan'].enable_after_scan_ui(not read_only)
            
    def update_rec_state(self, server, state):
        self.tab_widgets[server]['daq'].update_rec_state(state)
