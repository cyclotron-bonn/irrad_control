import numpy as np
import scipy.integrate as sint

from numba import njit

from irrad_control.analysis.utils import load_irrad_data


@njit
def gauss_2d_pdf(x, y, mu_x, mu_y, sigma_x, sigma_y, amplitude, normalized=False):

    norm_amplitude = amplitude if normalized else gauss_2d_norm(amplitude=amplitude, sigma_x=sigma_x, sigma_y=sigma_y)

    exponent = -0.5 * (((x - mu_x) ** 2 / sigma_x ** 2) + ((y - mu_y) ** 2 / sigma_y ** 2))

    return norm_amplitude * np.exp(exponent)


@njit
def gauss_2d_volume(amplitude, sigma_x, sigma_y):
    # https://en.wikipedia.org/wiki/Gaussian_function#Two-dimensional_Gaussian_function
    return 2 * np.pi * amplitude * sigma_x * sigma_y


@njit
def gauss_2d_norm(amplitude, sigma_x, sigma_y):
    return amplitude / (2 * np.pi * sigma_x * sigma_y)


@njit
def get_row_bin_times(row_bin_edges, scan_speed, scan_accel=2500.0):
    """
    Calculate the times spent in each bin and return array

    Parameters
    ----------
    row_bin_edges: np.ndarry
        Array of bin edges of scan rows
    scan_speed: float
        Scan speed in mm/s
    scan_accel: float
        De/acceleration with which *scan_speed* is approached/reduced in mm/s^2

    Returns
    -------
    Array of floats containing time in seconds which is spend in each bin
    """

    # Calculate the size of each bin
    row_bin_sizes = row_bin_edges[1:] - row_bin_edges[:-1]

    # Create return array
    row_bin_times = np.zeros(shape=len(row_bin_sizes))

    # Hold current speed
    current_speed = 0

    # Time needed to accelerate / decelerate to / from *scan_speed* in seconds
    # v = a * t
    de_accel_time = scan_speed / scan_accel

    # Distance covered for de/acceleration
    # s = a/2 * t^2
    de_accel_dist = scan_accel / 2. * de_accel_time ** 2.

    # Get index up to / from which is accelerated / decelerated
    idx = np.searchsorted(row_bin_edges, de_accel_dist)

    # Calculate the row bin times for the constant bins
    row_bin_times[idx:-idx] = row_bin_sizes[idx:-idx] / scan_speed

    # Calculate the row bin times for the acceleration / deceleration phase
    for i in range(idx):
        reverse_idx = -(i + 1)
        # Calculate time
        row_bin_times[i] = ((2 * row_bin_sizes[i] * scan_accel + current_speed ** 2) ** 0.5 - current_speed) / scan_accel
        row_bin_times[reverse_idx] = ((2 * row_bin_sizes[reverse_idx] * scan_accel + current_speed ** 2) ** 0.5 - current_speed) / scan_accel

        # Update speed
        current_speed += scan_accel * row_bin_times[i]

    return row_bin_times


def generate_fluence_map(bins=(100, 100), beam_sigma=(3.0, 4.0)):


    # Load beam and scan data and config of run; FIXME: get *Irrad* data
    data, config = load_irrad_data(data_file='examples/example_data.h5',
                                   config_file='examples/example_config.yaml',
                                   specify_entries=('Beam', 'Scan'))

    # Generate for each server
    for _, server_config in config['server'].items():

        server_name = server_config['name']

        # Extract scan an beam data as NumPy.ndarray
        beam_data, scan_data = data[server_name]['Beam'][:], data[server_name]['Scan'][:]


        # Get number of rows; FIXME: get n_rows from *Irrad* data
        n_rows = scan_data[0]['n_rows']

        # Fluence map
        fluence_map = np.zeros(shape=bins)

        # Get scan area; FIXME: get scan area from *Irrad* data
        # Everything in base unit mm
        scan_area_start = (scan_data[0]['row_start_x'], scan_data[n_rows]['row_start_y'])
        scan_area_end = (scan_data[0]['row_stop_x'], scan_data[0]['row_start_y'])

        # Create fluence map bin edge points
        map_bin_edges_x = np.linspace(0, scan_area_end[0] - scan_area_start[0], bins[0] + 1)
        map_bin_edges_y = np.linspace(0, scan_area_start[1] - scan_area_end[1], bins[1] + 1)

        # Create fluence map bin centers
        map_bin_centers_x = 0.5 * (map_bin_edges_x[:-1] + map_bin_edges_x[1:])
        map_bin_centers_y = 0.5 * (map_bin_edges_y[:-1] + map_bin_edges_y[1:])

        for i in range(len(scan_data)):
            print(scan_data[i]['row_start_timestamp'])

        # Loop over scanned rows
        for row_data in scan_data:

            # Get beam currents measured during scanning of current row
            beam_start_idx = np.searchsorted(beam_data['timestamp'], row_data['row_start_timestamp'], side='left')
            beam_stop_idx = np.searchsorted(beam_data['timestamp'], row_data['row_stop_timestamp'], side='right')
            row_currents = beam_data['beam_current'][beam_start_idx:beam_stop_idx]
            row_bin_times = get_row_bin_times(row_bin_edges=map_bin_edges_x, scan_speed=row_data['row_scan_speed'])  # FIXME: get accel from Irrad data
            row_bin_timestamps = np.cumsum(row_bin_times) + row_data['row_start_timestamp']



def fluence_2d_dist():

    data_file = 0


if __name__ == '__main__':
    generate_fluence_map()

    mu_x, mu_y = 0, 0
    sigma_x = sigma_y = .33
    beam_volume = 1e-6  # A => protons / s

    integral = sint.dblquad(gauss_2d_pdf, a=-6*sigma_x, b=6*sigma_x, gfun=-6*sigma_y, hfun=6*sigma_y, args=(mu_x, mu_y,sigma_x, sigma_y, beam_volume, ))

    print(f'Volume from function: {gauss_2d_volume(amplitude=gauss_2d_norm(beam_volume, sigma_x, sigma_y), sigma_x=sigma_x, sigma_y=sigma_y):.3E}')
    print(f'Volume from integral: {integral[0]:.3E}')

    # Load data and config of run
    data, config = load_irrad_data(data_file='examples/example_data.h5',
                                   config_file='examples/example_config.yaml',
                                   specify_entries=('Beam', 'Scan'))

    # Get number of rows
    n_rows = data['HSR']['Scan'][0]['n_rows']

    # Get scan area
    x_lower, x_upper = data['HSR']['Scan'][0]['row_start_x'], data['HSR']['Scan'][0]['row_stop_x']
    y_lower, y_upper = data['HSR']['Scan'][0]['row_start_y'], data['HSR']['Scan'][n_rows]['row_start_y']

    # Make bins for fluence distribution
    bins = (100, 100)

    # Create empty hist
    fluence_hist = np.zeros(shape=bins)

    # Create bin edges; set scan start to (0, 0)
    x_edges = np.linspace(0, x_upper-x_lower, bins[0] + 1)
    y_edges = np.linspace(0, y_upper-y_lower, bins[1] + 1)

    # Create bin centers
    x_centers = 0.5 * (x_edges[:-1] + x_edges[1:])
    y_centers = 0.5 * (y_edges[:-1] + y_edges[1:])

    print(x_centers.shape, fluence_hist.shape)
