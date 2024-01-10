import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as md
import matplotlib.colors as mc
import matplotlib.cm as cm
import irrad_control.analysis.constants as irrad_consts

from datetime import datetime, timedelta
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Rectangle
from matplotlib.legend_handler import HandlerBase
from mpl_toolkits.axes_grid1 import make_axes_locatable

from irrad_control.analysis.formulas import lin_odr
from irrad_control.utils.utils import duration_str_from_secs
from irrad_control.ions import get_ions


# Set matplotlib rcParams to steer appearance of irrad_analysis plots
plt.rcParams.update({
    'font.size': 11,  # default 10
    'figure.figsize': [8, 6],  # default [6.4, 4.8]
    'grid.alpha': 0.75,  # default 1.0
    'figure.max_open_warning': 0,  # default 20; disable matplotlib figure number warning; expect people to have more than 2 GB of RAM
    'path.simplify': True,  # default False: removes vertices that have no impact on plot visualization for the sake of better rendering performance
    'image.cmap': 'plasma'
    }
)


class HandlerColormap(HandlerBase):
    def __init__(self, cmap, num_stripes=8, **kw):
        HandlerBase.__init__(self, **kw)
        self.cmap = cmap
        self.num_stripes = num_stripes
    def create_artists(self, legend, orig_handle, 
                       xdescent, ydescent, width, height, fontsize, trans):
        stripes = []
        for i in range(self.num_stripes):
            s = Rectangle([xdescent + i * width / self.num_stripes, ydescent], 
                          width / self.num_stripes, 
                          height, 
                          fc=self.cmap((2 * i + 1) / (2 * self.num_stripes)), 
                          transform=trans)
            stripes.append(s)
        return stripes


def no_title(b):
    """Don't generate plot titles by setting background color to title color"""
    if b:
        plt.rcParams['axes.titlecolor'] = plt.rcParams['axes.facecolor']
        plt.rcParams['figure.titlesize'] = 1  # TODO: find a better solution


def align_axis(ax1, v1, ax2, v2, axis='y'):
    """adjust ax2 ylimit so that v2 in ax2 is aligned to v1 in ax1"""
    x1, y1 = ax1.transData.transform((0, v1))
    x2, y2 = ax2.transData.transform((0, v2))
    inv = ax2.transData.inverted()
    
    if axis == 'y':
        _, dy = inv.transform((0, 0)) - inv.transform((0, y1-y2))
        miny, maxy = ax2.get_ylim()
        ax2.set_ylim(miny+dy, maxy+dy)
    else:
        dx, _ = inv.transform((0, 0)) - inv.transform((0, x1-x2))
        minx, maxx = ax2.get_xlim()
        ax2.set_xlim(minx+dx, maxx+dx)


def _get_damage_label_unit_target(damage, ion_name, dut=False):
    damage_unit = r'n$_\mathrm{eq}$ cm$^{-2}$' if damage == 'neq' else f'{ion_name}s' + r' cm$^{-2}$' if damage == 'primary' else 'Mrad'
    damage_label = 'Fluence' if damage in ('neq', 'primary') else 'Total Ionizing Dose'
    damage_target = "DUT" if dut else "Scan"
    return damage_label, damage_unit, damage_target


def _apply_labels_damage_plots(ax, damage, ion_name, server='', cbar=None, dut=False, damage_map=None, uncertainty_map=False):

    damage_label, damage_unit, damage_target = _get_damage_label_unit_target(damage=damage, ion_name=ion_name, dut=dut)

    ax.set_xlabel(f'{damage_target} area horizontal / mm')
    ax.set_ylabel(f'{damage_target} area vertical / mm')
    plt.suptitle(f"{damage_label}{' Error' if uncertainty_map else ''} Distribution {damage_target} Area {'' if not server else server}")

    # 3D plot
    if hasattr(ax, 'set_zlabel'):
        ax.set_zlabel(f"{damage_unit}")

    if damage_map is not None and dut and not uncertainty_map:
        mean, std = np.nanmean(damage_map), np.nanstd(damage_map)
        damage_mean_std = "Mean = {:.2E}{}{:.2E} {}".format(mean, u'\u00b1', std, damage_unit)
        ax.set_title(damage_mean_std)

    if cbar is not None:
        cbar_label = f"{damage_label} / {damage_unit}"
        cbar.set_label(cbar_label)


