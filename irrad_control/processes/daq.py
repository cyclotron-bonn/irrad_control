import os
import yaml
import zmq
import logging
import signal
from time import sleep
from multiprocessing import Process
from threading import Event
from zmq.log import handlers
from irrad_control import pid_file
from irrad_control.utils.worker import ThreadWorker
from irrad_control.utils.utils import check_zmq_addr
from collections import defaultdict


class DAQProcess(Process):
    """Base-class of data acquisition processes"""

    def __init__(self, name, daq_streams=None, event_streams=None, hwm=None, internal_sub=None, *args, **kwargs):
        """
        Init the process

        Parameters
        ----------

        name: str
            Name of the process
        daq_streams: str, list, tuple
            String or iterable of strings of zmq addresses of data streams to connect to
        event_streams: str, list, tuple
            String or iterable of strings of zmq addresses of event streams to connect to
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

        # Events to handle sending / receiving of data and commands
        self.stop_flags = defaultdict(Event)  # Create events in subclasses on demand
        self.state_flags = defaultdict(Event)  # Create events in subclasses on demand

        # Ports/sockets used by this process
        self.ports = {"log": None, "cmd": None, "data": None, "event": None}
        self.sockets = {"log": None, "cmd": None, "data": None, "event": None}
        self.socket_type = {"log": zmq.PUB, "cmd": zmq.REP, "data": zmq.PUB, "event": zmq.PUB}

        # Attribute holding zmq context
        self.context = None

        # Sets internal subscriber address from which data is gathered (from potentially many sources) and published (on one port);
        # usually this is some intra-process communication protocol such as inproc/ipc. If not, this process listens to a different
        # DAQ processes DAQ threads in an attempt to distribute the load on multiple CPU cores more evenly
        self._internal_sub_addr = (
            internal_sub if internal_sub is not None and check_zmq_addr(internal_sub) else "inproc://internal"
        )

        # High-water mark for all ZMQ sockets
        self.hwm = 100 if hwm is None or not isinstance(hwm, int) else hwm

        # Attribute to store irrad session setup in
        self.setup = None

        # List to hold all threads of the process
        self.threads = []

        # List of input data stream addresses
        self.daq_streams = []

        if daq_streams is not None:
            self.add_daq_stream(daq_stream=daq_streams)

        # List of input data stream addresses
        self.event_streams = []

        if event_streams is not None:
            self.add_event_stream(event_stream=event_streams)

    def _enable_graceful_shutdown(self):
        """Method that redirects systems interrupt and terminatioin signals to the instances *shutdown* method"""

        # Enable graceful termination
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGQUIT):
            signal.signal(sig, self.shutdown)

    def _setup_zmq(self):
        """Setup the zmq context instance and allocate needed sockets"""

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
            self.ports[sock] = self.sockets[sock].bind_to_random_port(
                addr="tcp://*", min_port=min_port, max_port=max_port, max_tries=max_tries
            )

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
        proc_info["pid"] = self.pid
        proc_info["name"] = self.pname
        proc_info["ports"] = self.ports

        # Make file path; if a file already exists,overwrite
        with open(pid_file, "w") as pf:
            yaml.safe_dump(proc_info, pf, default_flow_style=False)

    def _remove_pid_file(self):
        """Method that removes the PID file in the config-folder of this package on process shutdown process"""
        if os.path.isfile(pid_file):
            os.remove(pid_file)

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

        # If there is data
        if len(self.daq_streams) > 0:
            # Start data receiver thread
            self.launch_thread(target=self.recv_data)

        # If there are events
        if len(self.event_streams) > 0:
            # Start data receiver thread
            self.launch_thread(target=self.recv_event)

    def _setup_logging(self):
        """
        Setup the logging module for the process. A custom logging handler is created which publishes
        the log messages on the port specified in *self.ports['log']*
        """

        # Numeric logging level
        numeric_level = getattr(logging, self.setup["session"]["loglevel"].upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError("Invalid log level: {}".format(self.setup["session"]["loglevel"].capitalize()))

        # Set level
        logging.getLogger().setLevel(level=numeric_level)

        # Create logging publisher first
        handler = handlers.PUBHandler(self.sockets["log"])
        logging.getLogger().addHandler(handler)

        # Allow connections to be made
        sleep(1)

    @staticmethod
    def _tcp_addr(port, ip="*"):
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
        return "tcp://{}:{}".format(ip, port)

    def recv_cmd(self):
        """
        Receiving commands at self.sockets['cmd']. This function is executed in an individual thread
        on calling the process' *start* method. This enables to receive commands on self.sockets['cmd']
        for setting up.
        """

        # Receive commands; wait 10 ms for stop flag
        while not self.stop_flags["__recv__"].wait(1e-2):
            # Check if were working on a command. We have to work sequentially
            if not self.state_flags["__busy__"].is_set():
                # Poll the command receiver socket for 1 ms; continue if there are no commands
                if not self.sockets["cmd"].poll(timeout=1, flags=zmq.POLLIN):
                    continue

                logging.debug("Receiving command")

                # Cmd must be dict with command as 'cmd' key and 'args', 'kwargs' keys
                cmd_dict = self.sockets["cmd"].recv_json()

                # Command data
                if "data" not in cmd_dict:
                    cmd_dict["data"] = None

                error_reply = self._check_cmd(cmd_dict=cmd_dict)

                # Check for errors
                if error_reply:
                    self._send_reply(reply=error_reply, sender=self.pname, _type="ERROR", data=None)
                else:
                    logging.debug("Handling command {}".format(cmd_dict["cmd"]))

                    # Set cmd to busy; other commands send will be queued and received later
                    self.state_flags["__busy__"].set()

                    self.handle_cmd(**cmd_dict)

                # Check if a reply has been sent while handling the command. If not send generic reply which resets flag
                if self.state_flags["__busy__"].is_set():
                    self._send_reply(reply=cmd_dict["cmd"], sender=cmd_dict["target"], _type="STANDARD")
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
            _, _ = cmd_dict["target"], cmd_dict["cmd"]

        except KeyError:
            error_reply += "Command dict incomplete. Missing 'cmd' or 'target' field!\n"
            logging.error(
                "Incomplete command dict. Missing field(s): {}".format(
                    ", ".join(x for x in ("target", "cmd") if x not in cmd_dict)
                )
            )

        return error_reply

    def _send_reply(self, reply, _type, sender, data=None):
        """
        Method to reply to a received command via the *self.sockets['cmd']* socket. After replying, the
        *self.state_flags['__busy__']* is cleared in order to able to receive new commands

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
        reply_dict = {"reply": reply, "type": _type, "sender": sender}

        # Add data if needed
        if data is not None:
            reply_dict["data"] = data

        # Send away and clear busy flag
        self.sockets["cmd"].send_json(reply_dict)
        self.state_flags["__busy__"].clear()

    def send_data(self):
        """
        Send out data on the corresponding self.sockets['data']. The data is mostly gathered from
        concurrent threads or other processes which publish to this instances *_internal_sub_addr*
        """

        internal_data_sub = self.context.socket(zmq.SUB)
        internal_data_sub.bind(self._internal_sub_addr)
        internal_data_sub.setsockopt(zmq.SUBSCRIBE, b"")  # specify bytes for Py3

        while not self.stop_flags["__send__"].is_set():  # Send data out as fast as possible
            # Poll the command receiver socket for 1 ms; continue if there are no commands
            if not internal_data_sub.poll(timeout=1, flags=zmq.POLLIN):
                continue

            # Get outgoing data from internal subscriber socket
            data = internal_data_sub.recv_json(zmq.NOBLOCK)

            # Send data on socket
            self.sockets["data"].send_json(data)

        internal_data_sub.close()

    def _add_stream(self, stream, stream_container):
        """
        Method to add a data/event stream address to listen to to

        Parameters
        ----------

        stream: str, list, tuple
            String or iterable of strings of zmq addresses of data streams to connect to
        stream_container: list
            List to which stream address is to be added to
        """

        streams_to_add = stream if isinstance(stream, (list, tuple)) else [stream]

        if not all(isinstance(ds, str) for ds in streams_to_add):
            logging.error("Data streams must be of type string")
            return

        for strm in streams_to_add:
            if check_zmq_addr(strm) and strm not in stream_container:
                stream_container.append(strm)

    def _recv_from_stream(self, kind, stream, callback, pub_results=False, delay=None):
        """
        Method which receives data from specific streams and calls a callback as well as publishes results internally.

        Parameters
        ----------
        kind : str
            Kind of stream to receive e.g. 'data' or 'event'
        stream : list
            List of streams to connect to
        callback : function
            Callable to be called on incoming packets
        pub_results : bool, optional
            Whther to create an internal publisher which send data via the 'send_data' method, by default False
        delay : float, optional
            Time in seconds sleep in between incoming data checks; useful save resources, by default None
        """

        if stream:
            logging.info(f"Start receiving {kind}")

            # Create subscriber for raw and XY-Stage data
            external_sub = self.context.socket(zmq.SUB)

            # Loop over all servers and connect to their respective data streams
            for s in stream:
                external_sub.connect(s)

            # Subscribe to all topics
            external_sub.setsockopt(zmq.SUBSCRIBE, b"")  # specify bytes for Py3

            if pub_results:
                internal_pub = self.create_internal_data_pub()

            # While event not set receive data
            while not self.stop_flags["__recv__"].is_set():
                # Poll the socket for 1 ms; continue if there is nothing
                if not external_sub.poll(timeout=1, flags=zmq.POLLIN):
                    # Allow the thread to release the GIL while sleeping if we don't need to check for incoming stream data full-speed
                    if delay is not None:
                        sleep(delay)
                    continue

                # Get data
                data = external_sub.recv_json(flags=zmq.NOBLOCK)

                # Callback for data
                result = callback(data)

                # Publish data
                if pub_results:
                    for res in result:
                        internal_pub.send_json(res)

            external_sub.close()
            if pub_results:
                internal_pub.close()

        else:
            logging.error("No streams to connect to. Add streams via '_add_stream'-method")

    def add_daq_stream(self, daq_stream):
        """
        Method to add a data stream address to listen to to convert data from

        Parameters
        ----------

        daq_stream: str, list, tuple
            String or iterable of strings of zmq addresses of data streams to connect to
        """
        self._add_stream(stream=daq_stream, stream_container=self.daq_streams)

    def recv_data(self):
        """Main method which receives raw data and calls interpretation and data storage methods"""
        self._recv_from_stream(kind="data", stream=self.daq_streams, callback=self.handle_data, pub_results=True)

    def add_event_stream(self, event_stream):
        """
        Method to add a data stream address to listen to to convert data from

        Parameters
        ----------

        event_stream: str, list, tuple
            String or iterable of strings of zmq addresses of event streams to connect to
        """
        self._add_stream(stream=event_stream, stream_container=self.event_streams)

    def recv_event(self):
        """Main method which receives events and calls handle event"""
        self._recv_from_stream(kind="events", stream=self.event_streams, callback=self.handle_event, delay=1e-2)

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

        # Check threads until stop flag is set
        while not self.stop_flags["__watch__"].wait(1.0):
            # Loop over all threads and check whether exceptions have occurred
            for thread in self.threads:
                is_alive = thread.is_alive()

                # If an exception occurred and has not yet been reported
                if thread.exception is not None:
                    # Construct error message
                    msg = "A {} exception occurred in thread executing function '{}':\n".format(
                        type(thread.exception).__name__, thread.name
                    )
                    msg += "{}\nThread is currently {}alive ".format(thread.traceback_str, "" if is_alive else "not ")

                    # Log message
                    logging.error(msg)

                # Remove thread object from container for garbage collection
                if not is_alive:
                    self.threads.remove(thread)

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
        """Main process function"""

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

    def handle_event(self, event_data):
        raise NotImplementedError("Implement a *handle_event* method")

    def handle_data(self, raw_data):
        raise NotImplementedError("Implement a *handle_data* method for converter processes")

    def handle_cmd(self, target, cmd, data=None):
        raise NotImplementedError("Implement a *handle_cmd* method")

    def clean_up(self):
        raise NotImplementedError("Implement a *clean_up* method")
