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
        self._init_info_boxes()


    def _init_info_boxes(self):
        pass


    def _init_buttons(self):
        test_label = QtWidgets.QLabel('TEST')

        channel_boxes = [QtWidgets.QCheckBox('channel' + str(n)) for n in range(16)]
        transmit_state_button = QtWidgets.QPushButton('send set state')
        transmit_state_button.clicked.connect(lambda _: self.transmit_state(channel_boxes))
        self.add_widget(widget=[test_label])
        self.add_widget(widget=channel_boxes)
        self.add_widget(transmit_state_button)


    def transmit_state(self, check_boxes):
        for i in range(len(check_boxes)):
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
