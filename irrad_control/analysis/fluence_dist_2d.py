import numpy as np
import scipy.integrate as sint
import tables as tb
import matplotlib.pyplot as plt
import time
from numba import njit

from irrad_control.analysis.constants import elementary_charge
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
def calc_row_bin_times(row_bin_times, row_bin_edges, scan_speed, scan_accel):
    """
    Calculate the times spent in each bin and return array

    Parameters
    ----------
    row_bin_times: np.ndarray
        Array to fill the row bin times into
    row_bin_edges: np.ndarray
        Array of bin edges of scan rows
    scan_speed: float
        Scan speed in mm/s
    scan_accel: float
        De/acceleration with which *scan_speed* is approached/reduced in mm/s^2
    """

    # Calculate the size of each bin
    row_bin_sizes = row_bin_edges[1:] - row_bin_edges[:-1]

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

@njit
def apply_gauss_2d_kernel(map_2d, bin_centers_x, bin_centers_y, mu_x, mu_y, sigma, amplitude, normalized=False):

    for i in range(map_2d.shape[0]):
        for j in range(map_2d.shape[1]):
            map_2d[i, j] += gauss_2d_pdf(x=bin_centers_x[j],
                                         y=bin_centers_y[i],
                                         mu_x=mu_x,
                                         mu_y=mu_y,
                                         sigma_x=sigma[0],
                                         sigma_y=sigma[1],
                                         amplitude=amplitude,
                                         normalized=normalized)



def generate_2d_fluence_map(beam_data, scan_data, bins=(100, 100), beam_sigma=(3.0, 4.0)):  # FIXME: bins are switched currently
    """
    

    Parameters
    ----------
    beam_data : np.array
        Beam data of irradiation
    scan_data : np.array
        Scan data of irradiation
    bins : tuple, optional
        Binning of the generated fluence map, by default (100, 100)
    beam_sigma : tuple, optional
        Beam sigma of the 2D Gaussian beam profile , by default (3.0, 4.0)
    """

    # Get number of rows; FIXME: get n_rows from *Irrad* data
    n_rows = np.max(scan_data['row']) + 1  # Rows start at 0

    # Fluence map
    fluence_map = np.zeros(shape=bins)

    # Get scan area; FIXME: get scan area from *Irrad* data
    # Everything in base unit mm
    scan_area_start = (scan_data[0]['x_start'], scan_data[n_rows]['y_start'])
    scan_area_end = (scan_data[0]['x_stop'], scan_data[0]['y_start'])
    
    print(scan_area_start)
    print(scan_area_end)

    # Create fluence map bin edge points
    map_bin_edges_x = np.linspace(0, abs(scan_area_end[0] - scan_area_start[0]), bins[0] + 1)
    map_bin_edges_y = np.linspace(0, abs(scan_area_start[1] - scan_area_end[1]), bins[1] + 1)
    
    # Create fluence map bin centers
    map_bin_centers_x = 0.5 * (map_bin_edges_x[:-1] + map_bin_edges_x[1:])
    map_bin_centers_y = 0.5 * (map_bin_edges_y[:-1] + map_bin_edges_y[1:])
    print(map_bin_centers_y)

    # Row bin times
    row_bin_times = np.zeros_like(map_bin_centers_x)

    # Loop over scanned rows
    for i, row_data in enumerate(scan_data):
        
        # Update row bin times
        calc_row_bin_times(row_bin_times=row_bin_times, row_bin_edges=map_bin_edges_x, scan_speed=row_data['speed'], scan_accel=2500)  # FIXME: get accel from Irrad data

        # Determine communication timing overhead; assume symmetric dead time at row start and end
        row_start_overhead = (row_data['timestamp_stop'] - row_data['timestamp_start'] - row_bin_times.sum()) / 2.
        
        # Get the timestamp from which to check for beam currents
        actual_row_start_timestamp = row_data['timestamp_start'] + row_start_overhead

        # Get beam currents measured during scanning of current row
        beam_start_idx = np.searchsorted(beam_data['timestamp'], row_data['timestamp_start'], side='left')
        beam_stop_idx = np.searchsorted(beam_data['timestamp'], row_data['timestamp_stop'], side='right')
        
        row_currents = beam_data['current_analog'][beam_start_idx:beam_stop_idx]
        row_timestamps = beam_data['timestamp'][beam_start_idx:beam_stop_idx]

        row_bin_center_currents = np.interp(actual_row_start_timestamp + row_bin_times, row_timestamps, row_currents)

        row_bin_center_protons = (row_bin_center_currents * row_bin_times) / elementary_charge

        #Loop over row times
        for k in range(row_bin_center_currents.shape[0]):
                # Position is from right to left
            mu_x = map_bin_centers_x[-(k+1) if row_data['row'] else k]
            mu_y = row_data['y_start'] - scan_area_end[-1]
            protons = row_bin_center_protons[k]
            start = time.time()
            #print(protons)
            #Now loop over map
            apply_gauss_2d_kernel(map_2d=fluence_map,
                                  bin_centers_x=map_bin_centers_x,
                                  bin_centers_y=map_bin_centers_y,
                                  mu_x=mu_x,
                                  mu_y=mu_y,
                                  sigma=beam_sigma,
                                  #sigma_y=beam_sigma[1],
                                  amplitude=protons,
                                  normalized=False)

            # for i in range(fluence_map.shape[0]):
            #     for j in range(fluence_map.shape[1]):

            #         fluence_map[i, j] += gauss_2d_pdf(x=map_bin_centers_x[j],
            #                                           y=map_bin_centers_y[i],
            #                                           mu_x=mu_x,
            #                                           mu_y=mu_y,
            #                                           sigma_x=beam_sigma[0],
            #                                           sigma_y=beam_sigma[1],
            #                                           amplitude=protons,
            #                                           normalized=False)
            print(time.time()- start)
        if i == 20:
            break
            
        
    plt.imshow(fluence_map)
    plt.show()
           

