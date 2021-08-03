from PyQt5 import QtWidgets
from collections import OrderedDict

# Package imports
from irrad_control.gui.widgets import plot_widgets as plots  # Actual plots


class IrradMonitorTab(QtWidgets.QWidget):
    """Widget which implements a data monitor"""

    def __init__(self, setup, parent=None):
        super(IrradMonitorTab, self).__init__(parent)

        self.setup = setup

        self.monitors = ('Raw', 'Beam', 'SEM', 'Fluence', 'Temp')

        self.daq_tabs = QtWidgets.QTabWidget()
        self.monitor_tabs = {}

        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().addWidget(self.daq_tabs)

        self.plots = OrderedDict()

        self._init_tabs()

    def _init_tabs(self):

        for server in self.setup:

            self.plots[server] = OrderedDict()

            # Tabs per server
            self.monitor_tabs[server] = QtWidgets.QTabWidget()

            for monitor in self.monitors:

                monitor_widget = None

                if 'readout' in self.setup[server]:

                    if monitor == 'Raw':

                        channels = self.setup[server]['readout']['channels']
                        daq_device = self.setup[server]['daq']['sem']
                        self.plots[server]['raw_plot'] = plots.RawDataPlot(channels=channels,
                                                                           daq_device=daq_device)
                        monitor_widget = plots.PlotWrapperWidget(self.plots[server]['raw_plot'])

                    elif monitor == 'Beam':

                        channels = ('beam_current', 'beam_current_error', 'reconstructed_beam_current')
                        daq_device = self.setup[server]['daq']['sem']
                        if 'blm' in self.setup[server]['readout']['types']:
                            channels += ('beam_loss', )
                        self.plots[server]['current_plot'] = plots.BeamCurrentPlot(channels=channels,
                                                                                   daq_device=daq_device)

                        self.plots[server]['pos_plot'] = plots.BeamPositionPlot(self.setup[server], daq_device=daq_device)

                        beam_current_wrapper = plots.PlotWrapperWidget(self.plots[server]['current_plot'])
                        beam_pos_wrapper = plots.PlotWrapperWidget(self.plots[server]['pos_plot'])

                        monitor_widget = plots.MultiPlotWidget(plots=[beam_current_wrapper, beam_pos_wrapper])

                    elif monitor == 'SEM':
                        plot_wrappers = []
                        if all(x in self.setup[server]['readout']['types'] for x in ('sem_right', 'sem_left')):
                            self.plots[server]['sem_h_plot'] = plots.SEYFractionHist(rel_sig='sey_horizontal', norm_sig='SEM_{}'.format(u'\u03A3'))
                            plot_wrappers.append(plots.PlotWrapperWidget(self.plots[server]['sem_h_plot']))

                        if all(x in self.setup[server]['readout']['types'] for x in ('sem_up', 'sem_down')):
                            self.plots[server]['sem_v_plot'] = plots.SEYFractionHist(rel_sig='sey_vertical', norm_sig='SEM_{}'.format(u'\u03A3'))
                            plot_wrappers.append(plots.PlotWrapperWidget(self.plots[server]['sem_v_plot']))

                        if len(plot_wrappers) == 1:
                            monitor_widget = plot_wrappers[0]
                        elif plot_wrappers:
                            monitor_widget = plots.MultiPlotWidget(plots=plot_wrappers)

                if 'ntc' in self.setup[server]['readout'] or 'ArduinoTempSens' in self.setup[server]['devices']:

                    if monitor == 'Temp':
                        plot_wrappers = []

                        if 'ntc' in self.setup[server]['readout']:
                            channels = list(self.setup[server]['readout']['ntc'].values())
                            self.plots[server]['temp_daq_board_plot'] = plots.TemperatureDataPlot(channels=channels,
                                                                                                  daq_device='DAQBoard')
                            plot_wrappers.append(plots.PlotWrapperWidget(self.plots[server]['temp_daq_board_plot']))

                        if 'ArduinoTempSens' in self.setup[server]['devices']:
                            channels = list(self.setup[server]['devices']['ArduinoTempSens']['setup'].values())
                            self.plots[server]['temp_arduino_plot'] = plots.TemperatureDataPlot(channels=channels,
                                                                                                daq_device='ArduinoTempSens')
                            plot_wrappers.append(plots.PlotWrapperWidget(self.plots[server]['temp_arduino_plot']))

                        if len(plot_wrappers) == 1:
                            monitor_widget = plot_wrappers[0]
                        elif plot_wrappers:
                            monitor_widget = plots.MultiPlotWidget(plots=plot_wrappers)

                if monitor_widget is not None:
                    self.monitor_tabs[server].addTab(monitor_widget, monitor)

            self.daq_tabs.addTab(self.monitor_tabs[server], self.setup[server]['name'])

    def add_fluence_hist(self, n_rows, kappa):

        for server in self.setup:

            self.plots[server]['fluence_plot'] = plots.FluenceHist(n_rows=n_rows, kappa=kappa)
            monitor_widget = plots.PlotWrapperWidget(self.plots[server]['fluence_plot'])
            self.monitor_tabs[server].addTab(monitor_widget, 'Fluence')
