#!/usr/bin/python3

# Example for serial communication to iseg HV devices
# Needs Python 3 and python3-serial

import os
import serial
import sys



class HV:

    v_lim = 50

    def __init__(self, port=None):

        self.port = port
        self.baudrate = 9600
        self.bytesize = serial.EIGHTBITS
        self.parity = serial.PARITY_NONE
        self.stopbits = serial.STOPBITS_ONE
        self.timeout = 0.5

    # open serial port
    def open(self):
        try:
            self.ser = serial.Serial(port = self.port,
                                     baudrate = self.baudrate,
                                     bytesize = self.bytesize,
                                     parity = self.parity,
                                     stopbits = self.stopbits,
                                     timeout = self.timeout)

        except:
            raise ValueError("Serial port is already claimed or can not be found!")

    # close serial port
    def close(self):
        self.ser.close()

    # write command character-wise to device
    def write(self, command):
        for c in command + "\r\n":
            self.ser.write(bytes(c, "utf-8"))
            echo = self.ser.read(1)
    # read answer from device
    def read(self):
        return self.ser.readline().decode("utf-8").replace("\r\n", "")

    # set voltage
    def setvoltage(self):
        #i = HV(sys.argv[1])
        voltage = input('Set voltage: ')
        v_1 = int(voltage)
        if v_1 >= self.v_lim:
          print("your voltage is to high.")
          self.setvoltage()
        else:
          self.write('D1=' + voltage)
          answer = self.read()
          print(answer)
          Y ='G1'
        self.write(Y)
        answer = self.read()
        print(answer)
    def HV_on(self):
        on = '5'
        self.write('D1=' + on)
        print('D1=' + on)
        answer = self.read()
        print(answer)
        Y ='G1'
        self.write(Y)
        answer = self.read()
        print(answer)

    def HV_off(self):
        off = '0'
        self.write('D1=' + off)
        answer = self.read()
        print(answer)
        Y ='G1'
        self.write(Y)
        answer = self.read()
        print(answer)

    #set dely time
    def setdelay(self):
        delay = input('Set delay: ')
        self.write('D1=' + delay)
        answer = self.read()
        print(answer)
    #get delay time
    def getdelay(self):
        X = 'W'
        self.write(X)
        answer = self.read()
        print(answer)

    # get voltage
    def getvoltage(self):
        Z = 'U1'
        self.write(Z)
        answer = self.read()
        print(answer)

    # test function
    def test(self):
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
    i.open()
    i.setvoltage()
    #i.HV_on()
    i.getvoltage()
    #i.setdelay()
    #i.getdelay()
    i.close()
    return 0

if __name__ == '__main__':
    main()
