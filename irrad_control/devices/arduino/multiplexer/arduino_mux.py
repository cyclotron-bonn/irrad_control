from threading import Event
from irrad_control.devices.arduino.arduino_serial import ArduinoSerial
from irrad_control.utils.worker import ThreadWorker


class ArduinoMUX(ArduinoSerial):
    # FIXME: this ping_loop implementation does not look threadsafe w.r.t en/disable_channel

    CMDS = {"enable_channel": "E", "disable_channel": "D", "ping": "P", "get_status": "Q", "reset_char": "R"}

    ERRORS = {"error": "An error occured"}

    delay = 1.0

    def __init__(self, port="/dev/ttyS0", baudrate=9600, timeout=1):
        super().__init__(port=port, baudrate=baudrate, timeout=timeout)

        self.stop_ping = Event()
        self.ping_thread = ThreadWorker(target=self.ping_loop)
        self.ping_thread.start()

    def ping_loop(self):
        while not self.stop_ping.wait(self.delay):
            self.ping()

    def ping(self):
        self.write(self.create_command(self.CMDS["ping"]))

    def enable_channel(self, channel: int = 16):
        self.write(self.create_command(self.CMDS["enable_channel"], channel))

    def disable_channel(self, channel: int = 16):
        self.write(self.create_command(self.CMDS["disable_channel"], channel))

    def channel_states(self):
        response = self.query(self.create_command(self.CMDS["get_status"]))
        response = response.split()

    def shutdown(self):
        self.stop_ping.set()
        self.ping_thread.join()
