from irrad_control.utils.tools import location, load_yaml, make_path

DEVICES_CONFIG = load_yaml(make_path(location(__file__), 'devices_config.yaml'))
