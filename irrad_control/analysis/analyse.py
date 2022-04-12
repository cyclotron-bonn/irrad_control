import sys
import os
import logging
import argparse
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages

import irrad_control.analysis as irrad_analysis

logging.getLogger().setLevel('INFO')


# Different types of analysis that can be performed
ANALYSIS_TYPES = ('damage', 'beam', 'irradiation', 'calibration', 'full')


def analyse_damage(beam_data, scan_data, hardness_factor, stopping_power=irrad_analysis.constants.p_stop_Si):

    figs = []

    fluence_map, map_centers_x, map_centers_y = irrad_analysis.fluence.generate_fluence_map(beam_data=beam_data, scan_data=scan_data, bins=(100, 100))
    
    tid_map = irrad_analysis.formulas.tid_scan(proton_fluence=fluence_map, stopping_power=stopping_power)
    neq_map = fluence_map * hardness_factor

    map_centers_y_reversed = map_centers_y[::-1]

    # Extract scan dimensions
    scan_dim_x = map_centers_x[-1] + (map_centers_x[1] - map_centers_x[0])/2.
    scan_dim_y = map_centers_y[-1] + (map_centers_y[1] - map_centers_y[0])/2.
    
    # Extract default 2x2 cm center region of scan; FIXME: use actual DUT dimensions from *Irrad* data
    dut_dim_idxs = (np.searchsorted(map_centers_y, (scan_dim_y-20.)/2.),
                    np.searchsorted(map_centers_y, scan_dim_y-(scan_dim_y-20.)/2., side='left'),
                    np.searchsorted(map_centers_x, (scan_dim_x-20.)/2.),
                    np.searchsorted(map_centers_x, scan_dim_x-(scan_dim_x-20.)/2., side='left'))

    # Generate mesh for plotting entire scan area
    map_mesh = np.meshgrid(map_centers_x, map_centers_y_reversed)  # Reverse Y axis to put origin to upper left

    dut_slice = np.s_[dut_dim_idxs[0]:dut_dim_idxs[1], dut_dim_idxs[-2]:dut_dim_idxs[-1]]

    dut_tid_map, dut_neq_map = tid_map[dut_slice], neq_map[dut_slice]
    
    # Generate mesh for plotting DUT area
    dut_mesh = (map_mesh[0][dut_slice], map_mesh[1][dut_slice])


    neq_3d_fig, _ = irrad_analysis.plotting.plot_damage_map_3d(damage_map=neq_map, map_centers_x=map_centers_x, map_centers_y=map_centers_y)
    figs.append(neq_3d_fig)

    neq_2d_fig, _ = irrad_analysis.plotting.plot_damage_map_2d(damage_map=neq_map, map_centers_x=map_centers_x, map_centers_y=map_centers_y)
    figs.append(neq_2d_fig)

    neq_2d_contour, _ = irrad_analysis.plotting.plot_damage_map_contourf(damage_map=neq_map, map_centers_x=map_centers_x, map_centers_y=map_centers_y)
    figs.append(neq_2d_contour)

    tid_3d_fig, _ = irrad_analysis.plotting.plot_damage_map_3d(damage_map=tid_map, map_centers_x=map_centers_x, map_centers_y=map_centers_y, damage='TID')
    figs.append(tid_3d_fig)

    tid_2d_fig, _ = irrad_analysis.plotting.plot_damage_map_2d(damage_map=tid_map, map_centers_x=map_centers_x, map_centers_y=map_centers_y, damage='TID')
    figs.append(tid_2d_fig)

    tid_2d_contour, _ = irrad_analysis.plotting.plot_damage_map_contourf(damage_map=tid_map, map_centers_x=map_centers_x, map_centers_y=map_centers_y, damage='TID')
    figs.append(tid_2d_contour)

    return figs


def main():

    # Create parser
    analyse_parser = argparse.ArgumentParser(description="Perform analysis on irradiation data")

    # Input file
    analyse_parser.add_argument('-f', '--file', required=True, dest='infile')

    # Optionally, give a dedicated output PDF path
    analyse_parser.add_argument('-o', '--output', required=False, dest='outpdf')

    # Determine which kind of analysis to perform
    analysis_type_group = analyse_parser.add_mutually_exclusive_group()

    # Different types of analysis to perform; default is --damage
    analysis_type_group.add_argument('-d', '--damage', required=False, action='store_false')
    analysis_type_group.add_argument('-b', '--beam', required=False, action='store_true')
    analysis_type_group.add_argument('-i', '--irradiation', required=False, action='store_true')
    analysis_type_group.add_argument('-c', '--calibration', required=False, action='store_true')
    analysis_type_group.add_argument('-x', '--full', required=False, action='store_true')

    parsed = vars(analyse_parser.parse_args(sys.argv[1:]))

    # Check parsed args
    # Check if we have a config as well as data file
    file_folder = os.path.dirname(os.path.abspath(parsed['infile']))
    file_name = os.path.basename(parsed['infile'])
    
    # Get name of irradiation session; there must be two files with this name; one h5 and one yaml
    session_name = file_name.split('.')[0]
    session_config = os.path.join(file_folder, session_name + '.yaml')
    session_data = os.path.join(file_folder, session_name + '.h5')

    # Make output pdf
    analysis_out_pdf = f"{session_name}_analysis_{'_'.join(x for x in ANALYSIS_TYPES if parsed[x])}.pdf"
    analysis_out_pdf = os.path.join(file_folder, analysis_out_pdf) if parsed['outpdf'] is None else parsed['outpdf']  

    assert os.path.isfile(session_config), f"Configuration YAML file '{session_config}' cannot be found"
    assert os.path.isfile(session_data), f"Data file '{session_data}' cannot be found"
    
    # Load data
    data, config = irrad_analysis.utils.load_irrad_data(data_file=session_data, config_file=session_config)

    logging.info(f"Opening {analysis_out_pdf}")

    with PdfPages(analysis_out_pdf) as _pdf:

        # Loop over different irradiation server and perform analysis
        for _, content in config['server'].items():

            if parsed['damage']:
                
                res = analyse_damage(beam_data=data[content['name']]['Beam'],
                                     scan_data=data[content['name']]['Scan'],
                                     hardness_factor=content['daq']['kappa'])

                for fig in res:
                    _pdf.savefig(fig)

if __name__ == '__main__':
    main()
    