def _make_cbar(fig, damage_map, damage, ion_name, rel_error_lims=None, add_cbar_axis=True, **cbar_wkargs):

    damage_label, damage_unit, _ = _get_damage_label_unit_target(damage=damage, ion_name=ion_name, dut=False)

    # Make axis for cbar
    if add_cbar_axis:
        cbar_axis = plt.axes([0.85, 0.1, 0.033, 0.8])
    else:
        cbar_axis = None

    cbar = fig.colorbar(damage_map, cax=cbar_axis, label=f"{damage_label} / {damage_unit}", **cbar_wkargs)

    if rel_error_lims is not None:
        cbar_rel_axis = cbar_axis.twinx()
        cbar.ax.yaxis.set_ticks_position('left')
        cbar.ax.yaxis.set_label_position('left')
        cbar_rel_axis.set_ylabel("Relative uncertainty / %")
        cbar_rel_axis.ticklabel_format(axis='y', useOffset=False, style='plain')
        cbar_rel_axis.set_ylim(rel_error_lims)

def plot_damage_error_3d(damage_map, error_map, map_centers_x, map_centers_y, view_angle=(25, -115), contour=False, **damage_label_kwargs):

    # Make figure
    fig, ax = plt.subplots(subplot_kw={"projection": "3d"})

    # Generate meshgird to plot on
    mesh_x, mesh_y = np.meshgrid(map_centers_x, map_centers_y)

    # plot surface
    surface_3d = ax.plot_surface(mesh_x, mesh_y, error_map, antialiased=True, cmap=plt.rcParams['image.cmap'])
    
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
    surface_3d = ax.plot_surface(mesh_x, mesh_y, damage_map, antialiased=True, cmap=plt.rcParams['image.cmap'])

    # Plot contour
    if contour:
        contour_2d = ax.contourf(mesh_x, mesh_y, damage_map, zdir='z', offset=-0.05*damage_map.max(), cmap=plt.rcParams['image.cmap'])
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

    im = ax.imshow(damage_map, extent=extent, cmap=plt.rcParams['image.cmap'])

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
    contour_2d = ax.contourf(mesh_x, mesh_y, damage_map, cmap=plt.rcParams['image.cmap'])
    _ = plt.clabel(contour_2d, inline=True, fmt='%1.2E', colors='k')
    ax.set_ylim(ax.get_ylim()[::-1])  # Inverty y axis in order to set origin to upper left

    cbar = fig.colorbar(contour_2d)
    
    # Apply labels
    _apply_labels_damage_plots(ax=ax, cbar=cbar, damage_map=damage_map, **damage_label_kwargs)

    return fig, ax


