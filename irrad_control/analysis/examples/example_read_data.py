import matplotlib.pyplot as plt
from irrad_control.analysis.utils import load_irrad_data


if __name__ == '__main__':

    # File paths
    data_file = './example_data.h5'
    config_file = './example_config.yaml'

    # Load data and config
    irrad_data, irrad_config = load_irrad_data(data_file=data_file, config_file=config_file)

    for s in irrad_config['server']:

        server_name = irrad_config['server'][s]['name']

        # These fields are further explained in irrad_control/analysis/dtype.py
        print('Server *{}* contains the fields: {}'.format(server_name, ', '.join(irrad_data[server_name].keys())))

        # Get beam-related data
        beam_data_timestamp = irrad_data[server_name]['Beam']['timestamp']
        beam_data_current = irrad_data[server_name]['Beam']['beam_current']
        beam_data_current_error = irrad_data[server_name]['Beam']['beam_current_error']

        print(f'\nMean beam current {beam_data_current.mean()*1e9:.3f} nA, mean current error {beam_data_current_error.mean()*1e9:.3f} nA')

        # Get beam position histogram stuff
        histogram_beam_position = irrad_data[server_name]['Histogram']['BeamPosition']

        # Actual histogram
        print('\nBeam position histogram:\n', histogram_beam_position['hist'])

        # 2D hist of all positions
        im = plt.imshow(histogram_beam_position['hist'].T, extent=[histogram_beam_position['edges'][0][0],
                                                                   histogram_beam_position['edges'][0][-1],
                                                                   histogram_beam_position['edges'][1][0],
                                                                   histogram_beam_position['edges'][1][-1]],
                        cmap='viridis', origin='lower')
        plt.colorbar(im)
        plt.show()

        # Mask data to only get the beam data during the irradiation
        beam_data_mask = (irrad_data[server_name]['Scan'][0]['row_start_timestamp'] <= irrad_data[server_name]['Beam']['timestamp']) & \
                         (irrad_data[server_name]['Scan'][-1]['row_stop_timestamp'] >= irrad_data[server_name]['Beam']['timestamp'])

        # Beam centers, edges and unit
        # print(histogram_beam_position['centers'], histogram_beam_position['edges'], histogram_beam_position['unit'])

        # Channel names and types used during this irradiation
        print('\nChannel names: ', irrad_config['server'][s]['readout']['channels'],'\nChannel types: ', irrad_config['server'][s]['readout']['types'])
