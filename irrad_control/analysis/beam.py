import numpy as np
from irrad_control.analysis import plotting, constants


def main(data, config=None):

    figs = []
    server = config['name']

    beam_current = data[server]['Beam']['beam_current'] / constants.nano

    # Beam current over time
    fig, _ = plotting.plot_beam_current(timestamps=data[server]['Beam']['timestamp'],
                                        beam_current=beam_current)
    figs.append(fig)

    # Beam current histogram
    plot_data = {
        'xdata': beam_current,
        'xlabel': 'Beam current / nA',
        'ylabel': '#',
        'label': "Beam current over {}".format(plotting._calc_duration(start=data[server]['Beam']['timestamp'][0],
                                                                       end=data[server]['Beam']['timestamp'][-1],
                                                                       as_str=True)),
        'title': "Beam current distribution",
        'fmt': 'C0'
    }
    plot_data['label'] += ":\n    ({:.2f}{}{:.2f}) nA".format(beam_current.mean(), u'\u00b1', beam_current.std())

    fig, _ = plotting.plot_generic_fig(plot_data=plot_data, hist_data={'bins': 'stat'})
    figs.append(fig)

    # Relative position of beam-mean wrt the beam pipe center
    fig, _ = plotting.plot_relative_beam_position(horizontal_pos=data[server]['Beam']['horizontal_beam_position'],
                                                  vertical_pos=data[server]['Beam']['vertical_beam_position'])
    figs.append(fig)

    return figs