import numpy as np
import matplotlib.pyplot as plt


def plot_damage_map_3d(damage_map, map_centers_x, map_centers_y, view_angle=(25, -115), cmap='viridis', damage='NIEL'):

    # Make figure
    fig, ax = plt.subplots(figsize=(8, 6), tight_layout=True, subplot_kw={"projection": "3d"})

    # Generate meshgird to plot on
    mesh_x, mesh_y = np.meshgrid(map_centers_x, map_centers_y[::-1])

    # plot surface
    surface_3d = ax.plot_surface(mesh_x, mesh_y, damage_map, antialiased=True, cmap=cmap)

    # Plot contour
    contour_2d = ax.contourf(mesh_x, mesh_y, damage_map, zdir='z', offset=-0.05*damage_map.max(), cmap=cmap)
    
    # Adjust angle
    ax.view_init(*view_angle)
    ax.set_zlim(-0.05*damage_map.max(), damage_map.max())
    ax.set_ylim(ax.get_ylim()[::-1])

    ax.set_xlabel('Scan area horizontal [mm]')
    ax.set_ylabel('Scan area vertical [mm]')
    ax.set_zlabel(r"Fluence [n$_\mathrm{eq}$ / cm$^2$]" if damage == 'NIEL' else "TID [Mrad]")
    ax.set_title('{} distribution'.format('Fluence' if damage == 'NIEL' else 'TID'))

    damage_mean = ''  # "(Mean = {:.2E}{}{:.2E} {})".format(damage_map.mean(), u'\u00B1', damage_map.std(), r'n$_\mathrm{eq}$ / cm$^2$' if damage == 'NIEL' else 'Mrad')
    
    cbar = fig.colorbar(surface_3d)
    cbar.set_label(f"{ax.get_zlabel()} {damage_mean}")

    return fig, ax


def plot_damage_map_2d(damage_map, map_centers_x, map_centers_y, cmap='viridis', damage='NIEL'):

    # Make figure
    fig, ax = plt.subplots(figsize=(8, 6), tight_layout=True)

    extent = [0, map_centers_x[-1] + (map_centers_x[1] - map_centers_x[0])/2., map_centers_y[-1] + (map_centers_y[1] - map_centers_y[0])/2., 0]

    im = ax.imshow(damage_map, origin='upper', extent=extent, cmap=cmap)
    
    ax.set_xlabel('Scan area horizontal [mm]')
    ax.set_ylabel('Scan area vertical [mm]')
    ax.set_title(r"Fluence distribution [n$_\mathrm{eq}$ / cm$^2$]" if damage == 'NIEL' else "TID distribution[Mrad]")
    
    damage_mean = ''  # "(Mean = {:.2E}{}{:.2E} {})".format(damage_map.mean(), u'\u00B1', damage_map.std(), r'n$_\mathrm{eq}$ / cm$^2$' if damage == 'NIEL' else 'Mrad')

    cbar = fig.colorbar(im)
    cbar.set_label(r"Fluence [n$_\mathrm{eq}$ / cm$^2$]" if damage == 'NIEL' else 'TID [Mrad]' + f" {damage_mean}")

    return fig, ax

def plot_damage_map_contourf(damage_map, map_centers_x, map_centers_y, cmap='viridis', damage='NIEL'):

    # Make figure
    fig, ax = plt.subplots(figsize=(8, 6), tight_layout=True)

     # Generate meshgird to plot on
    mesh_x, mesh_y = np.meshgrid(map_centers_x, map_centers_y[::-1])

    # Plot contour
    contour_2d = ax.contourf(mesh_x, mesh_y, damage_map, cmap=cmap)
    plt.clabel(contour_2d, inline=True, fmt='%1.2E')
    ax.set_ylim(ax.get_ylim()[::-1])
    
    ax.set_xlabel('Scan area horizontal [mm]')
    ax.set_ylabel('Scan area vertical [mm]')
    ax.set_title(r"Fluence distribution [n$_\mathrm{eq}$ / cm$^2$]" if damage == 'NIEL' else "TID distribution[Mrad]")
    
    damage_mean = ''  # "(Mean = {:.2E}{}{:.2E} {})".format(damage_map.mean(), u'\u00B1', damage_map.std(), r'n$_\mathrm{eq}$ / cm$^2$' if damage == 'NIEL' else 'Mrad')

    cbar = fig.colorbar(contour_2d)
    cbar.set_label(r"Fluence [n$_\mathrm{eq}$ / cm$^2$]" if damage == 'NIEL' else 'TID [Mrad]' + f" {damage_mean}")

    return fig, ax
