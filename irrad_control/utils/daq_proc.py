import os
import yaml
import zmq
import logging
import signal
from time import sleep
from multiprocessing import Process
from threading import Event
from zmq.log import handlers
from irrad_control import config_path
from irrad_control.utils.worker import ThreadWorker
from collections import defaultdict


class DAQProcess(Process):
    """Base-class of data acquisition processes"""

    def __init__(self, name, commands, daq_streams=None, hwm=None, internal_sub=None, *args, **kwargs):
        """
        Init the process

        Parameters
        ----------

        name: str
            Name of the process
        commands: dict
            Dictionary containing command strings and targets
        daq_streams: str, list, tuple
            String or iterable of strings of zmq addresses of data streams to connect to
        hwm: int
             High-water mark of zmq sockets
        internal_sub: str, None
            String of zmq address to which the internal subscribe listens to, which puts data on the data publisher port.
            If None, use internal address which is used by internally created sockets (see *create_internal_data_pub*)
        args: list
            Positional arguments which are passed to Process.__init__()
        kwargs: dict
            Keyword arguments which are passed to Process.__init__()
        """
        # Call super's init
        super(DAQProcess, self).__init__(*args, **kwargs)

        # Initialize a name which is connected to this process
        self.pname = name
        self.pfile = os.path.join(config_path, '.irrad.pid')  # Create hidden PID file

        # Events to handle sending / receiving of data and commands
        self.stop_flags = dict([(x, Event()) for x in ('send', 'recv', 'watch')])
        self.state_flags = dict([(x, Event()) for x in ('busy', 'converter')])
        self.on_demand_events = defaultdict(Event)  # Create events in subclasses on demand

        # Ports/sockets used by this process
        self.ports = {'log': None, 'cmd': None, 'data': None}
        self.sockets = {'log': None, 'cmd': None, 'data': None}
        self.socket_type = {'log': zmq.PUB, 'cmd': zmq.REP, 'data': zmq.PUB}

        # Attribute holding zmq context
        self.context = None

        # Sets internal subscriber address from which data is gathered (from potentially many sources) and published (on one port);
        # usually this is some intra-process communication protocol such as inproc/ipc. If not, this process listens to a different
        # DAQ processes DAQ threads in an attempt to distribute the load on multiple CPU cores more evenly
        self._internal_sub_addr = internal_sub if internal_sub is not None and self._check_addr(internal_sub) else 'inproc://internal'

        # High-water mark for all ZMQ sockets
        self.hwm = 100 if hwm is None or not isinstance(hwm, int) else hwm

        # Dict of known commands
        self.commands = commands

        # Attribute to store irrad session setup in
        self.setup = None

        # List to hold all threads of the process
        self.threads = []

        # List of input data stream addresses
        self.daq_streams = [] if daq_streams is None else daq_streams if isinstance(daq_streams, (list, tuple)) else [daq_streams]

        # Quick check
        self.daq_streams = [dstream for dstream in self.daq_streams if self._check_addr(addr=dstream)]

        # If the process is a converter, the 'data' socket will send out data as well as receive data
        self.is_converter = len(self.daq_streams) > 0

    @property
    def is_converter(self):
        """Return whether this instance is also a converter"""
        return self.state_flags['converter'].is_set()

    @is_converter.setter
    def is_converter(self, state):
        """
        Set whether this instance is a converter

        Parameters
        ----------

        state: bool
            Whether this instance should be a converter
        """
        # Set the flag
        self.state_flags['converter'].set() if bool(state) else self.state_flags['converter'].clear()

    def _check_addr(self, addr):
        """
        Check address format for zmq sockets

        Parameters
        ----------

        addr: str
            String of zmq address

        Returns
        -------
        bool:
            Whether the address is valid
        """

        if not isinstance(addr, str):
            logging.error("Address must be string")
            return False

        addr_components = addr.split(':')

        # Not TCP or UDP
        if len(addr_components) == 2:
            protocol, endpoint = addr_components
            if endpoint[:2] != '//':
                logging.error("Incorrect address format. Must be 'protocol://endpoint'")
                return False
            elif protocol in ('tcp', 'udp'):
                logging.error("Incorrect address format. Must be 'protocol://address:port' for 'tcp/udp' protocols")
                return False
        # TCP / UDP
        elif len(addr_components) == 3:
            protocol, ip, port = addr_components
            if ip[:2] != '//':
                logging.error("Incorrect address format. Must be 'protocol://address:port' for 'tcp/udp' protocols")
                return False
            try:
                port = int(port)
                if not 0 < port < 2 ** 16 - 1:
                    raise ValueError
            except ValueError:
                logging.error("'port' must be an integer between 1 and {} (16 bit)".format(2 ** 16 - 1))
                return False
        else:
            logging.error("Incorrect address format. Must be 'protocol://endpoint")
            return False

        return True if protocol else False

    def _enable_graceful_shutdown(self):
        """ Method that redirects systems interrupt and terminatioin signals to the instances *shutdown* method """

        # Enable graceful termination
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGQUIT):
            signal.signal(sig, self.shutdown)

    def _setup_zmq(self):
        """ Setup the zmq context instance and allocate needed sockets """

        # Create a context instance
        self.context = zmq.Context()

        # Create sockets
        self._allocate_sockets()

    def _allocate_sockets(self, min_port=8000, max_port=9000, max_tries=100, rep_linger=500):
        """
        Method to acquire all needed sockets. Ports are selected by zmq's *bind_to_random_port* method which
        eliminates the need for hard-coded ports. The port configuration is stored in a PID.yaml within the
        config-folder of the package

        Parameters
        ----------
        min_port: int
            minimum port number; usually ports 0-1023 are reserved for system
        max_port: int
            maximum port number
        max_tries:
            maximum number of tries to bind to a port within range *min_port* to *max_port*
        rep_linger: int
            number of milliseconds to wait before closing socket; useful for sending last reply on zmq.REP
        """

        # Loop over needed sockets and create and bind
        for sock in self.sockets:

            # Create socket
            self.sockets[sock] = self.context.socket(self.socket_type[sock])

            # If the socket is a publisher, set a high water mark in order to protect the process from memory issues if subscribers can't receive fast enough
            if self.socket_type[sock] == zmq.PUB:
                self.sockets[sock].setsockopt(zmq.SNDHWM, self.hwm)

            # If the socket is a reply socket, set a linger period to avoid message loss
            elif self.socket_type[sock] == zmq.REP:
                self.sockets[sock].setsockopt(zmq.LINGER, rep_linger)

            # Bind socket to random port
            self.ports[sock] = self.sockets[sock].bind_to_random_port(addr='tcp://*', min_port=min_port, max_port=max_port, max_tries=max_tries)

    def create_internal_data_pub(self):
        """
        Create an internal publisher socket which publishes data in a sub-thread. The main *send_data* method
        has an internal subscriber bound to this publishers address and receives its data.

        Returns
        -------
        zmq.context.socket(zmq.PUB):
            A publisher socket which is used to publish data from concurrent thread
        """

        internal_data_pub = self.context.socket(zmq.PUB)
        internal_data_pub.setsockopt(zmq.SNDHWM, self.hwm)
        internal_data_pub.setsockopt(zmq.LINGER, 0)
        internal_data_pub.connect(self._internal_sub_addr)

        return internal_data_pub

    def _write_pid_file(self):
        """
        Method that writes information of this process into a yaml file and stores it in the config-folder
        of this package. The file is used by the main process of *irrad_control* to determine the PID as
        well as the ports.
        """

        # Construct dict with information on the process
        proc_info = {}

        # Fill dict
        proc_info['pid'] = self.pid
        proc_info['name'] = self.pname
        proc_info['ports'] = self.ports

        # Make file path; if a file already exists,overwrite
        with open(self.pfile, 'w') as pid_file:
            yaml.safe_dump(proc_info, pid_file, default_flow_style=False)

    def _remove_pid_file(self):
        """ Method that removes the PID file in the config-folder of this package on process shutdown process """
        if os.path.isfile(self.pfile):
            os.remove(self.pfile)

    def _setup(self):
        """Setup everything neeeded for the instance"""

        # Make zmq setup
        self._setup_zmq()

        # Redirect signals for graceful termination
        self._enable_graceful_shutdown()

        # Write PID file
        self._write_pid_file()

    def launch_thread(self, target, *args, **kwargs):
        """Launch a ThreadWorker instance with *target* function and append to self.threads"""

        # Create and launch
        thread = ThreadWorker(target=target, args=args, kwargs=kwargs)
        thread.start()

        # Add to instance threads
        self.threads.append(thread)

    def _launch_threads(self):
        """Launch this instances threads. Must be called within the *run* method"""

        # Start command receiver thread
        self.launch_thread(target=self.recv_cmd)

        # Start command receiver thread
        self.launch_thread(target=self.send_data)

        # If the process is a converter
        if self.is_converter:

            # Start data receiver thread
            self.launch_thread(target=self.recv_data)

    def _setup_logging(self):
        """
        Setup the logging module for the process. A custom logging handler is created which publishes
        the log messages on the port specified in *self.ports['log']*
        """

        # Numeric logging level
        numeric_level = getattr(logging, self.setup['session']['loglevel'].upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError('Invalid log level: {}'.format(self.setup['session']['loglevel'].capitalize()))

        # Set level
        logging.getLogger().setLevel(level=numeric_level)

        # Create logging publisher first
        handler = handlers.PUBHandler(self.sockets['log'])
        logging.getLogger().addHandler(handler)

        # Allow connections to be made
        sleep(1)

    @staticmethod
    def _tcp_addr(port, ip='*'):
        """
        Creates string of a complete tcp address which sockets can bind/connect to

        Parameters
        ----------
        port: int
            port to use
        ip: str
            IP address string

        Returns
        -------
        : str
            Formatted string that sockets can bind/connect to

        """
        return 'tcp://{}:{}'.format(ip, port)

    def recv_cmd(self):
        """
        Receiving commands at self.sockets['cmd']. This function is executed in an individual thread
        on calling the process' *start* method. This enables to receive commands on self.sockets['cmd']
        for setting up.
        """

        # Receive commands; wait 10 ms for stop flag
        while not self.stop_flags['recv'].wait(1e-2):

            # Check if were working on a command. We have to work sequentially
            if not self.state_flags['busy'].is_set():

                # Poll the command receiver socket for 1 ms; continue if there are no commands
                if not self.sockets['cmd'].poll(timeout=1, flags=zmq.POLLIN):
                    continue

                logging.debug("Receiving command")

                # Cmd must be dict with command as 'cmd' key and 'args', 'kwargs' keys
                cmd_dict = self.sockets['cmd'].recv_json()

                # Command data
                if 'data' not in cmd_dict:
                    cmd_dict['data'] = None

                error_reply = self._check_cmd(cmd_dict=cmd_dict)

                # Check for errors
                if error_reply:
                    self._send_reply(reply=error_reply, sender=self.pname, _type='ERROR', data=None)
                else:
                    logging.debug('Handling command {}'.format(cmd_dict['cmd']))

                    # Set cmd to busy; other commands send will be queued and received later
                    self.state_flags['busy'].set()

                    self.handle_cmd(**cmd_dict)

                # Check if a reply has been sent while handling the command. If not send generic reply which resets flag
                if self.state_flags['busy'].is_set():
                    self._send_reply(reply=cmd_dict['cmd'], sender=cmd_dict['target'], _type='STANDARD')
                    # Now flag is cleared

    def _check_cmd(self, cmd_dict):
        """
        Method used by the process to check whether a received command dict is valid

        Parameters
        ----------
        cmd_dict: dict
            dict containing 'target' and 'cmd' fields

        Returns
        -------
        error_reply: str
            empty string if no errors occurred, else string stating errors
        """

        # Containers for errors; empty string if everything is fine
        error_reply = ""

        # Extract info from cmd_dict
        try:

            target = cmd_dict['target']
            cmd = cmd_dict['cmd']

            # Command sanity checks
            # Log message for sanity checks
            error_log = "Target '{}' unknown. Known {} are: {}!"

            if target not in self.commands:
                logging.error(error_log.format(target, 'targets', ', '.join(self.commands.keys())))
                error_reply += "No {} target named {}\n".format(self.pname, target)

            elif cmd not in self.commands[target]:
                logging.error(error_log.format(cmd, 'commands', ', '.join(self.commands[target])))
                error_reply = 'No target command named {}'.format(cmd)

        except KeyError:
            error_reply += "Command dict incomplete. Missing 'cmd' or 'target' field!\n"
            logging.error("Incomplete command dict. Missing field(s): {}".format(', '.join(x for x in ('target', 'cmd') if x not in cmd_dict)))

        return error_reply

    def _send_reply(self, reply, _type, sender, data=None):
        """
        Method to reply to a received command via the *self.sockets['cmd']* socket. After replying, the
        *self.state_flags['busy']* is cleared in order to able to receive new commands

        Parameters
        ----------
        reply: str
            reply string, usually same as target string of *self.recv_cmd*
        _type: str:
            type of reply; either 'STANDARD' or 'ERROR'
        sender: str
            command string which is handled by *self.handle_cmd* method
        data: object
            Python-object which can be serialized via Json
        """

        # Make reply dict
        reply_dict = {'reply': reply, 'type': _type, 'sender': sender}

        # Add data if needed
        if data is not None:
            reply_dict['data'] = data

        # Send away and clear busy flag
        self.sockets['cmd'].send_json(reply_dict)
        self.state_flags['busy'].clear()

    def send_data(self):
        """
        Send out data on the corresponding self.sockets['data']. The data is mostly gathered from
        concurrent threads or other processes which publish to this instances *_internal_sub_addr*
        """

        internal_data_sub = self.context.socket(zmq.SUB)
        internal_data_sub.bind(self._internal_sub_addr)
        internal_data_sub.setsockopt(zmq.SUBSCRIBE, b'')  # specify bytes for Py3

        while not self.stop_flags['send'].is_set():  # Send data out as fast as possible

            # Poll the command receiver socket for 1 ms; continue if there are no commands
            if not internal_data_sub.poll(timeout=1, flags=zmq.POLLIN):
                continue

            # Get outgoing data from internal subscriber socket
            data = internal_data_sub.recv_json(zmq.NOBLOCK)

            # Send data on socket
            self.sockets['data'].send_json(data)

        internal_data_sub.close()

    def add_daq_stream(self, daq_stream):
        """
        Method to add a data stream address to listen to to convert data from

        Parameters
        ----------

        daq_stream: str, list, tuple
            String or iterable of strings of zmq addresses of data streams to connect to
        """

        streams_to_add = daq_stream if isinstance(daq_stream, (list, tuple)) else [daq_stream]

        if not all(isinstance(ds, str) for ds in streams_to_add):
            logging.error("Data streams must be of type string")
            return

        for ds in streams_to_add:
            if self._check_addr(ds) and ds not in self.daq_streams:
                self.daq_streams.append(ds)

    def recv_data(self):
        """Main method which receives raw data and calls interpretation and data storage methods"""

        if self.daq_streams:

            logging.info('Start receiving data')

            # Create subscriber for raw and XY-Stage data
            external_data_sub = self.context.socket(zmq.SUB)

            # Loop over all servers and connect to their respective data streams
            for stream in self.daq_streams:
                external_data_sub.connect(stream)

            # Subscribe to all topics
            external_data_sub.setsockopt(zmq.SUBSCRIBE, b'')  # specify bytes for Py3

            internal_data_pub = self.create_internal_data_pub()

            # While event not set receive data
            while not self.stop_flags['recv'].wait(1e-3):

                # Poll the command receiver socket for 1 ms; continue if there are no commands
                if not external_data_sub.poll(timeout=1, flags=zmq.POLLIN):
                    continue

                # Get data
                data = external_data_sub.recv_json(flags=zmq.NOBLOCK)

                # Interpret data
                interpreted_data = self.interpret_data(raw_data=data)

                # Publish data to internal pub
                for int_dat in interpreted_data:
                    internal_data_pub.send_json(int_dat)

            external_data_sub.close()
            internal_data_pub.close()

        else:
            logging.error("No data streams to connect to. Add streams via 'add_daq_stream'-method")

    def shutdown(self, signum=None, frame=None):
        """
        Method called to shut down the process gracefully. It can be called from within the class and is
        used to handle SIGINT / SIGTERM signals sent to the underlying process. The arguments are artifacts
        of the signal handling handler signature and are only used when handling signals

        Parameters
        ----------
        signum: int, None
            integer of signal or None if not called as signal handler
        frame: FrameObject, None
            FrameObject used in traceback etc or None if not called as signal handler
        """

        # Debug
        logging.debug("Shutdown of process {} with PID {} initiated".format(self.pname, self.pid))

        # Set signals
        for flag in self.stop_flags:
            self.stop_flags[flag].set()

    def _watch_threads(self):
        """
        Main function which is run: checks all the threads in which work is done and logs when an exception occurrs
        """

        reported = []

        # Check threads until stop flag is set
        while not self.stop_flags['watch'].wait(1.0):

            # Loop over all threads and check whether exceptions have occurred
            for daq_thread in self.threads:

                # If an exception occurred and has not yet been reported
                if daq_thread.exception is not None and daq_thread not in reported:

                    # Construct error message
                    msg = "A {} exception occurred in thread executing function '{}':\n".format(type(daq_thread.exception).__name__, daq_thread.name)
                    msg += "{}\nThread is currently {}alive ".format(daq_thread.traceback_str, '' if daq_thread.is_alive() else 'not ')

                    # Log message
                    logging.error(msg)

                    # Append to list of already reported exceptions
                    reported.append(daq_thread)

    def _close(self):

        # Wait for all the threads to join
        for t in self.threads:
            t.join()

        # Close action
        self._remove_pid_file()

        # Clean up
        self.clean_up()

        logging.info("Process {} with PID {} shut down successfully".format(self.pname, self.pid))

    def run(self):
        """ Main process function"""

        # Setup everything
        self._setup()

        # Launch DAQ threads of the process
        self._launch_threads()

        # The main loop of the process: watch the DAQ threads; BLOCKING
        #############################################
        self._watch_threads()
        #############################################

        # Close everything
        self._close()

    def interpret_data(self, raw_data):
        if self.is_converter:
            raise NotImplementedError("Implement a *interpret_data* method for converter processes")

    def handle_cmd(self, target, cmd, data=None):
        raise NotImplementedError("Implement a *handle_cmd* method")

    def clean_up(self):
        raise NotImplementedError("Implement a *clean_up* method")
