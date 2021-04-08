from PyQt5 import QtWidgets, QtCore
from collections import defaultdict

# Package imports
import irrad_control.devices.readout as ro
from irrad_control.gui.widgets import GridContainer
from irrad_control.devices.ic.ADS1256 import ads1256
from irrad_control.gui.utils import check_unique_input


def _check_has_text(_edit):
    t = _edit.text()
    return True if t and t != '...' else False


class BaseSetupWidget(GridContainer):

    setupChanged = QtCore.pyqtSignal(dict)

    @property
    def isSetup(self):
        return True

    @isSetup.setter
    def isSetup(self, s):
        raise ValueError('*isSetup* is read-only property')

    def setup(self):
        raise NotImplementedError('Implement a *setup* method which returns a setup dict')

    def _setup_changed(self):
        self.setupChanged.emit(self.setup())


class DeviceSetup(BaseSetupWidget):

    def __init__(self, name, parent=None):
        super(DeviceSetup, self).__init__(name=name, parent=parent)

        self._init_setup()

    def _init_setup(self):

        checkbox_stage = QtWidgets.QCheckBox('XY-Stage')
        checkbox_adc = QtWidgets.QCheckBox('ADC')
        checkbox_temp = QtWidgets.QCheckBox('Temperature sensor')

        # Add to layout
        self.add_widget(widget=[checkbox_stage, checkbox_adc, checkbox_temp])

        self.widgets['adc'] = checkbox_adc
        self.widgets['stage'] = checkbox_stage
        self.widgets['temp'] = checkbox_temp


class NTCSetup(BaseSetupWidget):

    @property
    def isSetup(self):
        check_edits = [e for i, e in enumerate(self.widgets['ntc_edits']) if self.widgets['ntc_chbxs'].isChecked()]
        return False if not check_edits else check_unique_input(check_edits)

    def __init__(self, name, n_sensors=8, parent=None):
        super(NTCSetup, self).__init__(name=name, parent=parent)

        self.n_sensors = n_sensors

        self._init_setup()

    def _init_setup(self):

        chbxs = []
        edits = []
        for i in range(self.n_sensors):
            chbx = QtWidgets.QCheckBox()
            edit = QtWidgets.QLineEdit()
            edit.setPlaceholderText('NTC #{}'.format(i + 1))
            chbx.stateChanged.connect(lambda state, e=edit: e.setEnabled(state))
            if i == 0:
                chbx.setChecked(True)
            chbx.stateChanged.emit(chbx.checkState())
            chbxs.append(chbx)
            edits.append(edit)

            # Connect
            edit.textEdited.connect(lambda _: self._setup_changed())
            chbx.stateChanged.connect(lambda _: self._setup_changed())

        # Add to layout
        widget_list = []
        widget_list1 = []
        for j in range(len(chbxs)):
            if j < int(len(chbxs)/2):
                widget_list.append(chbxs[j])
                widget_list.append(edits[j])
            else:
                widget_list1.append(chbxs[j])
                widget_list1.append(edits[j])

        self.add_widget(widget=widget_list)
        self.add_widget(widget=widget_list1)

        self.widgets['ntc_chbxs'] = chbxs
        self.widgets['ntc_edits'] = edits

    def setup(self):

        ntc = {}
        ntc['ntc_sensors'] = [i for i in range(len(self.widgets['ntc_chbxs'])) if self.widgets['ntc_chbxs'][i].isChecked()]
        ntc['ntc_names'] = [e.text() or e.placeholderText() for i, e in enumerate(self.widgets['ntc_edits']) if i in ntc['ntc_sensors']]

        return ntc


class ReadoutSelection(BaseSetupWidget):

    setupChanged = QtCore.pyqtSignal(str)

    def __init__(self, name, parent=None):
        super(ReadoutSelection, self).__init__(name=name, parent=parent)

        self._init_setup()

    def _init_setup(self):

        radio_btn_grp = QtWidgets.QButtonGroup()
        btns = []
        for ro_dev in ro.RO_DEVICES + ('None',):
            rb = QtWidgets.QRadioButton(ro_dev)
            rb.clicked.connect(lambda _: self._setup_changed())
            radio_btn_grp.addButton(rb)
            if ro_dev == ro.RO_DEVICES.DAQBoard:
                rb.toggle()
            self.widgets[ro_dev] = rb
            btns.append(rb)

        self.add_widget(btns)

    def setup(self):
        return [t for t in self.widgets if self.widgets[t].isChecked()][0]


