import tables as tb
import numpy as np
import collections.abc

# Package imports
from irrad_control.utils.tools import load_yaml


def update_dict(d, u):
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = update_dict(d.get(k, {}), v)
        else:
            d[k] = v
    return d


def load_irrad_data(data_file, config_file, specify_entries=None, subtract_raw_offset=True):
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
    subtract_raw_offset: bool
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

    # Open actual HDF5 file
    with tb.open_file(data_file, 'r') as dfile:

        # Loop over DAQ servers and load data
        for server in irrad_config['server']:

            # Extract respective servers data
            server_name = irrad_config['server'][server]['name']

            # Hold server data in dict
            irrad_data[server_name] = {}

            # Read leaves i.e. Arrays and Tables
            for leaf in dfile.walk_nodes("/", classname='Leaf'):

                # Get all the nested levels; Ignore first 2 elements since they are empty (0) and server_name (1)
                data_depth = leaf._v_pathname.split('/')[2:]

                # Skip this leaf if it belongs to a top-level node that is not specified to be read
                if entries_to_load:
                    if data_depth[0] not in entries_to_load:
                        continue

                # Make data dict with all nested levels needed
                nested_data = {}
                for i, d in enumerate(reversed(data_depth)):
                    nested_data = {d: nested_data}
                    if i == 0:
                        nested_data[d] = leaf.read()

                # Update the respective data in the return dict for this server
                update_dict(irrad_data[server_name], nested_data)

            # Subtract offsets of raw data
            if subtract_raw_offset and all(e in irrad_data[server_name] for e in ('Raw', 'RawOffset')):
                for dname in irrad_data[server_name]['RawOffset'].dtype.names:
                    if dname != 'timestamp' and len(irrad_data[server_name]['RawOffset']) > 0:
                        # Substract latest offset
                        irrad_data[server_name]['Raw'][dname] -= irrad_data[server_name]['RawOffset'][-1][dname]

    return irrad_data, irrad_config


def duration_str_from_secs(seconds, as_tuple=False):

    days = seconds / (24 * 3600)
    hours = (days % 1) * 24
    minutes = (hours % 1) * 60
    seconds = (minutes % 1) * 60
    
    # Return tuple in full days, hours, minutes and seconds
    res = tuple(int(x) for x in [days, hours, minutes, seconds])

    if as_tuple:
        return res
    else:
        return ", ".join(f"{a[0]}{a[1]}" for a in zip(res, 'dhms') if a[0]) or '0s'


def win_from_timestamps(ts_data, other_data, ts_start, ts_stop, to_secs=False):
        idx_start, idx_stop = np.searchsorted(ts_data, [ts_start, ts_stop])
        d_ts, d_ot = ts_data[idx_start:idx_stop], other_data[idx_start:idx_stop]
        if to_secs:
            d_ts = d_ts - d_ts[0]
        return d_ts, d_ot


def generate_default_summary_dict():
    return {
            'beam': {
                     'ion': None,
                     'kappa': None,
                     'energy': None,
                     'current': None,
                     'lambda': None
                    },
            'irrad': {
                     'date': None,
                     'duration': None,
                     'scan': None,
                     'fluence_ion': None,
                     'fluence_neq': None,
                     'tid': None,
                     'temp': None
                    },
            'sid': None,
            'summary_generated': False}
