from irrad_control.devices.arduino.arduino_serial import ArduinoSerial
import threading
import time
import logging

class ArduinoMUX(ArduinoSerial):
    CMDS = {
        'enable_channel': 'E',
        'disable_channel': 'D',
        'ping': 'P',
        'get_status': 'Q',
        'reset_char': 'R'
    }

    ERRORS = {
        'error': "An error occured"
    }

    delay = 1.0


    def __init__(self, port="/dev/ttyS0", baudrate=9600, timeout=1):
        logging.error("initiating arduino mux")
        logging.error("port={} baudrate={} timeout={}".format(port, baudrate, timeout))
        super().__init__(port=port, baudrate=baudrate, timeout=timeout)
        logging.error("super init finished")
        # start ping thread here??
        self.enable_ping = True
        self.ping_thread = threading.Thread(target = self.ping_loop)
        self.ping_thread.start()


    def ping_loop(self):
        while self.enable_ping:
            self.ping()
            time.sleep(self.delay)


    def ping(self):
        logging.error("pinging")
        self.write(self.create_command(self.CMDS['ping']))


    def _enable_channel(self, channel: int = 16):
        logging.error("called enable channel")
        logging.error("{}".format(self.create_command(self.CMDS['enable_channel'], channel)))
        self.write(self.create_command(self.CMDS['enable_channel'], channel))


    def _disable_channel(self, channel: int = 16):
        logging.error("called disable channel")
        logging.error("{}".format(self.create_command(self.CMDS['disable_channel'], channel)))
        self.write(self.create_command(self.CMDS['disable_channel'], channel))


    #@property
    def channel_states(self):
        response = self.query(self.create_command(self.CMDS['get_status']))
        response = response.split()


    def shutdown(self):
        self.enable_ping = False
        self.ping_thread.join()
