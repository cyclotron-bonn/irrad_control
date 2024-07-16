from PyQt5 import QtWidgets, QtCore
from collections import defaultdict

from irrad_control.devices import DEVICES_CONFIG
from irrad_control.gui.widgets import GridContainer, NoWheelQComboBox
from irrad_control.gui.utils import fill_combobox_items
from irrad_control.utils.events import create_irrad_events
from irrad_control.gui.widgets.control_widgets import ControlWidget

class ArduinoMuxWidget(ControlWidget):
    def __init__(self, server, parent=None):
        self.server = server
        super(ArduinoMuxWidget, self).__init__(name='Arduino Mux widget', parent=parent)


    def _init_widget(self):
        self.tabs = QtWidgets.QTabWidget()
        self._init_buttons()
        self.add_widget(self.tabs)


    def _init_buttons(self):
        # TODO: make 16 checkboxes in two groups
        transmit_state_button = QtWidgets.QPushButton('send set state')
        transmit_state_button.clicked.connect(lambda _: None) # TODO: implement actuall cmd

        channel_boxes = [QtWidgets.QCheckBox('channel' + str(n)) for n in range(16)]
