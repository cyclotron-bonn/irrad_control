from PyQt5 import QtWidgets, QtCore
from copy import deepcopy
from irrad_control import config, config_file
from irrad_control.utils.tools import save_yaml
from irrad_control.devices import DEVICES_CONFIG
from irrad_control.gui.widgets.setup_widgets import SessionSetupWidget, ServerSetupWidget


initial_config = deepcopy(config)


class IrradSetupTab(QtWidgets.QWidget):
    """Setup widget for the irradiation control software"""

    # Signal emitted when setup is completed
    setupCompleted = QtCore.pyqtSignal(dict)

    def __init__(self, parent=None):
        super(IrradSetupTab, self).__init__(parent)

        # Layouts; split in half's
        self.main_layout = QtWidgets.QHBoxLayout()

        # Make two half's
        self.left_widget = QtWidgets.QTabWidget()
        self.left_widget.setLayout(QtWidgets.QVBoxLayout())
        self.right_widget = QtWidgets.QTabWidget()
        self.right_widget.setLayout(QtWidgets.QVBoxLayout())

        # Splitters
        self.main_splitter = QtWidgets.QSplitter()
        self.main_splitter.setOrientation(QtCore.Qt.Horizontal)
        self.main_splitter.addWidget(self.left_widget)
        self.main_splitter.addWidget(self.right_widget)
        self.main_splitter.setSizes([int(self.width() / 2.)] * 2)
        self.main_splitter.setChildrenCollapsible(False)
        self.right_widget.setMinimumSize(self.main_splitter.frameWidth(), self.main_splitter.height())

        # Add splitters to main layout
        self.main_layout.addWidget(self.main_splitter)

        # Add main layout to widget layout and add ok button
        self.setLayout(self.main_layout)

        # Dict to store info for setup in
        self.setup = {}
        self.session_setup = SessionSetupWidget()
        self.session_setup.setup_widgets['selection'].setupChanged.connect(lambda setup: self.handle_server(setup))
        self.server_setup = ServerSetupWidget()

        # State of setup tab
        self.isSetup = False

        # Connect signal
        self.setupCompleted.connect(lambda _: self.set_read_only(True))
        
        # Setup te widgets for daq, session and connect
        self._init_setup()

    def _init_setup(self):
        """Setup all the necesary widgets and connections"""

        # Left side first
        # Add main widget
        self.left_widget.layout().addWidget(self.session_setup)
        self.left_widget.layout().addStretch()
        self.right_widget.layout().addWidget(QtWidgets.QLabel('Selected server(s)'))
        self.right_widget.layout().addWidget(self.server_setup)

        # Button for completing the setup
        self.btn_launch = QtWidgets.QPushButton('Start session')
        self.btn_launch.clicked.connect(self.update_setup)
        self.btn_launch.clicked.connect(lambda: self.setupCompleted.emit(self.setup))
        self.btn_launch.clicked.connect(self._save_setup)
        self.btn_launch.setEnabled(False)

        self.left_widget.layout().addWidget(self.btn_launch)
        

        # Connect
        self.session_setup.setupValid.connect(self._check_setup)
        self.server_setup.setupValid.connect(self._check_setup)

    def _check_setup(self):
        self.isSetup = self.session_setup.isSetup and self.server_setup.isSetup
        self.btn_launch.setEnabled(self.isSetup)

    def handle_server(self, selection):

        # Add and overwrite
        for ip, name in selection.items():
            self.server_setup.add_server(ip, name=name)

        current_servers = list(self.server_setup.server_ips.keys())

        # Remove
        for server_ip in current_servers:
            if server_ip not in selection:
                self.server_setup.remove_server(server_ip)

    def _save_setup(self):
        """Save setup dict to yaml file and save in output path"""

        # Save setup
        save_yaml(path=f"{self.setup['session']['outfile']}.yaml", data=self.setup)

        initial_servers = initial_config['server']['all']
        current_servers = config['server']['all']

        n_servers_changed = len(initial_servers) != len(current_servers)
        content_servers_changed = not all(current_servers[k] == initial_servers[k] for k in initial_servers)

        # Open the config.yaml and overwrite it with current server_ips if something changed
        if n_servers_changed or content_servers_changed:
            save_yaml(path=config_file, data=config)

    def update_setup(self):
        """Update the info into the setup dict"""

        # Session setup
        self.setup['session'] = self.session_setup.setup_widgets['session'].setup()

        # Network
        self.setup['host'] = self.session_setup.setup_widgets['network'].setup()

        # Server setup
        self.setup['server'] = {}

        # Loop over servers
        for server_ip, server_name in self.server_setup.server_ips.items():

            server_setup = {}

            # Update server name
            server_setup['name'] = server_name
            config['server']['all'][server_ip] = server_name

            # Readout
            if self.server_setup.setup_widgets[server_ip]['readout_sel'].setup() != 'None':
                server_setup['readout'] = self.server_setup.setup_widgets[server_ip]['readout_dev'].setup()

            # DAQ
            server_setup['daq'] = self.server_setup.setup_widgets[server_ip]['daq'].setup()

            # Server devices
            server_setup['devices'] = {}

            # Loop only over selected devices
            for device in [d for d, s in self.server_setup.setup_widgets[server_ip]['device'].setup().items() if s]:

                # Setup device and init
                server_setup['devices'][device] = {}
                server_setup['devices'][device]['init'] = DEVICES_CONFIG[device]['init']

                if device == 'ArduinoNTCReadout':
                    server_setup['devices'][device]['setup'] = self.server_setup.setup_widgets[server_ip]['temp'].setup()

            # Add
            self.setup['server'][server_ip] = server_setup

    def set_read_only(self, read_only=True):

        # Disable/enable main widgets to set to read_only
        self.session_setup.set_read_only(read_only)
        self.server_setup.set_read_only(read_only)
        self.btn_launch.setEnabled(not read_only)
