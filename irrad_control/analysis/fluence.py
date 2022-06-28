"""
This script contains the functions used for analysis of fluence distribution
"""

import logging
import numpy as np
from numba import njit  # Make analysis go brrrrr
from tqdm import tqdm  # Show progress

# Package imports
from irrad_control.analysis.constants import elementary_charge


# This is the main function
def generate_fluence_map(beam_data, scan_data, beam_sigma, bins=(100, 100)):
    """
    Generates a two-dimensional fluence map of the entire scan area from irrad_control output data.
    
    Parameters
    ----------
    beam_data : np.array, pytables.Table
        Beam data of irradiation
    scan_data : np.array, pytables.Table
        Scan data of irradiation
    beam_sigma : tuple
        Beam sigma of the 2D Gaussian beam profile in mm
    bins : tuple, optional
        Binning of the generated fluence map, by default (100, 100)
        CAUTION: the binning is numpy shape, therefore bins are (Y, X)

    Returns
    -------
    tuple: (np.ndarray, np.ndarray, np.ndarray, np.ndarray)
        Tuple containing fluence map, fluence map error, bin_centers_x, bin_centers_y
    """

    # Get number of rows; FIXME: get n_rows from *Irrad* data
    n_rows = np.max(scan_data['row']) + 1  # Rows start at 0
    
    # Get scan area; FIXME: get scan area from *Irrad* data
    # Everything in base unit mm
    scan_area_start = (scan_data[0]['row_start_x'], scan_data[n_rows]['row_start_y'])
    scan_area_end = (scan_data[0]['row_stop_x'], scan_data[0]['row_start_y'])

    # Fluence map
    fluence_map = np.zeros(shape=bins)
    fluence_map_error = np.zeros_like(fluence_map)

    # Create fluence map bin edge points
    map_bin_edges_y = np.linspace(0, abs(scan_area_start[1] - scan_area_end[1]), bins[0] + 1)
    map_bin_edges_x = np.linspace(0, abs(scan_area_end[0] - scan_area_start[0]), bins[1] + 1)
    
    # Create fluence map bin centers
    map_bin_centers_y = 0.5 * (map_bin_edges_y[:-1] + map_bin_edges_y[1:])
    map_bin_centers_x = 0.5 * (map_bin_edges_x[:-1] + map_bin_edges_x[1:])

    logging.info(f"Initializing fluence map of ({map_bin_edges_x[-1]:.2f}x{map_bin_edges_y[-1]:.2f}) mm² scan area in {bins[1]}x{bins[0]} bins")
    
    # Row bin times
    row_bin_transit_times = np.zeros_like(map_bin_centers_x)

    # Index that keeps track how far we have advanced trough the beam data
    current_row_idx = 0

    logging.info("Generating fluence distribution for Gaussian beam with {}_x={}mm, {}_y={}mm...".format(u'\u03c3', beam_sigma[0], u'\u03c3', beam_sigma[1]))

    # Loop over scanned rows
    for row_data in tqdm(scan_data, unit='rows'):

        current_row_idx = _process_row(row_data=row_data,
                                       beam_data=beam_data,
                                       fluence_map=fluence_map,
                                       fluence_map_error=fluence_map_error,
                                       row_bin_transit_times=row_bin_transit_times,
                                       map_bin_edges_x=map_bin_edges_x,
                                       map_bin_centers_x=map_bin_centers_x,
                                       map_bin_centers_y=map_bin_centers_y,
                                       beam_sigma=beam_sigma,
                                       scan_y_offset=scan_area_end[-1],
                                       current_row_idx=current_row_idx)

    logging.info(f"Finished generating fluence distribution.")                                       

    # Scale from protons / mm² (intrinsic unit) to neutrons / cm²
    fluence_map *= 100
    fluence_map_error *= 100

    return fluence_map, fluence_map_error, map_bin_centers_x, map_bin_centers_y


