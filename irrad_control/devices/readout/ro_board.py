from . import ro_board_config
from ..ic.TCA9555.tca9555 import TCA9555


class IrradDAQBoard(object):

    def __init__(self, address=0x20, version='v0.1'):

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
        return self._intf.int_from_bits(bits=self.config['pins']['temp'])

    @temp_channel.setter
    def temp_channel(self, ch):
        self._intf.int_to_bits(bits=self.config['pins']['temp'], val=ch)

    @staticmethod
    def _check_mux_group(self, check, group):

        if check not in group:
            raise ValueError('Multiplexer group {} does not exist. Existing groups: {}'.format(check, ', '.join(group)))

    def set_mux_value(self, group, val):

        self._check_mux_group(check=group, group=self.config['mux_groups'])

        self._intf.int_to_bits(self.config['pins'][group], val=val)

    def get_mux_value(self, group):

        self._check_mux_group(check=group, group=self.config['mux_groups'])

        return self._intf.int_from_bits(bits=self.config['pins'][group])

    def set_ifs(self, group, ifs):

        self._check_mux_group(check=group, group=self.config['gain_groups'])

        ifs_idx = self.config['current_scales'].index(ifs / self.config['jumper_scale'])

        self._intf.int_to_bits(self.config['pins'][group], val=ifs_idx)

    def get_ifs(self, group):

        self._check_mux_group(check=group, group=self.config['gain_groups'])

        ifs_idx = self._intf.int_from_bits(bits=self.config['pins'][group])

        return self.config['current_scales'][ifs_idx] * self.config['jumper_scale']
