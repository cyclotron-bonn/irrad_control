import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as md

from datetime import datetime
from matplotlib.colors import LogNorm

from irrad_control.analysis.formulas import lin_odr


def _get_damage_label_unit_target(damage, dut=False):
    damage_unit = r'n$_\mathrm{eq}$ cm$^{-2}$' if damage == 'neq' else r'p cm$^{-2}$' if damage == 'proton' else 'Mrad'
    damage_label = 'Fluence' if damage in ('neq', 'proton') else 'Total Ionizing Dose'
    damage_target = "DUT" if dut else "Scan"
    return damage_label, damage_unit, damage_target

def _apply_labels_damage_plots(ax, damage, server, cbar=None, dut=False, damage_map=None, uncertainty_map=False):

    damage_label, damage_unit, damage_target = _get_damage_label_unit_target(damage=damage, dut=dut)

    ax.set_xlabel(f'{damage_target} area horizontal / mm')
    ax.set_ylabel(f'{damage_target} area vertical / mm')
    plt.suptitle(f"{damage_label}{' Error' if uncertainty_map else ''} Distribution {damage_target} Area (Server: {server})")

    # 3D plot
    if hasattr(ax, 'set_zlabel'):
        ax.set_zlabel(f"{damage_label} / {damage_unit}")

    if damage_map is not None and dut and not uncertainty_map:
        mean, std = damage_map.mean(), damage_map.std()
        damage_mean_std = "Mean = {:.2E}{}{:.2E} {}".format(mean, u'\u00b1', std, damage_unit)
        ax.set_title(damage_mean_std)

    if cbar is not None:
        cbar_label = f"{damage_label} / {damage_unit}"
        cbar.set_label(cbar_label)

def _make_cbar(fig, damage_map, damage, rel_error_lims=None):

    damage_label, damage_unit, _ = _get_damage_label_unit_target(damage=damage, dut=False)

    # Make axis for cbar
    cbar_axis = plt.axes([0.85, 0.1, 0.033, 0.8])
    cbar = fig.colorbar(damage_map, cax=cbar_axis, label=f"{damage_label} / {damage_unit}")

    if rel_error_lims is not None:
        cbar_rel_axis = cbar_axis.twinx()
        cbar.ax.yaxis.set_ticks_position('left')
        cbar.ax.yaxis.set_label_position('left')
        cbar_rel_axis.set_ylim(rel_error_lims)
        cbar_rel_axis.set_ylabel("Relative uncertainty / %")
        cbar_rel_axis.yaxis.get_offset_text().set_alpha(0)  # Make offset disappear like a magician


def plot_damage_error_3d(damage_map, error_map, map_centers_x, map_centers_y, view_angle=(25, -115), cmap='viridis', contour=False, **damage_label_kwargs):

    # Make figure
    fig, ax = plt.subplots(figsize=(8, 6), subplot_kw={"projection": "3d"})

    # Generate meshgird to plot on
    mesh_x, mesh_y = np.meshgrid(map_centers_x, map_centers_y)

    # plot surface
    surface_3d = ax.plot_surface(mesh_x, mesh_y, error_map, antialiased=True, cmap=cmap)
    
    # Adjust angle
    ax.view_init(*view_angle)
    ax.set_ylim(ax.get_ylim()[::-1])  # Inverty y axis in order to set origin to upper left

    # Relative errors
    rel_damage_map = error_map / damage_map * 100.0

    _make_cbar(fig=fig, damage_map=surface_3d, damage=damage_label_kwargs.get('damage', 'neq'), rel_error_lims=(rel_damage_map.min(), rel_damage_map.max()))

    # Apply labels
    _apply_labels_damage_plots(ax=ax, damage_map=damage_map, uncertainty_map=True, **damage_label_kwargs)

    return fig, ax



def plot_damage_map_3d(damage_map, map_centers_x, map_centers_y, view_angle=(25, -115), cmap='viridis', contour=False, **damage_label_kwargs):

    # Make figure
    fig, ax = plt.subplots(figsize=(8, 6), subplot_kw={"projection": "3d"})

    # Generate meshgird to plot on
    mesh_x, mesh_y = np.meshgrid(map_centers_x, map_centers_y)

    # plot surface
    surface_3d = ax.plot_surface(mesh_x, mesh_y, damage_map, antialiased=True, cmap=cmap)

    # Plot contour
    if contour:
        contour_2d = ax.contourf(mesh_x, mesh_y, damage_map, zdir='z', offset=-0.05*damage_map.max(), cmap=cmap)
        ax.set_zlim(-0.05*damage_map.max(), damage_map.max())
        
    # Adjust angle
    ax.view_init(*view_angle)
    ax.set_ylim(ax.get_ylim()[::-1])  # Inverty y axis in order to set origin to upper left

    _make_cbar(fig=fig, damage_map=surface_3d, damage=damage_label_kwargs.get('damage', 'neq'))
    
    # Apply labels
    _apply_labels_damage_plots(ax=ax, damage_map=damage_map, **damage_label_kwargs)

    return fig, ax


