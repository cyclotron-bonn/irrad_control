import tables as tb

# Package imports
from irrad_control.utils.tools import load_yaml


def load_irrad_data(data_file, config_file, specify_entries=None, substract_raw_offset=True):
    """
    Function that reads the output files of an irradiation and returns generated data and configuration

    Parameters
    ----------
    data_file: str
        Path to the data file of respective irradiation
    config_file: str
        Path to the config file of respective irradiation
    specify_entries: list, str, None
        Name or iterable of names of entries to load. I None, all entries are loaded
    substract_raw_offset: bool
        Whether to subtract the offset from the raw data

    Returns
    -------
    tuple: (data, config)
    """

    # Container for loaded irrad data
    irrad_data = {}

    # Open config file
    irrad_config = load_yaml(config_file)

    # Check if we only want to load one field or all
    entries_to_load = [specify_entries] if isinstance(specify_entries, str) else specify_entries

    # Loop over DAQ servers and load data
    for server in irrad_config['server']:

        # Open actual HDF5 file
        with tb.open_file(data_file) as dfile:

            # Extract respective servers data
            server_name = irrad_config['server'][server]['name']
            server_data = dfile.root[server_name]
            available_nodes = tuple(server_data._v_children.keys())
            entries_to_load = available_nodes if entries_to_load is None else entries_to_load

            # Hold server data in dict
            irrad_data[server_name] = {}

            # Read entries
            for entry in entries_to_load:
                try:
                    irrad_data[server_name][entry] = server_data[entry].read()
                except IndexError:
                    raise IndexError("No child node with name '{}' exists. Existing children: {}".format(entry, ', '.join(available_nodes)))

            # Subtract offsets of raw data
            if substract_raw_offset and all(e in irrad_data[server_name] for e in ('Raw', 'RawOffset')):
                for dname in irrad_data[server_name]['RawOffset'].dtype.names:
                    if dname != 'timestamp':
                        # Substract latest offset
                        irrad_data[server_name]['Raw'][dname] -= irrad_data[server_name]['RawOffset'][-1][dname]

    return irrad_data, irrad_config
