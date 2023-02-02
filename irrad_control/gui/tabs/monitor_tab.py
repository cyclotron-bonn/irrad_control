from PyQt6 import QtWidgets
from collections import defaultdict

# Package imports
from irrad_control.gui.widgets import plot_widgets as plots  # Actual plots



class IrradMonitorTab(QtWidgets.QWidget):
    """Widget which implements a data monitor"""

    def __init__(self, setup, plot_path=None, parent=None):
        super(IrradMonitorTab, self).__init__(parent)

        self.setup = setup

        self.monitors = ('Raw', 'Beam', 'SEM', 'Fluence', 'Temp', 'DoseRate')

        self.daq_tabs = QtWidgets.QTabWidget()
        self.monitor_tabs = {}

        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().addWidget(self.daq_tabs)

        self.plot_path = plot_path

        self.plots = defaultdict(dict)
        self._plot_wrapper_widgets = defaultdict(dict)

        for server in self.setup:
            self._init_tab(server=server)
            self.enable_monitor(server=server, enable=False)

    def _init_tab(self, server):

        # Tabs per server
        self.monitor_tabs[server] = QtWidgets.QTabWidget()

        for monitor in self.monitors:

            monitor_widget = None

            # Dedicated flag for NTC readout of DAQ Board
            has_ntc_daq_board_ro = False

            if 'readout' in self.setup[server]:

                if 'ntc' in self.setup[server]['readout']:
                    has_ntc_daq_board_ro = True

                if monitor == 'Raw':

                    channels = self.setup[server]['readout']['channels']
                    self.plots[server]['raw_plot'] = plots.RawDataPlot(channels=channels)
                    monitor_widget = self._create_plot_wrapper(plot_name='raw_plot', server=server)

                elif monitor == 'Beam':

                    channels = ('beam_current', 'beam_current_error', 'reconstructed_beam_current')
                    if 'blm' in self.setup[server]['readout']['types']:
                        channels += ('beam_loss', )

                    self.plots[server]['current_plot'] = plots.BeamCurrentPlot(channels=channels, ion=self.setup[server]['daq']['ion'])
                    self.plots[server]['pos_plot'] = plots.BeamPositionPlot(self.setup[server])

                    beam_current_wrapper = self._create_plot_wrapper(plot_name='current_plot', server=server)
                    beam_pos_wrapper = self._create_plot_wrapper(plot_name='pos_plot', server=server)

                    monitor_widget = plots.MultiPlotWidget(plots=[beam_current_wrapper, beam_pos_wrapper])

                elif monitor == 'SEM':
                    plot_wrappers = []
                    if all(x in self.setup[server]['readout']['types'] for x in ('sem_right', 'sem_left')):
                        self.plots[server]['sem_h_plot'] = plots.SEYFractionHist(rel_sig='sey_horizontal', norm_sig='SEM_{}'.format(u'\u03A3'))
                        plot_wrappers.append(self._create_plot_wrapper(plot_name='sem_h_plot', server=server))

                    if all(x in self.setup[server]['readout']['types'] for x in ('sem_up', 'sem_down')):
                        self.plots[server]['sem_v_plot'] = plots.SEYFractionHist(rel_sig='sey_vertical', norm_sig='SEM_{}'.format(u'\u03A3'))
                        plot_wrappers.append(self._create_plot_wrapper(plot_name='sem_v_plot', server=server))
                    if len(plot_wrappers) == 1:
                        monitor_widget = plot_wrappers[0]
                    elif plot_wrappers:
                        monitor_widget = plots.MultiPlotWidget(plots=plot_wrappers)

            if has_ntc_daq_board_ro or 'ArduinoNTCReadout' in self.setup[server]['devices']:

                if monitor == 'Temp':
                    plot_wrappers = []

                    if has_ntc_daq_board_ro:
                        channels = list(self.setup[server]['readout']['ntc'].values())
                        self.plots[server]['temp_daq_board_plot'] = plots.TemperatureDataPlot(channels=channels, daq_device='DAQBoard')
                        plot_wrappers.append(self._create_plot_wrapper(plot_name='temp_daq_board_plot', server=server))

                    if 'ArduinoNTCReadout' in self.setup[server]['devices']:
                        channels = list(self.setup[server]['devices']['ArduinoNTCReadout']['setup'].values())
                        self.plots[server]['temp_arduino_plot'] = plots.TemperatureDataPlot(channels=channels, daq_device='ArduinoNTCReadout')
                        plot_wrappers.append(self._create_plot_wrapper(plot_name='temp_arduino_plot', server=server))

                    if len(plot_wrappers) == 1:
                        monitor_widget = plot_wrappers[0]
                    elif plot_wrappers:
                        monitor_widget = plots.MultiPlotWidget(plots=plot_wrappers)

            if 'RadiationMonitor' in self.setup[server]['devices'] and monitor == 'DoseRate':
                
                channels = ('rad_monitor',)
                daq_device = self.setup[server]['devices']['RadiationMonitor']['init']['counter_type']
                self.plots[server]['dose_rate_plot'] = plots.RadMonitorDataPlot(channels=channels, daq_device=daq_device)
                monitor_widget = self._create_plot_wrapper(plot_name='dose_rate_plot', server=server)

            if monitor_widget is not None:
                self.monitor_tabs[server].addTab(monitor_widget, monitor)

        self.daq_tabs.addTab(self.monitor_tabs[server], self.setup[server]['name'])

    def enable_monitor(self, server, enable=True):
        for i in range(self.daq_tabs.count()):
            if self.daq_tabs.tabText(i) == self.setup[server]['name']:
                self.daq_tabs.widget(i).setEnabled(enable)

    def _create_plot_wrapper(self, plot_name, server):

        file_name = f"{type(self.plots[server][plot_name]).__name__}_{self.setup[server]['name']}"
        
        self._plot_wrapper_widgets[server][plot_name] = plots.PlotWrapperWidget(plot=self.plots[server][plot_name],
                                                                                plot_path=self.plot_path,
                                                                                file_name=file_name)

        return self._plot_wrapper_widgets[server][plot_name]


    def add_fluence_hist(self, server, n_rows, kappa):
        self.plots[server]['fluence_plot'] = plots.FluenceHist(n_rows=n_rows, kappa=kappa)
        monitor_widget = self._create_plot_wrapper(plot_name='fluence_plot', server=server)
        self.monitor_tabs[server].addTab(monitor_widget, 'Fluence')

    def save_plots(self):
        for _, plot_wrappers in self._plot_wrapper_widgets.items():
            for _, wrapper in plot_wrappers.items():
                wrapper.save_plot()
