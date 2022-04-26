import numpy as np
import matplotlib.pyplot as plt


def _apply_labels_damage_plots(ax, damage, server, dut=False, cbar=None, damage_map=None):

    damage_unit = r'n$_\mathrm{eq}$ / cm$^2$' if damage == 'NIEL' else 'Mrad'
    damage_label = 'Fluence' if damage == 'NIEL' else 'Total Ionizing Dose'
    damage_target = "DUT" if dut else "Scan"

    ax.set_xlabel(f'{damage_target} area horizontal [mm]')
    ax.set_ylabel(f'{damage_target} area vertical [mm]')
    plt.suptitle(f'{damage_label} Distribution {damage_target} Area [Server: {server}]')

    # 3D plot
    if hasattr(ax, 'set_zlabel'):
        ax.set_zlabel(f"{damage_label} [{damage_unit}]")

    if damage_map is not None and dut:
        mean, std = damage_map.mean(), damage_map.std()
        damage_mean_std = "Mean = {:.2E}{}{:.2E} {}".format(mean, u'\u00b1', std, damage_unit)
        ax.set_title(damage_mean_std)

    if cbar is not None:
        cbar_label = f"{damage_label} [{damage_unit}]"
        cbar.set_label(cbar_label)


def plot_damage_map_3d(damage_map, map_centers_x, map_centers_y, view_angle=(25, -115), cmap='viridis', contour=False, **damage_label_kwargs):

    # Make figure
    fig, ax = plt.subplots(figsize=(8, 6), tight_layout=True, subplot_kw={"projection": "3d"})

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

    # Make colorbar
    cbar = fig.colorbar(surface_3d)

    # Apply labels
    _apply_labels_damage_plots(ax=ax, cbar=cbar, damage_map=damage_map, **damage_label_kwargs)

    return fig, ax


def plot_damage_map_2d(damage_map, map_centers_x, map_centers_y, cmap='viridis', **damage_label_kwargs):

    # Make figure
    fig, ax = plt.subplots(figsize=(8, 6), tight_layout=True)
    
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
    fig, ax = plt.subplots(figsize=(8, 6), tight_layout=True)

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


def plot_generic_fig(plot_data, fit_data=None, hist_data=None, **sp_kwargs):
    
    fig, ax = plt.subplots(**sp_kwargs)
    
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