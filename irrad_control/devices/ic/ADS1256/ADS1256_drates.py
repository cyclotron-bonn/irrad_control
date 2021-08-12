from irrad_control.devices.ic.ADS1256.ADS1256_definitions import *
from collections import OrderedDict

# ADS1256 data rates in samples per second
ads1256_drates = OrderedDict([(30000, DRATE_30000),
                              (15000, DRATE_15000),
                              (7500, DRATE_7500),
                              (3750, DRATE_3750),
                              (2000, DRATE_2000),
                              (1000, DRATE_1000),
                              (500, DRATE_500),
                              (100, DRATE_100),
                              (60, DRATE_60),
                              (50, DRATE_50),
                              (30, DRATE_30),
                              (25, DRATE_25),
                              (15, DRATE_15),
                              (10, DRATE_10),
                              (5, DRATE_5),
                              (2.5, DRATE_2_5)])
