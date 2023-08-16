import logging
import pyqtgraph as pg
import pyqtgraph.exporters as pg_ex
import numpy as np
import os
from matplotlib import cm as mcmaps, colors as mcolors
from PyQt5 import QtWidgets, QtCore, QtGui

# Package imports
from irrad_control.analysis.dtype import IrradHists
from irrad_control.ions import get_ions
from irrad_control.gui.widgets.util_widgets import GridContainer

# Matplotlib default colors
_MPL_COLORS = [tuple(round(255 * v) for v in rgb) for rgb in [mcolors.to_rgb(def_col) for def_col in mcolors.TABLEAU_COLORS]]

_BOLD_FONT = QtGui.QFont()
_BOLD_FONT.setBold(True)


class PlotWindow(QtWidgets.QMainWindow):
    """Window which only shows a PlotWidget as its central widget."""
        
    # PyQt signal which is emitted when the window closes
    closeWin = QtCore.pyqtSignal()

    def __init__(self, plot, parent=None):
        super(PlotWindow, self).__init__(parent)
        
        # PlotWidget to display in window
        self.pw = plot
        
        # Window appearance settings
        self.setWindowTitle(type(plot).__name__)
        self.screen = QtWidgets.QDesktopWidget().screenGeometry()
        self.setMinimumSize(int(0.25 * self.screen.width()), int(0.25 * self.screen.height()))
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        
        # Set plot as central widget
        self.setCentralWidget(self.pw)

    def closeEvent(self, _):
        self.closeWin.emit()
        self.close()


class PlotWrapperWidget(QtWidgets.QWidget):
    """Widget that wraps PlotWidgets and implements some additional features which allow to control the PlotWidgets content.
    Also adds button to show the respective PlotWidget in a QMainWindow"""

    def __init__(self, plot=None, plot_path=None, file_name=None, parent=None):
        super(PlotWrapperWidget, self).__init__(parent=parent)

        # Set a reasonable minimum size
        self.setMinimumSize(300, 300)

        # PlotWidget to display; set size policy 
        self.pw = plot
        self.pw.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.external_win = None

        # Main layout and sub layout for e.g. checkboxes which allow to show/hide curves in PlotWidget etc.
        self.setLayout(QtWidgets.QVBoxLayout())
        self.plot_options = GridContainer(name='Plot options' if not hasattr(self.pw, 'name') else '{} options'.format(self.pw.name))

        # Output path and file_name for screenshots
        self.plot_path = os.getcwd() if plot_path is None else plot_path
        self.file_name = type(plot).__name__ if file_name is None else file_name
        self.file_format = 'png'

        # Setup widget if class instance was initialized with plot
        if self.pw is not None:
            self._setup_widget()

    def _setup_widget(self):
        """Setup of the additional widgets to control the appearance and content of the PlotWidget"""

        _sub_layout_1 = QtWidgets.QHBoxLayout()
        _sub_layout_1.setSpacing(self.plot_options.grid.verticalSpacing())
        _sub_layout_2 = QtWidgets.QHBoxLayout()
        _sub_layout_2.setSpacing(self.plot_options.grid.verticalSpacing())

        # Create checkboxes in order to show/hide curves in plots
        if hasattr(self.pw, 'show_data') and hasattr(self.pw, 'curves'):
            _sub_layout_2.addWidget(QtWidgets.QLabel('Toggle curve{}:'.format('s' if len(self.pw.curves) > 1 else '')))
            all_checkbox = QtWidgets.QCheckBox('All')
            all_checkbox.setFont(_BOLD_FONT)
            all_checkbox.setChecked(True)
            _sub_layout_2.addWidget(all_checkbox)
            for curve in self.pw.curves:
                checkbox = QtWidgets.QCheckBox(curve)
                checkbox.setChecked(True)
                all_checkbox.stateChanged.connect(lambda _, cbx=checkbox: cbx.setChecked(all_checkbox.isChecked()))
                checkbox.stateChanged.connect(lambda v, n=checkbox.text(): self.pw.show_data(n, bool(v)))
                _sub_layout_2.addWidget(checkbox)

        _sub_layout_1.addWidget(QtWidgets.QLabel('Features:'))
        _sub_layout_1.addStretch()

        # Add possibility to en/disable showing curve statistics
        if hasattr(self.pw, 'enable_stats'):
            stats_checkbox = QtWidgets.QCheckBox('Enable statistics')
            stats_checkbox.setChecked(self.pw._show_stats)
            stats_checkbox.stateChanged.connect(lambda state: self.pw.enable_stats(bool(state)))
            stats_checkbox.setToolTip("Show curve statistics while hovering / clicking curve(s)")
            _sub_layout_1.addWidget(stats_checkbox)

        # Whenever x axis is time add spinbox to change time period for which data is shown
        if hasattr(self.pw, 'update_period'):

            # Add horizontal helper line if we're looking at scrolling data plot
            unit = self.pw.plt.getAxis('left').labelUnits or '[?]'
            label = self.pw.plt.getAxis('left').labelText or 'Value'
            self.helper_line = pg.InfiniteLine(angle=0, label=label + ': {value:.2E} ' + unit)
            self.helper_line.setMovable(True)
            self.helper_line.setPen(color='w', style=pg.QtCore.Qt.DashLine, width=2)
            if hasattr(self.pw, 'unitChanged'):
                self.pw.unitChanged.connect(lambda u: setattr(self.helper_line.label, 'format', self.pw.plt.getAxis('left').labelText + ': {value:.2E} ' + u))
                self.pw.unitChanged.connect(self.helper_line.label.valueChanged)
            hl_checkbox = QtWidgets.QCheckBox('Show helper line')
            hl_checkbox.stateChanged.connect(
                lambda v: self.pw.plt.addItem(self.helper_line) if v else self.pw.plt.removeItem(self.helper_line))
            _sub_layout_1.addWidget(hl_checkbox)

            # Spinbox for period to be shown on x axis
            spinbox_period = QtWidgets.QSpinBox()
            spinbox_period.setRange(1, 3600)
            spinbox_period.setValue(self.pw._period)
            spinbox_period.setPrefix('Time period: ')
            spinbox_period.setSuffix(' s')
            spinbox_period.valueChanged.connect(lambda v: self.pw.update_period(v))
            _sub_layout_1.addWidget(spinbox_period)

        if hasattr(self.pw, 'update_refresh_rate'):

            # Spinbox for plot refresh rate
            spinbox_refresh = QtWidgets.QSpinBox()
            spinbox_refresh.setRange(0, 60)
            spinbox_refresh.setValue(int(1000 / self.pw.refresh_timer.interval()))
            spinbox_refresh.setPrefix('Refresh rate: ')
            spinbox_refresh.setSuffix(' Hz')
            spinbox_refresh.valueChanged.connect(lambda v: self.pw.update_refresh_rate(v))
            _sub_layout_1.addWidget(spinbox_refresh)

        # Button to reset the contents of the self.pw
        if hasattr(self.pw, 'reset_plot'):
            self.btn_reset = QtWidgets.QPushButton()
            self.btn_reset.setIcon(self.btn_reset.style().standardIcon(QtWidgets.QStyle.SP_BrowserReload))
            self.btn_reset.setToolTip('Reset plot')
            self.btn_reset.setFixedSize(25, 25)
            self.btn_reset.clicked.connect(self.pw.reset_plot)
            _sub_layout_1.addWidget(self.btn_reset)

        # Button to save contents of self.pw.plt instance
        self.btn_save = QtWidgets.QPushButton()
        self.btn_save.setIcon(self.btn_save.style().standardIcon(QtWidgets.QStyle.SP_DriveFDIcon))
        self.btn_save.setToolTip('Save plot as PNG')
        self.btn_save.setFixedSize(25, 25)
        self.btn_save.clicked.connect(lambda: self.btn_open.setEnabled(False))
        self.btn_save.clicked.connect(self.save_plot)
        self.btn_save.clicked.connect(lambda: self.btn_open.setEnabled(True))

        # Button to move self.pw to PlotWindow instance
        self.btn_open = QtWidgets.QPushButton()
        self.btn_open.setIcon(self.btn_open.style().standardIcon(QtWidgets.QStyle.SP_TitleBarMaxButton))
        self.btn_open.setToolTip('Open plot in window')
        self.btn_open.setFixedSize(25, 25)
        self.btn_open.clicked.connect(self.move_to_win)
        self.btn_open.clicked.connect(lambda: self.layout().insertStretch(1))
        self.btn_open.clicked.connect(lambda: self.btn_open.setEnabled(False))
        self.btn_open.clicked.connect(lambda: self.btn_close.setEnabled(True))

        # Button to close self.pw to PlotWindow instance
        self.btn_close = QtWidgets.QPushButton()
        self.btn_close.setIcon(self.btn_close.style().standardIcon(QtWidgets.QStyle.SP_TitleBarCloseButton))
        self.btn_close.setToolTip('Close plot in window')
        self.btn_close.setFixedSize(25, 25)
        self.btn_close.setEnabled(False)
        self.btn_close.clicked.connect(lambda: self.btn_close.setEnabled(False))
        self.btn_close.clicked.connect(lambda: self.external_win.close())

        _sub_layout_1.addWidget(self.btn_save)
        _sub_layout_1.addWidget(self.btn_open)
        _sub_layout_1.addWidget(self.btn_close)

        self.plot_options.add_layout(_sub_layout_1)
        self.plot_options.add_layout(_sub_layout_2)
        
        # Insert everything into main layout
        self.layout().insertWidget(0, self.plot_options)
        self.layout().insertWidget(1, self.pw)

    def set_plot(self, plot):
        """Set PlotWidget and set up widgets"""
        self.pw = plot
        self._setup_widget()

    def move_to_win(self):
        """Move PlotWidget to PlotWindow. When window is closed, transfer widget back to self"""
        self.external_win = PlotWindow(plot=self.pw, parent=self)
        self.external_win.closeWin.connect(lambda: self.layout().takeAt(1))
        self.external_win.closeWin.connect(lambda: self.layout().insertWidget(1, self.pw))
        self.external_win.closeWin.connect(lambda: self.btn_open.setEnabled(True))
        self.external_win.show()

    def save_plot(self):

        exporter = pg_ex.ImageExporter(self.pw.plt)

        # Generate filename
        number = 0
        out_file = lambda n: os.path.join(self.plot_path, f'{self.file_name}_{n}.{self.file_format}')
        while os.path.isfile(out_file(number)):
            number += 1

        exporter.export(out_file(number))
        logging.info(f"Saved plot to {out_file(number)}")


