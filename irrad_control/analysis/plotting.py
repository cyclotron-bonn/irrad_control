import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as md
import irrad_control.analysis.constants as irrad_consts

from datetime import datetime
from matplotlib.colors import LogNorm
from mpl_toolkits.axes_grid1 import make_axes_locatable

from irrad_control.analysis.formulas import lin_odr, tid_per_scan


# Set matplotlib rcParams to steer appearance of irrad_analysis plots
plt.rcParams.update({
    'font.size': 11,  # default 10
    'figure.figsize': [8, 6],  # default [6.4, 4.8]
    'grid.alpha': 0.75,  # default 1.0
    'figure.max_open_warning': 0,  # default 20; disable matplotlib figure number warning; expect people to have more than 2 GB of RAM
    'path.simplify': True,  # default False: removes vertices that have no impact on plot visualization for the sake of better rendering performance
    'axes.grid' : True,
    'image.cmap': 'plasma'
    }
)


def no_title(b):
    """Don't generate plot titles by setting background color to title color"""
    if b:
        plt.rcParams['axes.titlecolor'] = plt.rcParams['axes.facecolor']


def _get_damage_label_unit_target(damage, ion_name, dut=False):
    damage_unit = r'n$_\mathrm{eq}$ cm$^{-2}$' if damage == 'neq' else f'{ion_name}s' + r' cm$^{-2}$' if damage == 'primary' else 'Mrad'
    damage_label = 'Fluence' if damage in ('neq', 'primary') else 'Total Ionizing Dose'
    damage_target = "DUT" if dut else "Scan"
    return damage_label, damage_unit, damage_target

def _apply_labels_damage_plots(ax, damage, ion_name, server, cbar=None, dut=False, damage_map=None, uncertainty_map=False):

    damage_label, damage_unit, damage_target = _get_damage_label_unit_target(damage=damage, ion_name=ion_name, dut=dut)

    ax.set_xlabel(f'{damage_target} area horizontal / mm')
    ax.set_ylabel(f'{damage_target} area vertical / mm')
    plt.suptitle(f"{damage_label}{' Error' if uncertainty_map else ''} Distribution {damage_target} Area (Server: {server})")

    # 3D plot
    if hasattr(ax, 'set_zlabel'):
        ax.set_zlabel(f"{damage_unit}")

    if damage_map is not None and dut and not uncertainty_map:
        mean, std = damage_map.mean(), damage_map.std()
        damage_mean_std = "Mean = {:.2E}{}{:.2E} {}".format(mean, u'\u00b1', std, damage_unit)
        ax.set_title(damage_mean_std)

    if cbar is not None:
        cbar_label = f"{damage_label} / {damage_unit}"
        cbar.set_label(cbar_label)

def _make_cbar(fig, damage_map, damage, ion_name, rel_error_lims=None):

    damage_label, damage_unit, _ = _get_damage_label_unit_target(damage=damage, ion_name=ion_name, dut=False)

    # Make axis for cbar
    cbar_axis = plt.axes([0.85, 0.1, 0.033, 0.8])
    cbar = fig.colorbar(damage_map, cax=cbar_axis, label=f"{damage_label} / {damage_unit}")

    if rel_error_lims is not None:
        cbar_rel_axis = cbar_axis.twinx()
        cbar.ax.yaxis.set_ticks_position('left')
        cbar.ax.yaxis.set_label_position('left')
        cbar_rel_axis.set_ylabel("Relative uncertainty / %")
        cbar_rel_axis.ticklabel_format(axis='y', useOffset=False, style='plain')
        cbar_rel_axis.set_ylim(rel_error_lims)

def _calc_duration(start, end, as_str=False):

    duration = end - start
    days = duration / (24 * 3600)
    hours = (days % 1) * 24
    minutes = (hours % 1) * 60
    seconds = (minutes % 1) * 60
    
    # Return tuple in full days, hours, minutes and seconds
    res = tuple(int(x) for x in [days, hours, minutes, seconds])
    
    return res if not as_str else ", ".join(f"{a[0]}{a[1]}" for a in zip(res, 'dhms') if a[0])

