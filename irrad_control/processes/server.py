import logging
from bitstring import CreationError
from time import time, sleep
from serial import SerialException

# Package imports
from irrad_control.devices import devices
from irrad_control.devices.motorstage import motorstage
from irrad_control.devices.motorstage.base_axis import BaseAxis, BaseAxisTracker
from irrad_control.utils.dut_scan import DUTScan
from irrad_control.devices.readout import RO_DEVICES
from irrad_control.processes.daq import DAQProcess
from irrad_control.utils.events import create_irrad_events


class IrradServer(DAQProcess):
    """Implements a server process which controls the DAQ and XYStage"""

    def __init__(self, name=None):

        # Set name of this interpreter process
        name = 'server' if name is None else name

        # Hold server devices
        self.devices = {}

        self._motorstages = []

        self.irrad_events = create_irrad_events()

        # Call init of super class
        super(IrradServer, self).__init__(name=name)

    def _start_server(self, setup):
        """Sets up the server process"""

        # Update setup
        self.server = setup['server']
        self.setup = setup['setup']
        self.name = setup['setup']['server'][self.server]['name']

        # Overwrite server setup with our server
        self.setup['server'] = self.setup['server'][self.server]

        # Setup logging
        self._setup_logging()

        self._init_devices()

        self._setup_devices()

        self._launch_daq_threads()

        # Listen to events from converter
        self.add_event_stream(event_stream=self._tcp_addr(ip=self.setup['host'], port=self.setup['ports']['event']))
        self.launch_thread(target=self.recv_event)

    def _init_devices(self):

        # Dict holding potentially shared ports which connect to multi-device controllers
        shared_ports = {}

        # When ever a BaseAxis device is initialized, we want to track the movement
        self.axis_tracker = BaseAxisTracker(context=self.context,
                                            address=self._internal_sub_addr,
                                            sender=self.server)

        # Loop over server devices and initialize
        for dev in self.setup['server']['devices']:

            try:

                # Get device and init kwargs
                device = getattr(devices, dev)
                init_kwargs = self.setup['server']['devices'][dev]['init']

                # Check if device is Zaber motorstage which potentially shares port through multi controller
                if issubclass(device, (devices.ZaberStepAxis, devices.ZaberMultiAxis)):
                    port = init_kwargs['port']
                    # Check if port has been opened
                    if port not in shared_ports:
                        shared_ports[port] = devices.ZaberAsciiPort(port)
                    init_kwargs['port'] = shared_ports[port]

                # Actually initialize device
                if isinstance(init_kwargs, dict):
                    self.devices[dev] = device(**init_kwargs)
                else:
                    self.devices[dev] = device()

                # Device is a motorstages
                if hasattr(motorstage, dev):

                    # If device is BaseAxis, track movement
                    if isinstance(self.devices[dev], BaseAxis):
                        self.axis_tracker.track_axis(axis=self.devices[dev], axis_id=0, axis_domain=dev)

                    elif hasattr(self.devices[dev], 'axis'):
                        for axis_id, a in enumerate(self.devices[dev].axis):
                            if isinstance(a, BaseAxis):
                                self.axis_tracker.track_axis(axis=a, axis_id=axis_id, axis_domain=dev)

                    # Store device names of motorstages
                    self._motorstages.append(dev)

            except (IOError, SerialException, CreationError) as e:

                if type(e) is SerialException:
                    msg = "Could not connect to serial port {}. Maybe it is used by another process?"

                    if 'port' in self.setup['server']['devices'][dev]['init']:
                        port = self.setup['server']['devices'][dev]['init']['port']
                    elif 'serial_port' in self.setup['server']['devices'][dev]['init']:
                        port = self.setup['server']['devices'][dev]['init']['serial_port']
                    else:
                        port = 'unknown'

                    logging.error(msg.format(port))
                elif type(e) is CreationError:
                    logging.error("Could not find DAQBoard on I2C bus")
                else:
                    if dev == 'ADCBoard':
                        logging.error("Could not access SPI device file. Enable SPI interface!")
                    else:
                        logging.error(f"Error when initializing device '{dev}': {repr(e)}")

                if dev in self.devices:
                    del self.devices[dev]
                    logging.warning("{} removed from server devices".format(dev))

    def _setup_devices(self):

        ### Specific device-related procedures ###

        if 'ADCBoard' in self.devices:
            self.devices['ADCBoard'].drate = self.setup['server']['readout']['sampling_rate']
            self.devices['ADCBoard'].setup_channels(self.setup['server']['readout']['ch_numbers'])

        self._daq_board_ntc_ro = False
        if 'IrradDAQBoard' in self.devices and self.setup['server']['readout']['device'] == RO_DEVICES.DAQBoard:
            # Set initial ro scales
            self.devices['IrradDAQBoard'].set_ifs(group='sem',
                                                  ifs=self.setup['server']['readout']['ro_group_scales']['sem'])
            self.devices['IrradDAQBoard'].set_ifs(group='ch12',
                                                  ifs=self.setup['server']['readout']['ro_group_scales']['ch12'])

            if 'ntc' in self.setup['server']['readout']:
                ntc_channels = [int(ntc) for ntc in self.setup['server']['readout']['ntc']]
                self.devices['IrradDAQBoard'].init_ntc_readout(ntc_channels=ntc_channels)
                self.launch_thread(target=self._sync_ntc_readout)
                self._daq_board_ntc_ro = True

        if 'RadiationMonitor' in self.devices:
            self.on_demand_events['rad_monitor_ready'].clear()

        if 'ScanStage' in self.devices:

            # Add special __scan__ device which from now on can be accessed via the direct device calls
            self.devices['__scan__'] = DUTScan(scan_stage=self.devices['ScanStage'],
                                               irrad_events=self.irrad_events)

            # Connect to ZMQ
            self.devices['__scan__'].setup_zmq(ctx=self.context,
                                               skt=self.socket_type['data'],
                                               addr=self._internal_sub_addr,
                                               sender=self.server)

    def daq_thread(self, daq_func):
        """
        Does data acquisition in separate thread, retrieving results and putting them into the outgoing queue
        """

        internal_data_pub = self.create_internal_data_pub()

        # Acquire data if not stop signal is set
        while not self.stop_flags['send'].is_set():

            meta, data = daq_func()

            # Put data into outgoing queue
            internal_data_pub.send_json({'meta': meta, 'data': data})

    def _launch_daq_threads(self):

        for dev in self.devices:

            # Start data sending thread
            if dev == 'ADCBoard':
                self.launch_thread(target=self.daq_thread, daq_func=self._daq_adc)

            elif dev == 'ArduinoNTCReadout':
                self.launch_thread(target=self.daq_thread, daq_func=self._daq_temp)

            elif dev == 'RadiationMonitor':
                self.launch_thread(target=self.daq_thread, daq_func=self._daq_rad_monitor)

    def _daq_adc(self):
        """
        Does data acquisition of ADC
        """

        # Add meta data and data
        _meta = {'timestamp': time(), 'name': self.server, 'type': 'raw_data'}

        _data = self.devices['ADCBoard'].read_channels(self.setup['server']['readout']['channels'])

        # If we're using the NTC readout of the DAqBoard
        if self._daq_board_ntc_ro:
            _meta['ntc_ch'] = self.devices['IrradDAQBoard'].ntc
            if self.devices['IrradDAQBoard'].ntc_sync.is_set():
                self.devices['IrradDAQBoard'].next_ntc()
                self.devices['IrradDAQBoard'].ntc_sync.clear()
        return _meta, _data

    def _sync_ntc_readout(self, sync_time=0.2):
        """Sync ADC readout with switching NTC channels on IrradDAQBoard"""
        while not self.stop_flags['send'].wait(sync_time):
            self.devices['IrradDAQBoard'].ntc_sync.set()

    def _daq_temp(self):
        """
        Does data acquisition in separate thread by reading the temp values and putting the result into the outgoing queue
        """

        # Add meta data and data
        _meta = {'timestamp': time(), 'name': self.server, 'type': 'temp'}

        temp_setup = self.setup['server']['devices']['ArduinoNTCReadout']['setup']

        # Read raw temp data
        raw_temp = self.devices['ArduinoNTCReadout'].get_temp(sorted(temp_setup.keys()))

        _data = dict([(temp_setup[sens], raw_temp[sens]) for sens in raw_temp])

        return _meta, _data

    def _daq_rad_monitor(self):

        # Wait until we want to read the daq_monitor; less CPU-hungry than pure Event.wait() see https://stackoverflow.com/questions/29082268/python-time-sleep-vs-event-wait/29082411#29082411
        while not self.on_demand_events['rad_monitor_ready'].is_set():
            sleep(1)
        
        dose_rate, frequency = self.devices['RadiationMonitor'].get_dose_rate(return_frequency=True)

        # Add meta data and data
        meta = {'timestamp': time(), 'name': self.server, 'type': 'rad_monitor'}
        data = {'dose_rate': dose_rate, 'frequency': frequency}

        return meta, data

    def _call_device_method(self, device, method, call_data):

        def _call(call_kwargs, callback=None):

            # Make result dict and call
            res = {
                'call': {'method': method, 'kwargs': call_kwargs, 'device': device},
                'result': getattr(self.devices[device], method)(**call_kwargs)
            }

            # Check for callback
            if callback and hasattr(self.devices[device], callback['method']):
                res['callback'] = {**callback}
                callback_kwargs = res['callback'].get('kwargs', {}) 
                res['callback']['result'] = getattr(self.devices[device], res['callback']['method'])(**callback_kwargs)

            return res

        call_kwargs = {} if call_data is None else call_data.get('kwargs', {})
        callback = False if call_data is None else call_data.get('callback', False)
        call_threaded = False if call_data is None else call_data.get('threaded', False)

        try:
            if call_threaded:
                data = self.launch_thread(target=_call, call_kwargs=call_kwargs, callback=callback)  # data will be None
            else:
                data =_call(call_kwargs, callback)
            
            self._send_reply(reply=method, sender=device, _type='STANDARD', data=data)
        except Exception as e:
            self._send_reply(reply=method, _type='ERROR', sender=device, data=repr(e))

    def handle_cmd(self, target, cmd, data=None):
        """Handle all commands. After every command a reply must be send."""

        # Check if we want to call a devices method directly
        if target in self.devices and hasattr(self.devices[target], cmd):
            self._call_device_method(device=target, method=cmd, call_data=data)

        # Handle server commands
        elif target == 'server':

            if cmd == 'start':

                # Start server with setup which is cmd data
                self._start_server(data)
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=self.pid)

            elif cmd == 'shutdown':
                self.shutdown()

            elif cmd == 'motorstages':
                reply_data = {ms :{'positions': self.devices[ms].get_positions(), 'props': self.devices[ms].get_physical_props()} for ms in self._motorstages}
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=reply_data)

            elif cmd == 'rad_mon_daq':
                # Toggle rad monitor DAQ
                if data is True:
                    self.on_demand_events['rad_monitor_ready'].set()
                else:
                    self.on_demand_events['rad_monitor_ready'].clear()

        else:
            logging.error(f"Command {cmd} with target {target} does not exist for server {self.name}.")
            self._send_reply(reply=cmd, _type='ERROR', sender=target)

    def handle_event(self, event_data):

        # Only handle events of this server
        if event_data['server'] != self.server:
            logging.warning(f"Received event of server {event_data['server']} not meant for this server {self.server}!")
            return
        
        try:
            event_name = event_data['event']
            self.irrad_events[event_name].value.active = event_data['active']
            self.irrad_events[event_name].value.disabled = event_data['disabled']
            logging.debug(f"Event {event_data['event']} on server {self.name} is {'' if event_data['active'] else 'in'}active")
        except KeyError:
            logging.error(f"Event {event_name} unknown!")

    def clean_up(self):
        """Mandatory clean up - method"""
        # Check if we want to store configs
        for dev in self.devices:
            if hasattr(self.devices[dev], 'save_config'):
                self.devices[dev].save_config()
            if hasattr(self.devices[dev], 'shutdown'):
                self.devices[dev].shutdown()


def run(blocking=True):

    irrad_server = IrradServer()
    irrad_server.start()
    
    if blocking:
        irrad_server.join()


if __name__ == '__main__':
    run()
