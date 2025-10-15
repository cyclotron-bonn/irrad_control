"""
This script contains the functions used for beam monitor calibration
"""

import logging
import numpy as np
import scipy.odr as odr
from scipy.optimize import curve_fit
from uncertainties import ufloat
from collections import defaultdict
from irrad_control.analysis import plotting

import irrad_control.analysis.formulas as irrad_formulas
from irrad_control.devices.readout import RO_DEVICES, DAQ_BOARD_CONFIG
from irrad_control.ions import get_ions


def _get_ifs(channel_idx, config):

    if config['readout']['device'] == RO_DEVICES.DAQBoard:
        return config['readout']['ro_group_scales'][config['readout']['ch_groups'][channel_idx]]
    
    return config['readout']['ro_scales'][channel_idx]


def _get_ref_voltage(config):

    # Get max reference voltage of readout board
    if config['readout']['device'] == RO_DEVICES.DAQBoard:
        return DAQ_BOARD_CONFIG['common']['voltages']['5Vp']
    
    # Otherwise 5 V
    return 5.


def main(data, config, summary=None):

    server = config['name']
    ion_name = config['daq']['ion']
    ion_energy = config['daq']['ekin_initial']
    
    # Get raw data and event data; events are needed in order to check for changing full scale factors when using the IrradDAQBoard
    raw_data = data[server]['Raw']

    assert 'readout' in config, "Configuration field 'readout' required but not found"
    ch_types = config['readout']['types']

    if config['readout']['device'] == RO_DEVICES.DAQBoard:
        assert 'Event' in data[server], "Data entry 'Event' required in input data but not found"

    # Check configuration for required channel types: calibrate all channels of type *cup* or *blm* vs *sem_sum*
    assert 'sem_sum' in ch_types, "Channel of type 'sem_sum' required for calibration but not found"
    assert 'cup' in ch_types or 'blm' in ch_types, "Channel(s) of type 'cup'/'blm' required for calibration but not found"
    
    # Extract relevant channel numbers and names
    sem_calib_channel = defaultdict(dict)
    cup_calib_channel = defaultdict(dict)

    for i, ch in enumerate(config['readout']['channels']):
        
        ch_type = config['readout']['types'][i]

        if ch_type == 'sem_sum':
            sem_calib_channel[ch]['idx'] = i

        elif ch_type in ('cup', 'blm'):
            cup_calib_channel[ch]['idx'] = i

    # Get info about the full scale current
    for quant in (sem_calib_channel, cup_calib_channel):
        for ch in quant:
            quant[ch]['ifs'] = _get_ifs(channel_idx=quant[ch]['idx'], config=config)

    # Search events for 'update_group_ifs' which indicate change in readout IFS scale
    events = data[server]['Event']
    update_ifs_events = events[events['event'] == b'update_group_ifs']

    # Make list of figures to return
    figs = []

    # Loop over all combinations of sem calibration channels versus cups
    for sem_ch in sem_calib_channel:
        for cup_ch in cup_calib_channel:

            # Make data cuts to exclude quick changes and data taken at edge of range
            # Cuts are made on the *cup_ch*
            cut_data = apply_rel_data_cuts(data=raw_data,
                                           ref_sig=raw_data[cup_ch],
                                           ref_sig_max=_get_ref_voltage(config=config),  # Max reference signal
                                           cut_slope=0.01,  # Cut variation larger than 3% of *ref_signal_max*
                                           cut_min=0.02,  # Cut data smaller than 2% of *ref_signal_max*
                                           cut_max=0.98)  # Cut data larger than 98% of *ref_signal_max*

            if cut_data[cup_ch].shape[0] < 100:
                logging.error(f"Insufficient data after cuts! Skipping calibration for cup-type channel '{cup_ch}' vs. sem-type channel '{sem_ch}'")
                continue

            # Perform calibration between the two channels
            calib_result, stat_result, fit_values, misc_arrays = calibrate_sem_vs_cup(data=cut_data,
                                                                                      sem_ch_idx=sem_calib_channel[sem_ch]['idx'],
                                                                                      cup_ch_idx=cup_calib_channel[cup_ch]['idx'],
                                                                                      config=config,
                                                                                      update_ifs_events=update_ifs_events,
                                                                                      return_full=True)

            # Extract results
            _, _, red_chi = fit_values
            current_sem_ch, current_cup_ch, lambda_stat_array, stat_mask = misc_arrays
            _, lambda_stat = stat_result

            # Start the plotting
            #Beam current over time
            fig, _ = plotting.plot_beam_current(timestamps=cut_data['timestamp'][stat_mask], beam_current=current_cup_ch[stat_mask], ch_name=cup_ch)

            figs.append(fig)

            #Beam current over time
            fig, _ = plotting.plot_calibration(calib_data=current_sem_ch[stat_mask],
                                               ref_data=current_cup_ch[stat_mask],
                                               calib_sig=sem_ch, ref_sig=cup_ch,
                                               red_chi=red_chi,
                                               gamma_lambda=calib_result,
                                               ion_name=ion_name,
                                               ion_energy=ion_energy)

            figs.append(fig)

            #Beam current over time
            fig, _ = plotting.plot_calibration(calib_data=current_sem_ch[stat_mask],
                                               ref_data=current_cup_ch[stat_mask],
                                               calib_sig=sem_ch, ref_sig=cup_ch,
                                               red_chi=red_chi,
                                               gamma_lambda=calib_result,
                                               ion_name=ion_name,
                                               ion_energy=ion_energy,
                                               hist=True)

            figs.append(fig)

            # Statistical distribution of lambdas
            fig, _ = plotting.plot_generic_fig(plot_data={'xdata': lambda_stat_array,
                                                          'xlabel': r'$\mathrm{\lambda_{stat}\ /\ V^{-1}}$',
                                                          'ylabel': r'$\mathrm{\#}$',
                                                          'label': r'$\mathrm{\lambda_{stat} = (%.3f\pm %.3f)\ /\ V^{-1}}$' % (lambda_stat.n, lambda_stat.s),
                                                          'title': r"$\lambda_{stat}$ distribution after 2$\sigma$ cut",
                                                          'fmt': 'C0.'},
                                                hist_data={'bins': 'stat'},
                                                figsize=(8,6))

            figs.append(fig)

    return figs


