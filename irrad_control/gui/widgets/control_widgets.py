from PyQt5 import QtWidgets, QtCore
from collections import defaultdict


import irrad_control.devices.readout as ro
from irrad_control.devices import DEVICES_CONFIG
from irrad_control.gui.widgets import GridContainer
from irrad_control.gui.widgets import MotorstagePositionWindow
from irrad_control.gui.utils import fill_combobox_items


class ControlWidget(GridContainer):

    sendCmd = QtCore.pyqtSignal(dict)

    def send_cmd(self, hostname, target, cmd, cmd_data=None):
        self.sendCmd.emit({'hostname': hostname,
                           'target': target,
                           'cmd': cmd,
                           'cmd_data': cmd_data})


class MotorStageControlWidget(ControlWidget):

    motorstagePropertiesUpdated = QtCore.pyqtSignal()

    def __init__(self, server, parent=None):
        super(MotorStageControlWidget, self).__init__(name='Motorstage Control', parent=parent)

        # Store server hostname
        self.server = server

        # Main widget
        self.tabs = QtWidgets.QTabWidget()

        # Make motorstage positions window
        self.motorstage_positions_window = MotorstagePositionWindow()

        self.motorstage_properties = defaultdict(dict)

        self._init_buttons()

        self.add_widget(self.tabs)

    def _init_buttons(self):

        master_btn_stop = QtWidgets.QPushButton('Stop all motorstages')
        master_btn_stop.setStyleSheet('QPushButton {color: red;}')
        master_btn_stop.setToolTip("Stop movement of all motorstage")

        master_btn_positions = QtWidgets.QPushButton('Motorstage positions')
        master_btn_positions.setToolTip('View/edit motorstage positions')

        ### Connections ###
        master_btn_stop.clicked.connect(lambda _: [self.send_cmd(hostname=self.server, target=ms, cmd='stop') for ms in self.motorstage_properties])

        # Open positionswindow and switch to respective motorstage tab
        for x in [lambda _: self.motorstage_positions_window.show(),
                  lambda _: self.motorstage_positions_window.tabs.setCurrentIndex(self.tabs.currentIndex())]:
            master_btn_positions.clicked.connect(x)

        # self.add_widget(master_btn_stop)
        self.add_widget(master_btn_positions)

    def add_motorstage(self, motorstage, config):

        # Add only if not already a tab
        if motorstage not in self.motorstage_properties:

            # Make stop button
            label_stop = QtWidgets.QLabel("Stop motorstage:")
            btn_stop = QtWidgets.QPushButton('Stop')
            btn_stop.setStyleSheet('QPushButton {color: red;}')
            btn_stop.setToolTip("Stop movement of all axes of motorstage")

            # Range btn and spinbox
            label_range = QtWidgets.QLabel('Set range:')
            btn_range = QtWidgets.QPushButton('Set range')
            layout_spxs = QtWidgets.QHBoxLayout()
            spxs_range = []
            for i, k in enumerate(['low', 'high']):
                spx = QtWidgets.QDoubleSpinBox()
                spx.setPrefix(f'{k.capitalize()}: ')
                spx.setSuffix(' mm')
                spx.setDecimals(3)
                spx.setMinimum(0)
                spx.setMaximum(1e3)
                spx.setValue(0)
                layout_spxs.addWidget(spx)
                layout_spxs.addSpacing(self.grid.horizontalSpacing() if not i else 0)
                spxs_range.append(spx)

            # Make range limits follow each other
            spxs_range[0].valueChanged.connect(lambda v, s=spxs_range[1]: s.setValue(s.value() if v < s.value() else v + 1.0))
            spxs_range[1].valueChanged.connect(lambda v, s=spxs_range[0]: s.setValue(s.value() if v > s.value() else v - 1.0))

            # Movement speed
            label_speed = QtWidgets.QLabel('Set speed:')
            btn_speed = QtWidgets.QPushButton('Set speed')
            spx_speed = QtWidgets.QDoubleSpinBox()
            spx_speed.setMinimum(0.1)
            spx_speed.setMaximum(110.0)
            spx_speed.setDecimals(3)
            spx_speed.setSuffix(' mm/s')

            # Relative movements
            label_rel = QtWidgets.QLabel('Move relative:')
            btn_rel = QtWidgets.QPushButton('Move rel.')
            spx_rel = QtWidgets.QDoubleSpinBox()
            spx_rel.setDecimals(3)
            spx_rel.setMinimum(-1e3)
            spx_rel.setMaximum(1e3)
            spx_rel.setSuffix(' mm')

            # Absolute movements
            label_abs = QtWidgets.QLabel('Move absolute:')
            btn_abs = QtWidgets.QPushButton('Move abs.')
            spx_abs = QtWidgets.QDoubleSpinBox()
            spx_abs.setDecimals(3)
            spx_abs.setMinimum(0.0)
            spx_abs.setMaximum(1e3)
            spx_abs.setSuffix(' mm')

            # Predefined positions
            label_pos = QtWidgets.QLabel('Predefined positions:')
            label_pos.setToolTip('Move to or add/edit named stage positions')
            cbx_pos = QtWidgets.QComboBox()
            btn_pos = QtWidgets.QPushButton('Move to')

            # Get number of axis
            n_axis = 1 if 'n_axis' not in DEVICES_CONFIG[motorstage]['init'] else DEVICES_CONFIG[motorstage]['init']['n_axis']

            # Fill properties; base unit always mm
            for a in range(n_axis):
                self.motorstage_properties[motorstage][a] = {'range': [0, 1000], 'speed': 50, 'accel': 3000}

            # Handle multiple axes by combobox
            if n_axis > 1:

                # Axis selection
                label_axis = QtWidgets.QLabel('Axis selection: ')
                cbx_axis = QtWidgets.QComboBox()
                cbx_axis.addItems([f'Axis {n}' for n in range(n_axis)])

                # Connections
                for con in [
                            # Update button texts
                            lambda idx: btn_range.setText(f'Set {cbx_axis.itemText(idx)} range'),
                            lambda idx: btn_speed.setText(f'Set {cbx_axis.itemText(idx)} speed'),
                            lambda idx: btn_rel.setText(f'Move {cbx_axis.itemText(idx)} rel.'),
                            lambda idx: btn_abs.setText(f'Move {cbx_axis.itemText(idx)} abs.'),
                            # Update range spinboxes limits
                            lambda idx: spxs_range[1].setMaximum(DEVICES_CONFIG[motorstage]['init']['axis_init'][idx]['travel'] * 1e3),
                            lambda idx: [s.setValue(self.motorstage_properties[motorstage][idx]['range'][i]) for i, s in enumerate(spxs_range)],
                            lambda idx: spx_abs.setRange(*self.motorstage_properties[motorstage][idx]['range']),
                            lambda idx: spx_abs.setValue(self.motorstage_properties[motorstage][idx]['range'][0]),
                            # Update speed
                            lambda idx: spx_speed.setValue(self.motorstage_properties[motorstage][idx]['speed'])
                            ]:
                    cbx_axis.currentIndexChanged.connect(con)

                cbx_axis.currentIndexChanged.emit(cbx_axis.currentIndex())

                spxs_range[1].setMaximum(DEVICES_CONFIG[motorstage]['init']['axis_init'][cbx_axis.currentIndex()]['travel'] * 1e3)
                spx_abs.setMaximum(DEVICES_CONFIG[motorstage]['init']['axis_init'][cbx_axis.currentIndex()]['travel'] * 1e3)
            else:
                spxs_range[1].setMaximum(DEVICES_CONFIG[motorstage]['init']['travel'] * 1e3)
                spxs_range[1].setValue(spxs_range[1].maximum())
                spx_abs.setMaximum(DEVICES_CONFIG[motorstage]['init']['travel'] * 1e3)
                spx_speed.setValue(self.motorstage_properties[motorstage][0]['speed'])

            # Get axis index; also for 1 axis
            axis_idx = lambda: 0 if n_axis == 1 else cbx_axis.currentIndex()

            ### Connections ###
            ### Connect widgets ###
            # Update motorstage properties
            btn_range.clicked.connect(lambda _: self.motorstage_properties[motorstage][axis_idx()].update(
                {'range': [s.value() for s in spxs_range]}))
            btn_speed.clicked.connect(lambda _: self.motorstage_properties[motorstage][axis_idx()].update(
                {'speed': spx_speed.value()}))
            btn_range.clicked.connect(
                lambda _: spx_abs.setRange(*self.motorstage_properties[motorstage][axis_idx()]['range']))
            btn_range.clicked.connect(
                lambda _: spx_abs.setValue(self.motorstage_properties[motorstage][axis_idx()]['range'][0]))

            # Update combobox items
            self.motorstage_positions_window.motorstagePosChanged.connect(
                lambda pos, ms=motorstage: None if ms not in pos else fill_combobox_items(cbx_pos, pos[ms]))

            cbx_pos.currentTextChanged.connect(lambda text: btn_pos.setText(f'Move to {text}'))

            ### Connect commands ###
            # Generate axis kwargs with respect to n_axis
            axis_kwargs = lambda kwargs: kwargs if n_axis == 1 else {'axis': cbx_axis.currentIndex(), **kwargs}
            # Send stop to all axes of motorstage
            btn_stop.clicked.connect(lambda _, ms=motorstage: self.send_cmd(hostname=self.server,
                                                                            target=ms,
                                                                            cmd='stop'))
            # Range
            btn_range.clicked.connect(lambda _, ms=motorstage: self.send_cmd(hostname=self.server,
                                                                             target=ms,
                                                                             cmd='set_range',
                                                                             cmd_data={'kwargs': axis_kwargs({'value': [s.value() for s in spxs_range],
                                                                                                              'unit': 'mm'}),
                                                                                       'callback':
                                                                                           {'method': 'get_range',
                                                                                            'kwargs': {'unit': 'mm'}}}))
            # Speed
            btn_speed.clicked.connect(lambda _, ms=motorstage: self.send_cmd(hostname=self.server,
                                                                             target=ms,
                                                                             cmd='set_speed',
                                                                             cmd_data={'kwargs': axis_kwargs({'value': spx_speed.value(),
                                                                                                              'unit': 'mm/s'}),
                                                                                       'callback':
                                                                                           {'method': 'get_speed',
                                                                                            'kwargs': {'unit': 'mm/s'}}}))
            # Rel. movement
            btn_rel.clicked.connect(lambda _, ms=motorstage: self.send_cmd(hostname=self.server,
                                                                           target=ms,
                                                                           cmd='move_rel',
                                                                           cmd_data={'kwargs': axis_kwargs({'value': spx_rel.value(),
                                                                                                            'unit': 'mm'}),
                                                                                     'threaded': True}))  # Movement in separate thread
            # Abs. movement
            btn_abs.clicked.connect(lambda _, ms=motorstage: self.send_cmd(hostname=self.server,
                                                                           target=ms,
                                                                           cmd='move_abs',
                                                                           cmd_data={'kwargs': axis_kwargs({'value': spx_abs.value(),
                                                                                                            'unit': 'mm'}),
                                                                                     'threaded': True}))  # Movement in separate thread
            # Abs. movement
            btn_pos.clicked.connect(lambda _, ms=motorstage: self.send_cmd(hostname=self.server,
                                                                           target=ms,
                                                                           cmd='move_pos',
                                                                           cmd_data={'kwargs': {'pos': cbx_pos.currentText()},
                                                                                     'threaded': True}))  # Movement in separate thread

            # Add everything to container
            container = GridContainer(name='')
            container.grid.addWidget(label_stop, container.grid.rowCount(), 0)
            container.grid.addWidget(btn_stop, container.grid.rowCount() - 1, 1, 1, 2)
            if n_axis > 1:
                container.grid.addWidget(label_axis, container.grid.rowCount(), 0)
                container.grid.addWidget(cbx_axis, container.grid.rowCount() - 1, 1, 1, 2)
            container.add_widget(widget=[label_range, layout_spxs, btn_range])
            container.add_widget(widget=[label_speed, spx_speed, btn_speed])
            container.add_widget(widget=[label_rel, spx_rel, btn_rel])
            container.add_widget(widget=[label_abs, spx_abs, btn_abs])
            container.add_widget(widget=[label_pos, cbx_pos, btn_pos])

            self.tabs.addTab(container, motorstage)
            self.motorstage_positions_window.add_motorstage(motorstage=motorstage, config=config)


