import numpy as np
import tables as tb
import matplotlib.pyplot as plt


from tqdm import tqdm
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
def apply_gauss_2d_kernel(map_2d, bin_centers_x, bin_centers_y, mu_x, mu_y, sigma_x, sigma_y, amplitude, normalized, skip_sigma=6):

    if skip_sigma < 3:
        raise ValueError('No')

    for j in range(map_2d.shape[0]):
        
        y_coord = bin_centers_y[j]

        if abs(y_coord-mu_y) > skip_sigma * sigma_y:
            continue

        for i in range(map_2d.shape[1]):
            
            x_coord = bin_centers_x[i]

            if abs(x_coord-mu_x) > skip_sigma * sigma_x:
                continue

            map_2d[j, i] += gauss_2d_pdf(x=x_coord,
                                         y=y_coord,
                                         mu_x=mu_x,
                                         mu_y=mu_y,
                                         sigma_x=sigma_x,
                                         sigma_y=sigma_y,
                                         amplitude=amplitude,
                                         normalized=normalized)

@njit
def process_row_scan(row_data, beam_data, row_bin_times, fluence_map, map_bin_edges_x, map_bin_centers_x, map_bin_centers_y, beam_sigma, scan_y_offset, prev_row_idx):

    # Advance slice of beam data which is relevant for this row
    relevant_beam_data = beam_data[prev_row_idx:]

    # Get beam currents measured during scanning of current row
    row_start_idx = np.searchsorted(relevant_beam_data['timestamp'], row_data['timestamp_start'], side='left')
    row_stop_idx = np.searchsorted(relevant_beam_data['timestamp'], row_data['timestamp_stop'], side='right')
    next_row_idx = prev_row_idx + row_stop_idx

    # Get beam currents while waiting to start next row after scan of first row
    if prev_row_idx > 0:
        row_waiting_currents = relevant_beam_data[:row_start_idx]
        wait_mu_x = map_bin_edges_x[-1 if row_data['row'] % 2 else 0]
        wait_mu_y = row_data['y_start'] - scan_y_offset
        # Loop over currents and apply Gauss kernel at given position
        for i in range(row_waiting_currents.shape[0] - 1):

            wait_current = row_waiting_currents[i]['current_analog']

            # Calculate how many seconds this current was present while waiting
            wait_interval = row_waiting_currents[i+1]['timestamp'] - row_waiting_currents[i]['timestamp']

            wait_protons = wait_current * wait_interval / elementary_charge

            #Now loop over map
            apply_gauss_2d_kernel(map_2d=fluence_map,
                                 bin_centers_x=map_bin_centers_x,
                                 bin_centers_y=map_bin_centers_y,
                                 mu_x=wait_mu_x,
                                 mu_y=wait_mu_y,
                                 sigma_x=beam_sigma[0],
                                 sigma_y=beam_sigma[1],
                                 amplitude=wait_protons,
                                 normalized=False)

    # Update row bin times
    calc_row_bin_times(row_bin_times=row_bin_times, row_bin_edges=map_bin_edges_x, scan_speed=row_data['speed'], scan_accel=2500)  # FIXME: get accel from Irrad data

    # Determine communication timing overhead; assume symmetric dead time at row start and end
    row_start_overhead = (row_data['timestamp_stop'] - row_data['timestamp_start'] - row_bin_times.sum()) / 2.
    
    # Get the timestamp from which to check for beam currents
    actual_row_start_timestamp = row_data['timestamp_start'] + row_start_overhead
    
    row_currents = relevant_beam_data['current_analog'][row_start_idx:row_stop_idx]
    row_timestamps = relevant_beam_data['timestamp'][row_start_idx:row_stop_idx]

    row_bin_center_currents = np.interp(actual_row_start_timestamp + row_bin_times, row_timestamps, row_currents)

    row_bin_center_protons = (row_bin_center_currents * row_bin_times) / elementary_charge

    #Loop over row times
    for k in range(row_bin_center_currents.shape[0]):
        # Position is from right to left
        mu_x_idx = (-(k+1) if row_data['row'] % 2 else k)
        mu_x = map_bin_centers_x[mu_x_idx]
        mu_y = row_data['y_start'] - scan_y_offset
        protons = row_bin_center_protons[k]
        #Now loop over map
        apply_gauss_2d_kernel(map_2d=fluence_map,
                              bin_centers_x=map_bin_centers_x,
                              bin_centers_y=map_bin_centers_y,
                              mu_x=mu_x,
                              mu_y=mu_y,
                              sigma_x=beam_sigma[0],
                              sigma_y=beam_sigma[1],
                              amplitude=protons,
                              normalized=False)

    return next_row_idx

