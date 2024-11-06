from PyQt5 import QtWidgets, QtCore
from collections import defaultdict

from irrad_control.devices import DEVICES_CONFIG
from irrad_control.gui.widgets import GridContainer, NoWheelQComboBox
from irrad_control.gui.utils import fill_combobox_items
from irrad_control.utils.events import create_irrad_events
from irrad_control.gui.widgets.control_widgets import ControlWidget

import logging


class ArduinoMuxWidget(ControlWidget):
    def __init__(self, server, parent=None):
        self.server = server
        super(ArduinoMuxWidget, self).__init__(name='Arduino Mux widget', parent=parent, enable=True)


    def _init_widget(self):
        #self.tabs = QtWidgets.QTabWidget()
        self._init_buttons()
        #self._init_info_boxes()


    def _init_info_boxes(self):
        pass

    def activate_transmit(self):
        self.transmit_state_button.setEnabled(True)


    def _init_buttons(self):
#        channel_boxes = [QtWidgets.QCheckBox('channel ' + str(n)) for n in range(1, 17)]
        self.channel_boxes = [QtWidgets.QPushButton('channel ' + str(n)) for n in range(1, 17)]

        style = """QPushButton {
            background-color: grey;
        }
        QPushButton:checked {
            background-color: red;
        }"""

        for i in range(len(self.channel_boxes)):
            self.channel_boxes[i].setCheckable(True)
            self.channel_boxes[i].setFixedSize(80, 60)
            self.channel_boxes[i].setStyleSheet(style)
            self.channel_boxes[i].clicked.connect(self.activate_transmit)

        label_con1 = QtWidgets.QLineEdit('Connector 1')
        label_con1.setAlignment(QtCore.Qt.AlignCenter)
        label_con1.setReadOnly(True)
        label_con2 = QtWidgets.QLineEdit('Connector 2')
        label_con2.setAlignment(QtCore.Qt.AlignCenter)
        label_con2.setReadOnly(True)

        con1_box = QtWidgets.QGridLayout()
        #con1_box.setSpacing(2)
        con2_box = QtWidgets.QGridLayout()
        #con2_box.setSpacing(2)

        con1_box.addWidget(label_con1, 0, 0, 1, 2)
        con2_box.addWidget(label_con2, 0, 0, 1, 2)

        for i in range(4):
            con1_box.addWidget(self.channel_boxes[i], i + 1, 0)
            con1_box.addWidget(self.channel_boxes[i + 4], i + 1, 1)

            con2_box.addWidget(self.channel_boxes[i + 8], i + 1, 0)
            con2_box.addWidget(self.channel_boxes[i + 4 + 8], i + 1, 1)

        self.transmit_state_button = QtWidgets.QPushButton('send set state')
        self.transmit_state_button.clicked.connect(lambda _: self.transmit_state(self.channel_boxes))

        meta_box = QtWidgets.QHBoxLayout()
        meta_box.addLayout(con1_box)
        meta_box.addLayout(con2_box)

        self.add_widget(meta_box)
        self.add_widget(self.transmit_state_button)


    def transmit_state(self, check_boxes):
        self.transmit_state_button.setEnabled(False)
        for i in range(len(check_boxes)):
            print(str(i) + ' ' + str(check_boxes[i].isChecked()))
            self.set_channel(i, check_boxes[i].isChecked())


    def set_channel(self, channel, state):
        if state:
            self.send_cmd(hostname=self.server,
                      target='ArduinoMUX',
                      cmd='_enable_channel',
                      cmd_data={'kwargs': {'channel': channel}}
            )
        else:
            self.send_cmd(hostname=self.server,
                        target='ArduinoMUX',
                        cmd='_disable_channel',
                        cmd_data={'kwargs': {'channel': channel}}
            )
