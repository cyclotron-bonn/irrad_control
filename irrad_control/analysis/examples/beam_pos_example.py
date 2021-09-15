import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import NullFormatter
from scipy.optimize import curve_fit
from matplotlib.colors import LogNorm

def gauss(x, mu, sigma, h):
    return h * np.exp(-0.5 * np.power((x - mu) / sigma, 2.))

path_to_data = ""  # Put your data here

# load data
data = np.loadtxt(path_to_data, unpack=True)
time = data[0] - data[0][0]
L, R, O, U, _ = (data[i] for i in range(1, 6))

x = -(L-R)/(L+R)
y = (O-U)/(O+U)

# To mm; Beam width was approx 5mm => +-1V = 2.5 mm
x*=2.5
y*=2.5

nullfmt = NullFormatter()         # no labels

# definitions for the axes
left, width = 0.125, 0.6
bottom, height = 0.125, 0.6
bottom_h = left_h = left + width + 0.01

rect_scatter = [left, bottom, width, height]
rect_histx = [left, bottom_h, width, 0.2]
rect_histy = [left_h, bottom, 0.2, height]

# start with a rectangular Figure
plt.figure(1, figsize=(6, 6))

axScatter = plt.axes(rect_scatter)
axHistx = plt.axes(rect_histx)
axHisty = plt.axes(rect_histy)

axScatter.grid()
axHistx.grid()
axHisty.grid()

# no labels
axHistx.xaxis.set_major_formatter(nullfmt)
axHisty.yaxis.set_major_formatter(nullfmt)

# the scatter plot:
#axScatter.scatter(x, y, label='Beam position over time:\n'+ r'%2.f s @ $\approx$ 15 Hz => 11678 entries ' % time[-1])
#heatmap , xedges, yedges = np.histogram2d(x, y, bins=(np.linspace(-.5, .5, 75),np.linspace(-0.15, 0.85, 75)))
#extent = [xedges[0], xedges[-1], yedges[0], yedges[-1]]
#im = axScatter.imshow(heatmap.T, origin='lower', extent=extent)
im = axScatter.hist2d(x, y, bins=100,cmin=1)#,norm=LogNorm())
axScatter.set_xlim(-0.85, 0.85)
axScatter.set_ylim(-0.85, 0.85)
plt.colorbar(im[-1], ax=axHisty)#,ticks=[0, 20, 40, 60, 80, 100])

# now determine nice limits by hand:
binwidth = 10e-3
xymax = np.max([np.max(np.fabs(x)), np.max(np.fabs(y))])
lim = (int(xymax/binwidth) + 1) * binwidth

l0 = r'Approx. beam position over $\approx$ %i minutes:' % int(round(time[-1]/60.))

bins = np.arange(-lim, lim + binwidth, binwidth)
hist_x = axHistx.hist(x, bins=bins)
hist_y = axHisty.hist(y, bins=bins, orientation='horizontal')

hist_x_corr = 0.5* (hist_x[1][:-1] + hist_x[1][1:])
hist_y_corr = 0.5* (hist_y[1][:-1] + hist_y[1][1:])

popt_x, pcov_x = curve_fit(gauss, hist_x_corr, hist_x[0])
popt_y, pcov_y = curve_fit(gauss, hist_y_corr, hist_y[0])#, p0=(0.15, 0.025, 1e4))

l1 = '\t' + r'Horizontal = $(%.2f \pm %.2f)$ $\mu$m' % (popt_x[0]*1e3, abs(popt_x[1])*1e3)
l2 ='\t' + r'Vertical = $(%.2f \pm %.2f)$ $\mu$m' % (popt_y[0]*1e3, abs(popt_y[1])*1e3)

axHistx.plot(hist_x_corr, gauss(hist_x_corr, *popt_x))
axHisty.plot(gauss(hist_y_corr, *popt_y), hist_y_corr)  # switched orientation


axScatter.plot([], [], ls='none', label=l0)
axScatter.plot([], [], ls='none', label=l1)
axScatter.plot([], [], ls='none', label=l2)
p1, = axScatter.plot([], [], 'C1-')

gauss_leg = axScatter.legend((p1,), ('Gaussian fits',), loc='upper center')
axScatter.add_artist(gauss_leg)

axHistx.set_xlim(axScatter.get_xlim())
axHisty.set_ylim(axScatter.get_ylim())

axScatter.legend(loc='lower center')

axScatter.set_xlabel('Horizontal / mm')
axScatter.set_ylabel('Vertical / mm')

plt.savefig('beam_pos_hist.png')
plt.savefig('beam_pos_hist.pdf')
