"""Collection of dtypes for numpy structured arrays used within the analysis / interpretation"""
from dataclasses import dataclass
from numpy import dtype


# Event dtype; used to log events such as beam current shutdowns, state changes etc
_event_dtype = [('timestamp', '<f4'),
                ('event', 'U64'),
                ('parameters', 'U256')]

# Motorstage data type; contains motorstage positions and parameters
_motorstage_dtype = [('timestamp', '<f4'),  # Timestamp [s]
                     ('axis_id', '<i1'),  # Integer which corresponds to axis (0->x, 1->y, ...)
                     ('movement_status', 'U10'),  # String stating whether stage starts or stops movement
                     ('position', '<f4'),  # Position at movement status
                     ('speed', '<f4'),  # Speed at movement status
                     ('accel', '<f4'),  # Acceleration at movement status
                     ('travel', '<f4')]  # Travel

# Beam data type: contains info about beam current and position from primary and secondary signals
_beam_dtype = [('timestamp', '<f4'),  # Timestamp of current measurement [s]
               ('beam_current', '<f4'),  # Beam current value [A]
               ('beam_current_error', '<f4'),  # Error of the beam current e.g. measurement error [A]
               ('reconstructed_beam_current', '<f4'),  # Beam current value reconstructed from signal after ADC instead of analog signal [A]
               ('reconstructed_beam_current_error', '<f4'),  # Error of beam current value reconstructed from signal after ADC instead of analog signal [A]
               ('horizontal_beam_position', '<f4'),  # Relative x position of the mean of the beam distribution [%]
               ('vertical_beam_position', '<f4')]  # Relative y position of the mean of the beam distribution [%]

# Scan data type: contains the data gathered while scanning samples through the particle beam.
_scan_dtype = [('scan', '<i2'),  # Number of current scan
               ('row', '<i2'),  # Number of current row
               ('row_start_timestamp', '<f4'),  # Posix-timestamp when beginning to scan a row [s]
               ('row_stop_timestamp', '<f4'),  # Posix-timestamp when ending to scan a row [s]
               ('row_start_x', '<f4'),  # x component of the starting position of currently-scanned row [mm]
               ('row_start_y', '<f4'),  # y component of the starting position of currently-scanned row [mm]
               ('row_stop_x', '<f4'),  # x component of the stopping position of currently-scanned row [mm]
               ('row_stop_y', '<f4'),  # # y component of the stopping position of currently-scanned row [mm]
               ('row_mean_beam_current', '<f4'),  # Mean of the beam current during scanning current row [nA]
               ('row_mean_beam_current_err', '<f4'),  # Error of the beam current; quadratic addition of std of beam current and measurement error [nA]
               ('row_scan_speed', '<f4'),  # Speed with which the sample is scanned [mm/s]
               ('row_separation', '<f4')]  # Row separation e.g. step size of scan, spacing in between scanned rows [mm]

# Damage data dtype; contains NIEL and TID damage data on a per-scan basis
_damage_dtype = [('timestamp', '<f4'), # Timestamp [s]
                 ('scan', '<i2'),  # Number of *completed* scans,
                 ('scan_proton_fluence', '<f8'),  # Proton fluence delivered in this scan [protons/cm^2]
                 ('scan_proton_fluence_error', '<f8'),  # Error of proton fluence delivered in this scan [protons/cm^2]
                 ('scan_tid', '<f8'),  # Total-ionizing dose delivered in this scan [Mrad]
                 ('scan_tid_error', '<f8')]  # Error of total-ionizing dose delivered in this scan [Mrad]


# Result data type: contains proton as well as neutron fluence and scaling factor
_result_dtype = [('proton_fluence', '<f8'),
                 ('proton_fluence_error', '<f8'),
                 ('neutron_fluence', '<f8'),
                 ('neutron_fluence_error', '<f8'),
                 ('tid', '<f8'),
                 ('tid_error', '<f8')]


@dataclass
class IrradDtypes:

    event = dtype(_event_dtype)
    motorstage = dtype(_motorstage_dtype)
    beam = dtype(_beam_dtype)
    scan = dtype(_scan_dtype)
    damage = dtype(_damage_dtype)
    result = dtype(_result_dtype)

    def generic_dtype(self, names, dtypes=None, default_dtype='<f4'):

        dtypes = [default_dtype] * len(names) if dtypes is None else dtypes

        return dtype(list(zip(names, dtypes)))
