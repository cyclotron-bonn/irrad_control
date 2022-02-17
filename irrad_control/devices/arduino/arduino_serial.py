import serial
from time import sleep

class ArduinoSerial:
    _DELIM = ':'
    _END = '\n'

    def __init__(self, port, baudrate=115200, timeout=1):
        self._intf = serial.Serial(port=port, baudrate=baudrate, timeout=timeout) 
        sleep(2)  # Allow Arduino to reboot; serial connection resets the Arduino
    
    def write(self, msg):
        """resets output buffer and writes data via serial

        Args:
            msg (any type): the data to send via serial
        """
        if not isinstance(msg, bytes):
            msg = str(msg).encode()

        sleep(0.1)  # TODO: figure out if this is needed
        self._intf.write(msg)

    def read(self):
        """reads serial buffer until ':\r\n'
        returns:
            encoded string of received message
        """
        sleep(0.1) # TODO: figure out if this is needed
        return self._intf.read_until(b':\r\n').decode().strip(":\r\n")  # TODO: Stop having separator before \n and after

    def query(self, msg):
        """writes a message in binary via serial to arduino and reads the answer

        Args:
            _msg (any): [what you want to send to arduino]
        returns:
            answer (see <read()>)
        
        """
        self.write(msg)
        return self.read()
    
    def create_command(self, *args):
        """create a command the arduino can process
        args are seperated by sep (default is ':') ends with ':\n:  # TODO: Stop having separator before \n and after

        Args:
            args (any type)
            sep (string) optional
            end (string) optional
        returns:
            encoded message in given structure
        """
        return f'{self._DELIM.join(str(a) for a in args)}{self._DELIM}{self._END}'.encode()
