"""
This Python Class includes all functions to control the RS-232 Interface
"""

import os
import serial
import sys
import logging


class IsegHVPS(object):

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
            'get_delay' : 'W',
            'confirm_cmd': 'G1'}

    # Reply reference from protocol
    fail_cmd = '????'

    def __init__(self, port='/dev/ttyUSB0', shutdown_on_close=True, hv=30):
        """
        The init initializes a serial communication with the power supply

        Parameters
        ----------
        port: str
            Device path under which the serial communication is opened (e.g /dev/ttyUSB0)
        """

        if hv > self.v_lim:
            msg = "Target voltage of {} is higher then the allowed maximum voltage of {}. Setting voltage to the maximum voltage".format(hv, self.v_lim)
            logging.warning(msg)
            self.hv = self.v_lim
        else:
            # hv is equal to the main working voltage and can be changed in the brackets of the __init__ function
            self.hv = hv
        
        # The Port on the Pi is /dev/ttyUSB0
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
            #We enter the if-loop if self.shutdown_on_close == True
            voltage = self.get_voltage()
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
        answer = self.read()
        if answer != self.fail_cmd:
            return answer
        else:
            raise ValueError('Your Input was wrong')

    def _set_property(self, prop, prop_str):
        #Set the property in the HV supply
        answer = self.write_and_check(self.cmds[prop_str] + str(prop))

        if answer != self.fail_cmd:
            answer = self.write_and_check(self.cmds['confirm_cmd'])
            return answer
        else:
            raise ValueError('Cannot write {} with value {}.'.format(prop_str, prop))

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
            self._set_property(voltage, 'set_voltage')

    #Turns the voltage to hv
    def HV_on(self):
        self.set_voltage(self.hv)

    # Turns the voltage to zero
    def HV_off(self):
        self.set_voltage(0)

    #set dely time
    def set_delay(self, delay):
        self.write_and_check(self.cmds['set_delay'] + str(delay))


    #get delay time
    def get_delay(self):
        """
        Returns
        -------
        float:
            value of current delay
        """
        answer = self.write_and_check(self.cmds['get_delay'])  # answer is always a str
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

    def increase_voltage(self, voltage):
        """
        increases the voltage by your input value
        """
        if voltage + self.get_voltage() > self.v_lim:
            raise ValueError('Voltage is to high')
        else:
            return float(voltage + self.get_voltage())

    # test function not necessary anymore
    def interactive_mode(self):
        while True:
            command = input("Enter command (q for quit): ")

            if command == "q":
                break

            self.write(command)
            answer = self.read()
            logging.info(answer)
        return True

