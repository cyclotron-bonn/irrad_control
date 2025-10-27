import os
import time
import logging
import subprocess
from PyQt5 import QtWidgets, QtCore, QtGui
from collections import defaultdict

# Package imports
import irrad_control.devices.readout as ro
from irrad_control.utils.logger import log_levels
from irrad_control.utils.worker import QtWorker
from irrad_control.gui.utils import check_unique_input, fill_combobox_items, remove_widget, get_host_ip
from irrad_control.devices import DEVICES_CONFIG
from irrad_control.gui.widgets.util_widgets import GridContainer, NoBackgroundScrollArea, NoWheelQComboBox
from irrad_control import config, config_file, tmp_path
from irrad_control.utils.tools import save_yaml
from irrad_control.ions import get_ions


def _check_has_text(_edit):
    t = _edit.text()
    return True if t and t != '...' else False


class BaseSetupWidget(GridContainer):

    setupChanged = QtCore.pyqtSignal(dict)

    @property
    def isSetup(self):
        return self._is_setup()

    @isSetup.setter
    def isSetup(self, v):
        raise ValueError("'isSetup' is read-only attribute")

    def __init__(self, name, parent=None):
        super(BaseSetupWidget, self).__init__(name=name, parent=parent)

    def setup(self):
        raise NotImplementedError('Implement a *setup* method which returns a setup dict')

    def _setup_changed(self):
        self.setupChanged.emit(self.setup())

    def _is_setup(self):
        return True

#################################################################
# Irradiation session setup widget                              #
#################################################################


class SessionSetupWidget(QtWidgets.QWidget):

    # Signal which is emitted whenever the server setup has been changed; bool indicates whether the setup is valid
    setupValid = QtCore.pyqtSignal(bool)

    def __init__(self, parent=None):
        super(SessionSetupWidget, self).__init__(parent=parent)

        # The main layout for this widget
        self.setLayout(QtWidgets.QVBoxLayout())

        # Server setup; store the entire setup of all servers in this bad boy
        self.setup_widgets = {}

        # Store dict of ips and names
        self.server_ips = {}

        self.isSetup = False

        self._init_setup()

    def _init_setup(self):

        session_setup = SessionSetup('Session')
        network_setup = NetworkSetup('Network')
        server_selection = ServerSelection('Server selection')

        network_setup.serverIPsFound.connect(lambda ips: server_selection.add_selection(ips))
        network_setup.serverIPsFound.connect(
            lambda ips: None if len(ips) == 0 else
            server_selection.widgets[ips[0]]['checkbox'].setChecked(1)
            if (config['server']['default'] not in ips or len(ips) == 1)
            else server_selection.widgets[config['server']['default']]['checkbox'].setChecked(1)
        )

        self.layout().addWidget(session_setup)
        self.layout().addWidget(network_setup)
        self.layout().addWidget(server_selection)

        self.setup_widgets['session'] = session_setup
        self.setup_widgets['network'] = network_setup
        self.setup_widgets['selection'] = server_selection

        # Connect config widgets
        for wdgt in self.setup_widgets:
            self.setup_widgets[wdgt].setupChanged.connect(self._validate_setup)

    def _validate_setup(self):

        try:

            # Check whether all widgets are setup
            for _, w in self.setup_widgets.items():
                if not w.isSetup:
                    logging.warning("{} is not properly set up".format(w.name.capitalize()))
                    self.isSetup = False
                    return

            self.isSetup = True
        finally:
            self.setupValid.emit(self.isSetup)

    def set_read_only(self, read_only=True):
        for widget in self.setup_widgets:
            self.setup_widgets[widget].set_read_only(read_only=read_only)

#################################################################
# Setup widgets related to the setup of the irradiation session #
#################################################################


