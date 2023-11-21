import logging

from threading import Thread, Event
from queue import Queue
from time import time

from irrad_control.devices.arduino.arduino_serial import ArduinoSerial


class ArduinoGPIOSwitch(ArduinoSerial):

    CMDS = {
        'ping': 'P',  # Issue a 'ping' that resets the internal counter in the firmware. If no ping is issued for a period of time, longer than the *timeout*, the GPIO pins go into the default state
        'ping_timeout': 'T',  # Timeout in seconds before which a ping has to be sent
        'gpio': 'G',  # Set or read the state of a GPIO pin
        'reset': 'R',  # Reset the GPIO pins into the default state
        'state': 'I',  # Set or get the GPIO state of multiple pins
        'default': 'X'  # Set or get the GPIO default state of pins
    }
    
    ERRORS = {
        'error': "Serial transmission error"  # Custom return code for unsuccesful serial communciation
    }


    @property
    def gpio_state(self):
        return self.query(self.create_command(self.CMDS['state']))


    @gpio_state.setter
    def gpio_state(self, state):
        """
        Sets the gpio pins of the switch to the desired state

        Parameters
        ----------
        state : dict
            Dict with pin numbers as keys and state as val e.g.

            {0:1, 1:1, 2:1, 3:0 ...} sets pins (0, 1, 2) to high and 3 to low etc.
        """
        self.write(self.create_command(self.CMDS['state'].lower(), ';'.join(f'{k}-{v}' for k, v in state.items())))


    @property
    def default_state(self):
        return self.query(self.create_command(self.CMDS['default']))
    

    @default_state.setter
    def default_state(self, state):
        """
        Sets the default state

        Parameters
        ----------
        state : dict
            Dict with pin numbers as keys and state as val e.g.

            {0:1, 1:1, 2:1, 3:0 ...} sets pins (0, 1, 2) to high and 3 to low etc
        """
        self.write(self.create_command(self.CMDS['state'].lower(), ';'.join(f'{k}-{v}' for k, v in state.items())))

    @property
    def ping_timeout(self):
        return self.query(self.create_command(self.CMDS['ping_timeout']))
    
    @ping_timeout.setter
    def ping_timeout(self, val):
        self._set_and_retrieve(cmd='ping_timeout', val=val)
        

    def __init__(self, port, ping_rate=1, ping_timeout=5, baudrate=115200, timeout=1, switch_config=None):
        super().__init__(port, baudrate, timeout)

        self._stop = Event()
        
        self._ping_rate = ping_rate
        self._ping_every = 1. / ping_rate

        self._cmd_queue = Queue()
        self._res_queue = Queue()

        self._poll_thread = Thread(target=self._poll_cmds)
        self._poll_thread.start()

        self._last_ping = None

        # Start to actually talk to the hardware
        self.ping_timeout = ping_timeout

        self.switch_config = switch_config
        if switch_config is not None:
            logging.info(f"Configuring {type(self).__name__} with config: {switch_config}")

            # Continue the initialization of the switch here by giving a config
            # ... 

    def _poll_cmds(self):
        """
        This function runs in a separate thread and checks for incoming commands.
        Additionally, it sends a ping every *self._ping_every* seconds to reset the dead man's switch timer.

        This approach only works if the commands take substantially less time than the timeout of the dead man's switch *self.ping_timout*
        which should be generally the case. If this starts to become an issue, need to reimplement using second thread or better: asyncio 
        """

        # Check if we're trying to stop; wait 10 ms for event to be set, otherwise poll for cmds
        while not self._stop.wait(1e-2):

            cmds = []

            # Check if we want to ping
            if self._last_ping is None or time() - self._last_ping > self._ping_every:
                cmds.append({'write': self.create_command(self.CMDS['ping'])})
                self._last_ping = time()

            while not self._cmd_queue.empty():
                cmds.append(self._cmd_queue.get_nowait())

            for cmd in cmds:
                if 'write' in cmd:
                    super().write(cmd['write'])
                elif 'read' in cmd:
                    res = super().read()
                    self._res_queue.put(res)
                elif 'query' in cmd:
                    res = super().query(cmd['query'])
                    self._res_queue.put(res)
                else:
                    logging.error(f"Unrecognised command signature: {cmd}")

    def write(self, msg):
         self._cmd_queue.put(dict(write=msg))

    def read(self):
        self._cmd_queue.put(dict(read=''))
        return self._res_queue.get()
    
    def query(self, msg):
        self._cmd_queue.put(dict(query=msg))
        return self._res_queue.get()
    
    def shutdown(self):
        self._stop.set()
        self._poll_thread.join()

    def gpio_pin_is_set(self, pin):
        """
        Checks if *pin* is high

        Parameters
        ----------
        pin : int
            Number of pin to check

        Returns
        -------
        state: bool
            Whether pin is high
        """
        return bool(int(self.query(self.create_command(self.CMDS['gpio'], pin))))

    def set_gpio_pin(self, pin):
        """
        Sets *pin* to high

        Parameters
        ----------
        pin : int
            Number of pin to set high
        """
        self.write(self.create_command(self.CMDS['gpio'].lower(), pin, 1))

    def unset_gpio_pin(self, pin):
        """
        Sets *pin* to low

        Parameters
        ----------
        pin : int
            Number of pin to set high
        """
        self.write(self.create_command(self.CMDS['gpio'].lower(), pin, 0))
