import serial
import time

class ArdSer:
    _DELIM = ':'
    _END = '\n'

    def __init__(self, port, baudrate = 115200, timeout = 1.):
        self._intf = serial.Serial(port = port, baudrate = baudrate, timeout = timeout) 
        time.sleep(2)
    
    def query(self, _msg):
        """writes a message in binary via serial to arduino and reads the answer

        Args:
            _msg (encoded string (binary)): [what you want to send to arduino]
        """
        self._intf.reset_input_buffer()
        self._intf.reset_output_buffer()
        self._intf.write(_msg)
        time.sleep(0.1)
        return self._intf.readline().decode().strip()
    
    def create_command(self, arg1, arg2='', arg3=''):
        """create a command the arduino can process
        returned command has structure 'arg1:arg2:arg3:\n'

        Args:
            arg1 (any type)
            arg2 (any type) optional
            arg3 (any type) optional
        """
        return ''.join([str(arg1), self._DELIM, str(arg2), self._DELIM, str(arg3), self._DELIM, self._END]).encode()