def fill_fluence_map(fluence_map, map_bin_centers, row_currents, row_timestamps, row_bin_times):
    pass


# # This is valid for the new irrad data types
# def generate_fluence_map(bins=(100, 100), beam_sigma=(3.0, 4.0)):


#     # Load beam and scan data and config of run; FIXME: get *Irrad* data
#     data, config = load_irrad_data(data_file='examples/example_data.h5',
#                                    config_file='examples/example_config.yaml',
#                                    specify_entries=('Beam', 'Scan'))

#     # Generate for each server
#     for _, server_config in config['server'].items():

#         server_name = server_config['name']

#         # Extract scan an beam data as NumPy.ndarray
#         beam_data, scan_data = data[server_name]['Beam'][:], data[server_name]['Scan'][:]


#         # Get number of rows; FIXME: get n_rows from *Irrad* data
#         n_rows = scan_data[0]['n_rows']

#         # Fluence map
#         fluence_map = np.zeros(shape=bins)

#         # Get scan area; FIXME: get scan area from *Irrad* data
#         # Everything in base unit mm
#         scan_area_start = (scan_data[0]['row_start_x'], scan_data[n_rows]['row_start_y'])
#         scan_area_end = (scan_data[0]['row_stop_x'], scan_data[0]['row_start_y'])

#         # Create fluence map bin edge points
#         map_bin_edges_x = np.linspace(0, scan_area_end[0] - scan_area_start[0], bins[0] + 1)
#         map_bin_edges_y = np.linspace(0, scan_area_start[1] - scan_area_end[1], bins[1] + 1)

#         # Create fluence map bin centers
#         map_bin_centers_x = 0.5 * (map_bin_edges_x[:-1] + map_bin_edges_x[1:])
#         map_bin_centers_y = 0.5 * (map_bin_edges_y[:-1] + map_bin_edges_y[1:])

#         for i in range(len(scan_data)):
#             print(scan_data[i]['row_start_timestamp'])

#         # Loop over scanned rows
#         for row_data in scan_data:

#             # Get beam currents measured during scanning of current row
#             beam_start_idx = np.searchsorted(beam_data['timestamp'], row_data['row_start_timestamp'], side='left')
#             beam_stop_idx = np.searchsorted(beam_data['timestamp'], row_data['row_stop_timestamp'], side='right')
#             row_currents = beam_data['beam_current'][beam_start_idx:beam_stop_idx]
#             row_bin_times = get_row_bin_times(row_bin_edges=map_bin_edges_x, scan_speed=row_data['row_scan_speed'])  # FIXME: get accel from Irrad data
#             row_bin_timestamps = np.cumsum(row_bin_times) + row_data['row_start_timestamp']


if __name__ == '__main__':

    mu_x, mu_y = 0, 0
    sigma_x = sigma_y = .33
    beam_volume = 1e-6  # A => protons / s

    integral = sint.dblquad(gauss_2d_pdf, a=-6*sigma_x, b=6*sigma_x, gfun=-6*sigma_y, hfun=6*sigma_y, args=(mu_x, mu_y,sigma_x, sigma_y, beam_volume, ))

    print(f'Volume from function: {gauss_2d_volume(amplitude=gauss_2d_norm(beam_volume, sigma_x, sigma_y), sigma_x=sigma_x, sigma_y=sigma_y):.3E}')
    print(f'Volume from integral: {integral[0]:.3E}')

    # Load test data
    with tb.open_file('./examples/fixed_timestamps_data.h5', 'r') as irrad_data:
        
        beam_data = irrad_data.root.Hochstromraum2.Beam[:]
        scan_data = irrad_data.root.Hochstromraum2.Fluence[:]

        generate_2d_fluence_map(beam_data=beam_data,
                                scan_data=scan_data)
    