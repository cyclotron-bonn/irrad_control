from irrad_control.devices.serial_device import SerialDevice


class ISEGHighVoltagePS(SerialDevice):

    # Command references from protocol
    CMDS = {
        'set_voltage': 'D1={}',
        'set_delay': 'W={}',
        'get_voltage': 'U1',
        'get_delay' : 'W',
        'confirm': 'G1'
        }

    ERRORS = {
        '????': 'Command rejected'
    }

    # Maximum voltage that is allowed for this power supply
    V_MAX = 600  #V

    @property
    def voltage(self):
        return float(self.query(self.CMDS['get_voltage']))

    @voltage.setter
    def voltage(self, voltage):
        if voltage > self.V_MAX:
            raise ValueError(f"Value too high! Maximum allowed voltage is {self.V_MAX} V")
        self._set_value_and_confirm(cmd='set_voltage', val=voltage)

    @property
    def current(self):
        raise NotImplementedError
    
    @current.setter
    def current(self, curr):
        raise AttributeError("This attribute is read-only")

    @property
    def delay(self):
        return float(self.query(self.CMDS['get_delay']))

    @delay.setter
    def delay(self, dly):
        self._set_value_and_confirm(cmd='set_delay', val=dly)

    @property
    def polarity(self):
        raise NotImplementedError

    @polarity.setter
    def polarity(self, pol):
        raise NotImplementedError

    @property
    def ramp_speed(self):
        raise NotImplementedError

    @ramp_speed.setter
    def ramp_speed(self, rs):
        raise NotImplementedError

    def __init__(self, port, high_voltage=None):
        super().__init__(port=port, baudrate=9600)
        self.WRITE_TERMINATION = '\r\n'
        self.READ_TERMINATION = '\r\n'

        self.high_voltage = high_voltage

    def _set_value_and_confirm(self, cmd, val):
        """
        Sets a value via sending a command string and confirms the selection by sending a confirmation command

        Parameters
        ----------
        cmd : str
            Command string contained in self.CMDS
        val : float, int
            Value to set
        """
        self.query(self.CMDS[cmd].format(val))
        return self.query(self.CMDS['confirm'])

    def write(self, msg):
        super().write(msg)
        self._intf.read(len(msg))  # FIXME: why does it need to be like this?

    def read(self):
        """
        Overwrites read method to check whether the read value is contained in self.ERRORS.
        If so, raise a RuntimeError. If not just return read value

        Returns
        -------
        str
            Value read from serial bus

        Raises
        ------
        RuntimeError
            Value read from serial bus is an error
        """
        read_value = super().read()
        
        if read_value in self.ERRORS:
            raise RuntimeError(self.ERRORS[read_value])
        
        return read_value

    def output_on(self):
        raise NotImplementedError

    def output_off(self):
        raise NotImplementedError

    def hv_on(self):
        self.voltage = self.high_voltage

    def hv_off(self):
        self.voltage = 0
