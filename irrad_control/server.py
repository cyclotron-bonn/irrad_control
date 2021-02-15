import logging
from time import time
from serial import SerialException

# Package imports
from .utils.daq_proc import DAQProcess
from .devices.ic.ADS1256.ADS1256_definitions import *
from .devices.ic.ADS1256.ADS1256_drates import ads1256_drates
from .devices.ic.ADS1256.pipyadc import ADS1256
from .devices.stage.xystage import ZaberXYStage
from .devices.temp.arduino_temp_sens import ArduinoTempSens
from .devices.readout.ro_board import IrradDAQBoard


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

        # If this server has an ADC, setup and start sending data
        if 'adc' in self.setup['server']['devices']:

            # Setup adc and start DAQ in separate thread
            self._init_daq_adc()

        # Otherwise remove from command list
        else:
            del self.commands['adc']

        # If this server has temp sensor
        if 'temp' in self.setup['server']['devices']:

            self._init_daq_temp()

        # Otherwise remove from command list
        else:
            del self.commands['temp']

        # If this server has stage
        if 'stage' in self.setup['server']['devices']:

            self._init_xy_stage()

        # Otherwise remove from command list
        else:
            del self.commands['stage']

        # If this server has stage
        if 'ro_board' in self.setup['server']['devices']:

            self._init_ro_board()

        # Otherwise remove from command list
        else:
            del self.commands['ro_board']

    def _init_daq_adc(self):
        """Setup the ADS1256 instance and channels"""

        try:
            self.adc_setup = self.setup['server']['devices']['adc']

            # Instance of ADS1256 ADC on WaveShare board
            self.adc = ADS1256()

            # Set initial data rate from DAQ setup
            self.adc.drate = ads1256_drates[self.adc_setup['sampling_rate']]

            # Calibrate the ADC before DAQ
            self.adc.cal_self()

            # Declare all available channels of the ADS1256
            pos_channels = (POS_AIN0, POS_AIN1, POS_AIN2, POS_AIN3, POS_AIN4, POS_AIN5, POS_AIN6, POS_AIN7)
            gnd = NEG_AINCOM
            self.adc_channels = []

            # Assign the physical channel numbers e.g. multiplexer address
            for ch in self.adc_setup['ch_numbers']:
                # Single-ended versus common ground gnd
                if isinstance(ch, int):
                    tmp_ch = pos_channels[ch] | gnd
                # Differential measurement
                else:
                    a, b = ch
                    tmp_ch = pos_channels[a] | pos_channels[b]
                # Add to channels
                self.adc_channels.append(tmp_ch)

            # Start data sending thread
            self.launch_thread(target=self._daq_adc)

        except IOError:
            logging.error("Could not access SPI device file. Enable SPI interface!")
            logging.warning("ADC removed from server devices")
            del self.commands['adc']

    def _daq_adc(self):
        """
        Does data acquisition int separate thread by reading the ADC values and putting the result into the outgoing queue
        """

        internal_data_pub = self.create_internal_data_pub()

        # Acquire data if not stop signal is set
        while not self.stop_flags['send'].is_set():

            # Read raw data from ADC
            raw_data = self.adc.read_sequence(self.adc_channels)

            # Add meta data and data
            _meta = {'timestamp': time(), 'name': self.server, 'type': 'raw'}

            if 'ro_board' in self.setup['server']['devices']:
                _meta['temp_ch'] = self.ro_board.get_temp_channel(cached=True)  # Expect the temp channel only to be changed programmatically

            _data = dict([(self.adc_setup['channels'][i], raw_data[i] * self.adc.v_per_digit) for i in range(len(raw_data))])

            # Put data into outgoing queue
            internal_data_pub.send_json({'meta': _meta, 'data': _data})

    def _init_daq_temp(self):

        try:

            self.temp_setup = self.setup['server']['devices']['temp']

            # Init temp sens
            self.temp_sens = ArduinoTempSens(port="/dev/ttyUSB1")  # TODO: pass port as arg in device setup

            # Start data sending thread
            self.launch_thread(target=self._daq_temp)

        except SerialException:
            logging.error("Could not connect to port {}. Maybe it is used by another process?".format("/dev/ttyUSB1"))
            logging.warning("Temperature sensor removed from server devices")
            del self.commands['temp']

    def _daq_temp(self):
        """
        Does data acquisition in separate thread by reading the temp values and putting the result into the outgoing queue
        """

        internal_data_pub = self.create_internal_data_pub()

        # Send data als long as specified
        while not self.stop_flags['send'].is_set():

            # Read raw temp data
            raw_temp = self.temp_sens.get_temp(sorted(self.temp_setup.keys()))

            # Add meta data and data
            _meta = {'timestamp': time(), 'name': self.server, 'type': 'temp'}
            _data = dict([(self.temp_setup[sens], raw_temp[sens]) for sens in raw_temp])

            # Put data into outgoing queue
            internal_data_pub.send_json({'meta': _meta, 'data': _data})

    def _init_xy_stage(self):

        try:
            # Init stage
            self.xy_stage = ZaberXYStage(serial_port='/dev/ttyUSB0')  # TODO: pass port as arg in device setup

            # Setup zmq for the stage to publish data
            self.xy_stage.setup_zmq(ctx=self.context, skt=self.socket_type['data'], addr=self._internal_sub_addr, sender=self.server)

        except SerialException:
            logging.error("Could not connect to port {}. Maybe it is used by another process?".format("/dev/ttyUSB0"))
            logging.warning("XYStage removed from server devices")
            del self.commands['stage']

    def _init_ro_board(self):

        try:
            # Init stage
            self.ro_board = IrradDAQBoard(version='v0.2')  # TODO: pass version as arg in device setup

        except IOError:
            logging.error("Could not find device on I2C bus address {}".format(0x20))
            logging.warning("IrradDAQBoard removed from server devices")
            del self.commands['ro_board']

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

            if cmd == 'set_ifs':
                self.ro_board.set_ifs(group=data['group'], ifs=data['ifs'])
            elif cmd == 'get_ifs':
                _data = self.ro_board.get_ifs(group=data['group'])
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)
            elif cmd == 'get_ifs':
                _data = self.ro_board.get_ifs(group=data['group'])
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)
            elif cmd == 'set_temp_ch':
                if self.ro_board.is_cycling_temp_channels():
                    self.ro_board.stop_cycle_temp_channels()
                self.ro_board.set_temp_channel(channel=data['ch'])
            elif cmd == 'cycle_temp_chs':
                self.ro_board.cycle_temp_channels(channels=data['chs'], timeout=data['timeout'])
            elif cmd == 'set_gpio':
                self.ro_board.gpio_value = data['val']
            elif cmd == 'get_gpio':
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=self.ro_board.gpio_value)

        elif target == 'stage':

            if cmd == 'move_rel':
                axis = data['axis']
                if axis == 'x':
                    self.xy_stage.move_relative(data['distance'], self.xy_stage.x_axis, unit=data['unit'])
                elif axis == 'y':
                    self.xy_stage.move_relative(data['distance'], self.xy_stage.y_axis, unit=data['unit'])

                _data = [self.xy_stage.steps_to_distance(pos, unit='mm') for pos in self.xy_stage.position]

                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)

            elif cmd == 'move_abs':
                axis = data['axis']
                if axis == 'x':
                    self.xy_stage.move_absolute(data['distance'], self.xy_stage.x_axis, unit=data['unit'])
                elif axis == 'y':
                    _m_dist = self.xy_stage.steps_to_distance(int(300e-3 / self.xy_stage.microstep), unit=data['unit'])
                    d = _m_dist - data['distance']
                    self.xy_stage.move_absolute(d, self.xy_stage.y_axis, unit=data['unit'])

                _data = [self.xy_stage.steps_to_distance(pos, unit='mm') for pos in self.xy_stage.position]

                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)

            elif cmd == 'set_speed':
                axis = data['axis']
                if axis == 'x':
                    self.xy_stage.set_speed(data['speed'], self.xy_stage.x_axis, unit=data['unit'])
                elif axis == 'y':
                    self.xy_stage.set_speed(data['speed'], self.xy_stage.y_axis, unit=data['unit'])

                _data = [self.xy_stage.get_speed(a, unit='mm/s') for a in (self.xy_stage.x_axis, self.xy_stage.y_axis)]

                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)

            elif cmd == 'set_range':
                axis = data['axis']
                if axis == 'x':
                    self.xy_stage.set_range(data['range'], self.xy_stage.x_axis, unit=data['unit'])
                elif axis == 'y':
                    self.xy_stage.set_range(data['range'], self.xy_stage.y_axis, unit=data['unit'])

                _data = [self.xy_stage.get_range(self.xy_stage.x_axis, unit='mm'), self.xy_stage.get_range(self.xy_stage.y_axis, unit='mm')]

                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)

            elif cmd == 'prepare':
                self.xy_stage.prepare_scan(server=self.server, **data)
                _data = {'n_rows': self.xy_stage.scan_params['n_rows'], 'rows': self.xy_stage.scan_params['rows']}

                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)

            elif cmd == 'scan':
                self.xy_stage.scan_device()

            elif cmd == 'stop':
                if not self.xy_stage.stop_scan.is_set():
                    self.xy_stage.stop_scan.set()

            elif cmd == 'finish':
                if not self.xy_stage.finish_scan.is_set():
                    self.xy_stage.finish_scan.set()

            elif cmd == 'pos':
                _data = [self.xy_stage.steps_to_distance(pos, unit='mm') for pos in self.xy_stage.position]
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)

            elif cmd == 'get_pos':
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=self.xy_stage.config['positions'])

            elif cmd == 'add_pos':
                self.xy_stage.add_position(**data)

            elif cmd == 'del_pos':
                self.xy_stage.remove_position(data)

            elif cmd == 'move_pos':
                self.xy_stage.move_to_position(**data)

            elif cmd == 'get_speed':
                speed = [self.xy_stage.get_speed(a, unit='mm/s') for a in (self.xy_stage.x_axis, self.xy_stage.y_axis)]
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=speed)

            elif cmd == 'get_range':
                _range = [self.xy_stage.get_range(self.xy_stage.x_axis, unit='mm'), self.xy_stage.get_range(self.xy_stage.y_axis, unit='mm')]
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_range)

            elif cmd == 'home':
                self.xy_stage.home_stage()
                _data = [self.xy_stage.steps_to_distance(pos, unit='mm') for pos in self.xy_stage.position]
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)

            elif cmd == 'no_beam':
                if data:
                    if not self.xy_stage.pause_scan.is_set():
                        self.xy_stage.pause_scan.set()
                else:
                    if self.xy_stage.pause_scan.is_set():
                        self.xy_stage.pause_scan.clear()
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
