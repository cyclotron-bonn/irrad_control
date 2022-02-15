import serial
import time

class ArdSer:
    _DELIM = ':'
    _END = "\r\n"

    def __init__(self, port, baudrate = 115200, timeout = 1.):
        self._intf = serial.Serial(port = port, baudrate = baudrate, timeout = timeout) 
        time.sleep(2)
    
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
        self._intf.reset_output_buffer()
        self._intf.write(_msg.encode())

    def read(self):
        """reads serial buffer until ’\n' and resets input buffer
        returns:
            encoded string of received message
        """
        msg = self._intf.read_until('\n').decode().strip()
        self._intf.reset_input_buffer()
        return msg

    def query(self, _msg):
        """writes a message in binary via serial to arduino and reads the answer

        Args:
            _msg (any): [what you want to send to arduino]
        
        """
        self.write(_msg)
        return self.read()
    
    def create_command(self, *args, sep = self._DELIM, end = self._END):
        """create a command the arduino can process
        args are seperated by sep (default is ':') ends with ':\r\n:

        Args:
            args (any type)
            sep (string) optional
            end (string) optional
        returns:
            encoded message in given structure
        """
        msg = sep.join(str(arg) for arg in args) + sep + end
        return msg.encode()