class MultiPlotWidget(QtWidgets.QScrollArea):
    """Widget to display multiple plot in a matrix"""

    def __init__(self, plots=None, parent=None):
        super(MultiPlotWidget, self).__init__(parent)

        # Some basic settings
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        # Main widget is a vertical splitter
        self.main_splitter = QtWidgets.QSplitter()
        self.main_splitter.setOrientation(QtCore.Qt.Vertical)
        self.main_splitter.setChildrenCollapsible(False)

        # Colors
        p, r = self.palette(), self.backgroundRole()
        p.setColor(r, self.main_splitter.palette().color(QtGui.QPalette.AlternateBase))
        self.setPalette(p)
        self.setAutoFillBackground(True)

        # Set main widget
        self.setWidget(self.main_splitter)

        # Add initial plots
        if plots is not None:
            if any(isinstance(x, (list, tuple)) for x in plots):
                self.add_plot_matrix(plots)
            else:
                self.add_plots(plots)

    def add_plots(self, plots):

        # If we only add one plot; just add to layout
        if isinstance(plots, QtWidgets.QWidget):
            self.main_splitter.addWidget(plots)
        # *plots* is an iterable of plots
        elif isinstance(plots, (list, tuple)):
            # Create a horizontal splitter
            splitter = QtWidgets.QSplitter()
            splitter.setOrientation(QtCore.Qt.Horizontal)
            splitter.setChildrenCollapsible(False)
            # Loop over individual plots and add them
            for sub_plot in plots:
                splitter.addWidget(sub_plot)
            self.main_splitter.addWidget(splitter)  # Add to main layout
            splitter.setSizes([int(self.width() / len(plots))] * len(plots))  # Same width
        else:
            raise TypeError("*plot* must be individual or iterable of plot widgets")

    def add_plot_matrix(self, plot_matrix):

        if not isinstance(plot_matrix, (list, tuple)):
            raise ValueError("*plot* needs to be 2-dimensional iterable containing plots / QWidgets")

        for sub_plots in plot_matrix:
            self.add_plots(sub_plots)

    def wheelEvent(self, ev):
        """Override mousewheel; plots use mouse wheel event for zoom"""
        if ev.type() == QtCore.QEvent.Wheel:
            ev.ignore()


