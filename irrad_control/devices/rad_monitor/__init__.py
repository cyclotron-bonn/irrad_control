from irrad_control.utils.tools import location, load_yaml, make_path

RAD_MONITOR_CONFIG = load_yaml(make_path(location(__file__), "rad_monitor_config.yaml"))
