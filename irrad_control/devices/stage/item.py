import time
import telnetlib
import logging

# Package imports
from .base_axis import BaseAxis


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
    
    def __init__(self, host, port):
        super(ItemLinearStage, self).__init__(init_props=('position', 'speed', 'accel'))

        self.client = ItemTelnetClient(host=host, port=port)
        self.controller_id = None
    
    def convert_from_unit(self, value, unit):
        pass

    def _get_property(self, prop):

        return self._send_cmd('GET {cntrllr_id} {prop}'.format(cntrllr_id=self.controller_id,
                                                               prop=prop))
    
    def convert_to_unit(self, value, unit):
        pass

    def get_position(self, unit=None):
        """
        Returns the current position of the XY-stage in given unit

        unit : str, None
            unit in which range is given. Must be in self.dist_units. If None, set speed in steps
        """

        # Get position
        pos = self._get_property('POS')

        # Convert to *unit* if needed
        return pos if unit is None else self.convert_to_unit(pos, unit)

    def _move(self, value, unit, absolute=True):
        """
        Method to move the axis either to an absolute position *value* or relative by *value* to the current position.
        Unit can be None (a.k.a the native unit) or in *self.units[self._dist]*. Does sanity check on travel destination

        Parameters
        ----------
        value : float, int
            distance of relative/absolute travel
        unit : None, str
            unit in which target is given. Must be in self.dist_units. If None, interpret as steps
        """

        # Get target of travel in steps
        target = value if unit is None else self.convert_from_unit(value, unit)

        # Do sanity check whether movement is within axis range and move
        self._send_cmd("MOVETO {cntrllr_id} {pos} {speed} {accel} {mode}".format(cntrllr_id=self.controller_id,
                                                                                 pos=target,
                                                                                 speed=self.get_speed(unit=unit),
                                                                                 accel=self.get_accel(unit=unit),
                                                                                 mode='A' if absolute else 'R'))

    @BaseAxis.update_config(entry='position')
    def move_rel(self, value, unit=None):
        """ See self._move """

        self._move(value, unit, absolute=False)

    @BaseAxis.update_config(entry='position')
    def move_abs(self, value, unit=None):
        """ See self._move """

        self._move(value, unit, absolute=True)

    def move_pos(self, name):
        """
        Method which moves the stage to a given position: Position can either be defined by giving *x* and *y* values
        with a *unit* or a *name*. If a *name* is given, it must be contained in the self.config['positions']. If a
        a name as well as x and y values are given, the name is prioritized.

        Parameters
        ----------
        name: str
            name of position in self.config['positions'] to travel to
        """
        # Check if position is in config
        if name not in self.config['positions']:
            raise KeyError("Position '{}' not in known position: {}".format(name, ', '.join(n for n in self.config['positions'])))

        # Get values
        pos, unit = (self.config['positions'][name][v] for v in ('value', 'unit'))

        # Do the movement
        self.move_abs(pos, unit)
