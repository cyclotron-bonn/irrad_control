import logging
import time
from os.path import isfile
from functools import wraps
from types import MethodType
from threading import get_ident

# Package imports
from irrad_control import axis_config
from irrad_control.utils.utils import create_pub_from_ctx
from irrad_control.utils.tools import save_yaml, load_yaml


def load_base_axis_config(config):

    if config is not None:
        if isinstance(config, dict):
            return config
        elif isfile(config):
            return load_yaml(config)
    else:
        return axis_config


def base_axis_config_updater(base_axis_func):
    """Decorator which wraps around a function which changes the axis configuration such as each *set* method"""

    @wraps(base_axis_func)
    def wrapper(instance, value, unit):

        res = base_axis_func(instance, value, unit)

        if not instance.error:
            prop = base_axis_func.__name__.split('_')[-1]
            if any(p in base_axis_func.__name__.lower() for p in ('move', 'stop')):
                instance.config['position'].update({'value': instance.get_position(unit=unit), 'unit': unit})
            elif instance.hasattr('get_{}'.format(prop)):
                instance.config[prop].update({'value': getattr(instance, 'get_{}'.format(prop))(unit=unit), 'unit': unit})
            else:
                raise KeyError("Property {} not in instances config: {}".format(prop, ', '.join(instance.config.key())))

            instance.config['last_updated'] = time.asctime()

        return res

    return wrapper


def base_axis_movement_tracker(axis_movement_func, axis_id, zmq_config, axis_domain=None):
    """
    Decorator function which is used keep track of the stage travel. Optionally publishes movement data via ZMQ.

    Parameters
    ----------
    axis_movement_func: function object
        function which executes an axis movement
    axis_id: int
        Identifier for this axis under which the data is published
    zmq_config: dict
        dict containing needed zmq objects to publish axis movement data
    Returns
    -------
    movement_wrapper: function object
        wrapped movement_func
    """

    @wraps(axis_movement_func)
    def movement_wrapper(axis, value, unit):

        _axis_key = id(axis)

        # PUB thread and current thread are not the same; need to create new socket
        if zmq_config['axis_pubs'][_axis_key]['thread_id'] != get_ident():
            zmq_config['axis_pubs'][_axis_key]['pub'] = create_pub_from_ctx(ctx=zmq_config['ctx'],
                                                                            addr=zmq_config['addr'])
            zmq_config['axis_pubs'][_axis_key]['thread_id'] = get_ident()

        # Get starting position of movement in native unit
        start = axis.convert_from_unit(**axis.config['position'])

        # Publish collection of data from which movement can be predicted
        _meta = {'timestamp': time.time(), 'name': zmq_config['sender'], 'type': 'axis'}
        _data = {'status': 'move_start', 'axis': axis_id, 'axis_domain': axis_domain}
        _data.update({prop: axis.config[prop] for prop in axis.init_props})

        # Publish data
        zmq_config['axis_pubs'][_axis_key]['pub'].send_json({'meta': _meta, 'data': _data})

        # Execute movement
        reply = axis_movement_func(value, unit)

        # Get position after movement
        stop = axis.convert_from_unit(**axis.config['position'])

        # Calculate distance travelled in native unit
        travel = abs(stop - start)

        # Publish collection of data from which movement can be predicted
        _meta = {'timestamp': time.time(), 'name': zmq_config['sender'], 'type': 'axis'}
        _data = {'status': 'move_stop', 'axis': axis_id, 'axis_domain': axis_domain,
                 'travel': axis.convert_to_unit(travel, unit), 'unit': unit}

        # Publish data
        zmq_config['axis_pubs'][_axis_key]['pub'].send_json({'meta': _meta, 'data': _data})

        if axis.config['travel']['unit'] is not None:
            tot_travel = axis.convert_to_unit(travel, unit=axis.config['travel']['unit'])
        else:
            tot_travel = axis.convert_from_unit(travel, unit=axis.config['travel']['unit'])

        axis.config['travel']['value'] += tot_travel
        axis.config['last_updated'] = time.asctime()

        return reply

    return movement_wrapper