class IrradPlotWidget(pg.PlotWidget):
    """Base class for plot widgets"""

    def __init__(self, refresh_rate=20, parent=None):
        super(IrradPlotWidget, self).__init__(parent)

        # Actual plotitem
        self.plt = self.getPlotItem()

        # Store curves to be displayed and active curves under cursor
        self.curves = dict()
        self.active_curves = dict()  # Store channel which is currently active (e.g. statistics are shown)

        # Hold data
        self._data = dict()
        self._data_is_set = False

        # Timer for refreshing plots with a given time interval to avoid unnecessary updating / high load
        self.refresh_timer = QtCore.QTimer()

        # Connect timeout signal of refresh timer to refresh_plot method
        self.refresh_timer.timeout.connect(self.refresh_plot)

        # Start timer
        self.refresh_timer.start(int(1000 / refresh_rate))

        # Hold buttons which are inside the plot
        self._in_plot_btns = []

        # TextItem for showing statistic of curves; set invisible first, only show on user request
        self.stats_text = pg.TextItem(text='No statistics to show', border=pg.mkPen(color='w', style=pg.QtCore.Qt.SolidLine))
        self._static_stats_text = False
        self._show_stats = False  # Show statistics of curves
        self.stats_text.setVisible(False)

    def enable_stats(self, enable=True):

        def _manage_signals(sig, slot, connect):

            try:
                sig.connect(slot) if connect else sig.disconnect(slot)
            except Exception:
                logging.error('Signal {} not {} slot {}'.format(repr(sig), '{}connected {}'.format(*('', 'to') if connect else ('dis', 'from')), repr(slot)))

        # Set flag
        self._show_stats = enable

        # Signals
        _manage_signals(sig=self.plt.scene().sigMouseMoved, slot=self._set_active_curves, connect=enable)
        _manage_signals(sig=self.plt.scene().sigMouseClicked, slot=self._set_active_curves, connect=enable)
        _manage_signals(sig=self.plt.scene().sigMouseClicked, slot=self._toggle_static_stat_text, connect=enable)

        # Add/remove stats text from plt
        self.stats_text.setParentItem(self.plt if enable else None)

        if not enable:
            self.stats_text.setVisible(enable)

    def _toggle_static_stat_text(self, click):
        self._static_stats_text = not self._static_stats_text if any(self.active_curves.values()) else False
        self._set_active_curves(click)

    def _set_active_curves(self, event):
        """Method updating which curves are active; active curves statistics are shown on plot"""

        if self._static_stats_text:
            return

        # Check whether it was a click or move
        click = hasattr(event, 'button')

        event_pos = event if not click else event.scenePos()

        # Get mouse coordinates in the coordinate system of the plot
        pos = self.plt.vb.mapSceneToView(event_pos)

        # Update current active curves
        for curve in self.curves:
            if isinstance(self.curves[curve], pg.PlotCurveItem):
                self.active_curves[curve] = self.curves[curve].mouseShape().contains(pos) or self.curves[curve].getPath().contains(pos)
            elif isinstance(self.curves[curve], CrosshairItem):
                self.active_curves[curve] = True if self.curves[curve].intersect.pointsAt(pos) else False
            elif isinstance(self.curves[curve], pg.ImageItem):
                self.active_curves[curve] = self.plt.scene().sceneRect().contains(pos) and self.curves[curve] in self.plt.items
            else:
                self.active_curves[curve] = False

        # We have active curves
        if any(self.active_curves.values()):
            self.stats_text.setPos(event_pos)
            self.stats_text.setVisible(True)
        else:
            self.stats_text.setVisible(False)

    def _setup_plot(self):
        raise NotImplementedError('Please implement a _setup_plot method')

    def set_data(self):
        raise NotImplementedError('Please implement a set_data method')

    def refresh_plot(self):
        raise NotImplementedError('Please implement a refresh_plot method')

    def update_refresh_rate(self, refresh_rate):
        """Update rate with which the plot is drawn"""
        if refresh_rate == 0:
            logging.warning("{} display stopped. Data is not being buffered while not being displayed.".format(type(self).__name__))
            self.refresh_timer.stop()  # Stops QTimer
        else:
            self.refresh_timer.start(int(1000 / refresh_rate))  # Restarts QTimer with new updated interval

    def add_plot_button(self, btn):
        """Adds an in-plot button to the plotitem"""

        if btn not in self._in_plot_btns:
            self._in_plot_btns.append(btn)

        self._update_button_pos()

    def _update_button_pos(self, btn_spacing=20, x_offset=70, y_offset=5):

        btn_pos_x = x_offset
        btn_pos_y = y_offset

        is_visible = [b.isVisible() for b in self._in_plot_btns]

        for i, _btn in enumerate(self._in_plot_btns):

            # The first button will always be set to upper left corner
            # Check if the previous button was visible; if not, place at current position
            if i != 0 and is_visible[i - 1]:
                btn_pos_x += self._in_plot_btns[i - 1].boundingRect().width() + btn_spacing

            # Place button
            _btn.setPos(btn_pos_x, btn_pos_y)

    def show_data(self, curve=None, show=True):
        """Show/hide the data of curve in PlotItem. If *curve* is None, all curves are shown/hidden."""

        if curve is not None and curve not in self.curves:
            logging.error('{} data not in graph. Current graphs: {}'.format(curve, ','.join(self.curves.keys())))
            return

        _curves = [curve] if curve is not None else self.curves

        for _cu in _curves:
            if isinstance(self.curves[_cu], CrosshairItem):
                self.curves[_cu].add_to_plot() if show else self.curves[_cu].remove_from_plot()
                self.curves[_cu].add_to_legend() if show else self.curves[_cu].remove_from_legend()
            else:

                if not any(isinstance(self.curves[_cu], x) for x in (pg.InfiniteLine, pg.ImageItem)):
                    self.legend.addItem(self.curves[_cu], _cu) if show else self.legend.removeItem(_cu)

                self.plt.addItem(self.curves[_cu]) if show else self.plt.removeItem(self.curves[_cu])


