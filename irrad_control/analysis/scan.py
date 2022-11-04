import logging
import numpy as np
from irrad_control.analysis import plotting
from irrad_control.analysis import constants
from tqdm import tqdm
from numba import njit

@njit
def data_while_scanning(stamps, data):
    scan_data = np.empty(0)
    for i in stamps:
        scan_data = np.append(scan_data, data[int(i)])
    return scan_data

def stamps_scanning(timestamps, start_timestamps, stop_timestamps):
    stamps = np.empty(0)
    pos = 0
    for i in tqdm(range(len(timestamps)), desc="Get Scan Data", unit="timestamps"):
        scan, pos = during_scan(timestamps[i], start_timestamps, stop_timestamps, pos)
        if scan:
            stamps = np.append(stamps, i)
    return stamps

@njit
def during_scan(timestamp, start_timestamps, stop_timestamps, pos):
    #check if timestamp is during scan process
    for j in range(pos, pos+2): #use range(0, len(start_timestamps)) if timestamps not ascending
        if start_timestamps[j] <= timestamp <= stop_timestamps[j]:
            return True, j
    return False, pos

def data_per_row(n_scan, n_rows, rows, data):
    res = np.empty(shape=(0, n_scan+1))
    for i in range(n_rows):
        temp = [[data[j] for j in range(len(data)) if rows[j]==i]]
        res = np.concatenate((res,temp))
    return res
        
def analyse_scan(data, **scan_kwargs):
    figs = []
    server = scan_kwargs['server']
    stamps = stamps_scanning(timestamps = data[server]['Beam']['timestamp'],
                            start_timestamps=data[server]['Scan']['row_start_timestamp'],
                            stop_timestamps=data[server]['Scan']['row_stop_timestamp'])
    nano = np.array(constants.nano)
    beam_current_nA = data[server]['Beam']['beam_current']/nano #beam current in nA
    logging.info("Generating plots ...")
    #Beam current over time while scanning
    timestamps_while_scan = data_while_scanning(stamps, data[server]['Beam']['timestamp'])
    beam_currents_while_scan = data_while_scanning(stamps=stamps, data=beam_current_nA)
    
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
    hor_beam_pos_scan = data_while_scanning(stamps=stamps,
                                            data=data[server]['Beam']['horizontal_beam_position'])
    ver_beam_pos_scan = data_while_scanning(stamps=stamps,
                                            data=data[server]['Beam']['vertical_beam_position'])
    
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
    res = data_per_row(n_scan=data[server]['Scan']['scan'][-1],
                       n_rows=data[server]['Scan']['n_rows'][0],
                       rows=data[server]['Scan']['row'],
                       data=data[server]['Scan']['row_tid'])
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
    fig = plotting.plot_everything(data={'scan_start':scan_start_timestamp,
                                         'scan_stop': scan_stop_timestamp,
                                         'row_start': data[server]['Scan']['row_start_timestamp'],
                                         'row_stop': data[server]['Scan']['row_stop_timestamp'],
                                         'row_tid': acc_tid,
                                         'beam_current': data[server]['Scan']['row_mean_beam_current']/nano,
                                         'proton_fluence': data[server]['Scan']['row_proton_fluence']},
                                    hardness_factor=scan_kwargs['hardness_factor'],
                                    stopping_power=scan_kwargs['stopping_power'])
    figs.append(fig)
    logging.info("Finished plotting.")
    return figs
