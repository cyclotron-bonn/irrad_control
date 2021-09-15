import matplotlib.pyplot as plt
import matplotlib.dates as md
import datetime as dt
from matplotlib.colors import LogNorm
from matplotlib.backends.backend_pdf import PdfPages


def plot_fig(plot_data, fit_data=None, hist_data=None, **sp_kwargs):
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
                bins = np.arange(n - 3 * s, n + 3 * s + binwidth, binwidth)
            else:
                bins = hist_data['bins']

            _, _, _ = ax.hist(plot_data['xdata'], bins=bins, label=plot_data['label'])
        elif len(hist_data['bins']) == 2:
            _, _, _, im = ax.hist2d(plot_data['xdata'], plot_data['ydata'], bins=hist_data['bins'], norm=hist_data['norm'], cmap=hist_data['cmap'], cmin=1,
                                    label=plot_data['label'])
            plt.colorbar(im)
        else:
            raise ValueError('bins must be 2D iterable of intsd or int')
    else:
        ax.plot(plot_data['xdata'], plot_data['ydata'], plot_data['fmt'], label=plot_data['label'])
    ax.grid()
    ax.legend(loc='upper left')

    return fig, ax


def plot_vs_time(timestamps, y_data, t_formatter='%Y-%m-%d %H:%M', ax=None):
    """

    Parameters
    ----------
    timestamps: ndarray
        Array of timestamps
    y_data: ndarray
        Array of data
    t_formatter: str
        Formatting for time
    ax: Matplotlib axis object

    Returns
    -------

    """

    # Convert timestamps to formatted datetime objects
    time_data = [dt.datetime.fromtimestamp(ts) for ts in timestamps]

    """
    Do the plotting here
    """

    # Apply correct time formatting
    ax.xaxis.set_major_formatted(md.DateFormatter(t_formatter))

    return ax
