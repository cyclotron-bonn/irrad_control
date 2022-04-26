import sys
import os
import logging
import argparse
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib as mpl

import irrad_control.analysis as irrad_analysis
from irrad_control.analysis.utils import load_irrad_data
from irrad_control.analysis.constants import p_stop_Si



# Disable matplotlib figure number warning; expect people to have more than 2 GB of RAM
mpl.rcParams['figure.max_open_warning'] = 0

# Logging level
logging.getLogger().setLevel('INFO')


# Analysis flags available to the parser
ANALYSIS_FLAGS = ('damage', 'scan', 'beam', 'calibration')


# Group multiple analysis together
GROUPED_ANALYSIS_FLAGS = {'irradiation': ('damage', 'scan'),
                          'full': ANALYSIS_FLAGS}

DEFAULT_ANALYSIS = 'irradiation'


def get_analysis_suffix(parsed_args):

    # Loop over mutually exclusive groups to determine analysis suffix
    for mutex_ana in GROUPED_ANALYSIS_FLAGS:
        if parsed_args[mutex_ana]:
            analysis_suffix = mutex_ana
            break
    # None of the grouped analysis steps is selected, search the individual analysis steps
    else:
        analysis_suffix = '_'.join(actual_ana for actual_ana in ANALYSIS_FLAGS if parsed_args[actual_ana])

    return analysis_suffix


def main():

    # Create parser
    analyse_parser = argparse.ArgumentParser(description="Perform analysis on irradiation data")

    # Input file
    analyse_parser.add_argument('-f', '--file', required=True, dest='infile')

    # Optionally, give a dedicated output PDF path
    analyse_parser.add_argument('-o', '--output', required=False, dest='outpdf')

    # Analysis types which can be performed
    # Determine which kind of analysis to perform
    main_analysis_group = analyse_parser.add_mutually_exclusive_group()
    main_analysis_group.add_argument('--irradiation', required=False, action='store_true')
    main_analysis_group.add_argument('--full', required=False, action='store_true')

    # Different types of analysis to perform; default is --damage
    sub_analysis_group = analyse_parser.add_argument_group()
    sub_analysis_group.add_argument('--damage', required=False, action='store_true')
    sub_analysis_group.add_argument('--beam', required=False, action='store_true')
    sub_analysis_group.add_argument('--scan', required=False, action='store_true')
    sub_analysis_group.add_argument('--calibration', required=False, action='store_true')

    parsed = vars(analyse_parser.parse_args(sys.argv[1:]))

    analysis_suffix = get_analysis_suffix(parsed_args=parsed)

    # If nothing was selected
    if not analysis_suffix:
        analysis_suffix = DEFAULT_ANALYSIS
    
    if analysis_suffix in GROUPED_ANALYSIS_FLAGS:
        for flag in GROUPED_ANALYSIS_FLAGS[analysis_suffix]:
                parsed[flag] = True
    
    # Check parsed args
    # Check if we have a config as well as data file
    file_folder = os.path.dirname(os.path.abspath(parsed['infile']))
    file_name = os.path.basename(parsed['infile'])
    
    # Get name of irradiation session; there must be two files with this name; one h5 and one yaml
    session_name = file_name.split('.')[0]
    session_config = os.path.join(file_folder, session_name + '.yaml')
    session_data = os.path.join(file_folder, session_name + '.h5')

    assert os.path.isfile(session_config), f"Configuration YAML file '{session_config}' cannot be found"
    assert os.path.isfile(session_data), f"Data file '{session_data}' cannot be found"
    
    # Load data
    data, config = load_irrad_data(data_file=session_data, config_file=session_config)

    # Make output pdf
    analysis_out_pdf = os.path.join(file_folder, f"{session_name}_analysis_{analysis_suffix}.pdf")
    analysis_out_pdf = analysis_out_pdf if parsed['outpdf'] is None else parsed['outpdf']  

    logging.info(f"Opening analysis output PDF {os.path.relpath(analysis_out_pdf, file_folder)}")

    with PdfPages(analysis_out_pdf) as _pdf:

        # Loop over different irradiation server and perform analysis
        for _, content in config['server'].items():

            irrad_server_name = content['name']

            if parsed['damage']:
                
                res = irrad_analysis.damage.analyse_radiation_damage(data=data,
                                                                     server=irrad_server_name,
                                                                     hardness_factor=content['daq']['kappa'],
                                                                     stopping_power=p_stop_Si)

                for fig in res:
                    _pdf.savefig(fig)


if __name__ == '__main__':
    main()
    