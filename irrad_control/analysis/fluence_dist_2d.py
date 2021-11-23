import numpy as np
import scipy.integrate as sint

from numba import njit

from irrad_control.analysis.utils import load_irrad_data


@njit
def gauss_2d_pdf(x, y, mu_x, mu_y, sigma_x, sigma_y, volume, normalized=False):

    norm_vol = volume if normalized else gauss_2d_norm(volume=volume, sigma_x=sigma_x, sigma_y=sigma_y)

    exponent = -0.5 * (((x - mu_x) ** 2 / sigma_x ** 2) + ((y - mu_y) ** 2 / sigma_y ** 2))

    return norm_vol * np.exp(exponent)

@njit
def gauss_2d_volume(amplitude, sigma_x, sigma_y):
    # https://en.wikipedia.org/wiki/Gaussian_function#Two-dimensional_Gaussian_function
    return 2 * np.pi * amplitude * sigma_x * sigma_y

@njit
def gauss_2d_norm(volume, sigma_x, sigma_y):
    return volume / (2 * np.pi * sigma_x * sigma_y)


if __name__ == '__main__':

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

    print(x_centers.shape, x_bins.shape)
