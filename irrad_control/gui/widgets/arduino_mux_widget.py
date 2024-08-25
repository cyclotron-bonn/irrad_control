from PyQt5 import QtWidgets, QtCore
from collections import defaultdict

from irrad_control.devices import DEVICES_CONFIG
from irrad_control.gui.widgets import GridContainer, NoWheelQComboBox
from irrad_control.gui.utils import fill_combobox_items
from irrad_control.utils.events import create_irrad_events
from irrad_control.gui.widgets.control_widgets import ControlWidget

import logging

def transmit_state(state, sender):
    for i in range(len(state)):
        sender(i, state[i].isChecked())


class ArduinoMuxWidget(ControlWidget):
    def __init__(self, server, parent=None):
        self.server = server
        super(ArduinoMuxWidget, self).__init__(name='Arduino Mux widget', parent=parent)


    def _init_widget(self):
        #self.tabs = QtWidgets.QTabWidget()
        self._init_buttons()


    def _init_buttons(self):
        test_label = QtWidgets.QLabel('TEST')

        channel_boxes = [QtWidgets.QCheckBox('channel' + str(n)) for n in range(16)]
        transmit_state_button = QtWidgets.QPushButton('send set state')
        transmit_state_button.clicked.connect(lambda _: transmit_state(channel_boxes, self.set_channel))
        self.add_widget(widget=[test_label])
        self.add_widget(widget=channel_boxes)
        self.add_widget(transmit_state_button)


    def set_channel(self, channel, state):
        if state:
            self.send_cmd(hostname=self.server,
                      target='ArduinoMUX',
                      cmd='_enable_channel',
                      cmd_data={'kwd_args': {'channel': channel}})
        else:
            self.send_cmd(hostname=self.server,
                        target='ArduinoMUX',
                        cmd='_disable_channel',
                        cmd_data={'kwd_args': {'channel': channel}})
