import serial
import logging
import time


class ArduinoFreqCount(object):
    """Class to read from Arduino temperature sensor setup"""

    # Command references
    cmds = {'get_frequency': 'gf',
            'get_samplingtime': 'gt',
            'set_samplingtime': 'st{}',
            'failure_cmd': 'fh'}
    

    #I guess still need to write get_raw_frequency and get samplingtime
    def __init__(self, port="/dev/ttyACM0", baudrate=9600, timeout=5):

        #super() hilft bei mehrfach vererbung
        super(ArduinoFreqCount, self).__init__()

        # Make nice serial interface
        self.interface = serial.Serial(port=port, baudrate=baudrate, timeout=timeout)
        time.sleep(2)  # Sleep to allow Arduino to reboot caused by serial connection

        # Check connection by writing invalid data and receiving answer
        # Could this be any invalid data?
        self.interface.write(self.cmds['failure_cmd'].encode())
        test_res = int(self.interface.readline().strip())
        
        if test_res == -1:
            print('yes')
            logging.debug("Serial connection to Arduino temperature sensor established.")
        else:
            logging.error("No reply on serial connection to Arduino FreqCounter.")

    def get_samplingtime(self):
        """Gets the samplingtime of the Arduino"""
        cmd = self.cmds['get_samplingtime']
        self.interface.write(cmd.encode())
        samplingtime = float(self.interface.readline().strip())
        
        print(samplingtime)

        return samplingtime
    
    def get_frequency(self):
        """Gets the current frequency"""
        cmd = self.cmds['get_frequency']
        self.interface.write(cmd.encode())
        frequency = float(self.interface.readline().strip())
        print(frequency)
        return frequency
    
    def set_samplingtime(self, samplingtime):
        """Sets the samplingtime"""
        #cmd = self.cmds['set_samplingtime'.format(samplingtime)]
        self.interface.write('st{}\n'.format(samplingtime).encode())


