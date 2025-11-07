from PyQt5 import QtWidgets, QtCore, QtGui
from irrad_control.gui.widgets.util_widgets import GridContainer, NoBackgroundScrollArea


class DaqInfoWidget(QtWidgets.QWidget):
    """
    Widget to display all necessary information about the data acquisition such as the amount of ADCs, their channels
    and the respective raw data and the sampling rate and numbers of internal ADC averages. Also displays the hardware
    configuration of the RO electronics for each ADC such as the 5V full scale and channel type.
    """

    def __init__(self, setup, table_fontsize=(12, 14), parent=None):
        super(DaqInfoWidget, self).__init__(parent)

        # Init class attributes
        self.setup = setup

        # Data related per server
        self.servers = list(self.setup.keys())
        self.channels = {}
        self.ch_types = {}
        self.n_channels = {}
        self.tables = {}

        # Timestamps per ADC
        self.refresh_timestamp = {}
        self.data_timestamp = {}

        # Beam current values
        self._beam_current_vals = {}

        # Check number of DAQ ADCs
        for server in self.servers:
            if 'readout' in self.setup[server]:
                self.channels[server] = self.setup[server]['readout']['channels']
                self.ch_types[server] = self.setup[server]['readout']['types']
                self.n_channels[server] = len(self.channels[server])

        # Info related per ADC
        self.n_digits = dict(zip(self.servers, [3] * len(self.servers)))
        self.refresh_interval = dict(zip(self.servers, [1] * len(self.servers)))
        self.unit = dict(zip(self.servers, ['V'] * len(self.servers)))

        # Data table fonts
        self.table_header_font = QtGui.QFont()
        self.table_header_font.setPointSize(table_fontsize[0])
        self.table_header_font.setBold(True)
        self.table_value_font = QtGui.QFont()
        self.table_value_font.setPointSize(table_fontsize[1])
        self.table_value_font.setBold(True)

        # Spacing
        self.h_space = 100
        self.v_space = 50

        # Style used for icons
        self._style = QtWidgets.qApp.style()

        # Init user interface
        self._init_ui()

    def _init_ui(self):
        """Init the user interface of the widget. Use one tab per ADC"""

        # Main layout of the widget
        self.main_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.main_layout)

        # Main widget
        self.tabs = QtWidgets.QTabWidget()

        # Info labels for all ADCs
        self.data_rate_labels = {}
        self.sampling_rate_labels = {}
        self.num_avg_labels = {}
        self.full_scale_labels = {}
        self.beam_current_labels = {}

        # Buttons for pausing/resuming recording of data
        self.record_btns = {}

        # Loop over all servers and check whether we have an ADC
        for server in self.servers:

            if 'readout' not in self.setup[server]:
                continue

            info_widget = GridContainer(name='Info')

            # Fill info layout with labels and widgets
            # Check info in daq_setup
            _cnfg = self.setup[server]['readout']
            _srate_lbl = '' if 'sampling_rate' not in _cnfg else _cnfg['sampling_rate']

            # Set labels
            self.data_rate_labels[server] = QtWidgets.QLabel('Data rate :' + '\t' + 'Hz ')
            self.sampling_rate_labels[server] = QtWidgets.QLabel('Sampling rate: %s sps' % _srate_lbl)
            self.beam_current_labels[server] = QtWidgets.QLabel('Beam current:' + '\t' + 'nA')

            # Tooltips of labels
            self.data_rate_labels[server].setToolTip('Rate of incoming data of respective ADC')
            self.sampling_rate_labels[server].setToolTip('Samples per second of the ADS1256')

            # Helper widgets to change display of raw data
            # Spinbox to select refresh rate of data
            interval_spinbox = QtWidgets.QDoubleSpinBox()
            interval_spinbox.setPrefix('Refresh every ')
            interval_spinbox.setSuffix(' s')
            interval_spinbox.setDecimals(1)
            interval_spinbox.setRange(0, 10)  # max 10 s
            interval_spinbox.setValue(self.refresh_interval[server])
            interval_spinbox.valueChanged.connect(lambda v, x=server: self.update_interval(x, v))

            # Spinbox to adjust number of digits
            digit_spinbox = QtWidgets.QSpinBox()
            digit_spinbox.setPrefix('Digits: ')
            digit_spinbox.setRange(1, 10)  # max 10 decimals
            digit_spinbox.setValue(self.n_digits[server])
            digit_spinbox.valueChanged.connect(lambda v, x=server: self.update_digits(x, v))

            # Radio buttons in order to set unit in which raw data should be displayed
            unit_label = QtWidgets.QLabel('Unit:')
            volt_rb = QtWidgets.QRadioButton('V')
            volt_rb.setChecked(True)
            ampere_rb = QtWidgets.QRadioButton('nA')
            volt_rb.toggled.connect(lambda v, x=server: self.update_unit(v, x, volt_rb.text()))
            ampere_rb.toggled.connect(lambda v, x=server: self.update_unit(v, x, ampere_rb.text()))

            unit_widget = QtWidgets.QWidget()
            unit_widget.setLayout(QtWidgets.QHBoxLayout())
            unit_widget.layout().addWidget(volt_rb)
            unit_widget.layout().addWidget(ampere_rb)

            # Add to layout
            info_widget.add_widget(widget=[self.data_rate_labels[server], self.beam_current_labels[server], interval_spinbox, digit_spinbox])
            info_widget.add_widget(widget=[self.sampling_rate_labels[server], unit_label, unit_widget])

            # Layout for table area
            table_widget = QtWidgets.QWidget()
            table_layout = QtWidgets.QVBoxLayout()
            table_widget.setLayout(table_layout)

            # Make table for ADC
            self.tables[server] = self._setup_table(server)

            all_tables = GridContainer(name='Raw data')
            for table in self.tables[server]:
                all_tables.add_widget(table)

            self.record_btns[server] = QtWidgets.QPushButton()
            self.record_btns[server].setVisible(False)

            # Add to layout
            table_layout.addWidget(self.record_btns[server])
            table_layout.addWidget(info_widget)
            table_layout.addWidget(all_tables)

            # Make scroll widget and set widget
            scroll_area = NoBackgroundScrollArea()
            scroll_area.setWidget(table_widget)

            self.tabs.addTab(scroll_area, self.setup[server]['name'])
            self.update_rec_state(server=server, state=True)

        self.main_layout.addWidget(self.tabs)

    def update_rec_state(self, server, state=True):

        icon = self._style.SP_DialogYesButton if state else self._style.SP_DialogNoButton
        tooltip = "Recording" if state else "Data recording paused"
        btn_text = "Pause" if state else "Resume"
        self.record_btns[server].setText(btn_text)
        idx = [self.tabs.tabText(i) for i in range(self.tabs.count())].index(self.setup[server]['name'])
        self.tabs.setTabIcon(idx, self._style.standardIcon(icon))
        self.tabs.setTabToolTip(idx, tooltip)

    def _setup_table(self, server):
        """Setup and return table widget(s) in order to display channel data of adc"""
        
        # Check how many tables are needed to display all channels
        total_tables = self._check_n_tables(server)

        # Determine which table has how many columns
        cols_per_table, remnant = divmod(self.n_channels[server], total_tables)
        cols_final = [cpt + 1 if (i + 1) <= remnant else cpt for i, cpt in enumerate([cols_per_table] * total_tables)]

        # Loop over tables and fill list
        tables = []
        for i in range(total_tables):
            table = QtWidgets.QTableWidget()
            table.showGrid()
            table.setRowCount(1)
            table.verticalHeader().setVisible(False)
            table.setColumnCount(cols_final[i])
            current_headers = self.channels[server][sum(cols_final[:i]): sum(cols_final[:i + 1])]
            table.setHorizontalHeaderLabels([h + ' / ' + self.unit[server] for h in current_headers])
            for j in range(table.columnCount()):
                table.horizontalHeaderItem(j).setToolTip('Channel of type %s' % self.ch_types[server][j])
                table.horizontalHeaderItem(j).setFont(self.table_header_font)
                table.setItem(0, j, QtWidgets.QTableWidgetItem(format(0, '.{}f'.format(self.n_digits[server]))))
                table.item(0, j).setTextAlignment(QtCore.Qt.AlignCenter)
                table.item(0, j).setFlags(QtCore.Qt.ItemIsEnabled)
                table.item(0, j).setFont(self.table_value_font)
                table.resizeColumnToContents(j)

            # Set minimum widths and stretch policies
            table.setMinimumWidth(sum([table.columnWidth(k) for k in range(table.columnCount())]))
            table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
            table.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)

            tables.append(table)

        return tables

    def _check_n_tables(self, server):

        # make as many tables as necessary in order to display the data
        enough_tables = False
        total_cols = 0
        total_tables = 0

        # check how many tables are needed to display raw data
        while not enough_tables:
            table = QtWidgets.QTableWidget()
            table.setRowCount(1)
            n_cols = 1
            while n_cols <= (self.n_channels[server] - total_cols):
                table.setColumnCount(n_cols)
                current_headers = [h + ' / ' + self.unit[server] for h in self.channels[server][total_cols: total_cols + n_cols]]
                table.setHorizontalHeaderLabels(current_headers)
                for j in range(table.columnCount()):
                    table.setItem(0, j, QtWidgets.QTableWidgetItem(format(0, '.{}f'.format(self.n_digits[server]))))
                    table.resizeColumnToContents(j)

                if sum([table.columnWidth(i) for i in range(table.columnCount() + 1)]) > self.width():
                    break

                n_cols += 1

            total_tables += 1
            total_cols += n_cols

            if total_cols >= self.n_channels[server]:
                enough_tables = True

        return total_tables

    def update_raw_data(self, data):
        """Function handling incoming data and updating table widgets"""

        # Extract meta data and actual data
        meta_data, channel_data = data['meta'], data['data']

        # Name of ADC; first raw data will not have data rate
        server, drate = meta_data['name'], 0 if 'data_rate' not in meta_data else meta_data['data_rate']

        # First incoming data sets is displayed and sets timestamp
        if server not in self.refresh_timestamp:
            self.refresh_timestamp[server] = self.refresh_interval[server]

        # Timestamp, data rate and update
        timestamp = meta_data['timestamp']
        refresh_time = timestamp - self.refresh_timestamp[server]

        # Only update widgets if it's time to refresh; if interval is 0, update all the time
        if refresh_time >= self.refresh_interval[server] or self.refresh_interval[server] == 0:
            self.update_drate(server=server, drate=drate)
            self.update_table(server=server, ch_data=channel_data)

            # Update latest value of beam current
            if server in self._beam_current_vals:
                self.beam_current_labels[server].setText('Beam current: ({:.2f} {} {:.2f}) nA'.format(self._beam_current_vals[server][0],
                                                                                                      u'\u00B1',
                                                                                                      self._beam_current_vals[server][1]))

            # Update refresh timestamp
            self.refresh_timestamp[server] = timestamp

    def update_table(self, server, ch_data=None):
        """Method updating table data per ADC"""

        # Loop over tables of adc
        for table in self.tables[server]:
            # Loop over column index
            for i in range(table.columnCount()):
                # Get current column header text and strip data unit
                data_header = table.horizontalHeaderItem(i).text().split(' ')[0]
                # If channel data is none only update number of digits or unit
                if ch_data is None:
                    table.horizontalHeaderItem(i).setText(data_header + ' / ' + self.unit[server])
                    table.item(0, i).setText(format(float(table.item(0, i).text()), '.{}f'.format(self.n_digits[server])))
                # Update table entries with new data
                else:
                    measure = 'voltage' if self.unit[server] == 'V' else 'current'
                    scale = 1 if measure == 'voltage' else 1e9  # nA
                    val = 'NaN' if data_header not in ch_data[measure] else format(scale * ch_data[measure][data_header], '.{}f'.format(self.n_digits[server]))
                    table.item(0, i).setText(val)

    def _update_tables(self, ch_data=None):
        """Helper func to update all tables at once"""
        for server in self.servers:
            self.update_table(server, ch_data=ch_data)

    def update_beam_current(self, beam_data):
        server, actual_data = beam_data['meta']['name'], beam_data['data']
        self._beam_current_vals[server] = (actual_data['current']['beam_current'] * 1e9,
                                           actual_data['current']['beam_current_error'] * 1e9)

    def update_digits(self, server, digits):
        """Update the digits to display in table data"""
        self.n_digits[server] = digits
        self._update_tables()

    def update_interval(self, server, interval):
        """Update the data rate label"""
        self.refresh_interval[server] = interval

    def update_unit(self, v, server, unit):
        self.unit[server] = unit if v else self.unit[server]
        self._update_tables()

    def update_drate(self, server, drate):
        """Update the data rate label"""
        self.data_rate_labels[server].setText('Data rate: {} Hz'.format(format(drate, '.2f')))

    def update_srate(self, server, srate):
        """Update the sampling rate label"""
        self.sampling_rate_labels[server].setText('Sampling rate: {} sps'.format(srate))