class BaseAxis(object):
    """
    Base class of a single motor stage represented by a movable point on a one dimensional axis. The main attributes of a motor stage are:
    """

    def __init__(self, config=None, native_unit=None, init_props=('position', 'speed', 'accel', 'range')):

        # Axis configuration; holds physical properties such as movement speed, acceleration, etc.
        self.config = load_base_axis_config(config=config)

        self._dist, self._accel, self._speed = 'distance', 'speed', 'acceleration'

        # Dimensions of physical properties
        self.unit_scale = {'m': 1e0, 'cm': 1e-2, 'mm': 1e-3}
        self.units = {self._dist: ('m', 'cm', 'mm'),
                      self._speed: ('m/s', 'cm/s', 'mm/s'),
                      self._accel: ('m/s^2', 'cm/s^2', 'mm/s^2')}

        self.native_unit = native_unit

        self.error = None

        self.blocking = True

        self.init_props = init_props

        if self.config:
            self._apply_config()

    def _read_config(self, base_unit='mm'):

        for prop in self.init_props:
            _unit = ('{}/s' if prop == 'speed' else '{}/s^2' if prop == 'accel' else '{}').format(base_unit)
            self.config[prop].update({'value': getattr(self, 'get_{}'.format(prop))(_unit), 'unit': _unit})

    def _apply_config(self):

        for prop in self.init_props:
            # Don't set the position; we don't want the stage to move on init
            if prop != 'position':
                getattr(self, 'set_'.format(prop))(value=self.config[prop]['value'], unit=self.config[prop]['unit'])

        self.invert_axis = self.config['inverted']

    def _check_unit(self, unit, unit_type):
        """Checks whether *unit* as well as *unit_type* are in *self.units*."""

        if unit_type not in self.units:
            raise TypeError("Invalid unit type '{}'. Valid units: {}".format(unit_type, ', '.join(self.units.keys())))

        # Check if unit is okay
        if unit not in self.units[unit_type]:
            logging.warning("Unit of {} must be one of '{}'. Using {}!".format(unit_type, ', '.join(self.units[unit_type]), self.units[unit_type][0]))
            unit = self.units[unit_type][0]

        return unit

    def add_position(self, name, unit, value=None, date=None):
        """
        Method which stores new named position on the axis in the config. If it already exists in self.config['positions'], the entries are updated

        Parameters
        ----------
        name: str
            name of the position
        value: int, float, None
            position, if None position is current position
        unit: str
            string of unit
        date: str, None
            if None, will be return value of time.asctime()
        """

        # Position info dict
        new_pos = {'value': value if value is not None else self.get_position(unit),
                   'unit': unit, 'date': time.asctime() if date is None else date}

        # We're updating an existing position
        if name in self.config['positions']:

            logging.debug('Updating position {} (Last update: {})'.format(name, self.config['positions'][name]['date']))

            # Update directly in dict
            self.config['positions'][name].update(new_pos)

        # We're adding a new position
        else:

            logging.debug('Adding position {}!'.format(name))

            self.config['positions'][name] = new_pos

    def remove_position(self, name):
        """
        Method which removes an existing XY stage position from self.config['positions']

        Parameters
        ----------
        name: str
            name of the position
        """

        if name in self.config['positions']:
            del self.config['positions'][name]
        else:
            logging.warning('Position {} unknown and therefore cannot be removed.'.format(name))

    def save_config(self):
        """
        Method save the content of self.config aka irrad_control.XX_stage_config to the respective config yaml (overwriting it).
        This method get's called inside the instances' destructor.
        """

        if self.config['filename'] is None:
            return

        try:
            logging.info('Updating {} axis positions')

            save_yaml(path=self.config['filename'], data=self.config)

            logging.info('Successfully updated axis configuration')

        except (OSError, IOError):
            logging.warning("Could not update axis configuration file at {}. Maybe it is opened by another process?".format(self.config['filename']))

    def __del__(self):
        self.save_config()

    def convert_to_unit(self, value, unit):
        raise NotImplementedError("{} needs to implement a 'convert_to_unit'-method".format(self.__class__.__name__))

    def convert_from_unit(self, value, unit):
        raise NotImplementedError("{} needs to implement a 'convert_from_unit'-method".format(self.__class__.__name__))

    def get_position(self, unit):
        raise NotImplementedError("{} needs to implement a 'get_position'-method".format(self.__class__.__name__))

    def get_speed(self, unit):
        raise NotImplementedError("{} needs to implement a 'get_speed'-method".format(self.__class__.__name__))

    def get_accel(self, unit):
        raise NotImplementedError("{} needs to implement a 'get_accel'-method".format(self.__class__.__name__))

    def get_range(self, unit):
        raise NotImplementedError("{} needs to implement a 'get_range'-method".format(self.__class__.__name__))

    def set_position(self, value, unit):
        return self.move_abs(value, unit)

    def set_speed(self, value, unit):
        raise NotImplementedError("{} needs to implement a 'set_speed'-method".format(self.__class__.__name__))

    def set_accel(self, value, unit):
        raise NotImplementedError("{} needs to implement a 'set_accel'-method".format(self.__class__.__name__))

    def set_range(self, value, unit):
        raise NotImplementedError("{} needs to implement a 'set_range'-method".format(self.__class__.__name__))

    def move_rel(self, value, unit):
        raise NotImplementedError("{} needs to implement a 'move_rel'-method".format(self.__class__.__name__))

    def move_abs(self, value, unit):
        raise NotImplementedError("{} needs to implement a 'move_abs'-method".format(self.__class__.__name__))

    def stop(self):
        raise NotImplementedError("{} needs to implement a 'stop'-method".format(self.__class__.__name__))


