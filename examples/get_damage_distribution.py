# This file demonstrates how to get the 2D damage distribution on the scan area as well as the DUT.
# Furthermore, the conversion to NIEL and TID damage is shown.

import os

# Installation path
from irrad_control import package_path

# Analysis submodules
from irrad_control.analysis import fluence, utils, formulas

# Path to data file
data_file = os.path.join(package_path, "../tests/fixtures/test_irrad_w_corr.h5")

# Path to config file
config_file = os.path.join(package_path, "../tests/fixtures/test_irrad_w_corr.yaml")

# Name of the irradiation server used e.g. 'HSR' for 'Hochstromraum'
irrad_server = "HSR"


if __name__ == "__main__":
    # Returns a tuple of (data, config)
    data, config = utils.load_irrad_data(
        data_file=data_file,
        config_file=config_file,
        specify_entries=[
            "Beam",
            "Scan",
            "Irrad",
        ],  # Here, you can place a list of entries to load e.g. ['Beam', 'Damage', Raw', Irrad']. If None, load everything
    )

    # Get the config of our irrad_server; use fancy ',' extraction syntax
    (server_config,) = (conf for serv, conf in config["server"].items() if conf["name"] == irrad_server)

    ##############################################################################################################
    #            Generate fluence distribution on scan area and extract the DUT region from it                   #
    ##############################################################################################################

    # Generate the primary fluence distribution of scan area from the data
    # Returns tuple of (fluence_map, error_map, bin_centers_x, bin_centers_y)
    fluence_map, error_map, bin_c_x, bin_c_y = fluence.generate_fluence_map(
        beam_data=data[irrad_server]["Beam"],
        scan_data=data[irrad_server]["Scan"],
        irrad_data=data[irrad_server]["Irrad"],
        bins=(100, 100),
    )

    # Extract DUT map
    fluence_map_DUT, bin_c_x_DUT, bin_c_y_DUT = fluence.extract_dut_map(
        fluence_map=fluence_map,
        map_bin_centers_x=bin_c_x,
        map_bin_centers_y=bin_c_y,
        irrad_data=data[irrad_server]["Irrad"],
    )

    # Extract respective dut error map
    error_map_DUT, _, _ = fluence.extract_dut_map(
        fluence_map=error_map,
        map_bin_centers_x=bin_c_x,
        map_bin_centers_y=bin_c_y,
        irrad_data=data[irrad_server]["Irrad"],
    )

    ##############################################################################################################
    #           Calculate the NEQ and TID distributions and their errors from the DUT maps                       #
    ##############################################################################################################

    # Convert to NEQ fluence and error via Gaussian error prop.
    neq_map_DUT = fluence_map_DUT * server_config["daq"]["kappa"]["nominal"]
    neq_error_map_DUT = (
        (server_config["daq"]["kappa"]["nominal"] * error_map_DUT) ** 2
        + (fluence_map_DUT * server_config["daq"]["kappa"]["sigma"]) ** 2
    ) ** 0.5

    # Convert to TID and error via Gaussian error prop.
    tid_map_DUT = formulas.tid_per_scan(
        primary_fluence=fluence_map_DUT, stopping_power=server_config["daq"]["stopping_power"]
    )
    tid_error_map_DUT = formulas.tid_per_scan(
        primary_fluence=error_map_DUT, stopping_power=server_config["daq"]["stopping_power"]
    )

    ##############################################################################################################
    #                                     Print the different results                                            #
    ##############################################################################################################

    # Print 2D primary fluence (e.g. proton fluence) map on scan area
    print(f"Proton fluence map on scan area [p/cm²] (bins={fluence_map.shape}):\n\n{fluence_map}\n\n")

    # Print 2D NEQ fluence map on DUT
    print(
        f"NEQ fluence map on DUT [neq/cm²] (bins={neq_map_DUT.shape}, mean={neq_map_DUT.mean():.2E}):\n\n{neq_map_DUT}\n\n"
    )

    # Print 2D TID map on DUT
    print(f"TID map on DUT [Mrad] (bins={tid_map_DUT.shape}, mean={tid_map_DUT.mean():.2E}):\n\n{tid_map_DUT}\n\n")