class ScrollingIrradDataPlot(IrradPlotWidget):
    """PlotWidget which displays a set of irradiation data curves over time"""

    def __init__(self, channels, units=None, period=60, refresh_rate=20, colors=_MPL_COLORS, name=None, parent=None):
        super(ScrollingIrradDataPlot, self).__init__(refresh_rate=refresh_rate, parent=parent)

        self.channels = channels
        self.units = units
        self.name = name

        # Attributes for data visualization
        self._time = None  # array for timestamps
        self._start = 0  # starting timestamp of each cycle
        self._timestamp = 0  # timestamp of each incoming data
        self._offset = 0  # offset for increasing cycle time
        self._idx = 0  # cycling index through time axis
        self._period = period  # amount of time for which to display data; default, displaying last 60 seconds of data
        self._filled = False  # bool to see whether the array has been filled
        self._drate = None  # data rate
        self._colors = colors  # Colors to plot curves in

        # Setup the main plot
        self._setup_plot()

    def _setup_plot(self):
        """Setting up the plot. The Actual plot (self.plt) is the underlying PlotItem of the respective PlotWidget"""

        # Get plot item and setup
        self.plt.setDownsampling(auto=True)
        self.plt.setLabel('left', text='Signal', units='V' if self.units is None else self.units['left'])

        # Title
        self.plt.setTitle('' if self.name is None else self.name)

        # Additional axis if specified
        if self.units is not None and 'right' in self.units:
            self.plt.setLabel('right', text='Signal', units=self.units['right'])

        # X-axis is time
        self.plt.setLabel('bottom', text='Time', units='s')
        self.plt.showGrid(x=True, y=True, alpha=0.66)
        self.plt.setLimits(xMax=0)

        self.enable_stats()

        # Make legend entries for curves
        self.legend = pg.LegendItem(offset=(80, -50))
        self.legend.setParentItem(self.plt)

        # Make dict of curves and dict to hold active value indicating whether the user interacts with the curve
        for i, ch in enumerate(self.channels):
            self.curves[ch] = pg.PlotCurveItem(pen=self._colors[i % len(self._colors)])
            self.curves[ch].opts['mouseWidth'] = 20  # Needed for indication of active curves
            self.show_data(ch)  # Show data and legend

    def _set_stats(self):
        """Show curve statistics for active_curves which have been clicked or are hovered over"""

        current_actives = [curve for curve in self.active_curves if self.active_curves[curve]]

        if not current_actives:
            return

        n_actives = len(current_actives)

        # Update text for statistics widget
        current_stat_text = 'Curve stats of {} curve{}:\n'.format(n_actives, '' if n_actives == 1 else 's')

        # Loop over active curves and create current stats
        for curve in current_actives:

            # If data is not yet filled; mask all NaN values and invert bool mask
            mask = None if self._filled else ~np.isnan(self._data[curve])

            # Get stats
            if mask is None:
                mean, std, entries = self._data[curve].mean(), self._data[curve].std(), self._data[curve].shape[0]
            else:
                mean, std, entries = self._data[curve][mask].mean(), self._data[curve][mask].std(), self._data[curve][mask].shape[0]

            current_stat_text += '  '
            current_stat_text += curve + u': ({:.2E} \u00B1 {:.2E}) {} (#{})'.format(mean, std, self.plt.getAxis('left').labelUnits, entries)
            current_stat_text += '\n' if curve != current_actives[-1] else ''

        # Set color and text
        current_stat_color = (100, 100, 100) if n_actives != 1 else self.curves[current_actives[0]].opts['pen'].color()
        self.stats_text.fill = pg.mkBrush(color=current_stat_color, style=pg.QtCore.Qt.SolidPattern)
        self.stats_text.setText(current_stat_text)

    def reset_plot(self):
        self._idx, self._time, self._data_is_set = 0, None, False

    def set_data(self, meta, data):
        """Set the data of the plot. Input data is data plus meta data"""

        # Store timestamp of current data
        self._timestamp = meta['timestamp']

        # Set data rate if available
        if 'data_rate' in meta:
            self._drate = meta['data_rate']

        # Get data rate from data in order to set time axis
        if self._time is None:
            if 'data_rate' in meta:
                self._drate = meta['data_rate']
                shape = int(round(self._drate) * self._period + 1)
                self._time = np.full(shape=shape, fill_value=np.nan)
                for ch in self.channels:
                    self._data[ch] = np.full(shape=shape, fill_value=np.nan)
                self._data_is_set = True

        # Fill data
        else:

            # If we made one cycle, start again from the beginning
            if self._idx == self._time.shape[0]:
                self._idx = 0
                self._filled = True

            # If we start a new cycle, set new start timestamp and offset
            if self._idx == 0:
                self._start = self._timestamp
                self._offset = 0

            # Set time axis
            self._time[self._idx] = self._start - self._timestamp + self._offset

            # Increment index
            self._idx += 1

            # Set data in curves
            for ch in self.channels:
                # Shift data to the right and set 0th element
                self._data[ch][1:] = self._data[ch][:-1]
                self._data[ch][0] = data[ch]

    def refresh_plot(self):
        """Refresh the plot. This method is supposed to be connected to the timeout-Signal of a QTimer"""

        if self._data_is_set:
            for curve in self.curves:

                # Update data of curves
                if not self._filled:
                    mask = ~np.isnan(self._data[curve])  # Mask all NaN values and invert bool mask
                    self.curves[curve].setData(self._time[mask], self._data[curve][mask])
                else:
                    self.curves[curve].setData(self._time, self._data[curve])

            # Only calculate statistics if we look at them
            if self._show_stats:
                self._set_stats()

    def update_axis_scale(self, scale, axis='left'):
        """Update the scale of current axis"""
        self.plt.getAxis(axis).setScale(scale=scale)

    def update_period(self, period):
        """Update the period of time for which the data is displayed in seconds"""

        # Update attribute
        self._period = period

        # Create new data and time
        shape = int(round(self._drate) * self._period + 1)
        new_data = dict([(ch, np.full(shape=shape, fill_value=np.nan)) for ch in self.channels])
        new_time = np.full(shape=shape, fill_value=np.nan)

        # Check whether new time and data hold more or less indices
        decreased = self._time.shape[0] >= shape

        if decreased:
            # Cut time axis
            new_time = self._time[:shape]

            # If filled before, go to 0, else go to 0 if current index is bigger than new shape
            if self._filled:
                self._idx = 0
            else:
                self._idx = 0 if self._idx >= shape else self._idx

            # Set wheter the array is now filled
            self._filled = True if self._idx == 0 else False

        else:
            # Extend time axis
            new_time[:self._time.shape[0]] = self._time

            # If array was filled before, go to last time, set it as offset and start from last timestamp
            if self._filled:
                self._idx = self._time.shape[0]
                self._start = self._timestamp
                self._offset = self._time[-1]

            self._filled = False

        # Set new time and data
        for ch in self.channels:
            if decreased:
                new_data[ch] = self._data[ch][:shape]
            else:
                new_data[ch][:self._data[ch].shape[0]] = self._data[ch]

        # Update
        self._time = new_time
        self._data = new_data


