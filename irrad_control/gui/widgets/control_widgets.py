from PyQt5 import QtWidgets, QtCore
from collections import defaultdict


import irrad_control.devices.readout as ro
from irrad_control.devices import DEVICES_CONFIG
from irrad_control.gui.widgets import GridContainer
from irrad_control.gui.widgets import MotorstagePositionWindow
from irrad_control.gui.utils import fill_combobox_items


class ControlWidget(GridContainer):

    sendCmd = QtCore.pyqtSignal(dict)

    def __init__(self, name, x_space=20, y_space=10, parent=None, enable=True):
        super().__init__(name, x_space, y_space, parent)

        if enable:
            self._init_widget()
        else:
            self.add_widget(widget=QtWidgets.QLabel(f'{self.name} currently not available!'))


    def send_cmd(self, hostname, target, cmd, cmd_data=None):
        self.sendCmd.emit({'hostname': hostname,
                           'target': target,
                           'cmd': cmd,
                           'cmd_data': cmd_data})

    def _init_widget(self):
        raise NotImplementedError


class MotorStageControlWidget(ControlWidget):

    motorstagePropertiesUpdated = QtCore.pyqtSignal(str)

    def __init__(self, server, parent=None, enable=True):
        # Store server hostname
        self.server = server
        super(MotorStageControlWidget, self).__init__(name='Motorstage Control', parent=parent, enable=enable)

    def _init_widget(self):
        # Main widget
        self.tabs = QtWidgets.QTabWidget()

        # Make motorstage positions window
        self.motorstage_positions_window = MotorstagePositionWindow()

        self.motorstage_positions_window.motorstagePosAdded.connect(lambda ms, pos: [self.send_cmd(hostname=self.server,
                                                                                                   target=ms,
                                                                                                   cmd='add_position',
                                                                                                   cmd_data={'kwargs': {'name': n, **p},
                                                                                                             'callback': {'method': 'get_positions'}})
                                                                                     for n, p in pos.items()])


        self.motorstage_positions_window.motorstagePosRemoved.connect(lambda ms, pos: self.send_cmd(hostname=self.server,
                                                                                                    target=ms,
                                                                                                    cmd='remove_position',
                                                                                                    cmd_data={'kwargs': {'name': pos},
                                                                                                              'callback': {'method': 'get_positions'}})
                                                                                       )

        self.motorstage_properties = defaultdict(dict)

        self._ms_widgets = defaultdict(dict)

        self._init_buttons()

        self.add_widget(self.tabs)

    def _init_buttons(self):

        master_btn_stop = QtWidgets.QPushButton('Stop all motorstages')
        master_btn_stop.setStyleSheet('QPushButton {color: red;}')
        master_btn_stop.setToolTip("Stop movement of all motorstage")

        master_btn_positions = QtWidgets.QPushButton('Motorstage positions')
        master_btn_positions.setToolTip('View/edit motorstage positions')

        ### Connections ###
        master_btn_stop.clicked.connect(lambda _: [self.send_cmd(hostname=self.server,
                                                                 target=ms,
                                                                 cmd='stop',
                                                                 cmd_data={'callback': {'method': 'get_physical_props',
                                                                                        'kwargs': {'base_unit': 'mm'}}})
                                                    for ms in self.motorstage_properties])

        # Open positionswindow and switch to respective motorstage tab
        for x in [lambda _: self.motorstage_positions_window.show(),
                  lambda _: self.motorstage_positions_window.tabs.setCurrentIndex(self.tabs.currentIndex())]:
            master_btn_positions.clicked.connect(x)

        self.add_widget(master_btn_stop)
        self.add_widget(master_btn_positions)

    def _get_n_axis(self, motorstage):
        return DEVICES_CONFIG[motorstage]['init'].get('n_axis', 1)

    def _update_ui_elements(self, motorstage):
        
        if self._get_n_axis(motorstage) == 1:
            self._ms_widgets[motorstage]['spxs_range'][0].setValue(self.motorstage_properties[motorstage]['range'][0])
            self._ms_widgets[motorstage]['spxs_range'][1].setValue(self.motorstage_properties[motorstage]['range'][1])
            self._ms_widgets[motorstage]['spx_speed'].setValue(self.motorstage_properties[motorstage]['speed'])
            self._ms_widgets[motorstage]['spx_abs'].setRange(*self.motorstage_properties[motorstage]['range'])
            self._ms_widgets[motorstage]['spx_abs'].setValue(self.motorstage_properties[motorstage]['range'][0])
            self._ms_widgets[motorstage]['label_pos'].setText(f"{self.motorstage_properties[motorstage]['position']:.3f} mm")

        else:
            axis_idx = self._ms_widgets[motorstage]['cbx_axis'].currentIndex()
            self._ms_widgets[motorstage]['spxs_range'][0].setValue(self.motorstage_properties[motorstage][axis_idx]['range'][0])
            self._ms_widgets[motorstage]['spxs_range'][1].setValue(self.motorstage_properties[motorstage][axis_idx]['range'][1])
            self._ms_widgets[motorstage]['spx_speed'].setValue(self.motorstage_properties[motorstage][axis_idx]['speed'])
            self._ms_widgets[motorstage]['spx_abs'].setRange(*self.motorstage_properties[motorstage][axis_idx]['range'])
            self._ms_widgets[motorstage]['spx_abs'].setValue(self.motorstage_properties[motorstage][axis_idx]['range'][0])
            self._ms_widgets[motorstage]['label_pos'].setText(',    '.join(f"Axis {i}: {p['position']:.3f} mm" for i, p in self.motorstage_properties[motorstage].items()))

    def update_motorstage_properties(self, motorstage, properties, axis=None):

        if motorstage in self.motorstage_properties:
            if 'n_axis' in DEVICES_CONFIG[motorstage]['init']:
                if axis is not None:
                    self.motorstage_properties[motorstage][axis].update(properties)
                else:
                    for i in range(DEVICES_CONFIG[motorstage]['init']['n_axis']):
                        self.motorstage_properties[motorstage][i].update(properties[i])
            else:
                self.motorstage_properties[motorstage].update(properties)

            self.motorstagePropertiesUpdated.emit(motorstage)

    def add_motorstage(self, motorstage, positions, properties):

        # Add only if not already a tab
        if motorstage not in self.motorstage_properties:

            # Label for current positions
            _label_curr_pos = QtWidgets.QLabel("Current position:")
            if self._get_n_axis(motorstage) == 1:
                label_curr_pos = QtWidgets.QLabel(f"{properties['position']} mm")
            else:
                label_curr_pos = QtWidgets.QLabel(';\t'.join(f"Axis {i}: {p['position']} mm" for i, p in enumerate(properties)))

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
            n_axis = self._get_n_axis(motorstage)

            # Axis selection
            label_axis = QtWidgets.QLabel('Axis selection: ')
            cbx_axis = QtWidgets.QComboBox()

            spxs_range[0].valueChanged.connect(lambda v, sa=spx_abs: sa.setRange(v, spxs_range[1].value()))
            spxs_range[1].valueChanged.connect(lambda v, sa=spx_abs: sa.setRange(spxs_range[0].value(), v))

            # Handle multiple axes by combobox
            if n_axis > 1:

                # Fill properties; base unit always mm
                for a in range(n_axis):
                    self.motorstage_properties[motorstage][a] = {prop: properties[a][prop] for prop in properties[a]}
                    cbx_axis.addItem(f'Axis {a}')

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
                spxs_range[1].setValue(self.motorstage_properties[motorstage][cbx_axis.currentIndex()]['range'][1])

            else:
                # Only one axis
                for prop in properties:
                    self.motorstage_properties[motorstage][prop] = properties[prop]

                spxs_range[1].setMaximum(DEVICES_CONFIG[motorstage]['init']['travel'] * 1e3)
                spxs_range[1].setValue(self.motorstage_properties[motorstage]['range'][1])
                spx_abs.setMaximum(DEVICES_CONFIG[motorstage]['init']['travel'] * 1e3)
                spx_speed.setValue(self.motorstage_properties[motorstage]['speed'])
        
            ### Connections ###
            ### Connect widgets ###

            # Update UI elements for the motorstage
            self.motorstagePropertiesUpdated.connect(lambda ms: self._update_ui_elements(ms))

            # Update combobox items
            self.motorstage_positions_window.motorstagePosChanged.connect(
                lambda ms, pos: fill_combobox_items(self._ms_widgets[ms]['cbx_pos'], pos))

            cbx_pos.currentTextChanged.connect(lambda text: btn_pos.setText(f'Move to {text}'))

            ### Connect commands ###
            # Generate axis kwargs with respect to n_axis
            axis_kwargs = lambda kwargs: kwargs if n_axis == 1 else {'axis': cbx_axis.currentIndex(), **kwargs}
            # Send stop to all axes of motorstage
            btn_stop.clicked.connect(lambda _, ms=motorstage: self.send_cmd(hostname=self.server,
                                                                            target=ms,
                                                                            cmd='stop',
                                                                            cmd_data={'callback': {'method': 'get_physical_props',
                                                                                                   'kwargs': {'base_unit': 'mm'}}}))
            # Range
            btn_range.clicked.connect(lambda _, ms=motorstage: self.send_cmd(hostname=self.server,
                                                                             target=ms,
                                                                             cmd='set_range',
                                                                             cmd_data={'kwargs': axis_kwargs({'value': [s.value() for s in spxs_range],
                                                                                                              'unit': 'mm'}),
                                                                                       'callback':
                                                                                           {'method': 'get_physical_props',
                                                                                            'kwargs': {'base_unit': 'mm'}}}))
            # Speed
            btn_speed.clicked.connect(lambda _, ms=motorstage: self.send_cmd(hostname=self.server,
                                                                             target=ms,
                                                                             cmd='set_speed',
                                                                             cmd_data={'kwargs': axis_kwargs({'value': spx_speed.value(),
                                                                                                              'unit': 'mm/s'}),
                                                                                       'callback':
                                                                                           {'method': 'get_physical_props',
                                                                                            'kwargs': {'base_unit': 'mm'}}}))
            
            # Rel. movement
            btn_rel.clicked.connect(lambda _, ms=motorstage: self._send_movement_cmd(motorstage=ms,
                                                                                     cmd='move_rel',
                                                                                     cmd_data={'kwargs': axis_kwargs({'value': spx_rel.value(), 'unit': 'mm'}),
                                                                                               'threaded': True}))  # Movement in separate thread
            # Abs. movement
            btn_abs.clicked.connect(lambda _, ms=motorstage: self._send_movement_cmd(motorstage=ms,
                                                                                     cmd='move_abs',
                                                                                     cmd_data={'kwargs': axis_kwargs({'value': spx_abs.value(), 'unit': 'mm'}),
                                                                                               'threaded': True}))  # Movement in separate thread
            # Abs. movement
            btn_pos.clicked.connect(lambda _, ms=motorstage: self._send_movement_cmd(motorstage=ms,
                                                                                     cmd='move_pos',
                                                                                     cmd_data={'kwargs': {'name': cbx_pos.currentText()},
                                                                                               'threaded': True}))  # Movement in separate thread

            # Add all widgets which need to be accessed by instance to dict
            self._ms_widgets[motorstage]['label_pos'] = label_curr_pos
            self._ms_widgets[motorstage]['btn_stop'] = btn_stop
            self._ms_widgets[motorstage]['cbx_axis'] = cbx_axis
            self._ms_widgets[motorstage]['spxs_range'] = spxs_range
            self._ms_widgets[motorstage]['spx_speed'] = spx_speed
            self._ms_widgets[motorstage]['cbx_pos'] = cbx_pos
            self._ms_widgets[motorstage]['spx_abs'] = spx_abs
            
            # Add everything to container
            container = GridContainer(name='')
            container.grid.addWidget(_label_curr_pos, container.grid.rowCount(), 0)
            container.grid.addWidget(label_curr_pos, container.grid.rowCount() - 1, 1, 1, 2)
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
            self.motorstage_positions_window.add_motorstage(motorstage=motorstage, positions=positions, properties=properties)

    def _send_movement_cmd(self, motorstage, cmd, cmd_data):
        
        restricted = ('SetupTableStage', 'ExternalCupStage')
        restricted_controllable = [r in self.motorstage_properties for r in restricted]
        move = False

        # Do checks on restricted movement
        if motorstage in restricted:
            
            # We have control over all stages which is nice
            if all(restricted_controllable):

                if motorstage == restricted[0] and self.motorstage_properties[restricted[1]]['position'] > 1:
                    # We need to move restricted[1] to 0 first to allow movement of restricted[0]
                    restricting_ms = restricted[1]
                elif motorstage == restricted[1] and self.motorstage_properties[restricted[0]]['position'] > 1:
                    # We need to move restricted[0] to 0 first to allow movement of restricted[1]
                    restricting_ms = restricted[0]
                else:
                    restricting_ms = None        
                
                # If no restriction, move
                if restricting_ms is None:
                    move = True
                
                else:
                    # Construct message for user
                    msg = f"Movement of {motorstage} is currently restricted due to {restricting_ms} position being not 0 mm"
                    msg += f" (current position at {self.motorstage_properties[restricting_ms]['position']} mm)."
                    msg += f" Do you wish to move {restricting_ms} to its 0 position first? Make sure {restricting_ms} can be moved without obstacles!"
                    msg += f"Press 'OK' to move {restricting_ms}, press 'Abort' to cancel."
                    msg += f" You can always stop {restricting_ms}s movement using the 'Stop' button."

                    # Make MessageBox
                    mbox = QtWidgets.QMessageBox()
                    mbox.setIcon(QtWidgets.QMessageBox.Warning)
                    mbox.setWindowTitle(f"Movement of {motorstage} restricted by {restricting_ms}")
                    mbox.setText(msg)
                    mbox.addButton(QtWidgets.QMessageBox.Ok)
                    mbox.addButton(QtWidgets.QMessageBox.Abort)

                    # Move restricting motorstage first
                    if mbox.exec_() == QtWidgets.QMessageBox.Ok:
                        self.send_cmd(hostname=self.server,
                                      target=restricting_ms,
                                      cmd='move_abs',
                                      cmd_data={'kwargs': {'value': 0, 'unit': 'mm'},
                                                'threaded': True})
            
            # We have control over *motorstage* but not the other one        
            else:

                missing_ms = [restricted[i] for i, k in enumerate(restricted_controllable) if not k]
                
                # Construct message for user
                msg = f"Movement of {motorstage} may be restricted due to {missing_ms} not being at 0 position."
                msg += f" {missing_ms} is currently not controlled by irrad_control and its position can not be checked."
                msg += f"Do you wish to move {motorstage} anyway? Make sure that {missing_ms} is not restricting {motorstage}s movement!"
                msg += f"Press 'OK' to move {motorstage}, press 'Abort' to cancel."
                msg += f"You can always stop {motorstage}s movement using the 'Stop' button."

                # Make MessageBox
                mbox = QtWidgets.QMessageBox()
                mbox.setIcon(QtWidgets.QMessageBox.Warning)
                mbox.setWindowTitle(f"Movement of {motorstage} may be restricted by {missing_ms}")
                mbox.setText(msg)
                mbox.addButton(QtWidgets.QMessageBox.Ok)
                mbox.addButton(QtWidgets.QMessageBox.Abort)

                # Move anyway
                if mbox.exec_() == QtWidgets.QMessageBox.Ok:
                    move = True
        # Target motorstage is not restricted, just move
        else:
            move = True
        
        if move:
            self.send_cmd(hostname=self.server, target=motorstage, cmd=cmd, cmd_data=cmd_data)


