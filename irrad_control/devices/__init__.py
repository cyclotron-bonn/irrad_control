import logging
from os.path import isfile
from irrad_control.utils.tools import location, load_yaml, make_path


DEVICES_CONFIG = load_yaml(make_path(location(__file__), 'devices_config.yaml'))


# Check if config files need to be loaded for device inits
def load_device_init_configs():
    # Loop over devices in device config dict
    for _, init in DEVICES_CONFIG.items():

        # Config is in init
        if 'config' in init['init']:

            # Check if config is already a dict or needs to be loaded from yaml
            if not isinstance(init['init']['config'], dict):
                # Check if config file exists and overwrite, otherwise config is None
                if isfile(init['init']['config']):
                    try:
                        config_file = str(init['init']['config'])
                        init['init']['config'] = load_yaml(config_file)
                        init['init']['config']['filename'] = config_file
                    except FileNotFoundError:
                        init['init']['config'] = None
                        logging.warning("Config file {} could not be found!".format(config_file))

load_device_init_configs()