def plot_damage_error_3d(damage_map, error_map, map_centers_x, map_centers_y, view_angle=(25, -115), contour=False, **damage_label_kwargs):

    # Make figure
    fig, ax = plt.subplots(subplot_kw={"projection": "3d"})

    # Generate meshgird to plot on
    mesh_x, mesh_y = np.meshgrid(map_centers_x, map_centers_y)

    # plot surface
    surface_3d = ax.plot_surface(mesh_x, mesh_y, error_map, antialiased=True)
    
    # Adjust angle
    ax.view_init(*view_angle)
    ax.set_ylim(ax.get_ylim()[::-1])  # Inverty y axis in order to set origin to upper left

    # Relative errors
    rel_damage_map = error_map / damage_map * 100.0

    _make_cbar(fig=fig, damage_map=surface_3d, damage=damage_label_kwargs.get('damage', 'neq'), ion_name=damage_label_kwargs['ion_name'], rel_error_lims=(rel_damage_map.min(), rel_damage_map.max()))

    # Apply labels
    _apply_labels_damage_plots(ax=ax, damage_map=damage_map, uncertainty_map=True, **damage_label_kwargs)

    return fig, ax



def plot_damage_map_3d(damage_map, map_centers_x, map_centers_y, view_angle=(25, -115), contour=False, **damage_label_kwargs):

    # Make figure
    fig, ax = plt.subplots(figsize=(8, 6), subplot_kw={"projection": "3d"})

    # Generate meshgird to plot on
    mesh_x, mesh_y = np.meshgrid(map_centers_x, map_centers_y)

    # plot surface
    surface_3d = ax.plot_surface(mesh_x, mesh_y, damage_map, antialiased=True)

    # Plot contour
    if contour:
        contour_2d = ax.contourf(mesh_x, mesh_y, damage_map, zdir='z', offset=-0.05*damage_map.max())
        ax.set_zlim(-0.05*damage_map.max(), damage_map.max())
        
    # Adjust angle
    ax.view_init(*view_angle)
    ax.set_ylim(ax.get_ylim()[::-1])  # Inverty y axis in order to set origin to upper left

    _make_cbar(fig=fig, damage_map=surface_3d, damage=damage_label_kwargs.get('damage', 'neq'), ion_name=damage_label_kwargs['ion_name'])
    
    # Apply labels
    _apply_labels_damage_plots(ax=ax, damage_map=damage_map, **damage_label_kwargs)

    return fig, ax


def plot_damage_map_2d(damage_map, map_centers_x, map_centers_y, **damage_label_kwargs):

    # Make figure
    fig, ax = plt.subplots()
    
    bin_width_y = (map_centers_y[1] - map_centers_y[0])
    bin_width_x = (map_centers_x[1] - map_centers_x[0])
    
    extent = [map_centers_x[0] - bin_width_x/2., map_centers_x[-1] + bin_width_x/2., map_centers_y[-1] + bin_width_y/2., map_centers_y[0]- bin_width_y/2.]

    im = ax.imshow(damage_map, extent=extent)

    cbar = fig.colorbar(im)

    # Apply labels
    _apply_labels_damage_plots(ax=ax, cbar=cbar, damage_map=damage_map, **damage_label_kwargs)

    return fig, ax

def plot_damage_map_contourf(damage_map, map_centers_x, map_centers_y, **damage_label_kwargs):

    # Make figure
    fig, ax = plt.subplots()

     # Generate meshgird to plot on
    mesh_x, mesh_y = np.meshgrid(map_centers_x, map_centers_y)

    # Plot contour
    contour_2d = ax.contourf(mesh_x, mesh_y, damage_map)
    _ = plt.clabel(contour_2d, inline=True, fmt='%1.2E', colors='k')
    ax.set_ylim(ax.get_ylim()[::-1])  # Inverty y axis in order to set origin to upper left

    cbar = fig.colorbar(contour_2d)
    
    # Apply labels
    _apply_labels_damage_plots(ax=ax, cbar=cbar, damage_map=damage_map, **damage_label_kwargs)

    return fig, ax

