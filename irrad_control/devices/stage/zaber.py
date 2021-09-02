import logging
from zaber.serial import AsciiDevice, AsciiSerial

# Package imports
from .base_axis import BaseAxis, base_axis_config_updater, load_base_axis_config, save_base_axis_config


class ZaberStepAxis(BaseAxis):
    """Base-class representing basic functionality of a Zaber motorstage with a stepper motor"""

    def __init__(self, port, dev_addr=1, step=0.49609375e-6, travel=300e-3, model='X-XY-LRQ300BL-E01', config=None):

        super(ZaberStepAxis, self).__init__(config=config, native_unit='step')

        # If we are not already connected to a serial port, open one
        if not isinstance(port, AsciiSerial):
            port = AsciiSerial(port)

        # Create a device with the given address
        self.device = AsciiDevice(port, dev_addr)

        # Create an axis representing the device
        self.axis = self.device.axis(1)

        # Whether the axis is inverted
        self.invert_axis = False

        # Model specific attributes
        self.model = model
        self.microstep = step  # meter
        self.travel = travel  # meter
        self.travel_microsteps = int(self.travel / self.microstep)

    @staticmethod
    def _check_reply(reply):
        """Method to check the reply of a command which has been issued to one of the axes"""

        # Get reply data and corresponding axis
        msg = "Axis {}: {}".format(reply.device_address, reply.data)

        # Flags are either 'OK' or 'RJ'
        if reply.reply_flag != 'OK':
            logging.error("Command rejected by {}".format(msg))
            return False

        # Use logging to debug
        logging.debug("Command succeeded: {}".format(msg))
        return True

    def _send_cmd(self, cmd):
        """Sends ASCII command to axis and checks the reply"""

        reply = self.axis.send(cmd)

        self.error = False if self._check_reply(reply) else reply.data

        return reply

    def _convert(self, value, unit, to_native=False):
        """
        Converts between native and physical units. For more info see:
        https://www.zaber.com/protocol-manual?device=X-LRQ300BL-E01&peripheral=N%2FA&version=7.15&protocol=ASCII#topic_physical_units

        Parameters
        ----------
        value: float, int
            Numerical value to/from which is converted
        unit: str
            Unit from/to which is converted; must be in sel.units
        to_native: bool
            Whether or not to convert to the native unit

        Returns
        -------
            int, float
        """

        if unit in self.units[self._dist]:
            factor = self.microstep

        elif unit in self.units[self._speed]:
            factor = self.microstep / 1.6384

        elif unit in self.units[self._accel]:
            factor = self.microstep / 1.6384e-4

        elif to_native and unit is None:
            return int(value)

        else:
            raise ValueError("Could not convert value {} {} unit {}".format(value, 'from' if to_native else 'to', unit))

        # Determine factor wrt whether we go to or from physical unit
        factor **= (-1.0 if to_native else 1.0)

        # Scale the result between unit prefixes
        factor *= self.unit_scale[unit.split('/')[0]] ** (1.0 if to_native else -1.0)

        # Calculate result
        res = factor * value

        # Return result in native units as int or physical unit float
        return int(res) if to_native else float(res)

    def convert_to_unit(self, value, unit):
        """See self._convert"""
        return self._convert(value, unit)

    def convert_from_unit(self, value, unit):
        """See self._convert"""
        return self._convert(value, unit, to_native=True)

    def get_position(self, unit=None):
        """
        Returns the current position of the XY-stage in given unit

        unit : str, None
            unit in which range is given. Must be in self.dist_units. If None, set speed in steps
        """

        # Get position
        pos = self.axis.get_position()

        # Axis is inverted
        if self.invert_axis:
            pos = self.travel_microsteps - pos

        # Convert to *unit* if needed
        return pos if unit is None else self.convert_to_unit(pos, unit)

    @base_axis_config_updater
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

        # If unit is given, get speed in steps
        speed = value if unit is None else self.convert_from_unit(value, unit)

        # https://www.zaber.com/protocol-manual?device=X-LRQ300BL-E01&peripheral=N%2FA&version=7.15&protocol=ASCII#topic_setting_maxspeed
        max_speed = int(self._send_cmd("get resolution").data) * 16384

        # Check whether speed is not larger than *max_speed*
        if not (1 <= speed <= max_speed):
            msg = "Maximum speed of this axis is {} mm/s. Speed not updated!".format(self.convert_to_unit(max_speed, 'mm/s'))
            logging.warning(msg)
            return

        self._send_cmd("set maxspeed {}".format(speed))

    def get_speed(self, unit=None):
        """
        Get the speed at which axis moves for move rel and move abs commands

        Parameters
        ----------
        unit : str, None
            unit in which speed should be converted. Must be in self.speed_units. If None, return speed in steps / s
        """

        # Issue command and wait for reply and check
        _reply = self._send_cmd("get maxspeed")

        # Get speed in steps per second; 0 if command didn't succeed
        speed = 0 if self.error else int(_reply.data)

        return speed if unit is None else self.convert_to_unit(speed, unit)

    @base_axis_config_updater
    def set_range(self, value, unit=None):
        """
        Set the speed at which axis moves for move rel and move abs commands

        Parameters
        ----------
        value : iterable
            range to be set, must be of len 2
        unit : str, None
            unit in which range is given. Must be in self.dist_units. If None, set speed in steps
        """

        if len(value) != 2:
            logging.warning("Range must be 2-element iterable containing lower and upper limit. Abort")
            return

        if self.invert_axis:
            value = [self.travel_microsteps - v for v in reversed(value)]

        for i, lim in enumerate(('min', 'max')):
            self._send_cmd("set limit.{} {}".format(lim, value[i] if unit is None else self.convert_from_unit(value[i], unit)))

    def get_range(self, unit=None):
        """
        Get the travel range of axis

        Parameters
        ----------
        unit : str, None
            unit in which range should be converted. Must be in self.dist_units. If None, return speed in steps
        """

        # Issue command and wait for reply and check
        _range = []
        for i, lim in enumerate(('min', 'max')):
            _reply = self._send_cmd("get limit.{}".format(lim))
            _range.append(0 if self.error else int(_reply.data))

        if self.invert_axis:
            _range = [self.travel_microsteps - r for r in reversed(_range)]

        return _range if unit is None else [self.convert_to_unit(r, unit) for r in _range]

    @base_axis_config_updater
    def set_accel(self, value, unit=None):
        """
        Set the acceleration at which the axis increases speed for move rel and move abs commands

        Parameters
        ----------
        value : float, int
            acceleration; float if *unit* is given, else integer in steps
        unit : str, None
            unit in which distance is given. Must be in self.dist_units. If None, get acceleration in steps / s^2
        """

        # If unit is given, get acceleration in steps
        accel = value if unit is None else self.convert_from_unit(value, unit)

        max_accel = 32767

        # Check whether speed is not larger than maxspeed
        if accel > max_accel:
            msg = "Maximum acceleration of this axis is {} m/s^2." \
                  "Acceleration not updated!".format(self.convert_to_unit(max_accel, 'm/s^2'))
            logging.warning(msg)
            return

        self._send_cmd("set accel {}".format(accel))

    def get_accel(self, unit=None):
        """
        Get the acceleration at which the axis increases speed for move rel and move abs commands

        Parameters
        ----------
        unit : str, None
            unit in which acceleration should be converted. Must be in self.accel_units.
            If None, get acceleration in steps / s^2
        """

        # Issue command and wait for reply and check
        _reply = self._send_cmd("get accel")

        # Get acceleration in steps per square second; 0 if command didn't succeed
        accel = 0 if self.error else int(_reply.data)

        return accel if unit is None else self.convert_to_unit(accel, unit)

    def _check_move(self, value):
        """Checks whether the target *value* is within the axis range"""

        # Get minimum and maximum steps of travel
        min_native, max_native = self.get_range()

        # Check whether there's still room to move
        if not (min_native <= value <= max_native):
            logging.error("Movement out of travel range. Abort!")
            return False

        return True and not self.error

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

        if self.invert_axis:
            target = self.travel_microsteps - target if absolute else target * (-1)

        # Do sanity check whether movement is within axis range and move
        if self._check_move(value=target if absolute else target + self.get_position()):
            self._send_cmd("move {} {}".format('abs' if absolute else 'rel', target))

            # Block until movement is finished if wanted
            if self.blocking:
                self.axis.poll_until_idle()

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

    def stop(self, emergency=False):
        """
        Stops current movement by decelerating until hold. I *emergency* is True, shut off driver current
        for immediate halt.

        Parameters
        ----------
        emergency: bool
            whether to shut off the driver current
        """
        self._send_cmd('stop' if not emergency else 'estop')
        self.config['position']['value'] = self.get_position(unit=self.config['position']['unit'])