def generate_ch_ifs_array(data, config, channel_idx, update_ifs_events=None):

    channel = config['readout']['channels'][channel_idx]

    ifs_array = np.full_like(data[channel], fill_value=_get_ifs(channel_idx=channel_idx, config=config))

    # The IFS have been changed during the session: adapt
    if update_ifs_events is not None:
        # Extract IFS group that the channel belongs to
        channel_group = config['readout']['ch_groups'][channel_idx]
        # Loop over updates and check if our channel is affected
        for ifs_update in update_ifs_events:
            
            # Get update prameters to check channel
            update_parameters = str(ifs_update['parameters'])

            if channel_group in update_parameters:
                # Extract IFS value in nA
                # Prior to v2.2
                try:
                    updated_ifs_value = float(update_parameters.split()[1])
                # From v2.2 onwards
                except IndexError:
                    for up in update_parameters.split(','):
                        k, v = up.split('=')
                        if k == 'ifs':
                            updated_ifs_value = float(v)
                            break
                    else:
                        raise RuntimeError("Could not extract 'I_FS' parameter from update event")

                # Search for the index at which the IFS change happened
                idx = np.searchsorted(data['timestamp'], ifs_update['timestamp'], side='right')
                # Update subsequent IFS values
                ifs_array[idx:] = updated_ifs_value

    return ifs_array