def plot_scan_damage_resolved(damage_map, damage, ion_name, row_separation, n_complete_scans):

    def make_axis_int_only(ax, axis='x'):
        actual_axis =getattr(ax, 'xaxis' if axis == 'x' else 'yaxis')
        scan_numbers = [int(lbl.get_position()[0]) for lbl in actual_axis.get_ticklabels() if lbl.get_position()[0] % 1 == 0]
        actual_axis.set_ticks(scan_numbers, labels=[str(i) for i in scan_numbers])

    # Our irradiation consisted of complete scans and subsequent correction scans of individual rows
    if n_complete_scans != damage_map.shape[1]:
        
        # Complete scan and correction scan map
        comp_map = damage_map[:, :n_complete_scans]
        corr_map = damage_map[: , n_complete_scans:]

        # Minimum width the plots get
        min_width = 0.75

        width_ratios = [min_width + comp_map.shape[1] / damage_map.shape[1], min_width + corr_map.shape[1] / damage_map.shape[1]]

        # From https://stackoverflow.com/questions/32185411/break-in-x-axis-of-matplotlib
        fig, ax = plt.subplots(1, 2, facecolor='w', width_ratios=width_ratios)
        plt.subplots_adjust(wspace=0.075)

        comp_idx = n_complete_scans - 1
        corr_idx = corr_map.shape[1] - 1

        # Scale axis to that scan numbers are centerd under bin
        comp_extend=[-0.5, comp_idx + 0.5, comp_map.shape[0], 0]
        corr_extend=[n_complete_scans - 0.5, corr_idx + n_complete_scans + 0.5, comp_map.shape[0], 0]

        # PLot the actual images
        _ = ax[0].imshow(comp_map, origin='upper', extent=comp_extend, cmap=plt.rcParams['image.cmap'], aspect='auto', vmin=damage_map.min(), vmax=damage_map.max())
        im_corr = ax[1].imshow(corr_map, origin='upper', extent=corr_extend, cmap=plt.rcParams['image.cmap'], aspect='auto', vmin=damage_map.min(), vmax=damage_map.max())

        # Make colorbar for the im_corr map which contains the final map
        _make_cbar(fig=fig, damage_map=im_corr, damage=damage, ion_name=ion_name, add_cbar_axis=False, pad=0.275)

        # Hide spines between axes
        ax[0].spines['right'].set_visible(False)
        ax[1].spines['left'].set_visible(False)

        # Tick stuff
        ax[0].yaxis.tick_left()
        ax[0].tick_params(labelright=False)
        ax[1].set_yticks([])
        ax[0].yaxis.set_ticks(range(damage_map.shape[0]))  # Show ticks for every row

        # Only lable every 5th row when there are too many
        if damage_map.shape[0] >= 20:
            ax[0].yaxis.set_ticklabels([str(i) if i%5 == 0 else '' for i in range(len(ax[0].yaxis.get_ticklabels()))])
        
        # X axis labels
        for curr_x in ax:
            make_axis_int_only(curr_x)

        # Make second y axis for showing row locations in mm
        ax_mm = ax[1].twinx()
        ax_mm.set_ylim(row_separation * damage_map.shape[0], 0)

        ax[0].set_xlabel(r'Complete scan $\mathrm{\#_{scan}}$')
        ax[1].set_xlabel(r'Correction scan $\mathrm{\#_{corr}}$')
        ax[0].set_ylabel(r'Row $\mathrm{\#_{row}}$')
        ax_mm.set_ylabel('Relative row position / mm')

        align_axis(ax1=ax[0], ax2=ax_mm, v1=0, v2=0, axis='y')

        dmg_lbl, dmg_unt, dmg_trgt = _get_damage_label_unit_target(damage=damage, ion_name=ion_name)

        # Fake a little legend
        ax[0].text(s=r'$\mathrm{\mu}$='+"({:.1E}{}{:.1E}) {}".format(np.nanmean(comp_map), u'\u00b1', np.nanstd(comp_map), dmg_unt),
                    x=0.075, y=0.5, rotation=90, fontsize=10, va='center', ha='center',
                    bbox=dict(boxstyle='round', facecolor='white', edgecolor='grey', alpha=0.8),
                    transform=ax[0].transAxes)
        ax[1].text(s=r'$\mathrm{\mu}$='+"({:.1E}{}{:.1E}) {}".format(np.nanmean(corr_map), u'\u00b1', np.nanstd(corr_map), dmg_unt),
                    x=0.075, y=0.5, rotation=90, fontsize=10, va='center', ha='center',
                    bbox=dict(boxstyle='round', facecolor='white', edgecolor='grey', alpha=0.8),
                    transform=ax[1].transAxes)
        
        fig.suptitle(f"{dmg_lbl} on {dmg_trgt.lower()} area, row-resolved")

        # Make the break lines
        d = .015  # how big to make the diagonal lines in axes coordinates
        # arguments to pass plot, just so we don't keep repeating them
        kwargs = dict(transform=ax[0].transAxes, color='k', clip_on=False)
        ax[0].plot((1-d, 1+d), (-d, +d), **kwargs)
        ax[0].plot((1-d, 1+d), (1-d, 1+d), **kwargs)

        kwargs.update(transform=ax[1].transAxes)  # switch to the bottom axes
        ax[1].plot((-d, +d), (1-d, 1+d), **kwargs)
        ax[1].plot((-d, +d), (-d, +d), **kwargs)

    else:

        # Make figure
        fig, ax = plt.subplots()

        im = ax.imshow(damage_map, origin='upper', cmap=plt.rcParams['image.cmap'], aspect='auto')

        make_axis_int_only(ax)

        # Show ticks for every row
        ax.yaxis.set_ticks(range(damage_map.shape[0]))
        
        # Only lable every 5th row when there are too many
        if damage_map.shape[0] >= 20:
            ax.yaxis.set_ticklabels([str(i) if i%5 == 0 else '' for i in range(len(ax.yaxis.get_ticklabels()))])

        _make_cbar(fig=fig, damage_map=im, damage=damage, ion_name=ion_name, add_cbar_axis=False, pad=0.125)

        dmg_lbl, dmg_unt, dmg_trgt = _get_damage_label_unit_target(damage=damage, ion_name=ion_name)

        ax_mm = ax.twinx()
        ax_mm.set_ylim(row_separation * damage_map.shape[0], 0)

        # Fake a little legend
        ax.text(s=r'$\mathrm{\mu}$='+"({:.1E}{}{:.1E}) {}".format(np.nanmean(damage_map), u'\u00b1', np.nanstd(damage_map), dmg_unt),
                x=abs(ax.get_xlim()[0] - ax.get_xlim()[1]) * 0.225 + ax.get_xlim()[0],
                y=ax.get_ylim()[0]*0.05, rotation=0, fontsize=10,
                bbox=dict(boxstyle='round', facecolor='white', edgecolor='grey', alpha=0.8))

        # Axes labels
        ax.set_xlabel(r'Complete scan $\mathrm{\#_{scan}}$')
        ax.set_ylabel(r'Row $\mathrm{\#_{row}}$')
        ax_mm.set_ylabel('Relative row position / mm')
        ax.set_title(f"{dmg_lbl} on {dmg_trgt.lower()} area, row-resolved")

        align_axis(ax1=ax, ax2=ax_mm, v1=0, v2=0, axis='y')

    return fig, ax


