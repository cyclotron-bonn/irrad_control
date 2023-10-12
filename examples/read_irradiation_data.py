# This file shows how to read data poduced by irrad_control
# Please check https://github.com/cyclotron-bonn/irrad_control/blob/main/irrad_control/analysis/dtype.py
# for info on the available data types for each entry.

import os

# Utility function for loading data
from irrad_control.analysis.utils import load_irrad_data
from irrad_control import package_path

# Path to data file
data_file = os.path.join(package_path, '../tests/fixtures/test_irrad_w_corr.h5')

# Path to config file
config_file = os.path.join(package_path, '../tests/fixtures/test_irrad_w_corr.yaml')

# Name of the irradiation server used e.g. 'HSR' for 'Hochstromraum'
irrad_server = 'HSR'

if __name__ == '__main__':
    
    # Returns a tuple of (data, config)
    data, config = load_irrad_data(data_file=data_file,
                                   config_file=config_file,
                                   specify_entries=None,  # Here, you can place a list of entries to load e.g. ['Beam', 'Damage', Raw', Irrad']. If None, load everything
                                  )

    # *data* is a dict with the respective irradiation servers as keys
    actual_data = data[irrad_server]

    # Available data
    print(f"Available entries: {[n for n in actual_data]}")

    # Beam-related data; numpy structured array
    beam_data = actual_data['Beam']

    # Get timestamps and beam currents
    ts_beam, current_beam = beam_data['timestamp'], beam_data['beam_current']

    # Get temperature data; temperature data can be recorded using different device therefore there is the *ArduinoNTCReadout* in the dict path
    ts_temp = actual_data['Temperature']['ArduinoNTCReadout']['timestamp']
    temp_DUT =  actual_data['Temperature']['ArduinoNTCReadout']['DUT']

    print(f"Average DUT temperature: {temp_DUT.mean():.2f} °C")
