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
            print('success')
            logging.debug("Serial connection to Arduino temperature sensor established.")
        else:
            logging.error("No reply on serial connection to Arduino FreqCounter.")

    def get_samplingtime(self):
        """Gets the samplingtime of the Arduino"""
        
        #writes the command to the arduino
        self.interface.write(self.cmds['get_samplingtime'].encode())
        #saves the answer from the arduino
        samplingtime = float(self.interface.readline().strip())

        return samplingtime
    
    def get_frequency(self):
        """Gets the current frequency"""
        
        #writing the command to the arduino
        self.interface.write(self.cmds['get_frequency'].encode())
        #saves the answer from the arduino
        frequency = float(self.interface.readline().strip())
        
        return frequency
    
    def set_samplingtime(self, samplingtime):
        """Sets the samplingtime"""
        #sending the command of setting the samplingtime to the arduino
        self.interface.write('st{}\n'.format(samplingtime).encode())

    def test(self):
        #testing the frequency measurements
        while(1<3):
            print(self.get_frequency())