class ScanControlWidget(ControlWidget):

    scanParamsUpdated = QtCore.pyqtSignal(dict)

    def __init__(self, server, daq_setup, parent=None, enable=True):

        # Store server hostname
        self.server = server
        self.daq_setup = daq_setup

        self.scan_params = {'row_sep': 1.0,
                            'scan_speed': 70.0,
                            'min_current': 0.0,
                            'aim_damage': 'primary',
                            'aim_value': 1e14,
                            'beam_fwhm': [10, 10],
                            'dut_rect_upper': [0, 0],
                            'dut_rect_lower': [0, 0],
                            'dut_rect_is_scan_area': False,
                            'server': self.server}

        self._after_scan_container = None
        self.n_rows = None
        self.auto_finish_scan = True

        super(ScanControlWidget, self).__init__(name='Scan Control', parent=parent, enable=enable)
    
    def _init_widget(self):
        
        self._init_ui()

        spacer = QtWidgets.QVBoxLayout()
        spacer.addStretch()
        self.add_widget(spacer)

    def launch_scan(self):
        self.send_cmd(hostname=self.server, target='__scan__', cmd='scan_device')

    def update_scan_params(self, **kwargs):
        self.scan_params.update(kwargs)
        self.scanParamsUpdated.emit(self.scan_params)

    def _damage_toggled(self, damage_buttons, sv, se):
        
        # Get active button
        active = damage_buttons.checkedButton()
        if active is None:
            damage = 'primary'
        else:
            damage = active.text().lower()

        if damage == 'primary':
            se.setSuffix(f" {self.daq_setup['ion']} / cm^2")
            se.setRange(3, 20)
            sv.setValue(1)
            se.setValue(14)
        elif damage == 'neq':
            se.setSuffix(f" neq / cm^2")
            se.setRange(3, 20)
            sv.setValue(1)
            se.setValue(14)
        else:
            se.setRange(1, 6)
            se.setSuffix(' Mrad')
            sv.setValue(1)
            se.setValue(2)

        self.update_scan_params(aim_damage=damage)

    def _init_ui(self):

        scan_parameters_container = GridContainer('Scan parameters')
        scan_parameters_container.setToolTip('Set up fixed scan parameters')

        # Row separation
        spx_row_sep = QtWidgets.QDoubleSpinBox()
        spx_row_sep.setToolTip("Separation of rows with which the scan grid is set up")
        spx_row_sep.setPrefix('Row separation: ')
        spx_row_sep.setMinimum(0.01)
        spx_row_sep.setMaximum(20.0)
        spx_row_sep.setDecimals(3)
        spx_row_sep.setSuffix(" mm")
        spx_row_sep.valueChanged.connect(lambda v: self.update_scan_params(row_sep=v))
        spx_row_sep.setValue(self.scan_params['row_sep'])

        # Scan speed
        spx_scan_speed = QtWidgets.QDoubleSpinBox()
        spx_scan_speed.setToolTip("Speed with which the DUT is scanned through each row")
        spx_scan_speed.setPrefix('Scan speed: ')
        spx_scan_speed.setMinimum(0.1)
        spx_scan_speed.setMaximum(110.0)
        spx_scan_speed.setDecimals(3)
        spx_scan_speed.setSuffix(' mm/s')
        spx_scan_speed.valueChanged.connect(lambda v: self.update_scan_params(scan_speed=v))
        spx_scan_speed.setValue(self.scan_params['scan_speed'])

        # Beam current
        spx_min_current = QtWidgets.QSpinBox()
        spx_min_current.setToolTip("Minimum current which is required for a row to be scanned")
        spx_min_current.setPrefix('Min. beam current: ')
        spx_min_current.setRange(0, 4000)
        spx_min_current.setSingleStep(50)
        spx_min_current.setSuffix(' nA')
        spx_min_current.setValue(0)
        spx_min_current.valueChanged.connect(lambda v: self.update_scan_params(min_current=v))

        scan_parameters_container.add_widget(widget=[spx_row_sep, spx_scan_speed, spx_min_current])

        damage_container = GridContainer('Radiation damage')
               
        label_damage_target = QtWidgets.QLabel('Target:')
        spx_damage_val = QtWidgets.QDoubleSpinBox()
        spx_damage_val.setRange(1e-3, 10)
        spx_damage_val.setDecimals(3)
        spx_damage_exp = QtWidgets.QSpinBox()
        spx_damage_exp.setPrefix('e ')

        label_damage_type = QtWidgets.QLabel('    Type:')
        rbtn_neq = QtWidgets.QRadioButton('NEQ')
        rbtn_tid = QtWidgets.QRadioButton('TID')
        rbtn_primary = QtWidgets.QRadioButton('Primary')
        damage_buttons = QtWidgets.QButtonGroup()
        damage_buttons.addButton(rbtn_neq)
        damage_buttons.addButton(rbtn_tid)
        damage_buttons.addButton(rbtn_primary)

        # Add radio buttons for different types of damage
        if self.daq_setup['kappa'] is None:
            damage_buttons.removeButton(rbtn_neq)    
        if self.daq_setup['stopping_power'] is None:
            damage_buttons.removeButton(rbtn_tid)

        for btn in damage_buttons.buttons():
            btn.toggled.connect(lambda _, bg=damage_buttons, sv=spx_damage_val, se=spx_damage_exp: self._damage_toggled(bg, sv, se))
        
        spx_damage_val.valueChanged.connect(lambda v: self.update_scan_params(aim_value=float(f'{v}e{spx_damage_exp.value()}')))
        spx_damage_exp.valueChanged.connect(lambda v: self.update_scan_params(aim_value=float(f'{spx_damage_val.value()}e{v}')))

        # Toggle initially
        rbtn_primary.toggle()

        damage_container.add_widget(widget=[label_damage_target, spx_damage_val, spx_damage_exp, label_damage_type] + damage_buttons.buttons()+[])
        #damage_container.add_widget(widget=[spx_damage_val, spx_damage_exp])

        beam_container = GridContainer(name='Beam parameters')

        # Beam FWHM
        label_fwhm = QtWidgets.QLabel('Beam FWHM:')
        spx_fwhm_x = QtWidgets.QDoubleSpinBox()
        spx_fwhm_x.setRange(1e-2, 20)
        spx_fwhm_x.setValue(10)
        spx_fwhm_x.setDecimals(2)
        spx_fwhm_x.setPrefix('x: ')
        spx_fwhm_x.setSuffix(' mm')
        spx_fwhm_y = QtWidgets.QDoubleSpinBox()
        spx_fwhm_y.setRange(1e-3, 20)
        spx_fwhm_y.setValue(10)
        spx_fwhm_y.setDecimals(2)
        spx_fwhm_y.setPrefix('y: ')
        spx_fwhm_y.setSuffix(' mm')
        spx_fwhm_x.valueChanged.connect(lambda v, s=spx_fwhm_y: self.update_scan_params(beam_fwhm=[v, s.value()]))
        spx_fwhm_y.valueChanged.connect(lambda v, s=spx_fwhm_x: self.update_scan_params(beam_fwhm=[s.value(), v]))

        beam_container.add_widget(widget=[label_fwhm, spx_fwhm_x, spx_fwhm_y])
        
        
        # Define DUT rectangle relative to the origin of the scan coordinate system
        dut_rect_container = GridContainer(name='Dut rectangle')
        dut_rect_container.setToolTip('Define the DUT area relative to the scan origin. Complete scan area will be calculated according to scan speed and beam fwhm')
        
        label_start = QtWidgets.QLabel('Start:')
        spx_start_x = QtWidgets.QDoubleSpinBox()
        spx_start_x.setRange(-300., 300.)
        spx_start_x.setValue(0)
        spx_start_x.setDecimals(2)
        spx_start_x.setPrefix('x: ')
        spx_start_x.setSuffix(' mm')
        spx_start_y = QtWidgets.QDoubleSpinBox()
        spx_start_y.setRange(-300., 300.)
        spx_start_y.setValue(0)
        spx_start_y.setDecimals(2)
        spx_start_y.setPrefix('y: ')
        spx_start_y.setSuffix(" mm")
        spx_start_x.valueChanged.connect(lambda v: self.update_scan_params(dut_rect_upper=[v, spx_start_y.value()]))
        spx_start_y.valueChanged.connect(lambda v: self.update_scan_params(dut_rect_upper=[spx_start_x.value(), v]))

        # End point
        label_end = QtWidgets.QLabel('    Stop:')
        spx_end_x = QtWidgets.QDoubleSpinBox()
        spx_end_x.setRange(-300., 300.)
        spx_end_x.setValue(0)
        spx_end_x.setDecimals(2)
        spx_end_x.setPrefix('x: ')
        spx_end_x.setSuffix(' mm')
        spx_end_y = QtWidgets.QDoubleSpinBox()
        spx_end_y.setRange(-300., 300.)
        spx_end_y.setValue(0)
        spx_end_y.setDecimals(2)
        spx_end_y.setPrefix('y: ')
        spx_end_y.setSuffix(' mm')
        spx_end_x.valueChanged.connect(lambda v: self.update_scan_params(dut_rect_lower=[v, spx_end_y.value()]))
        spx_end_y.valueChanged.connect(lambda v: self.update_scan_params(dut_rect_lower=[spx_end_x.value(), v]))

        checkbox_scan_rect = QtWidgets.QCheckBox('Use as scan area')
        checkbox_scan_rect.setToolTip('Use DUT rectangle as scan rectangle instead. No modifications will be made w.r.t scan speed or beam fwhm')
        checkbox_scan_rect.stateChanged.connect(lambda state: self.update_scan_params(dut_rect_is_scan_area=bool(state)))

        dut_rect_container.add_widget(widget=[label_start, spx_start_x, spx_start_y, label_end, spx_end_x, spx_end_y, checkbox_scan_rect])
        
        scan_interaction_container = GridContainer(name='Scan interaction')
        scan_interaction_container.setToolTip("Interact with the scanning routine during the scan")

        # Scan buttons
        btn_start = QtWidgets.QPushButton('START')
        btn_start.setToolTip("Start scan.")
        btn_start.clicked.connect(lambda _: self.send_cmd(hostname=self.server,
                                                          target='__scan__',
                                                          cmd='setup_scan',
                                                          cmd_data={'kwargs': {'scan_config': self.scan_params}}))

        btn_pause = QtWidgets.QPushButton('PAUSE')
        btn_pause.setToolTip("Pause the scan. Allow remaining rows to be scanned before pausing.")
        btn_pause.clicked.connect(lambda _: self.send_cmd(hostname=self.server,
                                                          target='__scan__',
                                                          cmd='handle_event',
                                                          cmd_data={'kwargs': {'event': btn_pause.text().lower()}}))
        btn_pause.clicked.connect(lambda _: btn_pause.setText('CONTINUE' if btn_pause.text() == 'PAUSE' else 'PAUSE'))

        btn_finish = QtWidgets.QPushButton('FINISH')
        btn_finish.setToolTip("Finish the scan. Allow remaining rows to be scanned before finishing.")
        btn_finish.clicked.connect(lambda _: self.send_cmd(hostname=self.server,
                                                           target='__scan__',
                                                           cmd='handle_event',
                                                           cmd_data={'kwargs': {'event': 'finish'}}))

        # Stop button
        btn_stop = QtWidgets.QPushButton('STOP')
        btn_stop.setToolTip("Immediately cancel scan and return to scan origin")
        btn_stop.clicked.connect(lambda _: self.send_cmd(hostname=self.server,
                                                           target='__scan__',
                                                           cmd='handle_event',
                                                           cmd_data={'kwargs': {'event': 'abort'}}))

        btn_start.setStyleSheet('QPushButton {color: green;}')
        btn_pause.setStyleSheet('QPushButton {color: green;}')
        btn_finish.setStyleSheet('QPushButton {color: orange;}')
        btn_stop.setStyleSheet('QPushButton {color: red;}')
        
        # Cheboxes
        # Auto finish scan
        checkbox_auto_finish = QtWidgets.QCheckBox('Auto finish scan')
        checkbox_auto_finish.setToolTip("Automatically finish scan procedure when target damage is reached.")
        checkbox_auto_finish.stateChanged.connect(lambda state: setattr(self, 'auto_finish_scan', bool(state)))
        checkbox_auto_finish.setChecked(True)

        scan_interaction_container.add_widget(widget=[btn_start, btn_pause, btn_finish, btn_stop])
        scan_interaction_container.add_widget(widget=checkbox_auto_finish)

        # Add to layout
        self.add_widget(damage_container)
        self.add_widget(scan_parameters_container)
        self.add_widget(beam_container)
        self.add_widget(dut_rect_container)
        self.add_widget(scan_interaction_container)

        self.widgets['scan_interaction_container'] = scan_interaction_container

    def init_after_scan_ui(self):

        if self.n_rows is not None:
            # Make container
            self._after_scan_container = GridContainer('After scan')

            # Individual row scanning
            label_scan_row = QtWidgets.QLabel('Scan individual row:')
            spx_row = QtWidgets.QSpinBox()
            spx_row.setPrefix('Row: ')
            spx_row.setRange(0, self.n_rows - 1)
            spx_speed = QtWidgets.QDoubleSpinBox()
            spx_speed.setPrefix('Scan speed: ')
            spx_speed.setSuffix(' mm/s')
            spx_speed.setRange(1e-3, 110)
            spx_speed.setValue(self.scan_params['scan_speed'])
            spx_repeat = QtWidgets.QSpinBox()
            spx_repeat.setPrefix('Repeat: ')
            spx_repeat.setRange(1, 10)
            btn_scan_row = QtWidgets.QPushButton('Scan row')
            btn_scan_row.clicked.connect(lambda _: self.send_cmd(hostname=self.server,
                                                                target='__scan__',
                                                                cmd='scan_row',
                                                                cmd_data={'kwargs': {'row': spx_row.value(),
                                                                                    'speed': spx_speed.value(),
                                                                                    'repeat': spx_repeat.value()}}))

            self._after_scan_container.add_widget(widget=[label_scan_row, spx_row, spx_speed, spx_repeat, btn_scan_row])
            self.add_widget(self._after_scan_container)


class DAQControlWidget(ControlWidget):

    enableDAQRec = QtCore.pyqtSignal(str, bool)

    def __init__(self, server, ro_device, parent=None, enable=True):
        self.server = server
        self.ro_device = ro_device
        self._style = QtWidgets.qApp.style()
        super(DAQControlWidget, self).__init__(name='DAQ Control', parent=parent, enable=enable)

    def _init_widget(self):
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