def plot_generic_axis(axis_data, fig_ax=None, set_grid=True, **sp_kwargs):
    fig, ax = plt.subplots(**sp_kwargs) if fig_ax is None else fig_ax
    
    ax.set_title(axis_data['title'])
    ax.set_xlabel(axis_data['xlabel'])
    ax.set_ylabel(axis_data['ylabel'])
    if set_grid: ax.grid()
    return fig, ax
    

def plot_generic_fig(plot_data, fit_data=None, hist_data=None, fig_ax=None, **sp_kwargs):
    fig, ax = plt.subplots(**sp_kwargs) if fig_ax is None else fig_ax
    
    # Make figure and axis
    ax.set_title(plot_data['title'])
    ax.set_xlabel(plot_data['xlabel'])
    ax.set_ylabel(plot_data['ylabel'])
    
    if fit_data:
        ax.plot(fit_data['xdata'], fit_data['func'](*fit_data['fit_args']), fit_data['fmt'], label=fit_data['label'], zorder=10)
    if hist_data:
        if isinstance(hist_data['bins'], (int, str, type(None))):
            if hist_data['bins'] == 'stat':
                n, s = np.mean(plot_data['xdata']), np.std(plot_data['xdata'])
                binwidth = 6 * s / 100.
                bins = np.arange(n-3*s, n+3*s + binwidth, binwidth)
            else:
                bins = hist_data['bins']

            _, _, _ = ax.hist(plot_data['xdata'], bins=bins, label=plot_data['label'])
        elif len(hist_data['bins']) == 2:
            cmap = plt.get_cmap(plt.rcParams['image.cmap'])
            cmap.set_bad('w')
            _, _, _, im = ax.hist2d(plot_data['xdata'], plot_data['ydata'], bins=hist_data['bins'],norm=hist_data['norm'], cmap=cmap, rasterized=True)
            #im.set_edgecolor("face")
            plt.colorbar(im, label=plot_data.get('label', ''))
        else:
            raise ValueError('bins must be 2D iterable of intsd or int')
    else:
        ax.plot(plot_data['xdata'], plot_data['ydata'], plot_data['fmt'], label=plot_data['label'], alpha=plot_data.get('alpha', 1))
    ax.grid(True)
    ax.legend(loc='upper left')
    
    return fig, ax


def plot_beam_current(timestamps, beam_current, ch_name=None, scan_data=None):

    dtfts = datetime.fromtimestamp(timestamps[0])

    plot_data = {'xdata': [datetime.fromtimestamp(ts) for ts in timestamps],
                 'ydata': beam_current,
                 'xlabel': f"{dtfts.strftime('%d %b %Y')}",
                 'ylabel': f"Cup channel {ch_name} current / nA",
                 'label': f"{ch_name or 'Beam'} current over {_calc_duration(start=timestamps[0], end=timestamps[-1], as_str=True)}{' irradiation' if scan_data else ''}",
                 'title': f"Current of channel {ch_name}",
                 'fmt': 'C0-'}

    if ch_name is None:
        plot_data['ylabel'] = 'Beam current / nA'
        plot_data['title'] = "Beam current over time"

    if scan_data is not None:
        plot_data['title'] = 'Beam current during irradiation'

    plot_data['label'] += ":\n    ({:.2f}{}{:.2f}) nA".format(np.nanmean(beam_current), u'\u00b1', np.nanstd(beam_current))

    fig, ax = plot_generic_fig(plot_data=plot_data)

    ax.xaxis.set_major_formatter(md.DateFormatter('%H:%M'))
    fig.autofmt_xdate()

    return fig, ax


