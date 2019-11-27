import os
import numpy as np
import tables as tb
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from uncertainties import ufloat as uf
from matplotlib.backends.backend_pdf import PdfPages

def _create_figure_axis(figsize=(8,6)):
	"""Function to create a figure/axis to plot into"""
	
	return plt.subplots(figsize=figsize)

def plot_beam_info(beam_table, outfile=None, show=False):
	"""Function to visualize the beam properties such as position and current.
	We plot  beam current over time,  histogramm of beam current and 2D-hist of beam position"""
	
	# We will potenntially generate many figures
	_figs = []
	
	# Get the data
	timestamp = beam_table[:]['timestamp']
	seconds = timestamp - timestamp[0]
	beam_current = beam_table[:]['current_analog']  # 'current_digital' is only reference
	mask_current = beam_current > 1e-8  # Reject currents under 10 nAv
	beam_current_nA = beam_current[mask_current] * 1e9  # Scale to nA
	beam_pos_x = beam_table[:]['position_h_digital']
	beam_pos_y = beam_table[:]['position_v_digital']
	
	# Get something to plot into
	fig, ax = _create_figure_axis()
	
	# Set title and labels
	ax.set_title(r'Beam current over time')
	ax.set_xlabel(r'Time [s]')
	ax.set_ylabel(r'Beam current [nA]')
	
	# PLot
	ax.plot(seconds[mask_current], beam_current_nA, ls='-', label=r'Beam current')
	ax.legend(loc='upper left')
	
	# Make grid
	ax.grid()
	
	# Potential show
	if show:
		plt.show()
	
	# Add
	_figs.append(fig)
	
	# Get something to plot into
	fig, ax = _create_figure_axis()
	
	# Set title and labels
	ax.set_title(r'Beam current histogram')
	ax.set_xlabel(r'Beam current [nA]')
	ax.set_ylabel(r'#')
	
	# Get std. dev. and mean
	mu, sigma = np.mean(beam_current_nA), np.std(beam_current_nA)
	
	# Plot
	ax.hist(beam_current_nA, bins=50, label=r'Beam current = $(%.1f \pm %.1f)$ nA' % (mu, sigma))
	ax.legend(loc='upper left')
	
	# Make grid
	ax.grid()
	
	# Potential show
	if show:
		plt.show()
	
	# Add
	_figs.append(fig)
	
	# Get something to plot into
	fig, ax = _create_figure_axis()
	
	# Set title and labels
	ax.set_title(r'Beam position histogram')
	ax.set_xlabel(r'Horizontal relative position [%]')
	ax.set_ylabel(r'Vertical relative position [%]')
	
	# Get std. dev. and mean
	mu_pos_x, sigma_pos_x = np.mean(beam_pos_x), np.std(beam_pos_x)
	mu_pos_y, sigma_pos_y = np.mean(beam_pos_y), np.std(beam_pos_y)
	
	_label = 'Position of beam mean over {:.1f} hours:\n\t'.format(seconds[-1]/60**2)
	_label += r"x=$(%.1f \pm %.1f)$ percent\n\t" % (mu_pos_x, sigma_pos_x)
	_label += r"y=$(%.1f \pm %.1f)$ percent" % (mu_pos_y, sigma_pos_y)
	
	# Plot
	hist_pos_2d = ax.hist2d(beam_pos_x, beam_pos_y, bins=150, cmin=100, label=_label)
	ax.set_xlim(-100, 100)
	ax.set_ylim(-100, 100)
	plt.colorbar(hist_pos_2d[-1], ax=ax)
	ax.legend(loc='upper left')
	
	# Potential show
	if show:
		plt.show()
	
	# Add
	_figs.append(fig)
	
	# We can store this directly
	if outfile is not None:
		with PdfPages(outfile if outfile.endswith('.pdf') else outfile + 'pdf') as out:
			for _fig in _figs:
				out.savefig(_fig, bbox_inches='tight')
	
	return _figs
	
def plot_all():
	
	#data = tb.open_file('/home/leloup/ownCloud/phd_thesis/data/BPW34F_diodes/irradiated/HISKP/irradiation_3/diodes/1e13/1e13_diode_new_extraction.h5')
	
	#beam_table = data.root.Hochstromraum.Beam
	
	#plot_beam_info(beam_table, 'testii.pdf', True)
	pass

plot_all()
	
	