def plot_scan_overview(overview, beam_data, daq_config, temp_data=None):

    def _win_from_timestamps(ts_data, other_data, ts_start, ts_stop, to_secs=False):
        idx_start, idx_stop = np.searchsorted(ts_data, [ts_start, ts_stop])
        d_ts, d_ot = ts_data[idx_start:idx_stop], other_data[idx_start:idx_stop]
        if to_secs:
            d_ts = d_ts - d_ts[0]
        return d_ts, d_ot
    
    def _to_dt(ts, delta=False):
        return [datetime.fromtimestamp(t) if not delta else timedelta(seconds=float(t)) for t in ts]
    
    # Plot scan overview
    if 'kappa' in daq_config and not np.isnan(daq_config['kappa']['nominal']):
        kappa = daq_config['kappa']['nominal']
        FluenceToTID = lambda f: irrad_consts.MEV_PER_GRAM_TO_MRAD * f / kappa * daq_config['stopping_power']
        TIDToFluence = lambda t: t * kappa / (irrad_consts.MEV_PER_GRAM_TO_MRAD * daq_config['stopping_power'])
        damage = lambda x: x * kappa
        dmg_label = r"1 MeV neutron fluence / $\mathrm{neq \ cm^{-2}}$"
    else:
        FluenceToTID = lambda f: irrad_consts.MEV_PER_GRAM_TO_MRAD * f * daq_config['stopping_power']
        TIDToFluence = lambda t: t  / (irrad_consts.MEV_PER_GRAM_TO_MRAD * daq_config['stopping_power'])
        damage = lambda x: x
        dmg_label = rf"{daq_config['ion'].capitalize()} fluence / $\mathrm{{{daq_config['ion']}s\ cm^{{-2}}}}$"

    # Make figure and gridspec on which to place subplots
    fig = plt.figure()
    gs = GridSpec(2, 2, height_ratios=[2.5, 1], width_ratios=[2.5, 1], wspace=0.3, hspace=0.15)
    
    # Make axes
    ax_complete = fig.add_subplot(gs[0])
    ax_beam = fig.add_subplot(gs[2], sharex=ax_complete)
    ax_result = fig.add_subplot(gs[1])
    
    # Set axes parameters
    ax_result.yaxis.set_tick_params(labelright=False, right=False, labelleft=True, left=True)
    ax_result.yaxis.grid()
    ax_result.set_xlabel('Row')
    ax_result.set_ylabel(dmg_label)

    # Make TID axis and plot title
    ax_tid = ax_result.secondary_yaxis('right', functions=(FluenceToTID, TIDToFluence))
    ax_complete.set_title("Irradiation overview", y=1.15, loc='right')
    
    # Axes container
    ax = (ax_complete, ax_beam, ax_result)

    # No labels on xaxis of main plots; add grid
    ax_complete.xaxis.set_tick_params(labelbottom=False)
    ax_beam.xaxis.set_tick_params(top=True)
    ax_complete.grid()
    ax_beam.grid()

    # Start/stop overview plot at beginning/end of irradiation
    start_ts, stop_ts = overview['row_hist']['center_timestamp'][0], overview['row_hist']['center_timestamp'][-1]
    chrono_ts_idxs = np.argsort(overview['row_hist']['center_timestamp'])

    ax_complete.bar(_to_dt(overview['row_hist']['center_timestamp'][chrono_ts_idxs]), damage(overview['row_hist']['primary_damage'][chrono_ts_idxs]), _to_dt(overview['row_hist']['duration'][chrono_ts_idxs], True) , label='Row fluence')
    ax_complete.errorbar(_to_dt(overview['scan_hist']['center_timestamp']), damage(overview['scan_hist']['primary_damage']), yerr=damage(overview['scan_hist']['primary_damage_error']), fmt='C1.', label='Scan fluence')
    ax_complete.set_ylabel(dmg_label)
    ax_complete.yaxis.offsetText.set(va='bottom', ha='center')

    # Plot mask of where irradiation was halted for longer than 30 seconds
    halt_criteria = overview['row_hist']['duration'].mean() + 3 * overview['row_hist']['duration'].std() + 10  # 10 seconds to acount for row switching and condition checking 
    halt_start_idxs = np.argwhere(np.diff(overview['row_hist']['center_timestamp'][chrono_ts_idxs]) > halt_criteria)
    for i in range(len(halt_start_idxs)):
        h_start = overview['row_hist']['center_timestamp'][chrono_ts_idxs][halt_start_idxs[i]]
        h_stop = overview['row_hist']['center_timestamp'][chrono_ts_idxs][halt_start_idxs[i]+1]
        ax_complete.bar(_to_dt(h_start), damage(overview['row_hist']['primary_damage'][chrono_ts_idxs][halt_start_idxs[i]]), _to_dt(h_stop-h_start, True),
                        align='edge', label='Scan halt' if i == 0 else '', color='gray', ls='-', alpha=0.33, zorder=-1)

    ax_complete.legend(loc='upper left', fontsize=10)    

    # Add scan number ticks
    ax_scan = ax_complete.secondary_xaxis('top')
    ax_scan.set_xlabel('Scan number')
    every_10nth_scan = len(overview['scan_hist']['number'])//10 + 1

    ax_scan.set_xticks(_to_dt(overview['scan_hist']['center_timestamp'][::every_10nth_scan]),
                       overview['scan_hist']['number'][::every_10nth_scan])

    ax_tid.set_ylabel('TID / Mrad')
    align_axis(ax1=ax_complete, ax2=ax_tid, v1=0, v2=0, axis='y')

    # Irradiations plotted happened across different days
    if datetime.fromtimestamp(start_ts).strftime('%d/%m/%Y') != datetime.fromtimestamp(stop_ts).strftime('%d/%m/%Y'):
        time_label = f"Time between {datetime.fromtimestamp(start_ts).strftime('%d/%m/%Y')} and {datetime.fromtimestamp(stop_ts).strftime('%d/%m/%Y')}"
        time_fmt = '%H'
    else:
        time_label = f"Time on {datetime.fromtimestamp(start_ts).strftime('%a %d/%m/%Y')}"
        time_fmt = '%H:%M'
    
    # Plot beam current
    beam_ts, beam_nanos = _win_from_timestamps(beam_data['timestamp'],
                                               beam_data['beam_current'] / irrad_consts.nano,
                                               start_ts,
                                               stop_ts,
                                               to_secs=False)
    ax_beam.plot(_to_dt(beam_ts), beam_nanos, label='Beam current')
    ax_beam.set_ylim(0, beam_nanos.max() * 1.25)
    ax_beam.set_ylabel(f"{daq_config['ion'].capitalize()} current / nA")
    ax_beam.set_xlabel(time_label)
    ax_beam.legend(loc='upper left', fontsize=8)


    # Plot last scan distribution
    ax_result.bar(overview['result_hist']['number'], damage(overview['result_hist']['primary_damage']), label='Result')
    ax_result.yaxis.offsetText.set(va='bottom', ha='center')

    if 'correction_scans' in overview:

        # Count the amount of individual scans and fluence inside
        indv_row_scans = dict(zip(overview['result_hist']['number'], [1] * len(overview['result_hist']['number'])))
        indv_row_offsets = dict(zip(overview['result_hist']['number'], damage(overview['result_hist']['primary_damage'])))
        corrections_scans_labels = []

        # Loop over individual scans
        for entry in overview['correction_scans']:

            row = entry['number']
            indv_damage = damage(entry['primary_damage'])

            ax_result.bar(row, indv_damage, bottom=indv_row_offsets[row], color=f"C{indv_row_scans[row]}")
            indv_row_offsets[row] += indv_damage
            corrections_scans_labels.append(indv_row_scans[row])
            indv_row_scans[row] += 1

        # Resulting mean fluence on 1D
        mean = np.nanmean(list(indv_row_offsets.values()))
        ax_result.axhline(y=mean, label="Mean", ls='--', lw=1, c='gray', zorder=10)

        leg1 = ax_result.legend(loc='upper center', fontsize=10)

        # Make custom colorbar to show number of correction scans, it's cheecky breeky-style
        max_indv_scans = max(indv_row_scans.values())
        cmap = mc.ListedColormap([f'C{i}' for i in range(1, max_indv_scans)])
        norm = mc.BoundaryNorm(np.arange(0.5, max_indv_scans), cmap.N)
        mappable = cm.ScalarMappable(cmap=cmap, norm=norm)
        ax_cbar = fig.add_subplot(gs[3])  # Add colorbar to lower right axes but make new axes there for it
        cb = plt.colorbar(mappable, ax=ax_cbar, ticks=range(1, max_indv_scans),label='n-th correction scan', location='top', orientation='horizontal')
        cb._long_axis().set(label_position='bottom', ticks_position='bottom')  # Put cbar at top of ax_cbar but put labels and ticks downward
        ax_cbar.remove()  # Cheeky-breeky remove the orginal axes where the cbar axes was attached at the top, hehe

        # Zoom in correction plot to see resulting distribution
        ax_result.set_ylim(min(damage(overview['result_hist']['primary_damage']))*0.95, max(list(indv_row_offsets.values()))*1.05)

        # Beautiful custom patch showing colorbar
        cmh = [Rectangle((0, 0), 1, 1)]
        handler_map = dict(zip(cmh, [HandlerColormap(cmap, num_stripes=max_indv_scans-1)]))
        ax_result.legend(handles=leg1.legendHandles+cmh,
                         labels=[t.get_text() for t in leg1.get_texts()] + ['Corrections'],
                         handler_map=handler_map, loc='upper center', fontsize=10)
    else:
        # Resulting mean fluence on 1D
        mean = np.nanmean(damage(overview['result_hist']['primary_damage']))
        ax_result.axhline(y=mean, label="Mean", ls='--', lw=1, c='gray', zorder=10)

        ax_result.legend(loc='upper center', fontsize=10)

        # Zoom in correction plot to see resulting distribution
        ax_result.set_ylim(min(damage(overview['result_hist']['primary_damage']))*0.95, max(damage(overview['result_hist']['primary_damage']))*1.05)

    if temp_data is not None:
        ax_temp = ax_beam.twinx()
        ax_temp.set_ylabel(r'Temperature / $\mathrm{^\circ C}$')
        for i, temp in enumerate(t for t in temp_data.dtype.names if t != 'timestamp'):
            temp_ts, temp_dt = _win_from_timestamps(temp_data['timestamp'],
                                                    temp_data[temp],
                                                    start_ts,
                                                    stop_ts,
                                                    to_secs=False)
            ax_temp.plot(_to_dt(temp_ts), temp_dt, c=f'C{i+1}', label=f'{temp} temp.')
        ax_temp.legend(loc='upper center', fontsize=8)

    ax_beam.xaxis.set_major_formatter(md.DateFormatter(time_fmt))
    for label in ax_beam.get_xticklabels(which='major'):
        label.set_ha('right')
        label.set_rotation(30)

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
                n, s = np.nanmean(plot_data['xdata']), np.nanstd(plot_data['xdata'])
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
    ax.legend(loc='best')
    
    return fig, ax


