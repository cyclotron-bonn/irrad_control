import logging
import threading
import time
from irrad_control.utils.utils import create_pub_from_ctx


class ScanError(Exception):
    pass


class DUTScan(object):
    """Class that handles the scanning of a device-under-test (DUT) through a grid-like scheme by controlling a two-dimensional motor stage.
    Additionally, if set up, the scan progress is published via ZMQ"""

    @property
    def n_rows(self):
        return self._scan_params['n_rows']

    @n_rows.setter
    def n_rows(self, val):
        raise AttributeError("n_rows is read-only")

    @property
    def rows(self):
        return self._scan_params['rows']

    @rows.setter
    def rows(self, val):
        raise AttributeError("rows is read-only")

    def __init__(self, scan_stage, scan_config):

        # Timing-related
        self._event_wait_time = 0.1  # Wait for events to be set
        self._between_checks_time = 1.0  # Wait for

        self.scan_stage = scan_stage

        # Scan configuration
        self.scan_config = scan_config

        # ZMQ configuration
        self.zmq_config = {}

        # Minimum info the scan_config must contain in order to scan
        self.scan_reqs = ('origin', 'start', 'end', 'n_rows', 'rows', 'scan_speed', 'row_sep')

        # Events controlling the scanning procedure
        self._events = {e: threading.Event() for e in ('stop', 'complete', 'standby', 'wait')}

        # Scan parameters; derived from scan config
        self._scan_params = {}

        # Construct scan parameters
        self._setup_scan()

    def handle_event(self, event):
        """
        Method to handle an event. *event* is string and can be any of the following

        abort:
            Scan stops immediately after scanning current row. Setup relocates to scan origin
        finish:
            Scan stops after current scan is completed. Setup relocates to scan origin
        pause:
            Scan pauses until *continue* event before next scan is done. Beam located on shielding
        continue:
            Scan continues after pausing.
        beam_down:
            Scan pauses before/ after scanning row (depending on when event arrives) until *beam_ok* event. Beam located on shielding.
        beam_jitter:
            Scan pauses before/ after scanning row (depending on when event arrives) until *beam_ok* event. Beam located on shielding.
        beam_ok:
            Scan pauses before/ after scanning row (depending on when event arrives) until *beam_ok* event. Beam located on shielding.

        """

        if event == 'abort':
            self._events['stop'].set()
        elif event == 'finish':
            self._events['complete'].set()
        elif event == 'pause':
            self._events['wait'].set()
        elif event == 'continue':
            self._events['wait'].clear()
        elif event in ('beam_down', 'beam_jitter'):
            self._events['standby'].set()
        elif event == 'beam_ok':
            self._events['standby'].clear()

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

    def _setup_scan(self):
        """
        Prepares a scan by gathering info from self.scan_config and generating all needed quantities in internal self._scan_config

        rel_start : tuple, list
            iterable of starting point (x [mm], y [mm]) relative to current position, defining upper left corner of area
        rel_end : tuple, list
            iterable of end point (x [mm], y [mm]) relative to current position, defining lower right corner of area
        scan_speed : float
            horizontal scan speed in mm / s
        row_sep : float
            step size of vertical steps in mm
        """

        # Convert mm to native axis unit
        axis_mm_to_native = lambda axis_idx, val: self.scan_stage.axis[axis_idx].convert_to_native(val, unit='mm')

        # Store origin of relative coordinate system used for scan
        self._scan_params['origin'] = tuple(self.scan_stage.get_position())  # Native units

        # Start position of the scan in native units
        self._scan_params['start'] = tuple(self._scan_params['origin'][i] - axis_mm_to_native(i, self.scan_config['rel_start'][i]) for i in (0, 1))

        # Start position of the scan in native units
        self._scan_params['end'] = tuple(self._scan_params['origin'][i] - axis_mm_to_native(i, self.scan_config['rel_end'][i]) for i in (0, 1))

        # Store scan speed
        self._scan_params['scan_speed'] = self.scan_config['scan_speed']  # mm/s

        # Store step size
        self._scan_params['row_sep'] = self.scan_config['row_sep']  # mm

        # Store number of rows in this scan
        self._scan_params['n_rows'] = int(abs(self._scan_params['end'][1] - self._scan_params['start'][1]) / axis_mm_to_native(1, self.scan_config['row_sep']))

        # Make dictionary with absolute position in native units of each row
        self._scan_params['rows'] = dict([(row, self._scan_params['start'][1] - row * axis_mm_to_native(1, self._scan_params['row_sep']))
                                         for row in range(self._scan_params['n_rows'])])

    def _check_scan(self):
        """
        Method to do sanity checks on the generated *self._scan_params* dict.
        """

        # Check if dict is empty or not dict
        if not self._scan_params or not isinstance(self._scan_params, dict):
            msg = "Scan parameter dict is empty or not of type dictionary! "
            logging.error(msg)
            return False

        # Check if self._scan_params dict contains all necessary info
        missed_reqs = [req for req in self.scan_reqs if req not in self._scan_params]

        # Return if info is missing
        if missed_reqs:
            msg = "Scan parameter dict is missing required info: {}. Abort.".format(', '.join(missed_reqs))
            logging.error(msg)
            return False

        return True

    def scan_row(self, row, speed=None):
        """
        Method to scan a single row of a device. Uses info about scan parameters from self._scan_params dict.
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

        # Check row is in self._scan_params['rows']
        if row not in self._scan_params['rows']:
            logging.error("Row {} is not in range of 0 - {} of this scan. Abort".format(row, self._scan_params['n_rows']))
            return

        # Start scan in separate thread
        scan_thread = threading.Thread(target=self._scan_row, args=(row, speed))
        scan_thread.start()

    def scan_device(self):
        """
        Method to scan a rectangular area by stepping vertically with fixed step size and moving with
        fixed speed horizontally. Uses info about scan parameters from self._scan_params dict. Does sanity checks.
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
        from_origin = tuple(self.scan_stage.get_position()) == self._scan_params['origin']

        # Set custom speed to scan this row
        if speed is not None:
            self.scan_stage.set_speed(speed, axis=0, unit='mm/s')

        # Make x start and end variables
        x_start, x_end = self._scan_params['start_pos'][0], self._scan_params['end_pos'][0]

        # Check whether we are scanning from origin
        if from_origin:
            self.scan_stage.move_abs(axis=0, value=x_start)

            # Check reply; if something went wrong raise error
            if self.scan_stage.axis[0].error:
                msg = "X-axis did not move to start point. Abort"
                raise ScanError(msg)

        # Move to the current row
        self.scan_stage.move_abs(axis=1, value=self._scan_params['rows'][row])

        # Check reply; if something went wrong raise error
        if self.scan_stage.axis[1].error:
            msg = "Y-axis did not move to row {}. Abort.".format(row)
            raise ScanError(msg)

        # Current x position
        x_current = self.scan_stage.axis[0].get_position()

        # If we're not at the start or end of a row, something went wrong
        if x_current not in (x_start, x_end):
            msg = "Current x-axis position ({}) does not correspond to either start ({}) or end ({}) x-position of the scan. Abort!"
            msg.format(x_current, x_start, x_end)
            raise ScanError(msg)

        # Check for beam current to be sufficient / beam to be on for scan; if not wait
        while self._events['standby'].wait(self._event_wait_time):
            logging.warning("Insufficient beam conditions. Waiting for beam to stabilize")
            time.sleep(self._between_checks_time)

            # If beam does not recover and we need to stop manually
            if self.stop_scan.wait(self._event_wait_time):
                raise ScanError("Scan was stopped manually")

        # Publish if we have a socket
        if data_pub is not None:

            # Publish data
            _meta = {'timestamp': time.time(), 'name': self.zmq_config['sender'], 'type': 'scan'}
            _data = {'status': 'scan_start', 'scan': scan, 'row': row,
                     'speed': self.scan_stage.axis[0].get_speed(unit='mm/s'),
                     'accel': self.scan_stage.axis[0].get_accel(unit='mm/s^2'),
                     'x_start': self.scan_stage.axis[0].get_position(unit='mm'),
                     'y_start': self.scan_stage.axis[1].get_position(unit='mm')}

            # Publish data
            data_pub.send_json({'meta': _meta, 'data': _data})

        # Scan the current row
        self.scan_stage.move_abs(axis=0, value=x_end if x_current == x_start else x_start)

        # Check reply; if something went wrong raise error
        if self.scan_stage.axis[0].error:
            msg = "X-axis did not scan row {}. Abort.".format(row)
            raise ScanError(msg)

        # Publish if we have a socket
        if data_pub is not None:

            # Publish stop data
            _meta = {'timestamp': time.time(), 'name': self.zmq_config['sender'], 'type': 'scan'}
            _data = {'status': 'scan_stop',
                     'x_stop': self.scan_stage.axis[0].position(unit='mm'),
                     'y_stop': self.scan_stage.axis[1].position(unit='mm')}

            # Publish data
            data_pub.send_json({'meta': _meta, 'data': _data})

        if spawn_pub:
            data_pub.close()

        if from_origin:
            # Move back to origin; move y first in order to not scan over device
            self.scan_stage.move_abs(axis=1, value=self._scan_params['origin'][1])
            self.scan_stage.move_abs(axis=0, value=self._scan_params['origin'][0])

    def _scan_device(self):
        """
        Method which is supposed to be called by self.scan_device. See docstring there.

        """

        data_pub = None

        # If we can use zmq
        if self.zmq_config:

            # Initialize zmq data publisher
            data_pub = create_pub_from_ctx(ctx=self.zmq_config['ctx'], addr=self.zmq_config['addr'])

            # Initialize scan
            _meta = {'timestamp': time.time(), 'name': self.zmq_config['sender'], 'type': 'scan'}
            _data = {'status': 'scan_init', 'y_step': self._scan_params['row_sep'], 'n_rows': self._scan_params['n_rows']}

            # Put init data
            data_pub.send_json({'meta': _meta, 'data': _data})

        # Move to start point
        self.scan_stage.move_abs(axis=0, value=self._scan_params['start'][0])
        self.scan_stage.move_abs(axis=1, value=self._scan_params['start'][1])

        # Set the scan speed
        self.scan_stage.set_speed(value=self._scan_params['scan_speed'], axis=0, unit='mm/s')

        # Start actual scan: each scan is counted as one coverage of the entire area
        try:

            # Initialize scan number
            scan = 0

            # Initialize rows of scan for top to bottom and bottom to top scan; reuse to safe resources
            top_to_bottom_rows = range(self._scan_params['rows'])
            bottom_to_top_rows = range(self._scan_params['rows']-1, -1, -1)  # Same as reversed, but not iterator -> can be reused

            # Loop until self._events['stop'] or self._events['complete']
            while not (self.events['stop'].wait(self._event_wait_time) or self.events['complete'].wait(self._event_wait_time)):

                # Pause scan indefinitely until manually resuming
                while self._events['wait'].wait(self._event_wait_time):
                    logging.debug(f'Scan paused after {scan} scans. Waiting to continue')
                    time.sleep(self._between_checks_time)

                # Determine whether we're scanning top to bottom or opposite
                current_rows = top_to_bottom_rows if scan % 2 == 0 else bottom_to_top_rows

                # Loop over rows
                for row in current_rows:

                    # Check for emergency stop; if so, raise error
                    if self._events['stop'].wait(self._event_wait_time):
                        raise ScanError("Scan was stopped manually")

                    # Scan row
                    self._scan_row(row=row, scan=scan, data_pub=data_pub)

                # Increment
                scan += 1

        # Some axis command didn't succeed or emergency exit was issued
        except ScanError:
            logging.exception("Scan aborted!")

        finally:

            if data_pub is not None:
                # Put finished data
                _meta = {'timestamp': time.time(), 'name': self.zmq_config['sender'], 'type': 'scan'}
                _data = {'status': 'scan_finished'}

                # Publish data
                data_pub.send_json({'meta': _meta, 'data': _data})

                data_pub.close()

            # Reset speeds and move back to origin; move y first in order to not scan over device
            for i in (1, 0):
                self.scan_stage.set_speed(value=10, axis=i, unit='mm/s')
                self.scan_stage.move_abs(axis=i, value=self._scan_params['origin'][i])

            # Reset signal so one can scan again
            for _, e in self._events.items():
                e.clear()
