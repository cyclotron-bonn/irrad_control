import logging
from pipyadc import ADS1256
from pipyadc import ADS1256_definitions as ADS1256_defs
from pipyadc import ADS1256_default_config as ADS1256_conf


# Package imports
from irrad_control.devices import DEVICES_CONFIG


class ADCBoard(object):
    @property
    def drate(self):
        hw_drate = self.adc.drate
        (decimal_drate,) = [k for k, v in DEVICES_CONFIG["ADCBoard"]["drates"].items() if v == hw_drate]
        return decimal_drate

    @drate.setter
    def drate(self, val):
        if val in DEVICES_CONFIG["ADCBoard"]["drates"]:
            self.adc.drate = DEVICES_CONFIG["ADCBoard"]["drates"][val]
        else:
            msg = "{} not in available data rates: {}".format(
                val, ", ".join(str(k) for k in DEVICES_CONFIG["ADCBoard"]["drates"])
            )
            msg += " No changes applied."
            logging.warning(msg)

    def __init__(self):
        # Enable AUTOCAL and disable buffer
        # IMPORTANT: BUFFER_ENABLE bit needs to be DISABLED! Otherwise, voltage range only 0-3V instead of 0-5V
        ADS1256_conf.gain_flags = ADS1256_defs.GAIN_1  # 0-5V
        ADS1256_conf.status = ADS1256_defs.AUTOCAL_ENABLE  # 0x04

        # Initialize ADS1256
        self.adc = ADS1256(conf=ADS1256_conf)

        # Self calibrate
        self.adc.cal_self()

        # Define (positive) input pins
        self.input_pins = (
            ADS1256_defs.POS_AIN0,
            ADS1256_defs.POS_AIN1,
            ADS1256_defs.POS_AIN2,
            ADS1256_defs.POS_AIN3,
            ADS1256_defs.POS_AIN4,
            ADS1256_defs.POS_AIN5,
            ADS1256_defs.POS_AIN6,
            ADS1256_defs.POS_AIN7,
        )

        # Define respective ground pin
        self.gnd_pin = ADS1256_defs.NEG_AINCOM

        self._adc_channels = []

    def setup_channels(self, channels_nums):
        self._adc_channels = []

        # Assign the physical channel numbers e.g. multiplexer address
        for ch in channels_nums:
            # Single-ended versus common ground gnd
            if isinstance(ch, int):
                channel = self.input_pins[ch] | self.gnd_pin
            # Differential measurement
            else:
                a, b = ch
                channel = self.input_pins[a] | self.input_pins[b]

            # Add to channels
            self._adc_channels.append(channel)

    def read_channels(self, channel_names=None):
        result = {}
        ch_names = channel_names if channel_names is not None else list(range(len(self._adc_channels)))

        if self._adc_channels:
            raw_data = self.adc.read_sequence(self._adc_channels)

            for i, raw_d in enumerate(raw_data):
                result[ch_names[i]] = raw_d * self.adc.v_per_digit

        else:
            logging.warning("No input channels to read from are setup. Use 'setup_channels' method")

        return result

    def shutdown(self):
        self.adc.stop()
