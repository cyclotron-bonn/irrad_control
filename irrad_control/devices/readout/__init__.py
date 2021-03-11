from irrad_control.utils.tools import location, load_yaml, make_path

ro_board_config = load_yaml(make_path(location(__file__), 'ro_board_config.yaml'))
ro_electronics_config = load_yaml(make_path(location(__file__), 'ro_electronics_config.yaml'))
