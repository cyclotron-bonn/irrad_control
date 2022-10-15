# Imports
import os
from .utils import tools

# Version
__version__ = '2.0.0'

# Dirs to be checked / made
tmp_dir = '/tmp/irrad_control'
config_dir = f"{os.path.expanduser('~')}/.config/irrad_control"

# Paths
package_path = os.path.dirname(__file__)
config_path = os.path.abspath(config_dir)
tmp_path = os.path.abspath(tmp_dir)
script_path = os.path.abspath(os.path.join(package_path, '../scripts'))

# Files
config_file = os.path.join(config_path, 'config.yaml')

# Check / make
for check_path in (tmp_path, config_path):
    if not os.path.isdir(check_path):
        os.mkdir(check_path)

# Check for config.yaml
if os.path.isfile(config_file):
    config = tools.load_yaml(path=config_file)
else:
    # Create empty config yaml
    config = {'server': {'all': {}, 'default': None}, 'git': None}
    tools.save_yaml(path=config_file, data=config)
