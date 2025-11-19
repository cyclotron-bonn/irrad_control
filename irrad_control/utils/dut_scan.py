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
        return self._scan_params["n_rows"]

    @n_rows.setter
    def n_rows(self, val):
        raise AttributeError("n_rows is read-only")

    @property
    def rows(self):
        return self._scan_params["rows"]

    @rows.setter
    def rows(self, val):
        raise AttributeError("rows is read-only")

    def __init__(self, scan_stage, irrad_events, config=None):
        # Timing-related
        self._event_wait_time = 0.1  # Wait for events to be set
        self._between_checks_time = 1.0  # Wait for

        # Scan area safety margin to account for e.g. misalignment when placing the DUT.
        # Scan area beam margin to account for beam size
        # Asymmetric due to misalignment being more relevant in x than in y
        self._scan_safety_margin = (10, 5)  # (x, y) mm
        self._scan_beam_margin = (4, 3)  # (x, y) beam sigmas

        # Allow to compensate for erroneous position reporting by scan stage controller
        # Motor stage position error counter
        # (Verified) current position; set after first move (per axis)
        self._position_recovery_margin = 0.1  #  mm
        self._position_errors = 0
        self._current_native_position = [None, None]

        self.scan_stage = scan_stage

        # Keep track of scan number
        self.n_complete_scan = 0

        # ZMQ configuration
        self.zmq_config = {}

        # Minimum info the scan_config must contain in order to scan
        self.scan_reqs = ("origin", "start", "end", "n_rows", "rows", "scan_speed", "row_sep")

        # Events to be automatically updated
        self.irrad_events = irrad_events

        # Events controlling the scanning procedure
        self.interaction_events = {e: threading.Event() for e in ("abort", "finish", "pause")}

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

        if interaction == "abort":
            logging.warning("Aborting scan!")
            self.interaction_events["abort"].set()
        elif interaction == "finish":
            logging.info("Finishing scan!")
            self.interaction_events["finish"].set()
        elif interaction == "pause":
            logging.info("Pausing scan!")
            self.interaction_events["pause"].set()
        elif interaction == "continue":
            logging.info("Continuing scan!")
            self.interaction_events["pause"].clear()

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
        self.zmq_config.update({"ctx": ctx, "skt": skt, "addr": addr, "sender": sender})

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
        def axis_mm_to_native(axis_idx, val):
            return self.scan_stage.axis[axis_idx].convert_from_unit(val, unit="mm")

        def axis_native_to_mm(axis_idx, val):
            return self.scan_stage.axis[axis_idx].convert_to_unit(val, unit="mm")

        # Store origin of relative coordinate system used for scan
        self._scan_params["origin"] = tuple(self.scan_stage.get_position())  # Native units

        start, end = [], []

        for i in range(2):
            dut_rect_upper = axis_mm_to_native(i, self._scan_params["dut_rect_upper"][i])
            dut_rect_lower = axis_mm_to_native(i, self._scan_params["dut_rect_lower"][i])

            start.append(self._scan_params["origin"][i] + dut_rect_upper)
            end.append(self._scan_params["origin"][i] + dut_rect_lower)

        self._scan_params["dut_rect_start"] = tuple(axis_native_to_mm(i, start[i]) for i in range(2))
        self._scan_params["dut_rect_stop"] = tuple(axis_native_to_mm(i, end[i]) for i in range(2))

        # We take the given rectangle as the DUT area and need modifications
        if not self._scan_params["dut_rect_is_scan_area"]:
            # Beam-caused additional spacing we need: 3 sigma in each plane
            beam_sigma_x, beam_sigma_y = (x / 2.3548 for x in self._scan_params["beam_fwhm"])
            # De/Acceleration when scanning a row
            scan_accel = self.scan_stage.axis[0].get_accel(unit="mm/s^2")
            # Distance travelled until scan speed is reached
            accel_distance = 0.5 * self._scan_params["scan_speed"] ** 2 / scan_accel
            # Resulting offsets in x and y, including safety margins
            scan_offset_x = self._scan_safety_margin[0] + self._scan_beam_margin[0] * beam_sigma_x + accel_distance
            scan_offset_y = self._scan_safety_margin[1] + self._scan_beam_margin[1] * beam_sigma_y
            scan_offset_x = axis_mm_to_native(0, scan_offset_x)
            scan_offset_y = axis_mm_to_native(1, scan_offset_y)

            # Apply offset
            start[0] -= scan_offset_x
            end[0] += scan_offset_x
            start[1] -= scan_offset_y
            end[1] += scan_offset_y

        self._scan_params["start"] = tuple(start)
        self._scan_params["end"] = tuple(end)

        # Store number of rows in this scan
        n_rows = abs(self._scan_params["end"][1] - self._scan_params["start"][1])
        row_sep = axis_mm_to_native(1, self._scan_params["row_sep"])
        n_rows /= row_sep
        self._scan_params["n_rows"] = int(n_rows + 1)  # Always round up to next largest int

        # Make dictionary with absolute position in native units of each row
        rows = {}
        for row in range(self._scan_params["n_rows"]):
            rows[row] = self._scan_params["start"][1] + row * row_sep
        self._scan_params["rows"] = rows

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
            msg = "Scan parameter dict is missing required info: {}. Abort.".format(", ".join(missed_reqs))
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
        if self.interaction_events["abort"].wait(self._event_wait_time):
            raise ScanError("Scan was stopped manually")

    def _wait_for_condition(self, condition_call, log_msg=None, log_level="INFO", check_call=None):
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

    def _get_position(self, axis, unit=None):
        """
        Method that returns the current position of *axis* in *unit*.
        This method only works within as the DUTScan class as it relies on the correct
        cashing of positon data within the _move_and_check method.

        Parameters
        ----------
        axis: int
            The index of the axis
        unit: str, None, optional
            The unit in which the position is returned, by default None i.e. native units
        """

        if self._current_native_position[axis] is None:
            self._current_native_position[axis] = self.scan_stage.axis[axis].get_position()

        position = self._current_native_position[axis]

        if unit is None:
            return position

        return self.scan_stage.axis[axis].convert_to_unit(position, unit=unit)

    def _return_to_origin(self, return_speed=10):
        """
        Mehod that returns the scan to the origin.
        It resets the movement speeds, checks the current position and returns the box
        to the origin without moving the beam though the scan area
        """

        current_x = self._get_position(axis=0)

        # Reset speeds
        for i in (1, 0):
            self.scan_stage.set_speed(axis=i, value=return_speed, unit="mm/s")

        # Make 3 sigma margins for x and why to drive around the scan area
        x_return = 3 / 2.3548 * self._scan_params["beam_fwhm"][0]  # 3 * x beam sigma in mm
        x_return = self.scan_stage.axis[1].convert_from_unit(x_return, unit="mm")  # Convert to axis units

        y_return = 3 / 2.3548 * self._scan_params["beam_fwhm"][1]  # 3 * y beam sigma in mm
        y_return = self.scan_stage.axis[1].convert_from_unit(y_return, unit="mm")  # Convert to axis units

        # We are on the close side of the scan area
        if current_x <= self._scan_params["start"][0]:
            # Move 3 sigma outside of the scan area, then to origin y and x
            self._move_and_check(axis=0, position=current_x - x_return)

        # We have to move "around" scan area; We have "unlimited" space to the top so we should return around the bottom
        elif current_x >= self._scan_params["end"][0]:
            # Go to x value which is 3 sigma outside the scan area to the right
            # Go to y value which is 3 sigma outside the scan area to the bottom
            self._move_and_check(axis=0, position=x_return + current_x)
            self._move_and_check(
                axis=1, position=y_return + max(self._scan_params["rows"].values())
            )  # Add lowest row a.k.a maximum y value
            self._move_and_check(axis=0, position=self._scan_params["start"][0] - x_return)
        else:
            raise ScanError("Trying to return from scan failed. Turn off beam and return manually!")

        self._move_and_check(axis=1, position=self._scan_params["origin"][1])
        self._move_and_check(axis=0, position=self._scan_params["origin"][0])

    def _move_and_check(self, axis, position, unit=None, max_tries=5):
        """
        Method that moves to an absolute position, checks the respective axis for error and checks whether the target position is read back after the move.
        If the target is not read back from the axis after the move has been completed, we repeat the move a couple of times and try again.
        If we end up not reaching the target or the stage has errors, raise ScanError

        Parameters
        ----------
        axis : int
            Index of the axis to be moved
        position : int, float
            Target position in units known to axis. If unit is None, use native units
        unit : str, None, optional
            String of the unit in which the target position is given. If None, use axis native unit, by default None
        max_tries : int, optional
            Number of tries to move to position, by default 5

        Raises
        ------
        ScanError
            The target position could not be read back properly so we don't know whether we moved axis to positon
        """

        assert axis < len(self.scan_stage.axis), f"Axis can only be 0 to {len(self.scan_stage.axis) - 1}"

        if unit is not None:
            assert unit in self.scan_stage.axes[axis].units["distance"], f"Unit {unit} not in axis distance units"
            target_in_native = self.scan_stage.axis[axis].convert_from_unit(
                position, unit=unit
            )  # Convert to axis units
        else:
            target_in_native = position

        success = False
        # Try to move maximum of 5 times before raising ScanError
        for n in range(1, max_tries + 1):
            self.scan_stage.move_abs(axis=axis, value=target_in_native)

            # Check no error and read back position after move in native
            success = not bool(self.scan_stage.axis[axis].error)
            success &= self.scan_stage.axis[axis].get_position() == target_in_native

            # Everything looks good
            if success:
                # Update current axis position and break out of the loop
                self._current_native_position[axis] = target_in_native
                break
            # If the axis is not at the target or has an error value other than False, try again
            else:
                unt = self.scan_stage.axis[axis].native_unit if unit is None else unit
                msg = f"Moving axis {axis} to position {position} {unt} failed. Try {n} of {max_tries}."
                logging.warning(msg)
                self._position_errors += 1
                time.sleep(0.1)

        # If we enter this else block, we never reached our target / always errored
        else:
            msg = f"Moving axis {axis} to position {position} {self.scan_stage.axis[axis].native_unit if unit is None else unit} repeatadly failed."
            msg += f"Current position: {self.scan_stage.axis[axis].get_position(unit=unit)} {unit or 'native units'}"
            msg += f"Axis error: {self.scan_stage.axis[axis].error or 'None'}"
            raise ScanError(msg)

    def _get_current_row_x_target(self, recover_inaccuracy=True):
        """
        Method to determine whether current row is scanned from row start to row end position or vice versa.
        This method accounts for inaccuracies in the readback of positions by the motorstage controller if
        they are sufficiently small (see self._position_recovery_margin) and recover_inaccuracy=True.
        """

        # Read current x position if it has not been set before
        x_current = self._get_position(axis=0)

        # Read x start and end variables from scan params
        x_start, x_end = self._scan_params["start"][0], self._scan_params["end"][0]

        # Everything is well
        if x_current == x_start:
            return x_end
        # Everything is well
        elif x_current == x_end:
            return x_start
        # Everything is not well
        else:
            self._position_errors += 1
            # Store positions in mm
            x_erroneous_mm = self.scan_stage.axis[0].convert_to_unit(x_current, "mm")
            x_start_mm = self.scan_stage.axis[0].convert_to_unit(x_start, "mm")
            x_end_mm = self.scan_stage.axis[0].convert_to_unit(x_end, "mm")

            msg = f"Current x-axis position ({x_erroneous_mm:.3f} mm) matches neither"
            msg += f" start ({x_start_mm:.3f} mm) nor end ({x_end_mm:.3f} mm) of scan pattern."
            logging.warning(msg)

            # Try to recover where to go if we are at either start or end within some deviation
            x_target = None
            if recover_inaccuracy:
                logging.warning("Attempting to recover erroneous position")
                x_dev_native = self.scan_stage.axis[0].convert_from_unit(self._position_recovery_margin, "mm")
                if x_start - x_dev_native <= x_current <= x_start + x_dev_native:
                    x_target = x_end
                elif x_end - x_dev_native <= x_current <= x_end + x_dev_native:
                    x_target = x_start

            if x_target is not None:
                x_target_mm = self.scan_stage.axis[0].convert_to_unit(x_target, "mm")
                logging.debug(
                    f"Position recovered as {x_target_mm:.3f} mm within {self._position_recovery_margin} mm margin."
                )
                return x_target
            else:
                msg = "Unable to recover from errorneous position"
                if recover_inaccuracy:
                    msg += f"within {self._position_recovery_margin} mm margin."
                else:
                    msg += "due to 'recover_inaccuracy=False' setting."
                msg += "Abort scan."
                raise ScanError(msg)

    def scan_row(self, row, speed=None, repeat=1, from_origin=True):
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
        from_origin : bool, optional
            Whether to scan the row from the scan origin, by default True
        """

        # Check scan configuration dict
        if not self._check_scan():
            return

        # Start scan in separate thread
        scan_thread = threading.Thread(
            target=self._scan_row, kwargs={"row": row, "speed": speed, "repeat": repeat, "from_origin": from_origin}
        )
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

    def _scan_row(self, row, speed=None, scan=-1, data_pub=None, repeat=1, from_origin=True):
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
        from_origin : bool, optional
            Whether to scan the row from the scan origin, by default True
        """

        # Check row is in self._scan_params['rows']
        if row not in self._scan_params["rows"]:
            logging.error(
                "Row {} is not in range of 0 - {} of this scan. Abort".format(row, self._scan_params["n_rows"])
            )
            return

        # Check socket, if no socket is given and ZMQ is setup for this instance, open one
        spawn_pub = data_pub is None and self.zmq_config

        # If we're closing the socket, we have to open one before
        if spawn_pub:
            data_pub = create_pub_from_ctx(ctx=self.zmq_config["ctx"], addr=self.zmq_config["addr"])

        # Set custom speed to scan this row
        if speed is not None:
            self.scan_stage.set_speed(speed, axis=0, unit="mm/s")

        if data_pub is not None:
            # Publish stop data
            _meta = {"timestamp": time.time(), "name": self.zmq_config["sender"], "type": "scan"}
            _data = {"status": "scan_row_initiated", "scan": scan, "row": row}

            # Publish data
            data_pub.send_json({"meta": _meta, "data": _data})

        # Check whether we are scanning from origin
        if from_origin:
            self._move_and_check(axis=0, position=self._scan_params["start"][0])

        # Move to the current row
        self._move_and_check(axis=1, position=self._scan_params["rows"][row])

        # Scan row *repeat* times
        for _ in range(int(repeat)):
            # Check for beam conditions to be okay before scanning a row, if not wait
            self._wait_for_condition(
                condition_call=self.irrad_events.beam_ok,
                log_msg="Insufficient beam conditions. Waiting for beam to stabilize...",
                log_level="WARNING",
                check_call=self._check_abort,
            )  # If beam does not recover and we need to stop manually

            # Publish if we have a socket
            if data_pub is not None:
                # Publish data
                _meta = {"timestamp": time.time(), "name": self.zmq_config["sender"], "type": "scan"}
                _data = {
                    "status": "scan_start",
                    "scan": scan,
                    "row": row,
                    "speed": self.scan_stage.axis[0].get_speed(unit="mm/s"),
                    "accel": self.scan_stage.axis[0].get_accel(unit="mm/s^2"),
                    "x_start": self._get_position(axis=0, unit="mm"),
                    "y_start": self._get_position(axis=1, unit="mm"),
                }

                # Publish data
                data_pub.send_json({"meta": _meta, "data": _data})

            # Scan the current row
            self._move_and_check(axis=0, position=self._get_current_row_x_target())

            # Publish if we have a socket
            if data_pub is not None:
                # Publish stop data
                _meta = {"timestamp": time.time(), "name": self.zmq_config["sender"], "type": "scan"}
                _data = {
                    "status": "scan_stop",
                    "x_stop": self._get_position(axis=0, unit="mm"),
                    "y_stop": self._get_position(axis=1, unit="mm"),
                }

                # Publish data
                data_pub.send_json({"meta": _meta, "data": _data})

        if from_origin:
            self._return_to_origin()

        if data_pub is not None:
            # Publish stop data
            _meta = {"timestamp": time.time(), "name": self.zmq_config["sender"], "type": "scan"}
            _data = {"status": "scan_row_completed", "scan": scan, "row": row}

            # Publish data
            data_pub.send_json({"meta": _meta, "data": _data})

        if spawn_pub:
            data_pub.close()

    def _scan_device(self, speed=None, repeat=None):
        """
        Method which is supposed to be called by self.scan_device. See docstring there.

        """

        # Check scan configuration dict
        if not self._check_scan():
            return

        # Calculate the target scan number from the current scan number and the number of repetitions
        # Needed because its possible to perform full scan after main scan so scan number will not be 0
        if repeat is not None:
            target_scan_number = self.n_complete_scan + repeat

        # Initialize zmq data publisher if zmq is setup
        data_pub = (
            None
            if not self.zmq_config
            else create_pub_from_ctx(ctx=self.zmq_config["ctx"], addr=self.zmq_config["addr"])
        )

        # Move to start point
        self._move_and_check(axis=0, position=self._scan_params["start"][0])
        self._move_and_check(axis=1, position=self._scan_params["start"][1])

        # Set the scan speed
        self.scan_stage.set_speed(
            value=self._scan_params["scan_speed"] if speed is None else speed, axis=0, unit="mm/s"
        )

        if data_pub is not None:
            # Initialize scan
            _meta = {"timestamp": time.time(), "name": self.zmq_config["sender"], "type": "scan"}
            _data = {
                "status": "scan_init",
                "row_sep": self._scan_params["row_sep"],
                "n_rows": self._scan_params["n_rows"],
                "aim_damage": self.scan_config["aim_damage"],
                "aim_value": self.scan_config["aim_value"],
                "min_current": self.scan_config["min_current"],
                "scan_origin": tuple(
                    self.scan_stage.axis[i].convert_to_unit(self._scan_params["origin"][i], "mm") for i in range(2)
                ),
                "scan_area_start": tuple(
                    self.scan_stage.axis[i].convert_to_unit(self._scan_params["start"][i], "mm") for i in range(2)
                ),
                "scan_area_stop": tuple(
                    self.scan_stage.axis[i].convert_to_unit(self._scan_params["end"][i], "mm") for i in range(2)
                ),
                "dut_rect_start": self._scan_params["dut_rect_start"],
                "dut_rect_stop": self._scan_params["dut_rect_stop"],
                "beam_fwhm": self.scan_config["beam_fwhm"],
            }

            # Put init data
            data_pub.send_json({"meta": _meta, "data": _data})

        # Start actual scan: each scan is counted as one coverage of the entire area
        try:
            # Initialize rows of scan for top to bottom and bottom to top scan; reuse to safe resources
            top_to_bottom_rows = range(self._scan_params["n_rows"])
            bottom_to_top_rows = range(
                self._scan_params["n_rows"] - 1, -1, -1
            )  # Same as reversed, but not iterator -> can be reused

            # Loop until self.interaction_events['abort'] or self.interaction_events['finish']
            while not any(self.interaction_events[iv].wait(self._event_wait_time) for iv in ("abort", "finish")):
                # Break if the scan is completed either by the corresponding event or the number of repetitions of full scans
                if repeat is None:
                    if self.irrad_events.IrradiationComplete.value.is_valid():
                        break
                else:
                    if self.n_complete_scan == target_scan_number:
                        break

                # Pause scan indefinitely until manually resuming
                self._wait_for_condition(
                    condition_call=lambda: not self.interaction_events["pause"].wait(self._event_wait_time),
                    log_msg=f"Scan paused after {self.n_complete_scan} scans. Waiting to continue",
                    log_level="INFO",
                )

                # Determine whether we're scanning top to bottom or opposite
                current_rows = top_to_bottom_rows if self.n_complete_scan % 2 == 0 else bottom_to_top_rows

                # Loop over rows
                for row in current_rows:
                    # Check for emergency stop; if so, raise error
                    if self.interaction_events["abort"].wait(self._event_wait_time):
                        raise ScanError("Scan was stopped manually")

                    # Scan row
                    self._scan_row(row=row, scan=self.n_complete_scan, data_pub=data_pub, from_origin=False)

                _meta = {"timestamp": time.time(), "name": self._scan_params["server"], "type": "scan"}
                _data = {"status": "scan_complete", "scan": self.n_complete_scan}

                data_pub.send_json({"meta": _meta, "data": _data})

                # Increment
                self.n_complete_scan += 1

        # Some axis command didn't succeed or emergency exit was issued
        except ScanError:
            logging.exception("Scan aborted!")

        finally:
            if data_pub is not None:
                # Put finished data
                _meta = {"timestamp": time.time(), "name": self.zmq_config["sender"], "type": "scan"}
                _data = {"status": "scan_finished"}

                # Publish data
                data_pub.send_json({"meta": _meta, "data": _data})

                data_pub.close()

            self._return_to_origin()

            # Reset signal so one can scan again
            for _, e in self.interaction_events.items():
                e.clear()

            # Log stage errors if present
            if self._position_errors:
                msg = f"{self._position_errors} position readback error(s) occured during scan."
                logging.warning(msg)
