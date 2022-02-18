import serial
from time import sleep

class ArduinoSerial:
    _DELIM = ':'
    _END = '\n'

    def __init__(self, port, baudrate=115200, timeout=1):
        self._intf = serial.Serial(port=port, baudrate=baudrate, timeout=timeout) 
        sleep(2)  # Allow Arduino to reboot; serial connection resets the Arduino
    
    def write(self, msg):
        """
        Write *msg* on the serial port. If necessary, convert to string and encode

        Parameters
        ----------
        msg : str, bytes
            Message to be written on the serial port
        """
        if not isinstance(msg, bytes):
            msg = str(msg).encode()

        sleep(0.1)  # TODO: figure out if this is needed
        self._intf.write(msg)

    def read(self):
        """
        Reads from serial port until self._END byte is encountered.
        This is equivalent to serial.Serial.readline() but respects timeouts

        Returns
        -------
        str
            Decoded, stripped string, read from serial port
        """
        sleep(0.1) # TODO: figure out if this is needed
        return self._intf.read_until(self._END.encode()).decode().strip()

    def query(self, msg):
        """
        Queries a message *msg* and reads the answer

        Parameters
        ----------
        msg : str, bytes
            Message to be queried

        Returns
        -------
        str
            Decoded, stripped string, read from serial port
        """
        self.write(msg)
        return self.read()
    
    def create_command(self, *args):
        """
        Create command string according to specified format.
        Arguments to this function are formatted and separated using self._DELIM
        
        Examples:
        
        self.create_command('W', 0x03, 0xFF) -> 'W:3:255:\n'
        self.create_command('R', 0x03) -> 'R:3:\n'

        Returns
        -------
        str
            Formatted command string
        """
        return f'{self._DELIM.join(str(a) for a in args)}{self._DELIM}{self._END}'.encode()
