from threading import Thread, Event

# Package imports
from irrad_control.devices.readout import DAQ_BOARD_CONFIG
from irrad_control.devices.ic.TCA9555.tca9555 import TCA9555


class IrradDAQBoard(object):

    def __init__(self, port, version='v0.1', address=0x20):

        # Check for version support
        if version not in DAQ_BOARD_CONFIG['version']:
            raise ValueError("{} not supported. Supported versions are {}".format(version, ', '.join(DAQ_BOARD_CONFIG['version'].keys())))

        # Initialize the interface to the board via I2C
        self._intf = TCA9555(port=port, address=address)
        self.version = version

        # Related to ntc channel cycling
        # NTC readouts; iterable of ints corresponding to pin header number
        self.ntc_channels = None
        self.ntc = None
        self._ntc_cycle_thread = None
        self._stop_ntc_cycle_flag = Event()
        self._ntc_idx = 0
        self.ntc_sync = Event()

        # Setup the initial state of the board
        self.restore_defaults()

    def restore_defaults(self):

        # Set the direction (in or output) of the pins
        self._intf.set_direction(direction=0, bits=DAQ_BOARD_CONFIG['version'][self.version]['defaults']['output'])
        self._intf.set_direction(direction=1, bits=DAQ_BOARD_CONFIG['version'][self.version]['defaults']['input'])

        # Set the input current scale IFS
        self.set_ifs(group='sem', ifs=DAQ_BOARD_CONFIG['version'][self.version]['defaults']['sem_ifs'])
        # Set the input current scale
        self.set_ifs(group='ch12', ifs=DAQ_BOARD_CONFIG['version'][self.version]['defaults']['ch12_ifs'])

        self.set_ntc_channel(channel=DAQ_BOARD_CONFIG['version'][self.version]['defaults']['ntc_ch'])

    def init_ntc_readout(self, ntc_channels):
        self.ntc_channels = [ntc_channels] if isinstance(ntc_channels, int) else ntc_channels
        # Set first channel
        self.set_ntc_channel(self.ntc_channels[self._ntc_idx])

    @property
    def jumper_scale(self):
        # FIXME
        return DAQ_BOARD_CONFIG['common']['jumper_scale']

    @jumper_scale.setter
    def jumper_scale(self, js):
        if js not in (1, 10):
            raise ValueError('The input jumper scales the full-scale current range (IFS) either by 1 or 10.')
        # FIXME this changes value in global constant config
        DAQ_BOARD_CONFIG['common']['jumper_scale'] = js

    @property
    def gpio_value(self):
        return self._intf.int_from_bits(bits=DAQ_BOARD_CONFIG['version'][self.version]['pins']['gpio'])

    @gpio_value.setter
    def gpio_value(self, val):
        self._intf.int_to_bits(bits=DAQ_BOARD_CONFIG['version'][self.version]['pins']['gpio'], val=val)

    @property
    def gpio_direction(self):
        return [self._intf.format_config()['config'][p] for p in DAQ_BOARD_CONFIG['version'][self.version]['pins']['gpio']]

    @gpio_direction.setter
    def gpio_direction(self, direction):
        self._intf.set_direction(bits=DAQ_BOARD_CONFIG['version'][self.version]['pins']['gpio'], direction=direction)

    def set_mux_value(self, group, val):

        self._intf.int_to_bits(DAQ_BOARD_CONFIG['version'][self.version]['pins'][group], val=val)

    def get_mux_value(self, group):

        return self._intf.int_from_bits(bits=DAQ_BOARD_CONFIG['version'][self.version]['pins'][group])

    def get_ntc_channel(self, cached=False):

        if self.ntc is None or not cached:
            self.ntc = self._intf.int_from_bits(bits=DAQ_BOARD_CONFIG['version'][self.version]['pins']['ntc'])

        return self.ntc

    def set_ntc_channel(self, channel):

        self._intf.int_to_bits(bits=DAQ_BOARD_CONFIG['version'][self.version]['pins']['ntc'], val=channel)

        self.ntc = channel

    def set_ifs(self, group, ifs):
        # FIXME
        ifs_idx = DAQ_BOARD_CONFIG['common']['ifs_scales'].index(ifs / DAQ_BOARD_CONFIG['common']['jumper_scale'])

        self._intf.int_to_bits(DAQ_BOARD_CONFIG['version'][self.version]['pins'][group], val=ifs_idx)

    def get_ifs(self, group):

        ifs_idx = self._intf.int_from_bits(bits=DAQ_BOARD_CONFIG['version'][self.version]['pins'][group])
        # FIXME
        return DAQ_BOARD_CONFIG['common']['ifs_scales'][ifs_idx] * DAQ_BOARD_CONFIG['common']['jumper_scale']

    def get_ifs_label(self, group):

        ifs_idx = self._intf.int_from_bits(bits=DAQ_BOARD_CONFIG['version'][self.version]['pins'][group])
        # FIXME
        return DAQ_BOARD_CONFIG['common']['ifs_labels'][ifs_idx] if DAQ_BOARD_CONFIG['common']['jumper_scale'] == 1 else DAQ_BOARD_CONFIG['common']['ifs_labels_10'][ifs_idx]

    def _check_and_map_gpio(self, pins):

        pins = [pins] if isinstance(pins, int) else pins

        if any(not 0 <= p < len(DAQ_BOARD_CONFIG['version'][self.version]['pins']['gpio']) for p in pins):
            raise IndexError("GPIO pins are indexed from {} to {}".format(0, len(DAQ_BOARD_CONFIG['version'][self.version]['pins']['gpio']) - 1))

        return [DAQ_BOARD_CONFIG['version'][self.version]['pins']['gpio'][p] for p in pins]

    def set_gpio_value(self, pins, value):

        self._intf.int_to_bits(bits=self._check_and_map_gpio(pins=pins), val=value)

    def set_gpio_direction(self, pins, direction):

        self._intf.set_direction(bits=self._check_and_map_gpio(pins=pins), direction=direction)

    def set_gpio_pins(self, pins):

        self._intf.set_bits(bits=self._check_and_map_gpio(pins=pins))

    def unset_gpio_pins(self, pins):

        self._intf.unset_bits(bits=self._check_and_map_gpio(pins=pins))

    def is_cycling_ntc_channels(self):
        return False if self._ntc_cycle_thread is None else self._ntc_cycle_thread.is_alive()

    def stop_cycle_ntc_channels(self):
        if not self.is_cycling_ntc_channels():
            return
        self._stop_ntc_cycle_flag.set()
        self._ntc_cycle_thread.join()
        self._stop_ntc_cycle_flag.clear()
        self._ntc_cycle_thread = None

    def cycle_ntc_channels(self, timeout=None):

        # In case of restart
        if self.is_cycling_ntc_channels():
            self.stop_cycle_ntc_channels()

        self._ntc_cycle_thread = Thread(target=self._cycle_ntc_channels, args=(timeout, ))
        self._ntc_cycle_thread.start()

    def _cycle_ntc_channels(self, timeout=None):

        while not self._stop_ntc_cycle_flag.wait(timeout=timeout):
            self.next_ntc()

    def next_ntc(self):

        # If there are not ntc channels or there is only one, do nothing
        if self.ntc_channels is None or len(self.ntc_channels) == 1:
            return

        self.set_ntc_channel(channel=self.ntc_channels[self._ntc_idx])
        self._ntc_idx = self._ntc_idx + 1 if self._ntc_idx != len(self.ntc_channels) - 1 else 0
