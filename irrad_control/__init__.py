# Imports
import os
import yaml

# Paths
package_path = os.path.dirname(__file__)
config_path = os.path.join(package_path, 'config')
tmp_dir = '/tmp/irrad_control'

# Shell script to config server
config_server_script = os.path.join(package_path, 'configure_server.sh')

# Make tmp folder to store temp files in
if not os.path.isdir(tmp_dir):
    os.mkdir(tmp_dir)

# Load network and data acquisition config
with open(os.path.join(config_path, 'network_config.yaml'), 'r') as _nc:
    network_config = yaml.safe_load(_nc)

with open(os.path.join(config_path, 'daq_config.yaml'), 'r') as _dc:
    daq_config = yaml.safe_load(_dc)