class BaseAxisTracker(object):
    """Object that keeps track of a *BaseAxis*-instances movement by publishing its properties on every
    movement-state change e.g. start / stop """

    def __init__(self, context, address, axis=None, axis_domain=None, sender=None):

        # ZMQ configuration
        self.ctx = context
        self.addr = address
        self.sender = sender
        self._zmq_config = {'ctx': self.ctx, 'addr': self.addr, 'sender': sender, 'axis_pubs': {}}

        # Store axis, pubs / threads they live on
        self._tracked_axes = []

        # We have axis to track
        if axis:
            if isinstance(axis, (list, tuple)):
                for i, a in enumerate(axis):
                    self.track_axis(axis=a, axis_id=i, axis_domain=axis_domain)
            else:
                self.track_axis(axis=axis, axis_id=0, axis_domain=axis_domain)

    def track_axis(self, axis, axis_id, axis_domain=None):
        """
        Method that decorates movement functions of *axis* so that movement is tracked in axis config. If set up,
        axis data is published via ZMQ.

        Parameters
        ----------
        axis: BaseAxis
            BaseAxis instance
        axis_id: int
            Identifier for this axis under which the data is published
        axis_domain: str
            Name of the axis domain (e.g. the motorstage which contains the axis e.g. 'ScanStage'
        """

        if not isinstance(axis, BaseAxis):
            logging.error('Axis must be instance of BaseAxis, is {}. Not tracking axis {}'.format(type(axis), axis_id))
            return

        if axis in self._tracked_axes:
            logging.warning('Axis {} with ID {} is already tracked.'.format(type(axis), axis_id))
            return

        self._zmq_config['axis_pubs'][id(axis)] = {'pub': create_pub_from_ctx(ctx=self.ctx, addr=self.addr),
                                                   'thread_id': get_ident()}

        # Decorator replacing original movement funcs
        # See https://stackoverflow.com/questions/394770/override-a-method-at-instance-level
        axis.move_abs = MethodType(base_axis_movement_tracker(axis_movement_func=axis.move_abs,
                                                              axis_id=axis_id,
                                                              zmq_config=self._zmq_config,
                                                              axis_domain=axis_domain),
                                   axis)
        axis.move_rel = MethodType(base_axis_movement_tracker(axis_movement_func=axis.move_rel,
                                                              axis_id=axis_id,
                                                              zmq_config=self._zmq_config,
                                                              axis_domain=axis_domain),
                                   axis)