def plot_relative_beam_position(horizontal_pos, vertical_pos, n_bins=100, scan_data=None):

    fig, ax_hist_2d = plt.subplots()

    ax_hist_2d.set_aspect(1.0)

    # Use fancy submodule, making grid of plots a 10000 times easier
    # See https://matplotlib.org/stable/gallery/axes_grid1/scatter_hist_locatable_axes.html#sphx-glr-gallery-axes-grid1-scatter-hist-locatable-axes-py
    anchor = make_axes_locatable(ax_hist_2d)

    # Create a bunch of new axes for the other hists and the cbar
    ax_hist_h = anchor.append_axes('top', 0.85, pad=0.1, sharex=ax_hist_2d)
    ax_hist_v = anchor.append_axes('left', 0.85, pad=0.1, sharey=ax_hist_2d)
    ax_cbar = anchor.append_axes('right', 0.2, pad=0.1)

    # Set the tick locations correctly and inverty y axis of one hist to place it on left
    ax_hist_h.xaxis.set_tick_params(labelbottom=False)
    ax_hist_2d.yaxis.set_tick_params(labelleft=False)
    ax_hist_v.invert_xaxis()

    # Make the plots and trash what we don't need
    _, _, _, im = ax_hist_2d.hist2d(horizontal_pos, vertical_pos, bins=(n_bins, n_bins), norm=LogNorm(), cmin=1)
    _, _, _ = ax_hist_h.hist(horizontal_pos, bins=n_bins)
    _, _, _ = ax_hist_v.hist(vertical_pos, bins=n_bins, orientation='horizontal')

    # Add colorbar to predefined axis
    fig.colorbar(im, cax=ax_cbar, label="")

    # Add reticle
    x_min, x_max = ax_hist_2d.get_xbound()
    y_min, y_max = ax_hist_2d.get_ybound()
    ax_hist_2d.annotate(text='Right', xy=(0, 0), xycoords='data',
                        xytext=(x_max, 0),
                        textcoords='data',
                        arrowprops=dict(arrowstyle='<-', ls='--', alpha=0.8),
                        ha='right', va='center', rotation=270)
    ax_hist_2d.annotate(text='Left', xy=(0, 0), xycoords='data',
                        xytext=(x_min, 0),
                        textcoords='data',
                        arrowprops=dict(arrowstyle='<-', ls='--', alpha=0.8),
                        ha='left', va='center', rotation=90)
    ax_hist_2d.annotate(text='Up', xy=(0, 0), xycoords='data',
                        xytext=(0, y_max),
                        textcoords='data',
                        arrowprops=dict(arrowstyle='<-', ls='--', alpha=0.8),
                        ha='center', va='top')
    ax_hist_2d.annotate(text='Down', xy=(0, 0), xycoords='data',
                        xytext=(0, y_min),
                        textcoords='data',
                        arrowprops=dict(arrowstyle='<-', ls='--', alpha=0.8),
                        ha='center', va='bottom')

    # Make labels and legends
    ax_hist_h.set_title(f"Beam-mean position relative to center {'during irradiation' if scan_data else ''}")
    ax_hist_2d.set_xlabel('Rel. horizontal deviation / %')
    ax_hist_v.set_ylabel('Rel. vertical deviation / %')

    # Fake a little legend
    ax_hist_h.text(s=r'$\mathrm{\mu_h}$='+"({:.1f}{}{:.1f}) %".format(horizontal_pos.mean(), u'\u00b1', horizontal_pos.std()),
                   x=x_min*0.95,
                   y=ax_hist_h.get_ylim()[-1]*0.775, rotation=0, fontsize=10,
                   bbox=dict(boxstyle='round', facecolor='white', edgecolor='grey', alpha=0.33))
    ax_hist_v.text(s=r'$\mathrm{\mu_v}$='+"({:.1f}{}{:.1f}) %".format(vertical_pos.mean(), u'\u00b1', vertical_pos.std()),
                   x=ax_hist_v.get_xlim()[0]*0.925,
                   y=y_min*0.925, rotation=90, fontsize=10,
                   bbox=dict(boxstyle='round', facecolor='white', edgecolor='grey', alpha=0.33))

    return fig, (ax_hist_2d, ax_hist_h, ax_hist_v)


