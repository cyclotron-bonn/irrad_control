"""Collection of analysis functions"""
import math
import numpy as np
import irrad_control.analysis.constants as irrad_consts


def tid_per_scan(primary_fluence, stopping_power):
    """

    Parameters
    ----------
    primary_fluence: float
        Number of ions per square centimeter

    stopping_power:
        Total stopping power of the ions in MeV cm^2 / g

    Returns
    -------
    Total ionizing dose in Mrad
    """
    return irrad_consts.MEV_PER_GRAM_TO_MRAD * primary_fluence * stopping_power


def tid_rate(ion_rate, stopping_power):
    """

    Parameters
    ----------
    ion_rate: float
        Number of ions per second

    stopping_power:
        Total stopping power of the ions in MeV cm^2 / g

    Returns
    -------
    Total ionizing dose rate in Mrad/s
    """
    return irrad_consts.MEV_PER_GRAM_TO_MRAD * ion_rate * stopping_power


def fluence_per_scan(ion_current, ion_n_charge, scan_step, scan_speed):
    """

    Parameters
    ----------
    current: float
        Ion beam current in A

    scan_step: float
        Separation between scanned rows in mm

    scan_speed:
        Speed with which rows are scanned in mm/s

    Returns
    -------
    Fluence in ions / cm^2 delivered.

    """
    return ion_current / (ion_n_charge * irrad_consts.elementary_charge * scan_speed * scan_step * 1e-2)


def neq_rate(ion_rate, hardness_factor):
    """

    Parameters
    ----------
    ion_rate: float
        Ion rate in particles / s

    hardness_factor:
        Hardness factor to scale damage to neutron eqivalents

    Returns
    -------
    1 MeV neutron eqivalent damages / s
    """
    return ion_rate * hardness_factor


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
    temp = 1.0 / (1.0 / (temp_nominal + irrad_consts.kelvin) + 1.0 / beta_coefficient * math.log(ntc_resistance / ntc_nominal))

    # Adjust to Celsius
    temp -= irrad_consts.kelvin

    return temp


def get_hist_idx(val, bin_edges, side='left'):
    res = np.searchsorted(bin_edges, val, side=side)
    if isinstance(res, np.ndarray):
        return [int(idx) - 1 for idx in res]
    else:
        return int(res) - 1


def lin_odr(B, x):
    return B[0] * x + (0 if len(B) == 1 else B[1])


def lin(x, *args):
    return args[0] * x + (0 if len(args) == 1 else args[1])


def red_chisquare(observed, expected, observed_error, popt):
    return np.sum(((observed - expected) / observed_error)**2 / (len(observed_error) - len(popt) - 1))

def gamma(energy, mass):
    return energy / mass + 1
    
def beta(energy=None, mass=None, gamma_val=None):
    assert energy is not None and mass is not None or gamma_val is not None, "Either gamm or energy and mass has to be given"
    
    gv = gamma_val if gamma_val is not None else gamma(energy, mass)
    
    return (1 - 1 / gv**2)** .5

def bethe_bloch_Si(charge, mass, energy, density_normalized=True):
    """
    Bethe-Bloch formula for ionizing energy loss of ions in Si.
    largely taken 'Particle Detectors - Fundamentals and Applications' by N. Wermes, H. Kolanoski
    """
    # Constant K = 4 * pi * N_A * r_e^2 * m_e * c^2
    K = 0.307  # MeV cm² / mol

    # Charge, atomic number, mean exitation energy and density of silicon
    Z_Si, A_Si, I_Si, rho_Si= 14, 28.0855, 173e-6, 2.329  # e, u, MeV, g/cm³

    # Electron mass
    m_e = 0.511  # MeV
    
    # speed of light in nat units
    c = 1
    
    # Lorentz gamma
    lorentz_gamma = gamma(energy=energy, mass=mass)
    lorentz_beta = beta(gamma_val=lorentz_gamma)
    beta_gamma = lorentz_beta*lorentz_gamma

    # Max energy transfer
    T_max = (2 * m_e* c**2 * beta_gamma**2) / (1 + (2 * lorentz_gamma * m_e / mass) + (m_e / mass)**2)

    # Prefactor
    pre_fac = K * Z_Si / A_Si * (charge / lorentz_beta)**2 * (1 if density_normalized else rho_Si)

    # Log term
    log_term = math.log(2 * m_e * (c * beta_gamma)**2 * T_max / I_Si**2)

    # Correction for high energy
    delta_correction = 0

    # Shell correction for low energy; very relevant here but no straight forward way to calculate?
    # see https://journals.aps.org/pra/pdf/10.1103/PhysRevA.65.052709
    # ~2% e.g. 0.02 for 10 MeV protons in Al, should consider to add this
    shell_correction = 0

    return pre_fac * (0.5 * log_term - lorentz_beta**2 - delta_correction - shell_correction)


def semi_empirical_mass_formula(n_protons, n_nucleons):

    nucleon_mass = n_protons * irrad_consts.m_p + (n_nucleons - n_protons) * irrad_consts.m_n

    volume_term = 15.67 * n_nucleons
    surface_term = -17.23 * n_nucleons ** (2./3.)
    coulomb_term = - 0.714 * n_protons * (n_protons - 1) * n_nucleons ** (-.33)
    symmetry_term = -93.15 * ((n_nucleons - n_protons) - n_protons) ** 2 / 4 * n_nucleons
    pair_term =0


    binding_energy = 15.67 * n_nucleons - 17.23 * n_nucleons ** (2./3.) - 0.714 * n_protons * (n_protons - 1) * n_nucleons ** (-.33)