class ZaberMultiAxis(object):
    """Implements a multi-axis Zaber motorstage"""

    def __init__(self, n_axis, port='/dev/ttyUSB0', dev_addrs=None, config=None, invert_axis=None):

        # Holding the axis objects
        self.axis = []

        self._dev_addrs = [i+1 for i in range(n_axis)] if dev_addrs is None else dev_addrs

        # Initialize the zaber device
        if not isinstance(port, AsciiSerial):
            port = AsciiSerial(port)

        self.config = load_base_axis_config(config=config)

        # Initialize axes
        for a in range(n_axis):
            self.axis.append(ZaberStepAxis(port=port, addr=self._dev_addrs[a],
                                           config=None if config is None else self.config[a]))

        if invert_axis:
            for axis in invert_axis:
                self.axis[axis].invert_axis = True

    def home_stage(self):
        """Send all axis to their lower limit"""
        for axis in reversed(self.axis):
            axis.move_abs(axis.config['range']['value'][0], unit=axis.config['range']['unit'])

    def move_to_position(self, pos=None, unit=None, name=None):
        """
        Method which moves the stage to a given position: Position can either be defined by giving *x* and *y* values
        with a *unit* or a *name*. If a *name* is given, it must be contained in the self.config['positions']. If a
        a name as well as x and y values are given, the name is prioritized.

        Parameters
        ----------
        pos: iterable
            position given in *unit*
        unit: str, None
             string of unit to use. Must be in self.dist_units. If None, x and y must be integers and the unit is interpreted as steps
        name: str
            name of position in self.config['positions'] to travel to
        """

        if name is None and pos is None:
            raise ValueError("Either the 'pos' arguments or the name of the position have to be given")

        if len(self.axis) != len(pos):
            raise ValueError("Number of axis does not match given position")

        for i, axis in self.axis:
            # If we're moving to an already known position
            if name is not None:
                axis.move_pos(name=name)
            else:
                axis.move_abs(value=pos[i], unit=unit)

    def add_position(self, name, unit, pos=None, date=None):
        """
        Method which stores new XY stage position in the config. If it already exists in self.config['positions'], the entries are updated

        Parameters
        ----------
        name: str
            name of the position
        pos: iterable, None
            iterable of position, if None, call get position
        unit: str
            string of metric unit
        date: str, None
            if None, will be return value of time.asctime()
        """

        for i, axis in enumerate(self.axis):
            axis.add_position(name=name, value=axis.get_position(unit) if pos is None else pos[i], unit=unit, date=date)

    def remove_position(self, name):
        """
        Method which removes an existing XY stage position from self.config['positions']

        Parameters
        ----------
        name: str
            name of the position
        """

        for i, axis in enumerate(self.axis):
            axis.remove_position(name=name)

    def save_config(self):
        """
        Method save the content of self.config aka irrad_control.XX_stage_config to the respective config yaml (overwriting it).
        This method get's called inside the instances' destructor.
        """
        save_base_axis_config(config=self.config)