def extract_dut_map(fluence_map, map_bin_centers_x, map_bin_centers_y, dut_rectangle, center_symm=False):
    """
    Extracts the DUT region from the fluence map.

    Parameters
    ----------
    fluence_map : 2D np.ndarray
        Fluence map
    map_bin_centers_x : np.ndarray
        Bin centers of the fluence map in x a.k.a scan direction
    map_bin_centers_y : np.ndarray
        Bin centers of the fluence map in y a.k.a row direction
    dut_rectangle : tuple
        Relative position of the DUT rectangle in the form of (x_min, y_min, x_max, y_max) or (x_width, y_width) if *center_symm* is True
    center_symm: bool
        If True, the *dut_rectangle* has the form of (x_width, y_width) and the exctracted map is centered symmetrically

        (0, 0)-----------------------------------------------------------------------------     
             |                               Fluence map                                   |
             |                                                                             |
             |    --- (x_min, y_min) -----------------------------                         |
             |     |                 |                           |                         |
             |     |                 |                           |                         |
             |     | y_width         |         DUT map           |                         |
             |     |                 |                           |                         |
             |     |                 |                           |                         |
             |     |                 |                           |                         |
             |    ---                ----------------------------- (x_max, y_max)          |
             |                                                                             |
             |                       |----------x_width----------|                         |
              ------------------------------------------------------------------------------
    Returns
    -------
    tuple
        (2D np.ndarray, 1D np.ndarray, 1D np.ndarray) -> (DUT_fluence_map, DUT_map_bins_x, DUT_map_bins_y)
    """

    if center_symm and len(dut_rectangle) != 2:
        raise ValueError("*dut_rectangle* needs to be in the form of (x_width, y_width)")
    
    if not center_symm and len(dut_rectangle) != 4:
        raise ValueError("*dut_rectangle needs to be in the form of (x_min, y_min, x_max, y_max)")

    scan_area_x = map_bin_centers_x[-1] + (map_bin_centers_x[1] - map_bin_centers_x[0])/2.
    scan_area_y = map_bin_centers_y[-1] + (map_bin_centers_y[1] - map_bin_centers_y[0])/2.

    # Make map edges
    map_bin_edges_x = np.linspace(0, scan_area_x, len(map_bin_centers_x)+1)
    map_bin_edges_y = np.linspace(0, scan_area_y, len(map_bin_centers_y)+1)

    if center_symm:
        # Extract scan dimensions    
        dut_rectangle = ((scan_area_x - dut_rectangle[0])/2., (scan_area_y - dut_rectangle[1])/2.,
                         (scan_area_x + dut_rectangle[0])/2., (scan_area_y + dut_rectangle[1])/2.)

    x_min_idx, x_max_idx = np.searchsorted(map_bin_edges_x, dut_rectangle[0]), np.searchsorted(map_bin_edges_x, dut_rectangle[-2], side='right')
    y_min_idx, y_max_idx = np.searchsorted(map_bin_edges_y, dut_rectangle[1]), np.searchsorted(map_bin_edges_y, dut_rectangle[-1], side='right')

    return fluence_map[y_min_idx:y_max_idx, x_min_idx:x_max_idx], map_bin_centers_x[x_min_idx:x_max_idx], map_bin_centers_y[y_min_idx:y_max_idx]


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


@njit
def _process_row_wait(row_data, wait_beam_data, fluence_map, fluence_map_error, map_bin_edges_x, map_bin_centers_x, map_bin_centers_y, beam_sigma, scan_y_offset):
    """
    Processes the times where the beam is waiting on the periphery of the scan area or switches rows

    Parameters
    ----------
    row_data : numpy.ndarray
        Structured numpy array containing data of current row
    wait_beam_data : numpy.ndarray
        Beam data measured while waiting, in-between two rows
    fluence_map : numpy.ndarray
        Two-dimensional numpy.ndarray which holds the fluence distribution and is updated for this row
    fluence_map_error : numpy.ndarray
        Two-dimensional numpy.ndarray which holds the fluence error distribution and is updated for this row
    row_bin_transit_times : numpy.ndarray
        Flat numpy array which is used to hold the bin transit times for this row
    map_bin_edges_x : numpy.ndarray
        Flat numpy array holding the bin edges of the *fluence_map* in scan direction
    map_bin_centers_x : numpy.ndarray
        Flat numpy array holding the bin centers of the *fluence_map* in scan direction
    map_bin_centers_y : numpy.ndarray
        Flat numpy array holding the bin centers of the *fluence_map* in row direction
    beam_sigma : tuple, list, numpy.ndarray
        Iterable of beam sigmas with len(beam_sigma) == 2
    scan_y_offset : float
        Offset in mm which determines the relative 0 position in row direction: same as the y coordinate of row 0
    """
    
    # Determine the mean of the beam
    wait_mu_x = map_bin_edges_x[-1 if row_data['row'] % 2 else 0]
    wait_mu_y = row_data['row_start_y'] - scan_y_offset

    # Add variation to the uncertainty
    wait_protons_std = np.std(wait_beam_data['beam_current'])
    
    # Loop over currents and apply Gauss kernel at given position
    for i in range(wait_beam_data.shape[0] - 1):

        # Get beam current measurement
        wait_current = wait_beam_data[i]['beam_current']
        wait_current_error = wait_beam_data[i]['beam_current_error']

        # Calculate how many seconds this current was present while waiting
        wait_interval = wait_beam_data[i+1]['timestamp'] - wait_beam_data[i]['timestamp']

        # Integrate over *wait_interval* to obtain number of protons induced
        wait_protons = wait_current * wait_interval / elementary_charge
        wait_protons_error = wait_current_error * wait_interval / elementary_charge
        wait_protons_error = (wait_protons_error**2 + wait_protons_std**2)**.5

        # Apply Gaussian kernel for protons
        apply_gauss_2d_kernel(map_2d=fluence_map,
                              bin_centers_x=map_bin_centers_x,
                              bin_centers_y=map_bin_centers_y,
                              mu_x=wait_mu_x,
                              mu_y=wait_mu_y,
                              sigma_x=beam_sigma[0],
                              sigma_y=beam_sigma[1],
                              amplitude=wait_protons,
                              normalized=False)
        
        # Apply Gaussian kernel for proton error
        apply_gauss_2d_kernel(map_2d=fluence_map_error,
                              bin_centers_x=map_bin_centers_x,
                              bin_centers_y=map_bin_centers_y,
                              mu_x=wait_mu_x,
                              mu_y=wait_mu_y,
                              sigma_x=beam_sigma[0],
                              sigma_y=beam_sigma[1],
                              amplitude=wait_protons_error,
                              normalized=False)


