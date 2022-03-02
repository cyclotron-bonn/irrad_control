from irrad_control.devices.arduino.arduino_serial import ArduinoSerial


class I2CTransmissionError(RuntimeError):
    pass


class ArduinoToI2C(ArduinoSerial):

    CMDS = {
        'write': 'W',
        'read': 'R',
        'address': 'A',
        'check': 'T'
    }
    
    # Check https://www.arduino.cc/en/Reference/WireEndTransmission
    ERRORS = {
        '0': "Success",
        '1': "Rata too long to fit in transmit buffer",
        '2': "Received NACK on transmit of address",
        '3': "Received NACK on transmit of data",
        '4': "Other error",
        'error': "Serial transmission error"  # Custom return code for unsuccesful serial communciation
    }

    @property
    def i2c_address(self):
        """
        Read back the I2C address property from the firmware.
        Uses super().query because instance query always returns i2c return code
        but i2c bus is not involved in this query

        Returns
        -------
        int
            I2C address
        """
        return int(super().query(self.create_command(self.CMDS['address'])))

    @i2c_address.setter
    def i2c_address(self, addr):
        """
        Set the I2C address of the device on the bus to talk to.
        Uses super().query because instance query always returns i2c return code
        but i2c bus is not involved in this query

        Parameters
        ----------
        addr : int
            I2C address

        Raises
        ------
        I2CTransmissionError
            If the set address on the Arduino does not match with what has been sent
        """
        super()._set_and_retrieve(cmd='address', val=int(addr), exception_=I2CTransmissionError)

    def __init__(self, port, address=0x20, baudrate=115200, timeout=1):
        super().__init__(port=port, baudrate=baudrate, timeout=timeout)
        self.i2c_address = address
        self.check_i2c_connection()

    def _check_return_code(self, return_code):
        """
        Checks the return code of the Arduino Wire endTransmission 

        Parameters
        ----------
        return_code : str
            Return code of Wire.endTransmission as dtype str

        Raises
        ------
        NotImplementedError
            return_code is unknown
        I2CTransmissionError
            dedicated error code from Wire library
        """

        if return_code != '0':
            if return_code not in self.ERRORS:
                raise NotImplementedError(f"Unknown return code {return_code}")
            else:
                if return_code == 'error':
                    self.reset_buffers()  # Serial error, just reset buffers
                else:
                    raise I2CTransmissionError(self.ERRORS[return_code])

    def query(self, msg):
        """
        Queries a message *msg* and reads the i2c return code.
        Additional data after the query can be retrive using a self.read

        Parameters
        ----------
        msg : str, bytes
            Message to be queried

        Returns
        -------
        str
            Decoded, stripped string, read from serial port
        """
        i2c_return_code = super().query(msg)
        self._check_return_code(return_code=i2c_return_code)

    def read_register(self, reg):
        """
        Read data from register *reg*

        Parameters
        ----------
        reg : int
            Register to read from

        Returns
        -------
        int
            Data read from *reg*
        """
        self.query(self.create_command(self.CMDS['read'], reg))
        return int(self.read())

    def write_register(self, reg, data):
        """
        Write *data* to register *reg*

        Parameters
        ----------
        reg : int
            Register to write to
        data : int
            Data to write to register *reg*
        """
        self.query(self.create_command(self.CMDS['write'], reg, data))
    
    def check_i2c_connection(self):
        """
        Checks the i2c connection from arduino to bus device
        """
        self.query(self.create_command(self.CMDS['check']))
