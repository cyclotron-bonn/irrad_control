"""Collection of dtypes for numpy structured arrays used within the analysis / interpretation"""
import numpy as np
from dataclasses import dataclass


# Event dtype; used to log events such as beam current shutdowns, state changes etc
_event_dtype = [('timestamp', '<f8'),
                ('event', '<S64'),
                ('parameters', '<S256')]

# Motorstage data type; contains motorstage positions and parameters
_motorstage_dtype = [('timestamp', '<f8'),  # Timestamp [s]
                     ('axis', '<i1'),  # Integer which corresponds to axis (0->x, 1->y, ...)
                     ('movement_status', 'S10'),  # String stating whether stage starts or stops movement
                     ('position', '<f4'),  # Position at movement status [mm]
                     ('speed', '<f4'),  # Speed at movement status [mm/s]
                     ('accel', '<f4'),  # Acceleration at movement status [mm/s2]
                     ('travel', '<f4')]  # Travel [mm]

# Beam data type: contains info about beam current and position from primary and secondary signals
_beam_dtype = [('timestamp', '<f8'),  # Timestamp of current measurement [s]
               ('beam_current', '<f4'),  # Beam current value [A]
               ('beam_current_error', '<f4'),  # Error of the beam current e.g. measurement error [A]
               ('reconstructed_beam_current', '<f4'),  # Beam current value reconstructed from signal after ADC instead of analog signal [A]
               ('beam_loss', '<f4'),  # Beam current loss at extraction, detected by Beam-Loss-Monitor [A]
               ('horizontal_beam_position', '<f4'),  # Relative x position of the mean of the beam distribution [%]
               ('vertical_beam_position', '<f4')]  # Relative y position of the mean of the beam distribution [%]

# Scan data type: contains the data gathered while scanning samples through the particle beam.
_scan_dtype = [('scan', '<i2'),  # Number of current scan
               ('row', '<i2'),  # Number of current row
               ('row_start_timestamp', '<f8'),  # Posix-timestamp when beginning to scan a row [s]
               ('row_stop_timestamp', '<f8'),  # Posix-timestamp when ending to scan a row [s]
               ('row_start_x', '<f4'),  # x component of the starting position of currently-scanned row [mm]
               ('row_start_y', '<f4'),  # y component of the starting position of currently-scanned row [mm]
               ('row_stop_x', '<f4'),  # x component of the stopping position of currently-scanned row [mm]
               ('row_stop_y', '<f4'),  # # y component of the stopping position of currently-scanned row [mm]
               ('row_mean_beam_current', '<f4'),  # Mean of the beam current during scanning current row [A]
               ('row_mean_beam_current_error', '<f4'),  # Error of the beam current; quadratic addition of std of beam current and measurement error [A]
               ('row_primary_fluence', '<f8'),  # The ion fluence during scanning current row [ions/cm^2]
               ('row_primary_fluence_error', '<f8'),  # Error of the ion fluence during scanning current row [ions/cm^2]
               ('row_tid', '<f4'),  # The TID during scanning current row [Mrad]
               ('row_tid_error', '<f4'),  # Error of the tid [Mrad]
               ('row_scan_speed', '<f4'),  # Speed with which the sample is scanned [mm/s]
               ('row_scan_accel', '<f4')]  # Acceleration with which scan speed is approached / slowed down [mm/s^2]

