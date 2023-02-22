import sys
import os
import logging
import argparse
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from tqdm import tqdm
import matplotlib as mpl

import irrad_control.analysis as irrad_analysis
from irrad_control.analysis.utils import load_irrad_data


# Disable matplotlib figure number warning; expect people to have more than 2 GB of RAM
mpl.rcParams['figure.max_open_warning'] = 0

# Logging level
logging.getLogger().setLevel('INFO')


# Analysis flags available to the parser
ANALYSIS_FLAGS = ('damage', 'scan', 'beam', 'calibration')


# Option flags available
OPTION_FLAGS = ('multipart', )


# Group multiple analysis together
GROUPED_ANALYSIS_FLAGS = {'irradiation': ('damage', 'scan'),
                          'full': ANALYSIS_FLAGS}

DEFAULT_ANALYSIS = 'irradiation'


def process_parsed_args(parsed_args, analysis_suffix):
    
    if analysis_suffix in GROUPED_ANALYSIS_FLAGS:
        for flag in GROUPED_ANALYSIS_FLAGS[analysis_suffix]:
                parsed_args[flag] = True

    # Check options
    if parsed_args['multipart'] and not parsed_args['damage']:
        raise ValueError("The --multipart option only works on the --damage analysis")


def get_analysis_suffix(parsed_args):

    # Loop over mutually exclusive groups to determine analysis suffix
    for mutex_ana in GROUPED_ANALYSIS_FLAGS:
        if parsed_args[mutex_ana]:
            analysis_suffix = mutex_ana
            break
    # None of the grouped analysis steps is selected, search the individual analysis steps
    else:
        analysis_suffix = '_'.join(actual_ana for actual_ana in ANALYSIS_FLAGS if parsed_args[actual_ana])

    # None of the group flags or the individual flags were selected; do default
    if not analysis_suffix:
        analysis_suffix = DEFAULT_ANALYSIS

    return analysis_suffix


def get_outfile(infiles):
    """
    Reads the *infiles* and determines the outfile name.
    If len(*infiles*) > 1, the first element determines the outfile name

    Parameters
    ----------
    infile_path : list
        Input file list
    """


def input_files(infiles):
    """
    Generator that loads all input files

    Parameters
    ----------
    infiles : list
        List of paths to input files
    """
    
    for i, infile in enumerate(infiles):

        # Check if we have a config as well as data file
        file_folder = os.path.dirname(os.path.abspath(infile))
        file_name = os.path.basename(infile)
        
        # Get name of irradiation session; there must be two files with this name; one h5 and one yaml
        session_name = file_name.split('.')[0]
        session_config = os.path.join(file_folder, session_name + '.yaml')
        session_data = os.path.join(file_folder, session_name + '.h5')

        if not os.path.isfile(session_config) or not os.path.isfile(session_data):
            logging.error(f"Input file(s) {file_name}.h5(.yaml) not found! Skipping.")
            continue

        # Load data
        data, config = load_irrad_data(data_file=session_data, config_file=session_config)

        # Make default output analysis file name
        session_basename = os.path.join(file_folder, session_name)

        yield i, data, config, session_basename

def save_plots(plots, outfile):
    """
    Save plots to output file

    Parameters
    ----------
    plots : Iterable of Figures
        Figures to save
    outfile : PDFPages
        Filehandle of PDFPages object
    """
    for plot in tqdm(plots, desc="Saving plots", unit='plots'):
        outfile.savefig(plot, bbox_inches='tight')


def main():

    # Create parser
    analyse_parser = argparse.ArgumentParser(description="Perform analysis on irradiation data")

    # Input file
    analyse_parser.add_argument('-f', '--file', required=True, nargs='+', dest='infile')

    # Optionally, give a dedicated output PDF path
    analyse_parser.add_argument('-o', '--output', required=False, nargs='+', dest='outpdf')

    # Analysis types which can be performed
    # Determine which kind of analysis to perform
    main_analysis_group = analyse_parser.add_mutually_exclusive_group()
    for main_ana_flag in GROUPED_ANALYSIS_FLAGS:
        main_analysis_group.add_argument(f'--{main_ana_flag}', required=False, action='store_true')

    # Different types of analysis to perform
    sub_analysis_group = analyse_parser.add_argument_group()
    for sub_ana_flag in ANALYSIS_FLAGS:
        sub_analysis_group.add_argument(f'--{sub_ana_flag}', required=False, action='store_true')

    # Parse options
    option_group = analyse_parser.add_argument_group()
    for option_flag in OPTION_FLAGS:
        option_group.add_argument(f'--{option_flag}', required=False, action='store_true')
    
    # Actually parse the guy 
    parsed = vars(analyse_parser.parse_args(sys.argv[1:]))

    analysis_suffix = get_analysis_suffix(parsed_args=parsed)

    process_parsed_args(parsed_args=parsed, analysis_suffix=analysis_suffix)

    # We are doing damage analysis on a single irradiation which is split in multiple files
    if parsed['multipart']:
        
        # Make output pdf
        file_folder = os.path.dirname(os.path.abspath(parsed['infile'][0]))
        file_name = os.path.basename(parsed['infile'][0])
        session_name = file_name.split('.')[0]
        analysis_out_pdf = os.path.join(file_folder, f"{session_name}_multipart_analysis_{analysis_suffix}.pdf")
        if parsed['outpdf'] and len(parsed['outpdf']) == 1:
            analysis_out_pdf = parsed['outpdf'][0]

        logging.info(f"Opening analysis output PDF {os.path.relpath(analysis_out_pdf, file_folder)}")

        # Open PDF 
        with PdfPages(analysis_out_pdf) as out_pdf:

            res = irrad_analysis.damage.main(data=input_files(infiles=parsed['infile']))

            save_plots(plots=res, outfile=out_pdf)

    # We are doing the same analysis on multiple files
    else:

        # Check outfiles
        if parsed['outpdf'] and len(parsed['outpdf']) == len(parsed['infile']):
            analysis_out_pdf = parsed['outpdf']
        else:
            analysis_out_pdf = None
        
        # Loop over generator and do same analysis on each input file
        for nfile, data, config, session_basename in input_files(infiles=parsed['infile']):

            actual_analysis_out_pdf = session_basename + f'_analysis_{analysis_suffix}.pdf' if analysis_out_pdf is None else analysis_out_pdf[nfile]

            logging.info(f"Opening analysis output PDF {os.path.relpath(actual_analysis_out_pdf, os.getcwd())}")

            with PdfPages(actual_analysis_out_pdf) as out_pdf:

                # Loop over different irradiation server and perform analysis
                for _, content in config['server'].items():

                    if parsed['damage']:
                        
                        res = irrad_analysis.damage.main(data=data, config=content)

                        save_plots(plots=res, outfile=out_pdf)
            
                    if parsed['calibration']:

                        res = irrad_analysis.calibration.main(irrad_data=data, irrad_config=content)

                        save_plots(plots=res, outfile=out_pdf)

                    if parsed['scan']:
                        
                        res = irrad_analysis.scan.main(data=data, config=content)
                        
                        save_plots(plots=res, outfile=out_pdf)

                    if parsed['beam']:
                        
                        res = irrad_analysis.beam.main(data=data, config=content)
                    
                        save_plots(plots=res, outfile=out_pdf)
                    
if __name__ == '__main__':
    main()
    