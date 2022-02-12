from irrad_control.devices.arduino.serial_to_i2c import ArdSer

class ArdRO(ArdSer):
    def __init__(self, port, address=0x20, baudrate=115200, timeout = 1.):
        self.intf = super().__init__(port=port, baudrate=baudrate, timeout=timeout)
        cmd = self.intf.create_command('A',32)
        self.intf.query(cmd)

    def read_data(self, reg):
        """
        reads data from a given register
        """
        #transmit data to get the value from a certain register reg
        msg = self.intf.create_command('R', reg)
        ans = self.intf.query(msg)
        return int(ans)

    def write_data(self, reg, data):
        """
        writes data to a given register
        """
        #transmit data to set the value val of a certain register reg
        msg = self.intf.cre_cmd('W', reg, data)
        self.intf.query(msg)
    
    def check_i2c_con(self):
        """checks the i2c connection from arduino to bus device
        Raises:
            RuntimeError: the arduino should return a 0 if the test was successful,
                          anything else is an error
        """
        cmd = self.intf.create_command('T')
        check = int(self.intf.query(cmd))
        if check != 0:
            raise RuntimeError("I2C connection to bus device unsuccessful")
    
    def set_i2c_address(self, add):
        """sets a new i2c address

        Args:
            add (int): new address
        """
        cmd = self.intf.create_command('A', add)
        self.intf.query(cmd)