from irrad_control.devices.arduino import ardser
from time import sleep

class ArdRO(ardser.ArdSer):
    def __init__(self, port, address=0x20, baudrate=115200, timeout = 1.):
        super().__init__(port=port, baudrate=baudrate, timeout=timeout)
        self.set_i2c_address(address)

    def read_data(self, reg):
        """
        reads data from a given register
        """
        #transmit data to get the value from a certain register reg
        msg = self.create_command('R', reg)
        ans = self.query(msg)
        return int(ans)

    def write_data(self, reg, data):
        """
        writes data to a given register
        """
        #transmit data to set the value val of a certain register reg
        msg = self.create_command('W', reg, data)
        self.query(msg)
    
    def check_i2c_con(self):
        """checks the i2c connection from arduino to bus device
        Raises:
            RuntimeError: the arduino should return a 0 if the test was successful,
                          anything else is an error
        """
        cmd = self.create_command('T')
        check = int(self.query(cmd))
        if check != 0:
            print(check)
            raise RuntimeError("I2C connection to bus device unsuccessful")
    
    def set_i2c_address(self, add):
        """sets a new i2c address

        Args:
            add (int): new address
        """
        cmd = self.create_command("A", add)
        self.query(cmd)