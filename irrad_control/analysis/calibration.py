"""
This script contains the functions used for beam monitor calibration
"""

import logging
import numpy as np
import scipy.odr as odr
from scipy.optimize import curve_fit
from uncertainties import ufloat
from collections import defaultdict

import irrad_control.analysis.formulas as irrad_formulas
from irrad_control.devices.readout import RO_DEVICES, DAQ_BOARD_CONFIG, RO_ELECTRONICS_CONFIG


def beam_monitor_calibration(irrad_data, irrad_config, server):

    # Get raw data and event data; events are needed in order to check for changing full scale factors when using the IrradDAQBoard
    raw_data = irrad_data[server]['Raw']

    assert 'readout' in irrad_config, "Configuration field 'readout' required but not found"
    ch_types = irrad_config['readout']['types']

    if irrad_config['readout']['device'] == RO_DEVICES.DAQBoard:
        assert 'Event' in irrad_data[server], "Data entry 'Event' required in input data but not found"

    # Check configuration for required channel types: calibrate all channels of type *cup* or *blm* vs *sem_sum*
    assert 'sem_sum' in ch_types, "Channel of type 'sem_sum' required for calibration but not found"
    assert 'cup' in ch_types or 'blm' in ch_types, "Channel(s) of type 'cup'/'blm' required for calibration but not found"
    
    # Extract relevant channel numbers and names
    sem_calib_channel = defaultdict(dict)
    cup_calib_channel = defaultdict(dict)

    for i, ch in enumerate(irrad_config['readout']['channels']):
        
        ch_type = irrad_config['readout']['types'][i]

        if ch_type == 'sem_sum':
            sem_calib_channel[ch]['idx'] = i

        elif ch_type in ('cup', 'blm'):
            cup_calib_channel[ch]['idx'] = i

    # Get info about the full scale current
    for quant in (sem_calib_channel, cup_calib_channel):
        for ch in quant:

            # Set initial IFS per channel
            if irrad_config['readout']['device'] == RO_DEVICES.DAQBoard:
                quant[ch]['ifs'] = irrad_config['readout']['ro_group_scales'][irrad_config['readout']['ch_groups'][quant[ch]['idx']]]
            else:
                quant[ch]['ifs'] = irrad_config['readout']['ro_scales'][quant[ch]['idx']]

    # Get max reference voltage of readout
    if irrad_config['readout']['device'] == RO_DEVICES.DAQBoard:
        ref_voltage = DAQ_BOARD_CONFIG['common']['voltages']['5Vp']
    else:
        ref_voltage = 5.

    # Loop over all combinations of sem calibration channels versus cups
    for sem_ch in sem_calib_channel:
        for cup_ch in cup_calib_channel:

            # Make data cuts to exclude quick changes and data taken at edge of range
            cut_data = apply_rel_data_cuts(data=raw_data,
                                           ref_sig=raw_data[cup_ch],
                                           ref_sig_max=ref_voltage,  # Max reference signal
                                           cut_slope=0.03,  # Cut variation larger than 3% of *ref_signal_max*
                                           cut_min=0.02,  # Cut data smaller than 2% of *ref_signal_max*
                                           cut_max=0.98)  # Cut data larger than 98% of *ref_signal_max*

            # Initialize arrays containing the IFS values for each entry
            ifs_sem_ch = np.full_like(cut_data[sem_ch], fill_value=sem_calib_channel[sem_ch]['ifs'])
            ifs_cup_ch = np.full_like(cut_data[cup_ch], fill_value=cup_calib_channel[cup_ch]['ifs'])
             
            # Do calibration with respect to changing scales 
            if irrad_config['readout']['device'] == RO_DEVICES.DAQBoard:

                # Search events for 'update_group_ifs' which indicate change in readout IFS scale
                events = irrad_data[server]['Event']
                update_ifs_events = events[events['event'] == b'update_group_ifs']
                
                # IFS groups
                sem_group = irrad_config['readout']['ch_groups'][sem_calib_channel[sem_ch]['idx']]
                cup_group = irrad_config['readout']['ch_groups'][cup_calib_channel[cup_ch]['idx']]

                # Init indeces to update IFS values
                sem_update_idx = cup_update_idx = 0
                
                # Loop over all updates
                for ifs_updates in update_ifs_events:
                    
                    update_parameters = str(ifs_updates['parameters'])
                    idx = np.searchsorted(cut_data['timestamp'], ifs_updates['timestamp'], side='right')
                    updated_ifs_value = float(update_parameters.split()[1])  # This is the IFS in nA

                    if sem_group in update_parameters:
                        #ifs_sem_ch[sem_update_idx:idx] = updated_ifs_value
                        #sem_update_idx = idx
                        ifs_sem_ch[idx:] = updated_ifs_value

                    elif cup_group in update_parameters:
                        #ifs_cup_ch[cup_update_idx:idx] = updated_ifs_value
                        #cup_update_idx = idx
                        ifs_cup_ch[idx:] = updated_ifs_value

                # Calibrate current_sem_ch to current_cup_ch in this case
                current_sem_ch = irrad_formulas.v_sig_to_i_sig(cut_data[sem_ch], full_scale_current=ifs_sem_ch, full_scale_voltage=ref_voltage)
                current_cup_ch = irrad_formulas.v_sig_to_i_sig(cut_data[cup_ch], full_scale_current=ifs_cup_ch, full_scale_voltage=ref_voltage)
                
                # Do fit
                popt, perr, red_chi = fit(xdata=current_sem_ch, ydata=current_cup_ch, xerr=current_sem_ch*0.05, yerr=current_cup_ch*0.05, use_odr=True)

                beta_const = ufloat(popt[0], perr[0])
                lambda_const = beta_const / ufloat(ref_voltage, ref_voltage*0.01)
                print(lambda_const)

            # Do calibration with static IFS scales
            else:
                ifs_cup_array = np.full_like(cut_data[cup_ch], fill_value=cup_calib_channel[cup_ch]['ifs'])


