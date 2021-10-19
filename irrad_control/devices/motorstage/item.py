import time
import telnetlib
import logging

# Package imports
from .base_axis import BaseAxis, base_axis_config_updater


class ItemTelnetClient(object):

    # Byte tokens
    cr_lf_token = '\r\n'

    # String tokens
    ok_token = 'OK'
    async_token = '!!'

    def __init__(self, host, port, timeout=1):

        self.port = port
        self.host = host
        self.error = False

        # Open telnet connection
        self._client = telnetlib.Telnet(host=host, port=port, timeout=timeout)

        # Allow connections to be made
        time.sleep(1)

        # try to connect
        self._establish_connection()

    def _establish_connection(self):

        # Send dummy bytes
        self.send('')

        # Receive all initial garbage and throw it into gc
        _ = self.recv_all()

        # Send dummy bytes again and receive OK
        reply = self.send_and_recv('')

        # Receive all initial garbage and throw it into gc
        _ = self.recv_all()

        if reply.split()[-1] != self.ok_token:
            raise ValueError('Connection could not be established')

    def send(self, msg):

        # Apparently needed to discard unwanted additional messages from server
        _ = self.recv_all()

        _msg = bytes(msg + self.cr_lf_token, encoding='utf-8')
        logging.debug('Raw message sent: {}'.format(_msg))
        self._client.write(_msg)

    def recv(self):
        reply = self._client.read_until(bytes(self.cr_lf_token, encoding='utf-8'), timeout=self._client.timeout).rstrip()
        logging.debug('Raw reply received: {}'.format(reply))
        return str(reply, encoding='utf-8')

    def _check_msg_reply(self, msg, reply):

        # Separate into actual data and the return status
        try:
            actual_reply, status = reply.split()

            # Get HTTP status
            if actual_reply.startswith(self.async_token):
                https_state = actual_reply.split(':')[-1]
            else:
                https_state = actual_reply.split()[0]

            if status != self.ok_token:
                self.error = True
                logging.error("Command {} to server unsuccessful: received HTTP status {}".format(msg, https_state))
            else:
                self.error = False
                logging.debug("Command {} to server successful: received HTTP status {}".format(msg, https_state))

        except ValueError:
            pass

    def send_and_recv(self, msg):

        self.send(msg)
        reply = self.recv()
        self._check_msg_reply(msg, reply)

        return reply

    def send_and_recv_multiple(self, msg):

        self.send(msg)
        reply = self.recv_multiple()
        self._check_msg_reply(msg, reply[0])

        return reply

    def recv_all(self):

        raw_reply = b''

        # Read from connection until empty
        part = self._client.read_very_eager()
        while part:
            raw_reply += part
            part = self._client.read_very_eager()

        logging.debug('Raw reply received: {}'.format(raw_reply))

        return str(raw_reply, encoding='utf-8')

    def send_cmd(self, cmd, data=None, single_reply=True):

        # Build command string
        cmd_str = str(cmd)

        # data has more than one field
        if isinstance(data, (tuple, list)):
            cmd_str += ' ' + ' '.join(str(a) for a in data)
        elif data is not None:
            cmd_str += ' ' + str(data)

        logging.debug(cmd_str)

        return self.send_and_recv(msg=cmd_str) if single_reply else self.send_and_recv_multiple(msg=cmd_str)

    def recv_multiple(self):

        replies = []

        next_reply = self.recv()
        while next_reply:
            replies.append(next_reply)
            next_reply = self.recv()

        return replies


