from PyQt5 import QtWidgets

# Package imports
from irrad_control.gui.widgets import GridContainer
from irrad_control.devices.ic.ADS1256 import ads1256
from irrad_control.devices.readout import ro_board_config, ro_electronics_config


class ReadoutSetup(GridContainer):
    """Setup for R/O via 8 Channels ADC ADS1256"""

    def __init__(self, name, ro_device='ro_board', n_channels=8, parent=None):
        """
        Parameters
        ----------
        name: str
            Name to be displayed by GridContainer
        ro_device: str
            Which readout device is used; can be *adc*, *ro_electronics* or *ro_board*
        n_channels: int
            Number of ADC channels
        parent: QtWidgets.QWidget
            Parent widget
        """
        super(ReadoutSetup, self).__init__(name=name, parent=parent)

        self._ro_devices = ('adc', 'ro_board', 'ro_electronics')

        if ro_device not in self._ro_devices:
            raise ValueError('R/O device unknown. Must be either *adc*, *ro_board* or *ro_electronics*')

        self.ro_device = ro_device
        self.n_channels = n_channels

        self.default_ch_names = ('Left', 'Right', 'Up', 'Down', 'Sum')

        self._init_setup()

    def _init_setup(self):

        # Sampling rate related widgets
        label_sps = QtWidgets.QLabel('Sampling rate [sps]:')
        combo_srate = QtWidgets.QComboBox()
        combo_srate.addItems([str(drate) for drate in ads1256['drate'].values()])
        combo_srate.setCurrentIndex(list(ads1256['drate'].values()).index(100))

        # Add to layout
        self.add_widget(widget=[label_sps, combo_srate])

        # Label for readout scale combobox
        if self.ro_device != 'adc':
            label_scale_str = 'R/O {} scale I_FS:'.format('electronics' if self.ro_device != 'ro_board' else 'board')
            label_scale = QtWidgets.QLabel(label_scale_str)
            label_scale.setToolTip("Input current corresponding to 5V full-scale output voltage")
            if self.ro_device != 'ro_board':
                combo_scale = QtWidgets.QComboBox()
                combo_scale.addItems(ro_electronics_config['ifs_labels'])
                combo_scale.setCurrentIndex(ro_electronics_config['ifs_labels'].index(ro_electronics_config['default']['ifs']))
                checkbox_scale = QtWidgets.QCheckBox('Set scale per channel')  # Allow individual scales per channel
                checkbox_scale.stateChanged.connect(lambda state: combo_scale.setEnabled(not bool(state)))
            else:
                combo_scale = {group: QtWidgets.QComboBox(ro_board_config['ifs_labels']) for group in ro_board_config['gain_groups']}
                checkbox_jumper = QtWidgets.QCheckBox('x 10 Jumper')
                checkbox_jumper.stateChanged.connect(
                    lambda state, cbx=combo_scale:
                    [(cbx[g].clear(), cbx[g].addItems(ro_board_config['ifs_labels{}'.format('_10' if bool(state) else '')])) for g in cbx])




                # Add to layout
        self.add_widget(widget=[label_scale, combo_scale, checkbox_scale])

        # ADC channel related input widgets
        label_channel = QtWidgets.QLabel('Channels:')
        label_channel_number = QtWidgets.QLabel('#')
        label_channel_number.setToolTip('Number of the channel. Corresponds to physical channel on ADC')
        label_channel_name = QtWidgets.QLabel('Name')
        label_channel_name.setToolTip('Name of respective channel')
        label_channel_scale = QtWidgets.QLabel('R/O scale')
        label_channel_scale.setToolTip('Readout scale of respective channel')
        label_channel_type = QtWidgets.QLabel('Type')
        label_channel_type.setToolTip('Type of channel according to the custom readout electronics')
        label_channel_ref = QtWidgets.QLabel('Reference')
        label_channel_ref.setToolTip('Reference channel for measurement. Can be ground (GND) or any other channels.')

        # Add to layout
        self.add_widget(widget=label_channel)
        self.add_widget(widget=[label_channel_number, label_channel_name, label_channel_scale, label_channel_type, label_channel_ref])

        # Input widgets lists
        edits = []
        combos_types = []
        combos_refs = []
        combos_scales = []
        combos_groups = []

        # Loop over number of available ADC channels which is 8.
        # Make combobox for channel type, edit for name and label for physical channel number
        for i in range(self.n_channels):
            # Channel RO scale combobox
            _cbx_scale = QtWidgets.QComboBox()
            _cbx_scale.addItems(list(_ro_scales.keys()))
            _cbx_scale.setToolTip('Select RO scale for each channel individually.')
            _cbx_scale.setCurrentIndex(combo_scale.currentIndex())

            # Channel RO group combobox
            _cbx_group = QtWidgets.QComboBox()
            _cbx_group.addItems(['sem', 'ch12'])
            _cbx_group.setToolTip('Select R/O board channel group individually.')

            # Channel type combobox
            _cbx_type = QtWidgets.QComboBox()
            _cbx_type.addItems(daq_config['adc_channels'])
            _cbx_type.setToolTip('Select type of readout channel. If not None, this info is used for interpretation.')
            _cbx_type.setCurrentIndex(i if i < len(self.default_channels) else daq_config['adc_channels'].index('none'))

            # Reference channel to measure voltage; can be GND or any of the other channels
            _cbx_ref = QtWidgets.QComboBox()
            _cbx_ref.addItems(['GND'] + [str(k) for k in range(1, self.n_channels + 1) if k != i + 1])
            _cbx_ref.setCurrentIndex(0)
            _cbx_ref.setProperty('lastitem', 'GND')
            _cbx_ref.currentTextChanged.connect(lambda item, c=_cbx_ref: self._handle_ref_channels(item, c))

            # Channel name edit
            _edit = QtWidgets.QLineEdit()
            _edit.setPlaceholderText('Not used')
            _edit.textChanged.connect(lambda text, cbx=_cbx_scale, checkbox=checkbox_scale: cbx.setEnabled(checkbox.isChecked() and (True if text else False)))
            _edit.textChanged.connect(lambda text, cbx=_cbx_type: cbx.setEnabled(True if text else False))
            _edit.textChanged.connect(lambda text, cbx=_cbx_ref: cbx.setEnabled(True if text else False))
            _edit.setText('' if i > len(self.default_channels) - 1 else self.default_channels[i])

            # Connections between RO scale combos
            checkbox_scale.stateChanged.connect(lambda state, cbx=_cbx_scale, edit=_edit: cbx.setEnabled(bool(state) if edit.text() else False))
            checkbox_scale.stateChanged.connect(lambda _, cbx=_cbx_scale, combo=combo_scale: cbx.setCurrentIndex(combo.currentIndex()))
            combo_scale.currentIndexChanged.connect(lambda idx, cbx=_cbx_scale, checkbox=checkbox_scale:
                                                    cbx.setCurrentIndex(idx if not checkbox.isChecked() else cbx.currentIndex()))

            # Disable widgets with no default channels at first
            _cbx_scale.setEnabled(False)
            _cbx_type.setEnabled(_edit.text() != '')
            _cbx_ref.setEnabled(_edit.text() != '')

            # Append to list
            edits.append(_edit)
            combos_types.append(_cbx_type)
            combos_refs.append(_cbx_ref)
            combos_scales.append(_cbx_scale)
            combos_groups.append(_cbx_group)

            # Add to layout
            self.add_widget(widget=[QtWidgets.QLabel('{}.'.format(i + 1)), _edit, _cbx_scale, _cbx_group, _cbx_type, _cbx_ref])

        # Store all input related widgets in dict
        self.widgets['scale_combo'] = combo_scale
        self.widgets['scale_combos'] = combos_scales
        self.widgets['group_combos'] = combos_groups
        self.widgets['type_combos'] = combos_types
        self.widgets['ref_combos'] = combos_refs
        self.widgets['channel_edits'] = edits
        self.widgets['srate_combo'] = combo_srate
        self.widgets['scale_chbx'] = checkbox_scale




