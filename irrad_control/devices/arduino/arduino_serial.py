import serial
from time import sleep

class ArduinoSerial:
    _DELIM = ':'
    _END = "\n"

    def __init__(self, port, baudrate = 115200, timeout = 1.):
        self._intf = serial.Serial(port = port, baudrate = baudrate, timeout = timeout) 
        sleep(3)
    
    def write(self, _msg):
        """resets output buffer and writes data via serial

        Args:
            _msg (any type): the data to send via serial
        """
        if isinstance(_msg, bytes):
            pass
        elif isinstance(msg, str):
            msg = msg.encode()
        else:
            msg = str(msg).encode()
        #self._intf.reset_output_buffer()
        sleep(0.3)
        self._intf.write(_msg)

    def read(self):
        """reads serial buffer until ’\n' and resets input buffer
        returns:
            encoded string of received message
        """
        msg = self._intf.read_until(b':\r\n').decode().strip(":\r\n")
        self._intf.reset_input_buffer()
        return msg

    def query(self, _msg):
        """writes a message in binary via serial to arduino and reads the answer

        Args:
            _msg (any): [what you want to send to arduino]
        
        """
        self.write(_msg)
        sleep(0.3)
        return self.read()
    
    def create_command(self, *args):
        """create a command the arduino can process
        args are seperated by sep (default is ':') ends with ':\n:

        Args:
            args (any type)
            sep (string) optional
            end (string) optional
        returns:
            encoded message in given structure
        """
        sep = self._DELIM
        end = self._END
        msg = sep.join(str(arg) for arg in args) + sep + end
        return msg.encode()