@njit
def _process_row_scan(row_data, row_beam_data, fluence_map, fluence_map_error, row_bin_transit_times, map_bin_edges_x, map_bin_centers_x, map_bin_centers_y, beam_sigma, scan_y_offset):
    """
    Processes the scanning of a single row.

    Parameters
    ----------
    row_data : numpy.ndarray
        Structured numpy array containing data of current row
    row_beam_data : numpy.ndarray
        Beam data measured during scanning of this row; used for interpolation
    fluence_map : numpy.ndarray
        Two-dimensional numpy.ndarray which holds the fluence distribution and is updated for this row
    fluence_map_error : numpy.ndarray
        Two-dimensional numpy.ndarray which holds the fluence error distribution and is updated for this row
    row_bin_transit_times : numpy.ndarray
        Flat numpy array which is used to hold the bin transit times for this row
    map_bin_edges_x : numpy.ndarray
        Flat numpy array holding the bin edges of the *fluence_map* in scan direction
    map_bin_centers_x : numpy.ndarray
        Flat numpy array holding the bin centers of the *fluence_map* in scan direction
    map_bin_centers_y : numpy.ndarray
        Flat numpy array holding the bin centers of the *fluence_map* in row direction
    beam_sigma : tuple, list, numpy.ndarray
        Iterable of beam sigmas with len(beam_sigma) == 2
    scan_y_offset : float
        Offset in mm which determines the relative 0 position in row direction: same as the y coordinate of row 0
    """

    # Update row bin times
    _calc_bin_transit_times(bin_transit_times=row_bin_transit_times, bin_edges=map_bin_edges_x, scan_speed=row_data['row_scan_speed'], scan_accel=2500)  # FIXME: get accel from Irrad data

    # Determine communication timing overhead; assume symmetric dead time at row start and end
    row_start_overhead = (row_data['row_stop_timestamp'] - row_data['row_start_timestamp'] - row_bin_transit_times.sum()) / 2.0
    
    # Get the timestamp from which to check for beam currents, adjusted by the overhead
    actual_row_start_timestamp = row_data['row_start_timestamp'] + row_start_overhead

    # Calculate the timstamps which correspond to being in the map_bin_centers_x 
    row_bin_center_timestamps = actual_row_start_timestamp + np.cumsum(row_bin_transit_times) - row_bin_transit_times / 2.0
    
    # Interpolate the beam current measurements at the bin center for this scan
    row_bin_center_currents = np.interp(row_bin_center_timestamps, row_beam_data['timestamp'], row_beam_data['beam_current'])
    row_bin_center_current_errors = np.interp(row_bin_center_timestamps, row_beam_data['timestamp'], row_beam_data['beam_current_error'])

    # Integrate the current measurements with the times spent in each bin to calculate the amount of protons in the bin
    row_bin_center_protons = (row_bin_center_currents * row_bin_transit_times) / elementary_charge
    row_bin_center_proton_errors = (row_bin_center_current_errors * row_bin_transit_times) / elementary_charge
    row_bin_center_proton_errors = (row_bin_center_proton_errors**2 + np.std(row_bin_center_protons)**2)**.5

    # Loop over row times
    for i in range(row_bin_center_protons.shape[0]):
        
        # Update mean location of the distribution
        mu_x = map_bin_centers_x[(-(i+1) if row_data['row'] % 2 else i)]
        mu_y = row_data['row_start_y'] - scan_y_offset
        
        # Apply Gaussian kernel for protons
        apply_gauss_2d_kernel(map_2d=fluence_map,
                              bin_centers_x=map_bin_centers_x,
                              bin_centers_y=map_bin_centers_y,
                              mu_x=mu_x,
                              mu_y=mu_y,
                              sigma_x=beam_sigma[0],
                              sigma_y=beam_sigma[1],
                              amplitude=row_bin_center_protons[i],
                              normalized=False)

        # Apply Gaussian kernel for proton error
        apply_gauss_2d_kernel(map_2d=fluence_map_error,
                              bin_centers_x=map_bin_centers_x,
                              bin_centers_y=map_bin_centers_y,
                              mu_x=mu_x,
                              mu_y=mu_y,
                              sigma_x=beam_sigma[0],
                              sigma_y=beam_sigma[1],
                              amplitude=row_bin_center_proton_errors[i],
                              normalized=False)



