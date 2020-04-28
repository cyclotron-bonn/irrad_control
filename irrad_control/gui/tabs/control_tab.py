import time
from PyQt5 import QtWidgets, QtCore
from collections import OrderedDict
from copy import deepcopy
from irrad_control.gui.widgets import GridContainer, XYStagePositionWindow
from irrad_control import xy_stage_config
from .setup_tab import _fill_combobox_items


class IrradControlTab(QtWidgets.QWidget):
    """Control widget for the irradiation control software"""

    sendCmd = QtCore.pyqtSignal(dict)
    stageInfo = QtCore.pyqtSignal(dict)
    enableDAQRec = QtCore.pyqtSignal(str, bool)

    def __init__(self, setup, parent=None):
        super(IrradControlTab, self).__init__(parent)

        # Setup related
        self.setup = setup  # Store setup of server(s)
        self.stage_server = [server for server in setup if 'stage' in setup[server]['devices']]

        # Check
        if len(self.stage_server) == 1:
            self.stage_server = self.stage_server[0]
        else:
            if self.stage_server:
                raise IndexError("Only one server can control a XY-Stage. Currently {} servers have a XY-stage in their setup.".format(len(self.stage_server)))
            else:
                self.stage_server = None

        # Attributes for the stage
        self.current_pos = [0.0, 0.0]
        self.current_speed = [0.0, 0.0]
        self.aim_fluence = None
        self.beam_current = None
        self.min_scan_current = None
        self.scan_params = OrderedDict()
        self.beam_down = False
        self.beam_down_timer = None
        self.info_labels = {}
        self._scan_param_units = {}
        self._xy_stage_config = deepcopy(xy_stage_config)
        self.xy_stage_position_win = XYStagePositionWindow(self._xy_stage_config)
        self.xy_stage_position_win.stagePosChanged.connect(lambda config: self._xy_stage_config.update(config))

        # Layouts; split in quadrants
        self.main_layout = QtWidgets.QHBoxLayout()

        # Make quadrants
        self.info_widget = GridContainer('Info')
        self.control_widget = GridContainer('Setup control')
        self.scan_widget = GridContainer('Scan')
        self.daq_widget = GridContainer('Data acquisition')

        # Splitters
        self.main_splitter = QtWidgets.QSplitter()
        self.main_splitter.setOrientation(QtCore.Qt.Vertical)
        self.main_splitter.setChildrenCollapsible(False)
        self.sub_splitter_1 = QtWidgets.QSplitter()
        self.sub_splitter_1.setOrientation(QtCore.Qt.Horizontal)
        self.sub_splitter_1.setChildrenCollapsible(False)
        self.sub_splitter_1.addWidget(self.control_widget)
        self.sub_splitter_1.addWidget(self.scan_widget)
        self.sub_splitter_2 = QtWidgets.QSplitter()
        self.sub_splitter_2.setOrientation(QtCore.Qt.Horizontal)
        self.sub_splitter_2.setChildrenCollapsible(False)
        self.sub_splitter_2.addWidget(self.daq_widget)
        self.sub_splitter_2.addWidget(self.info_widget)
        self.main_splitter.addWidget(self.sub_splitter_1)
        self.main_splitter.addWidget(self.sub_splitter_2)

        # Add splitters to main layout
        self.main_layout.addWidget(self.main_splitter)

        # Add main layout to widget layout and define style for icons
        self.setLayout(self.main_layout)
        self._style = QtWidgets.qApp.style()

        # Appearance
        self.show()
        self.sub_splitter_1.setSizes([self.width(), self.width()])
        self.sub_splitter_2.setSizes([self.width(), self.width()])
        self.main_splitter.setSizes([self.height(), self.height()])

        # Setup the widgets for each quadrant
        self._setup_info()
        self._setup_control()
        self._setup_scan()
        self._setup_daq()

        #self.control_widget.setVisible(self.stage_server is not None)
        #self.scan_widget.setVisible(self.stage_server is not None)
        #self.info_widget.setVisible(self.stage_server is not None)

    def _setup_control(self):

        # Button to home the device
        label_home = QtWidgets.QLabel('Home stage:')
        btn_home = QtWidgets.QPushButton('Home axes')
        btn_home.setToolTip("Moves XY-Stage to home position as defined by the lower limit of the range in each direction")
        btn_home.clicked.connect(lambda _: self.send_cmd(target='stage', cmd='home'))

        # Stage range
        label_range = QtWidgets.QLabel('Set range:')
        spx_low_range = QtWidgets.QDoubleSpinBox()
        spx_low_range.setPrefix('Low: ')
        spx_low_range.setDecimals(3)
        spx_low_range.setMinimum(0.0)
        spx_low_range.setMaximum(299.999)
        spx_low_range.setValue(0)
        spx_low_range.setSuffix(' mm')
        spx_high_range = QtWidgets.QDoubleSpinBox()
        spx_high_range.setPrefix('High: ')
        spx_high_range.setDecimals(3)
        spx_high_range.setMinimum(0.001)
        spx_high_range.setMaximum(300.0)
        spx_high_range.setValue(300.0)
        spx_high_range.setSuffix(' mm')
        spx_low_range.valueChanged.connect(lambda v, s=spx_high_range: s.setValue(s.value() if v < s.value() else v + 1.0))
        spx_high_range.valueChanged.connect(lambda v, s=spx_low_range: s.setValue(s.value() if v > s.value() else v - 1.0))
        range_layout = QtWidgets.QHBoxLayout()
        range_layout.addWidget(spx_low_range)
        range_layout.addSpacing(10)
        range_layout.addWidget(spx_high_range)
        cbx_range = QtWidgets.QComboBox()
        cbx_range.addItems(['x', 'y'])
        stage_ranges = {'x': [spx_low_range.minimum(), spx_high_range.maximum()], 'y': [spx_low_range.minimum(), spx_high_range.maximum()]}
        btn_set_range = QtWidgets.QPushButton('Set {} range'.format(cbx_range.currentText()))

        # Make connections
        for x in [lambda t, b=btn_set_range: b.setText('Set {} range'.format(t)),
                  lambda t: [_spx.setValue(stage_ranges[t][_i]) for _i, _spx in enumerate([spx_low_range, spx_high_range])],
                  lambda t: spx_abs.setRange(*stage_ranges[t]) if t == cbx_axis_abs.currentText() else spx_abs.value(),
                  lambda t: spx_abs.setValue(stage_ranges[t][0]) if t == cbx_axis_abs.currentText() else spx_abs.value()]:
            cbx_range.currentTextChanged.connect(x)
        for xx in [lambda _: stage_ranges.update({cbx_range.currentText(): [spx_low_range.value(), spx_high_range.value()]}),
                   lambda _, t=cbx_range.currentText(): spx_abs.setRange(*stage_ranges[t]) if t == cbx_axis_abs.currentText() else spx_abs.value(),
                   lambda _, t=cbx_range.currentText(): spx_abs.setValue(stage_ranges[t][0]) if t == cbx_axis_abs.currentText() else spx_abs.value()]:
            btn_set_range.clicked.connect(xx)

        btn_set_range.clicked.connect(lambda _: self.send_cmd(target='stage',
                                                              cmd='set_range',
                                                              cmd_data={'axis': cbx_range.currentText(),
                                                                        'range': (spx_low_range.value(), spx_high_range.value()),
                                                                        'unit': 'mm'}))

        # Movement speed
        label_speed = QtWidgets.QLabel('Set speed:')
        spx_speed = QtWidgets.QDoubleSpinBox()
        spx_speed.setMinimum(0.000303)
        spx_speed.setMaximum(205.)
        spx_speed.setDecimals(3)
        spx_speed.setSuffix(' mm/s')
        cbx_axis = QtWidgets.QComboBox()
        cbx_axis.addItems(['x', 'y'])
        btn_set_speed = QtWidgets.QPushButton('Set {} speed'.format(cbx_axis.currentText()))
        cbx_axis.currentTextChanged.connect(lambda t, b=btn_set_speed: b.setText('Set {} speed'.format(t)))
        btn_set_speed.clicked.connect(lambda _: self.send_cmd(target='stage',
                                                              cmd='set_speed',
                                                              cmd_data={'axis': cbx_axis.currentText(),
                                                                        'speed': spx_speed.value(),
                                                                        'unit': 'mm/s'}))

        # Relative movements
        label_rel = QtWidgets.QLabel('Move relative:')
        spx_rel = QtWidgets.QDoubleSpinBox()
        spx_rel.setDecimals(3)
        spx_rel.setMinimum(-300.0)
        spx_rel.setMaximum(300.0)
        spx_rel.setSuffix(' mm')
        cbx_axis_rel = QtWidgets.QComboBox()
        cbx_axis_rel.addItems(['x', 'y'])
        btn_rel = QtWidgets.QPushButton('Move {} rel.'.format(cbx_axis_rel.currentText()))
        cbx_axis_rel.currentTextChanged.connect(lambda t, b=btn_rel: b.setText('Move {} rel.'.format(t)))
        btn_rel.clicked.connect(lambda _: self.send_cmd(target='stage',
                                                        cmd='move_rel',
                                                        cmd_data={'axis': cbx_axis_rel.currentText(),
                                                                  'distance': spx_rel.value(),
                                                                  'unit': 'mm'}))

        # Absolute movements
        label_abs = QtWidgets.QLabel('Move absolute:')
        spx_abs = QtWidgets.QDoubleSpinBox()
        spx_abs.setDecimals(3)
        spx_abs.setMinimum(0.0)
        spx_abs.setMaximum(300.0)
        spx_abs.setSuffix(' mm')
        cbx_axis_abs = QtWidgets.QComboBox()
        cbx_axis_abs.addItems(['x', 'y'])
        btn_abs = QtWidgets.QPushButton('Move {} abs.'.format(cbx_axis_abs.currentText()))
        cbx_axis_abs.currentTextChanged.connect(lambda t, b=btn_abs: b.setText('Move {} abs.'.format(t)))
        cbx_axis_abs.currentTextChanged.connect(lambda t: spx_abs.setRange(*stage_ranges[t]))
        cbx_axis_abs.currentTextChanged.connect(lambda t: spx_abs.setValue(stage_ranges[t][0]))
        btn_abs.clicked.connect(lambda _: self.send_cmd(target='stage',
                                                        cmd='move_abs',
                                                        cmd_data={'axis': cbx_axis_abs.currentText(),
                                                                  'distance': spx_abs.value(),
                                                                  'unit': 'mm'}))

        # Go to predefined positions
        label_positions = QtWidgets.QLabel('Predefined positions:')
        label_positions.setToolTip('Move to or add/edit named stage positions')
        self.cbx_position = QtWidgets.QComboBox()
        self.xy_stage_position_win.stagePosChanged.connect(lambda _: _fill_combobox_items(self.cbx_position, self._xy_stage_config['positions']))
        btn_mv_to_pos = QtWidgets.QPushButton()
        btn_edit_positions = QtWidgets.QPushButton('Edit positions')

        # Connect
        self.cbx_position.currentTextChanged.connect(lambda t, b=btn_mv_to_pos: b.setText("Move to {}".format(t)))
        btn_edit_positions.clicked.connect(self.xy_stage_position_win.show)

        if 'positions' in self._xy_stage_config:
            _fill_combobox_items(self.cbx_position, self._xy_stage_config['positions'])

        # Move to position by moving x and then y
        for i, axis in enumerate(['x', 'y']):
            btn_mv_to_pos.clicked.connect(lambda _, pos=self.cbx_position.currentText():
                                          self.send_cmd(target='stage',
                                                        cmd='move_abs',
                                                        cmd_data={'axis': axis,
                                                                  'distance': self._xy_stage_config['positions']['all'][pos][axis],
                                                                  'unit': self._xy_stage_config['positions']['all'][pos]['unit']}))

        # Add to layout
        self.control_widget.add_widget(widget=[label_home, btn_home])
        self.control_widget.add_widget(widget=[label_range, range_layout, cbx_range, btn_set_range])
        self.control_widget.add_widget(widget=[label_speed, spx_speed, cbx_axis, btn_set_speed])
        self.control_widget.add_widget(widget=[label_rel, spx_rel, cbx_axis_rel, btn_rel])
        self.control_widget.add_widget(widget=[label_abs, spx_abs, cbx_axis_abs, btn_abs])
        self.control_widget.add_widget(widget=[label_positions, self.cbx_position, btn_edit_positions, btn_mv_to_pos])

        # Add spacer layout
        spacer = QtWidgets.QVBoxLayout()
        spacer.addStretch()
        self.control_widget.add_layout(spacer)

    def _setup_scan(self):

        # Step size
        label_step_size = QtWidgets.QLabel('Step size:')
        spx_step_size = QtWidgets.QDoubleSpinBox()
        spx_step_size.setMinimum(0.01)
        spx_step_size.setMaximum(10.0)
        spx_step_size.setDecimals(3)
        spx_step_size.setSuffix(" mm")
        spx_step_size.valueChanged.connect(lambda v, spx=spx_step_size: self.update_scan_parameters(step_size=v, unit=spx.suffix()))
        spx_step_size.setValue(1.0)

        # Scan speed
        label_scan_speed = QtWidgets.QLabel('Scan speed:')
        spx_scan_speed = QtWidgets.QDoubleSpinBox()
        spx_scan_speed.setMinimum(10.)
        spx_scan_speed.setMaximum(200.)
        spx_scan_speed.setDecimals(3)
        spx_scan_speed.setSuffix(' mm/s')
        spx_scan_speed.valueChanged.connect(lambda v, spx=spx_scan_speed: self.update_scan_parameters(scan_speed=v, unit=spx.suffix()))
        spx_scan_speed.setValue(80.0)

        # Beam current
        label_min_current = QtWidgets.QLabel('Minimum scan current:')
        label_min_current.setToolTip("")
        spx_min_current = QtWidgets.QSpinBox()
        spx_min_current.setRange(0, 1000)
        spx_min_current.setSingleStep(50)
        spx_min_current.setSuffix(' nA')
        spx_min_current.setValue(0)
        spx_min_current.valueChanged.connect(lambda v: self.set_min_current(v))

        # Fluence
        label_aim_fluence = QtWidgets.QLabel('Aim fluence:')
        spx_fluence_val = QtWidgets.QDoubleSpinBox()
        spx_fluence_val.setRange(1e-3, 10)
        spx_fluence_val.setDecimals(3)
        spx_fluence_exp = QtWidgets.QSpinBox()
        spx_fluence_exp.setPrefix('e ')
        spx_fluence_exp.setSuffix(' p / cm^2')
        spx_fluence_exp.setRange(10, 20)
        spx_fluence_val.valueChanged.connect(lambda v, e=spx_fluence_exp: self.set_aim_fluence(v, e.value()))
        spx_fluence_exp.valueChanged.connect(lambda e, v=spx_fluence_val: self.set_aim_fluence(v.value(), e))
        spx_fluence_val.setValue(1)
        spx_fluence_exp.setValue(13)

        # Start point
        label_start = QtWidgets.QLabel('Relative start point:')
        spx_start_x = QtWidgets.QDoubleSpinBox()
        spx_start_x.setRange(-300.,  300.)
        spx_start_x.setDecimals(3)
        spx_start_x.setPrefix('x: ')
        spx_start_x.setSuffix(' mm')
        spx_start_y = QtWidgets.QDoubleSpinBox()
        spx_start_y.setRange(-300., 300.)
        spx_start_y.setDecimals(3)
        spx_start_y.setPrefix('y: ')
        spx_start_y.setSuffix(" mm")
        spx_start_x.valueChanged.connect(lambda v, spx=spx_start_x: self.update_scan_parameters(rel_start_point=(v, spx_start_y.value()), unit=spx.suffix()))
        spx_start_y.valueChanged.connect(lambda v, spx=spx_start_y: self.update_scan_parameters(rel_start_point=(spx_start_x.value(), v), unit=spx.suffix()))
        spx_start_x.valueChanged.emit(0.0)

        # End point
        label_end = QtWidgets.QLabel('Relative end point')
        spx_end_x = QtWidgets.QDoubleSpinBox()
        spx_end_x.setRange(-300., 300.)
        spx_end_x.setDecimals(3)
        spx_end_x.setPrefix('x: ')
        spx_end_x.setSuffix(' mm')
        spx_end_y = QtWidgets.QDoubleSpinBox()
        spx_end_y.setRange(-300., 300.)
        spx_end_y.setDecimals(3)
        spx_end_y.setPrefix('y: ')
        spx_end_y.setSuffix(' mm')
        spx_end_x.valueChanged.connect(lambda v, spx=spx_end_x: self.update_scan_parameters(rel_end_point=(v, spx_end_y.value()), unit=spx.suffix()))
        spx_end_y.valueChanged.connect(lambda v, spx=spx_end_y: self.update_scan_parameters(rel_end_point=(spx_end_x.value(), v), unit=spx.suffix()))
        spx_end_x.valueChanged.emit(0.0)

        self.btn_start = QtWidgets.QPushButton('START')
        self.btn_start.setToolTip("Start scan.")
        self.btn_start.clicked.connect(lambda _: self.send_cmd(target='stage', cmd='prepare', cmd_data=self.scan_params))

        self.btn_finish = QtWidgets.QPushButton('FINISH')
        self.btn_finish.setToolTip("Finish the scan. Allow remaining rows of current scan to be scanned before finishing.")
        self.btn_finish.clicked.connect(lambda _: self.send_cmd(target='stage', cmd='finish'))

        # Stop button
        self.btn_stop = QtWidgets.QPushButton('STOP')
        self.btn_stop.setToolTip("Immediately cancel scan and return to origin from where scan started.")
        self.btn_stop.clicked.connect(lambda _: self.send_cmd(target='stage', cmd='stop'))

        self.btn_start.setStyleSheet('QPushButton {color: green;}')
        self.btn_finish.setStyleSheet('QPushButton {color: orange;}')
        self.btn_stop.setStyleSheet('QPushButton {color: red;}')

        # Add to layout
        self.scan_widget.add_widget(widget=[label_step_size, spx_step_size])
        self.scan_widget.add_widget(widget=[label_scan_speed, spx_scan_speed])
        self.scan_widget.add_widget(widget=[label_min_current, spx_min_current])
        self.scan_widget.add_widget(widget=[label_aim_fluence, spx_fluence_val, spx_fluence_exp])
        self.scan_widget.add_widget(widget=[label_start, spx_start_x, spx_start_y])
        self.scan_widget.add_widget(widget=[label_end, spx_end_x, spx_end_y])
        self.scan_widget.add_widget(widget=[self.btn_start, self.btn_finish, self.btn_stop])

        # Add spacer layout
        spacer = QtWidgets.QVBoxLayout()
        spacer.addStretch()
        self.scan_widget.add_layout(spacer)

    def _setup_daq(self):

        # DAQ control for servers from respective tabs
        tab_widget = QtWidgets.QTabWidget()
        record_btns = {}

        self.daq_widget.widgets['tabs'] = tab_widget
        self.daq_widget.widgets['rec_btns'] = record_btns

        # Loop over servers and create widgets
        for server in self.setup:

            # Grid for server
            grid = GridContainer(name='')

            label_offset = QtWidgets.QLabel('Raw data offset:')
            btn_offset = QtWidgets.QPushButton('Compensate offset')
            btn_offset.clicked.connect(lambda _, _server=server: self.send_cmd(target='interpreter',
                                                                               cmd='zero_offset',
                                                                               cmd_data=_server))

            # Button for auto zero offset
            label_record = QtWidgets.QLabel("Data recording:")
            btn_record = QtWidgets.QPushButton('Pause')
            btn_record.clicked.connect(lambda _, _server=server: self.send_cmd(target='interpreter', cmd='record_data', cmd_data=_server))
            record_btns[server] = btn_record

            chbx_record = QtWidgets.QCheckBox('Enable toggling recording state in DAQ dock')
            chbx_record.stateChanged.connect(lambda state, _server=server: self.enableDAQRec.emit(_server, bool(state)))

            # Add spacer layout
            spacer = QtWidgets.QVBoxLayout()
            spacer.addStretch()

            grid.add_widget(widget=[label_offset, btn_offset])
            grid.add_widget(widget=[label_record, btn_record])
            grid.add_widget(widget=[QtWidgets.QLabel(''), chbx_record])
            grid.add_layout(spacer)

            tab_widget.addTab(grid, self.setup[server]['name'])
            self.update_rec_state(server=server, state=True)

        self.daq_widget.add_widget(widget=tab_widget)

    def _setup_info(self):

        # Info for setup
        setup_info = GridContainer('Setup')

        # Info on position
        label_position_info = QtWidgets.QLabel('Position:')

        # Info on position
        label_speed_info = QtWidgets.QLabel('Speed:')

        # Info on travel range
        label_range_info = QtWidgets.QLabel('Travel ranges:')

        # Add to layout
        setup_info.add_widget(widget=label_position_info)
        setup_info.add_widget(widget=label_speed_info)
        setup_info.add_widget(widget=label_range_info)

        scan_info = GridContainer('Scan')

        # Stage status info
        label_stage_status = QtWidgets.QLabel('Stage status:')

        # Info on fluence in row
        label_fluence_row = QtWidgets.QLabel("Fluence previous row:")

        # Info on fluence in scan
        label_fluence_scan = QtWidgets.QLabel("Fluence completed scans:")

        # Remaining scans info
        label_nscan_info = QtWidgets.QLabel('Est. remaining scans:')

        # Scan parameters
        label_scan_params = QtWidgets.QLabel('Scan parameters:')

        # Add to layout
        scan_info.add_widget(widget=label_stage_status)
        scan_info.add_widget(widget=label_fluence_row)
        scan_info.add_widget(widget=label_fluence_scan)
        scan_info.add_widget(widget=label_nscan_info)
        scan_info.add_widget(widget=label_scan_params)

        # Store labels in class attribute to change their text later
        self.info_labels ={'setup': {'position': label_position_info, 'speed': label_speed_info, 'range': label_range_info},
                           'fluence': {'row': label_fluence_row, 'scan': label_fluence_scan},
                           'scan': {'status': label_stage_status, 'nscan': label_nscan_info, 'params': label_scan_params}}

        self.info_widget.add_widget(widget=setup_info)
        self.info_widget.add_widget(widget=scan_info)

        # Add spacer layout
        spacer = QtWidgets.QVBoxLayout()
        spacer.addStretch()
        self.info_widget.add_layout(spacer)

    def send_cmd(self, target, cmd, cmd_data=None):
        """Function emitting signal with command dict which is send to server in main"""
        if target == 'stage':
            self.sendCmd.emit({'hostname': self.stage_server, 'target': target, 'cmd': cmd, 'cmd_data': cmd_data})
        elif target == 'interpreter':
            self.sendCmd.emit({'hostname': 'localhost', 'target': target, 'cmd': cmd, 'cmd_data': cmd_data})

    def set_aim_fluence(self, nominal, exponent):
        self.aim_fluence = nominal * 10**exponent

    def set_min_current(self, min_current):
        self.min_scan_current = min_current * 1e-9  # Nano ampere

    def check_no_beam(self):

        if self.min_scan_current is not None:

            if self.beam_current < self.min_scan_current:

                self.beam_down_timer = time.time()

                if not self.beam_down:
                    self.send_cmd('stage', 'no_beam', True)
                    self.beam_down = True

            else:
                if self.beam_down:
                    if time.time() - self.beam_down_timer > 1.0:
                        self.send_cmd('stage', 'no_beam', False)
                        self.beam_down = False

    def update_info(self, **info):
        """Method to update the text of the label infos"""

        unit = None if 'unit' not in info else info['unit']
        entries = [self.info_labels[k] for k in self.info_labels]

        # Loop over potentially many info kwargs
        for kw in info:
            for entry in entries:
                if kw in entry:

                    # Get text of label
                    tmp_text = entry[kw].text()

                    # Update position label
                    if kw == 'position':
                        tmp_text = kw.capitalize() + ': ' + '({:.3f}, {:.3f})'.format(*info[kw]) + ('' if unit is None else ' {}'.format(unit))
                        self.current_pos = info[kw]
                    # Update speed label
                    elif kw == 'speed':
                        tmp_text = kw.capitalize() + ': ' + '({:.3f}, {:.3f})'.format(*info[kw]) + ('' if unit is None else ' {}'.format(unit))
                        self.current_speed = info[kw]
                    # Update travel range label
                    elif kw == 'range':
                        tmp_text = kw.capitalize() + ': '
                        tmp_text += 'x: ({:.3f}, {:.3f})'.format(*info[kw][0]) + (', ' if unit is None else ' {}, '.format(unit))
                        tmp_text += 'y: ({:.3f}, {:.3f})'.format(*info[kw][1]) + (', ' if unit is None else ' {}, '.format(unit))
                    # Update fluence in previous row label
                    elif kw == 'row':
                        tmp_text = 'Fluence previous row: ' + '{:.3E}'.format(info[kw]) + ('' if unit is None else ' {}'.format(unit))
                    # Update fluence overall scan label
                    elif kw == 'scan':
                        tmp_text = 'Fluence completed scans: ' + '{:.3E}'.format(info[kw]) + ('' if unit is None else ' {}'.format(unit))
                    # Update stage status label
                    elif kw == 'status':
                        tmp_text = 'Stage status: ' + '{}'.format(info[kw]) + ('' if unit is None else ' {}'.format(unit))
                    # Update estimated remaining scans label
                    elif kw == 'nscan':
                        tmp_text = 'Est. remaining scans: ' + '{}'.format(info[kw]) + ('' if unit is None else ' {}'.format(unit))

                    # Set text
                    entry[kw].setText(tmp_text)

    def update_scan_parameters(self, **params):

        unit = None if 'unit' not in params else params['unit'].strip()

        if unit is not None:
            del params['unit']

        # Update dicts
        for param in params:
            self.scan_params[param] = params[param]
            self._scan_param_units[param] = unit if unit is not None else ''

        # Update params text
        tmp_text = 'Scan parameters:\n'
        for i, n in enumerate(self.scan_params):
            if n == 'rows':
                continue
            tmp_text += '{}: {} {}, '.format(n, self.scan_params[n], self._scan_param_units[n])
            tmp_text += '\n' if (i + 1) % 4 == 0 else ''

        self.info_labels['scan']['params'].setText(tmp_text)

    def scan_status(self, status='started'):

        # Disable control widgets during scan
        self.scan_widget.set_read_only(read_only=status == 'started', omit=QtWidgets.QPushButton)
        self.scan_widget.set_widget_read_only(self.btn_start, read_only=status == 'started')
        self.control_widget.set_read_only(read_only=status == 'started')
        self.daq_widget.set_read_only(read_only=status == 'started')

    def update_rec_state(self, server, state):

        icon = self._style.SP_DialogYesButton if state else self._style.SP_DialogNoButton
        tooltip = "Recording" if state else "Data recording paused"
        btn_text = "Pause" if state else "Resume"
        self.daq_widget.widgets['rec_btns'][server].setText(btn_text)
        idx = [self.daq_widget.widgets['tabs'].tabText(i) for i in range(self.daq_widget.widgets['tabs'].count())].index(self.setup[server]['name'])
        self.daq_widget.widgets['tabs'].setTabIcon(idx, self._style.standardIcon(icon))
        self.daq_widget.widgets['tabs'].setTabToolTip(idx, tooltip)
