"""
This Python Class includes all functions to control the RS-232 Interface
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

    """
    Every voltage change has to be confirmed
    """

    # Command references from protocol
    cmds = {'set_voltage': 'D1=',
            'set_delay': 'W=',
            'get_voltage': 'U1',
            'confirm_cmd': 'G1'}

    # Reply reference from protocol
    replies = {'success': 'OK',
               'fail': '????'}

    def __init__(self, port, shutdown_on_close=True, hv=30):
        """
        The init initializes a serial communication with the power supply

        Parameters
        ----------
        port: str
            Device path under which the serial communication is opened (e.g /dev/ttyUSB0)
        """
        self.hv = hv
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
            # Question: DO I need necessary to code like this. And is the self in the brackets necessary?
            voltage = self.get_voltage(self)
            if voltage != 0:
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

    # enters the command and checks it
    def write_and_check(self, cmd):
        self.write(cmd)
        reply = self.read()
        # I still have to check the argument of reply
        if reply == 'OK':
            return reply
        else:
            raise ValueError('Your Input was wrong')

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
            answer = self.write_and_check(self.cmds['set_voltage'] + self.voltage)
            # answer holds a value which tells you whether or not the write was successful
            # I still have to check the argument of answer
            if answer == 'OK':
                answer = self.write_and_check(self.cmds['confirm_cmd'])
                return answer
            else:
                raise ValueError('Writing to power supply was not successful.')

    #Turns the voltage to 5V
    def HV_on(self):
        self.set_voltage(hv)

    # Turns the voltage to zero
    def HV_off(self):
        self.set_voltage(0)

    #set dely time
    def set_delay(self, delay):
        self.write_and_check(self.cmds['set_delay'] + delay)


    #get delay time
    def get_delay(self):
        """
        Returns
        -------
        float:
            value of current delay
        """
        answer = self.write_and_check(self.cmds['set_delay'])  # answer is always a str
        return float(answer)  # But time is a number

    # get voltage
    def get_voltage(self):
        """
        Returns
        -------
        float:
        value of current delay
        """
        answer = self.write_and_check(self.cmds['get_voltage'])
        return float(answer)

    # Do we really need this fuction? ANd what should the function do?
    def increase_voltage(self, voltage):
        if voltage + self.get_voltage(self) > self.v_lim:
            raise ValueError('Voltage is to high')

    # test function not necessary anymore
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
    i.get_delay()
    i.close()
    return 0

if __name__ == '__main__':
    main()