def plot_calibration(calib_data, ref_data, calib_sig, ref_sig, red_chi, beta_lambda, hist=False):

    beta_const, lambda_const = beta_lambda

    fit_label=r'Linear fit: $\mathrm{I_{Beam} = \beta \cdot I_{SEE}}$;'
    fit_label += '\n\t' + r'$\beta=(%.2E \pm %.2E)$' % (beta_const.n, beta_const.s)
    fit_label += '\n\t' + r'$\lambda=\beta / 5\ V=(%.3f \pm %.3f) \ V^{-1}$' % (lambda_const.n, lambda_const.s)
    fit_label += '\n\t' + r'$\mathrm{SEY}=\beta^{-1}=(%.3f \pm %.3f)$' % ((100./beta_const).n, (100./beta_const).s) + ' %'
    fit_label += '\n\t' + r'$\chi^2_{red}= %.2f\ $' % red_chi

    # Make figure and axis
    fig, ax = plot_generic_fig(plot_data={'xdata': calib_data,
                                          'ydata': ref_data,
                                          'xlabel': r"Secondary electron current $\mathrm{I_{SEE}}$ / nA",
                                          'ylabel': r"Beam current $\mathrm{I_{Beam}}$ / nA",
                                          'label': f"SEE channel '{calib_sig}' vs. Cup channel '{ref_sig}'",
                                          'title':"Beam current calibration",
                                          'fmt':'C0.',
                                          'alpha': 0.33},
                               fit_data={'xdata': calib_data,
                                         'func': lin_odr,
                                         'fit_args': [[beta_const.n], calib_data],
                                         'fmt': 'C1-',
                                         'label': fit_label},
                               hist_data={'bins': (100, 100), 'norm': LogNorm()} if hist else {})
    
    return fig, ax


def plot_fluence_distribution(fluence_data, ion):

    plot_data = {
        'xdata': fluence_data,
        'xlabel': f"Fluence per scanned row / {ion}s / cm^2",
        'ylabel': '#',
        'label': "({:.2E}{}{:.2E}) {}s / cm^2".format(fluence_data.mean(), u'\u00b1', fluence_data.std(), ion),
        'title': "Row fluence distribution",
        'fmt': 'C0'
    }

    fig, ax = plot_generic_fig(plot_data=plot_data, hist_data={'bins': 'stat'})

    return fig, ax


def plot_damage_resolved(primary_damage_resolved, stopping_power=None, hardness_factor=None, **damage_label_kwargs):
    fig, ax = plot_generic_axis(axis_data={'xlabel': 'Row number',
                                           'ylabel': 'Scan number',
                                           'title': "Damage scan and row resolved"})

    if hardness_factor is not None:
        damage = primary_damage_resolved * hardness_factor
    else:
        damage = primary_damage_resolved

    if stopping_power is not None:
        tid = tid_per_scan(primary_damage_resolved, stopping_power=stopping_power)
        secondary_cbar_axis = {'ylim': (tid.min(), tid.max()), 'ylabel': 'Total-ionizing dose / Mrad'}
    else:
        secondary_cbar_axis = {}
    
    extent = [0, primary_damage_resolved.shape[1], 0, primary_damage_resolved.shape[0]]

    im = ax.imshow(damage, origin='lower', extent=extent)
    #ax.grid(False)

    _make_cbar(fig=fig,
               damage_map=im,
               damage='neq',
               ion_name=damage_label_kwargs['ion_name'])

    # neqax = ax.twinx()
    # neqlabel = str(r'Fluence / n$_\mathrm{eq}$ cm$^{-2}$')
    # neqax.set_ylabel(neqlabel)
    # neqax.grid(axis='y')
    # neq_ylims = [lim*kwargs['hardness_factor']/(1e5 * irrad_consts.elementary_charge * kwargs['stopping_power']) for lim in ax.get_ylim()]
    # neqax.set_ylim(ymin=neq_ylims[0], ymax=neq_ylims[1])
    return fig, ax

