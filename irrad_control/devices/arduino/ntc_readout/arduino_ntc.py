import logging

from irrad_control.devices.arduino.arduino_serial import ArduinoSerial


class ArduinoNTCReadout(ArduinoSerial):
    """Class to read from Arduino temperature sensor setup"""

    CMDS = {
        'temp': 'T',
        'delay': 'D',
        'sample': 'S'
    }
    
    ERROR_CODES = {
        '999': "Invalid NTC pin",
        'error': "Serial transmission error"  # Custom return code for unsuccesful serial communciation
    }

    def __init__(self, port="/dev/ttyUSB0", baudrate=115200, timeout=5, ntc_lim=(-55, 125)):
        super().__init__(port=port, baudrate=baudrate, timeout=timeout)

        self.ntc_lim = ntc_lim  # Store temperature limits of NTC thermistor
        self._check_communication()

    def _check_communication(self):
        """
        Queries invalid pin to be read out for testing communictaion
        """
        res = self.query(self.create_command('T', 100))  # Try to read from pin 100 which does not exist
        if res == '999':
            logging.debug("Serial connection to Arduino temperature sensor established.")
        else:
            logging.error("No reply on serial connection to Arduino temperature sensor.")


    def get_temp(self, sensor):
        """Gets temperature of sensor where 0 <= sensor <= 7 is the physical pin number of the sensor on
        the Arduino analog pin. Can also be a list of ints."""

        # Make int sensors to list
        sensor = sensor if isinstance(sensor, list) else [sensor]

        # Write command to read all these sensors
        self.write(self.create_command(self.CMDS['temp'], *sensor))

        # Get result; make sure we get the correct amount of results
        result = {s: self.read() for s in sensor}

        for sens in result:
            if result[sens] in self.ERROR_CODES:
                logging.error(f"{self.ERROR_CODES[result[sens]]} for NTC {sens}")
            else:
                result[sens] = float(result[sens])

                if not self.ntc_lim[0] <= result[sens] <= self.ntc_lim[1]:
                    msg = f"NTC {sens} out of clibration range (NTC_{sens}={result[sens]} °C, NTC_range=({self.ntc_lim[0]};{self.ntc_lim[1]}) °C)."
                    msg += " Is the thermistor connected correctly?"
                    logging.warning(msg)
        
        return result

    def set_n_samples(self, n_samples):
        """
        Set the number of temperature measurements to take from which the average is calculated.
        This helps to cancel out slight fluctuations.

        Parameters
        ----------
        n_samples : int
            Number of samples to take which are averaged to calc the temp
        """
        res = self.query(self.create_command('S', n_samples))
        if res in self.ERROR_CODES:
            logging.error(f"{self.ERROR_CODES[res]} when setting the number of samples")
            self.reset_buffers()
        elif int(res) != n_samples:
             logging.error(f"Set number of samples {int(res)} does not equal target of {n_samples}")
        else:
            logging.debug(f"Set number of samples to {n_samples}")

    def set_delay(self, delay):
        """
        Set the delay in milliseconds between two consecutive Serial commands.
        This allows to limit the readout rate which is approx 1/delay for large delays.

        Parameters
        ----------
        delay : int
            Delay in milliseconds
        """
        res = self.query(self.create_command('D', delay))
        if res in self.ERROR_CODES:
            logging.error(f"{self.ERROR_CODES[res]} when setting the delay between consecutive commands")
            self.reset_buffers()
        elif int(res) != delay:
             logging.error(f"Set delay {int(res)} does not equal target of {delay}")
        else:
            logging.debug(f"Set delay to {delay} ms")