class IrradDataHist(IrradPlotWidget):
    """This implements a 1D histogram plot with an additional indicator of where the latest entry was"""

    def __init__(self, hist_config, xlabel=None, unit=None, name=None, refresh_rate=10, parent=None):
        super(IrradDataHist, self).__init__(refresh_rate=refresh_rate, parent=parent)

        self._data['hist'], self._data['edges'], self._data['centers'] = hist_config
        self.unit = unit or 'a.u.'
        self.name = name or type(self).__name__
        self.xlabel = xlabel or 'Signal'

        self._setup_plot()

    def _setup_plot(self):

        # Get plot item and setup
        self.plt.setDownsampling(auto=True)
        self.plt.setTitle(self.name)
        self.plt.setLabel('left', text='#')
        self.plt.setLabel('bottom', text=self.xlabel, units=self.unit)
        self.plt.getAxis('left').enableAutoSIPrefix(False)
        self.plt.showGrid(x=True, y=True)
        self.plt.setLimits(xMin=np.min(self._data['edges']), xMax=np.max(self._data['edges']), yMin=0)
        self.legend = pg.LegendItem(offset=(80, 80))
        self.legend.setParentItem(self.plt)

        self.enable_stats()

        # Histogram of fraction
        self.curves['hist'] = pg.PlotCurveItem(name='Histogram')
        self.curves['hist'].setFillLevel(0.33)
        self.curves['hist'].setBrush(pg.mkBrush(color=_MPL_COLORS[0]))

        # Init items needed
        self.curves['value'] = CrosshairItem(color=_MPL_COLORS[1], name='Current value')
        self.curves['value'].v_shift_line.setValue(1)  # Make crosshair point visible above 0
        self.curves['value'].v_shift_line.setVisible(False)  # We need x and y for the dot in the middle but we don't want horizontal line to be visible
        self.curves['value'].set_legend(self.legend)
        self.curves['value'].set_plotitem(self.plt)

        # Show data and legend
        for curve in self.curves:
            self.show_data(curve)

    def set_data(self, data):
        # Store current fraction
        self._data['value'] = data
        self._data_is_set = True

    def update_hist(self, data):
        # Histogram
        self._data['hist'][data] += 1
        self._data['hist_idx'] = data

    def _set_stats(self):
        """Show curve statistics for active_curves which have been clicked or are hovered over"""

        current_actives = [curve for curve in self.active_curves if self.active_curves[curve]]

        if not current_actives:
            return

        n_actives = len(current_actives)

        # Update text for statistics widget
        current_stat_text = 'Curve stats of {} curve{}:\n'.format(n_actives, '' if n_actives == 1 else 's')

        # Loop over active curves and create current stats
        for curve in current_actives:

            current_stat_text += '  '

            # Histogram stats
            if 'hist' in curve:
                try:
                    mean = np.average(self._data['centers'], weights=self._data['hist'])
                    std = np.sqrt(np.average((self._data['centers'] - mean)**2, weights=self._data['hist']))
                except ZeroDivisionError:  # Weights sum up to 0; no histogram entries
                    mean = std = np.nan
                current_stat_text += curve + u': ({:.2f} \u00B1 {:.2f}) {}'.format(mean, std, self.plt.getAxis('bottom').labelUnits)

            else:
                current_stat_text += curve + u': {:.2f} {}'.format(self._data['value'], self.plt.getAxis('bottom').labelUnits)

            current_stat_text += '\n' if curve != current_actives[-1] else ''

        # Set color and text
        current_stat_color = (100, 100, 100)
        self.stats_text.fill = pg.mkBrush(color=current_stat_color, style=pg.QtCore.Qt.SolidPattern)
        self.stats_text.setText(current_stat_text)

    def refresh_plot(self):
        """Refresh the plot. This method is supposed to be connected to the timeout-Signal of a QTimer"""

        # test if 'set_data' has been called
        if self._data_is_set:
            for curve in self.curves:

                if curve == 'hist':
                    self.curves[curve].setData(x=self._data['edges'], y=self._data['hist'], stepMode=True)
                if curve == 'value':
                    self.curves[curve].set_position(x=self._data['value'], y=self._data['hist'][self._data['hist_idx']])

            if self._show_stats:
                self._set_stats()


class RawDataPlot(ScrollingIrradDataPlot):
    """Plot for displaying the raw data of all channels of the respective ADC over time.
        Data is displayed in rolling manner over period seconds. The plot  unit can be switched between Volt and Ampere"""

    unitChanged = QtCore.pyqtSignal(str)

    def __init__(self, channels, daq_device=None, parent=None):

        self.use_unit = 'V'

        # Call __init__ of ScrollingIrradDataPlot
        super(RawDataPlot, self).__init__(channels=channels, units={'left': self.use_unit},
                                          name=type(self).__name__ + ('' if daq_device is None else ' ' + daq_device),
                                          parent=parent)

        # Make in-plot button to switch between units
        unit_btn = PlotPushButton(plotitem=self.plt, text='Switch unit ({})'.format('A'))
        unit_btn.clicked.connect(self.change_unit)

        # Connect to signal
        for con in [lambda u: self.plt.getAxis('left').setLabel(text='Signal', units=u),
                    lambda u: unit_btn.setText('Switch unit ({})'.format('A' if u == 'V' else 'V'))]:
            self.unitChanged.connect(con)

        # Add
        self.add_plot_button(unit_btn)

    def change_unit(self):
        self.use_unit = 'V' if self.use_unit == 'A' else 'A'
        self.unitChanged.emit(self.use_unit)

        # Restart the time of incoming data
        self.reset_plot()

    def set_data(self, meta, data):
        """Overwrite set_data method in order to show raw data in Ampere and Volt"""
        raw_data = data['current'] if self.use_unit == 'A' else data['voltage']
        super(RawDataPlot, self).set_data(meta=meta, data=raw_data)


class RadMonitorDataPlot(ScrollingIrradDataPlot):

    unitChanged = QtCore.pyqtSignal(str)

    def __init__(self, channels, daq_device=None, parent=None):

        self.uSv = '{}Sv/h'.format(u'\u00B5')

        self.use_unit = self.uSv

        super(RadMonitorDataPlot, self).__init__(channels=channels, units={'left': self.use_unit},
                                                 name=type(self).__name__ + ('' if daq_device is None else ' ' + daq_device),
                                                 parent=parent)

        # Make in-plot button to switch between units
        unit_btn = PlotPushButton(plotitem=self.plt, text='Switch unit ({})'.format('Hz'))
        unit_btn.clicked.connect(self.change_unit)

        # Connect to signal
        for con in [lambda u: self.plt.getAxis('left').setLabel(text='Frequency' if u == 'Hz' else 'Dose Rate', units=u),
                    lambda u: unit_btn.setText('Switch unit ({})'.format('Hz' if u == self.uSv else self.uSv))]:
            self.unitChanged.connect(con)

        # Add
        self.add_plot_button(unit_btn)

    def change_unit(self):
        self.use_unit = 'Hz' if self.use_unit == self.uSv else self.uSv
        self.unitChanged.emit(self.use_unit)

        # Restart the time of incoming data
        self.reset_plot()

    def set_data(self, meta, data):
        """Overwrite set_data method in order to show raw data in Ampere and Volt"""
        raw_data = data['frequency'] if self.use_unit == 'Hz' else data['dose_rate']
        super(RadMonitorDataPlot, self).set_data(meta=meta, data={'rad_monitor': raw_data})