class ADCSetup(GridContainer):

    def __init__(self, name, n_channels=8, parent=None):
        super(ADCSetup, self).__init__(name=name, parent=parent)

        # ADC name / identifier
        self.n_channels = n_channels
        self.default_channels = ('Left', 'Right', 'Up', 'Down', 'Sum')

        # Call setup
        self._init_setup()

    def _init_setup(self):

        # Sampling rate related widgets
        label_sps = QtWidgets.QLabel('Sampling rate [sps]:')
        combo_srate = QtWidgets.QComboBox()
        combo_srate.addItems([str(drate) for drate in ads1256['drate'].values()])
        combo_srate.setCurrentIndex(list(ads1256['drate'].values()).index(100))

        # Add to layout
        self.add_widget(widget=[label_sps, combo_srate])

        # Label for readout scale combobox
        label_scale = QtWidgets.QLabel('R/O electronics scale I_FS:')
        label_scale.setToolTip("Current corresponding to 5V full-scale voltage")
        combo_scale = QtWidgets.QComboBox()
        combo_scale.addItems(list(_ro_scales.keys()))
        combo_scale.setCurrentIndex(1)
        checkbox_scale = QtWidgets.QCheckBox('Set scale per channel')  # Allow individual scales per channel
        checkbox_scale.stateChanged.connect(lambda state: combo_scale.setEnabled(not bool(state)))

        # Add to layout
        self.add_widget(widget=[label_scale, combo_scale, checkbox_scale])

        # ADC channel related input widgets
        label_channel = QtWidgets.QLabel('Channels:')
        label_channel_number = QtWidgets.QLabel('#')
        label_channel_number.setToolTip('Number of the channel. Corresponds to physical channel on ADC')
        label_channel_name = QtWidgets.QLabel('Name')
        label_channel_name.setToolTip('Name of respective channel')
        label_channel_scale = QtWidgets.QLabel('R/O scale')
        label_channel_scale.setToolTip('Readout scale of respective channel')
        label_channel_type = QtWidgets.QLabel('Type')
        label_channel_type.setToolTip('Type of channel according to the custom readout electronics')
        label_channel_ref = QtWidgets.QLabel('Reference')
        label_channel_ref.setToolTip('Reference channel for measurement. Can be ground (GND) or any other channels.')

        # Add to layout
        self.add_widget(widget=label_channel)
        self.add_widget(widget=[label_channel_number, label_channel_name, label_channel_scale, label_channel_type, label_channel_ref])

        # Input widgets lists
        edits = []
        combos_types = []
        combos_refs = []
        combos_scales = []
        combos_groups = []

        # Loop over number of available ADC channels which is 8.
        # Make combobox for channel type, edit for name and label for physical channel number
        for i in range(self.n_channels):
            # Channel RO scale combobox
            _cbx_scale = QtWidgets.QComboBox()
            _cbx_scale.addItems(list(_ro_scales.keys()))
            _cbx_scale.setToolTip('Select RO scale for each channel individually.')
            _cbx_scale.setCurrentIndex(combo_scale.currentIndex())

            # Channel RO group combobox
            _cbx_group = QtWidgets.QComboBox()
            _cbx_group.addItems(['sem', 'ch12'])
            _cbx_group.setToolTip('Select R/O board channel group individually.')

            # Channel type combobox
            _cbx_type = QtWidgets.QComboBox()
            _cbx_type.addItems(daq_config['adc_channels'])
            _cbx_type.setToolTip('Select type of readout channel. If not None, this info is used for interpretation.')
            _cbx_type.setCurrentIndex(i if i < len(self.default_channels) else daq_config['adc_channels'].index('none'))

            # Reference channel to measure voltage; can be GND or any of the other channels
            _cbx_ref = QtWidgets.QComboBox()
            _cbx_ref.addItems(['GND'] + [str(k) for k in range(1, self.n_channels + 1) if k != i + 1])
            _cbx_ref.setCurrentIndex(0)
            _cbx_ref.setProperty('lastitem', 'GND')
            _cbx_ref.currentTextChanged.connect(lambda item, c=_cbx_ref: self._handle_ref_channels(item, c))

            # Channel name edit
            _edit = QtWidgets.QLineEdit()
            _edit.setPlaceholderText('Not used')
            _edit.textChanged.connect(lambda text, cbx=_cbx_scale, checkbox=checkbox_scale: cbx.setEnabled(checkbox.isChecked() and (True if text else False)))
            _edit.textChanged.connect(lambda text, cbx=_cbx_type: cbx.setEnabled(True if text else False))
            _edit.textChanged.connect(lambda text, cbx=_cbx_ref: cbx.setEnabled(True if text else False))
            _edit.setText('' if i > len(self.default_channels) - 1 else self.default_channels[i])

            # Connections between RO scale combos
            checkbox_scale.stateChanged.connect(lambda state, cbx=_cbx_scale, edit=_edit: cbx.setEnabled(bool(state) if edit.text() else False))
            checkbox_scale.stateChanged.connect(lambda _, cbx=_cbx_scale, combo=combo_scale: cbx.setCurrentIndex(combo.currentIndex()))
            combo_scale.currentIndexChanged.connect(lambda idx, cbx=_cbx_scale, checkbox=checkbox_scale:
                                                    cbx.setCurrentIndex(idx if not checkbox.isChecked() else cbx.currentIndex()))

            # Disable widgets with no default channels at first
            _cbx_scale.setEnabled(False)
            _cbx_type.setEnabled(_edit.text() != '')
            _cbx_ref.setEnabled(_edit.text() != '')

            # Append to list
            edits.append(_edit)
            combos_types.append(_cbx_type)
            combos_refs.append(_cbx_ref)
            combos_scales.append(_cbx_scale)
            combos_groups.append(_cbx_group)

            # Add to layout
            self.add_widget(widget=[QtWidgets.QLabel('{}.'.format(i + 1)), _edit, _cbx_scale, _cbx_group, _cbx_type, _cbx_ref])

        # Store all input related widgets in dict
        self.widgets['scale_combo'] = combo_scale
        self.widgets['scale_combos'] = combos_scales
        self.widgets['group_combos'] = combos_groups
        self.widgets['type_combos'] = combos_types
        self.widgets['ref_combos'] = combos_refs
        self.widgets['channel_edits'] = edits
        self.widgets['srate_combo'] = combo_srate
        self.widgets['scale_chbx'] = checkbox_scale

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
            self.widgets['channel_edits'][last_idx].setPlaceholderText('None')

            for rcbx in self.widgets['ref_combos']:
                if cbx != rcbx:
                    for i in range(rcbx.count()):
                        if rcbx.itemText(i) == str(last_idx + 1) or (idx is None and rcbx.itemText(i) == str(sender_idx)):
                            rcbx.model().item(i).setEnabled(True)