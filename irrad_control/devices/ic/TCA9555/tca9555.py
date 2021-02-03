import wiringpi as wp
import bitstring as bs
from collections import Iterable


def _check_register(func):

    def wrapper(instance, **kwargs):

        if kwargs['reg'] not in instance.regs:
            # Construct error message
            err_msg = 'write to' if 'set' in func.__name__ else 'read from'
            err_msg = 'Cannot {} register {}, it does not exist.'.format(err_msg, kwargs['reg'])
            err_msg = '{}. Available registers: {}'.format(err_msg, ', '.join(instance.regs.keys()))

            raise ValueError(err_msg)

        # Call function
        func(instance, **kwargs)


class TCA9555(object):
    """
    This class implements an interface to the 16-bit IO expander using the I2C-interface of a Raspberry Pi

    The TCA9555 consists of two 8-bit Configuration (input or output selection), Input Port, Output Port and
    Polarity Inversion (active high or active low operation) registers which are also referred to as ports:
    Port 0 covers the IO bits P[7:0], port 1 covers bits P[15:8] (P[17:10] in datasheet convention). The bit
    representation of the bit states hardware-wise is big-endian:

        port state: 128 == 0b10000000 == bit 7 high, all others low
        port state: 1 == 0b00000001 == bit 0 high, all others low

    The default of representing the bit states within this class is to order by actual bit indices

        port state: '10000000' ==  bit 0 high, all others low
        port state: '00000001' == bit 7 high, all others low
    """

    # Internal registers of (port_0, port_1)
    regs = {
        # Registers holding the actual values of the pin levels
        'input': (0x00, 0x01),
        # Registers holding the target values of pin levels
        'output': (0x02, 0x03),
        # Registers holding the polarity (active-high or active-low)
        'polarity': (0x04, 0x05),
        # Registers holding whether the pins are configured as in- (1) or output (0)
        'config': (0x06, 0x07)
    }

    # Number of available io bits; bits are shared into ports
    _n_io_bits = 16

    # Number of bits of one port
    _n_bits_per_port = 8

    # Number of ports of TCA9555
    _n_ports = 2

    def __init__(self, address=0x20, config=None):
        """
        Initialize the connection to the chip and set the a configuration if given

        address: int
            integer of the I2C address of the TCA9555 (default is 0x20 e.g. 32)
        config: dict
            dictionary holding register values which should be set
        """

        # I2C-bus address; 0x20 (32 in decimal) if all address pins A0=A1=A2 are low
        self.address = address

        # Setup I2C-bus communication using wiringpi library
        self.device_id = wp.wiringPiI2CSetup(self.address)

        # Quick check; if self.device_id == -1 an error occurred
        if self.device_id == -1:
            raise IOError("Failed to establish connection on I2C-bus address {}".format(hex(self.address)))

        if config:
            self.config = config

    @property
    def io_state(self):
        return self.get_state('input')

    @io_state.setter
    def io_state(self, state):
        self.set_state('output', state)

    @property
    def n_io_bits(self):
        return self._n_io_bits

    @n_io_bits.setter
    def n_io_bits(self, val):
        raise ValueError("This is a read-only property")

    @property
    def n_bits_per_port(self):
        return self._n_bits_per_port

    @n_bits_per_port.setter
    def n_bits_per_port(self, val):
        raise ValueError("This is a read-only property")

    @property
    def n_ports(self):
        return self._n_ports

    @n_ports.setter
    def n_ports(self, val):
        raise ValueError("This is a read-only property")

    @property
    def config(self):
        return {reg: self.get_state(reg) for reg in self.regs}

    @config.setter
    def config(self, config):
        for reg, val in config.items():
            self.set_state(reg, val)

    def _write_reg(self, reg, data):
        """
        Writes one byte of *data* to register *reg*
        reg: int
            register value to write byte to
        data: 8 bit
            8 bit of data to write

        Returns
        -------
        Integer indicating successful write
        """
        return wp.wiringPiI2CWriteReg8(self.device_id, reg, data)

    def _read_reg(self, reg):
        """
        Reads one byte of *data* from register *reg*

        Parameters
        ----------
        reg: int
            register value to write byte to

        Returns
        -------
        8 bit of data read from *reg*
        """
        return wp.wiringPiI2CReadReg8(self.device_id, reg)

    def _create_state(self, state, bit_length):
        """
        Method to create a BitArray which represents the desired *state* of *bit_length* bits

        Parameters
        ----------
        state: BitArray, int, str, Iterable
            state from which to create a BitArray
        bit_length: int
            length of the state
        """
        if isinstance(state, bs.BitArray):
            pass

        elif isinstance(state, int):
            state = bs.BitArray('uint:{}={}'.format(bit_length, state))

        elif isinstance(state, Iterable):
            state = bs.BitArray(state)

        else:
            raise ValueError('State must be integer, string or BitArray representing {} bits'.format(bit_length))

        if len(state) != bit_length:
            raise ValueError('State must be {}} bits'.format(bit_length))

        return state

    def _check_register(self, reg):

        if reg not in self.regs:
            raise ValueError('Register {} does not exist. Available registers: {}'.format(reg, ', '.join(self.regs.keys())))

    def set_state(self, reg, state):

        # Create empty target register state
        target_reg_state = self._create_state(state, self._n_io_bits)

        for port in range(self._n_ports):

            # Compare individual current port states with target port states
            target_port_state = target_reg_state[port * self._n_bits_per_port:(port + 1) * self._n_bits_per_port]

            if target_port_state != self.get_port_state(reg=reg, port=port):
                self.set_port_state(reg=reg, port=port, state=target_port_state)

    def get_state(self, reg):

        state = self._create_state(self._n_io_bits, self._n_io_bits)

        for port in range(self._n_ports):
            current_port_state = self.get_port_state(reg=reg, port=port)
            state[port * self._n_bits_per_port:(port + 1) * self._n_bits_per_port] = current_port_state

        return state

    def get_port_state(self, reg, port):

        # Check if register exists
        self._check_register(reg)

        # Read port state
        port_state = self._create_state(state=self._read_reg(reg=self.regs[reg][port]), bit_length=self._n_bits_per_port)

        # Match bit order with physical pin order, increasing left to right
        port_state.reverse()

        return port_state

    def set_port_state(self, reg, port, state):

        # Check if register exists
        self._check_register(reg)

        target_state = self._create_state(state=state, bit_length=self._n_bits_per_port)

        target_state.reverse()

        self._write_reg(reg=self.regs[reg][port], data=target_state.uint)

    def set_output(self, pins=None):

        if pins is not None:
            # Get current io configuration state
            state = self.get_state(reg='config')
        else:
            # Set all pins as outputs
            self.set_state('config', [0]*self._n_io_bits)

    def set_input(self, pins=None):
        if pins is not None:
            # Get current io configuration state
            state = self.get_state(reg='config')
        else:
            # Set all pins as outputs
            self.set_state('config', [1]*self._n_io_bits)

    def int_to_bits(self, bits, val):

        state = self.io_state

        val_bits = bs.BitArray('uint:{}={}'.format(len(bits), val))
        val_bits.reverse()

        for i, bit in enumerate(bits):
            state[bit] = val_bits[i]

        self.io_state = state

    def int_from_bits(self, bits):

        state = self.io_state

        val_bits = bs.BitArray([state[bit] for bit in bits])
        val_bits.reverse()

        return val_bits.uint

    def format_config(self, format_='bin'):
        return {reg: getattr(state, format_) for reg, state in self.config.items()}

    def _check_bits(self, bits, val):

        if val.bit_length() > len(bits):
            raise ValueError

        pass
