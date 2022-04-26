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
from irrad_control.analysis.utils import load_irrad_data
from irrad_control.devices.readout import RO_DEVICES


def beam_monitor_calibration(irrad_data, irrad_config, server):

    # Get raw data and event data; events are needed in order to check for changing full scale factors when using the IrradDAQBoard
    raw_data = irrad_data[server]['Raw']

    assert 'readout' in irrad_config, "Configuration field 'readout' required but not found"
    ch_types = irrad_config['readout']['types']

    print(irrad_config)

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

    print(sem_calib_channel, cup_calib_channel)



    







    



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