class ReadoutSetup(BaseSetupWidget):
    """Setup for R/O via 8 Channels ADC ADS1256"""

    @property
    def isSetup(self):
        check_0 = check_unique_input(self.widgets['channel_edits'], ignore=self.not_used_placeholder)
        check_1 = any(_check_has_text(e) for e in self.widgets['channel_edits'])
        check_2 = True if 'ntc_setup' not in self.widgets else self.widgets['ntc_setup'].isSetup
        return check_0 and check_1 and check_2

    def __init__(self, name, device=ro.RO_DEVICES.DAQBoard, n_channels=8, parent=None):
        """
        Parameters
        ----------
        name: str
            Name to be displayed by GridContainer
        device: str
            Which readout device is used; can be *adc*, *ro_electronics* or *ro_board*
        n_channels: int
            Number of ADC channels
        parent: QtWidgets.QWidget
            Parent widget
        """
        super(ReadoutSetup, self).__init__(name=name, parent=parent)

        if device not in ro.RO_DEVICES:
            raise ValueError('R/O device unknown. Must be on of {}'.format(', '.join(str(d) for d in ro.RO_DEVICES)))

        self.device = device
        self.n_channels = n_channels
        self.not_used_placeholder = 'Not used'

        self._init_setup()

    def _init_setup(self):

        # Temperature sensors
        if self.device == ro.RO_DEVICES.DAQBoard:
            checkbox_ntc = QtWidgets.QCheckBox('Connect NTCs')
            ntc_setup = NTCSetup('NTCs')
            ntc_setup.setupChanged.connect(lambda _: self._setup_changed())
            ntc_setup.setVisible(False)
            checkbox_ntc.stateChanged.connect(lambda state: ntc_setup.setVisible(bool(state)))
            self.widgets['ntc_chbx'] = checkbox_ntc
            self.widgets['ntc_setup'] = ntc_setup
            self.grid.addWidget(checkbox_ntc, self.grid.rowCount(), 0)
            self.grid.addWidget(ntc_setup, self.grid.rowCount(), 1, 1, 4)

        # Sampling rate related widgets
        label_sps = QtWidgets.QLabel('Sampling rate [sps]:')
        combo_srate = QtWidgets.QComboBox()
        combo_srate.addItems([str(drate) for drate in ads1256['drate'].values()])
        combo_srate.setCurrentIndex(list(ads1256['drate'].values()).index(100))
        self.widgets['srate_combo'] = combo_srate

        # Add to layout
        self.add_widget(widget=[label_sps, combo_srate])

        # R/O full-scale
        label_scale_str = 'R/O {} scale I_FS:'.format(self.device.split('_')[-1])
        label_scale = QtWidgets.QLabel(label_scale_str)
        label_scale.setToolTip("Input current corresponding to 5V full-scale output voltage")

        # Label for readout scale combobox
        widgets_to_add = [label_scale]

        if self.device != ro.RO_DEVICES.DAQBoard:
            combo_scale = QtWidgets.QComboBox()
            combo_scale.addItems(ro.RO_ELECTRONICS_CONFIG['ifs_labels'])
            combo_scale.setCurrentIndex(ro.RO_ELECTRONICS_CONFIG['ifs_scales'].index(ro.RO_ELECTRONICS_CONFIG['defaults']['ifs']))
            checkbox_scale = QtWidgets.QCheckBox('Set scale per channel')  # Allow individual scales per channel
            checkbox_scale.stateChanged.connect(lambda state: combo_scale.setEnabled(not bool(state)))
            widgets_to_add.extend([combo_scale, checkbox_scale])

            self.widgets['scale_combo'] = combo_scale
            self.widgets['scale_chbx'] = checkbox_scale

        else:
            combo_group_scale = {}
            lo = QtWidgets.QHBoxLayout()
            for group in ro.DAQ_BOARD_CONFIG['common']['gain_groups']:
                combo_group_scale[group] = QtWidgets.QComboBox()
                combo_group_scale[group].addItems(ro.DAQ_BOARD_CONFIG['common']['ifs_labels'])
                label_group = QtWidgets.QLabel('R/O group ' + group + ': ')
                lo.addWidget(label_group)
                lo.addSpacing(10)
                lo.addWidget(combo_group_scale[group])
                if group != ro.DAQ_BOARD_CONFIG['common']['gain_groups'][-1]:
                    lo.addStretch()
            checkbox_jumper = QtWidgets.QCheckBox('x 10 Jumper')
            checkbox_jumper.stateChanged.connect(
                lambda state, cbx=combo_group_scale:
                [(cbx[g].clear(), cbx[g].addItems(ro.DAQ_BOARD_CONFIG['common']['ifs_labels{}'.format('_10' if bool(state) else '')])) for g in cbx])

            widgets_to_add.extend([lo, checkbox_jumper])

            self.widgets['group_scale_combos'] = combo_group_scale
            self.widgets['jumper_chbx'] = checkbox_jumper

        # Add to layout
        self.add_widget(widget=widgets_to_add)
        self.add_widget(QtWidgets.QLabel('Channels:'))

        widgets_to_add = []
        # ADC channel related input widgets
        label_channel_number = QtWidgets.QLabel('#')
        label_channel_number.setToolTip('Number of the channel. Corresponds to physical channel on ADC')
        label_channel_name = QtWidgets.QLabel('Name')
        label_channel_name.setToolTip('Name of respective channel')
        widgets_to_add.extend([label_channel_number, label_channel_name])

        if self.device != ro.RO_DEVICES.DAQBoard:
            label_channel_scale = QtWidgets.QLabel('R/O scale')
            label_channel_scale.setToolTip('Readout scale of respective channel')
            widgets_to_add.append(label_channel_scale)
        else:
            label_channel_group = QtWidgets.QLabel('R/O group')
            label_channel_group.setToolTip('Readout group of respective channel')
            widgets_to_add.append(label_channel_group)

        label_channel_type = QtWidgets.QLabel('Type')
        label_channel_type.setToolTip('Type of channel according to the readout device')
        widgets_to_add.append(label_channel_type)

        label_channel_ref = QtWidgets.QLabel('Reference')
        label_channel_ref.setToolTip('Reference channel for measurement. Can be ground (GND) or any other channels.')
        widgets_to_add.append(label_channel_ref)

        # Add to layout
        self.add_widget(widget=widgets_to_add)

        input_widgets = defaultdict(list)

        # Loop over number of available ADC channels and make respective input widgets
        for i in range(self.n_channels):

            widgets_to_add = []

            # Channel name edit
            _edit = QtWidgets.QLineEdit()
            _edit.setPlaceholderText(self.not_used_placeholder)
            _edit.setText('' if i > len(ro.RO_DEFAULTS['ch_names']) - 1 else ro.RO_DEFAULTS['ch_names'][i])
            _edit.textEdited.connect(lambda _: self._setup_changed())
            input_widgets['channel_edits'].append(_edit)

            widgets_to_add.append(_edit)

            if self.device != ro.RO_DEVICES.DAQBoard:
                # Channel RO scale combobox
                _cbx_scale = QtWidgets.QComboBox()
                _cbx_scale.addItems(ro.RO_ELECTRONICS_CONFIG['ifs_labels'])
                _cbx_scale.setToolTip('Select R/O scale I_FS for each channel individually.')
                _cbx_scale.setCurrentIndex(combo_scale.currentIndex())
                _cbx_scale.setEnabled(False)
                input_widgets['scale_combos'].append(_cbx_scale)

                # Connections
                _edit.textChanged.connect(
                    lambda text, cbx=_cbx_scale, checkbox=checkbox_scale: cbx.setEnabled(checkbox.isChecked() and bool(text)))
                checkbox_scale.stateChanged.connect(
                    lambda state, cbx=_cbx_scale, edit=_edit: cbx.setEnabled(bool(state) if edit.text() else False))
                checkbox_scale.stateChanged.connect(
                    lambda _, cbx=_cbx_scale, combo=combo_scale: cbx.setCurrentIndex(combo.currentIndex()))
                combo_scale.currentIndexChanged.connect(
                    lambda idx, cbx=_cbx_scale, checkbox=checkbox_scale:
                    cbx.setCurrentIndex(idx if not checkbox.isChecked() else cbx.currentIndex()))

                widgets_to_add.append(_cbx_scale)

            else:
                _cbx_group = QtWidgets.QComboBox()
                _cbx_group.addItems(ro.DAQ_BOARD_CONFIG['common']['mux_groups'])
                _cbx_group.setToolTip('Select R/O group for each channel.')
                input_widgets['group_combos'].append(_cbx_group)

                # Connections
                _edit.textChanged.connect(
                    lambda text, cbx=_cbx_group: cbx.setEnabled(bool(text)))

                widgets_to_add.append(_cbx_group)

            # Channel type combobox
            _cbx_type = QtWidgets.QComboBox()
            _cbx_type.addItems(ro.RO_TYPES)
            _cbx_type.setToolTip('Select type of channel. If *general_purpose*, this info is used for interpretation.')
            _cbx_type.setCurrentIndex(i if i < len(ro.RO_DEFAULTS['ch_names']) else ro.RO_TYPES.index('general_purpose'))
            _cbx_type.setEnabled(bool(_edit.text()))
            input_widgets['type_combos'].append(_cbx_type)

            widgets_to_add.append(_cbx_type)

            # Reference channel to measure voltage; can be GND or any of the other channels
            _cbx_ref = QtWidgets.QComboBox()
            _cbx_ref.addItems(['GND'] + [str(k) for k in range(1, self.n_channels + 1) if k != i + 1])
            _cbx_ref.setCurrentIndex(0)
            _cbx_ref.setProperty('lastitem', 'GND')
            _cbx_ref.currentTextChanged.connect(lambda item, c=_cbx_ref: self._handle_ref_channels(item, c))
            _cbx_ref.setEnabled(_edit.text() != '')
            input_widgets['ref_combos'].append(_cbx_ref)

            widgets_to_add.append(_cbx_ref)

            # Connections
            _edit.textChanged.connect(lambda text, cbx=_cbx_type: cbx.setEnabled(bool(text)))
            _edit.textChanged.connect(lambda text, cbx=_cbx_ref: cbx.setEnabled(bool(text)))

            # Add to layout
            self.add_widget(widget=[QtWidgets.QLabel('{}.'.format(i + 1))] + widgets_to_add)

            _edit.textChanged.emit(_edit.text())

        # Store input widgets
        for iw in input_widgets:
            self.widgets[iw] = input_widgets[iw]

    def _handle_ref_channels(self, item, cbx):
        """Handles the ADC channel selection"""

        sender_idx = self.widgets['ref_combos'].index(cbx) + 1

        idx = None if item == 'GND' else int(item) - 1
        lastitem = cbx.property('lastitem')
        last_idx = None if lastitem == 'GND' else int(lastitem)
        cbx.setProperty('lastitem', 'GND' if idx is None else str(idx))

        if idx:

            self.widgets['channel_edits'][idx].setText('')
            self.widgets['channel_edits'][idx].setPlaceholderText('Ref. to ch. {}'.format(sender_idx))
            self.widgets['channel_edits'][idx].setEnabled(False)

            for rcbx in self.widgets['ref_combos']:
                if cbx != rcbx:
                    for i in range(rcbx.count()):
                        if rcbx.itemText(i) == item or rcbx.itemText(i) == str(sender_idx):
                            rcbx.model().item(i).setEnabled(False)

        if last_idx:

            self.widgets['channel_edits'][last_idx].setEnabled(True)
            self.widgets['channel_edits'][last_idx].setPlaceholderText(self.not_used_placeholder)

            for rcbx in self.widgets['ref_combos']:
                if cbx != rcbx:
                    for i in range(rcbx.count()):
                        if rcbx.itemText(i) == str(last_idx + 1) or (idx is None and rcbx.itemText(i) == str(sender_idx)):
                            rcbx.model().item(i).setEnabled(True)

    def setup(self):

        readout = {}

        readout['device'] = self.device
        readout['sampling_rate'] = float(self.widgets['srate_combo'].currentText())
        readout['channels'] = [e.text() for e in self.widgets['channel_edits'] if e.text()]
        readout['types'] = [c.currentText() for i, c in enumerate(self.widgets['type_combos']) if self.widgets['channel_edits'][i].text()]
        readout['ch_numbers'] = [i if self.widgets['ref_combos'][i].currentText() == 'GND'
                                 else (i, -1 + int(self.widgets['ref_combos'][i].currentText()))
                                 for i, w in enumerate(self.widgets['channel_edits']) if w.text()]

        if readout['device'] != ro.RO_DEVICES.DAQBoard:

            readout['ro_scales'] = [ro.RO_ELECTRONICS_CONFIG['ifs_scales'][ro.RO_ELECTRONICS_CONFIG['ifs_labels'].index(c.currentText())]
                                    for i, c in enumerate(self.widgets['scale_combos']) if self.widgets['channel_edits'][i].text()]
        else:
            readout['x10_jumper'] = self.widgets['jumper_chbx'].isChecked()
            readout['ro_group_scales'] = {g: ro.DAQ_BOARD_CONFIG['ifs_labels{}'.format(
                '_10' if readout['x10_jumper'] else '')].index(self.widgets['group_scale_combos'][g].currentText())
                                          for g in self.widgets['group_scale_combos']}
            readout['ch_groups'] = [c.currentText() for i, c in enumerate(self.widgets['group_combos']) if self.widgets['channel_edits'][i].text()]

            if self.widgets['ntc_chbx'].isChecked():
                readout['ntc'] = self.widgets['ntc_setup'].setup()

        return readout