@njit
def _process_row(row_data, beam_data, fluence_map, fluence_map_error, row_bin_transit_times, map_bin_edges_x, map_bin_centers_x, map_bin_centers_y, beam_sigma, scan_y_offset, current_row_idx):
    """
    Process the scanning and waiting / switching of a single row

    Parameters
    ----------
    row_data : numpy.ndarray
        Structured numpy array containing data of current row
    beam_data : numpy.ndarray, tables.Table
        Complete beam data which is sliced using *current_row_idx*
    fluence_map : numpy.ndarray
        Two-dimensional numpy.ndarray which holds the fluence distribution and is updated for this row
    fluence_map_error : numpy.ndarray
        Two-dimensional numpy.ndarray which holds the fluence error distribution and is updated for this row
    row_bin_transit_times : numpy.ndarray
        Flat numpy array which is used to hold the bin transit times for this row
    map_bin_edges_x : numpy.ndarray
        Flat numpy array holding the bin edges of the *fluence_map* in scan direction
    map_bin_centers_x : numpy.ndarray
        Flat numpy array holding the bin centers of the *fluence_map* in scan direction
    map_bin_centers_y : numpy.ndarray
        Flat numpy array holding the bin centers of the *fluence_map* in row direction
    beam_sigma : tuple, list, numpy.ndarray
        Iterable of beam sigmas with len(beam_sigma) == 2
    scan_y_offset : float
        Offset in mm which determines the relative 0 position in row direction: same as the y coordinate of row 0
    current_row_idx : int
        Integer corresponding to the index of beam data which has already been processed.
        Allows slicing beam data for (minimal) speed-up instead of always searching entire beam data (np.searchsorted is very, very fast)

    Returns
    -------
    int
        Index up to which beam data has been processed: used for slicing in next call of this function
    """

    # Advance slice of beam data which is relevant for this row
    current_beam_data = beam_data[current_row_idx:]

    # Get indice limits of beam currents measured during scanning of current row
    row_start_idx = np.searchsorted(current_beam_data['timestamp'], row_data['row_start_timestamp'], side='left')
    row_stop_idx = np.searchsorted(current_beam_data['timestamp'], row_data['row_stop_timestamp'], side='right')

    # Get beam data current measurements and corresponding timestamps of this row scan
    row_beam_data = current_beam_data[row_start_idx:row_stop_idx]
    
    # If this is not the first row, we want to process the waiting / switching row
    if current_row_idx > 0:
        
        # Get beam current measurements which were taken while waiting to start next row
        wait_beam_data = current_beam_data[:row_start_idx]
        
        # Process the currents measured while waiting
        _process_row_wait(row_data=row_data,
                          wait_beam_data=wait_beam_data,
                          fluence_map=fluence_map,
                          fluence_map_error=fluence_map_error,
                          map_bin_edges_x=map_bin_edges_x,
                          map_bin_centers_x=map_bin_centers_x,
                          map_bin_centers_y=map_bin_centers_y,
                          beam_sigma=beam_sigma,
                          scan_y_offset=scan_y_offset)

    # Process the scan
    _process_row_scan(row_data=row_data,
                      row_beam_data=row_beam_data,
                      fluence_map=fluence_map,
                      fluence_map_error=fluence_map_error,
                      row_bin_transit_times=row_bin_transit_times,
                      map_bin_edges_x=map_bin_edges_x,
                      map_bin_centers_x=map_bin_centers_x,
                      map_bin_centers_y=map_bin_centers_y,
                      beam_sigma=beam_sigma,
                      scan_y_offset=scan_y_offset)
    
    # Calculate index to return
    return current_row_idx + row_stop_idx
