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
    def query(self, _msg): #query
        self.interface.reset_input_buffer()
        self.interface.reset_output_buffer()
        self.interface.write(_msg)
        time.sleep(0.5)
        return self.interface.readline().decode().strip()
    
    def command(self, _cmd, reg, value=''):
        return ''.join([_cmd, str(reg), str(value)]).encode()
    
    def __init__(self, port_ = "/dev/cu.usbserial-AR0KKS1L" , baudrate_ = 9600, timeout_ = 1.):
        self.interface = serial.Serial(port=port_, baudrate=baudrate_, timeout=timeout_)
        time.sleep(2)
        check = self.query("T".encode())
        if(check == "success"):
            print("Serial and I2C connection established")
        elif (check == "noi2c"):
            logging.error("No I2C connection")
        else:
            logging.error("No Serial Connection")
            
    def read_data(self, reg):
        #transmit data to get the value from a certain register reg
        msg = self.command('R', reg)
        ans = self.query(msg)
        print(ans)
    
    def write_data(self, reg, value):
        #transmit data to set the value val of a certain register reg
        msg = self.command('W',reg,value)
        ans = self.query(msg)
        print(ans)
    
    def check_con(self):
        check = self.query("T".encode())
        if(check == "success"):
            print("Serial and I2C connection established")
        elif (check == "noi2c"):
            logging.error("No I2C connection")
        else:
            logging.error("No Serial Connection")
             