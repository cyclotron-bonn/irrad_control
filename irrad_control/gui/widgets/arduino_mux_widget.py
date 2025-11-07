from PyQt5 import QtWidgets, QtCore
from irrad_control.gui.widgets.control_widgets import ControlWidget


class ArduinoMuxWidget(ControlWidget):
    def __init__(self, server, parent=None):
        self.server = server
        self.internal_state = None
        super(ArduinoMuxWidget, self).__init__(name='Arduino Mux widget', parent=parent, enable=True)

    def _init_widget(self):
        self._init_buttons()

    def activate_transmit(self):
        button_states = [b.isChecked() for b in self.channel_boxes]
        if self.internal_state != button_states :
            self.transmit_state_button.setEnabled(True)
        else:
            self.transmit_state_button.setEnabled(False)

    def _init_buttons(self):
        self.channel_boxes = [QtWidgets.QPushButton('channel ' + str(n)) for n in range(1, 17)]

        style = """QPushButton {
            background-color: grey;
        }
        QPushButton:checked {
            background-color: red;
        }"""

        for i in range(len(self.channel_boxes)):
            self.channel_boxes[i].setCheckable(True)
            self.channel_boxes[i].setFixedSize(80, 40)
            self.channel_boxes[i].setStyleSheet(style)
            self.channel_boxes[i].clicked.connect(self.activate_transmit)

        label_con1 = QtWidgets.QLineEdit('Connector 1')
        label_con1.setAlignment(QtCore.Qt.AlignCenter)
        label_con1.setReadOnly(True)

        label_con2 = QtWidgets.QLineEdit('Connector 2')
        label_con2.setAlignment(QtCore.Qt.AlignCenter)
        label_con2.setReadOnly(True)

        con1_box = QtWidgets.QGridLayout()
        con2_box = QtWidgets.QGridLayout()

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

        rename_button = QtWidgets.QPushButton('rename channels')
        rename_button.clicked.connect(self.input_dialog)

        self.add_widget(meta_box)
        self.add_widget(self.transmit_state_button)
        self.add_widget(rename_button)


    def rename_channel_buttons(self, naming_string):
        for line in naming_string.split('\n'):
            try:
                num = int(line.split(":")[0])
                name = "".join(line.split(":")[1:])
                self.channel_boxes[num - 1].setText(name)
            except:
                pass


    def input_dialog(self):
        filename , ok = QtWidgets.QFileDialog.getOpenFileName(self, 'Select channel file','channel: name')
        if ok:
            with open(filename) as file:
                text = file.read()
                self.rename_channel_buttons(text)


    def transmit_state(self, check_boxes):
        self.transmit_state_button.setEnabled(False)
        self.internal_state = [b.isChecked() for b in self.channel_boxes]
        for i in range(len(check_boxes)):
            print(str(i) + ' ' + str(check_boxes[i].isChecked()))
            self.set_channel(i, check_boxes[i].isChecked())


    def set_channel(self, channel, state):
        if state:
            self.send_cmd(hostname=self.server,
                      target='ArduinoMUX',
                      cmd='enable_channel',
                      cmd_data={'kwargs': {'channel': channel}}
            )
        else:
            self.send_cmd(hostname=self.server,
                        target='ArduinoMUX',
                        cmd='disable_channel',
                        cmd_data={'kwargs': {'channel': channel}}
            )