class PlotPushButton(pg.TextItem):
    """Implements a in-plot push button for a PlotItem"""

    clicked = QtCore.pyqtSignal()

    def __init__(self, plotitem, **kwargs):

        if 'border' not in kwargs:
            kwargs['border'] = pg.mkPen(color='w', style=pg.QtCore.Qt.SolidLine)

        super(PlotPushButton, self).__init__(**kwargs)

        self.setParentItem(plotitem)
        self.setOpacity(0.7)
        self.btn_area = QtCore.QRectF(self.mapToParent(self.boundingRect().topLeft()), self.mapToParent(self.boundingRect().bottomRight()))

        # Connect to relevant signals
        plotitem.scene().sigMouseMoved.connect(self._check_hover)
        plotitem.scene().sigMouseClicked.connect(self._check_click)

    def setPos(self, *args, **kwargs):
        super(PlotPushButton, self).setPos(*args, **kwargs)
        self.btn_area = QtCore.QRectF(self.mapToParent(self.boundingRect().topLeft()), self.mapToParent(self.boundingRect().bottomRight()))

    def setFill(self, *args, **kwargs):
        self.fill = pg.mkBrush(*args, **kwargs)

    def _check_hover(self, evt):
        if self.btn_area.contains(evt):
            self.setOpacity(1.0)
        else:
            self.setOpacity(0.7)

    def _check_click(self, b):
        if self.btn_area.contains(b.scenePos()):
            self.clicked.emit()


class BeamCurrentPlot(ScrollingIrradDataPlot):
    """Plot for displaying the proton beam current over time. Data is displayed in rolling manner over period seconds"""

    def __init__(self, channels, ion, parent=None):

        # Call __init__ of ScrollingIrradDataPlot
        super(BeamCurrentPlot, self).__init__(channels=channels,
                                              name=type(self).__name__,
                                              parent=parent)
        # Scale between beam current and number of ions per second
        ion_scale = get_ions()[ion].rate(1)
        self.plt.setLabel('right', text=f'Ion rate', units=f'{ion.capitalize()}s / s')
        self.plt.setLabel('left', text='Beam current', units='A')                                  
        self.plt.getAxis('right').enableAutoSIPrefix(False)
        self.plt.getAxis('right').setScale(scale=ion_scale)
        

class TemperatureDataPlot(ScrollingIrradDataPlot):

    def __init__(self, channels, daq_device=None, parent=None):

        super(TemperatureDataPlot, self).__init__(channels=channels, units={'right': 'C', 'left': 'C'},
                                                  name=type(self).__name__ + ('' if daq_device is None else ' ' + daq_device),
                                                  parent=parent)

        self.plt.setLabel('left', text='Temperature', units='C')
        self.plt.hideAxis('left')
        self.plt.showAxis('right')
        self.plt.setLabel('right', text='Temperature', units='C')


class CrosshairItem:
    """This class implements three pyqtgraph items in order to display a reticle with a circle in its intersection."""

    def __init__(self, color, name, intersect_symbol=None, horizontal=True, vertical=True):

        if not horizontal and not vertical:
            raise ValueError('At least one of horizontal or vertical beam position must be true!')

        # Whether to show horizontal and vertical lines
        self.horizontal = horizontal
        self.vertical = vertical

        # Init items needed
        self.h_shift_line = pg.InfiniteLine(angle=90)
        self.v_shift_line = pg.InfiniteLine(angle=0)
        self.intersect = pg.ScatterPlotItem()

        # Drawing style
        self.h_shift_line.setPen(color=color, style=pg.QtCore.Qt.SolidLine, width=2)
        self.v_shift_line.setPen(color=color, style=pg.QtCore.Qt.SolidLine, width=2)
        self.intersect.setPen(color=color, style=pg.QtCore.Qt.SolidLine)
        self.intersect.setBrush(color=color)
        self.intersect.setSymbol('o' if intersect_symbol is None else intersect_symbol)
        self.intersect.setSize(10)

        # Items
        self.items = []

        # Add the respective lines
        if self.horizontal and self.vertical:
            self.items = [self.intersect, self.h_shift_line, self.v_shift_line]
        elif self.horizontal:
            self.items.append(self.h_shift_line)
        else:
            self.items.append(self.v_shift_line)

        self.legend = None
        self.plotitem = None
        self.name = name

    def set_position(self, x=None, y=None):

        if x is None and y is None:
            raise ValueError('Either x or y position have to be given!')

        if self.horizontal:
            _x = x if x is not None else self.h_shift_line.value()

        if self.vertical:
            _y = y if y is not None else self.v_shift_line.value()

        if self.horizontal and self.vertical:
            self.h_shift_line.setValue(_x)
            self.v_shift_line.setValue(_y)
            self.intersect.setData([_x], [_y])
        elif self.horizontal:
            self.h_shift_line.setValue(_x)
        else:
            self.v_shift_line.setValue(_y)

    def set_plotitem(self, plotitem):
        self.plotitem = plotitem

    def set_legend(self, legend):
        self.legend = legend

    def add_to_plot(self, plotitem=None):

        if plotitem is None and self.plotitem is None:
            raise ValueError('PlotItem item needed!')

        for item in self.items:
            if plotitem is None:
                self.plotitem.addItem(item)
            else:
                plotitem.addItem(item)

    def add_to_legend(self, label=None, legend=None):

        if legend is None and self.legend is None:
            raise ValueError('LegendItem needed!')

        _lbl = label if label is not None else self.name

        if legend is None:
            self.legend.addItem(self.intersect, _lbl)
        else:
            legend.addItem(self.intersect, _lbl)

    def remove_from_plot(self, plotitem=None):

        if plotitem is None and self.plotitem is None:
            raise ValueError('PlotItem item needed!')

        for item in self.items:
            if plotitem is None:
                self.plotitem.removeItem(item)
            else:
                plotitem.removeItem(item)

    def remove_from_legend(self, label=None, legend=None):

        if legend is None and self.legend is None:
            raise ValueError('LegendItem needed!')

        _lbl = label if label is not None else self.name

        if legend is None:
            self.legend.removeItem(_lbl)
        else:
            legend.removeItem(_lbl)


