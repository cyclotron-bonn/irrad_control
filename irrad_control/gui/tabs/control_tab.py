import time
from PyQt5 import QtWidgets, QtCore
from collections import defaultdict

# Pacakage imports
import irrad_control.gui.widgets.control_widgets as ic_cntrl_wdgts


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

    def _init_tab(self, server):

        # Get widgets
        motorstage_widget = ic_cntrl_wdgts.MotorStageControlWidget(server=server)
        scan_widget = ic_cntrl_wdgts.ScanControlWidget(server=server)
        daq_widget = ic_cntrl_wdgts.DAQControlWidget(server=server, ro_device=self.setup[server]['readout']['device'])
        status_widget = ic_cntrl_wdgts.StatusInfoWidget('Status')

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
        self.tabs.addTab(splitter, self.setup[server]['name'])

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

    def send_cmd(self, hostname, target, cmd, cmd_data=None):
        """Function emitting signal with command dict which is send to *server* in main"""
        self.sendCmd.emit({'hostname': hostname, 'target': target, 'cmd': cmd, 'cmd_data': cmd_data})

    def check_no_beam(self, server, beam_current):

        # If this server has no minimum scan current set
        if self.tab_widgets[server]['scan'].scan_params['min_current'] > 0:

            if beam_current < self.tab_widgets[server]['scan'].scan_params['min_current']:

                self._beam_down_timer[server] = time.time()

                if server not in self._beam_down or not self._beam_down[server]:
                    self.send_cmd(server, 'stage', 'no_beam', True)
                    self._beam_down[server] = True

            else:
                if server in self._beam_down and self._beam_down[server]:
                    if time.time() - self._beam_down_timer[server] > 1.0:
                        self.send_cmd(server, 'stage', 'no_beam', False)
                        self._beam_down[server] = False

    def scan_status(self, server, status='started'):
        read_only_state = status == 'started'
        # Set everything read-only when scan starts
        for t, w in self.tab_widgets[server].items():
            w.set_read_only(read_only=read_only_state, omit=None if t != 'scan' else QtWidgets.QPushButton)

    def update_rec_state(self, server, state):
        self.tab_widgets[server]['daq'].update_rec_state(state)