class ScanControlWidget(ControlWidget):

    scanParamsUpdated = QtCore.pyqtSignal(dict)

    def __init__(self, server, parent=None):
        super(ScanControlWidget, self).__init__(name='Scan Control', parent=parent)

        # Store server hostname
        self.server = server

        self.scan_params = {'row_sep': 1.0,
                            'scan_speed': 70.0,
                            'min_current': 0.0,
                            'aim_damage': 'niel',
                            'aim_value': 2e15,
                            'rel_start': [0.0, 0.0],
                            'rel_end': [0.0, 0.0]}

        self._after_scan_container = None

        self._init_ui()
        #self.init_after_scan_ui(40)

        spacer = QtWidgets.QVBoxLayout()
        spacer.addStretch()
        self.add_widget(spacer)

    def update_scan_params(self, **kwargs):
        self.scan_params.update(kwargs)
        self.scanParamsUpdated.emit(self.scan_params)

    def _init_ui(self):

        # Step size
        label_row_sep = QtWidgets.QLabel('Row separation:')
        label_row_sep.setToolTip("Separation of rows with which the scan grid is set up")
        spx_row_sep = QtWidgets.QDoubleSpinBox()
        spx_row_sep.setMinimum(0.01)
        spx_row_sep.setMaximum(20.0)
        spx_row_sep.setDecimals(3)
        spx_row_sep.setSuffix(" mm")
        spx_row_sep.valueChanged.connect(lambda v: self.update_scan_params(row_sep=v))
        spx_row_sep.setValue(self.scan_params['row_sep'])

        # Scan speed
        label_scan_speed = QtWidgets.QLabel('Scan speed:')
        label_scan_speed.setToolTip("Speed with which the DUT is scanned through each row")
        spx_scan_speed = QtWidgets.QDoubleSpinBox()
        spx_scan_speed.setMinimum(0.1)
        spx_scan_speed.setMaximum(110.0)
        spx_scan_speed.setDecimals(3)
        spx_scan_speed.setSuffix(' mm/s')
        spx_scan_speed.valueChanged.connect(lambda v: self.update_scan_params(scan_speed=v))
        spx_scan_speed.setValue(self.scan_params['scan_speed'])

        # Beam current
        label_min_current = QtWidgets.QLabel('Minimum current:')
        label_min_current.setToolTip("Minimum current which is required for a row to be scanned")
        spx_min_current = QtWidgets.QSpinBox()
        spx_min_current.setRange(0, 4000)
        spx_min_current.setSingleStep(50)
        spx_min_current.setSuffix(' nA')
        spx_min_current.setValue(0)
        spx_min_current.valueChanged.connect(lambda v: self.update_scan_params(min_current=v))

        # Fluence
        label_aim_damage = QtWidgets.QLabel('Aim damage:')
        label_aim_damage.setToolTip('Select type and quantity of damage to be introduced to DUT')
        rbtn_niel = QtWidgets.QRadioButton('NIEL')
        rbtn_tid = QtWidgets.QRadioButton('TID')
        spx_damage_val = QtWidgets.QDoubleSpinBox()
        spx_damage_val.setRange(1e-3, 10)
        spx_damage_val.setDecimals(3)
        spx_damage_exp = QtWidgets.QSpinBox()
        spx_damage_exp.setPrefix('e ')
        rbtn_niel.toggled.connect(lambda toggled, sv=spx_damage_val, se=spx_damage_exp:
                                  (se.setRange(3, 20), se.setSuffix(' neq / cm^2'), sv.setValue(2), se.setValue(15)))
        rbtn_tid.toggled.connect(lambda toggled, sv=spx_damage_val, se=spx_damage_exp:
                                 (se.setRange(1, 6), se.setSuffix(' Mrad'), sv.setValue(1), se.setValue(3)))
        rbtn_niel.toggled.connect(lambda toggled: self.update_scan_params(aim_damage='niel' if toggled else 'tid'))
        spx_damage_val.valueChanged.connect(lambda v: self.update_scan_params(aim_value=float(f'{v}e{spx_damage_exp.value()}')))
        spx_damage_exp.valueChanged.connect(lambda v: self.update_scan_params(aim_value=float(f'{spx_damage_val.value()}e{v}')))
        rbtn_niel.toggle()

        # Start point
        label_start = QtWidgets.QLabel('Relative start point:')
        spx_start_x = QtWidgets.QDoubleSpinBox()
        spx_start_x.setRange(-300., 300.)
        spx_start_x.setValue(0)
        spx_start_x.setDecimals(3)
        spx_start_x.setPrefix('x: ')
        spx_start_x.setSuffix(' mm')
        spx_start_y = QtWidgets.QDoubleSpinBox()
        spx_start_y.setRange(-300., 300.)
        spx_start_y.setValue(0)
        spx_start_y.setDecimals(3)
        spx_start_y.setPrefix('y: ')
        spx_start_y.setSuffix(" mm")
        spx_start_x.valueChanged.connect(lambda v: self.update_scan_params(rel_start=[v, spx_start_y.value()]))
        spx_start_y.valueChanged.connect(lambda v: self.update_scan_params(rel_start=[spx_start_x.value(), v]))

        # End point
        label_end = QtWidgets.QLabel('Relative end point:')
        spx_end_x = QtWidgets.QDoubleSpinBox()
        spx_end_x.setRange(-300., 300.)
        spx_end_x.setValue(0)
        spx_end_x.setDecimals(3)
        spx_end_x.setPrefix('x: ')
        spx_end_x.setSuffix(' mm')
        spx_end_y = QtWidgets.QDoubleSpinBox()
        spx_end_y.setRange(-300., 300.)
        spx_end_y.setValue(0)
        spx_end_y.setDecimals(3)
        spx_end_y.setPrefix('y: ')
        spx_end_y.setSuffix(' mm')
        spx_end_x.valueChanged.connect(lambda v: self.update_scan_params(rel_end=[v, spx_end_y.value()]))
        spx_end_y.valueChanged.connect(lambda v: self.update_scan_params(rel_start=[spx_end_x.value(), v]))

        # Scan
        btn_start = QtWidgets.QPushButton('START')
        btn_start.setToolTip("Start scan.")
        btn_start.clicked.connect(lambda _: self.send_cmd(hostname=self.server, target='scan', cmd='setup', cmd_data=self.scan_params))

        btn_finish = QtWidgets.QPushButton('FINISH')
        btn_finish.setToolTip("Finish the scan. Allow remaining rows to be scanned before finishing.")
        btn_finish.clicked.connect(lambda _: self.send_cmd(hostname=self.server, target='scan', cmd='finish'))

        # Stop button
        btn_stop = QtWidgets.QPushButton('STOP')
        btn_stop.setToolTip("Immediately cancel scan and return to scan origin")
        btn_stop.clicked.connect(lambda _: self.send_cmd(hostname=self.server, target='scan', cmd='stop'))

        btn_start.setStyleSheet('QPushButton {color: green;}')
        btn_finish.setStyleSheet('QPushButton {color: orange;}')
        btn_stop.setStyleSheet('QPushButton {color: red;}')

        layout_scan = QtWidgets.QHBoxLayout()
        layout_scan.setSpacing(self.grid.horizontalSpacing())
        layout_scan.addWidget(btn_start)
        layout_scan.addWidget(btn_finish)
        layout_scan.addWidget(btn_stop)

        # Add to layout
        self.add_widget(widget=[label_row_sep, spx_row_sep])
        self.add_widget(widget=[label_scan_speed, spx_scan_speed])
        self.add_widget(widget=[label_min_current, spx_min_current])
        self.add_widget(widget=[label_aim_damage, rbtn_niel, rbtn_tid])
        self.add_widget(widget=[QtWidgets.QLabel(''), spx_damage_val, spx_damage_exp])
        self.add_widget(widget=[label_start, spx_start_x, spx_start_y])
        self.add_widget(widget=[label_end, spx_end_x, spx_end_y])
        self.grid.addLayout(layout_scan, self.grid.rowCount(), 0, 1, 3)

    def init_after_scan_ui(self, n_rows):
        # Make container
        self._after_scan_container = GridContainer('After scan')

        # Individual row scanning
        label_scan_row = QtWidgets.QLabel('Scan individual row:')
        spx_row = QtWidgets.QSpinBox()
        spx_row.setPrefix('Row: ')
        spx_row.setRange(0, n_rows)
        spx_speed = QtWidgets.QDoubleSpinBox()
        spx_speed.setPrefix('Scan speed: ')
        spx_speed.setSuffix(' mm/s')
        spx_speed.setRange(1e-3, 110)
        spx_speed.setValue(self.scan_params['scan_speed'])
        spx_repeat = QtWidgets.QSpinBox()
        spx_repeat.setPrefix('Repeat: ')
        spx_repeat.setRange(1, 10)
        btn_scan_row = QtWidgets.QPushButton('Scan row')
        btn_scan_row.clicked.connect(lambda _: self.send_cmd(hostname=self.server, target='scan', cmd='row', cmd_data={'row': spx_row.value(),
                                                                                                                       'scan_speed': spx_speed.value(),
                                                                                                                       'repeat': spx_repeat.value()}))

        self._after_scan_container.add_widget(widget=[label_scan_row, spx_row, spx_speed, spx_repeat, btn_scan_row])
        self.grid.addWidget(self._after_scan_container, self.grid.rowCount(), 0, 1, 3)