def generate_2d_fluence_map(beam_data, scan_data, bins=(80, 100), beam_sigma=(4.72, 3.23)):
    """
    

    Parameters
    ----------
    beam_data : np.array
        Beam data of irradiation
    scan_data : np.array
        Scan data of irradiation
    bins : tuple, optional
        Binning of the generated fluence map, by default (100, 100)
        CAUTION: the binning is numpy shape, therefore bins are (Y, X)
    beam_sigma : tuple, optional
        Beam sigma of the 2D Gaussian beam profile , by default (4.72, 3.23)
    """

    # Get number of rows; FIXME: get n_rows from *Irrad* data
    n_rows = np.max(scan_data['row']) + 1  # Rows start at 0
    
    # Get scan area; FIXME: get scan area from *Irrad* data
    # Everything in base unit mm
    scan_area_start = (scan_data[0]['x_start'], scan_data[n_rows]['y_start'])
    scan_area_end = (scan_data[0]['x_stop'], scan_data[0]['y_start'])

    # Fluence map
    fluence_map = np.zeros(shape=bins)

    # Create fluence map bin edge points
    map_bin_edges_y = np.linspace(0, abs(scan_area_start[1] - scan_area_end[1]), bins[0] + 1)
    map_bin_edges_x = np.linspace(0, abs(scan_area_end[0] - scan_area_start[0]), bins[1] + 1)
    
    # Create fluence map bin centers
    map_bin_centers_y = 0.5 * (map_bin_edges_y[:-1] + map_bin_edges_y[1:])
    map_bin_centers_x = 0.5 * (map_bin_edges_x[:-1] + map_bin_edges_x[1:])
    

    # Row bin times
    row_bin_times = np.zeros_like(map_bin_centers_x)

    # Index that keeps track how far we have advanced trough the beam data
    prev_row_idx = 0

    # Loop over scanned rows
    for row_data in tqdm(scan_data, unit='rows'):

        prev_row_idx = process_row_scan(row_data=row_data,
                                        beam_data=beam_data,
                                        row_bin_times=row_bin_times,
                                        fluence_map=fluence_map,
                                        map_bin_edges_x=map_bin_edges_x,
                                        map_bin_centers_x=map_bin_centers_x,
                                        map_bin_centers_y=map_bin_centers_y,
                                        beam_sigma=beam_sigma,
                                        scan_y_offset=scan_area_end[-1],
                                        prev_row_idx=prev_row_idx)

    return fluence_map, map_bin_centers_x, map_bin_centers_y

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

    # Load test data
    with tb.open_file('./examples/fixed_timestamps_data.h5', 'r') as irrad_data:
        
        beam_data = irrad_data.root.Hochstromraum2.Beam[:]
        scan_data = irrad_data.root.Hochstromraum2.Fluence[:]

        # Make plots for different beam sigmas
        beam_sigmas = [(4.72, 3.23), (3., 2.5), (2., 1.5), (1.5, 1.)]

        # Loop
        for sigma in beam_sigmas:


            fluence_map, x, y = generate_2d_fluence_map(beam_data=beam_data, scan_data=scan_data, beam_sigma=sigma)
            fluence_map *= 400  # Convert bin entries from protons/mm² to neutrons/cm²
            
            dut_idxs = [np.searchsorted(y, (40-11.5)/2.), np.searchsorted(y, 40-(40-20)/2., side='left'),
                        np.searchsorted(x, (50-11.5)/2.), np.searchsorted(x, 50-(50-20)/2., side='left')]
            

            x, y = np.meshgrid(x, y)

            dut_map = fluence_map[dut_idxs[0]:dut_idxs[1], dut_idxs[-2]:dut_idxs[-1]]
            dut_x, dut_y = x[dut_idxs[0]:dut_idxs[1], dut_idxs[-2]:dut_idxs[-1]], y[dut_idxs[0]:dut_idxs[1], dut_idxs[-2]:dut_idxs[-1]]

            for i, stuff in enumerate([(fluence_map, x, y), (dut_map, dut_x, dut_y)]):
                
                _map, map_x, map_y = stuff
                map_mean, map_std = _map.mean(), _map.std()

                # Make figure for 3D
                #_x, _y = np.meshgrid(map_x, map_y)
                fig, ax = plt.subplots(figsize=(8, 6), tight_layout=True, subplot_kw={"projection": "3d"})
                surf = ax.plot_surface(map_x, map_y, _map, antialiased=False, cmap='viridis')
                ax.view_init(azim=-115, elev=25)
                if i==0:
                    xlabel = 'Scan area horizontal [mm]'
                    ylabel = 'Scan area vertical [mm]'
                    title = r"Fluence scan area for $\sigma_\mathrm{beam}$ = "+"({}, {}) mm".format(*sigma)
                    fname_3d = "fluence_scan_area_3d_beam_sigma_fasta_{}_{}.pdf".format(*sigma)
                    fname_2d = "fluence_scan_area_2d_beam_sigma_fasta_{}_{}.pdf".format(*sigma)
                    extent = (0, 50, 40, 0)
                    cs = ax.contourf(x, y, fluence_map, zdir='z', levels=10, offset=-1e14, cmap='viridis')
                    ax.set_zlim(-(0.05*_map.max()), _map.max())
                    plt.clabel(cs, fontsize=15, inline=True)
                else:
                    xlabel = 'DUT area horizontal [mm]'
                    ylabel = 'DUT area vertical [mm]'
                    title = r"Fluence DUT area for $\sigma_\mathrm{beam}$ = "+"({}, {}) mm".format(*sigma)
                    fname_3d = "fluence_dut_area_3d_beam_sigma_fasta_{}_{}.pdf".format(*sigma)
                    fname_2d = "fluence_dut_area_2d_beam_sigma_fasta_{}_{}.pdf".format(*sigma)
                    extent = (0, 20, 11.5, 0)
                    ax.set_zlim(map_mean-(6*map_std + 0.01*map_mean), map_mean+(6*map_std + 0.01*map_mean))
                ax.set_xlabel(xlabel)
                ax.set_ylabel(ylabel)
                ax.set_zlabel('Fluence [n$_\mathrm{eq}$ / cm$^2$]')
                ax.set_title(title)
                cbar = fig.colorbar(surf)
                cbar.set_label(r"Fluence [n$_\mathrm{eq}$ / cm$^2$]")
                plt.savefig(fname_3d)
                #plt.show()
                fig, ax = plt.subplots(figsize=(8, 6), tight_layout=True)
                im = ax.imshow(_map, origin='upper', extent=extent, cmap='viridis')
                ax.set_xlabel(xlabel)
                ax.set_ylabel(ylabel)
                ax.set_title(title)
                ax.text(5, 5, "Mean = {:.2E}{}{:.2E} {}".format(map_mean, u'\u00B1', map_std, r'n$_\mathrm{eq}$ / cm$^2$'))
                cbar = fig.colorbar(im)
                cbar.set_label(r"Fluence [n$_\mathrm{eq}$ / cm$^2$]")
                plt.savefig(fname_2d)
                #plt.show()