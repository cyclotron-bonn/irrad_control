import time
import telnetlib
import logging
from irrad_control.devices.stage.base_axis import BaseAxis


class ItemTelnetClient(object):

    cr_lf_token = b'\r\n'
    ok_token = b'200 OK'

    def __init__(self, host, port, timeout=1):

        # Open telnet connection
        self._client = telnetlib.Telnet(host=host, port=port, timeout=timeout)

        time.sleep(1)

        attempts = 0
        while attempts < 10:
            self._send('')
            if self._recv_until_CRLF() == self.ok_token:
                break
            attempts += 1

    def _send(self, msg):
        logging.debug('Raw message sent: {}'.format(msg))
        self._client.write(bytes(msg) + self.cr_lf_token)

    def _recv(self):

        raw_reply = b''

        # Read from connection until empty
        part = self._client.read_very_eager()
        while part:
            raw_reply += part
            part = self._client.read_very_eager()

        logging.debug('Raw reply received: {}'.format(raw_reply))

        return raw_reply

    def _recv_until_CRLF(self):
        return self._client.read_until(self.cr_lf_token, timeout=self._client.timeout).rstrip()

    def send_cmd(self, cmd, data=None):

        # Build command string
        cmd_str = str(cmd) + '' if data is None else ' '

        # data has more tha one field
        if isinstance(data, (tuple, list)):
            cmd_str += ' '.join(str(a) for a in data)
        else:
            cmd_str += str(data) if data is not None else ''

        logging.debug('Attempting to send command: {}'.format(cmd_str))

        self._send(msg=cmd_str)

    def recv_reply(self, return_status=False):

        status, reply = self._recv_until_CRLF(), self._recv_until_CRLF()

        if status != self.ok_token and status:
            logging.error("Command not succeeded with status {}; instead {}".format(self.ok_token, status))

        return reply if return_status is False else status

    def recv_multiple_replies(self):

        replies = []

        next_reply = self.recv_reply()
        while next_reply:
            replies.append(next_reply)
            next_reply = self.recv_reply()

        return replies


class ItemLinearStage(BaseAxis):
    
    def __init__(self):
        super(ItemLinearStage, self).__init__(init_props=('position'))
    
    def convert_from_unit(self, value, unit):
        pass
    
    def convert_to_unit(self, value, unit):
        pass
