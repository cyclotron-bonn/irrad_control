import logging
import numpy as np

from irrad_control.analysis import plotting, constants
from irrad_control.utils.utils import duration_str_from_secs


def create_beam_scan_mask(beam_data, scan_data):
    """
    

    Parameters
    ----------
    beam_data : ndarray
        Structured ndarray containing beam data accorindg to irrad_control.analysis.dtype._beam_dtype
    scan_data : ndarray
        Structured ndarray containing beam data accorindg to irrad_control.analysis.dtype._scan_dtype

    Returns
    -------
    ndarray
        bool mask indicating where scanning occured in the beam data
    """
    # Initially all false
    beam_during_scan_mask = np.zeros_like(beam_data, dtype=bool)

    speed_up_idx = 0
    
    for idx_scan in range(scan_data.shape[0]):
        current_beam_data = beam_data['timestamp'][speed_up_idx:]
        idx_row_start = np.searchsorted(current_beam_data, scan_data[idx_scan]['row_start_timestamp']) + speed_up_idx
        idx_row_stop = np.searchsorted(current_beam_data, scan_data[idx_scan]['row_stop_timestamp']) + speed_up_idx
        beam_during_scan_mask[idx_row_start:idx_row_stop] = True
        speed_up_idx = idx_row_stop
    
    return beam_during_scan_mask


def generate_scan_resolved_damage_map(scan_data, irrad_data, damage='row_primary_fluence'):
    # Create damage mape resolved in rows and scan number
    # Get number of rows
    n_rows = irrad_data['n_rows'][0]
    
    # Get indivudiually scanned rows
    individual_scan_mask = scan_data['scan'] == -1

    complete_scan_data = scan_data[~individual_scan_mask]
    individual_scan_data = scan_data[individual_scan_mask]

    # Get number of completed, individual and total scans
    n_complete_scans = complete_scan_data['scan'][-1] + 1
    n_individual_scans = len(individual_scan_data)
    n_total_scans = n_complete_scans + n_individual_scans

    # Make empty map of shape n_total_scans x n_rows
    resolved_map = np.zeros(shape=(n_rows, n_total_scans))

    logging.info(f"Generating row- and scan-resolved {damage} distribution for {n_rows} rows and {n_total_scans} scans...")

    # Loop over complete scan data and add to map
    for i in range(len(complete_scan_data)):

        row = complete_scan_data[i]['row']
        scan = complete_scan_data[i]['scan']

        # We are looking at completed scans
        # Add fluence of this row to all subsequent scans since in all following scans this fluence will already be applied in the row
        resolved_map[row, scan:] += complete_scan_data[i][damage]

    # Loop over individual row scans
    for j in range(len(individual_scan_data)):
        
        row = individual_scan_data[j]['row']
            
        resolved_map[row, j + n_complete_scans:] += individual_scan_data[j][damage]
    
    return resolved_map, n_complete_scans


def generate_scan_overview(scan_data, damage_data, irrad_data):

    overview = {}

    # Get number of rows
    n_rows = irrad_data['n_rows'][0]
    # Get indivudiually scanned rows
    individual_scan_mask = scan_data['scan'] == -1

    complete_scan_data = scan_data[~individual_scan_mask]

    # Get number of completed, individual and total scans
    n_complete_scans = complete_scan_data['scan'][-1] + 1
    n_indv_scans = np.count_nonzero(individual_scan_mask)
    hist_shape = n_rows * n_complete_scans

    # Make nice hists for rows and scans
    overview['row_hist'] = np.zeros(shape=hist_shape, dtype=[('center_timestamp', '<f8'),
                                                             ('primary_damage', '<f4'),
                                                             ('primary_damage_error', '<f4'),
                                                             ('number', '<i2')])
    
    overview['scan_hist'] = np.zeros(shape=n_complete_scans, dtype=overview['row_hist'].dtype)

    if n_indv_scans > 0:

        # Make nice hists for rows and scans
        overview['correction_hist'] = np.zeros(shape=n_rows, dtype=overview['row_hist'].dtype)
        
        overview['correction_scans'] = np.zeros(shape=n_indv_scans, dtype=overview['row_hist'].dtype)

    # Make a bunch of indices for searching
    scan_start_idx = scan_stop_idx = 0

    for scan in range(n_complete_scans):

        relevant_data = complete_scan_data[scan_start_idx:]
        scan_stop_idx = np.searchsorted(relevant_data['scan'], scan + 1)
        scan_start_idx += scan_stop_idx
        current_scan_data = relevant_data[:scan_stop_idx]

        # Where we are in the output hist
        current_offset = scan * n_rows
        for i, entry in enumerate(current_scan_data):

            cridx = current_offset + i

            # Add the current row fluence to the respective row in the histogram
            row_center_ts = (entry['row_stop_timestamp'] - entry['row_start_timestamp']) / 2 + entry['row_start_timestamp']
            
            current_row_idx = int(entry['row']) + current_offset

            overview['row_hist']['center_timestamp'][current_row_idx] = row_center_ts
            overview['row_hist']['primary_damage'][current_row_idx] += entry['row_primary_fluence']
            overview['row_hist']['primary_damage_error'][current_row_idx] = entry['row_primary_fluence_error']
            overview['row_hist']['number'][current_row_idx] = entry['row']

        # Add this to all remaining entries
        offset_future_scans = overview['row_hist']['primary_damage'][current_offset:cridx+1]

        # Add this scans resulting fluence as offset to all subsequent scans
        overview['row_hist']['primary_damage'][(scan+1)*n_rows:] = np.tile(offset_future_scans, n_complete_scans-(scan+1))
        
        # Center timestamp of this scan
        scan_start_ts = current_scan_data[0]['row_start_timestamp']
        scan_stop_ts = current_scan_data[-1]['row_stop_timestamp']
        scan_center_ts = (scan_stop_ts - scan_start_ts) / 2 + scan_start_ts
        
        # Get scan info from damage data
        current_damage_data = damage_data[np.searchsorted(damage_data['scan'], scan)]

        overview['scan_hist']['center_timestamp'][scan] = scan_center_ts
        overview['scan_hist']['primary_damage'][scan] = current_damage_data['scan_primary_fluence']
        overview['scan_hist']['primary_damage_error'][scan] = current_damage_data['scan_primary_fluence_error']
        overview['scan_hist']['number'][scan] = scan
    
    # Now we add the individual row scans
    if n_indv_scans > 0:
        
        for i, entry in enumerate(scan_data[individual_scan_mask]):
            # Add the current row fluence to the respective row in the histogram
            row_center_ts = (entry['row_stop_timestamp'] - entry['row_start_timestamp']) / 2 + entry['row_start_timestamp']
            
            overview['correction_scans']['center_timestamp'][i] = row_center_ts
            overview['correction_scans']['primary_damage'][i] = entry['row_primary_fluence']
            overview['correction_scans']['primary_damage_error'][i] = entry['row_primary_fluence_error']
            overview['correction_scans']['number'][i] = entry['row']

        # Have the resulting hist sorted in rows
        overview['correction_hist'] = overview['row_hist'][-n_rows:]

    return overview

        
