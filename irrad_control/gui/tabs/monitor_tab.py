from PyQt5 import QtWidgets
from collections import OrderedDict
from irrad_control.gui.widgets import PlotWrapperWidget, MultiPlotWidget  # Wrapper widgets
from irrad_control.gui.widgets import RawDataPlot, BeamPositionPlot, BeamCurrentPlot, FluenceHist, TemperatureDataPlot, FractionHist  # Actual plots


class IrradMonitorTab(QtWidgets.QWidget):
    """Widget which implements a data monitor"""

    def __init__(self, setup, plot_path=None, parent=None):
        super(IrradMonitorTab, self).__init__(parent)

        self.setup = setup

        self.monitors = ('Raw', 'Beam', 'SEM', 'Fluence', 'Temp')

        self.daq_tabs = QtWidgets.QTabWidget()
        self.monitor_tabs = {}

        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().addWidget(self.daq_tabs)

        self.plot_path = plot_path

        self.plots = OrderedDict()

        self._init_tabs()

    def _init_tabs(self):

        for server in self.setup:

            self.plots[server] = OrderedDict()

            # Tabs per server
            self.monitor_tabs[server] = QtWidgets.QTabWidget()

            for monitor in self.monitors:

                monitor_widget = None

                if 'adc' in self.setup[server]['devices']:

                    if monitor == 'Raw':

                        self.plots[server]['raw_plot'] = RawDataPlot(self.setup[server], daq_device=self.setup[server]['devices']['daq']['sem'])

                        monitor_widget = PlotWrapperWidget(self.plots[server]['raw_plot'], plot_path=self.plot_path)

                    elif monitor == 'Beam':

                        self.plots[server]['current_plot'] = BeamCurrentPlot(daq_device=self.setup[server]['devices']['daq']['sem'])
                        self.plots[server]['pos_plot'] = BeamPositionPlot(self.setup[server], daq_device=self.setup[server]['devices']['daq']['sem'])

                        beam_current_wrapper = PlotWrapperWidget(self.plots[server]['current_plot'],
                                                                 plot_path=self.plot_path)
                        beam_pos_wrapper = PlotWrapperWidget(self.plots[server]['pos_plot'],
                                                             plot_path=self.plot_path)

                        monitor_widget = MultiPlotWidget(plots=[beam_current_wrapper, beam_pos_wrapper])

                    elif monitor == 'SEM':
                        plot_wrappers = []
                        if all(x in self.setup[server]['devices']['adc']['types'] for x in ('sem_right', 'sem_left')):
                            self.plots[server]['sem_h_plot'] = FractionHist(rel_sig='SEM Horizontal', norm_sig='SEM_{}'.format(u'\u03A3'.encode('utf-8')))
                            plot_wrappers.append(PlotWrapperWidget(self.plots[server]['sem_h_plot'],
                                                                   plot_path=self.plot_path))

                        if all(x in self.setup[server]['devices']['adc']['types'] for x in ('sem_up', 'sem_down')):
                            self.plots[server]['sem_v_plot'] = FractionHist(rel_sig='SEM Vertical', norm_sig='SEM_{}'.format(u'\u03A3'.encode('utf-8')))
                            plot_wrappers.append(PlotWrapperWidget(self.plots[server]['sem_v_plot'],
                                                                   plot_path=self.plot_path))

                        if len(plot_wrappers) == 1:
                            monitor_widget = plot_wrappers[0]
                        elif plot_wrappers:
                            monitor_widget = MultiPlotWidget(plots=plot_wrappers)

                if 'temp' in self.setup[server]['devices']:

                    if monitor == 'Temp':
                        daq_device = 'ArduinoTempSens' if 'daq' not in self.setup[server]['devices'] else self.setup[server]['devices']['daq']['sem']
                        self.plots[server]['temp_plot'] = TemperatureDataPlot(self.setup[server], daq_device=daq_device)
                        monitor_widget = PlotWrapperWidget(self.plots[server]['temp_plot'],
                                                           plot_path=self.plot_path)

                if monitor_widget is not None:
                    self.monitor_tabs[server].addTab(monitor_widget, monitor)

            self.daq_tabs.addTab(self.monitor_tabs[server], self.setup[server]['name'])

    def add_fluence_hist(self, n_rows, kappa):

        for server in self.setup:

            self.plots[server]['fluence_plot'] = FluenceHist(irrad_setup={'n_rows': n_rows, 'kappa': kappa})
            monitor_widget = PlotWrapperWidget(self.plots[server]['fluence_plot'])
            self.monitor_tabs[server].addTab(monitor_widget, 'Fluence')