class SessionSetup(BaseSetupWidget):

    def __init__(self, name, parent=None):
        super(SessionSetup, self).__init__(name=name, parent=parent)

        # Attributes for paths and files
        self.output_path = os.getcwd()
        self.sids = []

        self._init_setup()

    def _init_setup(self):

        # Label and widgets to set the output folder
        label_folder = QtWidgets.QLabel('Output folder:')
        edit_folder = QtWidgets.QLineEdit()
        edit_folder.setText(self.output_path)
        edit_folder.setReadOnly(True)
        btn_folder = QtWidgets.QPushButton(' Set folder')
        btn_folder.setIcon(btn_folder.style().standardIcon(QtWidgets.QStyle.SP_DirIcon))
        btn_folder.clicked.connect(self._get_output_folder)
        btn_folder.clicked.connect(lambda _: edit_folder.setText(self.output_path))
        btn_dump = QtWidgets.QPushButton(' Dump')
        btn_dump.setIcon(btn_dump.style().standardIcon(QtWidgets.QStyle.SP_TrashIcon))
        btn_dump.clicked.connect(lambda _: edit_folder.setText(tmp_path))

        # Add to layout
        self.add_widget(widget=[label_folder, edit_folder, btn_dump, btn_folder])

        # Label and widgets for output file
        label_out_file = QtWidgets.QLabel('Output file:')
        label_out_file.setToolTip('Name of output file containing raw and interpreted data. Cannot contain whitespaces!')
        edit_out_file = QtWidgets.QLineEdit()
        edit_out_file.setPlaceholderText('irradiation_{}'.format('_'.join(time.asctime().split())))
        edit_out_file.textEdited.connect(lambda t, e=edit_out_file: e.setText(t.replace(' ', '_')))  # Don't allow whitespaces

        # Add to layout
        self.add_widget(widget=[label_out_file, edit_out_file])

        # Label and widgets for SIDs
        label_sid = QtWidgets.QLabel('Sample ID(s):')
        label_sid.setToolTip('Sample ID (SID) of the device to be irradiated. Given by radiation protection')
        layout_sid = QtWidgets.QHBoxLayout()
        edit_running_number = QtWidgets.QLineEdit()
        edit_running_number.setPlaceholderText('Running ID number')
        edit_running_number.setValidator(QtGui.QIntValidator())
        edit_sub_letter = QtWidgets.QLineEdit()
        edit_sub_letter.setPlaceholderText('Sub ID letter')
        edit_group = QtWidgets.QLineEdit()
        edit_group.setPlaceholderText('Group / Experiment')
        edit_desc = QtWidgets.QLineEdit()
        edit_desc.setPlaceholderText('Description')
        button_add_sid = QtWidgets.QPushButton('Add SID')
        button_add_sid.setToolTip('Add SID for this session. Enter at least the running number to add.')
        button_add_sid.setEnabled(False)
        
        self.widgets_sid = {'ern': edit_running_number, 'esl': edit_sub_letter, 'eg': edit_group, 'ed': edit_desc, 'bas': button_add_sid}

        for i, k in enumerate(('ern', 'esl', 'eg', 'ed')):
            ws = self.widgets_sid[k]
            if isinstance(ws, QtWidgets.QLineEdit):
                ws.setAlignment(QtCore.Qt.AlignHCenter)
                ws.textChanged.connect(lambda _: self._check_sid())

            if i != 0:
                layout_sid.addWidget(QtWidgets.QLabel('-'))

            layout_sid.addWidget(ws)

        button_add_sid.clicked.connect(self._add_sid)

        # Add to layout
        self.add_widget(widget=[label_sid, layout_sid, button_add_sid])

        self.sid_container = GridContainer(name='Selected SIDs')
        self.sid_container.setToolTip('Showing currently selected SIDs')
        self.add_widget(widget=[QtWidgets.QLabel(''), self.sid_container])
        
        # Label and combobox to set logging level
        label_logging = QtWidgets.QLabel('Logging level:')
        combo_logging = NoWheelQComboBox()
        combo_logging.addItems([log_levels[lvl] for lvl in sorted([n_lvl for n_lvl in log_levels if isinstance(n_lvl, int)])])
        combo_logging.setCurrentIndex(combo_logging.findText('INFO'))

        # Add to layout
        self.add_widget(widget=[label_logging, combo_logging])

        self.widgets['logging_combo'] = combo_logging
        self.widgets['folder_edit'] = edit_folder
        self.widgets['outfile_edit'] = edit_out_file

    def _get_output_folder(self):
        """Opens a QFileDialog to select/create an output folder"""

        caption = 'Select output folder'
        path = QtWidgets.QFileDialog.getExistingDirectory(caption=caption, directory=self.output_path)

        # If a path has been selected and its not the current path, update
        if path and path != self.output_path:
            self.output_path = path

    def _build_sid(self):
        # SID pattern -> SID-RunningNumber(SubIdentifier)-Group-Description
        sid_base = f"SID-{self.widgets_sid['ern'].text()}{self.widgets_sid['esl'].text()}"
        sid_tail = '-'.join(self.widgets_sid[k].text() for k in ('eg', 'ed') if self.widgets_sid[k].text())
        return f"{sid_base}-{sid_tail}" 

    def _check_sid(self):
        # Don't require sub letter of SID
        check = all(self.widgets_sid[k].text() for k in ('ern', 'eg', 'ed'))
        check = check and self._build_sid() not in self.sids 
        self.widgets_sid['bas'].setEnabled(check)

    def _add_sid(self):

        sid = self._build_sid()
        sid_label = QtWidgets.QLabel(f"SID #{len(self.sids)}:" + '\t' + f"{sid}")
        sid_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        btn_sid_rmv = QtWidgets.QPushButton()
        btn_sid_rmv.setIcon(btn_sid_rmv.style().standardIcon(QtWidgets.QStyle.SP_TrashIcon))
        btn_sid_rmv.setToolTip(f'Remove SID: {sid}')
        btn_sid_rmv.clicked.connect(lambda _, s=sid: self._remove_sid(s))

        self.sid_container.widgets[sid] = {'label': sid_label, 'btn': btn_sid_rmv}
        self.sid_container.add_widget(widget=[sid_label, btn_sid_rmv])

        self.sids.append(sid)

        # Clear input after adding SID
        for _, ws in self.widgets_sid.items():
            if isinstance(ws, QtWidgets.QLineEdit):
                ws.clear()

    def _remove_sid(self, sid):

        self.sids.remove(sid)
        self.sid_container.remove_widget(widget=self.sid_container.widgets[sid].values())
        del self.sid_container.widgets[sid]

        # Reorder labels
        for i, s in enumerate(self.sids):
            self.sid_container.widgets[s]['label'].setText(f"SID #{i}:" + '\t' + f"{s}")

    def setup(self):

        setup = {}
        setup['loglevel'] = self.widgets['logging_combo'].currentText()
        setup['outfolder'] = self.widgets['folder_edit'].text()
        setup['outfile'] = os.path.join(self.widgets['folder_edit'].text(), self.widgets['outfile_edit'].text() or self.widgets['outfile_edit'].placeholderText())
        
        if self.sids:
            setup['sids'] = self.sids
        
        return setup