class ItemLinearStage(BaseAxis):

    props = {'position': 'POSACTUAL'}

    def __init__(self, host, port, udp, travel=716.5e-3, config=None):

        self.udp = udp

        # Init client
        self.item_client = ItemTelnetClient(host=host, port=port)

        # Login stage
        self.item_client.send_cmd(cmd='LOGIN Stage Hochstromraum')

        # Connect to udp
        self.item_client.send_cmd(cmd='CONNECT udp', data=udp)

        self.controller_id = self.get_id()

        self.travel = travel  # meter

        super(ItemLinearStage, self).__init__(config=config, native_unit='mm')

    def _get_property(self, prop):

        reply = self.item_client.send_cmd(cmd='GET', data=[self.controller_id, prop])
        prop_value = reply.split(':')[-1]

        try:
            res = float(prop_value)
            if res.is_integer():
                res = int(res)
        except ValueError:
            res = prop_value

        return 0 if self.item_client.error else res

    def _set_enabled(self, state=True):
        self.item_client.send_cmd(cmd='{} {}'.format('ENABLE' if state else 'DISABLE', self.controller_id))

    def _check_move(self, value):
        """Checks whether the target *value* is within the axis range"""

        # Get minimum and maximum steps of travel
        min_native, max_native = self.get_range()

        # Check whether there's still room to move
        if not (min_native <= value <= max_native):
            logging.error("Movement out of travel range. Abort!")
            return False

        return True and not self.error

    def _convert(self, value, unit, to_native=False):
        """
        Converts between native and physical units. Item native unit is mm

        Parameters
        ----------
        value: float, int
            Numerical value to/from which is converted
        unit: str
            Unit from/to which is converted; must be in self.units
        to_native: bool
            Whether or not to convert to the native unit

        Returns
        -------
            int, float
        """
        return value * (1e3 * self.unit_scale[unit.split('/')[0]]) ** (1.0 if to_native else -1.0)

    def convert_to_unit(self, value, unit):
        """See self._convert"""
        return self._convert(value, unit)

    def convert_from_unit(self, value, unit):
        """See self._convert"""
        return self._convert(value, unit, to_native=True)

    def enable(self):
        self._set_enabled(True)

    def disable(self):
        self._set_enabled(False)

    def get_id(self):
        stage_id = self.item_client.send_and_recv_multiple(msg='LIST')[-1]
        return int(stage_id)

    def get_position(self, unit=None):
        """
        Returns the current position of the XY-stage in given unit

        unit : str, None
            unit in which range is given. Must be in self.dist_units. If None, set speed in steps
        """

        # Get position
        pos = self._get_property(self.props['position'])

        # Convert to *unit* if needed
        return pos if unit is None else self.convert_to_unit(pos, unit)

    def get_speed(self, unit=None):
        """
        Get the speed at which axis moves for move rel and move abs commands

        Parameters
        ----------
        unit : str, None
            unit in which speed should be converted. Must be in self.speed_units. If None, return speed in steps / s
        """

        speed, speed_unit = (self.config['axis']['speed'][v] for v in ('value', 'unit'))

        speed_mm = self.convert_from_unit(speed, speed_unit)

        return speed_mm if unit is None else self.convert_to_unit(speed_mm, unit)

    def set_speed(self, value, unit=None):
        """
        Set the speed at which axis moves for move rel and move abs commands

        Parameters
        ----------
        value : float, int
            speed at which *axis* should move
        unit : str, None
            unit in which speed is given. Must be in self.speed_units. If None, set speed in steps / s
        """
        self.config['axis']['speed'].update({'value': value, 'unit': unit})

    def get_range(self, unit=None):
        """
        Get the travel range of axis

        Parameters
        ----------
        unit : str, None
            unit in which range should be converted. Must be in self.dist_units. If None, return speed in steps
        """

        _range, range_unit = (self.config['axis']['range'][v] for v in ('value', 'unit'))

        _range_mm = [self.convert_from_unit(r_m, range_unit) for r_m in _range]

        return _range_mm if unit is None else [self.convert_to_unit(r, unit) for r in _range]

    def set_range(self, value, unit=None):
        """
        Set the speed at which axis moves for move rel and move abs commands

        Parameters
        ----------
        value : float, int
            speed at which *axis* should move
        unit : str, None
            unit in which speed is given. Must be in self.speed_units. If None, set speed in steps / s
        """
        self.config['axis']['range'].update({'value': value, 'unit': unit})

    def get_accel(self, unit=None):
        """
        Get the acceleration at which the axis increases speed for move rel and move abs commands

        Parameters
        ----------
        unit : str, None
            unit in which acceleration should be converted. Must be in self.accel_units.
            If None, get acceleration in steps / s^2
        """

        accel, accel_unit = (self.config['axis']['accel'][v] for v in ('value', 'unit'))

        accel_mms2 = self.convert_from_unit(accel, accel_unit)

        return accel_mms2 if unit is None else self.convert_to_unit(accel_mms2, unit)

    def set_accel(self, value, unit=None):
        """
        Set the speed at which axis moves for move rel and move abs commands

        Parameters
        ----------
        value : float, int
            speed at which *axis* should move
        unit : str, None
            unit in which speed is given. Must be in self.speed_units. If None, set speed in steps / s
        """
        self.config['axis']['accel'].update({'value': value, 'unit': unit})

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

        actual_move = lambda t: self.item_client.send_cmd(cmd='MOVETOMM', data=[self.controller_id,
                                                                                t,
                                                                                int(self.get_speed()),
                                                                                int(self.get_accel())])

        # Get target of travel in mm
        target = value if unit is None else self.convert_from_unit(value, unit)

        # Make absolute vs rel travel by hand
        target = target if absolute else target + self.get_position()

        # Do sanity check whether movement is within axis range and move
        if self._check_move(value=target):

            if self.blocking:
                # Enable for movement
                self.enable()
                # Start moving
                actual_move(t=target)
                # While stage moves, block
                while self._get_property('SPEEDACTUAL') != 0:
                    time.sleep(0.1)
                # Disable stage
                self.disable()
            else:
                actual_move(t=target)

    @base_axis_config_updater
    def move_rel(self, value, unit=None):
        """ See self._move """

        self._move(value, unit, absolute=False)

    @base_axis_config_updater
    def move_abs(self, value, unit=None):
        """ See self._move """

        self._move(value, unit, absolute=True)

    def move_pos(self, name):
        """
        Method which moves the stage to a given position: Position can either be defined by giving *x* and *y* values
        with a *unit* or a *name*. If a *name* is given, it must be contained in the self.config['axis']['positions']. If a
        a name as well as x and y values are given, the name is prioritized.

        Parameters
        ----------
        name: str
            name of position in self.config['axis']['positions'] to travel to
        """
        # Check if position is in config
        if name not in self.config['axis']['positions']:
            raise KeyError("Position '{}' not in known position: {}".format(name, ', '.join(n for n in self.config['axis']['positions'])))

        # Get values
        pos, unit = (self.config['axis']['positions'][name][v] for v in ('value', 'unit'))

        # Do the movement
        self.move_abs(pos, unit)

    def stop(self):
        """Stop any movement"""
        self.disable()
        self.config['axis']['position']['value'] = self.get_position(unit=self.config['axis']['position']['unit'])
