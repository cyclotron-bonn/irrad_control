from itertools import count
from irrad_control.devices.arduino.arduino_serial import ArduinoSerial



class ArduinoFreqCounter(ArduinoSerial):

    # Command references
    CMDS = {'sampling_time': 'G',
            'counts': 'C',
            'frequency': 'F',
            'restart': 'R'}
    
    ERROR_CODES = {
        'error': "An error occured"
    }

    @property
    def sampling_time(self):
        """
        Sampling time during which is counted in ms 

        Returns
        -------
        int
            Sampling time in milliseconds
        """
        return int(self.query(self.create_command(self.CMDS['sampling_time'])))

    @sampling_time.setter
    def sampling_time(self, sampling_time):
        """
        Setter of the sampling time property

        Parameters
        ----------
        sampling_time : int
            Sampling time in milliseconds

        Raises
        ------
        RuntimeError
            Set sampling time and retrieved sampling are unequal
        """
        self._set_and_retrieve(cmd='sampling_time', val=int(sampling_time))

    @property
    def counts(self):
        return int(self.query(self.create_command(self.CMDS['counts'])))

    @counts.setter
    def counts(self, val):
        raise AttributeError("Attribute is read-only")

    @property
    def frequency(self):
        return int(self.query(self.create_command(self.CMDS['frequency'])))

    @frequency.setter
    def frequency(self, val):
        raise AttributeError("Attribute is read-only")

    def __init__(self, port, baudrate=115200, timeout=1):
        super().__init__(port, baudrate, timeout)
        self.CMDS.update(ArduinoSerial.CMDS)
        self.ERRORS.update(ArduinoSerial.ERRORS)

    def restart(self):
        return self.write(self.create_command(self.CMDS['restart']))
