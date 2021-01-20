"""
This Python Class includes all functions to control the RS-232
"""

import os
import serial
import sys

class HighSupp(object):

    # Serial-related variables
    delay = 0
    baudrate = 9600
    bytesize = serial.EIGHTBITS
    parity = serial.PARITY_NONE
    stopbits = serial.STOPBITS_ONE
    timeout = 0.5

    # Max voltage of PSU
    v_lim = 50

    # Command references from protocol
    cmds = {'set_voltage': 'D1',
            'get_voltage': 'U1',
            'confirm_cmd': 'G1'}

    # Reply reference from protocol
    replies = {'success': 'OK',
               'fail': '????'}

    def __init__(self, port, shutdown_on_close=True):
        """
        The init initializes a serial communication with the power supply

        Parameters
        ----------
        port: str
            Device path under which the serial communication is opened (e.g /dev/ttyUSB0)
        """

        self.port = port
        self.shutdown_on_close = shutdown_on_close

        try:
            self.ser = serial.Serial(port=self.port,
                                     baudrate=self.baudrate,
                                     bytesize=self.bytesize,
                                     parity=self.parity,
                                     stopbits=self.stopbits,
                                     timeout=self.timeout)

        except serial.SerialException:
            raise ValueError("Serial port is already claimed or can not be found!")

    def __del__(self):
        self.close()

    # close serial port
    def close(self):
        if self.shutdown_on_close:
            if self.get_voltage() != 0:
                self.set_voltage(0)
        self.ser.close()

    # write command character-wise to device
    def write(self, command):
        for c in command + "\r\n":
            self.ser.write(bytes(c, "utf-8"))
            echo = self.ser.read(1)

    # read answer from device
    def read(self):
        return self.ser.readline().decode("utf-8").replace("\r\n", "")

    def write_and_check(self, cmd):

        self.write(cmd)
        reply = self.read()

        # TODO: check that the reply is ok
        # if reply == ...
        # elif reply == fail

        return reply

    # set voltage
    def set_voltage(self, voltage):
        """
        Parameters
        ----------
        voltage: int, float

        """

        if voltage > self.v_lim:
            raise ValueError('Voltage is too high! Max. voltage is {} V'.format(self.v_lim))
        else:
            self.write('D1={}'.format(voltage))
            answer = self.read()  # answer holds a value which tells you whether or not the write was successful
            if answer == 'OK':
                Y = 'G1'
                self.write(Y)
                answer = self.read()
                return answer
            else:
                raise ValueError('Writing to power supply was not successful.')

    def HV_on(self):
        self.set_voltage(5)
        #on = '5'
        #answer = self.write_and_check('D1=' + on)
        # self.write('D1=' + on)
        # answer = self.read()
        # answer = self.write_and_check(self.cmds['confirm_cmd'])
        # Y ='G1'
        # self.write(Y)
        # answer = self.read()

    def HV_off(self):
        off = '0'
        self.write_and_check('D1=' + off)
        # self.write('D1=' + off)
        # answer = self.read()
        Y ='G1'
        answer = self.write_and_check(self.cmds['confirm_cmd'])
        #self.write(Y)
        #answer = self.read()

    #set dely time
    def set_delay(self, delay):
        #sollte eher W=*** sein
        self.write('W=' + delay)
        answer = self.read()

    #get delay time
    def get_delay(self, answer):
        """
        Returns
        -------
        float:
            value of current delay
        """
        X = 'W'
        self.write(X)
        answer = self.read()  # answer is always a str
        print(answer)
        return float(answer)  # But time is a number

    # get voltage
    def get_voltage(self, answer):
        Z = 'U1'
        self.write(Z)
        answer = self.read()
        return float(answer)

    def increase_voltage(self, voltage):

        if voltage + self.get_voltage() > self.v_lim:
            raise ValueError()

    # test function
    def interactive_mode(self):
        while True:
            command = input("Enter command (q for quit): ")

            if command == "q":
                break

            self.write(command)
            answer = self.read()
            print(answer, 'here')

        return True

def main():

    i = HV(sys.argv[1])
    i.HV_on()
    #i.HV_off()
    i.set_voltage(20)
    #i.get_voltage('answer')
    #i.set_delay('10')
    i.get_delay('answer')
    i.close()
    return 0

if __name__ == '__main__':
    main()