def main(data, config):
    
    # Container for figures
    figs = []
    server = config['name']

    # Plot row-resolved scan damage
    for dmg in ('row_primary_fluence', 'row_tid'):

        resolved_map, n_comp = generate_scan_resolved_damage_map(scan_data=data[server]['Scan'],
                                                                 irrad_data=data[server]['Irrad'],
                                                                 damage=dmg)
        
        fig, _ = plotting.plot_scan_damage_resolved(resolved_map,
                                                    damage=dmg.split('_')[1], #data[server]['Irrad']['aim_damage'][0].decode(),
                                                    ion_name=config['daq']['ion'],
                                                    row_separation=data[server]['Irrad']['row_separation'][0],
                                                    n_complete_scans=n_comp)
        figs.append(fig)

    scan_overview = generate_scan_overview(scan_data=data[server]['Scan'],
                                           damage_data=data[server]['Damage'],
                                           irrad_data=data[server]['Irrad'])
    
    # Only allow arduino temp sensor for now
    if 'Temperature' in data[server] and 'ArduinoNTCReadout' in data[server]['Temperature']:
        temp_data = data[server]['Temperature']['ArduinoNTCReadout']
    else:
        temp_data = None
    
    fig, _ = plotting.plot_scan_overview(overview=scan_overview,
                                         beam_data=data[server]['Beam'],
                                         temp_data=temp_data,
                                         daq_config=config['daq'])
    figs.append(fig)

    logging.info("Analyse beam properties during scan...")
    # Beam current histogram
    beam_during_scan_mask = create_beam_scan_mask(beam_data=data[server]['Beam'],
                                                  scan_data=data[server]['Scan'])
    beam_during_scan = data[server]['Beam'][beam_during_scan_mask]

    # Beam current in nA during scanning
    beam_currents_during_scan = data[server]['Beam']['beam_current']
    beam_currents_during_scan[~beam_during_scan_mask] = np.nan  # Mask non-scanning values with np.nan so matplotlib wont connect data
    beam_currents_during_scan[beam_during_scan_mask] /= constants.nano

    # Get indices of start and end of scan
    scan_idxs = np.nonzero(beam_during_scan_mask)[0]
    scan_idx_start, scan_idx_end = scan_idxs[0], scan_idxs[-1]

    fig, _ = plotting.plot_beam_current(timestamps=data[server]['Beam']['timestamp'][scan_idx_start:scan_idx_end],
                                        beam_current=beam_currents_during_scan[scan_idx_start:scan_idx_end],
                                        scan_data=True)
    figs.append(fig)

    plot_data = {
        'xdata': beam_currents_during_scan[beam_during_scan_mask],
        'xlabel': 'Beam current / nA',
        'ylabel': '#',
        'label': "Beam current during {} scan".format(duration_str_from_secs(seconds=beam_during_scan['timestamp'][-1]-beam_during_scan['timestamp'][0])),
        'title': "Beam current distribution during scan",
        'fmt': 'C0'
    }
    plot_data['label'] += ":\n    ({:.2f}{}{:.2f}) nA".format(beam_currents_during_scan[beam_during_scan_mask].mean(), u'\u00b1', beam_currents_during_scan[beam_during_scan_mask].std())

    fig, _ = plotting.plot_generic_fig(plot_data=plot_data, hist_data={'bins': 'stat'})
    figs.append(fig)

    # Relative position of beam-mean wrt the beam pipe center
    fig, _ = plotting.plot_relative_beam_position(horizontal_pos=beam_during_scan['horizontal_beam_position'],
                                                    vertical_pos=beam_during_scan['vertical_beam_position'],
                                                    scan_data=True)
    figs.append(fig)

    # Histogram of row proton fluence
    fig, _ = plotting.plot_fluence_distribution(fluence_data=data[server]['Scan']['row_primary_fluence'],
                                                ion=config['daq']['ion'],
                                                hardness_factor=config['daq']['kappa']['nominal'],
                                                stoping_power=config['daq']['stopping_power'])

    figs.append(fig)

    return figs
