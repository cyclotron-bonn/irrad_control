import logging
import numpy as np
from irrad_control.analysis import plotting
from irrad_control.analysis import constants

def create_scan_mask(data, server):
    mask = np.zeros_like(data[server]['Beam']['timestamp'], dtype=bool)
    for idx_scan in range(data[server]['Scan'].shape[0]):
        scan_data = data[server]['Scan'][idx_scan]
        idx_row_start = np.searchsorted(data[server]['Beam']['timestamp'], scan_data['row_start_timestamp'])
        idx_row_stop = np.searchsorted(data[server]['Beam']['timestamp'], scan_data['row_stop_timestamp'])
        mask[idx_row_start:idx_row_stop] = True
    return mask

def heatmap_damage(rows, scan, damage):
    res = np.zeros(shape=(np.max(rows)+1, np.max(scan)+1), dtype=float)
    for i in range(len(scan)):
        res[rows[i],scan[i]]=damage[i]
    return res
        
def analyse_scan(data, **scan_kwargs):
    figs = []
    server = scan_kwargs['server']
    mask = create_scan_mask(data, server)
    nano = np.array(constants.nano)
    logging.info("Generating plots ...")
    #Beam current over time while scanning
    timestamps_while_scan = data[server]['Beam']['timestamp'][mask]
    beam_currents_while_scan = data[server]['Beam']['beam_current'][mask]/nano
    
    fig, _ = plotting.plot_beam_current(timestamps=timestamps_while_scan,
                                        beam_currents=beam_currents_while_scan,
                                        while_scan=True)
    figs.append(fig)
    
    #Histogram of Beam currents while scanning
    fig, _ = plotting.plot_beam_current_hist(beam_currents=beam_currents_while_scan,
                                             start=data[server]['Scan']['row_start_timestamp'][0],
                                             end=data[server]['Scan']['row_start_timestamp'][-1],
                                             while_scan=True)
    figs.append(fig)
    
    #Histogram of beam current diviation while scanning
    hor_beam_pos_scan = data[server]['Beam']['horizontal_beam_position'][mask]
    ver_beam_pos_scan = data[server]['Beam']['vertical_beam_position'][mask]
    
    fig, _ = plotting.plot_beam_deviation(horizontal_deviation=hor_beam_pos_scan,
                                          vertical_deviation=ver_beam_pos_scan,
                                          while_scan=True)
    figs.append(fig)
    #Histogram of proton fluence while scanning
    fluence_data = data[server]['Scan']['row_proton_fluence']
    fig, _ = plotting.fluence_row_hist(start=data[server]['Scan']['row_start_timestamp'][0],
                                        end=data[server]['Scan']['row_start_timestamp'][-1],
                                        fluence=fluence_data)
    figs.append(fig)
    
    #accumulated tid per row as bar diagram
    res = heatmap_damage(rows=data[server]['Scan']['row'],
                       scan=data[server]['Scan']['scan'],
                       damage=data[server]['Scan']['row_tid'])
    fig, _ = plotting.plot_tid_per_row(data=res, hardness_factor=scan_kwargs['hardness_factor'], stopping_power=scan_kwargs['stopping_power'])
    figs.append(fig)
    
    #Trying to cramp all of the above diagrams (except positional deviation) into one superduperdiagram
    tid_per_scan = [[data[server]['Scan']['row_tid'][i] for i in range(len(data[server]['Scan']['row_tid'])) if data[server]['Scan']['scan'][i] == scan] for scan in range(data[server]['Scan']['scan'][-1]+1)]
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
                                         'beam_current': data[server]['Scan']['row_mean_beam_current']/nano,
                                         'beam_loss': row_mean_beam_loss/nano},
                                    hardness_factor=scan_kwargs['hardness_factor'],
                                    stopping_power=scan_kwargs['stopping_power'])
    figs.append(fig)
    logging.info("Finished plotting.")
    return figs