def plot_beam_current(timestamps, beam_current, ch_name=None, scan_data=None):

    dtfts = datetime.fromtimestamp(timestamps[0])

    plot_data = {'xdata': [datetime.fromtimestamp(ts) for ts in timestamps],
                 'ydata': beam_current,
                 'xlabel': f"{dtfts.strftime('%d %b %Y')}",
                 'ylabel': f"Cup channel {ch_name} current / nA",
                 'label': f"{ch_name or 'Beam'} current over {duration_str_from_secs(seconds=timestamps[-1]-timestamps[0])}{' irradiation' if scan_data else ''}",
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
    _, _, _, im = ax_hist_2d.hist2d(horizontal_pos, vertical_pos, bins=(n_bins, n_bins), norm=mc.LogNorm(), cmin=1)
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
    ax_hist_h.text(s=r'$\mathrm{\mu_h}$='+"({:.1f}{}{:.1f}) %".format(np.nanmean(horizontal_pos), u'\u00b1', np.nanstd(horizontal_pos)),
                   x=x_min*0.95,
                   y=ax_hist_h.get_ylim()[-1]*0.775, rotation=0, fontsize=10,
                   bbox=dict(boxstyle='round', facecolor='white', edgecolor='grey', alpha=0.33))
    ax_hist_v.text(s=r'$\mathrm{\mu_v}$='+"({:.1f}{}{:.1f}) %".format(np.nanmean(vertical_pos), u'\u00b1', np.nanstd(vertical_pos)),
                   x=ax_hist_v.get_xlim()[0]*0.925,
                   y=y_min*0.925, rotation=90, fontsize=10,
                   bbox=dict(boxstyle='round', facecolor='white', edgecolor='grey', alpha=0.33))

    return fig, (ax_hist_2d, ax_hist_h, ax_hist_v)


def plot_calibration(calib_data, ref_data, calib_sig, ref_sig, red_chi, beta_lambda, ion_name, ion_energy, hist=False):

    ion = get_ions()[ion_name]

    beta_const, lambda_const = beta_lambda

    fit_label=r'Linear fit: $\mathrm{I_{Beam} = \beta \cdot I_{SEE}}$;'
    fit_label += '\n\t' + r'$\beta=(%.2E \pm %.2E)$' % (beta_const.n, beta_const.s)
    fit_label += '\n\t' + r'$\lambda=\beta\ /\ 5V=(%.3f \pm %.3f) \ V^{-1}$' % (lambda_const.n, lambda_const.s)
    fit_label += '\n\t' + r'$\mathrm{SEY}=q_{%s}\ /\ \beta=(%.2f \pm %.2f)$' % (ion_name, (100.*ion.n_charge/beta_const).n, (100.*ion.n_charge/beta_const).s) + ' %'
    fit_label += '\n\t' + r'$\chi^2_{red}= %.2f\ $' % red_chi

    label_ion = f"{ion_energy:.3f} MeV {ion_name.lower()} data " r'($\Sigma$={}):'.format(len(calib_data)) + '\n' + f"SEE channel '{calib_sig}' vs. cup channel '{ref_sig}'"

    # Make figure and axis
    fig, ax = plot_generic_fig(plot_data={'xdata': calib_data,
                                          'ydata': ref_data,
                                          'xlabel': r"Secondary electron current $\mathrm{I_{SEE}}$ / nA",
                                          'ylabel': r"Beam current $\mathrm{I_{Beam}}$ / nA",
                                          'label': label_ion,
                                          'title':"Beam monitor calibration",
                                          'fmt':'C0.',
                                          'alpha': 0.33},
                               fit_data={'xdata': calib_data,
                                         'func': lin_odr,
                                         'fit_args': [[beta_const.n], calib_data],
                                         'fmt': 'C1-',
                                         'label': fit_label},
                               hist_data={'bins': (100, 100), 'norm': mc.LogNorm()} if hist else {})
    
    return fig, ax


def plot_fluence_distribution(fluence_data, ion, hardness_factor=1, stoping_power=1):

    plot_data = {
        'xdata': fluence_data,
        'xlabel': f"Fluence per scanned row / {ion}s/cm^2",
        'ylabel': '#',
        'label': "({:.2E}{}{:.2E}) {}s / cm^2".format(np.nanmean(fluence_data), u'\u00b1', np.nanstd(fluence_data), ion),
        'title': "Row fluence distribution",
        'fmt': 'C0'
    }

    fig, ax = plot_generic_fig(plot_data=plot_data, hist_data={'bins': 'stat'})
    ax_neq = ax.twiny()
    ax_neq.set_xlim([x * hardness_factor for x in ax.get_xlim()])
    ax_neq.set_xlabel('NIEL fluence / neq/cm^2')
    align_axis(ax, 0, ax_neq, 0, axis='x')
    ax_neq.grid(False)
    return fig, ax
