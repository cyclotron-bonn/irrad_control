from irrad_control.devices.arduino.freq_counter.arduino_freq_counter import ArduinoFreqCounter
from irrad_control.devices.rad_counter.iseg_hv_ps import ISEGHighVoltagePS


class RadiationCounter(ArduinoFreqCounter):

    def __init__(self, hv_port, counter_port, high_voltage, sampling_time):
        super().__init__(port=counter_port)

        # Initialize high voltage power supply
        self.hv = ISEGHighVoltagePS(port=hv_port, high_voltage=high_voltage)

        self.sampling_time = sampling_time
