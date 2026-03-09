# Version
__version__ = "2.5.1"

# Imports
import os
from .utils import tools

# Dirs to be checked / made
tmp_dir = "/tmp/irrad_control"
config_dir = f"{os.path.expanduser('~')}/.config/irrad_control"

# Paths
package_path = os.path.dirname(__file__)
config_path = os.path.abspath(config_dir)
tmp_path = os.path.abspath(tmp_dir)

# Files
config_file = os.path.join(config_path, "config.yaml")
pid_file = os.path.join(config_path, "irrad_control.pid")
lock_file = os.path.join(config_path, "irrad_control.lck")

# Check / make
for check_path in (tmp_path, config_path):
    if not os.path.isdir(check_path):
        os.mkdir(check_path)

# Check for config.yaml
if os.path.isfile(config_file):
    config = tools.load_yaml(path=config_file)
else:
    # Create empty config yaml
    config = {"server": {"all": {}, "default": None}, "git": None}
    tools.save_yaml(path=config_file, data=config)

if not os.path.isfile(lock_file):
    with open(lock_file, "a"):
        pass