def plot_damage_map_2d(damage_map, map_centers_x, map_centers_y, cmap='viridis', **damage_label_kwargs):

    # Make figure
    fig, ax = plt.subplots(figsize=(8, 6))
    
    bin_width_y = (map_centers_y[1] - map_centers_y[0])
    bin_width_x = (map_centers_x[1] - map_centers_x[0])
    
    extent = [map_centers_x[0] - bin_width_x/2., map_centers_x[-1] + bin_width_x/2., map_centers_y[-1] + bin_width_y/2., map_centers_y[0]- bin_width_y/2.]

    im = ax.imshow(damage_map, extent=extent, cmap=cmap)

    cbar = fig.colorbar(im)

    # Apply labels
    _apply_labels_damage_plots(ax=ax, cbar=cbar, damage_map=damage_map, **damage_label_kwargs)

    return fig, ax

def plot_damage_map_contourf(damage_map, map_centers_x, map_centers_y, cmap='viridis', **damage_label_kwargs):

    # Make figure
    fig, ax = plt.subplots(figsize=(8, 6))

     # Generate meshgird to plot on
    mesh_x, mesh_y = np.meshgrid(map_centers_x, map_centers_y)

    # Plot contour
    contour_2d = ax.contourf(mesh_x, mesh_y, damage_map, cmap=cmap)
    _ = plt.clabel(contour_2d, inline=True, fmt='%1.2E', colors='k')
    ax.set_ylim(ax.get_ylim()[::-1])  # Inverty y axis in order to set origin to upper left

    cbar = fig.colorbar(contour_2d)
    
    # Apply labels
    _apply_labels_damage_plots(ax=ax, cbar=cbar, damage_map=damage_map, **damage_label_kwargs)

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
        if isinstance(hist_data['bins'], (int, str)):
            if hist_data['bins'] == 'stat':
                n, s = np.mean(plot_data['xdata']), np.std(plot_data['xdata'])
                binwidth = 6 * s / 100.
                bins = np.arange(n-3*s, n+3*s + binwidth, binwidth)
            else:
                bins = hist_data['bins']

            _, _, _ = ax.hist(plot_data['xdata'], bins=bins, label=plot_data['label'])
        elif len(hist_data['bins']) == 2:
            _, _, _, im = ax.hist2d(plot_data['xdata'], plot_data['ydata'], bins=hist_data['bins'],norm=hist_data['norm'], cmap=hist_data['cmap'], cmin=1, label=plot_data['label'])
            plt.colorbar(im)
        else:
            raise ValueError('bins must be 2D iterable of intsd or int')
    else:
        ax.plot(plot_data['xdata'], plot_data['ydata'], plot_data['fmt'], label=plot_data['label'])
    ax.grid()
    ax.legend(loc='upper left')
    
    return fig, ax


def plot_beam_current_over_time(timestamps, beam_current, ch_name):

    fig, ax = plot_generic_fig(plot_data={'xdata': [datetime.fromtimestamp(ts) for ts in timestamps],
                                          'ydata': beam_current,
                                          'xlabel': 'Time',
                                          'ylabel': f"Cup channel {ch_name} current / nA",
                                          'label': f'{ch_name} current',
                                          'title': f"Current of channel {ch_name}",
                                          'fmt': 'C0-'},
                               figsize=(8,6))

    ax.xaxis.set_major_formatter(md.DateFormatter('%Y-%m-%d %H:%M'))
    fig.autofmt_xdate()

    return fig, ax


def plot_calibration(calib_data, ref_data, calib_sig, ref_sig, red_chi, beta_lambda, hist=False):

    beta_const, lambda_const = beta_lambda

    fit_label=r'Linear fit: $\mathrm{I_{cup}(I_{sem_{sum}})=\beta \cdot I_{sem_sum}}$;'
    fit_label += '\n\t' + r'$\mathrm{\beta=\lambda \cdot 5\ V=(%.3f \pm %.3f)}$' % (beta_const.n, beta_const.s)
    fit_label += '\n\t' + r'$\lambda=(%.3f \pm %.3f) \ V^{-1}$' % (lambda_const.n, lambda_const.s)
    fit_label += '\n\t' + r'$\chi^2_{red}= %.2f\ $' % red_chi

    # Make figure and axis
    fig, ax = plot_generic_fig(plot_data={'xdata': calib_data,
                                          'ydata': ref_data,
                                          'xlabel': f"Calibration sem_sum-type channel '{calib_sig}' current / nA",
                                          'ylabel': f"Reference cup-type channel '{ref_sig}' current / nA",
                                          'label': 'Correlation',
                                          'title':"Beam current calibration", 'fmt':'C0.'},
                               fit_data={'xdata': calib_data,
                                         'func': lin_odr,
                                         'fit_args': [[beta_const.n], calib_data],
                                         'fmt': 'C1-',
                                         'label': fit_label},
                               hist_data={'bins': (100, 100), 'cmap': 'viridis', 'norm': LogNorm()} if hist else {},
                               figsize=(8,6))

    # Make figure and axis
    _, _ = ax.set_ylim(0, np.max(ref_data) * (1.25))
    return fig, ax
