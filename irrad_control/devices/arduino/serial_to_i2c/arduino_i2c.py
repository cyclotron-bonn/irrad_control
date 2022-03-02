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
    RETURN_CODES = {
        '0': "Success",
        '1': "Rata too long to fit in transmit buffer",
        '2': "Received NACK on transmit of address",
        '3': "Received NACK on transmit of data",
        '4': "Other error",
        'error': "Serial transmission error"  # Custom return code for unsuccesful serial communciation
    }

    @property
    def i2c_address(self):
        return self._i2c_addr

    @i2c_address.setter
    def i2c_address(self, addr):
        """
        Set the I2C address of the device on the bus to talk to

        Parameters
        ----------
        addr : int
            I2C address

        Raises
        ------
        I2CTransmissionError
            If the set address on the Arduino does not match with what has been sent
        """
        return_address = int(self.query(self.create_command(self.CMDS['address'], addr)))
        if return_address != addr:
            raise I2CTransmissionError(f"I2C address could not be set to {addr}. Got {return_address} instead.")
        self._i2c_addr = return_address

    def __init__(self, port, address=0x20, baudrate=115200, timeout=1):
        super().__init__(port=port, baudrate=baudrate, timeout=timeout)
        
        self._i2c_addr = None

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

        if return_code not in self.RETURN_CODES:
            raise NotImplementedError(f"Unknown return code {return_code}")

        if return_code != '0':
            if return_code == 'error':
                self.reset_buffers()  # Serial error, just reset buffers
            else:
                raise I2CTransmissionError(self.RETURN_CODES[return_code])

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
        self.write(self.create_command(self.CMDS['read'], reg))
        return_code = self.read()
        reg_data = self.read()
        self._check_return_code(return_code=return_code)
        return int(reg_data)

    def write_register(self, reg, data):
        """
        Write *data* to register *reg*

        Parameters
        ----------
        reg : _type_
            _description_
        data : _type_
            _description_
        """
        return_code = self.query(self.create_command(self.CMDS['write'], reg, data))
        self._check_return_code(return_code=return_code)
    
    def check_i2c_connection(self):
        """
        Checks the i2c connection from arduino to bus device
        """
        return_code = self.query(self.create_command(self.CMDS['check']))
        self._check_return_code(return_code=return_code)
