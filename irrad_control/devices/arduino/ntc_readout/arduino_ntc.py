import logging

from irrad_control.devices.arduino.arduino_serial import ArduinoSerial


class ArduinoNTCReadout(ArduinoSerial):
    """Class to read from Arduino temperature sensor setup"""

    CMDS = {
        'temp': 'T',
        'delay': 'D',
        'samples': 'S'
    }
    
    ERRORS = {
        '999': "Invalid NTC pin",
        'error': "Serial transmission error"  # Custom return code for unsuccesful serial communciation
    }

    @property
    def n_samples(self):
        return int(self.query(self.create_command(self.CMDS['samples'])))

    @n_samples.setter
    def n_samples(self, n_samples):
        self._set_and_retrieve(cmd='samples', val=int(n_samples))

    def __init__(self, port="/dev/ttyUSB0", baudrate=115200, timeout=1, ntc_lim=(-55, 125)):
        super().__init__(port=port, baudrate=baudrate, timeout=timeout)
        self.ntc_lim = ntc_lim  # Store temperature limits of NTC thermistor

    def get_temp(self, sensor):
        """Gets temperature of sensor where 0 <= sensor <= 7 is the physical pin number of the sensor on
        the Arduino analog pin. Can also be a list of ints."""

        # Make int sensors to list
        sensor = sensor if isinstance(sensor, list) else [sensor]

        # Write command to read all these sensors
        self.write(self.create_command(self.CMDS['temp'], *sensor))

        # Get result; make sure we get the correct amount of results
        result = {s: float(self.read()) for s in sensor}

        for sens in result:
            if not self.ntc_lim[0] <= result[sens] <= self.ntc_lim[1]:
                msg = f"NTC {sens} out of clibration range (NTC_{sens}={result[sens]} °C, NTC_range=({self.ntc_lim[0]};{self.ntc_lim[1]}) °C)."
                msg += " Is the thermistor connected correctly?"
                logging.warning(msg)
        
        return result
