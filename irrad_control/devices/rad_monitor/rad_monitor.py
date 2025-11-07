import logging
from time import sleep
from irrad_control.devices.arduino.freq_counter.arduino_freq_counter import ArduinoFreqCounter
from irrad_control.devices.power_supply.iseg_nhq_x0xx import IsegNHQx0xx
from irrad_control.devices.rad_monitor import RAD_MONITOR_CONFIG


class RadiationMonitor(ArduinoFreqCounter):

    def __init__(self, counter_type, counter_port,  hv_port):
        
        if counter_type not in RAD_MONITOR_CONFIG:
            raise KeyError(f'No configuration defined for counter type "{counter_type}"')

        super().__init__(port=counter_port)

        self.config = RAD_MONITOR_CONFIG[counter_type]

        # Initialize high voltage power supply
        self.hv = IsegNHQx0xx(port=hv_port, n_channel=2, high_voltage=self.config['high_voltage'])

        # Set correct HV supply parameters
        self.hv.channel = self.config['hv_channel']
        self.hv.ramp_speed = self.config['ramp_speed']
        self.hv.autostart = True  # Automatically start voltage change when new voltage is set

        # Gate interval in which pulses are counted in ms
        self.gate_interval = self.config['gate_interval']

    def _ramp(self, direction='up', blocking=True):

        n_seconds_to_ramp = self.hv.high_voltage // self.config['ramp_speed']
        n_seconds_to_ramp *= 2.  # Give some more time than the ramping should take

        # We are ramping up
        if direction == 'up':
            self.hv.hv_on()
            
            def criteria(volt):
                return volt < self.hv.high_voltage - 1
            
            logging.info(f"Ramping voltage up to {self.hv.high_voltage} V...")
        # We are ramping down
        else:
            self.hv.hv_off()
            
            def criteria(volt):
                # Outut sometimes remains 1 V when shutting down
                return volt > 1
            
            logging.info("Ramping voltage down to 0 V...")

        if blocking:

            while criteria(self.hv.voltage) and n_seconds_to_ramp > 0:
                sleep(1)
                logging.debug(f"Ramping HV to {self.hv.high_voltage if direction == 'up' else 0} V (Current value: {self.hv.voltage} V)")
                n_seconds_to_ramp -= 1

            if n_seconds_to_ramp < 0:
                logging.warning(f"Ramping {direction} voltage resulted in output voltage of {self.hv.voltage} V, ecpected is {self.hv.high_voltage if direction == 'up' else 0} V")
            else:
                logging.info("Ramping voltage completed")

    def ramp_up(self):
        self._ramp(direction='up')

    def ramp_down(self):
        self._ramp(direction='down')

    def get_dose_rate(self, return_frequency=False):
        freq = self.frequency
        res = self.config['dose_rate_calibration'] * freq
        return (res, freq) if return_frequency else res

    def shutdown(self):
        # Always ramp down on shutdown
        self._ramp(direction='down', blocking=False)