# Scan configuration data type: contains the initial scan configuration.
_irrad_dtype = [('timestamp', '<f8'),  # Posix-timestamp of init [s]
                ('row_separation', '<f4'),  # Row separation e.g. step size of scan, spacing in between scanned rows [mm]
                ('n_rows', '<i2'),  # Number of total rows in scan
                ('aim_damage', 'S4'),  # Either NIEL or TID
                ('aim_value', '<f4'),  # Nominal value of damage to be induced, either in neq/cm^2 or Mrad
                ('min_scan_current', '<f4'),  # Minimum current for scanning [A]
                ('scan_origin_x', '<f4'),  # x component of the scan origin from where the rel. coord. system is constructed [mm]
                ('scan_origin_y', '<f4'),  # y component of the scan origin from where the rel. coord. system is constructed [mm]
                ('scan_area_start_x', '<f4'),  # x component of the upper left corner of the scan area [mm]
                ('scan_area_start_y', '<f4'),  # y component of the upper left corner of the scan area [mm]
                ('scan_area_stop_x', '<f4'),  # x component of the lower right corner of the scan area [mm]
                ('scan_area_stop_y', '<f4')]  # Row separation e.g. step size of scan, spacing in between scanned rows [mm]

# Damage data dtype; contains NIEL and TID damage data on a per-scan basis
_damage_dtype = [('timestamp', '<f8'),  # Timestamp [s]
                 ('scan', '<i2'),  # Number of *completed* scans,
                 ('scan_primary_fluence', '<f8'),  # ion fluence delivered in this scan [ions/cm^2]
                 ('scan_primary_fluence_error', '<f8'),  # Error of ion fluence delivered in this scan [ions/cm^2]
                 ('scan_tid', '<f8'),  # Total-ionizing dose delivered in this scan [Mrad]
                 ('scan_tid_error', '<f8')]  # Error of total-ionizing dose delivered in this scan [Mrad]


# Result data type: contains ion as well as neutron fluence and scaling factor
_result_dtype = [('timestamp', '<f8'),
                 ('primary_fluence', '<f8'),
                 ('primary_fluence_error', '<f8'),
                 ('neq_fluence', '<f8'),
                 ('neq_fluence_error', '<f8'),
                 ('tid', '<f4'),
                 ('tid_error', '<f4')]


@dataclass
class IrradDtypes:

    event = np.dtype(_event_dtype)
    motorstage = np.dtype(_motorstage_dtype)
    beam = np.dtype(_beam_dtype)
    scan = np.dtype(_scan_dtype)
    irrad = np.dtype(_irrad_dtype)
    damage = np.dtype(_damage_dtype)
    result = np.dtype(_result_dtype)

    def generic_dtype(self, names, dtypes=None, default_dtype='<f4'):

        dtypes = [default_dtype] * len(names) if dtypes is None else dtypes

        return np.dtype(list(zip(names, dtypes)))

    def __getitem__(self, item):
        if hasattr(self, item) and isinstance(getattr(self, item), np.dtype):
            return getattr(self, item)
        else:
            raise KeyError("IrradDtypes do not contain {}".format(item))


@dataclass
class IrradHists:

    beam_position = {'unit': 'percent', 'bins': (100, 100), 'range': [(-110, 110), (-110, 110)]}
    sey_horizontal = {'unit': 'percent', 'bins': 50, 'range': (0, 110)}
    sey_vertical = {'unit': 'percent', 'bins': 50, 'range': (0, 110)}

    def create_hist(self, hist_name, return_edges=True, return_centers=True):
        hist_dict = self.__getitem__(hist_name)
        hist = np.zeros(shape=hist_dict['bins'])

        if len(hist.shape) == 1:
            edges = np.linspace(hist_dict['range'][0], hist_dict['range'][1], hist_dict['bins'] + 1)
            centers = 0.5 * (edges[1:] + edges[:-1])
        else:
            edges = [np.linspace(hist_dict['range'][i][0], hist_dict['range'][i][1], hist_dict['bins'][i] + 1) for i in range(len(hist.shape))]
            centers = [0.5 * (edges[i][1:] + edges[i][:-1]) for i in range(len(hist.shape))]
        res = [hist]

        if return_edges:
            res.append(edges)
        if return_centers:
            res.append(centers)

        return tuple(res) if len(res) != 1 else res[0]

    def __getitem__(self, item):
        if hasattr(self, item) and isinstance(getattr(self, item), dict):
            return getattr(self, item)
        else:
            raise KeyError("IrradHists do not contain {}".format(item))
