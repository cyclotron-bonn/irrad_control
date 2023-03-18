from PyQt5 import QtWidgets
from time import strftime, gmtime


class EventWidget(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setLayout(QtWidgets.QVBoxLayout())

        self.event_display = QtWidgets.QPlainTextEdit()
        self.event_display.setReadOnly(True)

        self.mute_checkbox = QtWidgets.QCheckBox(text="Mute event sound")

        self.layout().addWidget(self.mute_checkbox)
        self.layout().addWidget(self.event_display)

    def _play_notify_sound(self):
        if not self.mute_checkbox.isChecked():
            QtWidgets.QApplication.beep()


    def register_event(self, event_dict):

        if event_dict['active']:
            self._play_notify_sound()

        status = 'active' if event_dict['active'] else 'inactive'
        status_color = 'red' if event_dict['active'] else 'green'
        
        html_event = f"""
        <html>
          <body>
            {strftime("%d/%m/%Y %H:%M:%S", gmtime())} | {event_dict['server']} | {event_dict["event"]}(<font color = {status_color})>{status}</font> | {event_dict['description']}
          </body
        </html>
        """

        self.event_display.appendHtml(html_event) 
