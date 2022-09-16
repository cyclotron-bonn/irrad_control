import logging
from os import times
import numpy as np
from types import GeneratorType
from irrad_control.analysis import plotting
from irrad_control.analysis import constants
import matplotlib.pyplot as plt
from numba import njit 


def analyse_beam(data, **beam_kwargs):
    server = beam_kwargs['server']
    #get data while scanning
    figs = []
    nano = np.array(constants.nano)
    beam_current_nA = data[server]['Beam']['beam_current']/nano #beam current in nA
    #Beam Current over time
    fig, _ = plotting.plot_beam_current(timestamps=data[server]['Beam']['timestamp'], beam_currents=beam_current_nA)
    
    figs.append(fig)
    
    #Histogram of beam_current
    fig, _ = plotting.plot_beam_current_hist(beam_currents=beam_current_nA)
    
    figs.append(fig)
    #Histogram of beam current diviation
    fig, _ = plotting.plot_beam_deviation(horizontal_deviation=data[server]['Beam']['horizontal_beam_position'],
                                          vertical_deviation=data[server]['Beam']['vertical_beam_position'])
    figs.append(fig)
    logging.info("Finished plotting.")
    return figs