def calibrate_sem_vs_cup(data, sem_ch_idx, cup_ch_idx, config, update_ifs_events, return_full=False):

    sem_ch = config['readout']['channels'][sem_ch_idx]
    cup_ch = config['readout']['channels'][cup_ch_idx]
    ion = get_ions()[config['daq']['ion']]

    # Initialize arrays containing the IFS values for each entry
    ifs_sem_ch = generate_ch_ifs_array(data=data, config=config, channel_idx=sem_ch_idx, update_ifs_events=update_ifs_events)
    ifs_cup_ch = generate_ch_ifs_array(data=data, config=config, channel_idx=cup_ch_idx, update_ifs_events=update_ifs_events)

    ref_voltage = _get_ref_voltage(config=config)

    # Calibrate current_sem_ch to current_cup_ch in this case
    current_sem_ch = irrad_formulas.v_sig_to_i_sig(data[sem_ch], full_scale_current=ifs_sem_ch, full_scale_voltage=ref_voltage)
    current_cup_ch = irrad_formulas.v_sig_to_i_sig(data[cup_ch], full_scale_current=ifs_cup_ch, full_scale_voltage=ref_voltage)

    # Errors come from I_FS which is sqrt(3%²) = 0.0173
    current_sem_ch_error, current_cup_ch_error = 0.0173 * current_sem_ch, 0.0173 * current_cup_ch

    ########################################################################
    # Calibration:                                                         #
    # -> I_SEE = gamma * I_beam / q_ion                                    #
    # => I_sem_type = gamma * I_cup_type / q_ion                           #
    # -> I_sem_type = U_sem_type / ref_voltage * IFS                       #
    # -> gamma * I_cup_type / q_ion = U_sem_type / ref_voltage * IFS       #
    # <=> I_cup_type = q_ion / (gamma * ref_voltage) * IFS * U_sem_type    #
    # <=> I_cup_type = lambda * IFS * U_sem_type                           #
    # -> lambda = q_ion / (gamma * ref_voltage), [lambda] = 1/V            #
    # => I_beam(U_sem_type, IFS) = lambda * IFS * U_sem_type               #
    ########################################################################

    # Get statistical calibration constant and use it to cut the fit data on 2 sigma
    gamma_stat_array = current_sem_ch / current_cup_ch * ion.n_charge
    gamma_stat = ufloat(np.nanmean(gamma_stat_array), np.nanstd(gamma_stat_array))
    gamma_stat_mask = (gamma_stat_array > (gamma_stat.n - 2 * gamma_stat.s)) & (gamma_stat_array < (gamma_stat.n + 2 * gamma_stat.s))
    
    lambda_stat_array = ion.n_charge / (gamma_stat_array[gamma_stat_mask] * ref_voltage)
    lambda_stat = ufloat(np.nanmean(lambda_stat_array), np.nanstd(lambda_stat_array))

    logging.debug("Discarding {} ({:.2f} %) entries for calibration fit due to 2 sigma cut".format(np.count_nonzero(~gamma_stat_mask), 100 * (np.count_nonzero(~gamma_stat_mask) / gamma_stat_mask.shape[0])))
    
    # Do fit
    popt, perr, red_chi = fit(xdata=current_cup_ch[gamma_stat_mask],
                              ydata=current_sem_ch[gamma_stat_mask],
                              xerr=current_sem_ch_error[gamma_stat_mask],
                              yerr=current_cup_ch_error[gamma_stat_mask],
                              use_odr=True)

    # Get slope and finally lambda_const which is calibration value
    gamma_fit = ufloat(popt[0], perr[0]) * ion.n_charge
    
    # Mean of fit and stat
    gamma_res = (gamma_fit + gamma_stat) / 2.0
    lambda_res = ion.n_charge / (gamma_res * ref_voltage)

    # Notify the user if red. Chi² is very fishy
    if not 0.05 <= red_chi <= 5:
        logging.warning(f"The calibration fit resulted in a red. Chi^2 of {red_chi:.2E} which indicates a faulty fit or model.")

    logging.debug(f"Calibration of linear model I_SEE = gamma * I_beam / q_ion -> gamma=({100*gamma_fit.n:.2E}+-{100*gamma_fit.s:.2E}) % @ red. Chi^2 {red_chi:.2f}")

    logging.info("Beam monitor calibration for '{}' vs '{}': {} 1/V".format(cup_ch, sem_ch,
                                                                            '{}=({:.3f}{}{:.3f})'.format(u'\u03bb', lambda_res.n, u'\u00b1', lambda_res.s)))

    if return_full:
        return (gamma_res, lambda_res), (gamma_stat, lambda_stat), (popt, perr, red_chi), (current_sem_ch, current_cup_ch, lambda_stat_array, gamma_stat_mask)
    else:
        return (gamma_res, lambda_res), (gamma_stat, lambda_stat)

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
