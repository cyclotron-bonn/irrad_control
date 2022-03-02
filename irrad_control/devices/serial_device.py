import serial
from time import sleep

class SerialDevice(object):

    WRITE_TERMINATION = '\n'
    READ_TERMINATION = '\n'

    def __init__(self, port, baudrate=9600, timeout=1):
        self._intf = serial.Serial(port=port, baudrate=baudrate, timeout=timeout) 
        sleep(0.5)  # Allow connections to be made
    
    def reset_buffers(self):
        """
        Sleep for a bit and reset buffers to reset serial
        """
        sleep(0.5)
        self._intf.reset_input_buffer()
        self._intf.reset_output_buffer()

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

        self._intf.write(msg + self.WRITE_TERMINATION.encode())

    def read(self):
        """
        Reads from serial port until self.READ_TERMINATION byte is encountered.
        This is equivalent to serial.Serial.readline() but respects timeouts

        Returns
        -------
        str
            Decoded, stripped string, read from serial port
        """
        return self._intf.read_until(self.READ_TERMINATION.encode()).decode().strip()

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
