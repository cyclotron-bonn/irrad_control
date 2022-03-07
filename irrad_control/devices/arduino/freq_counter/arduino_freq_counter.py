from irrad_control.devices.arduino.arduino_serial import ArduinoSerial

class ArduinoFreqCounter(ArduinoSerial):

    # Command references
    CMDS = {'gate_interval': 'G',
            'counts': 'C',
            'frequency': 'F',
            'restart': 'R'}
    
    ERRORS = {
        'error': "An error occured"
    }

    @property
    def gate_interval(self):
        """
        Sampling time during which is counted in ms 

        Returns
        -------
        int
            Sampling time in milliseconds
        """
        return int(self.query(self.create_command(self.CMDS['gate_interval'])))

    @gate_interval.setter
    def gate_interval(self, gate_interval):
        """
        Setter of the gate interval property

        Parameters
        ----------
        gate_interval : int
            Gate interval in milliseconds

        Raises
        ------
        RuntimeError
            Set gate interval and retrieved interval are unequal
        """
        
        gate_seconds = gate_interval / 1000.0
        
        # If the gate_interval is the same as the serial timeout, we have to increase it
        if self._intf.timeout <= gate_seconds:
            self._intf.timeout = gate_seconds * 1.5
            
        self._set_and_retrieve(cmd='gate_interval', val=int(gate_interval))

    @property
    def counts(self):
        return int(self.query(self.create_command(self.CMDS['counts'])))

    @property
    def frequency(self):
        return int(self.query(self.create_command(self.CMDS['frequency'])))

    def __init__(self, port, baudrate=115200, timeout=1):
        super().__init__(port, baudrate, timeout)

    def restart(self):
        return self.write(self.create_command(self.CMDS['restart']))