class BeamPositionPlot(IrradPlotWidget):
    """
    Plot for displaying the beam position. The position is displayed from analog and digital data if available.
    """

    def __init__(self, daq_setup, daq_device=None, name=None, add_hist=True, parent=None):
        super(BeamPositionPlot, self).__init__(parent=parent)

        # Init class attributes
        self.daq_setup = daq_setup
        self.ro_types = daq_setup['readout']['types']
        self.daq_device = daq_device
        self.hist_types = IrradHists()
        self._add_hist = add_hist
        self.name = name if name is not None else type(self).__name__ if self.daq_device is None else type(self).__name__ + ' ' + self.daq_device

        # Setup the main plot
        self._setup_plot()

    def _setup_plot(self):

        # Get plot item and setup
        self.plt.setDownsampling(auto=True)
        self.plt.setTitle(self.name)
        self.plt.setLabel('left', text='Vertical displacement', units='%')
        self.plt.setLabel('bottom', text='Horizontal displacement', units='%')
        self.plt.showGrid(x=True, y=True, alpha=0.99)
        self.plt.setRange(xRange=self.hist_types['beam_position']['range'][0], yRange=self.hist_types['beam_position']['range'][1])
        self.plt.setLimits(**dict([(k, self.hist_types['beam_position']['range'][0 if i < 2 else 1][i % 2]) for i, k in enumerate(('xMin', 'xMax', 'yMin', 'yMax'))]))
        self.plt.hideButtons()

        self.enable_stats()

        v_line = self.plt.addLine(x=0, pen={'color': 'w', 'style': pg.QtCore.Qt.DashLine})
        h_line = self.plt.addLine(y=0., pen={'color': 'w', 'style': pg.QtCore.Qt.DashLine})
        _ = pg.InfLineLabel(line=h_line, text='Left', position=0.05, movable=False)
        _ = pg.InfLineLabel(line=h_line, text='Right', position=0.95, movable=False)
        _ = pg.InfLineLabel(line=v_line, text='Up', position=0.95, movable=False)
        _ = pg.InfLineLabel(line=v_line, text='Down', position=0.05, movable=False)
        self.legend = pg.LegendItem(offset=(80, -50))
        self.legend.setParentItem(self.plt)

        if any(all(x in self.ro_types for x in y) for y in [('sem_left', 'sem_right'), ('sem_up', 'sem_down')]):
            sig = 'beam_position'
            self.curves[sig] = CrosshairItem(color=_MPL_COLORS[1], name=sig,
                                             horizontal='sem_left' in self.ro_types and 'sem_right' in self.ro_types,
                                             vertical='sem_up' in self.ro_types and 'sem_down' in self.ro_types)
            # Add 2D histogram
            if self._add_hist and self.curves[sig].horizontal and self.curves[sig].vertical:
                self.add_2d_hist(curve=sig, autoDownsample=True, opacity=0.66, cmap='hot')

        # Show data and legend
        if self.curves:
            for curve in self.curves:
                if isinstance(self.curves[curve], CrosshairItem):
                    self.curves[curve].set_legend(self.legend)
                    self.curves[curve].set_plotitem(self.plt)
                self.show_data(curve)

    def add_2d_hist(self, curve, cmap='hot', **kwargs):

        if curve not in self.curves:
            logging.error("Can only add histogram to existing curve")
            return

        hist_name = curve + '_hist'

        # Add hist data
        bins = self.hist_types[curve]['bins']
        plot_range = self.hist_types[curve]['range']
        hist, edges, centers = self.hist_types.create_hist(curve)
        self._data[hist_name] = {'hist': hist, 'edges': edges, 'centers': centers}

        if 'lut' not in kwargs:
            # Create colormap and init
            colormap = mcmaps.get_cmap(cmap)
            colormap._init()

            # Convert matplotlib colormap from 0-1 to 0 -255 for Qt
            lut = (colormap._lut * 255).view(np.ndarray)
            # Update kw
            kwargs['lut'] = lut

        get_scale = lambda plt_range, n_bins: float(abs(plt_range[0] - plt_range[1])) / n_bins

        # Add and manage position
        tr = pg.QtGui.QTransform()
        tr.translate(plot_range[0][0], plot_range[1][0])
        tr.scale(get_scale(plot_range[0], bins[0]), get_scale(plot_range[1], bins[1]))
        self.curves[hist_name] = pg.ImageItem(**kwargs)
        self.curves[hist_name].setTransform(tr)
        self.curves[hist_name].setZValue(-10)

    def set_data(self, data):

        sig = 'beam_position'

        pos_data = data['data']['position']
        h_shift = None if 'h' not in pos_data else pos_data['h']
        v_shift = None if 'v' not in pos_data else pos_data['v']

        # Update data
        self._data[sig] = (h_shift, v_shift)
        self._data_is_set = True

    def update_hist(self, data):
        sig = 'beam_position'
        if sig + '_hist' in self.curves:
            idx_x, idx_y = data
            self._data[sig + '_hist']['hist'][idx_x, idx_y] += 1

    def _set_stats(self):
        """Show curve statistics for active_curves which have been clicked or are hovered over"""

        current_actives = [curve for curve in self.active_curves if self.active_curves[curve]]

        if not current_actives:
            return

        n_actives = len(current_actives)

        # Update text for statistics widget
        current_stat_text = 'Curve stats of {} curve{}:\n'.format(n_actives, '' if n_actives == 1 else 's')

        # Loop over active curves and create current stats
        for curve in current_actives:

            current_stat_text += '  '

            # Histogram stats
            if 'hist' in curve:
                v = np.sum(self._data[curve]['hist'], axis=0)
                h = np.sum(self._data[curve]['hist'], axis=1)
                try:  # Weights are fine
                    mean_h = np.average(self._data[curve]['centers'][0], weights=h)
                    std_h = np.sqrt(np.average((self._data[curve]['centers'][0] - mean_h)**2, weights=h))
                    mean_v = np.average(self._data[curve]['centers'][0], weights=v)
                    std_v = np.sqrt(np.average((self._data[curve]['centers'][1] - mean_v) ** 2, weights=v))
                except ZeroDivisionError:  # Weights sum up to 0; no histogram entries
                    mean_h = std_h = mean_v = std_v = np.nan

                current_stat_text += curve + ':\n    '
                current_stat_text += u'Horizontal: ({:.2f} \u00B1 {:.2f}) {}'.format(mean_h, std_h, self.plt.getAxis('bottom').labelUnits) + '\n    '
                current_stat_text += u'Vertical: ({:.2f} \u00B1 {:.2f}) {}'.format(mean_v, std_v, self.plt.getAxis('left').labelUnits)

            else:
                current_stat_text += curve + ':\n    ' + u'Position: ({:.2f}, {:.2f}) {}'.format(self._data[curve][0],
                                                                                                 self._data[curve][1],
                                                                                                 self.plt.getAxis('bottom').labelUnits)

            current_stat_text += '\n' if curve != current_actives[-1] else ''

        # Set color and text
        current_stat_color = (100, 100, 100)
        self.stats_text.fill = pg.mkBrush(color=current_stat_color, style=pg.QtCore.Qt.SolidPattern)
        self.stats_text.setText(current_stat_text)

    def refresh_plot(self):
        """Refresh the plot. This method is supposed to be connected to the timeout-Signal of a QTimer"""

        if self._data_is_set:
            for sig in self.curves:
                if sig not in self._data:
                    continue
                if isinstance(self.curves[sig], CrosshairItem):
                    self.curves[sig].set_position(*self._data[sig])
                else:
                    self.curves[sig].setImage(self._data[sig]['hist'])

            if self._show_stats:
                self._set_stats()


