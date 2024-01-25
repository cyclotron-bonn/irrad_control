import logging
import time
from PyQt6 import QtWidgets, QtCore, QtGui
from collections import defaultdict
from irrad_control.gui.widgets.util_widgets import GridContainer, NoBackgroundScrollArea
from irrad_control.devices import DEVICES_CONFIG

# TODO add btn to get current position
# TODO: Load stage positions from local config file on demand


class MotorstagePositionWindow(QtWidgets.QMainWindow):
    """Sub window for adding and editing known motorstage positions"""

    motorstagePosAdded = QtCore.pyqtSignal(str, dict)
    motorstagePosRemoved = QtCore.pyqtSignal(str, list)
    motorstagePosChanged = QtCore.pyqtSignal(str, dict)

    def __init__(self, parent=None):
        super(MotorstagePositionWindow, self).__init__(parent)

        self.positions = defaultdict(dict)

        self._positions_buffer = defaultdict(dict)

        self._ms_widgets = {}

        self._ms_spnbxs = {}

        self._containers = defaultdict(dict)

        self._are_you_sure = True

        self._edit_initiated = {}

        self._init_ui()

        # Connections
        for x in [lambda idx: self.btn_save.setText(f'Save {self.tabs.tabText(idx)} changes'),
                  lambda idx: self.btn_save.setEnabled(self._check_edit(motorstage=self.tabs.tabText(idx)))]:
            self.tabs.currentChanged.connect(x)

    def _init_ui(self):

        self.setWindowTitle('Add / edit motorstage positions')
        # Make this window blocking parent window
        self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        self.screen = QtGui.QGuiApplication.primaryScreen().availableGeometry()
        self.resize(int(0.5 * self.screen.width()), int(0.5 * self.screen.height()))

        # Main widget
        self.main_widget = QtWidgets.QWidget()
        self.main_widget.setLayout(QtWidgets.QVBoxLayout())
        self.setCentralWidget(self.main_widget)

        # Tab widget
        self.tabs = QtWidgets.QTabWidget()
        self.main_widget.layout().addWidget(self.tabs)

        # Buttons to apply /cancel save
        self._init_buttons()

    def _init_buttons(self):

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch(1)
        self.btn_cancel = QtWidgets.QPushButton('Close / Cancel')
        self.btn_save = QtWidgets.QPushButton('Save')
        self.btn_save.clicked.connect(lambda _: self._init_edit(motorstage=self.tabs.tabText(self.tabs.currentIndex()), interactive=True))
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(lambda _: self.btn_save.setEnabled(self._check_edit(motorstage=self.tabs.tabText(self.tabs.currentIndex()))))
        self.btn_cancel.clicked.connect(self.close)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)

        self.main_widget.layout().addLayout(btn_layout)

    def _add_motorstage(self, motorstage, travel_range, unit='mm'):

        if motorstage not in self._ms_widgets:

            def get_h_line():
                h_line = QtWidgets.QFrame()
                h_line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
                h_line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
                return h_line

            self._edit_initiated[motorstage] = False

            # Check if we only have single axis
            travel_range = travel_range if isinstance(travel_range[0], list) else [travel_range]

            # Make column names
            cols = ('Name', 'Position') + (len(travel_range) - 1) * ('',) + ('Date', 'Status', 'Delete')

            # Config is dict with axis id as key; start with axis 0
            axes = range(len(travel_range))

            # Make widget and layout
            ms_widget = QtWidgets.QWidget()
            ms_widget.setLayout(QtWidgets.QVBoxLayout())

            # Make scroll widget and set widget
            scroll = NoBackgroundScrollArea()
            scroll.setWidget(ms_widget)

            # Add containers for known positions and one for adding new ones
            self._containers[motorstage]['pos'] = GridContainer(name='Edit positions')
            self._containers[motorstage]['pos'].grid.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
            self._containers[motorstage]['pos'].add_widget(widget=[QtWidgets.QLabel(col) for col in cols])
            self._containers[motorstage]['pos'].add_widget(widget=[get_h_line() for _ in cols])

            # Name
            name_edit = QtWidgets.QLineEdit()
            name_edit.setPlaceholderText('Name of position')

            btn_add = QtWidgets.QPushButton('Add')
            btn_add.setEnabled(False)

            # Make connections
            name_edit.textChanged.connect(lambda text, b=btn_add: btn_add.setEnabled(text not in self._positions_buffer[motorstage] and text != ""))

            self._ms_spnbxs[motorstage] = []
            # Loop over axes
            for ax in axes:
                spx = QtWidgets.QDoubleSpinBox()
                spx.setPrefix(f'Axis {ax}: ')
                spx.setSuffix(f" {unit if unit else ' mm'}")
                spx.setDecimals(3)
                if travel_range[ax] is not None:
                    spx.setMinimum(travel_range[ax][0])
                    spx.setMaximum(travel_range[ax][-1])
                self._ms_spnbxs[motorstage].append(spx)

            # Add position to widget
            btn_add.clicked.connect(lambda _, m=motorstage, n=name_edit, u=unit: self._add_position(motorstage=m,
                                                                                                    name=n.text(),
                                                                                                    coordinates=[spx.value() for spx in self._ms_spnbxs[m]],
                                                                                                    unit=u,
                                                                                                    date=time.asctime()))

            btn_add.clicked.connect(lambda _, n=name_edit: n.setText(""))  # Reset name for next addition
            btn_add.clicked.connect(lambda _, m=motorstage: [_s.setValue(_s.minimum()) for _s in self._ms_spnbxs[m]])  # Reset values for next addition
            btn_add.clicked.connect(lambda _: self.btn_save.setEnabled(self._check_edit(motorstage=self.tabs.tabText(self.tabs.currentIndex()))))  # Check if we can enable

            self._containers[motorstage]['add'] = GridContainer(name='Add position')
            self._containers[motorstage]['add'].add_widget(widget=[QtWidgets.QLabel('Name:'), name_edit] + self._ms_spnbxs[motorstage] + [btn_add])

            ms_widget.layout().addWidget(self._containers[motorstage]['pos'])
            ms_widget.layout().addWidget(self._containers[motorstage]['add'])

            self._ms_widgets[motorstage] = ms_widget
            self.tabs.addTab(scroll, motorstage)

    def _add_position(self, motorstage, name, coordinates, unit, date=None, saved=False):
        """Method to create a set of widgets to allow setting position and name """

        if name not in self._positions_buffer[motorstage]:

            coordinates = coordinates if isinstance(coordinates, list) else [coordinates]
            date = date if date is not None else time.asctime()

            if len(coordinates) == 1:
                # Buffer original position when added
                self._positions_buffer[motorstage][name] = {'value': coordinates[0], 'unit': unit, 'date': date if date is not None else time.asctime(), 'delete': False}
            else:
                self._positions_buffer[motorstage][name] = {'value': coordinates, 'unit': unit, 'date': date if date is not None else time.asctime(), 'delete': False}

            def _update_pos(val, axis, ms, psname):
                if isinstance(self._positions_buffer[ms][psname]['value'], list):
                    self._positions_buffer[ms][psname]['value'][axis] = val
                else:
                    self._positions_buffer[ms][psname]['value'] = val

            # Make spinboxes for position
            spxs = []
            for i in range(len(coordinates)):
                spx = QtWidgets.QDoubleSpinBox()
                spx.setPrefix(f'Axis {i}: ')
                spx.setSuffix(f' {unit}')
                spx.setDecimals(3)
                spx.setMinimum(self._ms_spnbxs[motorstage][i].minimum())
                spx.setMaximum(self._ms_spnbxs[motorstage][i].maximum())
                spx.setValue(coordinates[i])
                spx.wheelEvent = lambda e: None  # Disable wheel event
                spx.valueChanged.connect(lambda val, axis=i: _update_pos(val=val, axis=axis, ms=motorstage, psname=name))
                spx.valueChanged.connect(lambda _: self.btn_save.setEnabled(self._check_edit(motorstage=self.tabs.tabText(self.tabs.currentIndex()))))
                spxs.append(spx)

            label_status = QtWidgets.QLabel('Saved' if saved else 'Not saved')
            label_status.setStyleSheet('QLabel {color: green;}' if saved else 'QLabel {color: orange;}')

            # Delete checkboxes
            chbx_del = QtWidgets.QCheckBox('Delete {}'.format(name))

            _widgets = [QtWidgets.QLabel(name)] + spxs + [QtWidgets.QLabel("Last updated: {}".format(date)),
                                                          label_status,
                                                          chbx_del]

            chbx_del.stateChanged.connect(lambda state: self._positions_buffer[motorstage][name].update({'delete': bool(state)}))
            chbx_del.stateChanged.connect(lambda _: self.btn_save.setEnabled(self._check_edit(motorstage=self.tabs.tabText(self.tabs.currentIndex()))))

            for w in _widgets[:-1]:
                chbx_del.stateChanged.connect(lambda state, m=motorstage, _w=w: self._containers[m]['add'].set_widget_read_only(_w, read_only=bool(state)))

            self._containers[motorstage]['pos'].widgets[name] = _widgets
            self._containers[motorstage]['pos'].add_widget(widget=_widgets)

    def _check_edit(self, motorstage):
        """Function to check whether entries in the motorstage positions will be edited"""

        # If we're deleting stuff, there will be an edit
        if any(self._positions_buffer[motorstage][n]['delete'] for n in self._positions_buffer[motorstage]):
            return True

        # If we're adding stuff, there will be an edit
        if len(self.positions[motorstage]) != len(self._positions_buffer[motorstage]):
            return True

        # If we're changing values, there will be an edit
        for p in self.positions[motorstage]:
            # Check if anything in the buffer is different; if yes, we want to edit
            for prop in self.positions[motorstage][p]:
                if self._positions_buffer[motorstage][p][prop] != self.positions[motorstage][p][prop]:
                    return True

        return False

    def _init_edit(self, motorstage, interactive=False):
        """Emit signals to edit the position entries of *motorstage*"""

        if interactive and self._are_you_sure:
            cb = QtWidgets.QCheckBox("Don't ask me again during this session")
            cb.stateChanged.connect(lambda state: setattr(self, '_are_you_sure', not bool(state)))
            mbox = QtWidgets.QMessageBox()
            mbox.setCheckBox(cb)
            mbox.setWindowTitle("Apply changes?")
            mbox.setText("Are you sure you want to apply changes? Changes are written to the {} configuration file".format(motorstage))
            mbox.addButton(QtWidgets.QMessageBox.StandardButton.Yes)
            mbox.addButton(QtWidgets.QMessageBox.StandardButton.Cancel)

            if mbox.exec() == QtWidgets.QMessageBox.StandardButton.Yes:
                self.statusBar().showMessage('Apply changes...', 4000)
            else:
                self.statusBar().showMessage('Cancel', 2000)
                return

        remove = []
        add = {}

        # Loop over buffer
        for p in self._positions_buffer[motorstage]:

            # If its in the aim dict, we're editing or removing
            if p in self.positions[motorstage]:

                # Check if we're removing
                if self._positions_buffer[motorstage][p]['delete']:
                    remove.append(p)
                # We're editing
                else:
                    add[p] = {k: v for k, v in self._positions_buffer[motorstage][p].items() if k != 'delete'}

            # If not, we're adding
            else:
                add[p] = {k: v for k, v in self._positions_buffer[motorstage][p].items() if k != 'delete'}

        if remove:
            self.motorstagePosRemoved.emit(motorstage, remove)
        
        if add:
            self.motorstagePosAdded.emit(motorstage, add)

        self._edit_initiated[motorstage] = True

    def add_motorstage(self, motorstage, positions, properties):
        """Get everything from motorstage configuration"""

        # We have multiple axes
        if 'n_axis' in DEVICES_CONFIG[motorstage]['init']:
            self._add_motorstage(motorstage=motorstage, travel_range=[p['range'] for p in properties], unit='mm')

        # We have only one axis
        else:
            self._add_motorstage(motorstage=motorstage, travel_range=properties['range'], unit='mm')
            
        # Add motorstage positions
        for pos_name, pos in positions.items():
            self.positions[motorstage][pos_name] = {'value': pos['value'], 'unit': pos['unit'], 'date': pos['date']}
            self._add_position(motorstage=motorstage,
                                name=pos_name,
                                coordinates=pos['value'],
                                unit=pos['unit'],
                                date=pos['date'],
                                saved=True)

        self._init_edit(motorstage=motorstage)

    def validate(self, motorstage, positions, validate):
        """
        Validates addition/update or removal of a motorstage position by looking at feedback from server that controls the motorstage

        Parameters
        ----------
        motorstage: str
            name of the motorstage (must be in self._positions_buffer[motorstage])
        positions: dict
            dict of position(s) that the motorstage has after the command
        validate: str:
            operation to validate; either *add* for addiation/update or *remove* for removal
        """

        # Check if the motorstage has more than one axis

        if validate == 'remove':

            # These should not exist
            remove = [name for name, pos in self._positions_buffer[motorstage].items() if pos['delete']]

            # Buffer should have all the positions, check that the right ones were deleted
            if any(pos in positions for pos in remove):
                logging.error(f"Position deletion unsuccessful")
                return
                
            for pos in remove:
                self._containers[motorstage]['pos'].remove_widget(self._containers[motorstage]['pos'].widgets[pos])
                del self.positions[motorstage][pos]
                del self._positions_buffer[motorstage][pos]
                del self._containers[motorstage]['pos'].widgets[pos]

        elif validate == 'add':

            # Loop over buffer and check if positions are the same; if so add to self.positions
            for name, pos in positions.items():
                buffer_pos = self._positions_buffer[motorstage]
                # Check for multi axis
                check = all(buffer_pos[name][entry] == pos[entry] for entry in pos)
                
                if check:
                    self.positions[motorstage][name] = {k: v for k, v in buffer_pos[name].items() if k != 'delete'}
                    self._containers[motorstage]['pos'].widgets[name][-2].setStyleSheet('QLabel {color: green;}')
                    self._containers[motorstage]['pos'].widgets[name][-2].setText('Saved')
                else:
                    logging.error(f"Postion {name} returned from server and in buffer are different")
        else:
            logging.info(f"Unknown validation '{validate}'")
            return

        self.motorstagePosChanged.emit(motorstage, self.positions[motorstage])
        self._edit_initiated[motorstage] = False

    def close(self):

        for m in self._positions_buffer:
            r = [k for k in self._positions_buffer[m] if k not in self.positions[m] and not self._edit_initiated[m]]
            for k in r:
                self._containers[m]['pos'].remove_widget(self._containers[m]['pos'].widgets[k])
                del self._positions_buffer[m][k]
                del self._containers[m]['pos'].widgets[k]

        super(MotorstagePositionWindow, self).close()
