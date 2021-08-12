import logging

# Package imports
import irrad_control.devices.ic.ADS1256.ADS1256_definitions as ADS1256_defs
import irrad_control.devices.ic.ADS1256.pipyadc as pipyadc


class ADCBoard(object):

    drates = dict([(30000, ADS1256_defs.DRATE_30000),
                   (15000, ADS1256_defs.DRATE_15000),
                   (7500, ADS1256_defs.DRATE_7500),
                   (3750, ADS1256_defs.DRATE_3750),
                   (2000, ADS1256_defs.DRATE_2000),
                   (1000, ADS1256_defs.DRATE_1000),
                   (500, ADS1256_defs.DRATE_500),
                   (100, ADS1256_defs.DRATE_100),
                   (60, ADS1256_defs.DRATE_60),
                   (50, ADS1256_defs.DRATE_50),
                   (30, ADS1256_defs.DRATE_30),
                   (25, ADS1256_defs.DRATE_25),
                   (15, ADS1256_defs.DRATE_15),
                   (10, ADS1256_defs.DRATE_10),
                   (5, ADS1256_defs.DRATE_5),
                   (2.5, ADS1256_defs.DRATE_2_5)])

    @property
    def drate(self):
        hw_drate = self.adc.drate
        decimal_drate = [k for k, v in self.drates.items() if v == hw_drate]
        return decimal_drate[0]

    @drate.setter
    def drate(self, val):
        if val in self.drates:
            self.adc.drate = self.drates[val]
        else:
            msg = "{} not in available data rates: {}".format(val, ', '.join(str(k) for k in self.drates))
            msg += " No changes applied."
            logging.warning(msg)

    def __init__(self):

        # Initialize ADS1256
        self.adc = pipyadc.ADS1256()

        # Self calibrate
        self.adc.cal_self()

        # Define (positive) input pins
        self.input_pins = (ADS1256_defs.POS_AIN0, ADS1256_defs.POS_AIN1,
                           ADS1256_defs.POS_AIN2, ADS1256_defs.POS_AIN3,
                           ADS1256_defs.POS_AIN4, ADS1256_defs.POS_AIN5,
                           ADS1256_defs.POS_AIN6, ADS1256_defs.POS_AIN7)

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
