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


def damage_per_scan_and_row(scan_data, irrad_data, damage='row_primary_fluence'):

    damage_map = np.zeros(shape=(scan_data['scan'][-1] + 1 or 1, irrad_data['n_rows'][0]), dtype=float)

    for i in range(scan_data.shape[0]):
        damage_map[scan_data['scan'][i], scan_data['row'][i]] = scan_data[damage][i]

    return damage_map

        
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

        # Beam current in nA during scanning
        beam_during_scan = data[server]['Beam'][beam_during_scan_mask]
        beam_currents_during_scan = beam_during_scan['beam_current'] / constants.nano
    
        fig, _ = plotting.plot_beam_current(timestamps=beam_during_scan['timestamp'],
                                            beam_current=beam_currents_during_scan,
                                            scan_data=data[server]['Scan'])
        figs.append(fig)
    
        #Histogram of Beam currents while scanning
        fig, _ = plotting.plot_beam_current_hist(beam_currents=beam_currents_during_scan,
                                                 start=data[server]['Scan']['row_start_timestamp'][0],
                                                 end=data[server]['Scan']['row_start_timestamp'][-1],
                                                 while_scan=True)
        figs.append(fig)
    
        fig, _ = plotting.plot_beam_deviation(horizontal_deviation=beam_during_scan['horizontal_beam_position'],
                                              vertical_deviation=beam_during_scan['vertical_beam_position'],
                                              while_scan=True)
        figs.append(fig)
    
        #Histogram of proton fluence while scanning
        fig, _ = plotting.fluence_row_hist(start=data[server]['Scan']['row_start_timestamp'][0],
                                           end=data[server]['Scan']['row_start_timestamp'][-1],
                                           fluence=data[server]['Scan']['row_primary_fluence'])
        figs.append(fig)
    
        #accumulated tid per row as bar diagram
        damage_map_scan_row = damage_per_scan_and_row(scan_data=data[server]['Scan'],
                                                      irrad_data=data[server]['Irrad'])

        fig, _ = plotting.plot_damage_resolved(primary_damage_resolved=damage_map_scan_row,
                                               stopping_power=config['daq']['stopping_power'],
                                               hardness_factor=config['daq']['kappa']['nominal'],
                                               ion_name=config['daq']['ion'])
        figs.append(fig)
    
        #Trying to cramp all of the above diagrams (except positional deviation) into one superduperdiagram
        tid_per_scan = [[data[server]['Scan']['row_tid'][i] for i in range(len(data[server]['Scan']['row_tid'])) if data[server]['Scan']['scan'][i] == scan] for scan in range(data[server]['Scan']['scan'][-1]+1)]
        print(tid_per_scan)
        acc_tid = np.zeros((len(tid_per_scan),len(tid_per_scan[0])))
        for i in range(len(tid_per_scan)):
            t = np.zeros(len(tid_per_scan[0]))
            for j in range(i+1):
                t = t + tid_per_scan[j]
            acc_tid[i] = t
        acc_tid = acc_tid.flatten()
        
        scan_start_timestamp = np.array([data[server]['Scan']['row_start_timestamp'][i] for i in range(len(data[server]['Scan']['scan'])) if i%data[server]['Scan']['n_rows'][i]==0])
        scan_stop_timestamp = np.array([data[server]['Scan']['row_stop_timestamp'][i] for i in range(len(data[server]['Scan']['scan'])) if i%data[server]['Scan']['n_rows'][0]==data[server]['Scan']['n_rows'][0]-1])
        row_mean_beam_loss = np.zeros_like(data[server]['Scan']['row_mean_beam_current'], dtype=float)
        for idx_scan in range(data[server]['Scan'].shape[0]):
            scan_data = data[server]['Scan'][idx_scan]
            idx_row_start = np.searchsorted(data[server]['Beam']['timestamp'], scan_data['row_start_timestamp'])
            idx_row_stop = np.searchsorted(data[server]['Beam']['timestamp'], scan_data['row_stop_timestamp'])
            row_mean_beam_loss[idx_scan]=np.mean(data[server]['Beam']['beam_loss'][idx_row_start:idx_row_stop])
        
        fig = plotting.plot_everything(data={'scan_start':scan_start_timestamp,
                                            'scan_stop': scan_stop_timestamp,
                                            'row_start': data[server]['Scan']['row_start_timestamp'],
                                            'row_stop': data[server]['Scan']['row_stop_timestamp'],
                                            'row_tid': acc_tid,
                                            'beam_current': data[server]['Scan']['row_mean_beam_current']/constants.nano,
                                            'beam_loss': row_mean_beam_loss/constants.nano},
                                        hardness_factor=config['daq']['kappa']['nominal'],
                                        stopping_power=config['daq']['stopping_power'])
        figs.append(fig)
        logging.info("Finished plotting.")
        return figs