class FluenceHist(IrradPlotWidget):
    """
        Plot for displaying the beam position. The position is displayed from analog and digital data if available.
        """

    def __init__(self, n_rows, kappa, refresh_rate=5, daq_device=None, parent=None):
        super(FluenceHist, self).__init__(refresh_rate=refresh_rate, parent=parent)

        # Init class attributes
        self.daq_device = daq_device
        self.n_rows = n_rows
        self.kappa = kappa

        self._data['hist_rows'] = np.arange(self.n_rows + 1)

        # Setup the main plot
        self._setup_plot()

    def _setup_plot(self):

        # Get plot item and setup
        self.plt.setDownsampling(auto=True)
        self.plt.setTitle(type(self).__name__ if self.daq_device is None else type(self).__name__ + ' ' + self.daq_device)
        self.plt.setLabel('left', text='Proton fluence', units='cm^-2')
        self.plt.setLabel('right', text='Neutron fluence', units='cm^-2')
        self.plt.setLabel('bottom', text='Scan row')
        self.plt.getAxis('left').enableAutoSIPrefix(False)
        self.plt.getAxis('right').enableAutoSIPrefix(False)
        self.plt.getAxis('right').setScale(self.kappa)
        self.plt.setLimits(xMin=0, xMax=self.n_rows, yMin=0)
        self.legend = pg.LegendItem(offset=(80, 80))
        self.legend.setParentItem(self.plt)

        # Histogram of fluence per row
        self.curves['hist'] = pg.PlotCurveItem()
        self.curves['hist'].setFillLevel(0.33)
        self.curves['hist'].setBrush(pg.mkBrush(color=_MPL_COLORS[0]))

        # Points at respective row positions
        self.curves['points'] = pg.ScatterPlotItem()
        self.curves['points'].setPen(color=_MPL_COLORS[2], style=pg.QtCore.Qt.SolidLine)
        self.curves['points'].setBrush(color=_MPL_COLORS[2])
        self.curves['points'].setSymbol('o')
        self.curves['points'].setSize(10)

        # Errorbars for points; needs to initialized with x, y args, otherwise cnnot be added to PlotItem
        self.curves['errors'] = pg.ErrorBarItem(x=np.arange(1), y=np.arange(1), beam=0.25)

        # Horizontal line indication the mean fluence over all rows
        self.curves['mean'] = pg.InfiniteLine(angle=0)
        self.curves['mean'].setPen(color=_MPL_COLORS[1], width=2)
        self.p_label = pg.InfLineLabel(self.curves['mean'], position=0.2)
        self.n_label = pg.InfLineLabel(self.curves['mean'], position=0.8)

        # Show data and legend
        for curve in self.curves:
            self.show_data(curve)

    def set_data(self, data):

        # Meta data and data
        _meta, _data = data['meta'], data['data']

        # Set data
        self._data['hist'] = data['data']['fluence_hist']
        self._data['hist_err'] = data['data']['fluence_hist_err']

        # Get stats
        self._data['hist_mean'], self._data['hist_std'] = (f(self._data['hist']) for f in (np.mean, np.std))

        self._data_is_set = True

    def refresh_plot(self):
        """Refresh the plot. This method is supposed to be connected to the timeout-Signal of a QTimer"""
        if self._data_is_set:
            for curve in self.curves:
                if curve == 'hist':
                    try:
                        self.curves[curve].setData(x=self._data['hist_rows'], y=self._data['hist'], stepMode=True)
                        self.curves['mean'].setValue(self._data['hist_mean'])
                        self.p_label.setFormat('Mean: ({:.2E} +- {:.2E}) protons / cm^2'.format(self._data['hist_mean'],
                                                                                                self._data['hist_std']))
                        self.n_label.setFormat('Mean: ({:.2E} +- {:.2E}) neq / cm^2'.format(*[x * self.kappa for x in (self._data['hist_mean'],
                                                                                                                       self._data['hist_std'])]))
                    except Exception as e:
                        logging.warning('Fluence histogram exception: {}'.format(e.message))

                elif curve == 'points':
                    self.curves[curve].setData(x=self._data['hist_rows'][:-1] + 0.5, y=self._data['hist'])
                elif curve == 'errors':
                    self.curves[curve].setData(x=self._data['hist_rows'][:-1] + 0.5, y=self._data['hist'], height=np.array(self._data['hist_err']), pen=_MPL_COLORS[2])


class SEEFracHist(IrradDataHist):

    def __init__(self, name, xlabel, refresh_rate=10, parent=None):

        super().__init__(hist_config=IrradHists().create_hist('see'),
                         xlabel=xlabel,
                         unit='%',
                         name=name,
                         refresh_rate=refresh_rate,
                         parent=parent)


class SEYHist(IrradDataHist):

    def __init__(self, name, xlabel, refresh_rate=10, parent=None):

        super().__init__(hist_config=IrradHists().create_hist('sey'),
                         xlabel=xlabel,
                         unit='%',
                         name=name,
                         refresh_rate=refresh_rate,
                         parent=parent)


class SEECurrentPlot(ScrollingIrradDataPlot):
    """Plot for displaying the proton beam current over time. Data is displayed in rolling manner over period seconds"""

    def __init__(self, channels, name=None, parent=None):

        # Call __init__ of ScrollingIrradDataPlot
        super(SEECurrentPlot, self).__init__(channels=channels,
                                              units={'right': 'A', 'left': 'A'},
                                              name=name or type(self).__name__,
                                              parent=parent)
        
        self.plt.setLabel('left', text='SEE current', units='A')
        self.plt.hideAxis('left')
        self.plt.showAxis('right')
        self.plt.setLabel('right', text='SEE current', units='A')
