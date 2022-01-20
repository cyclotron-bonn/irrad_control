"""
This script contains the functions used for analysis of irradiation tables
CAUTION: the current version of this file operates on a version of
irradiation tables which is deprecated but was need to develop the analysis
due to a bug in storing timestamps in the current development state
(see https://github.com/SiLab-Bonn/irrad_control/issues/59).
"""

import numpy as np
from numba import njit  # Make analysis go brrrrr
from tqdm import tqdm  # Show progress

# Package imports
from irrad_control.analysis.constants import elementary_charge
from irrad_control.analysis.formulas import tid_scan


@njit
def gauss_2d_pdf(x, y, mu_x, mu_y, sigma_x, sigma_y, amplitude, normalized=False):
    """
    2D normal distribution PDF according to
    https://en.wikipedia.org/wiki/Gaussian_function#Two-dimensional_Gaussian_function

    Parameters
    ----------
    x : float
        Location along first dimension
    y : float
        Location along second dimension
    mu_x : float
        Mean of distribution in first dimension
    mu_y : float
        Mean of distribution in second dimension
    sigma_x : float
        Standard deviation in first dimension
    sigma_y : float
        Standard deviation in second dimension
    amplitude : float
        Amplitude of distribution; must be normalized for correct results e.g. integral(gauss_2D_pdf) == 1
    normalized : bool, optional
        Whether to normaliz amplitude, by default False

    Returns
    -------
    float
        Probability at given input
    """
    # Amplitude; normalize if needed to satisfy integral(gauss_2D_pdf) == 1
    norm_amplitude = amplitude if normalized else gauss_2d_norm(amplitude=amplitude, sigma_x=sigma_x, sigma_y=sigma_y)

    # Exponent
    exponent = -0.5 * (np.square((x - mu_x) / sigma_x) + np.square((y - mu_y) / sigma_y))

    return norm_amplitude * np.exp(exponent)


@njit
def gauss_2d_volume(amplitude, sigma_x, sigma_y):
    """
    Volume under 2D Gaussian distribution according to
    https://en.wikipedia.org/wiki/Gaussian_function#Two-dimensional_Gaussian_function

    Parameters
    ----------
    amplitude : float
        Amplitude of distribution; must be normalized for correct results e.g. integral(gauss_2D_pdf) == 1
    sigma_x : float
        Standard deviation in first dimension
    sigma_y : float
        Standard deviation in second dimension

    Returns
    -------
    float
        Volume under 2D Gaussian with given input parameters
    """
    return 2 * np.pi * amplitude * sigma_x * sigma_y


@njit
def gauss_2d_norm(amplitude, sigma_x, sigma_y):
    """
    Calculate normalized amplitude to satisfy integral(gauss_2D_pdf) == 1
    
    Parameters
    ----------
    amplitude : float
        Amplitude of distribution to normalize
    sigma_x : float
        Standard deviation in first dimension
    sigma_y : float
        Standard deviation in second dimension

    Returns
    -------
    float
        Normalized amplitude
    """
    return amplitude / (2 * np.pi * sigma_x * sigma_y)


@njit
def apply_gauss_2d_kernel(map_2d, bin_centers_x, bin_centers_y, mu_x, mu_y, sigma_x, sigma_y, amplitude, normalized, skip_sigmas=6):
    """
    Applies a 2D Gaussian kernel on *map_2d*, along given bin centers in x and y dimension. See *gauss_2d_pdf* function
    for more info.

    Parameters
    ----------
    map_2d : np.ndarray
        Input map to apply kernel to which satisfies len(map_2d.shape)==2
    bin_centers_x : np.ndarray
        [description]
    bin_centers_y : np.ndarray
        [description]
    mu_x : float
        Mean of distribution in first dimension
    mu_y : float
        Mean of distribution in second dimension
    sigma_x : float
        Standard deviation in first dimension
    sigma_y : float
        Standard deviation in second dimension
    amplitude : float
        Amplitude of distribution; must be normalized for correct results e.g. integral(gauss_2D_pdf) == 1
    normalized : bool, optional
        Whether to normaliz amplitude, by default False
    skip_sigmas: float, int
        Skip calculation if point on *map_2d* is more tha this amountof sigmas away in respective dimension
        Decreasing this increases performance at the cost of accuracy. Minimum value is 3
    """
    # Check
    if skip_sigmas < 3:
        raise ValueError("Minimum of skip_sigmas is 3 to maintain reasonable accuracy")
    
    # Loop over y indices
    for j in range(map_2d.shape[0]):
        
        # Extract current y coordinate
        y_coord = bin_centers_y[j]
        
        # Check y coordinate
        if abs(y_coord - mu_y) > skip_sigmas * sigma_y:
            continue
        
        # Loop over x indices
        for i in range(map_2d.shape[1]):

            # Extract current x coordinate            
            x_coord = bin_centers_x[i]

            # Check x coordinate
            if abs(x_coord - mu_x) > skip_sigmas * sigma_x:
                continue
            
            # Apply Gaussian
            map_2d[j, i] += gauss_2d_pdf(x=x_coord,
                                         y=y_coord,
                                         mu_x=mu_x,
                                         mu_y=mu_y,
                                         sigma_x=sigma_x,
                                         sigma_y=sigma_y,
                                         amplitude=amplitude,
                                         normalized=normalized)


@njit
def _calc_bin_transit_times(bin_transit_times, bin_edges, scan_speed, scan_accel):
    """
    Calculate the time it takes to transit each bin in scan direction and fill array

    Parameters
    ----------
    bin_transit_times: np.ndarray
        Array to fill the row bin times into
    bin_edges: np.ndarray
        Array of bin edges of scan rows
    scan_speed: float
        Scan speed in mm/s
    scan_accel: float
        De/acceleration with which *scan_speed* is approached/reduced in mm/s^2
    """

    # Calculate the size of each bin
    bin_sizes = bin_edges[1:] - bin_edges[:-1]

    # Hold current speed
    current_speed = 0

    # Time needed to accelerate / decelerate to / from *scan_speed* in seconds
    # v = a * t
    de_accel_time = scan_speed / scan_accel

    # Distance covered for de/acceleration
    # s = a/2 * t^2
    de_accel_dist = scan_accel / 2. * de_accel_time ** 2.

    # Get index up to / from which is accelerated / decelerated
    idx = np.searchsorted(bin_edges, de_accel_dist)

    # Calculate the row bin times for the constant bins
    bin_transit_times[idx:-idx] = bin_sizes[idx:-idx] / scan_speed

    # Calculate the row bin times for the acceleration / deceleration phase
    for i in range(idx):
        reverse_idx = -(i + 1)
        # Calculate time
        bin_transit_times[i] = ((2 * bin_sizes[i] * scan_accel + current_speed ** 2) ** 0.5 - current_speed) / scan_accel
        bin_transit_times[reverse_idx] = ((2 * bin_sizes[reverse_idx] * scan_accel + current_speed ** 2) ** 0.5 - current_speed) / scan_accel

        # Update speed
        current_speed += scan_accel * bin_transit_times[i]