def plot_everything(data, **kwargs):
    fig, beamax = plt.subplots(figsize=(8,6))
    scanax = beamax.twiny()
    fig_title = "Row- and scanwise radiation data"
    fig.suptitle(fig_title)
    dtime_row_start = [datetime.fromtimestamp(ts) for ts in data['row_start']]
    dtime_row_stop = [datetime.fromtimestamp(ts) for ts in data['row_stop']]
    tss = datetime.fromtimestamp(data['row_start'][0])
    day = tss.strftime("%d")
    month = tss.strftime("%B")
    year = tss.strftime("%Y")
    xtimelabel = "Time on {} {} {}".format(day, month, year)
    beamax.plot(dtime_row_start, data['beam_current'], color="C1", label="Beam", zorder=6)
    beamax.set_ylabel(f"Beam current / nA")
    scanax.set_xlim(beamax.get_xlim())
    beamax.set_facecolor('none')
    bymin, bymax = beamax.get_ylim()
    beamax.set_ylim(bymin, 1.05*bymax) #make some room for labels
    tidax = beamax.twinx()
    neqax = beamax.twinx()
    
    beamax.spines['right'].set_position(('outward', 0.0))
    beamax.yaxis.tick_right()
    beamax.yaxis.set_label_position("right")

    neqlabel = str(r'Fluence / n$_\mathrm{eq}$ cm$^{-2}$')
    neqax.set_ylabel(neqlabel)
    neqax.spines['left'].set_position(('outward', 0))
    neqax.spines['left'].set_visible(True)
    neqax.yaxis.set_label_position("left")
    neqax.yaxis.tick_left()
    
    tidax.spines['left'].set_position(('outward', 55))
    tidax.spines['left'].set_visible(True)
    tidax.yaxis.set_label_position("left")
    tidax.yaxis.tick_left()
    ruderzeit = np.array([dtime_row_start[i+1] - dtime_row_start[i] for i in range(len(dtime_row_start)-1)])
    ruderzeit = np.append(arr=ruderzeit, values=(dtime_row_start[-1] - dtime_row_stop[-1]))
    tidax.bar(x=dtime_row_start, height=data['row_tid'], width=ruderzeit, label="Damage", color='C0', align='edge', zorder=-10) #add tid per scan
    tidax.set_ylabel("TID / Mrad")
    ymin, ymax = tidax.get_ylim()
    tidax.set_ylim(ymin, 1.1*ymax) #make some room for labels
    
    n_scan = len(data['scan_start'])
    tick_dist = n_scan/5
    beamaxlabel = ["Scan {}".format(i+1) for i in range(n_scan) if (i-19)%tick_dist==0]
    dtime_scan_start = [datetime.fromtimestamp(data['scan_start'][i]) for i in range(n_scan) if (i-19)%tick_dist==0]
    beamax.set_xticks(dtime_scan_start)
    beamax.set_xticklabels(beamaxlabel)
    scanax.xaxis.set_major_formatter(md.DateFormatter('%H:%M'))
    scanax.set_xlabel(xtimelabel)
    
    beamax.plot(dtime_row_start, data['beam_loss'], label="Beam loss", color="C2", zorder=50)
    beamax.legend()
    #beamlossax.xaxis.set_major_formatter(md.DateFormatter('%H:%M'))

    neq_ylims = [lim*kwargs['hardness_factor']/(1e5 * irrad_consts.elementary_charge * kwargs['stopping_power']) for lim in tidax.get_ylim()]
    neqax.set_ylim(ymin=neq_ylims[0], ymax=neq_ylims[1])
    beamax.legend(loc='upper right')
    tidax.legend(loc='upper left')
    neqax.grid(axis='y', zorder=11)
    beamax.grid(axis='x', zorder=10)
    return fig
