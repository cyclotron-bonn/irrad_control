"""Collection of analysis functions"""
import irrad_control.analysis.constants as irrad_consts
import numpy as np


def tid_scan(proton_fluence, stopping_power=irrad_consts.p_stop_Si):
    """

    Parameters
    ----------
    proton_fluence: float
        Number of protons per square centimeter

    stopping_power:
        Total stopping power of the protons in MeV cm^2 / g

    Returns
    -------
    Total ionizing dose in Mrad
    """
    return 1e5 * irrad_consts.elementary_charge * proton_fluence * stopping_power


def tid_rate_scan(proton_flux, stopping_power):
    """

    Parameters
    ----------
    proton_flux: float
        Number of protons per square centimeter per second

    stopping_power:
        Total stopping power of the protons in MeV cm^2 / g

    Returns
    -------
    Total ionizing dose in Mrad
    """
    return 1e5 * irrad_consts.elementary_charge * proton_flux * stopping_power


def proton_fluence_scan(proton_current, scan_step, scan_speed):
    """

    Parameters
    ----------
    proton_current: float
        Proton beam current in A

    scan_step: float
        Separation between scanned rows in mm

    scan_speed:
        Speed with which rows are scanned in mm/s

    Returns
    -------
    Fluence in protons / cm^2 delivered.

    """
    return proton_current / (irrad_consts.elementary_charge * scan_speed * scan_step * 1e-2)


def proton_flux_scan(proton_current, scan_step, scan_speed, scan_duration):
    """

    Parameters
    ----------
    proton_current: float
        Proton beam current in A

    scan_step: float
        Separation between scanned rows in mm / cm / m

    scan_speed: float
        Speed with which rows are scanned in mm/s / cm/s / m/s

    scan_duration:
        Duration which is needed to scan from first row to last row

    Returns
    -------
    Proton flux in protons/cm^2/s
    """
    return proton_fluence_scan(proton_current, scan_step, scan_speed) / scan_duration


def time_scan(scan_area, scan_step, scan_speed):
    """

    Parameters
    ----------
    scan_area: float
        The area that is scanned in mm^2 / cm^2 / m^2

    scan_step: float
        Separation between scanned rows in mm / cm / m

    scan_speed: float
        Speed with which rows are scanned in mm/s / cm/s / m/s

    Returns
    -------
    Time needed to scan the entire area NOT considering de-/acceleration on turning points.
    """
    return scan_area / (scan_step * scan_speed)


def calibrated_beam_current(beam_monitor_sig, calibration_factor, full_scale_current):
    """

    Parameters
    ----------
    beam_monitor_sig: float
        Beam monitor signal that was used for calibration e.g. SEM sum signal

    calibration_factor: float
        Calibration constant

    full_scale_current: float
        Full-scale current corresponding to 5V output of the respective channel

    Returns
    -------
    Beam current in nA
    """
    return calibration_factor * full_scale_current * beam_monitor_sig


def rel_beam_position(sig_a, sig_b, plane):

    try:
        rel_pos = float(sig_a - sig_b) / float(sig_a + sig_b)
    except ZeroDivisionError:
        rel_pos = 0.0

    # If we don't have beam, sometimes results get large and cause problems with displaying the data, therefore limit
    rel_pos = 1.0 if rel_pos > 1 else -1 if rel_pos < -1 else rel_pos

    # Horizontally, if we are shifted to the left the graph should move to the left, therefore * -1
    rel_pos *= -100 if plane == 'h' else 100

    return rel_pos


def v_sig_to_i_sig(v_sig, full_scale_current, full_scale_voltage):
    return v_sig * full_scale_current / full_scale_voltage


def i_sig_to_v_sig(i_sig, full_scale_current, full_scale_voltage):
    return i_sig * full_scale_voltage / full_scale_current


def get_ntc_temp(ntc_voltage, ref_voltage, ref_resistor=1e4, ntc_nominal=1e4, temp_nominal=25, beta_coefficient=3950):
    # 1 / T = 1 / T_0 + 1 / B * ln(R / R_0)

    # Calc resistance in Ohm
    ntc_resistance = ref_resistor / ((ref_voltage / ntc_voltage) - 1)

    # Calc temperature
    temp = 1.0 / (1.0 / (temp_nominal + irrad_consts.kelvin) + 1.0 / beta_coefficient * np.log(ntc_resistance / ntc_nominal))

    # Adjust to Celsius
    temp -= irrad_consts.kelvin

    return temp


def get_hist_idx(val, bin_edges, side='left'):
    res = np.searchsorted(bin_edges, val, side=side)
    if isinstance(res, np.ndarray):
        return [int(idx) - 1 for idx in res]
    else:
        return int(res) - 1

