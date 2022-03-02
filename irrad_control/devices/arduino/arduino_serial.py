from time import sleep
from irrad_control.devices.serial_device import SerialDevice


class ArduinoSerial(SerialDevice):
    
    CMD_DELIMITER = ':'

    def __init__(self, port, baudrate=115200, timeout=1):
        super().__init__(port=port, baudrate=baudrate, timeout=timeout) 
        sleep(1)  # Allow Arduino to reboot; serial connection resets the Arduino
    
    def create_command(self, *args):
        """
        Create command string according to specified format.
        Arguments to this function are formatted and separated using self._DELIM
        
        Examples:
        
        self.create_command('W', 0x03, 0xFF) -> 'W:3:255:'
        self.create_command('R', 0x03) -> 'R:3:'

        Returns
        -------
        str
            Formatted command string
        """
        return f'{self.CMD_DELIMITER.join(str(a) for a in args)}{self.CMD_DELIMITER}'.encode()