class DAQControlWidget(ControlWidget):

    enableDAQRec = QtCore.pyqtSignal(str, bool)

    def __init__(self, server, ro_device, parent=None):
        super(DAQControlWidget, self).__init__(name='DAQ Control', parent=parent)

        self.server = server

        self.ro_device = ro_device

        self._style = QtWidgets.qApp.style()

        self._init_ui()

        spacer = QtWidgets.QVBoxLayout()
        spacer.addStretch()
        self.add_widget(spacer)

    def _init_ui(self):

        # Button to compensate for noise on raw data
        label_offset = QtWidgets.QLabel('Raw data offset:')
        btn_offset = QtWidgets.QPushButton('Compensate offset')
        btn_offset.clicked.connect(lambda _: self.send_cmd(hostname='localhost', target='interpreter', cmd='zero_offset', cmd_data=self.server))

        # Button for auto zero offset
        label_record = QtWidgets.QLabel("Data recording:")
        self.btn_record = QtWidgets.QPushButton('Pause')
        self.btn_record.clicked.connect(lambda _: self.send_cmd(hostname='localhost', target='interpreter', cmd='record_data', cmd_data=(self.server, self.btn_record.text() == 'Resume')))

        chbx_record = QtWidgets.QCheckBox('Enable toggling recording state in DAQ dock')
        chbx_record.stateChanged.connect(lambda state: self.enableDAQRec.emit(self.server, bool(state)))

        # Change RO scale
        label_ro_scale = QtWidgets.QLabel("Set R/O group scale:")
        cbx_group = QtWidgets.QComboBox()
        cbx_group.addItems(ro.DAQ_BOARD_CONFIG['common']['gain_groups'])
        cbx_scale = QtWidgets.QComboBox()
        cbx_scale.addItems(ro.DAQ_BOARD_CONFIG['common']['ifs_labels'])
        btn_ro_scale = QtWidgets.QPushButton('Set R/O scale')
        layout_scale = QtWidgets.QHBoxLayout()
        layout_scale.setSpacing(self.grid.horizontalSpacing())
        layout_scale.addWidget(cbx_group)
        layout_scale.addWidget(cbx_scale)

        for action in [
            # Stop recording data
            lambda _: self.send_cmd(hostname='localhost',
                                    target='interpreter',
                                    cmd='record_data',
                                    cmd_data=(self.server, False)),
            # Switch scale on hardware
            lambda _: self.send_cmd(hostname=self.server,
                                    target='IrradDAQBoard',
                                    cmd='set_ifs',
                                    cmd_data={'kwargs': {'ifs': ro.DAQ_BOARD_CONFIG['common']['ifs_scales'][cbx_scale.currentIndex()],
                                                         'group': cbx_group.currentText()},
                                              'callback': {'method': 'get_ifs', 'kwargs': {'group': cbx_group.currentText()}}})]:
            btn_ro_scale.clicked.connect(action)

        self.add_widget(widget=[label_offset, btn_offset])
        self.add_widget(widget=[label_record, self.btn_record])
        self.add_widget(widget=[QtWidgets.QLabel(''), chbx_record])

        if self.ro_device == ro.RO_DEVICES.DAQBoard:
            self.add_widget(widget=[label_ro_scale, layout_scale, btn_ro_scale])

        self.update_rec_state(state=True)

    def update_rec_state(self, state):
        icon = self._style.standardIcon(self._style.SP_DialogYesButton if state else self._style.SP_DialogNoButton)
        tooltip = "Recording" if state else "Data recording paused"
        btn_text = "Pause" if state else "Resume"
        self.btn_record.setText(btn_text)
        self.btn_record.setIcon(icon)
        self.btn_record.setToolTip(tooltip)


class StatusInfoWidget(GridContainer):
    pass
