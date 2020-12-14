# Imports
import os
import yaml

# Paths
package_path = os.path.dirname(__file__)
config_path = os.path.join(package_path, 'config')
xy_stage_config_yaml = os.path.join(package_path, 'devices/stage/xy_stage_config.yaml')
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

with open(os.path.join(config_path, 'axis_config.yaml'), 'r') as _ac:
    axis_config = yaml.safe_load(_ac)

# Keep track of xy stage travel and known positions
if not os.path.isfile(xy_stage_config_yaml):
    # Open xy stats template and safe a copy
    with open(os.path.join(config_path, 'xy_stage_config.yaml'), 'r') as _xys_l:
        _xy_stage_config_tmp = yaml.safe_load(_xys_l)

    with open(xy_stage_config_yaml, 'w') as _xys_s:
        yaml.safe_dump(_xy_stage_config_tmp, _xys_s)

with open(os.path.join(package_path, 'devices/stage/xy_stage_config.yaml'), 'r') as _xys:
    xy_stage_config = yaml.safe_load(_xys)
