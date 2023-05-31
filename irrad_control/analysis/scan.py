import logging
import numpy as np
from irrad_control.analysis import plotting, constants


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

    # Make empty map of shape n_rows x n_total_scans
    resolved_map = np.zeros(shape=(n_total_scans, n_rows))

    # Loop over scan data and add to map
    indv_scan_number = n_complete_scans
    for i in range(len(scan_data)):

        row = scan_data[i]['row']
        scan = scan_data[i]['scan']

        # We are looking at completed scans
        if scan != -1:
            # Add fluence of this row to all subsequent scans since in all following scans this fluence will already be applied in the row
            resolved_map[scan:, row] += scan_data[i][damage]
        else:
            resolved_map[indv_scan_number:, row] += scan_data[i][damage]
            indv_scan_number += 1
    
    return resolved_map

        
def main(data, config=None):
    
    # Container for figures
    figs = []

    # Multipart analysis
    if config is None:
        pass
    
    # One file
    else:

        server = config['name']
        beam_during_scan_mask = create_beam_scan_mask(beam_data=data[server]['Beam'],
                                                      scan_data=data[server]['Scan'])
        # Beam current histogram
        beam_during_scan = data[server]['Beam'][beam_during_scan_mask]
        
        scan_duration_str = plotting._calc_duration(start=beam_during_scan['timestamp'][0],
                                                        end=beam_during_scan['timestamp'][-1],
                                                        as_str=True)

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
            'label': "Beam current during {} scan".format(scan_duration_str),
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

        
        resolved_map = generate_scan_resolved_damage_map(scan_data=data[server]['Scan'],
                                                         irrad_data=data[server]['Irrad'])
        
        fig, ax = plotting.plot_damage_resolved(resolved_map, damage='tid', ion_name='proton', server=server, dut=False)

        figs.append(fig)

        return figs
