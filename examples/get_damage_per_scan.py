# This file demonstrates how to get the primary fluence and TID for each scan.
# Furthermore, the conversion to NIEL and TID damage is shown.

import os

# Installation path
from irrad_control import package_path

# Analysis submodules
from irrad_control.analysis import utils, formulas

# Path to data file
data_file = os.path.join(package_path, '../tests/fixtures/test_irrad_w_corr.h5')

# Path to config file
config_file = os.path.join(package_path, '../tests/fixtures/test_irrad_w_corr.yaml')

# Name of the irradiation server used e.g. 'HSR' for 'Hochstromraum'
irrad_server = 'HSR'


if __name__ == '__main__':

    # Returns a tuple of (data, config)
    data, config = utils.load_irrad_data(data_file=data_file,
                                         config_file=config_file,
                                         specify_entries=['Damage'],  # Here, you can place a list of entries to load e.g. ['Beam', 'Damage', Raw', Irrad']. If None, load everything
                                  )

    # Get the config of our irrad_server; use fancy ',' extraction syntax
    server_config, = (conf for _, conf in config['server'].items() if conf['name'] == irrad_server)

    # Damage data coontains damage per scan
    damage_data = data[irrad_server]['Damage']

    # Available entries: 'timestamp', 'scan', 'scan_primary_fluence', 'scan_primary_fluence_error', 'scan_tid', 'scan_tid_error'
    print(f"Aivalable entries:\n{damage_data.dtype.names}\n")

    # Get neq fluence
    neq_fluence = damage_data['scan_primary_fluence'] * server_config['daq']['kappa']['nominal']
    neq_fluence_error = ((server_config['daq']['kappa']['nominal'] * damage_data['scan_primary_fluence_error'])**2 + (damage_data['scan_primary_fluence'] * server_config['daq']['kappa']['sigma'])**2)**.5

    # Print damage per scan
    print("Scan\t | \t NEQ fluence / cm²\t | TID / Mrad\n")
    for i in range(len(neq_fluence)):
        print(f"{damage_data['scan'][i]}\t | \t {neq_fluence[i]:.2E}+-{neq_fluence_error[i]:.2E} | \t {damage_data['scan_tid'][i]:.1f}+-{damage_data['scan_tid_error'][i]:.1f}")

