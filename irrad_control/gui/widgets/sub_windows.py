import yaml
import time
import logging
from PyQt5 import QtWidgets, QtCore
from .util_widgets import GridContainer, NoBackgroundScrollArea


class XYStagePositionWindow(QtWidgets.QMainWindow):
    """Sub window for adding and editing known stage positions"""

    stagePosChanged = QtCore.pyqtSignal(dict)

    def __init__(self, positions, parent=None):
        super(XYStagePositionWindow, self).__init__(parent)

        self.positions = positions

        self.positions_buffer = {}

        self.are_you_sure = True

        self._init_ui()

    def _init_ui(self):

        self.setWindowTitle('Add / edit XY-Stage positions')
        # Make this window blocking parent window
        self.setWindowModality(QtCore.Qt.ApplicationModal)
        self.screen = QtWidgets.QDesktopWidget().screenGeometry()
        self.resize(0.5 * self.screen.width(), 0.5 * self.screen.height())

        # Main widget
        self.main_widget = QtWidgets.QWidget()
        self.main_widget.setLayout(QtWidgets.QVBoxLayout())
        self.setCentralWidget(self.main_widget)

        self._init_edit_pos()
        self._init_add_position()
        self._init_buttons()

        if self.positions:
            for name in self.positions:
                tmp_pos = self.positions[name]
                self.add_position(name=name, x_pos=tmp_pos['x'], y_pos=tmp_pos['y'], unit=tmp_pos['unit'], date=tmp_pos['date'], saved=True)

    def _init_edit_pos(self):

        def get_h_line():
            h_line = QtWidgets.QFrame()
            h_line.setFrameShape(QtWidgets.QFrame.HLine)
            h_line.setFrameShadow(QtWidgets.QFrame.Sunken)
            return h_line

        # Add containers for known positions and one for adding new ones
        self.edit_pos = GridContainer(name='Edit positions')
        self.edit_pos.grid.setAlignment(QtCore.Qt.AlignTop)

        # make column names
        cols = ('Name', 'Position', '', 'Date', 'Status', 'Delete')

        self.edit_pos.add_widget(widget=[QtWidgets.QLabel(col) for col in cols])
        self.edit_pos.add_widget(widget=[get_h_line() for _ in cols])

        # Make scroll widget and set widget
        scroll = NoBackgroundScrollArea()
        scroll.setWidget(self.edit_pos)

        self.main_widget.layout().addWidget(scroll)

    def _init_add_position(self):

        self.add_pos = GridContainer(name='Add position')

        # Name
        name_edit = QtWidgets.QLineEdit()
        name_edit.setPlaceholderText('Name the position')
        # x position
        spx_x = QtWidgets.QDoubleSpinBox()
        spx_x.setPrefix('x: ')
        spx_x.setDecimals(3)
        spx_x.setMinimum(0.0)
        spx_x.setMaximum(300.0)
        spx_x.setSuffix(' {}'.format('mm'))
        # x position
        spx_y = QtWidgets.QDoubleSpinBox()
        spx_y.setPrefix('y: ')
        spx_y.setDecimals(3)
        spx_y.setMinimum(0.0)
        spx_y.setMaximum(300.0)
        spx_y.setSuffix(' {}'.format('mm'))
        # button add
        btn_add = QtWidgets.QPushButton('Add')
        btn_add.setEnabled(False)
        # Make connections
        name_edit.textChanged.connect(lambda text, b=btn_add: btn_add.setEnabled(text not in self.positions_buffer and text != ""))
        btn_add.clicked.connect(lambda _, n=name_edit, x=spx_x, y=spx_y: self.add_position(n.text(), x.value(), y.value(), 'mm', time.asctime()))
        btn_add.clicked.connect(lambda _, n=name_edit: n.setText(""))
        btn_add.clicked.connect(lambda _, x=spx_x, y=spx_y: (x.setValue(x.minimum()), y.setValue(y.minimum())))
        btn_add.clicked.connect(lambda _: self.btn_save.setEnabled(self._check_edit()))

        self.add_pos.add_widget((QtWidgets.QLabel('Name:'), name_edit, spx_x, spx_y, btn_add))
        self.main_widget.layout().addWidget(self.add_pos)

    def _init_buttons(self):

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch(1)
        self.btn_cancel = QtWidgets.QPushButton('Close / Cancel')
        self.btn_save = QtWidgets.QPushButton('Apply')
        self.btn_save.clicked.connect(self._edit)
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(lambda _: self.btn_save.setEnabled(self._check_edit()))
        self.btn_cancel.clicked.connect(self.close)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)

        self.main_widget.layout().addLayout(btn_layout)

    def add_position(self, name, x_pos, y_pos, unit, date=None, saved=True):
        """Method to create a set of widgets to allow setting position and name """

        if name not in self.positions_buffer:
            self.positions_buffer[name] = {'x': x_pos, 'y': y_pos, 'unit': unit, 'date': date if date is not None else time.asctime(), 'delete': False}

            # x position
            spx_x = QtWidgets.QDoubleSpinBox()
            spx_x.setPrefix('x: ')
            spx_x.setDecimals(3)
            spx_x.setMinimum(0.0)
            spx_x.setMaximum(300.0)
            spx_x.setValue(x_pos)
            spx_x.setSuffix(' {}'.format(unit))
            spx_x.valueChanged.connect(lambda val: self.positions_buffer[name].update({'x': val}))
            spx_x.valueChanged.connect(lambda _: self.btn_save.setEnabled(self._check_edit()))

            # y value
            spx_y = QtWidgets.QDoubleSpinBox()
            spx_y.setPrefix('y: ')
            spx_y.setDecimals(3)
            spx_y.setMinimum(0.0)
            spx_y.setMaximum(300.0)
            spx_y.setValue(y_pos)
            spx_y.setSuffix(' {}'.format(unit))
            spx_y.valueChanged.connect(lambda val: self.positions_buffer[name].update({'y': val}))
            spx_y.valueChanged.connect(lambda _: self.btn_save.setEnabled(self._check_edit()))

            label_status = QtWidgets.QLabel('Saved' if saved else 'Not saved')

            if not saved:
                label_status.setStyleSheet('QLabel {color: orange;}')

            # Delete checkboxes
            chbx_del = QtWidgets.QCheckBox('Delete {}'.format(name))

            _widgets = [QtWidgets.QLabel(name),
                        spx_x,
                        spx_y,
                        QtWidgets.QLabel("Last updated: {}".format(date if date is not None else time.asctime())),
                        label_status,
                        chbx_del]

            chbx_del.stateChanged.connect(lambda state: self.positions_buffer[name].update({'delete': bool(state)}))
            chbx_del.stateChanged.connect(lambda _: self.btn_save.setEnabled(self._check_edit()))

            for w in _widgets[:-1]:
                chbx_del.stateChanged.connect(lambda state, widget=w: self.add_pos.set_widget_read_only(widget, read_only=bool(state)))

            self.edit_pos.widgets[name] = _widgets
            self.edit_pos.add_widget(widget=self.edit_pos.widgets[name])

    def _check_edit(self):
        """Function to check whether entries in the xy_positions will be edited"""

        # If we're deleting stuff, there will be an edit
        if any(self.positions_buffer[k]['delete'] for k in self.positions_buffer):
            return True

        # If we're adding stuff, there will be an edit
        if len(self.positions) != len(self.positions_buffer):
            return True

        # If we're changing values, there will be an edit
        for kk in self.positions:

            # Check if anything in the buffer is different; if yes, we want to edit
            for prop in self.positions[kk]:
                if self.positions_buffer[kk][prop] != self.positions[kk][prop]:
                    return True

        return False

    def _edit(self):
        """Edit the position entries in our config"""

        if self.are_you_sure:
            cb = QtWidgets.QCheckBox("Don't ask me again during this session")
            cb.stateChanged.connect(lambda state: setattr(self, 'are_you_sure', not bool(state)))
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

        for k in self.positions_buffer:

            # If its in the aim dict, we're editing or removing
            if k in self.positions:

                # Check if we're removing
                if self.positions_buffer[k]['delete']:
                    remove.append(k)
                # We're editing
                else:
                    for kk in self.positions_buffer[k]:
                        if kk != 'delete':
                            self.positions[k][kk] = self.positions_buffer[k][kk]

            # If not, we're adding
            else:
                self.positions[k] = dict([(kkk, self.positions_buffer[k][kkk]) for kkk in self.positions_buffer[k] if kkk != 'delete'])

        for r in remove:
            self.edit_pos.remove_widget(self.edit_pos.widgets[r])
            del self.positions[r]
            del self.positions_buffer[r]
            del self.edit_pos.widgets[r]

        self.stagePosChanged.emit(self.positions)

    def close(self):

        r = [k for k in self.positions_buffer if k not in self.positions]
        for k in r:
            self.edit_pos.remove_widget(self.edit_pos.widgets[k])
            del self.positions_buffer[k]
            del self.edit_pos.widgets[k]

        # TODO: write delete position func
        # TODO: make visible that position is not yet added if apply is not hit via color
        # TODO add btn to get current position

        super(XYStagePositionWindow, self).close()
