# This file demonstrates how to get the 2D damage distribution on the scan area as well as the DUT.
# Furthermore, the conversion to NIEL and TID damage is shown.

import os

# Installation path
from irrad_control import package_path

# Analysis submodules
from irrad_control.analysis import fluence, utils, formulas

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
                                         specify_entries=['Beam', 'Scan', 'Irrad'],  # Here, you can place a list of entries to load e.g. ['Beam', 'Damage', Raw', Irrad']. If None, load everything
                                  )

    # Get the config of our irrad_server; use fancy ',' extraction syntax
    server_config, = (conf for serv, conf in config['server'].items() if conf['name'] == irrad_server)
    
    # Generate the primary fluence distribution from the data
    # Returns tuple of (fluence_map, error_map, bin_centers_x, bin_centers_y)
    fluence_map, error_map, bin_c_x, bin_c_y = fluence.generate_fluence_map(beam_data=data[irrad_server]['Beam'],
                                                                            scan_data=data[irrad_server]['Scan'],
                                                                            irrad_data=data[irrad_server]['Irrad'],
                                                                            bins=(100, 100))

    # Print 2D primary fluence (e.g. proton fluence) map
    print(f"Proton fluence map [p/cm²] ({fluence_map.shape}):\n\n{fluence_map}")

    # Convert to NEQ fluence and error via Gaussian error prop.
    neq_map = fluence_map * server_config['daq']['kappa']['nominal']
    neq_error_map = ((server_config['daq']['kappa']['nominal'] * error_map)**2 + (neq_map * server_config['daq']['kappa']['sigma'])**2)**.5

    # Print 2D NEQ fluence map
    print(f"NEQ fluence map [neq/cm²] ({neq_map.shape}):\n\n{neq_map}")

    # Convert to TID and error via Gaussian error prop.
    tid_map = formulas.tid_per_scan(primary_fluence=fluence_map, stopping_power=server_config['daq']['stopping_power'])
    tid_error_map = formulas.tid_per_scan(primary_fluence=error_map, stopping_power=server_config['daq']['stopping_power'])

    # Print 2D NEQ fluence map
    print(f"TID map [Mrad] ({tid_map.shape}):\n\n{tid_map}")
