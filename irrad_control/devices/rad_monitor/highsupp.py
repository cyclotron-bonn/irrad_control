
    delay = 0
    
    baudrate = 9600
    bytesize = serial.EIGHTBITS
    parity = serial.PARITY_NONE
    stopbits = serial.STOPBITS_ONE
    timeout = 0.5

    def __init__(self, port=None):

        self.port = port

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

    def __del__(self):
        self.close()

    # write command character-wise to device
    def write(self, command):
        for c in command + "\r\n":
            self.ser.write(bytes(c, "utf-8"))
            echo = self.ser.read(1)

    # read answer from device
    def read(self):
        return self.ser.readline().decode("utf-8").replace("\r\n", "")

    # set voltage
    def set_voltage(self, voltage):
        if voltage >= self.v_lim:
            self.close()
            #print("your voltage is to high.")
        else:
          self.write('D1=' + voltage)
          answer = self.read()
          #print(answer)
          Y ='G1'
        self.write(Y)
        answer = self.read()
        return answer

    def HV_on(self):
        on = '5'
        self.write('D1=' + on)
        answer = self.read()
        Y ='G1'
        self.write(Y)
        answer = self.read()

    def HV_off(self):
        off = '0'
        self.write('D1=' + off)
        answer = self.read()
        Y ='G1'
        self.write(Y)
        answer = self.read()

    #set dely time
    def set_delay(self, delay):
        #sollte eher W=*** sein
        self.write('W=' + delay)
        answer = self.read()

    #get delay time
    def get_delay(self, answer):
        X = 'W'
        self.write(X)
        answer = self.read()
        print(answer)
        return answer

    # get voltage
    def get_voltage(self, answer):
        Z = 'U1'
        self.write(Z)
        answer = self.read()
        return answer

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
    #i.HV_on()
    #i.HV_off()
    #i.set_voltage('20')
    #i.get_voltage('answer')
    #i.set_delay('10')
    i.get_delay('answer')
    i.close()
    return 0

if __name__ == '__main__':
    main()