class NetworkSetup(BaseSetupWidget):

    serverIPsFound = QtCore.pyqtSignal(list)

    def __init__(self, name, parent=None):
        super(NetworkSetup, self).__init__(name=name, parent=parent)

        # Get global threadpool instance to launch search for available servers
        self.threadpool = QtCore.QThreadPool()
        self.available_servers = []
        self.selected_servers = []

        self._init_setup()
        self.find_servers()

    def _init_setup(self):

        # Host PC IP label and widget
        label_host = QtWidgets.QLabel('Host IP:')
        edit_host = QtWidgets.QLineEdit()
        edit_host.textEdited.connect(lambda _: self._setup_changed())
        edit_host.setInputMask("000.000.000.000;_")
        host_ip = get_host_ip()

        # If host can be found using get_host_ip(), don't allow manual input and don't show
        if host_ip is not None:
            edit_host.setText(host_ip)
            edit_host.setReadOnly(True)
            label_host.setVisible(False)
            edit_host.setVisible(False)

        # Add to layout
        self.add_widget(widget=[label_host, edit_host])

        # Server IP label and widgets
        label_add_server = QtWidgets.QLabel('Add server IP:')
        edit_server = QtWidgets.QLineEdit()
        edit_server.setInputMask("000.000.000.000;_")
        edit_server.textEdited.connect(lambda text: btn_add_server.setEnabled(text != '...' and text not in config['server']['all']))
        edit_server.textEdited.connect(lambda text: btn_add_server.setToolTip(
            "IP already in list of known server IPs" if text in config['server']['all'] else "Add IP to list of known servers"))
        btn_add_server = QtWidgets.QPushButton('Add')
        btn_add_server.clicked.connect(lambda _: self._add_to_known_servers(ip=edit_server.text()))
        btn_add_server.clicked.connect(lambda _: self.find_servers())
        btn_add_server.clicked.connect(lambda _: btn_add_server.setEnabled(False))
        btn_add_server.setEnabled(False)

        # Add to layout
        self.add_widget(widget=[label_add_server, edit_server, btn_add_server])

        self.label_status = QtWidgets.QLabel("Status")
        self.serverIPsFound.connect(lambda ips: self.label_status.setText("{} of {} known servers found.".format(len(ips), len(config['server']['all']))))

        # Add to layout
        self.add_widget(widget=self.label_status)

        self.widgets['host_edit'] = edit_host
        self.widgets['server_edit'] = edit_server

    def _add_to_known_servers(self, ip):
        """Add IP address *ip* to irrad_control.server_ips. Sets default IP if wanted"""

        msg = 'Set {} as default server address?'.format(ip)
        reply = QtWidgets.QMessageBox.question(self, 'Add server IP', msg, QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)

        if reply == QtWidgets.QMessageBox.Yes:
            config['server']['default'] = ip

        config['server']['all'][ip] = 'none'

        # Open the config.yaml and overwrite it with current server_ips
        save_yaml(path=config_file, data=config)

    def find_servers(self):

        self.label_status.setText("Finding server(s)...")
        self.threadpool.start(QtWorker(func=self._find_available_servers))

    def _find_available_servers(self, timeout=10):

        n_available = len(config['server']['all'])
        start = time.time()
        while len(self.available_servers) != n_available and time.time() - start < timeout:

            for ip in config['server']['all']:
                # If we already have found this server in the network, continue
                if ip in self.available_servers:
                    continue

                p = subprocess.Popen(["ping", "-q", "-c 1", "-W 1", ip], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                res = p.communicate(), p.returncode
                if res[-1] == 0:
                    self.available_servers.append(ip)
                else:
                    n_available -= 1

        self.serverIPsFound.emit(self.available_servers)

    def setup(self):
        return self.widgets['host_edit'].text()

    def _is_setup(self):
        check = False if self.widgets['host_edit'].isVisible() and not self.widgets['host_edit'].text() else True

        # Logging
        if not check:
            logging.warning("Host IP could not be determined. Please enter manually!")

        return check


class ServerSelection(BaseSetupWidget):

    def __init__(self, name, parent=None):
        super(ServerSelection, self).__init__(name=name, parent=parent)

    def add_selection(self, selection):

        for i, ip in enumerate(selection):

            if ip in self.widgets:
                continue

            chbx = QtWidgets.QCheckBox(str(ip))
            edit = QtWidgets.QLineEdit()
            default = 'Server_{}'.format(i + 1)
            edit.setPlaceholderText(default if ip not in config['server']['all'] else config['server']['all'][ip] if config['server']['all'][ip] != 'none' else default)

            # Connect
            chbx.stateChanged.connect(self._setup_changed)
            edit.textChanged.connect(self._setup_changed)

            self.widgets[ip] = {'checkbox': chbx, 'edit': edit}

            self.add_widget(widget=[chbx, edit])

    def setup(self):
        return {ip: con['edit'].text() or con['edit'].placeholderText() for ip, con in self.widgets.items() if con['checkbox'].isChecked()}

    def _is_setup(self):
        # Server selection check
        server_names = [(val['edit'].text() or val['edit'].placeholderText()) for val in self.widgets.values()]
        check_0 = any(chbx.isChecked() for chbx in [val['checkbox'] for val in self.widgets.values()])
        check_1 = len(set(server_names)) == len(server_names)

        # Logging
        if not check_0:
            logging.warning("No server is selected. Please select a server connected to control the setup")
        if not check_1:
            logging.warning("Server names must be unique.")

        return check_0 and check_1


#################################################################
# Server setup widget                                           #
#################################################################


class ServerSetupWidget(QtWidgets.QWidget):
    """
    Widget to do the setup of each available server. This includes what devices the server controls and
    the settings of these devices themselves. Each server is represented as tab within the self widget.
    """

    # Signal which is emitted whenever the server setup has been changed; bool indicates whether the setup is valid
    setupValid = QtCore.pyqtSignal(bool)

    def __init__(self, parent=None):
        super(ServerSetupWidget, self).__init__(parent)

        # The main layout for this widget
        self.setLayout(QtWidgets.QVBoxLayout())

        # No margins
        self.layout().setContentsMargins(0, 0, 0, 0)

        # Tabs for each available server
        self.tabs = QtWidgets.QTabWidget()
        self.layout().addWidget(self.tabs)

        # Server setup; store the entire setup of all servers in this bad boy
        self.setup_widgets = {}
        self.tab_widgets = {}

        # Store dict of ips and names
        self.server_ips = {}

        self.isSetup = False

    def add_server(self, ip, name=None):
        """Add a server  with ip *ip* for setup"""

        # Number servers
        current_server = name if name is not None else 'Server_{}'.format(self.tabs.count() + 1)

        # If this server is not already in setup
        if ip not in self.server_ips:
            # Setup
            self._init_setup(ip, current_server)
            self._validate_setup()

        else:
            self.tabs.setTabText(self.tabs.indexOf(self.tab_widgets[ip]), current_server)

        # Store/rename server name and ip
        self.server_ips[ip] = current_server

    def remove_server(self, ip):

        if ip not in self.tab_widgets:
            logging.warning("Server {} not in setup and therefore cannot be removed.".format(ip))
            return

        self.tabs.removeTab(self.tabs.indexOf(self.tab_widgets[ip]))
        del self.tab_widgets[ip]
        del self.server_ips[ip]
        del self.setup_widgets[ip]

    def _update_readout_widget(self, ip, ro_device, layout):

        if self.setup_widgets[ip]['readout_dev'].device == ro_device:
            return
        elif ro_device != 'None':
            ro_device_setup_updated = ReadoutDeviceSetup(name='Readout', device=ro_device)
            remove_widget(widget=self.setup_widgets[ip]['readout_dev'], layout=layout, replace_with=ro_device_setup_updated)
            self.setup_widgets[ip]['readout_dev'] = ro_device_setup_updated

    def _init_setup(self, ip, name=None):

        # Layout
        _layout = QtWidgets.QVBoxLayout()

        # Init setup
        ro_device_sel = ReadoutDeviceSelection(name='Readout device')
        serv_device_sel = ServerDeviceSelection(name='Server devices')
        daq_setup = DAQSetup(name='Data acquisition')
        ro_device_setup = ReadoutDeviceSetup('Readout', device=ro.RO_DEVICES.DAQBoard)
        arduino_temp_setup = NTCSetup(name='ArduinoNTCReadout')

        ro_device_sel.setupChanged.connect(lambda state, _ip=ip, _l=_layout:
                                           (self._update_readout_widget(_ip, state, _l),
                                            self.setup_widgets[_ip]['readout_dev'].setVisible(state != 'None'),
                                            daq_setup.setVisible(state != 'None'),
                                            None if 'ADCBoard' not in serv_device_sel.widgets else
                                            serv_device_sel.widgets['ADCBoard'].setChecked(
                                                state != 'None'),
                                            None if 'ADCBoard' not in serv_device_sel.widgets else
                                            serv_device_sel.widgets['ADCBoard'].setEnabled(
                                                not state != 'None'),
                                            None if 'IrradDAQBoard' not in serv_device_sel.widgets else
                                            serv_device_sel.widgets['IrradDAQBoard'].setChecked(
                                                state == ro.RO_DEVICES.DAQBoard),
                                            None if 'IrradDAQBoard' not in serv_device_sel.widgets else
                                            serv_device_sel.widgets['IrradDAQBoard'].setEnabled(
                                                state != ro.RO_DEVICES.DAQBoard)
                                            ))

        # TODO: make this generic for server devices that have a dedicated setup widget
        serv_device_sel.widgets['ArduinoNTCReadout'].stateChanged.connect(lambda state: arduino_temp_setup.setVisible(bool(state)))

        # Add to layout
        _layout.addWidget(ro_device_sel)
        _layout.addWidget(serv_device_sel)
        _layout.addWidget(arduino_temp_setup)
        _layout.addWidget(daq_setup)
        _layout.addWidget(ro_device_setup)
        _layout.addStretch()

        _widget = QtWidgets.QWidget()
        _widget.setLayout(_layout)

        # Store widgets
        self.setup_widgets[ip] = {'readout_sel': ro_device_sel,
                                  'device': serv_device_sel,
                                  'temp': arduino_temp_setup,
                                  'daq': daq_setup,
                                  'readout_dev': ro_device_setup}

        # Connect config widgets
        for wdgt in self.setup_widgets[ip]:
            self.setup_widgets[ip][wdgt].setupChanged.connect(self._validate_setup)

        # Make scroll widget and set widget
        scroll_server = NoBackgroundScrollArea()
        scroll_server.setWidget(_widget)

        # Finally, add to tab bar
        self.tab_widgets[ip] = scroll_server
        self.tabs.addTab(scroll_server, name)

        # Select defaults
        ro_device_sel.widgets[ro.RO_DEVICES.DAQBoard].toggle()
        serv_device_sel.widgets['ArduinoNTCReadout'].setChecked(True)
        serv_device_sel.widgets['ArduinoNTCReadout'].setChecked(False)
        ro_device_sel.setupChanged.emit(ro_device_sel.setup())

    def _validate_setup(self):
        """Check if all necessary input is ready to continue"""

        try:

            # Loop over all servers
            for ip in self.server_ips:

                # Check whether all widgets are setup
                for _, w in self.setup_widgets[ip].items():
                    if not w.isSetup:
                        logging.warning("{} is not properly set up".format(w.name.capitalize()))
                        self.isSetup = False
                        return

                # Check if server is used to control any device
                if not any(w.isChecked() for _, w in self.setup_widgets[ip]['device'].widgets.items()) and self.setup_widgets[ip]['readout_sel'].setup() == 'None':
                    logging.warning("No readout / server devices selected for server {}. Please choose devices or remove server.".format(ip))
                    self.isSetup = False
                    return

                if self.setup_widgets[ip]['device'].widgets['ArduinoNTCReadout'].isChecked() and not any(tcb.isChecked() for tcb in self.setup_widgets[ip]['temp'].widgets['ntc_chbxs']):
                    logging.warning("Select temperature sensors for server {} or remove from devices.".format(ip))
                    self.isSetup = False
                    return

            self.isSetup = True

        finally:
            self.setupValid.emit(self.isSetup)

    def set_read_only(self, read_only=True):

        for ip in self.setup_widgets:
            for k in self.setup_widgets[ip]:
                self.setup_widgets[ip][k].set_read_only(read_only=read_only)

#################################################################
# Setup widgets related top the setup of individual RPi servers #
#################################################################


class ServerDeviceSelection(BaseSetupWidget):

    def __init__(self, name, parent=None):
        super(ServerDeviceSelection, self).__init__(name=name, parent=parent)

        self._init_setup()

    def _init_setup(self):

        # Make checkboxes for device selection
        self.widgets = {dev: QtWidgets.QCheckBox(dev) for dev in DEVICES_CONFIG}

        for k, w in self.widgets.items():
            w.stateChanged.connect(lambda _: self._setup_changed())

        # Add to layout
        self.add_widget(widget=self.widgets.values())

    def setup(self):
        return {dev: w.isChecked() for dev, w in self.widgets.items()}


class NTCSetup(BaseSetupWidget):

    def __init__(self, name, n_sensors=8, parent=None):
        super(NTCSetup, self).__init__(name=name, parent=parent)

        self.n_sensors = n_sensors

        self._init_setup()

    def _init_setup(self):

        chbxs = []
        edits = []
        for i in range(self.n_sensors):
            chbx = QtWidgets.QCheckBox()
            edit = QtWidgets.QLineEdit()
            edit.setPlaceholderText('NTC #{}'.format(i + 1))
            chbx.stateChanged.connect(lambda state, e=edit: e.setEnabled(state))
            if i == 0:
                chbx.setChecked(True)
            chbx.stateChanged.emit(chbx.checkState())
            chbxs.append(chbx)
            edits.append(edit)

            # Connect
            edit.textEdited.connect(lambda _: self._setup_changed())
            chbx.stateChanged.connect(lambda _: self._setup_changed())

        # Add to layout
        widget_list = []
        widget_list1 = []
        for j in range(len(chbxs)):
            if j < int(len(chbxs)/2):
                widget_list.append(chbxs[j])
                widget_list.append(edits[j])
            else:
                widget_list1.append(chbxs[j])
                widget_list1.append(edits[j])

        self.add_widget(widget=widget_list)
        self.add_widget(widget=widget_list1)

        self.widgets['ntc_chbxs'] = chbxs
        self.widgets['ntc_edits'] = edits

    def setup(self):
        ntc_sensors = [i for i in range(len(self.widgets['ntc_chbxs'])) if self.widgets['ntc_chbxs'][i].isChecked()]
        ntc_names = [e.text() or e.placeholderText() for i, e in enumerate(self.widgets['ntc_edits']) if i in ntc_sensors]

        return dict(zip(ntc_sensors, ntc_names))

    def _is_setup(self):
        check_edits = [e for i, e in enumerate(self.widgets['ntc_edits']) if self.widgets['ntc_chbxs'][i].isChecked()]
        check_unique = check_unique_input(check_edits)

        # Logging
        if not check_edits:
            logging.warning("No temperature sensor (NTC) selected")
        if not check_unique:
            logging.warning("Temperature sensor names must be unique")

        return False if not check_edits else check_unique


class DAQSetup(BaseSetupWidget):

    def __init__(self, name, parent=None):
        super(DAQSetup, self).__init__(name=name, parent=parent)

        self.ions = get_ions()
        self.ion_names = list(self.ions.keys())

        # Call setup
        self._init_setup()

    def _init_setup(self):
        
        # Label for name of DAQ device which is represented by the ADC
        label_ion = QtWidgets.QLabel('Ion:')
        combo_ion = NoWheelQComboBox()
        fill_combobox_items(combo_ion, self.ions)

        # Add to layout
        self.add_widget(widget=[label_ion, combo_ion])

        # Label for name of DAQ device which is represented by the ADC
        label_energy = QtWidgets.QLabel('Kinetic energy [MeV]:')
        spbx_energy = QtWidgets.QDoubleSpinBox()
        spbx_energy.wheelEvent = lambda we: we.ignore()  # Ignore wheel event
        spbx_energy.setDecimals(3)

        # Add to layout
        self.add_widget(widget=[label_energy, spbx_energy])

        # Label for name of DAQ device which is represented by the ADC
        label_stopping_power = QtWidgets.QLabel('Stopping power [MeV cm²/g]:')
        label_stopping_power_value = QtWidgets.QLabel()

        # Add to layout
        self.add_widget(widget=[label_stopping_power, label_stopping_power_value])

        # Label for readout scale combobox
        label_kappa = QtWidgets.QLabel('Hardness factor %s:' % u'\u03ba')
        combo_kappa = NoWheelQComboBox()

        # Add to layout
        self.add_widget(widget=[label_kappa, combo_kappa])

        # Proportionality constant related widgets
        label_prop = QtWidgets.QLabel('Calibration factor %s [1/V]:' % u'\u03bb')
        label_prop.setToolTip('Constant translating SEM signal to actual proton beam current via I_Beam = %s * I_FS * SEM_%s' % (u'\u03A3', u'\u03bb'))
        combo_prop = NoWheelQComboBox()

        # Add to layout
        self.add_widget(widget=[label_prop, combo_prop])

        # Connections
        combo_ion.currentTextChanged.connect(lambda text: self._setup_ion_selection(ion=text, ckappa=combo_kappa, cprop=combo_prop, senergy=spbx_energy))
        spbx_energy.valueChanged.connect(lambda _: self._setup_energy_selection(ion=combo_ion.currentText(), ckappa=combo_kappa, cprop=combo_prop, senergy=spbx_energy, lstop=label_stopping_power_value))
    
        combo_ion.currentTextChanged.emit(combo_ion.currentText())

        # Store all daq related widgets in dict
        self.widgets['ion_combo'] = combo_ion
        self.widgets['energy_spbx'] = spbx_energy
        self.widgets['kappa_combo'] = combo_kappa
        self.widgets['lambda_combo'] = combo_prop

    def _setup_ion_selection(self, ion, ckappa, cprop, senergy):

        hardness = self.ions[ion].hardness_factor(as_dict=True)
        if hardness is None:
            ckappa.setEnabled(False)
            fill_combobox_items(ckappa, {f'Unavailable for {ion}': None})
        else:
            ckappa.setEnabled(True)
            fill_combobox_items(ckappa, hardness)

        calibration = self.ions[ion].calibration(as_dict=True)
        if calibration is None:
            cprop.setEnabled(False)
            fill_combobox_items(cprop, {f'Unavailable for {ion}': None})
        else:
            cprop.setEnabled(True)
            fill_combobox_items(cprop, calibration)

        senergy.setRange(*self.ions[ion].ekin_range())
        senergy.setValue(senergy.maximum())
        senergy.valueChanged.emit(senergy.value())

    def _setup_energy_selection(self, ion, ckappa, cprop, senergy, lstop):

        ckappa_idx = self.ions[ion].hardness_factor(at_energy=self.ions[ion].ekin_at_dut(senergy.value()), return_index=True)
        ckappa.setCurrentIndex(ckappa_idx if ckappa_idx is not None else ckappa.currentIndex())

        cprop_idx = self.ions[ion].calibration(at_energy=senergy.value(), return_index=True)
        cprop.setCurrentIndex(cprop_idx if cprop_idx is not None else cprop.currentIndex())

        ekin_at_dut = self.ions[ion].ekin_at_dut(energy=senergy.value())
        if ekin_at_dut != senergy.value():
            senergy.setSuffix(f" ({ekin_at_dut:.3f} at DUT)")
        else:
            senergy.setSuffix('')

        stopping_power = self.ions[ion].stopping_power(energy=senergy.value())
        if stopping_power:
            stop_text = f"{stopping_power:.3f}"
            stopping_power_at_dut = self.ions[ion].stopping_power(energy=senergy.value(), at_dut=True)
            if stopping_power != stopping_power_at_dut:
                stop_text += f" ({stopping_power_at_dut:.3f} at DUT)"
        else:
            stop_text = f"Unavailable for {ion}"
        
        lstop.setText(stop_text)

    def setup(self):

        setup = {}
        setup['ion'] = self.widgets['ion_combo'].currentText()
        setup['ekin_initial'] = self.widgets['energy_spbx'].value()
        setup['stopping_power_initial'] = self.ions[setup['ion']].stopping_power(energy=setup['ekin_initial'])
        setup['ekin'] = self.ions[setup['ion']].ekin_at_dut(energy=setup['ekin_initial'])
        setup['stopping_power'] = self.ions[setup['ion']].stopping_power(energy=setup['ekin'])
        setup['kappa'] = self.ions[setup['ion']].hardness_factor(as_dict=True, at_index=self.widgets['kappa_combo'].currentIndex())
        setup['lambda'] = self.ions[setup['ion']].calibration(as_dict=True, at_index=self.widgets['lambda_combo'].currentIndex())
        
        return setup


class ReadoutDeviceSelection(BaseSetupWidget):

    setupChanged = QtCore.pyqtSignal(str)

    def __init__(self, name, parent=None):
        super(ReadoutDeviceSelection, self).__init__(name=name, parent=parent)

        self._init_setup()

    def _init_setup(self):

        radio_btn_grp = QtWidgets.QButtonGroup()
        btns = []
        for ro_dev in ro.RO_DEVICES + ('None',):
            rb = QtWidgets.QRadioButton(ro_dev)
            rb.clicked.connect(lambda _: self._setup_changed())
            radio_btn_grp.addButton(rb)
            self.widgets[ro_dev] = rb
            btns.append(rb)

        self.add_widget(btns)

    def setup(self):
        return [t for t in self.widgets if self.widgets[t].isChecked()][0]


class ReadoutDeviceSetup(BaseSetupWidget):
    """Setup for R/O via 8 Channels ADC ADS1256"""

    def __init__(self, name, device=ro.RO_DEVICES.DAQBoard, n_channels=8, parent=None):
        """
        Parameters
        ----------
        name: str
            Name to be displayed by GridContainer
        device: str
            Which readout device is used; can be *adc*, *ro_electronics* or *ro_board*
        n_channels: int
            Number of ADC channels
        parent: QtWidgets.QWidget
            Parent widget
        """
        super(ReadoutDeviceSetup, self).__init__(name=name, parent=parent)

        if device not in ro.RO_DEVICES:
            raise ValueError('R/O device unknown. Must be on of {}'.format(', '.join(str(d) for d in ro.RO_DEVICES)))

        self.device = device
        self.n_channels = n_channels
        self.not_used_placeholder = 'Not used'

        self._init_setup()

    def _init_setup(self):

        # Temperature sensors
        if self.device == ro.RO_DEVICES.DAQBoard:
            checkbox_ntc = QtWidgets.QCheckBox('Use NTC readout')
            ntc_setup = NTCSetup('NTCs')
            ntc_setup.setupChanged.connect(lambda _: self._setup_changed())
            ntc_setup.setVisible(False)
            checkbox_ntc.stateChanged.connect(lambda state: ntc_setup.setVisible(bool(state)))
            checkbox_ntc.stateChanged.connect(lambda _: self._setup_changed())
            self.widgets['ntc_chbx'] = checkbox_ntc
            self.widgets['ntc_setup'] = ntc_setup
            self.grid.addWidget(checkbox_ntc, self.grid.rowCount(), 0)
            self.grid.addWidget(ntc_setup, self.grid.rowCount(), 1, 1, 4)

        # Sampling rate related widgets
        label_sps = QtWidgets.QLabel('Sampling rate [sps]:')
        combo_srate = NoWheelQComboBox()
        combo_srate.addItems([str(drate) for drate in DEVICES_CONFIG['ADCBoard']['drates']])
        combo_srate.setCurrentIndex(list(DEVICES_CONFIG['ADCBoard']['drates'].keys()).index(100))
        self.widgets['srate_combo'] = combo_srate

        # Add to layout
        self.add_widget(widget=[label_sps, combo_srate])

        # R/O full-scale
        label_scale_str = 'R/O {} scale I_FS:'.format(self.device.split('_')[-1])
        label_scale = QtWidgets.QLabel(label_scale_str)
        label_scale.setToolTip("Input current corresponding to 5V full-scale output voltage")

        # Label for readout scale combobox
        widgets_to_add = [label_scale]

        if self.device != ro.RO_DEVICES.DAQBoard:
            combo_scale = NoWheelQComboBox()
            combo_scale.addItems(ro.RO_ELECTRONICS_CONFIG['ifs_labels'])
            combo_scale.setCurrentIndex(ro.RO_ELECTRONICS_CONFIG['ifs_scales'].index(ro.RO_ELECTRONICS_CONFIG['defaults']['ifs']))
            checkbox_scale = QtWidgets.QCheckBox('Set scale per channel')  # Allow individual scales per channel
            checkbox_scale.stateChanged.connect(lambda state: combo_scale.setEnabled(not bool(state)))
            widgets_to_add.extend([combo_scale, checkbox_scale])

            self.widgets['scale_combo'] = combo_scale
            self.widgets['scale_chbx'] = checkbox_scale

        else:
            combo_group_scale = {}
            lo = QtWidgets.QHBoxLayout()
            for group in ro.DAQ_BOARD_CONFIG['common']['gain_groups']:
                combo_group_scale[group] = NoWheelQComboBox()
                combo_group_scale[group].addItems(ro.DAQ_BOARD_CONFIG['common']['ifs_labels'])
                label_group = QtWidgets.QLabel('R/O group ' + group + ': ')
                lo.addWidget(label_group)
                lo.addSpacing(10)
                lo.addWidget(combo_group_scale[group])
                if group != ro.DAQ_BOARD_CONFIG['common']['gain_groups'][-1]:
                    lo.addStretch()
            checkbox_jumper = QtWidgets.QCheckBox('x 10 Jumper')
            checkbox_jumper.stateChanged.connect(
                lambda state, cbx=combo_group_scale:
                [(cbx[g].clear(), cbx[g].addItems(ro.DAQ_BOARD_CONFIG['common']['ifs_labels{}'.format('_10' if bool(state) else '')])) for g in cbx])

            widgets_to_add.extend([lo, checkbox_jumper])

            self.widgets['group_scale_combos'] = combo_group_scale
            self.widgets['jumper_chbx'] = checkbox_jumper

        # Add to layout
        self.add_widget(widget=widgets_to_add)
        self.add_widget(QtWidgets.QLabel('Channels:'))

        widgets_to_add = []
        # ADC channel related input widgets
        label_channel_number = QtWidgets.QLabel('#')
        label_channel_number.setToolTip('Number of the channel. Corresponds to physical channel on ADC')
        label_channel_name = QtWidgets.QLabel('Name')
        label_channel_name.setToolTip('Name of respective channel')
        widgets_to_add.extend([label_channel_number, label_channel_name])

        if self.device != ro.RO_DEVICES.DAQBoard:
            label_channel_scale = QtWidgets.QLabel('R/O scale')
            label_channel_scale.setToolTip('Readout scale of respective channel')
            widgets_to_add.append(label_channel_scale)
        else:
            label_channel_group = QtWidgets.QLabel('R/O group')
            label_channel_group.setToolTip('Readout group of respective channel')
            widgets_to_add.append(label_channel_group)

        label_channel_type = QtWidgets.QLabel('Type')
        label_channel_type.setToolTip('Type of channel according to the readout device')
        widgets_to_add.append(label_channel_type)

        label_channel_ref = QtWidgets.QLabel('Reference')
        label_channel_ref.setToolTip('Reference channel for measurement. Can be ground (GND) or any other channels.')
        widgets_to_add.append(label_channel_ref)

        # Add to layout
        self.add_widget(widget=widgets_to_add)

        input_widgets = defaultdict(list)

        # Loop over number of available ADC channels and make respective input widgets
        for i in range(self.n_channels):

            widgets_to_add = []

            # Channel name edit
            _edit = QtWidgets.QLineEdit()
            _edit.setPlaceholderText(self.not_used_placeholder)
            _edit.setText('' if i > len(ro.RO_DEFAULTS['ch_names']) - 1 else ro.RO_DEFAULTS['ch_names'][i])
            _edit.textEdited.connect(lambda _: self._setup_changed())
            input_widgets['channel_edits'].append(_edit)

            widgets_to_add.append(_edit)

            if self.device != ro.RO_DEVICES.DAQBoard:
                # Channel RO scale combobox
                _cbx_scale = NoWheelQComboBox()
                _cbx_scale.addItems(ro.RO_ELECTRONICS_CONFIG['ifs_labels'])
                _cbx_scale.setToolTip('Select R/O scale I_FS for each channel individually.')
                _cbx_scale.setCurrentIndex(combo_scale.currentIndex())
                _cbx_scale.setEnabled(False)
                input_widgets['scale_combos'].append(_cbx_scale)

                # Connections
                _edit.textChanged.connect(
                    lambda text, cbx=_cbx_scale, checkbox=checkbox_scale: cbx.setEnabled(checkbox.isChecked() and bool(text)))
                checkbox_scale.stateChanged.connect(
                    lambda state, cbx=_cbx_scale, edit=_edit: cbx.setEnabled(bool(state) if edit.text() else False))
                checkbox_scale.stateChanged.connect(
                    lambda _, cbx=_cbx_scale, combo=combo_scale: cbx.setCurrentIndex(combo.currentIndex()))
                combo_scale.currentIndexChanged.connect(
                    lambda idx, cbx=_cbx_scale, checkbox=checkbox_scale:
                    cbx.setCurrentIndex(idx if not checkbox.isChecked() else cbx.currentIndex()))

                widgets_to_add.append(_cbx_scale)

            else:
                _cbx_group = NoWheelQComboBox()
                _cbx_group.addItems(ro.DAQ_BOARD_CONFIG['common']['mux_groups'])
                _cbx_group.setToolTip('Select R/O group for each channel.')
                _cbx_group.setCurrentIndex(_cbx_group.findText(ro.RO_DEFAULTS['ch_groups'][i]) if i < len(ro.RO_DEFAULTS['ch_names']) else 1)  # ch12
                _cbx_group.currentIndexChanged.connect(lambda _: self._setup_changed())
                input_widgets['group_combos'].append(_cbx_group)

                # Connections
                _edit.textChanged.connect(
                    lambda text, cbx=_cbx_group: cbx.setEnabled(bool(text)))

                widgets_to_add.append(_cbx_group)

            # Channel type combobox
            _cbx_type = NoWheelQComboBox()
            _cbx_type.addItems(ro.RO_TYPES)
            _cbx_type.setToolTip('Select type of channel. If *general_purpose*, this info is used for interpretation.')
            _cbx_type.setCurrentIndex(_cbx_type.findText(ro.RO_DEFAULTS['ch_types'][i]) if i < len(ro.RO_DEFAULTS['ch_names']) else ro.RO_TYPES.index('general_purpose'))
            _cbx_type.setEnabled(bool(_edit.text()))
            input_widgets['type_combos'].append(_cbx_type)

            widgets_to_add.append(_cbx_type)

            # Reference channel to measure voltage; can be GND or any of the other channels
            _cbx_ref = NoWheelQComboBox()
            _cbx_ref.addItems(['GND'] + [str(k) for k in range(1, self.n_channels + 1) if k != i + 1])
            _cbx_ref.setCurrentIndex(0)
            _cbx_ref.setProperty('lastitem', 'GND')
            _cbx_ref.currentTextChanged.connect(lambda item, c=_cbx_ref: self._handle_ref_channels(item, c))
            _cbx_ref.setEnabled(_edit.text() != '')
            input_widgets['ref_combos'].append(_cbx_ref)

            widgets_to_add.append(_cbx_ref)

            # Connections
            _edit.textChanged.connect(lambda text, cbx=_cbx_type: cbx.setEnabled(bool(text)))
            _edit.textChanged.connect(lambda text, cbx=_cbx_ref: cbx.setEnabled(bool(text)))

            # Add to layout
            self.add_widget(widget=[QtWidgets.QLabel('{}.'.format(i + 1))] + widgets_to_add)

            _edit.textChanged.emit(_edit.text())

        # Store input widgets
        for iw in input_widgets:
            self.widgets[iw] = input_widgets[iw]

    def _handle_ref_channels(self, item, cbx):
        """Handles the ADC channel selection"""

        sender_idx = self.widgets['ref_combos'].index(cbx) + 1

        idx = None if item == 'GND' else int(item) - 1
        lastitem = cbx.property('lastitem')
        last_idx = None if lastitem == 'GND' else int(lastitem)
        cbx.setProperty('lastitem', 'GND' if idx is None else str(idx))

        if idx:

            self.widgets['channel_edits'][idx].setText('')
            self.widgets['channel_edits'][idx].setPlaceholderText('Ref. to ch. {}'.format(sender_idx))
            self.widgets['channel_edits'][idx].setEnabled(False)

            for rcbx in self.widgets['ref_combos']:
                if cbx != rcbx:
                    for i in range(rcbx.count()):
                        if rcbx.itemText(i) == item or rcbx.itemText(i) == str(sender_idx):
                            rcbx.model().item(i).setEnabled(False)

        if last_idx:

            self.widgets['channel_edits'][last_idx].setEnabled(True)
            self.widgets['channel_edits'][last_idx].setPlaceholderText(self.not_used_placeholder)

            for rcbx in self.widgets['ref_combos']:
                if cbx != rcbx:
                    for i in range(rcbx.count()):
                        if rcbx.itemText(i) == str(last_idx + 1) or (idx is None and rcbx.itemText(i) == str(sender_idx)):
                            rcbx.model().item(i).setEnabled(True)

    def setup(self):

        readout = {}

        readout['device'] = self.device
        readout['sampling_rate'] = float(self.widgets['srate_combo'].currentText())
        readout['channels'] = [e.text() for e in self.widgets['channel_edits'] if e.text()]
        readout['types'] = [c.currentText() for i, c in enumerate(self.widgets['type_combos']) if self.widgets['channel_edits'][i].text()]
        readout['ch_numbers'] = [i if self.widgets['ref_combos'][i].currentText() == 'GND'
                                 else (i, -1 + int(self.widgets['ref_combos'][i].currentText()))
                                 for i, w in enumerate(self.widgets['channel_edits']) if w.text()]

        if readout['device'] != ro.RO_DEVICES.DAQBoard:

            readout['ro_scales'] = [ro.RO_ELECTRONICS_CONFIG['ifs_scales'][ro.RO_ELECTRONICS_CONFIG['ifs_labels'].index(c.currentText())]
                                    for i, c in enumerate(self.widgets['scale_combos']) if self.widgets['channel_edits'][i].text()]
        else:
            readout['x10_jumper'] = self.widgets['jumper_chbx'].isChecked()

            scale_labels = ro.DAQ_BOARD_CONFIG['common']['ifs_labels{}'.format('_10' if readout['x10_jumper'] else '')]
            readout['ro_group_scales'] = {g: ro.DAQ_BOARD_CONFIG['common']['ifs_scales'][
                scale_labels.index(self.widgets['group_scale_combos'][g].currentText())]
                                          for g in self.widgets['group_scale_combos']}

            readout['ch_groups'] = [c.currentText() for i, c in enumerate(self.widgets['group_combos']) if self.widgets['channel_edits'][i].text()]

            if self.widgets['ntc_chbx'].isChecked():
                readout['ntc'] = self.widgets['ntc_setup'].setup()

        return readout

    def _is_setup(self):
        check_0 = check_unique_input(self.widgets['channel_edits'], ignore=self.not_used_placeholder)
        check_1 = any(_check_has_text(e) for e in self.widgets['channel_edits'])
        check_2 = True if 'ntc_setup' not in self.widgets else True if not self.widgets['ntc_chbx'].isChecked() else self.widgets['ntc_setup'].isSetup
        check_3 = True if 'ntc_setup' not in self.widgets else True if not self.widgets['ntc_chbx'].isChecked() else len([True for gcbx in self.widgets['group_combos'] if gcbx.currentText() == 'ntc' and gcbx.isEnabled()]) == 1

        # Logging
        if not check_0:
            logging.warning("Channel names must be unique")
        if not check_1:
            logging.warning("No channel selected. Enter a channel name to activate respective channel")
        if not check_2:
            logging.warning("DAQBoard NTC readout not set up")
        if not check_3:
            logging.warning("No or multiple *ntc* group channels selected. Reading out NTCs requires exactly one channel to be selected as *ntc* group")

        return check_0 and check_1 and check_2 and check_3
