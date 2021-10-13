import time
from PyQt5 import QtWidgets, QtCore
from collections import defaultdict
from .util_widgets import GridContainer, NoBackgroundScrollArea


class MotorstagePositionWindow(QtWidgets.QMainWindow):
    """Sub window for adding and editing known motorstage positions"""

    motorstagePosChanged = QtCore.pyqtSignal(dict)

    def __init__(self, motorstages=None, positions=None, parent=None):
        super(MotorstagePositionWindow, self).__init__(parent)

        self.motorstages = motorstages

        self.positions = positions if positions is not None else defaultdict(dict)

        self._positions_buffer = defaultdict(dict)

        self._ms_widgets = {}

        self._ms_spnbxs = {}

        self._containers = defaultdict(dict)

        self._are_you_sure = True

        self._init_ui()

    def _init_ui(self):

        self.setWindowTitle('Add / edit motorstage positions')
        # Make this window blocking parent window
        self.setWindowModality(QtCore.Qt.ApplicationModal)
        self.screen = QtWidgets.QDesktopWidget().screenGeometry()
        self.resize(0.5 * self.screen.width(), 0.5 * self.screen.height())

        # Main widget
        self.main_widget = QtWidgets.QWidget()
        self.main_widget.setLayout(QtWidgets.QVBoxLayout())
        self.setCentralWidget(self.main_widget)

        # Tab widget
        self.tabs = QtWidgets.QTabWidget()
        self.main_widget.layout().addWidget(self.tabs)

        # Buttons to apply /cancel save
        self._init_buttons()

        #if self.positions:
        #    for ms in self.positions:
        #        self.add_motorstage(motorstage=ms, travel_range=self.po)
        #        tmp_pos = self.positions[name]
        #        self.add_position(name=name, x_pos=tmp_pos['x'], y_pos=tmp_pos['y'], unit=tmp_pos['unit'], date=tmp_pos['date'], saved=True)

    def _init_buttons(self):

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch(1)
        self.btn_cancel = QtWidgets.QPushButton('Close / Cancel')
        self.btn_save = QtWidgets.QPushButton('Apply')
        self.btn_save.clicked.connect(self._edit(motorstage=self.tabs.tabText(self.tabs.currentIndex())))
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(lambda _: self.btn_save.setEnabled(self._check_edit(motorstage=self.tabs.tabText(self.tabs.currentIndex()))))
        self.btn_cancel.clicked.connect(self.close)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)

        self.main_widget.layout().addLayout(btn_layout)

    def add_motorstage(self, motorstage, travel_range, unit='mm'):

        if motorstage not in self._ms_widgets:

            def get_h_line():
                h_line = QtWidgets.QFrame()
                h_line.setFrameShape(QtWidgets.QFrame.HLine)
                h_line.setFrameShadow(QtWidgets.QFrame.Sunken)
                return h_line

            # Make column names
            cols = ('Name', 'Position', '', 'Date', 'Status', 'Delete')

            # Config is dict with axis id as key; start with axis 0
            axes = sorted(travel_range.keys())

            # Make widget and layout
            ms_widget = QtWidgets.QWidget()
            ms_widget.setLayout(QtWidgets.QVBoxLayout())

            # Make scroll widget and set widget
            scroll = NoBackgroundScrollArea()
            scroll.setWidget(ms_widget)

            # Add containers for known positions and one for adding new ones
            self._containers[motorstage]['pos'] = GridContainer(name='Edit positions')
            self._containers[motorstage]['pos'].grid.setAlignment(QtCore.Qt.AlignTop)
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
                spx.setPrefix(f'Axis {ax}')
                spx.setSuffix(f' {unit}')
                spx.setDecimals(3)
                spx.setMinimum(travel_range[ax][0])
                spx.setMaximum(travel_range[ax][-1])
                spx.wheelEvent = lambda e: None  # Disable wheel event
                self._ms_spnbxs[motorstage].append(spx)

            # Add position to widget
            btn_add.clicked.connect(lambda _, m=motorstage, n=name_edit: self.add_position(motorstage=m,
                                                                                           name=n.text(),
                                                                                           axes_positions=[spx.value() for spx in self._ms_spnbxs[m]],
                                                                                           unit=unit,
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

    def add_position(self, motorstage, name, axes_positions, unit, date=None, saved=True):
        """Method to create a set of widgets to allow setting position and name """

        if name not in self._positions_buffer[motorstage]:
            # Buffer original position when added
            self._positions_buffer[motorstage][name] = {**{i: axes_positions[i] for i in range(len(axes_positions))},
                                                        **{'unit': unit, 'date': date if date is not None else time.asctime(), 'delete': False}}
            # Make spinboxes for position
            spxs = []
            for i in range(len(axes_positions)):
                spx = QtWidgets.QDoubleSpinBox()
                spx.setPrefix(f'Axis {i}')
                spx.setSuffix(f' {unit}')
                spx.setDecimals(3)
                spx.setMinimum(self._ms_spnbxs[motorstage].minimum())
                spx.setMaximum(self._ms_spnbxs[motorstage].maximum())
                spx.setValue(axes_positions[i])
                spx.wheelEvent = lambda e: None  # Disable wheel event
                spx.valueChanged.connect(lambda val, axis=i: self._positions_buffer[motorstage][name].update({axis: val}))
                spx.valueChanged.connect(lambda _: self.btn_save.setEnabled(self._check_edit(motorstage=self.tabs.tabText(self.tabs.currentIndex()))))
                spxs.append(spx)

            label_status = QtWidgets.QLabel('Saved' if saved else 'Not saved')

            if not saved:
                label_status.setStyleSheet('QLabel {color: orange;}')

            # Delete checkboxes
            chbx_del = QtWidgets.QCheckBox('Delete {}'.format(name))

            _widgets = [QtWidgets.QLabel(name)] + spxs + [QtWidgets.QLabel("Last updated: {}".format(self._positions_buffer[motorstage][name]['date'])),
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
                if self.positions_buffer[motorstage][p][prop] != self.positions[motorstage][p][prop]:
                    return True

        return False

    def _edit(self, motorstage):
        """Edit the position entries of *motorstage* in our config"""

        if self._are_you_sure:
            cb = QtWidgets.QCheckBox("Don't ask me again during this session")
            cb.stateChanged.connect(lambda state: setattr(self, '_are_you_sure', not bool(state)))
            mbox = QtWidgets.QMessageBox()
            mbox.setCheckBox(cb)
            mbox.setWindowTitle("Write changes to file?")
            mbox.setText("Are you sure you want to write changes to XY-Stage config file?")
            mbox.addButton(QtWidgets.QMessageBox.Yes)
            mbox.addButton(QtWidgets.QMessageBox.Cancel)

            if mbox.exec_() == QtWidgets.QMessageBox.Yes:
                self.statusBar().showMessage('Write changes...', 4000)
            else:
                self.statusBar().showMessage('Aborted. No changes written to file', 4000)
                return

        remove = []
        for p in self._positions_buffer[motorstage]:

            # If its in the aim dict, we're editing or removing
            if p in self.positions[motorstage]:

                # Check if we're removing
                if self._positions_buffer[motorstage][p]['delete']:
                    remove.append(p)
                # We're editing
                else:
                    for k in self.positions_buffer[motorstage][p]:
                        if k != 'delete':
                            self.positions[motorstage][p][k] = self.positions_buffer[motorstage][p][k]

            # If not, we're adding
            else:
                self.positions[motorstage][p] = {k: self._positions_buffer[motorstage][p][k] for k in self._positions_buffer[motorstage][p] if k != 'delete'}

        for p in remove:
            self._containers[motorstage]['pos'].remove(self._containers[motorstage]['pos'].widgets[p])
            del self.positions[motorstage][p]
            del self._positions_buffer[motorstage][p]
            del self._containers[motorstage]['pos'].widgets[p]

        self.motorstagePosChanged.emit({motorstage: self.positions[motorstage]})

    def close(self):

        for m in self._positions_buffer:
            r = [k for k in self.positions_buffer[m] if k not in self.positions[m]]
            for k in r:
                self._containers[m]['pos'].remove_widget(self._containers[m]['pos'].widgets[k])
                del self._positions_buffer[m][k]
                del self._containers[m]['pos'].widgets[k]

        # TODO: write delete position func
        # TODO: make visible that position is not yet added if apply is not hit via color
        # TODO add btn to get current position

        super(MotorstagePositionWindow, self).close()
