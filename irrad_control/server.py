import logging
from time import time
from serial import SerialException
from irrad_control.utils.daq_proc import DAQProcess
from irrad_control.devices.adc.ADS1256_definitions import *
from irrad_control.devices.adc.ADS1256_drates import ads1256_drates
from irrad_control.devices.adc.pipyadc import ADS1256
from irrad_control.devices.stage.zaber import ZaberMultiStage
from irrad_control.devices.stage.base_axis import BaseAxisTracker
from irrad_control.devices.temp.arduino_temp_sens import ArduinoTempSens
from irrad_control import xy_stage_config, xy_stage_config_yaml
from irrad_control.utils.dut_scan import DUTScan


class IrradServer(DAQProcess):
    """Implements a server process which controls the DAQ and XYStage"""

    def __init__(self, name=None):

        # Set name of this interpreter process
        name = 'server' if name is None else name

        # Dict of known commands
        commands = {'adc': [],
                    'temp': [],
                    'server': ['start', 'shutdown'],
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
            xy_config = xy_stage_config
            xy_config['filename'] = xy_stage_config_yaml

            self.xy_stage = ZaberMultiStage(n_axis=2, port='/dev/ttyUSB0', config=xy_config)  # TODO: pass port as arg in device setup
            self.axis_tracker = BaseAxisTracker()
            self.axis_tracker.setup_zmq(ctx=self.context, skt=self.socket_type['data'], addr=self._internal_sub_addr, sender=self.server)

            for i, axis in enumerate(self.xy_stage.axis):
                self.axis_tracker.track_axis(axis=axis, axis_id='ScanAxis{}'.format(i))

            self.dut_scan = DUTScan(scan_stage=self.xy_stage)
            self.dut_scan.setup_zmq(ctx=self.context, skt=self.socket_type['data'], addr=self._internal_sub_addr, sender=self.server)

        except SerialException:
            logging.error("Could not connect to port {}. Maybe it is used by another process?".format("/dev/ttyUSB0"))
            logging.warning("XYStage removed from server devices")
            del self.commands['stage']

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

        elif target == 'stage':

            if cmd == 'move_rel':

                self.xy_stage.axis[0 if data['axis'] == 'x' else 1].move_rel(value=data['distance'], unit=data['unit'])

                _data = [axis.get_position(unit='mm') for axis in self.xy_stage.axis]

                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)

            elif cmd == 'move_abs':

                self.xy_stage.axis[0 if data['axis'] == 'x' else 1].move_abs(value=data['distance'], unit=data['unit'])

                _data = [axis.get_position(unit='mm') for axis in self.xy_stage.axis]

                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)

            elif cmd == 'set_speed':

                self.xy_stage.axis[0 if data['axis'] == 'x' else 1].set_speed(value=data['speed'], unit=data['unit'])

                _data = [axis.get_speed(unit='mm/s') for axis in self.xy_stage.axis]

                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)

            elif cmd == 'set_range':

                self.xy_stage.axis[0 if data['axis'] == 'x' else 1].set_range(value=data['range'], unit=data['unit'])

                _data = [axis.get_range(unit='mm') for axis in self.xy_stage.axis]

                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)

            elif cmd == 'prepare':
                self.dut_scan.setup_scan(**data)
                _data = {'n_rows': self.dut_scan.scan_config['n_rows'], 'rows': self.dut_scan.scan_config['rows']}

                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)

            elif cmd == 'scan':
                self.dut_scan.scan_device()

            elif cmd == 'stop':
                if not self.dut_scan.event('stop'):
                    self.dut_scan.event('stop', True)

            elif cmd == 'finish':
                if not self.dut_scan.event('finish'):
                    self.dut_scan.event('finish', True)

            elif cmd == 'pos':
                _data = [axis.get_position(unit='mm') for axis in self.xy_stage.axis]
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)

            elif cmd == 'get_pos':
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=self.xy_stage.config[0]['positions'])  #FIXME!!!

            elif cmd == 'add_pos':
                self.xy_stage.add_position(**data)

            elif cmd == 'del_pos':
                self.xy_stage.remove_position(data)

            elif cmd == 'move_pos':
                self.xy_stage.move_to_position(**data)

            elif cmd == 'get_speed':
                _data = [axis.get_speed(unit='mm/s') for axis in self.xy_stage.axis]
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)

            elif cmd == 'get_range':
                _data = [axis.get_range(unit='mm') for axis in self.xy_stage.axis]
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)

            elif cmd == 'home':
                self.xy_stage.home_stage()
                _data = [axis.get_position(unit='mm') for axis in self.xy_stage.axis]
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)

            elif cmd == 'no_beam':
                if data:
                    if not self.dut_scan.event('no_beam'):
                        self.dut_scan.event('no_beam', True)
                else:
                    if not self.dut_scan.event('no_beam'):
                        self.dut_scan.event('no_beam', False)
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
