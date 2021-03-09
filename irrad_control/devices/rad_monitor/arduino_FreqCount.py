import serial
import logging
import time

logging.getLogger().setLevel('INFO')


def _check_cmd_fail(func):
    
    def wrapper(self, samplingtime=None):
        
        res = func(self) if samplingtime is None else func(self, samplingtime)
        
        if res == -1:
            raise ValueError('Method {} failed with return value -1'.format(func.__name__))
        
        return res
    
    return wrapper


class ArduinoFreqCount(object):
    """Class to read from Arduino temperature sensor setup"""

    # Command references
    cmds = {'get_frequency': 'gf',
            'get_samplingtime': 'gt',
            'get_counts': 'gc',
            'set_samplingtime': 'st{}',
            'failure_cmd': 'fh'}
    

    def __init__(self, port="/dev/ttyACM0", baudrate=9600, timeout=5):

        #super() helps with multiple inheritage
        super(ArduinoFreqCount, self).__init__()

        # Make nice serial interface
        self.interface = serial.Serial(port=port, baudrate=baudrate, timeout=timeout)
        time.sleep(2)  # Sleep to allow Arduino to reboot caused by serial connection

        # Check connection by writing invalid data and receiving answer
        self.interface.write(self.cmds['failure_cmd'].encode())
        test_res = int(self.interface.readline().strip())
        
        if test_res == -1:
            logging.debug("Serial connection to Arduino temperature sensor established.")
        else:
            logging.error("No reply on serial connection to Arduino FreqCounter.")
            
    def write_and_read(self, msg):
        self.interface.reset_input_buffer()
        self.interface.reset_output_buffer()
        self.interface.write(msg.encode())
        return self.interface.readline().strip()
    
    @_check_cmd_fail
    def get_samplingtime(self):
        """Gets the samplingtime of the Arduino"""
        return int(self.write_and_read(self.cmds['get_samplingtime']))
        #writes the command to the arduino
        #self.interface.write(self.cmds['get_samplingtime'].encode())
        # read the answer from the arduino
        #return int(self.interface.readline().strip())
    
    @_check_cmd_fail
    def get_frequency(self):
        """Gets the current frequency"""
        
        #writing the command to the arduino
        #self.interface.write(self.cmds['get_frequency'].encode())
        # read the answer from the arduino
        try:
            #a = self.interface.readline().strip()
            return int(self.write_and_read(self.cmds['get_frequency']))
        except ValueError:
            print(a)
    
    @_check_cmd_fail
    def get_counts(self):
        """Gets the current frequency"""
        
        #writing the command to the arduino
        #self.interface.write(self.cmds['get_counts'].encode())
        # read the answer from the arduino
        return int(self.write_and_read(self.cmds['get_counts']))
    
    @_check_cmd_fail
    def set_samplingtime(self, samplingtime):
        """Sets the samplingtime"""
        if samplingtime < 0:
            raise ValueError('Sampling time must be positive integer')
        #sending the command of setting the samplingtime to the arduino
        self.write_and_read(self.cmds['set_samplingtime'].format(int(samplingtime)))
        
    def test_serial_connection(self):
        self.interface.write('t'.encode())
        return self.interface.readline().strip()

    def continous_read(self, prop='frequency'):
        #testing the frequency measurements
        read_func = self.get_frequency if prop == 'frequency' else self.get_counts
        try:
            while True:
                logging.info('{} Hz'.format(read_func()))
        except KeyboardInterrupt:
            pass
