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

    def __init__(self, scan_stage, irrad_events, config=None):

        # Timing-related
        self._event_wait_time = 0.1  # Wait for events to be set
        self._between_checks_time = 1.0  # Wait for

        self.scan_stage = scan_stage

        # ZMQ configuration
        self.zmq_config = {}

        # Minimum info the scan_config must contain in order to scan
        self.scan_reqs = ('origin', 'start', 'end', 'n_rows', 'rows', 'scan_speed', 'row_sep')

        # Events to be automatically updated
        self.irrad_events = irrad_events

        # Events controlling the scanning procedure
        self.interaction_events = {e: threading.Event() for e in ('abort', 'finish', 'pause')}

        # Scan parameters; derived from scan config
        self._scan_params = {}

        # Construct scan parameters
        # Scan configuration
        if config is not None:
            self.setup_scan(scan_config=config)

    def handle_interaction(self, interaction):
        """
        Method to handle an interaction. *interaction* is string and can be any of the following

        abort:
            Scan stops immediately after scanning current row. Setup relocates to scan origin
        finish:
            Scan stops after current scan is completed. Setup relocates to scan origin
        pause:
            Scan pauses until *continue* event before next scan is done. Beam located on shielding
        continue:
            Scan continues after pausing.
        """

        if interaction == 'abort':
            logging.warning("Aborting scan!")
            self.interaction_events['abort'].set()
        elif interaction == 'finish':
            logging.info("Finishing scan!")
            self.interaction_events['finish'].set()
        elif interaction == 'pause':
            logging.info("Pausing scan!")
            self.interaction_events['pause'].set()
        elif interaction == 'continue':
            logging.info("Continuing scan!")
            self.interaction_events['pause'].clear()

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

    def setup_scan(self, scan_config):
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

        self._scan_params.update(scan_config)

        self._generate_scan_area()

        self.scan_config = scan_config

        return self._scan_params

    def _generate_scan_area(self):
        """
        Sets the 'start' and 'end' key values in the self.scan_params dict which define the scan area rectangle.
        The scan area is constructed with respect to the beam FWHM and scan velocity as well as acceleration.
        If the self.scan_params['dut_rect_is_scan_area'] is True, the scan area is consructed directly as the dut
        rect without considering acceleration, etc.
        """

        # Convert mm to native axis unit
        axis_mm_to_native = lambda axis_idx, val: self.scan_stage.axis[axis_idx].convert_from_unit(val, unit='mm')
        axis_native_to_mm = lambda axis_idx, val: self.scan_stage.axis[axis_idx].convert_to_unit(val, unit='mm')

        # Store origin of relative coordinate system used for scan
        self._scan_params['origin'] = tuple(self.scan_stage.get_position())  # Native units

        start, end = [], []

        for i in range(2):

            dut_rect_upper = axis_mm_to_native(i, self._scan_params['dut_rect_upper'][i])
            dut_rect_lower = axis_mm_to_native(i, self._scan_params['dut_rect_lower'][i])

            start.append(self._scan_params['origin'][i] + dut_rect_upper)
            end.append(self._scan_params['origin'][i] + dut_rect_lower)

        self._scan_params['dut_rect_start'] = tuple(axis_native_to_mm(i, start[i]) for i in range(2))
        self._scan_params['dut_rect_stop'] = tuple(axis_native_to_mm(i, end[i]) for i in range(2))

        # We take the given rectangle as the DUT area and need modifications
        if not self._scan_params['dut_rect_is_scan_area']:
            # Beam-caused additional spacing we need: 3 sigma in each plane
            beam_sigma_x, beam_sigma_y = (x / 2.3548 for x in self._scan_params['beam_fwhm'])
            # De/Acceleration when scanning a row
            scan_accel = self.scan_stage.axis[0].get_accel(unit='mm/s^2')
            # Distance travelled until scan speed is reached
            accel_distance = 0.5 * self._scan_params['scan_speed'] ** 2 / scan_accel
            # Resulting offsets in x and y
            scan_offset_x = axis_mm_to_native(0, 3 * beam_sigma_x + 2 * accel_distance)
            scan_offset_y = axis_mm_to_native(1, 3 * beam_sigma_y)

            # Apply offset
            start[0] -= scan_offset_x
            end[0] += scan_offset_x
            start[1] -= scan_offset_y
            end[1] += scan_offset_y
            

        self._scan_params['start'] = tuple(start)
        self._scan_params['end'] = tuple(end)

        # Store number of rows in this scan
        n_rows = abs(self._scan_params['end'][1] - self._scan_params['start'][1])
        row_sep = axis_mm_to_native(1, self._scan_params['row_sep'])
        n_rows /= row_sep
        self._scan_params['n_rows'] = int(n_rows + 1)  # Always round up to next largest int

        # Make dictionary with absolute position in native units of each row
        rows = {}
        for row in range(self._scan_params['n_rows']):
            rows[row] = self._scan_params['start'][1] + row * row_sep
        self._scan_params['rows'] = rows

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

    def _check_abort(self):
        """
        Check if scan is to be aborted.

        Raises
        ------
        ScanError
        """
        if self.interaction_events['abort'].wait(self._event_wait_time):
            raise ScanError("Scan was stopped manually")

    def _wait_for_condition(self, condition_call, log_msg=None, log_level='INFO', check_call=None):
        """
        Wait for condition, returned by *condition_call*,  to be True.
        Sleep between conditions, and log *log_msg* with level *log_level*, if given.
        If given, call *check_call* function every iteration.

        Parameters
        ----------
        condition_call : _type_
            _description_
        log_msg : _type_, optional
            _description_, by default None
        log_level : str, optional
            _description_, by default 'INFO'
        check_call : _type_, optional
            _description_, by default None
        """
    
        while not condition_call():    
            if log_msg is not None:
                logging.log(level=logging.getLevelName(log_level), msg=log_msg)
            if check_call is not None:
                check_call()
            time.sleep(self._between_checks_time)


    def scan_row(self, row, speed=None, repeat=1):
        """
        Method to scan a single row of a device. Uses info about scan parameters from self._scan_params dict.
        Does sanity checks. The actual scan is done in a separate thread which calls self._scan_row.

        Parameters
        ----------
        row : int:
            Integer of row which should be scanned
        speed : float, None
            Scan speed in mm/s or None. If None, current speed of x-axis is used for scanning
        repeat : int
            Number of times *row* should be scanned with *speed*
        """

        # Check scan configuration dict
        if not self._check_scan():
            return

        # Start scan in separate thread
        scan_thread = threading.Thread(target=self._scan_row, kwargs={'row': row, 'speed': speed, 'repeat': repeat})
        scan_thread.start()

    def scan_device(self):
        """
        Method to scan a rectangular area by stepping vertically with fixed step size and moving with
        fixed speed horizontally. Uses info about scan parameters from self._scan_params dict. Does sanity checks.
        The actual scan is done in a separate thread which calls self._scan_device.
        """

        # Start scan in separate thread
        scan_thread = threading.Thread(target=self._scan_device)
        scan_thread.start()

    def _scan_row(self, row, speed=None, scan=-1, data_pub=None, repeat=1):
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
        repeat : int
            Number of times *row* should be scanned with *speed*
        """

        # Check row is in self._scan_params['rows']
        if row not in self._scan_params['rows']:
            logging.error("Row {} is not in range of 0 - {} of this scan. Abort".format(row, self._scan_params['n_rows']))
            return

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
        x_start, x_end = self._scan_params['start'][0], self._scan_params['end'][0]

        if data_pub is not None:
            # Publish stop data
            _meta = {'timestamp': time.time(), 'name': self.zmq_config['sender'], 'type': 'scan'}
            _data = {'status': 'scan_row_initiated', 'scan': scan, 'row': row}

            # Publish data
            data_pub.send_json({'meta': _meta, 'data': _data})

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

        # Scan row *repeat* times
        for _ in range(int(repeat)):

            # Current x position
            x_current = self.scan_stage.axis[0].get_position()

            # If we're not at the start or end of a row, something went wrong
            if x_current not in (x_start, x_end):
                msg = "Current x-axis position ({}) does not correspond to either start ({}) or end ({}) x-position of the scan. Abort!"
                msg.format(x_current, x_start, x_end)
                raise ScanError(msg)

            # Check for beam conditions to be okay before scanning a row, if not wait
            self._wait_for_condition(condition_call=self.irrad_events.beam_ok,
                                     log_msg="Insufficient beam conditions. Waiting for beam to stabilize...",
                                     log_level='WARNING',
                                     check_call=self._check_abort)  # If beam does not recover and we need to stop manually

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
                        'x_stop': self.scan_stage.axis[0].get_position(unit='mm'),
                        'y_stop': self.scan_stage.axis[1].get_position(unit='mm')}

                # Publish data
                data_pub.send_json({'meta': _meta, 'data': _data})

        if from_origin:
            # Move back to origin; move y first in order to not scan over device
            self.scan_stage.move_abs(axis=1, value=self._scan_params['origin'][1])
            self.scan_stage.move_abs(axis=0, value=self._scan_params['origin'][0])

        if data_pub is not None:
            # Publish stop data
            _meta = {'timestamp': time.time(), 'name': self.zmq_config['sender'], 'type': 'scan'}
            _data = {'status': 'scan_row_completed', 'scan': scan, 'row': row}

            # Publish data
            data_pub.send_json({'meta': _meta, 'data': _data})

        if spawn_pub:
            data_pub.close()

    def _scan_device(self):
        """
        Method which is supposed to be called by self.scan_device. See docstring there.

        """

        # Check scan configuration dict
        if not self._check_scan():
            return

        # Initialize zmq data publisher if zmq is setup
        data_pub = None if not self.zmq_config else create_pub_from_ctx(ctx=self.zmq_config['ctx'], addr=self.zmq_config['addr'])

        # Move to start point
        self.scan_stage.move_abs(axis=0, value=self._scan_params['start'][0])
        self.scan_stage.move_abs(axis=1, value=self._scan_params['start'][1])

        # Set the scan speed
        self.scan_stage.set_speed(value=self._scan_params['scan_speed'], axis=0, unit='mm/s')

        if data_pub is not None:

            # Initialize scan
            _meta = {'timestamp': time.time(), 'name': self.zmq_config['sender'], 'type': 'scan'}
            _data = {'status': 'scan_init', 'row_sep': self._scan_params['row_sep'], 'n_rows': self._scan_params['n_rows'],
                     'aim_damage': self.scan_config['aim_damage'], 'aim_value': self.scan_config['aim_value'],
                     'min_current': self.scan_config['min_current'],
                     'scan_origin': tuple(self.scan_stage.axis[i].convert_to_unit(self._scan_params['origin'][i], 'mm') for i in range(2)),
                     'scan_area_start': tuple(self.scan_stage.axis[i].convert_to_unit(self._scan_params['start'][i], 'mm') for i in range(2)),
                     'scan_area_stop': tuple(self.scan_stage.axis[i].convert_to_unit(self._scan_params['end'][i], 'mm') for i in range(2)),
                     'dut_rect_start': self._scan_params['dut_rect_start'],
                     'dut_rect_stop': self._scan_params['dut_rect_stop'],
                     'beam_fwhm': self.scan_config['beam_fwhm']}

            # Put init data
            data_pub.send_json({'meta': _meta, 'data': _data})

        # Start actual scan: each scan is counted as one coverage of the entire area
        try:

            # Initialize scan number
            scan = 0

            # Initialize rows of scan for top to bottom and bottom to top scan; reuse to safe resources
            top_to_bottom_rows = range(self._scan_params['n_rows'])
            bottom_to_top_rows = range(self._scan_params['n_rows']-1, -1, -1)  # Same as reversed, but not iterator -> can be reused

            # Loop until self.interaction_events['abort'] or self.interaction_events['finish']
            while not any(self.interaction_events[iv].wait(self._event_wait_time) for iv in ('abort', 'finish')):

                # Pause scan indefinitely until manually resuming
                self._wait_for_condition(condition_call=lambda: not self.interaction_events['pause'].wait(self._event_wait_time),
                                         log_msg=f"Scan paused after {scan} scans. Waiting to continue",
                                         log_level='INFO')

                # Determine whether we're scanning top to bottom or opposite
                current_rows = top_to_bottom_rows if scan % 2 == 0 else bottom_to_top_rows

                # Loop over rows
                for row in current_rows:

                    # Check for emergency stop; if so, raise error
                    if self.interaction_events['abort'].wait(self._event_wait_time):
                        raise ScanError("Scan was stopped manually")

                    # Scan row
                    self._scan_row(row=row, scan=scan, data_pub=data_pub)

                _meta = {'timestamp': time.time(), 'name': self._scan_params['server'], 'type': 'scan'}
                _data = {'status': 'scan_complete', 'scan': scan}

                data_pub.send_json({'meta': _meta, 'data': _data})

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
            for _, e in self.interaction_events.items():
                e.clear()
