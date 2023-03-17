import sys
import time
import logging
import platform
import zmq
from email import message_from_string
from pkg_resources import get_distribution, DistributionNotFound
from PyQt5 import QtCore, QtWidgets, QtGui
from threading import Event

# Package imports
from irrad_control.utils.logger import CustomHandler, LoggingStream, log_levels
from irrad_control.utils.worker import QtWorker
from irrad_control.utils.proc_manager import ProcessManager
from irrad_control.utils.utils import get_current_git_branch
from irrad_control.gui.widgets import DaqInfoWidget, LoggingWidget, EventWidget
from irrad_control.gui.tabs import IrradSetupTab, IrradControlTab, IrradMonitorTab


PROJECT_NAME = 'Irrad Control'
GUI_AUTHORS = 'Pascal Wolf'
MINIMUM_RESOLUTION = (1366, 768)

try:
    pkgInfo = get_distribution('irrad_control').get_metadata('PKG-INFO')
    AUTHORS = message_from_string(pkgInfo)['Author']
except (DistributionNotFound, KeyError):
    AUTHORS = 'Not defined'


class IrradGUI(QtWidgets.QMainWindow):
    """Inits the main window of the irrad_control software."""

    # PyQt signals
    data_received = QtCore.pyqtSignal(dict)  # Signal for data
    log_received = QtCore.pyqtSignal(dict)  # Signal for log
    event_received = QtCore.pyqtSignal(dict)  # Signal for events
    reply_received = QtCore.pyqtSignal(dict)  # Signal for reply

    def __init__(self, parent=None):
        super(IrradGUI, self).__init__(parent)

        # Setup dict of the irradiation; is set when setup tab is completed
        self.setup = None
        
        # Needed in order to stop receiver threads
        self.stop_recv = Event()
        
        # ZMQ context; THIS IS THREADSAFE! SOCKETS ARE NOT!
        # EACH SOCKET NEEDS TO BE CREATED WITHIN ITS RESPECTIVE THREAD/PROCESS!
        self.context = zmq.Context()
        
        # QThreadPool manages GUI threads on its own; every runnable started via start(runnable) is auto-deleted after.
        self.threadpool = QtCore.QThreadPool()

        # Class to manage the server, interpreter and additional subprocesses
        self.proc_mngr = ProcessManager()

        # Keep track of successfully started daq processes
        self._started_daq_proc_hostnames = []

        # Shutdown related variables
        self._procs_launched = False
        self._shutdown_initiated = False
        self._shutdown_complete = False
        self._stopped_daq_proc_hostnames = []
        
        # Connect signals
        self.data_received.connect(lambda data: self.handle_data(data))
        self.log_received.connect(lambda log: self.handle_log(log))
        self.event_received.connect(lambda event: self.handle_event(event))
        self.reply_received.connect(lambda reply: self.handle_reply(reply))

        # Tab widgets
        self.setup_tab = None
        self.control_tab = None
        self.monitor_tab = None

        # Init user interface
        self._init_ui()
        self._init_logging()
        
    def _init_ui(self):
        """
        Initializes the user interface and displays "Hello"-message
        """

        # Main window settings
        self.setWindowTitle(PROJECT_NAME)
        self.screen = QtWidgets.QDesktopWidget().screenGeometry()
        self.setMinimumSize(MINIMUM_RESOLUTION[0], MINIMUM_RESOLUTION[1])
        self.resize(self.screen.width(), self.screen.height())
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        # Create main layout
        self.main_widget = QtWidgets.QWidget()
        self.main_layout = QtWidgets.QVBoxLayout(self.main_widget)
        self.setCentralWidget(self.main_widget)

        # Add QTabWidget for tab_widget
        self.tabs = QtWidgets.QTabWidget()

        # Main splitter
        self.main_splitter = QtWidgets.QSplitter()
        self.main_splitter.setOrientation(QtCore.Qt.Vertical)
        self.main_splitter.setChildrenCollapsible(False)

        # Sub splitter for log and displaying raw data as it comes in
        self.sub_splitter = QtWidgets.QSplitter()
        self.sub_splitter.setOrientation(QtCore.Qt.Horizontal)
        self.sub_splitter.setChildrenCollapsible(False)

        # Add to main layout
        self.main_splitter.addWidget(self.tabs)
        self.main_splitter.addWidget(self.sub_splitter)
        self.main_layout.addWidget(self.main_splitter)

        # Init widgets and add to main windowScatterPlotItem
        self._init_menu()
        self._init_tabs()
        self._init_info_dock()
        
        self.sub_splitter.setSizes([int(1. / 3. * self.width()), int(2. / 3. * self.width())])
        self.main_splitter.setSizes([int(0.8 * self.height()), int(0.2 * self.height())])
        
    def _init_menu(self):
        """Initialize the menu bar of the IrradControlWin"""

        self.file_menu = QtWidgets.QMenu('&File', self)
        self.file_menu.addAction('&Quit', self.file_quit, QtCore.Qt.CTRL + QtCore.Qt.Key_Q)
        self.menuBar().addMenu(self.file_menu)

        self.settings_menu = QtWidgets.QMenu('&Settings', self)
        self.settings_menu.addAction('&Connections')
        self.settings_menu.addAction('&Data path')
        self.menuBar().addMenu(self.settings_menu)

        self.appearance_menu = QtWidgets.QMenu('&Appearance', self)
        self.appearance_menu.setToolTipsVisible(True)
        self.appearance_menu.addAction('&Show/hide info dock', self.handle_info_ui, QtCore.Qt.CTRL + QtCore.Qt.Key_L)
        self.appearance_menu.addAction('&Show/hide DAQ dock', self.handle_daq_ui, QtCore.Qt.CTRL + QtCore.Qt.Key_D)
        self.menuBar().addMenu(self.appearance_menu)

    def _init_tabs(self):
        """
        Initializes the tabs for the control window
        """

        # Add tab_widget and widgets for the different analysis steps
        self.tab_order = ('Setup', 'Control', 'Monitor')

        # Store tabs
        tw = {}

        # Initialize each tab
        for name in self.tab_order:

            if name == 'Setup':
                self.setup_tab = IrradSetupTab(parent=self)
                self.setup_tab.session_setup.setup_widgets['session'].widgets['logging_combo'].currentTextChanged.connect(lambda lvl: self.log_widget.change_level(lvl))
                self.setup_tab.setupCompleted.connect(lambda setup: self._init_setup(setup))
                tw[name] = self.setup_tab
            else:
                tw[name] = QtWidgets.QWidget()

            self.tabs.addTab(tw[name], name)
            self.tabs.setTabEnabled(self.tabs.indexOf(tw[name]), name in ['Setup'])

    def _init_setup(self, setup):

        # Store setup
        self.setup = setup

        # Adjust logging level
        logging.getLogger().setLevel(setup['session']['loglevel'])

        # Update tab widgets accordingly
        self.update_tabs()

        # Init daq info widget
        self._init_daq_dock()

        # Init servers
        self._init_processes()

        # Show a progress dialog so user knows what is happening
        self._init_progress_dialog()

    def _init_progress_dialog(self):

        self.pdiag = QtWidgets.QProgressDialog()
        pdiag_label = QtWidgets.QLabel("Launching application:\n\n->Staring data converter...\n->Configuring {0} server(s)...\n->Starting {0} server(s)...".format(len(self.setup['server'])))
        pdiag_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.pdiag.setLabel(pdiag_label)
        self.pdiag.setRange(0, 0)
        self.pdiag.setMinimumDuration(0)
        self.pdiag.setCancelButton(None)
        self.pdiag.setModal(True)
        self.pdiag.show()

    def _init_info_dock(self):
        """Initializes corresponding log dock"""

        # Widget to display log in, we only want to read log
        self.log_widget = LoggingWidget()
        self.event_widget = EventWidget()

        info_tabs = QtWidgets.QTabWidget()
        info_tabs.addTab(self.log_widget, 'Log')
        info_tabs.addTab(self.event_widget, 'Event')
        
        # Dock in which text widget is placed to make it closable without losing log content
        self.info_dock = QtWidgets.QDockWidget()
        self.info_dock.setWidget(info_tabs)
        self.info_dock.setAllowedAreas(QtCore.Qt.BottomDockWidgetArea)
        self.info_dock.setFeatures(QtWidgets.QDockWidget.DockWidgetClosable)
        self.info_dock.setWindowTitle('Info')

        # Add to main layout
        self.sub_splitter.addWidget(self.info_dock)
        self.handle_info_ui()

    def _init_daq_dock(self):
        """Initializes corresponding daq info dock"""
        # Make raw data widget
        self.daq_info_widget = DaqInfoWidget(setup=self.setup['server'])

        # Dock in which text widget is placed to make it closable without losing log content
        self.daq_dock = QtWidgets.QDockWidget()
        self.daq_dock.setWidget(self.daq_info_widget)
        self.daq_dock.setAllowedAreas(QtCore.Qt.BottomDockWidgetArea)
        self.daq_dock.setFeatures(QtWidgets.QDockWidget.DockWidgetClosable)
        self.daq_dock.setWindowTitle('Data acquisition')

        # Add to main layout
        self.sub_splitter.addWidget(self.daq_dock)

    def _init_logging(self, loglevel=logging.INFO):
        """Initializes a custom logging handler and redirects stdout/stderr"""

        # Store loglevel of remote processes; subprocesses send log level and message separately
        self._remote_loglevel = 0
        self._loglevel_names = [lvl for lvl in log_levels if isinstance(lvl, str)]

        # Set logging level
        logging.getLogger().setLevel(loglevel)

        # Create logger instance
        self.logger = CustomHandler(self.main_widget)

        # Add custom logger
        logging.getLogger().addHandler(self.logger)

        # Connect logger signal to logger console
        LoggingStream.stdout().messageWritten.connect(lambda msg: self.log_widget.write_log(msg))
        LoggingStream.stderr().messageWritten.connect(lambda msg: self.log_widget.write_log(msg))
        
        logging.info('Started "irrad_control" on %s' % platform.system())

    def handle_log(self, log_dict):

        if 'level' in log_dict:
            self._remote_loglevel = log_dict['level']

        elif 'log' in log_dict:
            logging.log(level=self._remote_loglevel, msg=log_dict['log'])

    def _init_recv_threads(self):

        # Start receiving data, events and log messages from other processes
        for recv_func in (self.recv_data, self.recv_event, self.recv_log):
            self.threadpool.start(QtWorker(func=recv_func))

    def _init_processes(self):

        # Loop over all server(s), connect to the server(s) and launch worker for configuration
        server_config_workers = {}
        for server in self.setup['server']:
            # Connect
            self.proc_mngr.connect_to_server(hostname=server, username='pi')

            # Prepare server in QThread on init
            server_config_workers[server] = QtWorker(func=self.proc_mngr.configure_server,
                                                     hostname=server,
                                                     branch=get_current_git_branch(),
                                                     git_pull=True)

            # Connect workers finish signal to starting process on server
            server_config_workers[server].signals.finished.connect(lambda _server=server: self.start_server(_server))

            # Connect workers exception to log
            self._connect_worker_exception(worker=server_config_workers[server])

            # Launch worker on QThread
            self.threadpool.start(server_config_workers[server])

        self.start_interpreter()

        self._procs_launched = True

    def _started_daq_proc(self, hostname):
        """A DQAProcess has been sucessfully started on *hostname*"""
        
        self._started_daq_proc_hostnames.append(hostname)

        # Enable Control and Monitor tabs for this
        if hostname in self.setup['server']:
            self.control_tab.enable_control(server=hostname)
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

    def collect_proc_infos(self):
        """Run in a separate thread to collect infos of all launched processes"""

        while len(self.proc_mngr.active_pids) != len(self.proc_mngr.launched_procs):

            for proc in self.proc_mngr.launched_procs:

                proc_info = self.proc_mngr.get_irrad_proc_info(proc)

                if proc_info is not None and proc not in self.proc_mngr.active_pids:
                    self.proc_mngr.register_pid(hostname=proc, pid=proc_info['pid'], name=proc_info['name'], ports=proc_info['ports'])

                    # Update setup
                    if proc in self.setup['server']:
                        self.setup['server'][proc]['ports'] = proc_info['ports']
                    else:
                        self.setup['ports'] = proc_info['ports']

            # Wait a second before trying to read something again
            time.sleep(1)

    def send_start_cmd(self):

        for server in self.setup['server']:
            # Start server with 60s timeout: server can take some amount of time to start because of varying hardware startup times
            self.send_cmd(hostname=server, target='server', cmd='start', cmd_data={'setup': self.setup, 'server': server}, timeout=60)

        self.send_cmd(hostname='localhost', target='interpreter', cmd='start', cmd_data=self.setup)

    def _start_daq_proc(self, hostname, ignore_orphaned=False):

        # Check if there is an already-running irrad process instance; each DAQProcess creates/deletes a hidden pid-file on launch/shutdown
        orphaned_proc = self.proc_mngr.get_irrad_proc_info(hostname=hostname)

        # There is no indication for an orphaned process
        if orphaned_proc is None or ignore_orphaned:

            # We're launching a server
            if hostname in self.proc_mngr.client:
                # Launch server
                self.proc_mngr.start_server_process(hostname=hostname)

            # We're launching an interpreter
            else:
                # Launch interpreter
                self.proc_mngr.start_interpreter_process()

            self.proc_mngr.launched_procs.append(hostname)

            # Check if all servers and converter have been launched; if so start collecting process info and send start cmd
            servers_launched = all(server in self.proc_mngr.launched_procs for server in self.setup['server'])
            converter_launched = 'localhost' in self.proc_mngr.launched_procs

            # Servers AND converter need to be launched before collecting infos for event distribution 
            if servers_launched and converter_launched:
                proc_info_worker = QtWorker(func=self.collect_proc_infos)
                proc_info_worker.signals.finished.connect(self._init_recv_threads)
                proc_info_worker.signals.finished.connect(self.send_start_cmd)
                self.threadpool.start(proc_info_worker)

        # There is a pid-file
        else:
            # Check whether a process with the PID in the pid-file is still running
            ps_status = self.proc_mngr.check_process_status(hostname=hostname, pid=orphaned_proc['pid'])

            # The process is running
            if ps_status[hostname]:

                proc_kind = 'server' if hostname in self.proc_mngr.client else 'interpreter'
                pltfrm = 'localhost' if proc_kind == 'interpreter' else self.proc_mngr.server[hostname] + '@' + hostname

                msg = "A {0} process is already running on {1}. Only one {0} process at a time can be run on a host. " \
                      "Do you want to terminate the {0} process and relaunch a new one?" \
                      " Proceeding without terminating the currently running process may lead to faulty behavior".format(proc_kind, pltfrm)

                reply = QtWidgets.QMessageBox.question(self, 'Terminate running {} process and relaunch?'.format(proc_kind),
                                                       msg, QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)

                if reply == QtWidgets.QMessageBox.Yes:
                    self.proc_mngr.kill_proc(hostname=hostname, pid=orphaned_proc['pid'])
                    self._start_daq_proc(hostname=hostname)  # Try again

            else:
                self._start_daq_proc(hostname=hostname, ignore_orphaned=True)  # Try again

    def start_server(self, server):
        self._start_daq_proc(hostname=server)

    def start_interpreter(self):
        self._start_daq_proc(hostname='localhost')

    def _connect_worker_exception(self, worker):
        worker.signals.exception.connect(lambda e, trace: logging.error("{} on sub-thread: {}".format(type(e).__name__, trace)))
        
    def _tcp_addr(self, port, ip='*'):
        """Creates string of complete tcp address which sockets can bind to"""
        return 'tcp://{}:{}'.format(ip, port)

    def update_tabs(self):

        current_tab = self.tabs.currentIndex()

        # Create missing tabs
        self.control_tab = IrradControlTab(setup=self.setup['server'], parent=self.tabs)
        self.monitor_tab = IrradMonitorTab(setup=self.setup['server'], parent=self.tabs,
                                           plot_path=self.setup['session']['outfolder'])

        # Connect control tab
        self.control_tab.sendCmd.connect(lambda cmd_dict: self.send_cmd(**cmd_dict))
        self.control_tab.enableDAQRec.connect(lambda server, enable: self.daq_info_widget.record_btns[server].setVisible(enable))
        self.control_tab.enableDAQRec.connect(
            lambda server, enable: self.daq_info_widget.record_btns[server].clicked.connect(
                lambda _, _server=server: self.send_cmd(hostname='localhost',
                                                        target='interpreter',
                                                        cmd='record_data',
                                                        cmd_data=(_server, self.daq_info_widget.record_btns[server].text() == 'Resume')))
            if enable else self.daq_info_widget.record_btns[server].clicked.disconnect())  # Pretty crazy connection. Basically connects or disconnects a button

        # Make temporary dict for updated tabs
        tmp_tw = {'Control': self.control_tab, 'Monitor': self.monitor_tab}

        for tab in self.tab_order:
            if tab in tmp_tw:

                # Remove old tab, insert updated tab at same index and set status
                self.tabs.removeTab(self.tab_order.index(tab))
                self.tabs.insertTab(self.tab_order.index(tab), tmp_tw[tab], tab)

        # Set the tab index to stay at the same tab after replacing old tabs
        self.tabs.setCurrentIndex(current_tab)

    def handle_event(self, event_data):
        self.event_widget.register_event(event_dict=event_data)
    
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

            if 'frac_h' in data['data']['sey']:
                self.monitor_tab.plots[server]['sem_h_plot'].set_data(data['data']['sey']['frac_h'])
            if 'frac_v' in data['data']['sey']:
                self.monitor_tab.plots[server]['sem_v_plot'].set_data(data['data']['sey']['frac_v'])

        elif data['meta']['type'] == 'hist':
            if 'beam_position_idxs' in data['data']:
                self.monitor_tab.plots[server]['pos_plot'].update_hist(data['data']['beam_position_idxs'])
            if 'sey_horizontal_idx' in data['data']:
                self.monitor_tab.plots[server]['sem_h_plot'].update_hist(data['data']['sey_horizontal_idx'])
            if 'sey_vertical_idx' in data['data']:
                self.monitor_tab.plots[server]['sem_v_plot'].update_hist(data['data']['sey_vertical_idx'])

        elif data['meta']['type'] == 'damage':
            self.control_tab.tab_widgets[server]['status'].update_status(status='damage', status_values=data['data'])

        elif data['meta']['type'] == 'scan':

            if data['data']['status'] == 'scan_init':  # Scan is being initialized

                # Disable all record buttons when scan starts
                self.control_tab.tab_widgets[server]['daq'].btn_record.setEnabled(False)
                self.daq_info_widget.record_btns[server].setEnabled(False)

            elif data['data']['status'] in ('scan_start', 'scan_stop'):

                self.control_tab.tab_widgets[server]['status'].update_status(status='scan',
                                                                             status_values=data['data'],
                                                                             ignore_status=('speed',
                                                                                            'accel',
                                                                                            'x_start',
                                                                                            'x_stop',
                                                                                            'y_start',
                                                                                            'y_stop'))

            elif data['data']['status'] in ('scan_row_initiated', 'scan_row_completed'):

                # We are scanning individual rows
                if data['data']['scan'] == -1:
                    enable = data['data']['status'] == 'scan_row_completed'
                    self.control_tab.tab_widgets[server]['scan'].enable_after_scan_ui(enable)
                    self.control_tab.scan_status(server=server, status='started' if not enable else 'stopped')
                    self.control_tab.tab_widgets[server]['scan'].scan_in_progress = not enable

            elif data['data']['status'] == 'scan_finished':
                self.control_tab.scan_status(server=server, status=data['data']['status'])

                # Enable all record buttons when scan is over
                self.control_tab.tab_widgets[server]['daq'].btn_record.setEnabled(True)
                self.daq_info_widget.record_btns[server].setEnabled(True)
                self.control_tab.tab_widgets[server]['scan'].init_after_scan_ui()
                self.control_tab.tab_widgets[server]['scan'].scan_in_progress = False
                self.control_tab.tab_widgets[server]['scan'].enable_after_scan_ui(True)

                # Check whether data is interpreted
            elif data['data']['status'] == 'interpreted':
                self.monitor_tab.plots[server]['fluence_plot'].set_data(data)
                
                self.control_tab.tab_widgets[server]['status'].update_status(status='scan',
                                                                             status_values=data['data'],
                                                                             ignore_status=('fluence_hist',
                                                                                            'fluence_hist_err',
                                                                                            'status'))

                # Finish the scan programatically, if wanted
                self.control_tab.check_finish(server=server, eta_n_scans=data['data']['eta_n_scans'])

        elif data['meta']['type'] == 'temp_arduino':

            self.monitor_tab.plots[server]['temp_arduino_plot'].set_data(meta=data['meta'], data=data['data'])

        elif data['meta']['type'] == 'temp_daq_board':
            self.monitor_tab.plots[server]['temp_daq_board_plot'].set_data(meta=data['meta'], data=data['data'])

        elif data['meta']['type'] == 'dose_rate':
            self.monitor_tab.plots[server]['dose_rate_plot'].set_data(meta=data['meta'], data=data['data'])
            
        elif data['meta']['type'] == 'axis':
            self.control_tab.tab_widgets[server]['status'].update_status(status=data['data']['axis_domain'],
                                                                         status_values=data['data'],
                                                                         ignore_status=('axis_domain',))
            # Update motorstage positions after every move
            self.control_tab.tab_widgets[server]['motorstage'].update_motorstage_properties(motorstage=data['data']['axis_domain'],
                                                                                            properties={'position': data['data']['position']},
                                                                                            axis=data['data']['axis'])
            
    def send_cmd(self, hostname, target, cmd, cmd_data=None, timeout=5):
        """Send a command *cmd* to a target *target* running within the server or interpreter process.
        The command can have respective data *cmd_data*."""

        cmd_dict = {'target': target, 'cmd': cmd, 'data': cmd_data}
        cmd_worker = QtWorker(self._send_cmd_get_reply, hostname, cmd_dict, timeout)

        # Make connections
        self._connect_worker_exception(worker=cmd_worker)

        # Start
        self.threadpool.start(cmd_worker)

    def _send_cmd_get_reply(self, hostname, cmd_dict, timeout=None):
        """Sending a command to the server / interpreter and waiting for its reply. This runs on a separate QThread due
        to the blocking nature of the recv() method of sockets. *cmd_dict* contains the target, cmd and cmd_data."""

        # Spawn socket to send request to server / interpreter and connect
        req = self.context.socket(zmq.REQ)
        req_port = self.setup['server'][hostname]['ports']['cmd'] if hostname in self.setup['server'] else self.setup['ports']['cmd']

        if timeout:
            req.setsockopt(zmq.RCVTIMEO, int(timeout * 1000))
            req.setsockopt(zmq.LINGER, 0)  # Required if RCVTIMEO is used

        req.connect(self._tcp_addr(req_port, hostname))

        # Send command dict and wait for reply
        req.send_json(cmd_dict)

        try:
            reply = req.recv_json()

            # Update reply dict by the servers IP address
            reply['hostname'] = hostname

            # Emit the received reply in pyqt signal and close socket
            self.reply_received.emit(reply)

        except zmq.Again:
            msg = "Command '{}' with target '{}' timed out after {} seconds: no reply from server '{}'"
            logging.error(msg.format(cmd_dict['cmd'],
                                     cmd_dict['target'],
                                     timeout,
                                     'localhost' if hostname not in self.setup['server'] else self.setup['server'][hostname]['name']))
        finally:
            req.close()

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

                    # Get initial motorstage configuration
                    self.send_cmd(hostname=hostname, target=sender, cmd='motorstages')

                elif reply == 'shutdown':

                    logging.info("Server at {} confirmed shutdown".format(hostname))

                elif reply == 'motorstages':
                    for ms, ms_config in reply_data.items():
                        self.control_tab.tab_widgets[hostname]['motorstage'].add_motorstage(motorstage=ms,
                                                                                            positions=ms_config['positions'],
                                                                                            properties=ms_config['props'])

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
                    self.control_tab.update_rec_state(server=server, state=state)

                if reply == 'shutdown':

                    logging.info("Interpreter confirmed shutdown")

            elif sender == '__scan__':

                if reply == 'setup_scan':
                    self.monitor_tab.add_fluence_hist(server=hostname,
                                                      kappa=self.setup['server'][hostname]['daq']['kappa']['nominal'],
                                                      n_rows=reply_data['result']['n_rows'])
                    
                    self.control_tab.scan_status(server=hostname, status='started')
                    self.control_tab.tab_widgets[hostname]['scan'].enable_after_scan_ui(False)
                    self.control_tab.tab_widgets[hostname]['scan'].n_rows = reply_data['result']['n_rows']
                    self.control_tab.tab_widgets[hostname]['scan'].launch_scan()
                    self.control_tab.tab_widgets[hostname]['scan'].scan_in_progress = True

                    self.control_tab.tab_widgets[hostname]['status'].update_status(status='scan',
                                                                                   status_values=reply_data['result'],
                                                                                   only_status=('n_rows',))

            # Get motorstage responses
            elif sender in ('ScanStage', 'SetupTableStage', 'ExternalCupStage'):

                if reply in ('set_speed', 'set_range', 'set_accel', 'stop'):
                    # Callback is get_physical_props
                    self.control_tab.tab_widgets[hostname]['motorstage'].update_motorstage_properties(motorstage=sender,
                                                                                                      properties=reply_data['callback']['result'])
                elif reply in ['get_speed', 'get_range', 'get_accel', 'get_position']:
                    prop = reply.split('_')[-1]
                    prop = {prop: reply_data['result']} if not isinstance(reply_data['result'], list) else [{prop: r} for r in reply_data['result']]
                    self.control_tab.tab_widgets[hostname]['motorstage'].update_motorstage_properties(motorstage=sender,
                                                                                                      properties=prop)
                elif reply == 'get_physical_props':
                    self.control_tab.tab_widgets[hostname]['motorstage'].update_motorstage_properties(motorstage=sender,
                                                                                                      properties=reply_data['result'])

                elif reply in ('add_position', 'remove_position'):
                    self.control_tab.tab_widgets[hostname]['motorstage'].motorstage_positions_window.validate(motorstage=sender,
                                                                                                              positions=reply_data['callback']['result'],
                                                                                                              validate=reply.split('_')[0])

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

    def _recv_from_stream(self, stream, recv_func, emit_signal, callback=None, recv_msg=''):

        # Subscriber
        sub = self.context.socket(zmq.SUB)

        # Wait 1 sec for messages to be received
        sub.setsockopt(zmq.RCVTIMEO, int(1000))
        sub.setsockopt(zmq.LINGER, 0)

        # Loop over servers and connect to their data streams
        for server in self.setup['server']:
            sub.connect(self._tcp_addr(self.setup['server'][server]['ports'][stream], ip=server))

        # Connect to interpreter data stream
        sub.connect(self._tcp_addr(self.setup['ports'][stream], ip='localhost'))

        sub.setsockopt(zmq.SUBSCRIBE, b'')  # specify bytes for Py3

        logging.info(recv_msg or f"Start receiving from {stream} stream")
        
        while not self.stop_recv.is_set():
            try:
                res = getattr(sub, recv_func)()
                # Only emit if we got something
                if res:
                    emit_signal.emit(res if callback is None else callback(res))
            except zmq.Again:
                pass

    def recv_event(self):
        self._recv_from_stream(stream='event', recv_func='recv_json', emit_signal=self.event_received)

    def recv_data(self):
        self._recv_from_stream(stream='data', recv_func='recv_json', emit_signal=self.data_received)

    def recv_log(self):

        def callback(log):
            # Py3 compatibility; in Py 3 string is unicode, receiving log via socket will result in bytestring which needs to be decoded first;
            # Py2 has bytes as default; interestinglyy, u'test' == 'test' is True in Py2 (whereas 'test' == b'test' is False in Py3),
            # therefore this will work in Py2 and Py3
            log = log.decode()
            log_dict = {}

            if log.upper() in self._loglevel_names:
                log_dict['level'] = getattr(logging, log.upper(), None)
            else:
                log_dict['log'] = log.strip()
            return log_dict

        self._recv_from_stream(stream='log', recv_func='recv', emit_signal=self.log_received, callback=callback)

    def handle_messages(self, message, ms=4000):
        """Handles messages from the tabs shown in QMainWindows statusBar"""

        self.statusBar().showMessage(message, ms)

    def handle_info_ui(self):
        """Handle whether log widget is visible or not"""
        self.info_dock.setVisible(not self.info_dock.isVisible())
    
    def handle_daq_ui(self):
        """Handle whether log widget is visible or not"""
        self.daq_dock.setVisible(not self.daq_dock.isVisible())

    def file_quit(self):
        self.close()

    def _clean_up(self):

        # Stop receiver threads
        self.stop_recv.set()

        # Store all plots on close; AttributeError when app was not launched fully
        try:
            self.monitor_tab.save_plots()
        except AttributeError:
            pass

        # Wait 5 second for all threads to finish
        self.threadpool.waitForDone(5000)

    def _validate_close(self):

        # If all servers and the converters have responded to the shutdown, we proceed
        if len(self._stopped_daq_proc_hostnames) == len(self.proc_mngr.active_pids):
            
            # Check if all processes have indeed terminated; give it a couple of tries due to the shutdown of a server can take a second or two 
            for _ in range(10):
                time.sleep(0.5)
                self.proc_mngr.check_active_processes()
                
                if not any(self.proc_mngr.active_pids[h][pid]['active'] for h in self.proc_mngr.active_pids for pid in self.proc_mngr.active_pids[h]):
                    self._shutdown_complete = True
                    break
            
            # Unfortunately, we could not verify the close, inform user and close
            else:

                msg = "Shutdown of the converter and server processes could not be validated.\n" \
                      "Click 'Retry' to restart the shutdown and validation process.\n" \
                      "Click 'Abort' to kill all remaining processes and close the application.\n" \
                      "Click 'Ignore' to do nothing and close the application."

                msg_box = QtWidgets.QMessageBox(self)
                msg_box.setWindowTitle('Shutdown could not be validated')
                msg_box.setText(msg)
                msg_box.setStandardButtons(QtWidgets.QMessageBox.Ignore | QtWidgets.QMessageBox.Retry | QtWidgets.QMessageBox.Abort)
                reply = msg_box.exec()

                if reply == QtWidgets.QMessageBox.Ignore:
                    self._shutdown_complete = True
                elif reply == QtWidgets.QMessageBox.Abort:
                    for host in self.proc_mngr.active_pids:
                        for pid in self.proc_mngr.active_pids[host]:
                            if self.proc_mngr.active_pids[host][pid]['active']:
                                self.proc_mngr.kill_proc(hostname=host, pid=pid)
                    self._shutdown_complete = True
                else:
                    self._shutdown_initiated = False
                    self._stopped_daq_proc_hostnames.clear()

            self.close()

    def _validate_no_scan(self):

        scan_in_progress_servers = [s for s in self.setup['server'] if self.control_tab.tab_widgets[s]['scan'].scan_in_progress]

        if scan_in_progress_servers:
            server_names = ','.join(self.setup['server'][s]['name'] for s in scan_in_progress_servers)
            msg = "The following server(s) is currently conducting a scan: {}!\n" \
                  "Are you sure you want to close? This will terminate the scan and shut down the application.\n" \
                  "Click 'Abort' to terminate the scan and close the application.\n" \
                  "Click 'Cancel' to continue the scan and the application.".format(server_names)

            msg_box = QtWidgets.QMessageBox(self)
            msg_box.setWindowTitle('Scan in progress!')
            msg_box.setText(msg)
            msg_box.setStandardButtons(QtWidgets.QMessageBox.Cancel | QtWidgets.QMessageBox.Abort)
            reply = msg_box.exec()

            if reply == QtWidgets.QMessageBox.Cancel:
                return False
            else:
                for s in scan_in_progress_servers:
                    self.send_cmd(hostname=s,
                                  target='__scan__',
                                  cmd='handle_interaction',
                                  cmd_data={'kwargs': {'interaction': 'abort'}})

        return True

    def closeEvent(self, event):
        """Catches closing event and invokes customized closing routine"""

        shutdown = False

        # No process have been launched yet
        if not self._procs_launched:
            shutdown = True

        # We are initiating the shutdown routine
        elif not self._shutdown_initiated:

            # Check if a scan is currently in progress
            if self._validate_no_scan():

                logging.info('Initiating shutdown of servers and converter...')

                # Check
                self.proc_mngr.check_active_processes()

                # Loop over all started processes and send shutdown cmd
                for host in self.proc_mngr.active_pids:
                    
                    target = 'interpreter' if host == 'localhost' else 'server'
                    
                    shutdown_worker = QtWorker(func=self._send_cmd_get_reply,
                                            hostname=host,
                                            cmd_dict={'target': target, 'cmd': 'shutdown'},
                                            timeout=5)
                    # Make connections
                    self._connect_worker_exception(worker=shutdown_worker)
                    shutdown_worker.signals.finished.connect(lambda h=host: self._stopped_daq_proc_hostnames.append(h))
                    shutdown_worker.signals.finished.connect(self._validate_close)

                    # Start
                    self.threadpool.start(shutdown_worker)

                self._shutdown_initiated = True

        elif self._shutdown_complete:
            logging.info("Shutdown complete.")
            shutdown = True

        if shutdown:
            self._clean_up()
            event.accept()
        else:
            event.ignore()


def run():
    app = QtWidgets.QApplication(sys.argv)
    font = QtGui.QFont()
    font.setPointSize(11)
    app.setFont(font)
    gui = IrradGUI()
    gui.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    run()
