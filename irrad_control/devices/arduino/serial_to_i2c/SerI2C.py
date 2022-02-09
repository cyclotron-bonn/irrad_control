#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Feb  4 12:50:28 2022

@author: belaknopp
"""

import time
import serial
import logging

class SerI2C:
    _DELIM = ':'
    def __init__(self, port= "/dev/cu.usbserial-AR0KKS1L" , address = 0x20, baudrate_ = 115200, timeout_ = 1.):
        """
        establish serial communication at given port and set i2c device address on arduino
        """
        self.interface = serial.Serial(port=port, baudrate=baudrate_, timeout=timeout_)
        time.sleep(2)
        cmd = self._cre_cmd('A',0, 32)
        self._query(cmd)
        # self.check_serial_con()
        # self.check_i2c_con()

    def _query(self, _msg):
        """
        writes a given message via serial, waits some time for answer
        and then reads it
        """
        self.interface.reset_input_buffer()
        self.interface.reset_output_buffer()
        self.interface.write(_msg)
        time.sleep(0.1)
        return self.interface.readline().decode().strip()
    
    def _cre_cmd(self, _cmd, reg, data=''):
        """
        creates a command to be written to arduino
        commands have structure: '<what to do>:<register>:<value>\n'
        """
        return ''.join([_cmd, self._DELIM,str(reg),self._DELIM, str(data)]).encode()

    def read_data(self, reg):
        """
        reads data from a given register
        """
        #transmit data to get the value from a certain register reg
        msg = self._cre_cmd('R', reg)
        ans = self._query(msg)
        return int(ans)
    
    def write_data(self, reg, data):
        """
        writes data to a given register
        """
        #transmit data to set the value val of a certain register reg
        msg = self._cre_cmd('W', reg, data)
        self._query(msg)
    
    def check_i2c_con(self):
        """
        checks if the i2c connection is functioning
        """
        cmd = self._cre_cmd('T',0)
        check = int(self._query("T".encode()))
        if check != 0:
            raise RuntimeError("I2C connection to bus device unsuccessful")
