from . import ro_board_config
from ..ic.TCA9555.tca9555 import TCA9555


class IrradDAQBoard(object):

    def __init__(self, version='v0.1', address=0x20):

        # Check for version support
        if version not in ro_board_config:
            raise ValueError("{} not supported. Supported versions are {}".format(version, ', '.join(ro_board_config.keys())))

        # Initialize the interface to the board via I2C
        self._intf = TCA9555(address=address)

        # Store the board config
        self.config = ro_board_config[version]

        # Setup the initial state of the board
        self._setup_defaults()

    def _setup_defaults(self):

        # Set the direction (in or output) of the pins
        self._intf.set_direction(direction=0, bits=self.config['defaults']['output'])
        self._intf.set_direction(direction=1, bits=self.config['defaults']['input'])

        # Set the input current scale IFS
        self.set_ifs(group='sem', ifs=self.config['defaults']['sem_ifs'])
        # Set the input current scale
        self.set_ifs(group='ch12', ifs=self.config['defaults']['ch12_ifs'])

        self.temp_channel = self.config['defaults']['temp_ch']

    @property
    def temp_channel(self):
        if 'temp_ch' not in self.config:
            self.config['temp_ch'] = self._intf.int_from_bits(bits=self.config['pins']['temp'])
        return self.config['temp_ch']

    @temp_channel.setter
    def temp_channel(self, ch):
        self._intf.int_to_bits(bits=self.config['pins']['temp'], val=ch)
        self.config['temp_ch'] = ch

    @property
    def jumper_scale(self):
        return self.config['jumper_scale']

    @jumper_scale.setter
    def jumper_scale(self, js):
        if js not in (1, 10):
            raise ValueError('The input jumper scales the full-scale current range (IFS) either by 1 or 10.')
        self.config['jumper_scale'] = js

    @property
    def gpio_value(self):
        return self._intf.int_from_bits(bits=self.config['pins']['gpio'])

    @gpio_value.setter
    def gpio_value(self, val):
        self._intf.int_to_bits(bits=self.config['pins']['gpio'], val=val)

    def set_mux_value(self, group, val):

        self._intf.int_to_bits(self.config['pins'][group], val=val)

    def get_mux_value(self, group):

        return self._intf.int_from_bits(bits=self.config['pins'][group])

    def set_ifs(self, group, ifs):

        ifs_idx = self.config['ifs_scales'].index(ifs / self.config['jumper_scale'])

        self._intf.int_to_bits(self.config['pins'][group], val=ifs_idx)

    def get_ifs(self, group):

        ifs_idx = self._intf.int_from_bits(bits=self.config['pins'][group])

        return self.config['ifs_scales'][ifs_idx] * self.config['jumper_scale']

    def get_ifs_label(self, group):

        ifs_idx = self._intf.int_from_bits(bits=self.config['pins'][group])

        return self.config['ifs_labels'][ifs_idx] if self.config['jumper_scale'] == 1 else self.config['ifs_labels_10'][ifs_idx]

    def _check_and_map_gpio(self, pins):

        pins = [pins] if isinstance(pins, int) else pins

        if any(not 0 <= p < len(self.config['pins']['gpio']) for p in pins):
            raise IndexError("GPIO pins are indexed from {} to {}".format(0, len(self.config['pins']['gpio']) - 1))

        return [self.config['pins']['gpio'][p] for p in pins]

    def set_gpio_pins(self, pins):

        self._intf.set_bits(bits=self._check_and_map_gpio(pins=pins))

    def unset_gpio_pins(self, pins):

        self._intf.unset_bits(bits=self._check_and_map_gpio(pins=pins))
