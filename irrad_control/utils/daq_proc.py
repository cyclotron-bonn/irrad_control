import os
import yaml
import zmq
import logging
import signal
from time import sleep
from multiprocessing import Process
from threading import Thread, Event
from zmq.log import handlers
from irrad_control import config_path


class DAQProcess(Process):
    """Base-class of processes used in irrad_control"""

    def __init__(self, name, commands, daq_streams=None, hwm=None):
        super(DAQProcess, self).__init__()

        # Initialize a name which is connected to this process
        self.pname = name
        self.pfile = os.path.join(config_path, '.irrad.pid')  # Create hidden PID file

        # Events to handle sending / receiving of data and commands
        self.stop_flags = dict([(x, Event()) for x in ('send', 'recv')])
        self.state_flags = dict([(x, Event()) for x in ('busy', 'converter')])

        # Ports/sockets used by this process
        self.ports = {'log': None, 'cmd': None, 'data': None}
        self.sockets = {'log': None, 'cmd': None, 'data': None}
        self.socket_type = {'log': zmq.PUB, 'cmd': zmq.REP, 'data': zmq.PUB}

        # Attribute holding zmq context
        self.context = None

        # Internal process communication using zmq inproc transport
        self._internal_sub_addr = 'inproc://internal_pub'

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
        return self.state_flags['converter'].is_set()

    @is_converter.setter
    def is_converter(self, state):
        self.state_flags['converter'].set() if bool(state) else self.state_flags['converter'].clear()

    def _check_addr(self, addr):
        """Check address format"""

        if not isinstance(addr, basestring):
            logging.error("Address must be string")
            return False

        try:
            protocol, destination, port = addr.split(':')
        except ValueError:
            logging.error("Incorrect address format. Must be 'protocol://ip:port'")
            return False

        try:
            port = int(port)
            if not 0 < port < 2**16 - 1:
                raise ValueError
        except ValueError:
            logging.error("'port' must be an integer between 1 and {} (16 bit)".format(2**16 - 1))
            return False

        return True if protocol else False

    def _graceful_shutdown(self):

        # Enable graceful termination
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGQUIT):
            signal.signal(sig, self.shutdown)

    def _setup_zmq(self):

        # Create a context instance
        self.context = zmq.Context()

        # Create sockets
        self._allocate_sockets()

    def _close_zmq(self):

        # Close the sockets and context
        for sock in self.sockets:
            self.sockets[sock].close()

        # Terminate context
        self.context.term()

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

        internal_data_pub = self.context.socket(zmq.PUB)
        internal_data_pub.setsockopt(zmq.SNDHWM, self.hwm)
        internal_data_pub.bind(self._internal_sub_addr)

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
        """
        Method that removes the PID file in the config-folder of this package on process shutdown process
        """
        if os.path.isfile(self.pfile):
            os.remove(self.pfile)

    def _setup_process(self):

        # Make zmq setup
        self._setup_zmq()

        # Redirect signals for graceful termination
        self._graceful_shutdown()

        # Write PID file
        self._write_pid_file()

        # Start command receiver thread
        recv_cmd_thread = Thread(target=self.recv_cmd)
        recv_cmd_thread.start()

        # Add to instance threads
        self.threads.append(recv_cmd_thread)

        # If the process has been initialized with da streams, it's a converter
        if self.is_converter:
            self.start_converter()

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

            if cmd not in self.commands[target]:
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
        """Send data on the corresponding socket """

        internal_data_sub = self.context.socket(zmq.SUB)
        internal_data_sub.connect(self._internal_sub_addr)
        internal_data_sub.setsockopt(zmq.SUBSCRIBE, '')

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

        streams_to_add = daq_stream if isinstance(daq_stream, (list, tuple)) else [daq_stream]

        if not all(isinstance(ds, str) for ds in streams_to_add):
            logging.error("Data streams must be of type string")
            return

        for ds in streams_to_add:
            if self._check_addr(ds) and ds not in self.daq_streams:
                self.daq_streams.append(ds)

    def start_converter(self, daq_stream=None):

        # Set flag is this method is called after initializing the process
        self.is_converter = True

        if daq_stream is not None:
            self.add_daq_stream(daq_stream=daq_stream)

        # Start data receiver thread
        recv_data_thread = Thread(target=self.recv_data)
        recv_data_thread.start()

        # Add to instance threads
        self.threads.append(recv_data_thread)

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
            external_data_sub.setsockopt(zmq.SUBSCRIBE, '')

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

    def run(self):
        """ Main process function"""

        # Set up the process
        self._setup_process()

        # The main loop of the process sends out data
        #############################################
        self.send_data()
        #############################################

        # Wait for all the threads to join
        for t in self.threads:
            t.join()

        # Close action
        self._remove_pid_file()

        # Clean up
        self.clean_up()

        logging.info("Process {} with PID {} shut down successfully".format(self.pname, self.pid))

        # Close all zmq-related objects
        self._close_zmq()

    def interpret_data(self, raw_data):
        if self.is_converter:
            raise NotImplementedError("Implement a *interpret_data* method for converter processes")

    def handle_cmd(self, target, cmd, data=None):
        raise NotImplementedError("Implement a *handle_cmd* method")

    def clean_up(self):
        raise NotImplementedError("Implement a *clean_up* method")
