import logging
from time import time
from serial import SerialException

# Package imports
from irrad_control.devices import devices
from irrad_control.utils.daq_proc import DAQProcess


class IrradServer(DAQProcess):
    """Implements a server process which controls the DAQ and XYStage"""

    def __init__(self, name=None):

        # Set name of this interpreter process
        name = 'server' if name is None else name

        # Dict of known commands
        commands = {'adc': [],
                    'temp': [],
                    'server': ['start', 'shutdown'],
                    'ro_board': ['set_ifs', 'get_ifs', 'set_temp_ch', 'cycle_temp_chs', 'get_gpio', 'set_gpio'],
                    'stage': ['move_rel', 'move_abs', 'prepare', 'scan', 'finish', 'stop', 'pos', 'home',
                              'set_speed', 'get_speed', 'no_beam', 'set_range', 'get_range', 'add_pos', 'del_pos', 'move_pos', 'get_pos']
                    }

        # Hold server devices
        self.devices = {}

        # Call init of super class
        super(IrradServer, self).__init__(name=name, commands=commands)

    def _start_server(self, setup):
        """Sets up the server process"""

        # Update setup
        self.server = setup['server']
        self.setup = setup['setup']

        # Overwrite server setup with our server
        self.setup['server'] = self.setup['server'][self.server]

        # Setup logging
        self._setup_logging()

        self._init_devices()

        self._launch_daq_threads()

    def _init_devices(self):

        # Loop over server devices and initialize
        for dev in self.setup['server']['devices']:

            try:
                init_kwargs = self.setup['server']['devices'][dev]['init']

                if init_kwargs:
                    self.devices[dev] = getattr(devices, dev)(**init_kwargs)
                else:
                    self.devices[dev] = getattr(devices, dev)()

                if dev == 'ADCBoard':
                    self.devices[dev].drate = self.setup['server']['readout']['sampling_rate']
                    self.devices[dev].setup_channels(self.setup['server']['readout']['ch_numbers'])

                if dev == 'ZaberXYStage':
                    # Setup zmq for the stage to publish data
                    self.devices[dev].setup_zmq(ctx=self.context, skt=self.socket_type['data'],
                                                addr=self._internal_sub_addr, sender=self.server)

            except (IOError, SerialException) as e:

                if type(e) is SerialException:
                    msg = "Could not connect to serial port {}. Maybe it is used by another process?"

                    if 'port' in self.setup['server']['devices'][dev]['init']:
                        port = self.setup['server']['devices'][dev]['init']['port']
                    elif 'serial_port' in self.setup['server']['devices'][dev]['init']:
                        port = self.setup['server']['devices'][dev]['init']['serial_port']
                    else:
                        port = 'unknown'

                    logging.error(msg.format(port))

                else:
                    if dev == 'ADCBoard':
                        logging.error("Could not access SPI device file. Enable SPI interface!")

                logging.warning("{} removed from server devices".format(dev))

                if dev in self.commands:
                    del self.commands[dev]

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
                self.launch_thread(target=self.daq_thread, args=(self._daq_adc,))

            elif dev == 'ArduinoTempSens':
                self.launch_thread(target=self.daq_thread, args=(self._daq_temp,))

    def _daq_adc(self):
        """
        Does data acquisition of ADC
        """

        # Add meta data and data
        _meta = {'timestamp': time(), 'name': self.server, 'type': 'raw'}

        _data = self.devices['ADCBoard'].read_channels(self.setup['server']['readout']['channels'])

        # If we're using the NTC readout of the DAqBoard
        if 'IrradDAQBoard' in self.devices and 'ntc' in self.setup['server']['readout']:
            # Expect the temp channel only to be changed programmatically
            _meta['ntc_ch'] = self.devices['IrradDAQBoard'].get_temp_channel(cached=True)

        return _meta, _data

    def _daq_temp(self):
        """
        Does data acquisition in separate thread by reading the temp values and putting the result into the outgoing queue
        """

        # Add meta data and data
        _meta = {'timestamp': time(), 'name': self.server, 'type': 'temp'}

        temp_setup = self.setup['server']['devices']['ArduinoTempSens']['setup']

        # Read raw temp data
        raw_temp = self.devices['ArduinoTempSens'].get_temp(sorted(temp_setup.keys()))

        _data = dict([(temp_setup[sens], raw_temp[sens]) for sens in raw_temp])

        return _meta, _data

    def handle_cmd(self, target, cmd, data=None):
        """Handle all commands. After every command a reply must be send."""

        # Handle server commands
        if target == 'server':

            if cmd == 'start':

                # Start server with setup which is cmd data
                self._start_server(data)
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=self.pid)

            elif cmd == 'shutdown':
                self.shutdown()

        elif target == 'ro_board':

            ro_board = self.devices['IrradDAQBoard']

            if cmd == 'set_ifs':
                ro_board.set_ifs(group=data['group'], ifs=data['ifs'])
            elif cmd == 'get_ifs':
                _data = ro_board.get_ifs(group=data['group'])
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)
            elif cmd == 'set_temp_ch':
                if ro_board.is_cycling_temp_channels():
                    ro_board.stop_cycle_temp_channels()
                ro_board.set_temp_channel(channel=data['ch'])
            elif cmd == 'cycle_temp_chs':
                ro_board.cycle_temp_channels(channels=data['chs'], timeout=data['timeout'])
            elif cmd == 'set_gpio':
                ro_board.gpio_value = data['val']
            elif cmd == 'get_gpio':
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=ro_board.gpio_value)

        elif target == 'stage':

            xy_stage = self.devices['ZaberXYStage']

            if cmd == 'move_rel':
                axis = data['axis']
                if axis == 'x':
                    xy_stage.move_relative(data['distance'], xy_stage.x_axis, unit=data['unit'])
                elif axis == 'y':
                    xy_stage.move_relative(data['distance'], xy_stage.y_axis, unit=data['unit'])

                _data = [xy_stage.steps_to_distance(pos, unit='mm') for pos in xy_stage.position]

                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)

            elif cmd == 'move_abs':
                axis = data['axis']
                if axis == 'x':
                    xy_stage.move_absolute(data['distance'], xy_stage.x_axis, unit=data['unit'])
                elif axis == 'y':
                    _m_dist = xy_stage.steps_to_distance(int(300e-3 / xy_stage.microstep), unit=data['unit'])
                    d = _m_dist - data['distance']
                    xy_stage.move_absolute(d, xy_stage.y_axis, unit=data['unit'])

                _data = [xy_stage.steps_to_distance(pos, unit='mm') for pos in xy_stage.position]

                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)

            elif cmd == 'set_speed':
                axis = data['axis']
                if axis == 'x':
                    xy_stage.set_speed(data['speed'], xy_stage.x_axis, unit=data['unit'])
                elif axis == 'y':
                    xy_stage.set_speed(data['speed'], xy_stage.y_axis, unit=data['unit'])

                _data = [xy_stage.get_speed(a, unit='mm/s') for a in (xy_stage.x_axis, xy_stage.y_axis)]

                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)

            elif cmd == 'set_range':
                axis = data['axis']
                if axis == 'x':
                    xy_stage.set_range(data['range'], xy_stage.x_axis, unit=data['unit'])
                elif axis == 'y':
                    xy_stage.set_range(data['range'], xy_stage.y_axis, unit=data['unit'])

                _data = [xy_stage.get_range(xy_stage.x_axis, unit='mm'), xy_stage.get_range(xy_stage.y_axis, unit='mm')]

                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)

            elif cmd == 'prepare':
                xy_stage.prepare_scan(server=self.server, **data)
                _data = {'n_rows': xy_stage.scan_params['n_rows'], 'rows': xy_stage.scan_params['rows']}

                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)

            elif cmd == 'scan':
                xy_stage.scan_device()

            elif cmd == 'stop':
                if not xy_stage.stop_scan.is_set():
                    xy_stage.stop_scan.set()

            elif cmd == 'finish':
                if not xy_stage.finish_scan.is_set():
                    xy_stage.finish_scan.set()

            elif cmd == 'pos':
                _data = [xy_stage.steps_to_distance(pos, unit='mm') for pos in xy_stage.position]
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)

            elif cmd == 'get_pos':
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=xy_stage.config['positions'])

            elif cmd == 'add_pos':
                xy_stage.add_position(**data)

            elif cmd == 'del_pos':
                xy_stage.remove_position(data)

            elif cmd == 'move_pos':
                xy_stage.move_to_position(**data)

            elif cmd == 'get_speed':
                speed = [xy_stage.get_speed(a, unit='mm/s') for a in (xy_stage.x_axis, xy_stage.y_axis)]
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=speed)

            elif cmd == 'get_range':
                _range = [xy_stage.get_range(xy_stage.x_axis, unit='mm'), xy_stage.get_range(xy_stage.y_axis, unit='mm')]
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_range)

            elif cmd == 'home':
                xy_stage.home_stage()
                _data = [xy_stage.steps_to_distance(pos, unit='mm') for pos in xy_stage.position]
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)

            elif cmd == 'no_beam':
                if data:
                    if not xy_stage.pause_scan.is_set():
                        xy_stage.pause_scan.set()
                else:
                    if xy_stage.pause_scan.is_set():
                        xy_stage.pause_scan.clear()
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=data)

    def clean_up(self):
        """Mandatory clean up - method"""
        try:
            del self.xy_stage
        except AttributeError:
            pass


def main():

    irrad_server = IrradServer()
    irrad_server.start()
    irrad_server.join()


if __name__ == '__main__':
    main()