def _calibrate_static_ifs(data, sem_ch, sem_ifs, cup_ch, cup_ifs):

    # Extract data
    time_in_seconds = data['timestamp'] - data['timestamp'][0]
    voltage_sem_ch = data[sem_ch]
    current_cup_ch = irrad_formulas.v_sig_to_i_sig(v_sig=data[cup_ch], full_scale_current=cup_ifs, full_scale_voltage=5.0)
    
    # Errors
    current_cup_ch_error = current_cup_ch * 0.01  # Error of 1%
    voltage_sem_ch_error = voltage_sem_ch * 0.01  # Error of 1%

    # Make fit
    popt, perr, red_chi = fit(xdata=voltage_sem_ch, ydata=current_cup_ch, xerr=voltage_sem_ch_error, yerr=current_cup_ch_error, use_odr=True)

    # Calculate calibration constant lambda
    alpha_slope = ufloat(popt[0, popt[1]])
    ifs_calib = ufloat(sem_ifs, 0.01*sem_ifs)
    lambda_const = alpha_slope / ifs_calib


def fit(xdata, ydata, yerr=None, xerr=None, use_odr=True, p0=(1,), fit_func=irrad_formulas.lin_odr):

    # Orthogonal distance regression
    if use_odr:
        lin_model = odr.Model(fit_func)
        data_model = odr.RealData(xdata, ydata, sy=yerr, sx=xerr)
        odr_model = odr.ODR(data_model, lin_model, beta0=p0)
        fit_out = odr_model.run()
        popt = fit_out.beta
        perr = fit_out.sd_beta
        red_chi = fit_out.res_var
    # Curve fit
    else:
        popt, pcov = curve_fit(fit_func, xdata, ydata, p0=p0, sigma=yerr, absolute_sigma=True)
        perr = np.sqrt(np.diag(pcov))
        red_chi = np.nan if yerr is None else irrad_formulas.red_chisquare(ydata, fit_func(xdata, *popt), yerr, popt)

    return popt, perr, red_chi


def apply_rel_data_cuts(data, ref_sig, ref_sig_max, cut_slope=0.01, cut_min=0.01, cut_max=0.99, return_mask=False):

    # Initial mask
    mask_slope = np.ones_like(ref_sig, dtype=bool)

    # Slopes
    slope_ref_sig = np.abs(np.diff(ref_sig))

    # Mask qick changes in ref_sig; allow only slopes of max ref_sig_slope
    mask_slope[1:] = slope_ref_sig < (cut_slope * ref_sig_max)

    logging.debug("Masking {} ({:.2f} %) entries due to large (< {} % of ref. signal) changes".format(np.count_nonzero(~mask_slope), 100 * (np.count_nonzero(~mask_slope) / mask_slope.shape[0]), cut_slope))

    mask_min = ref_sig > cut_min * ref_sig_max

    logging.debug("Masking {} ({:.2f} %) entries due to low (> {} % of ref. signal) signal".format(np.count_nonzero(~mask_min), 100 * (np.count_nonzero(~mask_min) / mask_min.shape[0]), cut_min))

    mask_max = ref_sig < cut_max * ref_sig_max

    logging.debug("Masking {} ({:.2f} %) entries due to high (< {} % of ref. signal) signal".format(np.count_nonzero(~mask_max), 100 * (np.count_nonzero(~mask_max) / mask_max.shape[0]), cut_max))

    mask = mask_slope & mask_min & mask_max

    logging.info("Masking {} ({:.2f} %) entries due to cuts".format(np.count_nonzero(~mask), 100 * (np.count_nonzero(~mask) / mask.shape[0])))

    # Apply mask to data
    res = {k:data[k][mask] for k in data.dtype.names}

    return (res, mask) if return_mask else res
