import sys
import time
import logging
import platform
import zmq
import yaml
from collections import OrderedDict, defaultdict
from email import message_from_string
from pkg_resources import get_distribution, DistributionNotFound
from PyQt5 import QtCore, QtWidgets, QtGui
from threading import Event

# Package imports
from irrad_control.utils import CustomHandler, LoggingStream, log_levels, Worker, ProcessManager
from irrad_control.gui.widgets import DaqInfoWidget, LoggingWidget
from irrad_control.gui.tabs import IrradSetupTab, IrradControlTab, IrradMonitorTab


PROJECT_NAME = 'Irrad Control'
GUI_AUTHORS = 'Pascal Wolf'
MINIMUM_RESOLUTION = (1366, 768)

try:
    pkgInfo = get_distribution('irrad_control').get_metadata('PKG-INFO')
    AUTHORS = message_from_string(pkgInfo)['Author']
except (DistributionNotFound, KeyError):
    AUTHORS = 'Not defined'

# needed to dump OrderedDict into file, representer for ordereddict (https://stackoverflow.com/a/8661021)
represent_dict_order = lambda self, data: self.represent_mapping('tag:yaml.org,2002:map', data.items())
yaml.add_representer(OrderedDict, represent_dict_order)


class IrradControlWin(QtWidgets.QMainWindow):
    """Inits the main window of the irrad_control software."""

    # PyQt signals
    data_received = QtCore.pyqtSignal(dict)  # Signal for data
    reply_received = QtCore.pyqtSignal(dict)  # Signal for reply
    log_received = QtCore.pyqtSignal(dict)  # Signal for log

    def __init__(self, parent=None):
        super(IrradControlWin, self).__init__(parent)

        # Setup dict of the irradiation; is set when setup tab is completed
        self.setup = None
        
        # Needed in order to stop helper threads
        self.stop_recv_data = Event()
        self.stop_recv_log = Event()
        
        # ZMQ context; THIS IS THREADSAFE! SOCKETS ARE NOT!
        # EACH SOCKET NEEDS TO BE CREATED WITHIN ITS RESPECTIVE THREAD/PROCESS!
        self.context = zmq.Context()
        
        # QThreadPool manages GUI threads on its own; every runnable started via start(runnable) is auto-deleted after.
        self.threadpool = QtCore.QThreadPool()

        # Server process and hardware that can receive commands using self.send_cmd method
        self._targets = ('server', 'adc', 'stage', 'temp', 'interpreter')

        # Class to manage the server, interpreter and additional subprocesses
        self.proc_mngr = ProcessManager()

        # Keep track of send commands in order to wait for their response
        self._cmd_id = 0
        self._cmd_reply = defaultdict(list)
        self._try_close = False
        self._log_close = False
        
        # Connect signals
        self.data_received.connect(lambda data: self.handle_data(data))
        self.reply_received.connect(lambda reply: self.handle_reply(reply))
        self.log_received.connect(lambda log: self.handle_log(log))

        # Tab widgets
        self.setup_tab = None
        self.control_tab = None
        self.monitor_tab = None

        # Init user interface
        self._init_ui()
        self._init_logging()

        # Timer starting when application should be closed
        self.close_timer = QtCore.QTimer()
        self.close_timer.timeout.connect(self.close)
        self.close_timer.setInterval(500)
        
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
        self._init_log_dock()
        
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
        self.appearance_menu.addAction('&Show/hide log', self.handle_log_ui, QtCore.Qt.CTRL + QtCore.Qt.Key_L)
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
                self.setup_tab.irrad_setup.setup_widgets['session'].widgets['logging_combo'].currentTextChanged.connect(lambda lvl: self.log_widget.change_level(lvl))
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

        # Start receiving data and log
        self._init_threads()

        # Init subprocesses
        self._init_subprocesses()

    def _init_log_dock(self):
        """Initializes corresponding log dock"""

        # Widget to display log in, we only want to read log
        self.log_widget = LoggingWidget()
        
        # Dock in which text widget is placed to make it closable without losing log content
        self.log_dock = QtWidgets.QDockWidget()
        self.log_dock.setWidget(self.log_widget)
        self.log_dock.setAllowedAreas(QtCore.Qt.BottomDockWidgetArea)
        self.log_dock.setFeatures(QtWidgets.QDockWidget.DockWidgetClosable)
        self.log_dock.setWindowTitle('Log')

        # Add to main layout
        self.sub_splitter.addWidget(self.log_dock)
        self.handle_log_ui()

    def _init_daq_dock(self):
        """Initializes corresponding daq info dock"""
        # Make raw data widget
        self.daq_info_widget = DaqInfoWidget(setup=self.setup['server'])

        # Dock in which text widget is placed to make it closable without losing log content
        self.daq_info_dock = QtWidgets.QDockWidget()
        self.daq_info_dock.setWidget(self.daq_info_widget)
        self.daq_info_dock.setAllowedAreas(QtCore.Qt.BottomDockWidgetArea)
        self.daq_info_dock.setFeatures(QtWidgets.QDockWidget.NoDockWidgetFeatures)
        self.daq_info_dock.setWindowTitle('DAQ Info')

        # Add to main layout
        self.sub_splitter.addWidget(self.daq_info_dock)

    def _init_logging(self, loglevel=logging.INFO):
        """Initializes a custom logging handler and redirects stdout/stderr"""

        # Store loglevel of remote processes; subprocesses send log level and message separately
        self._remote_loglevel = 0
        self._loglevel_names = [lvl for lvl in log_levels.keys() if isinstance(lvl, str)]

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

    def _init_subprocesses(self):

        # Loop over all server(s), connect to the server(s) and launch worker for configuration
        server_config_workers = {}
        for server in self.setup['server']:
            # Connect
            self.proc_mngr.connect_to_server(hostname=server, username='pi')

            # Prepare server in QThread on init
            server_config_workers[server] = Worker(func=self.proc_mngr.configure_server, hostname=server, branch='master', git_pull=True)

            # Connect workers finish signal to starting process on server
            for con in [lambda _server=server: self.proc_mngr.start_server_process(_server, self.setup['port']['cmd']),
                        lambda _server=server: self.send_cmd(hostname=_server, target='server', cmd='start', cmd_data={'setup': self.setup, 'server': _server})
                        ]:
                server_config_workers[server].signals.finished.connect(con)

            # Connect workers exception to log
            self._connect_worker_exception(worker=server_config_workers[server])
            self._connect_worker_close(server_config_workers[server], server)

            # Launch worker on QThread
            self.threadpool.start(server_config_workers[server])

        # Launch interpreter process
        self.proc_mngr.start_interpreter_process(setup_yaml=self.setup['session']['outfile']+'.yaml')
        self.send_cmd(hostname='localhost', target='interpreter', cmd='pid')
            
    def _init_threads(self):       
                
        # Fancy QThreadPool and QRunnable approach
        recv_workers = {'recv_data': Worker(func=self.recv_data),
                        'recv_log': Worker(func=self.recv_log)}
        
        for _worker in recv_workers:
            self._connect_worker_exception(worker=recv_workers[_worker])
            self.threadpool.start(recv_workers[_worker])

    def _connect_worker_exception(self, worker):
        worker.signals.exceptionSignal.connect(lambda e, trace: logging.error("{} on sub-thread: {}".format(type(e).__name__, trace)))

    def _connect_worker_close(self, worker, hostname):
        self._cmd_reply[hostname].append(self._cmd_id)
        for con in [lambda _hostname=hostname, cmd_id=self._cmd_id: self._cmd_reply[_hostname].remove(cmd_id), self._check_close]:
            worker.signals.finished.connect(con)
        self._cmd_id += 1
        
    def _tcp_addr(self, port, ip='*'):
        """Creates string of complete tcp address which sockets can bind to"""
        return 'tcp://{}:{}'.format(ip, port)

    def update_tabs(self):

        current_tab = self.tabs.currentIndex()

        # Create missing tabs
        self.control_tab = IrradControlTab(setup=self.setup['server'], parent=self.tabs)
        self.monitor_tab = IrradMonitorTab(setup=self.setup['server'], parent=self.tabs)

        # Connect control tab
        self.control_tab.sendCmd.connect(lambda cmd_dict: self.send_cmd(**cmd_dict))

        # Make temporary dict for updated tabs
        tmp_tw = {'Control': self.control_tab, 'Monitor': self.monitor_tab}

        for tab in self.tab_order:
            if tab in tmp_tw.keys():

                # Remove old tab, insert updated tab at same index and set status
                self.tabs.removeTab(self.tab_order.index(tab))
                self.tabs.insertTab(self.tab_order.index(tab), tmp_tw[tab], tab)

        # Set the tab index to stay at the same tab after replacing old tabs
        self.tabs.setCurrentIndex(current_tab)
    
    def handle_data(self, data):

        server = data['meta']['name']

        # Check whether data is interpreted
        if data['meta']['type'] == 'raw':

            self.daq_info_widget.update_raw_data(data)
            self.monitor_tab.plots[server]['raw_plot'].set_data(data)

        # Check whether data is interpreted
        elif data['meta']['type'] == 'beam':
            self.daq_info_widget.update_beam_current(data)
            self.monitor_tab.plots[server]['pos_plot'].set_data(data)
            _data = {'meta': data['meta'], 'data': data['data']['current']}
            self.monitor_tab.plots[server]['current_plot'].set_data(_data)
            self.control_tab.beam_current = data['data']['current']['analog']
            self.control_tab.check_no_beam()

        # Check whether data is interpreted
        elif data['meta']['type'] == 'fluence':
            self.monitor_tab.plots[server]['fluence_plot'].set_data(data)

            hist, hist_err = (data['data'][x] for x in ('hist', 'hist_err'))

            lower_mean_f = sum([hist[i] - hist_err[i] for i in range(len(hist))]) / float(len(hist))

            if lower_mean_f >= self.control_tab.aim_fluence:
                self.send_cmd(server, 'stage', 'finish')

            self.control_tab.update_info(row=hist[self.control_tab.scan_params['row']], unit='p/cm^2')

            if self.control_tab.scan_params['row'] in (0, self.control_tab.scan_params['n_rows'] - 1):
                mean_fluence = sum(hist) / len(hist)
                self.control_tab.update_info(scan=mean_fluence, unit='p/cm^2')
                est_n_scans = (self.control_tab.aim_fluence - mean_fluence) / (self.control_tab.beam_current / (1.60217733e-19 * self.control_tab.scan_params['scan_speed'] * self.control_tab.scan_params['step_size'] * 1e-2))
                self.control_tab.update_info(nscan=int(est_n_scans))

        elif data['meta']['type'] == 'stage':

            if data['data']['status'] == 'start':
                self.control_tab.update_info(position=[data['data']['x_start'], data['data']['y_start']], unit='mm')
                self.control_tab.update_scan_parameters(scan=data['data']['scan'], row=data['data']['row'])
                self.control_tab.update_scan_parameters(scan_speed=data['data']['speed'], unit='mm/s')
                self.control_tab.update_info(status='Scanning...')

            elif data['data']['status'] == 'stop':
                self.control_tab.update_info(position=[data['data']['x_stop'], data['data']['y_stop']], unit='mm')
                self.control_tab.update_info(status='Turning')

            elif data['data']['status'] == 'finished':

                self.control_tab.scan_status(data['data']['status'])

        elif data['meta']['type'] == 'temp':

            self.monitor_tab.plots[server]['temp_plot'].set_data(data)
            
    def send_cmd(self, hostname, target, cmd, cmd_data=None, check_reply=True):
        """Send a command *cmd* to a target *target* running within the server or interpreter process.
        The command can have respective data *cmd_data*. Targets must be listed in self._targets."""

        if target not in self._targets:
            msg = '{} not in known by command targets. Known targets: {}'.format(target, ', '.join(self._targets))
            logging.error(msg)
            return

        cmd_dict = {'target': target, 'cmd': cmd, 'data': cmd_data}
        cmd_worker = Worker(self._send_cmd_get_reply, hostname, cmd_dict)

        # Make connections
        self._connect_worker_exception(worker=cmd_worker)

        # Keep track of commands
        if check_reply:
            self._connect_worker_close(cmd_worker, hostname)

        # Start
        self.threadpool.start(cmd_worker)

    def _send_cmd_get_reply(self, hostname, cmd_dict):
        """Sending a command to the server / interpreter and waiting for its reply. This runs on a separate QThread due
        to the blocking nature of the recv() method of sockets. *cmd_dict* contains the target, cmd and cmd_data."""

        # Spawn socket to send request to server / interpreter and connect
        req = self.context.socket(zmq.REQ)
        req.connect(self._tcp_addr(self.setup['port']['cmd'], hostname))

        # Send command dict and wait for reply
        req.send_json(cmd_dict)
        reply = req.recv_json()

        # Update reply dict by the servers IP address
        reply['hostname'] = hostname

        # Emit the received reply in pyqt signal and close socket
        self.reply_received.emit(reply)
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

                    self.proc_mngr.register_pid(hostname=hostname, pid=reply_data, name=sender + ':' + hostname)
                    self.tabs.setCurrentIndex(self.tabs.indexOf(self.monitor_tab))

                    # Send command to find where stage is and what the speeds are
                    if 'stage' in self.setup['server'][hostname]['devices']:
                        self.send_cmd(hostname, 'stage', 'pos')
                        self.send_cmd(hostname, 'stage', 'get_speed')
                        self.send_cmd(hostname, 'stage', 'get_range')

                elif reply == 'shutdown':

                    logging.info("Server at {} confirmed shutdown".format(hostname))

                    # FIXME: server does not always send a reply https://github.com/zeromq/libzmq/issues/1264
                    # Try to close
                    self.close()

            elif sender == 'interpreter':

                if reply == 'pid':
                    self.proc_mngr.register_pid(hostname=hostname, pid=reply_data, name=sender.capitalize())

                if reply == 'shutdown':

                    logging.info("Interpreter confirmed shutdown")

                    # Try to close
                    self.close()

            elif sender == 'stage':

                if reply in ['pos', 'move_rel', 'move_abs']:
                    self.control_tab.update_info(position=reply_data, unit='mm')

                elif reply in ['set_speed', 'get_speed']:
                    self.control_tab.update_info(speed=reply_data, unit='mm/s')

                elif reply in ['set_range', 'get_range']:
                    self.control_tab.update_info(range=reply_data, unit='mm')

                elif reply == 'prepare':
                    self.control_tab.update_scan_parameters(**reply_data)
                    self.monitor_tab.add_fluence_hist(**{'kappa': self.setup['server'][hostname]['devices']['daq']['kappa'],
                                                         'n_rows': reply_data['n_rows']})
                    self.send_cmd(hostname=hostname, target='stage', cmd='scan')
                    self.control_tab.scan_status('started')

                    est_n_scans = self.control_tab.aim_fluence / (self.control_tab.beam_current / (1.60217733e-19 * self.control_tab.scan_params['scan_speed'] * self.control_tab.scan_params['step_size'] * 1e-2))
                    self.control_tab.update_info(nscan=int(est_n_scans))

                elif reply == 'finish':

                    logging.info("Finishing scan!")

                elif reply == 'no_beam':

                    if reply_data:
                        logging.debug("No beam event set")
                    else:
                        logging.debug("No beam event cleared")

            # Debug
            msg = 'Standard {} reply received: {}'.format(sender.capitalize(), reply)
            logging.debug(msg)

        elif _type == 'ERROR':
            msg = '{} error occurred: {}'.format(sender.capitalize(), reply)
            logging.error(msg)
            self.log_dock.setVisible(True)

        else:
            logging.info('Received reply {} from {}'.format(reply, sender))

    def recv_data(self):
        
        # Data subscriber
        data_sub = self.context.socket(zmq.SUB)

        # Loop over servers and connect to their data streams
        for server in self.setup['server']:

            if 'adc' in self.setup['server'][server]['devices']:
                data_sub.connect(self._tcp_addr(self.setup['port']['data'], ip=server))

            if 'temp' in self.setup['server'][server]['devices']:
                data_sub.connect(self._tcp_addr(self.setup['port']['temp'], ip=server))

            if 'stage' in self.setup['server'][server]['devices']:
                data_sub.connect(self._tcp_addr(self.setup['port']['stage'], ip=server))

        # Connect to interpreter data stream
        data_sub.connect(self._tcp_addr(self.setup['port']['data'], ip='localhost'))

        data_sub.setsockopt(zmq.SUBSCRIBE, '')
        
        data_timestamps = {}
        
        logging.info('Data receiver ready')
        
        while not self.stop_recv_data.is_set():
            
            data = data_sub.recv_json()
            dtype = data['meta']['type']
            server = data['meta']['name']

            if server not in data_timestamps:
                data_timestamps[server] = {}

            if dtype not in data_timestamps[server]:
                data_timestamps[server][dtype] = time.time()
            else:
                now = time.time()
                drate = 1. / (now - data_timestamps[server][dtype])
                data_timestamps[server][dtype] = now
                data['meta']['data_rate'] = drate

            self.data_received.emit(data)
            
    def recv_log(self):
        
        # Log subscriber
        log_sub = self.context.socket(zmq.SUB)

        # Connect to log messages from remote server and local interpreter process
        for ip in list(self.setup['server'].keys()) + ['localhost']:
            log_sub.connect(self._tcp_addr(self.setup['port']['log'], ip=ip))

        log_sub.setsockopt(zmq.SUBSCRIBE, '')
        
        logging.info('Log receiver ready')
        
        while not self.stop_recv_log.is_set():
            log = log_sub.recv()
            if log:
                log_dict = {}

                if log.upper() in self._loglevel_names:
                    log_dict['level'] = getattr(logging, log.upper(), None)
                else:
                    log_dict['log'] = log.strip()

                self.log_received.emit(log_dict)

    def handle_messages(self, message, ms=4000):
        """Handles messages from the tabs shown in QMainWindows statusBar"""

        self.statusBar().showMessage(message, ms)

    def handle_log_ui(self):
        """Handle whether log widget is visible or not"""

        if self.log_dock.isVisible():
            self.log_dock.setVisible(False)
        else:
            self.log_dock.setVisible(True)

    def file_quit(self):
        self.close()
        self.close_timer.start()  # Repeatedly check if we can close

    def _check_close(self):
        """Check whether we're waiting for cmd replies in order to close"""
        if self._try_close:
            self.close()

    def _clean_up(self):

        # Stop receiver threads
        self.stop_recv_data.set()
        self.stop_recv_log.set()
        self.close_timer.stop()

        # Wait 1 second for all threads to finish
        self.threadpool.waitForDone(1000)

    def closeEvent(self, event):
        """Catches closing event and invokes customized closing routine"""

        # Indicate that we want to close
        self._try_close = True

        if any(val for val in self._cmd_reply.values()):

            if not self._log_close:
                for host in self._cmd_reply:
                    if self._cmd_reply[host]:
                        msg = "Waiting for reply from {} with command ID(s): {}".format(host, ', '.join([str(i) for i in self._cmd_reply[host]]))
                        logging.warning(msg)

                logging.warning("{} will be closed after all remaining replies have been received".format(PROJECT_NAME))
                self._log_close = True

            # Ignore closing
            event.ignore()

        # There are subprocesses to shut down
        elif any(self.proc_mngr.active_pids[h]['active'] for h in self.proc_mngr.active_pids):

            # If we're here, there's no more processecs; we will launch closing workers, they should not give warning to user
            self._log_close = True

            # Check
            self.proc_mngr.check_process_status()

            # Loop over all started processes and send shutdown cmd
            for host in self.proc_mngr.active_pids:

                # Shutdown all the servers
                if host in self.setup['server']:
                    logging.info("Shutting down server at {}".format(host))
                    # FIXME: server does not always send a reply https://github.com/zeromq/libzmq/issues/1264
                    self.send_cmd(host, 'server', 'shutdown', check_reply=False)

                # Shutdown interpreter
                if host == 'localhost':
                    logging.info("Shutting down interpreter...")
                    self.send_cmd(host, 'interpreter', 'shutdown', check_reply=False)

            # Ignore closing
            event.ignore()

        else:

            self._clean_up()

            # Close
            event.accept()


def main():
    app = QtWidgets.QApplication(sys.argv)
    font = QtGui.QFont()
    font.setPointSize(11)
    app.setFont(font)
    icw = IrradControlWin()
    icw.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
