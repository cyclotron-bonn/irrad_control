import logging
import threading
import time
from irrad_control.utils.utils import check_zmq_addr, create_pub_from_ctx


class ScanError(Exception):
    pass


class DUTScan(object):
    """Class that handles the scanning of a device-under-test (DUT) through a grid-like scheme by controlling a two-dimensional motor stage.
    Additionally, if set up, the scan progress is published via ZMQ"""

    def __init__(self, scan_stage):

        self.scan_stage = scan_stage

        self.events = {e: threading.Event() for e in ('stop', 'finish', 'pause', 'no_beam', 'scanning')}

        # Status of the scan
        self.status = None

        # Scan configuration
        self.scan_config = {}

        # Scan meta data
        self.scan_meta = {}

        # ZMQ configuration
        self.zmq_config = {}

        # Beam configuration
        self.beam_config = {}

        # DUT configuration
        self.dut_config = {}

        # Minimum info the scan_config must contain in order to scan
        self.scan_reqs = ('origin', 'start', 'end', 'n_rows', 'rows', 'speed', 'step')

    def event(self, event, set_to=None):
        """Method to get/set the state of an event"""

        if set_to is None:
            return self.events[event].is_set()
        else:
            return self.events[event].set() if set_to else self.events[event].clear()

    def set_beam_property(self, **kwargs):
        self.beam_config.update(**kwargs)

    def setup_zmq(self, ctx, skt, addr, sender=None):
        """
        Method to pass a ZMQ context to the stage class in order to allow it to publish data on a socket

        Parameters
        ----------
        ctx: zmq.Context instance
            A ZMQ context instance from which sockets can be created
        skt: zmq.PUB
            A ZMQ publisher socket
        addr: str
            A ZMQ address to connect to. Must be a valid combination of protocol, address and port
        sender: str, None
            Name of the device from which the stage is interfaced
        """
        # Store
        self.zmq_config.update({'ctx': ctx, 'skt': skt, 'addr': addr, 'sender': sender})

    def setup_scan(self, rel_start_point, rel_end_point, speed, step):
        """
        Prepares a scan by storing all needed info in self.scan_config

        Parameters
        ----------
        rel_start_point : tuple, list
            iterable of starting point (x [mm], y [mm]) relative to current position, defining upper left corner of area
        rel_end_point : tuple, list
            iterable of end point (x [mm], y [mm]) relative to current position, defining lower right corner of area
        speed : float
            horizontal scan speed in mm / s
        step : float
            step size of vertical steps in mm
        """

        # Store origin of relative coordinate system used for scan
        self.scan_config['origin'] = tuple(self.scan_stage.axis[i].position() for i in (0, 1))

        # Start position of the scan
        self.scan_config['start'] = tuple(self.scan_config['origin'][i] - self.scan_stage.convert_to_native(rel_start_point[i], unit='mm') for i in (0, 1))

        # Start position of the scan
        self.scan_config['end'] = tuple(self.scan_config['origin'][i] - self.scan_stage.convert_to_native(rel_end_point[i], unit='mm') for i in (0, 1))

        # Store scan speed
        self.scan_config['speed'] = speed

        # Store step size
        self.scan_config['step'] = step

        # Store number of rows in this scan
        self.scan_config['n_rows'] = int(abs(self.scan_config['end'][1] - self.scan_config['start'][1]) / self.scan_stage.convert_to_native(step, unit='mm'))

        # Make dictionary with absolute position (in steps) of each row
        self.scan_config['rows'] = dict([(row, self.scan_config['start'][1] - row * self.scan_stage.convert_to_native(step, unit='mm'))
                                         for row in range(self.scan_config['n_rows'])])
        
    def _check_scan(self):
        """
        Method to do sanity checks on the *self.scan_config* dict.
        """

        # Check if dict is empty or not dict
        if not self.scan_config or not isinstance(self.scan_config, dict):
            msg = "Scan parameter dict is empty or not of type dictionary! " \
                  "Try using setup_scan method or fill missing info in dict. Abort."
            logging.error(msg)
            return False

        # Check if scan_config dict contains all necessary info
        missed_reqs = [req for req in self.scan_reqs if req not in self.scan_config]

        # Return if info is missing
        if missed_reqs:
            msg = "Scan parameter dict is missing required info: {}. " \
                  "Try using prepare_scan method or fill missing info in dict. Abort.".format(', '.join(missed_reqs))
            logging.error(msg)
            return False

        return True

    def scan_row(self, row, speed=None):
        """
        Method to scan a single row of a device. Uses info about scan parameters from scan_config dict.
        Does sanity checks. The actual scan is done in a separate thread which calls self._scan_row.

        Parameters
        ----------
        row : int:
            Integer of row which should be scanned
        speed : float, None
            Scan speed in mm/s or None. If None, current speed of x-axis is used for scanning
        """

        # Check scan configuration dict
        if not self._check_scan():
            return

        # Check row is in scan_config['rows']
        if row not in self.scan_config['rows']:
            msg = "Row {} is not in range of rows starting from 0 to {}. Abort".format(row, self.scan_config['n_rows'])
            logging.error(msg)
            return

        # Start scan in separate thread
        scan_thread = threading.Thread(target=self._scan_row, args=(row, speed))
        scan_thread.start()

    def scan_device(self):
        """
        Method to scan a rectangular area by stepping vertically with fixed step size and moving with
        fixed speed horizontally. Uses info about scan parameters from scan_config dict. Does sanity checks.
        The actual scan is done in a separate thread which calls self._scan_device.
        """

        # Check scan configuration dict
        if not self._check_scan():
            return

        # Start scan in separate thread
        scan_thread = threading.Thread(target=self._scan_device)
        scan_thread.start()

    def _scan_row(self, row, speed=None, scan=-1, data_pub=None):
        """
        Method which is called by self._scan_device or self.scan_row. See docstrings there.

        Parameters
        ----------
        row : int
            Row to scan
        speed : float, None
            Scan speed in mm/s or None. If None, current speed of x-axis is used for scanning
        scan : int
            Integer indicating the scan number during self.scan_device. *scan* for single rows is -1
        data_pub : zmq socket, None
            Socket on which data is published. If None, check if a socket can be created, if not, no data is published
        """

        # Check socket, if no socket is given and ZMQ is setup for this instance, open one
        spawn_pub = data_pub is None and self.zmq_config

        # If we're closing the socket, we have to open one before
        if spawn_pub:
            data_pub = create_pub_from_ctx(ctx=self.zmq_config['ctx'], addr=self.zmq_config['addr'])

        # Check whether this method is called from within self.scan_device or single row is scanned.
        # If single row is scanned, we're coming from
        from_origin = (self.scan_stage.axis[0].position(), self.scan_stage.axis[1].position()) == self.scan_config['origin']

        # Set custom speed to scan this row
        if speed is not None:
            self.scan_stage.axis[0].set_speed(speed, unit='mm/s')

        # Make x start and end variables
        x_start, x_end = self.scan_config['start_pos'][0], self.scan_config['end_pos'][0]

        # Check whether we are scanning from origin
        if from_origin:
            self.scan_stage.axis[0].move_abs(x_start)

            # Check reply; if something went wrong raise error
            if self.scan_stage.axis[0].error:
                msg = "X-axis did not move to start point. Abort"
                raise ScanError(msg)

        # Move to the current row
        self.scan_stage.axis[1].move_abs(self.scan_config['rows'][row])

        # Check reply; if something went wrong raise error
        if self.scan_stage.axis[1].error:
            msg = "Y-axis did not move to row {}. Abort.".format(row)
            raise ScanError(msg)

        # Publish if we have a socket
        if data_pub is not None:

            # Publish data
            _meta = {'timestamp': time.time(), 'name': self.zmq_config['sender'], 'type': 'stage'}
            _data = {'status': 'scan_start', 'scan': scan, 'row': row,
                     'speed': self.scan_stage.axis[0].get_speed(unit='mm/s'),
                     'x_start': self.scan_stage.axis[0].position(unit='mm'),
                     'y_start': self.scan_stage.axis[1].position(unit='mm')}

            # Publish data
            data_pub.send_json({'meta': _meta, 'data': _data})

        self.event('scanning', True)

        # Scan the current row
        self.scan_stage.axis[0].move_abs(x_end if self.scan_stage.axis[0].position() == x_start else x_start)

        self.event('scanning', False)

        # Check reply; if something went wrong raise error
        if self.scan_stage.axis[0].error:
            msg = "X-axis did not scan row {}. Abort.".format(row)
            raise ScanError(msg)

        # Publish if we have a socket
        if data_pub is not None:

            # Publish stop data
            _meta = {'timestamp': time.time(), 'name': self.zmq_config['sender'], 'type': 'stage'}
            _data = {'status': 'scan_stop',
                     'x_stop': self.scan_stage.axis[0].position(unit='mm'),
                     'y_stop': self.scan_stage.axis[1].position(unit='mm')}

            # Publish data
            data_pub.send_json({'meta': _meta, 'data': _data})

        if spawn_pub:
            data_pub.close()

        if from_origin:
            # Move back to origin; move y first in order to not scan over device
            for i in (1, 0):
                self.scan_stage.axis[i].move_abs(self.scan_config['origin'][i])

    def _scan_device(self):
        """
        Method which is supposed to be called by self.scan_device. See docstring there.

        """

        # Initialize zmq data publisher
        data_pub = create_pub_from_ctx(ctx=self.zmq_config['ctx'], addr=self.zmq_config['addr'])

        # Move to start point
        for i in (0, 1):
            self.scan_stage.axis[i].move_abs(self.scan_config['start'][i])

        # Set the scan speed
        self.scan_stage.axis[0].set_speed(self.scan_config['speed'], unit='mm/s')

        # Initialize scan
        _meta = {'timestamp': time.time(), 'name': self.scan_config['server'], 'type': 'stage'}
        _data = {'status': 'scan_init', 'y_step': self.scan_config['step_size'], 'n_rows': self.scan_config['n_rows']}

        # Put init data
        data_pub.send_json({'meta': _meta, 'data': _data})

        try:

            # Loop until fluence is reached and self.stop_scan event is set
            # Each scan is counted as one coverage of the entire area
            scan = 0
            while not (self.events['stop'].wait(1e-1) or self.events['finish'].wait(1e-1)):

                # Determine whether we're going from top to bottom or opposite
                _tmp_rows = list(range(self.scan_config['n_rows']) if scan % 2 == 0 else reversed(range(self.scan_config['n_rows'])))

                # Loop over rows
                for row in _tmp_rows:

                    # Check for emergency stop; if so, raise error
                    if self.events['stop'].wait(1e-1):
                        msg = "Scan was stopped manually"
                        raise ScanError(msg)

                    # Wait for beam current to be sufficient / beam to be on for scan
                    while not (self.events['pause'].wait(1e-1) or self.events['no_beam'].wait(1e-1)):
                        msg = ''
                        if self.event('pause'):
                            msg += 'Scan paused manually'
                        if self.event('no_beam'):
                            msg += "Low beam current or no beam in row {} of scan {}. Waiting for beam current to rise.".format(row, scan)

                        logging.warning(msg)
                        time.sleep(1)

                        # If beam does not recover and we need to stop manually
                        if self.stop_scan.wait(1e-1):
                            msg = "Scan was stopped manually"
                            raise ScanError(msg)

                    # Scan row
                    self._scan_row(row=row, scan=scan, data_pub=data_pub)

                # Increment
                scan += 1

        # Some axis command didn't succeed or emergency exit was issued
        except ScanError:
            logging.exception("Scan aborted!")

        finally:

            # Put finished data
            _meta = {'timestamp': time.time(), 'name': self.zmq_config['sender'], 'type': 'stage'}
            _data = {'status': 'scan_finished'}

            # Publish data
            data_pub.send_json({'meta': _meta, 'data': _data})

            # Reset speeds and move back to origin; move y first in order to not scan over device
            for i in (1, 0):
                self.scan_stage.axis[i].set_speed(10, unit='mm/s')
                self.scan_stage.axis[i].move_abs(self.scan_config['origin'][i])

            # Reset signal so one can scan again
            for e in self.events:
                self.event(e, set_to=False)

            data_pub.close()
