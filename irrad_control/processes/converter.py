import logging
import numpy as np
import tables as tb
from time import time
from threading import Event
from collections import defaultdict
from uncertainties import ufloat, unumpy

# Package imports
import irrad_control.analysis as analysis
import irrad_control.devices.readout as ro
from irrad_control.processes.daq import DAQProcess


class IrradConverter(DAQProcess):
    """Interpreter process for irradiation site data"""

    def __init__(self, name=None):

        # Set name of this interpreter process
        name = 'interpreter' if name is None else name

        # Attributes controlling converter behaviour
        self._data_flush_interval = 1.0
        self._last_data_flush = None
        self._n_offset_samples = 100
        self._beam_cut_off_threshold = 0.1
        self._beam_correction_threshold = 0.05

        self.dtypes = analysis.dtype.IrradDtypes()
        self.hists = analysis.dtype.IrradHists()

        # Call init of super class
        super(IrradConverter, self).__init__(name=name)

    def _setup_daq(self):

        # Open only one output file and organize its data in groups
        self.output_table = tb.open_file(self.setup['session']['outfile'] + '.h5', 'w')

        # General setup; servers
        self.server = list(self.setup['server'].keys())

        self.interaction_flags = {server: {'write': Event(),
                                           'offset': Event()} for server in self.server}

        # We want to start writing data from every server from the start
        _ = [self.interaction_flags[s]['write'].set() for s in self.server]

        # Containers to hold data
        # Store tables
        self.data_tables = defaultdict(dict)

        # Store data per interpretation cycle
        self.data_arrays = defaultdict(dict)

        # Store hist data
        self.data_hists = defaultdict(dict)

        # Flag indicating whether to store data
        self.data_flags = defaultdict(dict)

        # Dict with lists to append beam current values to during scanning
        self._scan_currents = defaultdict(list)
        self._ntc_temps = defaultdict(dict)
        self._lookups = defaultdict(dict)
        self._raw_offsets = {}
        self._row_fluence_hist = {}
        self._dtimes = defaultdict(dict)
        self._daq_params = defaultdict(dict)

        # R/O setup per server
        self.readout_setup = {}

        for server, server_setup in self.setup['server'].items():
            self._add_server_data(server=server, server_setup=server_setup)
            self._setup_daq_parameters(server=server, server_setup=server_setup)

        self._scan_number = None

    def _add_server_data(self, server, server_setup):
        """Adds a group to the ouptut table for respective server"""

        # Create group at root
        self.output_table.create_group(self.output_table.root, server_setup['name'])

        # Dedicated flag for NTC readout of DAQ Board
        has_ntc_daq_board_ro = False

        if 'readout' in server_setup:

            self.readout_setup[server] = server_setup['readout']

            if 'ntc' in server_setup['readout']:
                has_ntc_daq_board_ro = True

            # Fill lookup dicts
            self._lookups[server]['ro_type_idx'] = {rt: server_setup['readout']['types'].index(rt) for rt in ro.RO_TYPES
                                                    if rt in server_setup['readout']['types']}

            self._lookups[server]['sem_foils'] = [ch for ch in self._lookups[server]['ro_type_idx'] if 'sem' in ch and 'sum' not in ch]
            self._lookups[server]['sem_h'] = all(x in self._lookups[server]['ro_type_idx'] for x in ('sem_left', 'sem_right'))
            self._lookups[server]['sem_v'] = all(x in self._lookups[server]['ro_type_idx'] for x in ('sem_up', 'sem_down'))
            self._lookups[server]['offset_ch'] = set([ch for ch in self._lookups[server]['ro_type_idx'] if 'ntc' not in ch])
            self._lookups[server]['full_scale_voltage'] = 5.0 if self.readout_setup[server]['device'] != ro.RO_DEVICES.DAQBoard else 2 * ro.DAQ_BOARD_CONFIG['common']['voltages']['2V5p']

            self._raw_offsets[server] = defaultdict(list)

            self.data_flags[server]['scanning'] = False

            # Create needed tables and arrays
            for dname in ('Raw', 'RawOffset', 'Event', 'Beam', 'Damage', 'Scan', 'Irrad', 'Result'):

                try:
                    dtype = self.dtypes[dname.lower()]
                except KeyError:  # Raw and RawOffset data
                    names = ['timestamp'] + self.readout_setup[server]['channels']
                    dtype = self.dtypes.generic_dtype(names=names, dtypes=['<f8']+['<f4']*(len(names)-1))

                # Create and store tables
                self.data_tables[server][dname.lower()] = self.output_table.create_table('/{}'.format(server_setup['name']),
                                                                                         description=dtype,
                                                                                         name=dname)
                # Create arrays
                self.data_arrays[server][dname.lower()] = np.zeros(shape=1, dtype=dtype)

                # Create data flags
                self.data_flags[server][dname.lower()] = False

            # Create histogram group and entries
            self.output_table.create_group('/{}'.format(server_setup['name']), 'Histogram')
            for hist_name in ('beam_position', 'sey_horizontal', 'sey_vertical'):
                hist, edges, centers = self.hists.create_hist(hist_name=hist_name)

                self.data_hists[server][hist_name] = {'meta': {'unit': self.hists[hist_name]['unit'], 'edges': edges, 'centers': centers}, 'hist': hist}

                table_name = '{}{}'.format(*[n.capitalize() for n in hist_name.split('_')])
                # Create group for histogram
                self.output_table.create_group('/{}/Histogram'.format(server_setup['name']), table_name)

                # Add meta data arrays for hist
                self.output_table.create_array('/{}/Histogram/{}'.format(server_setup['name'], table_name), 'edges', edges)
                self.output_table.create_array('/{}/Histogram/{}'.format(server_setup['name'], table_name), 'centers', centers)
                self.output_table.create_array('/{}/Histogram/{}'.format(server_setup['name'], table_name), 'unit', np.array([self.hists[hist_name]['unit']]))

        # We have temperature data
        if has_ntc_daq_board_ro or 'ArduinoNTCReadout' in server_setup['devices']:

            # Make temperature measurement group in outfile
            # Create group at root
            self.output_table.create_group('/{}'.format(server_setup['name']), 'Temperature')

            if has_ntc_daq_board_ro:

                dtype = self.dtypes.generic_dtype(names=['timestamp', 'ntc_channel', 'temperature'],
                                                  dtypes=['<f8', '<S{}'.format(np.max([len(s) for s in server_setup['readout']['ntc'].values()])), '<f2'])
                dname = 'temp_daq_board'
                node_name = 'DAQBoard'

                # Channel on which the NTC voltages are cycled
                self._lookups[server]['ntc_group_idx'] = self.readout_setup[server]['ch_groups'].index('ntc')

                # Create and store tables
                self.data_tables[server][dname] = self.output_table.create_table('/{}/Temperature'.format(server_setup['name']),
                                                                                 description=dtype,
                                                                                 name=node_name)
                # Create arrays
                self.data_arrays[server][dname] = np.zeros(shape=1, dtype=dtype)

                # Add flag
                self.data_flags[server][dname] = False

            if 'ArduinoNTCReadout' in server_setup['devices']:
                names = ['timestamp'] + list(server_setup['devices']['ArduinoNTCReadout']['setup'].values())
                dtype = self.dtypes.generic_dtype(names=names, dtypes=['<f8']+['<f4']*(len(names)-1))
                dname = 'temp_arduino'
                node_name = 'ArduinoNTCReadout'

                # Create and store tables
                self.data_tables[server][dname] = self.output_table.create_table('/{}/Temperature'.format(server_setup['name']),
                                                                                 description=dtype,
                                                                                 name=node_name)
                # Create arrays
                self.data_arrays[server][dname] = np.zeros(shape=1, dtype=dtype)

                # Add flag
                self.data_flags[server][dname] = False

        # We have motorstage data
        # FIXME: make flag for devices that are stages instead of hardcode
        for motorstage in ('ScanStage', 'SetupTableStage', 'ExternalCupStage'):

            if motorstage in server_setup['devices']:

                # Create group at root because we have a motorstage
                if '/{}/Motorstage'.format(server_setup['name']) not in self.output_table:
                    self.output_table.create_group('/{}'.format(server_setup['name']), 'Motorstage')

                dtype = self.dtypes['motorstage']
                dname = f'motorstage_{motorstage.lower()}'
                node_name = motorstage

                # Create and store tables
                self.data_tables[server][dname] = self.output_table.create_table('/{}/Motorstage'.format(server_setup['name']),
                                                                                 description=dtype,
                                                                                 name=node_name)
                # Create arrays
                self.data_arrays[server][dname] = np.zeros(shape=1, dtype=dtype)

                # Add flag
                self.data_flags[server][dname] = False

        if 'RadiationMonitor' in server_setup['devices']:
            
            names = ['timestamp', 'dose_rate', 'frequency']
            dtype = self.dtypes.generic_dtype(names=names, dtypes=['<f8', '<f4', '<f4'])
            dname = 'rad_monitor'
            node_name = 'RadMonitor'

            # Create and store tables
            self.data_tables[server][dname] = self.output_table.create_table('/{}'.format(server_setup['name']),
                                                                                description=dtype,
                                                                                name=node_name)
            # Create arrays
            self.data_arrays[server][dname] = np.zeros(shape=1, dtype=dtype)

            # Add flag
            self.data_flags[server][dname] = False

    def _setup_daq_parameters(self, server, server_setup):
        
        daq_setup = server_setup['daq']

        self._daq_params[server]['stopping_power'] = daq_setup['stopping_power'] or np.nan
        self._daq_params[server]['kappa'] = (np.nan, np.nan) if daq_setup['kappa'] is None else (daq_setup['kappa']['nominal'], daq_setup['kappa']['sigma'])
        self._daq_params[server]['lambda'] = (np.nan, np.nan) if daq_setup['lambda'] is None else (daq_setup['lambda']['nominal'], daq_setup['lambda']['sigma'])
            
    def _calc_drate(self, server, meta):

        # Check if we have incoming data timing stored
        if meta['type'] not in self._dtimes[server]:
            self._dtimes[server][meta['type']] = time()
            return

        # Calc data rate
        now = time()
        drate = 1. / (now - self._dtimes[server][meta['type']])
        self._dtimes[server][meta['type']] = now

        # Write data rate to meta
        meta['data_rate'] = drate

    def _get_raw_offset(self, server, data):

        # Loop over data until sufficient data for mean is collected
        for ch in data:

            self._raw_offsets[server][ch].append(self.data_arrays[server]['raw'][ch][0])

            if len(self._raw_offsets[server][ch]) == self._n_offset_samples:
                self.data_arrays[server]['rawoffset'][ch] = np.mean(self._raw_offsets[server][ch])

        # If all offsets have been found, clear signal and reset list
        if all(len(self._raw_offsets[server][ch]) >= self._n_offset_samples for ch in data):
            self.interaction_flags[server]['offset'].clear()
            self._raw_offsets[server] = defaultdict(list)
            self.data_arrays[server]['rawoffset']['timestamp'] = time()
            self.data_flags[server]['rawoffset'] = True

    def _get_full_scale_current(self, server, ch_idx, ro_device):
        """Get a channels full scale current wrt the readout device"""

        if ro_device == ro.RO_DEVICES.DAQBoard:
            ch_group = self.readout_setup[server]['ch_groups'][ch_idx]
            i_full_scale = self.readout_setup[server]['ro_group_scales'][ch_group]
        else:
            i_full_scale = self.readout_setup[server]['ro_scales'][ch_idx]

        return i_full_scale * analysis.constants.nano  # nA

    def _calc_mean_and_error(self, data):

        # Calculate mean and error on mean
        mean_w_err = np.mean(data)

        # Uncertainty on mean is error and std quadratically added
        if hasattr(mean_w_err, 'n') and hasattr(mean_w_err, 's'):
            res = mean_w_err.n, (mean_w_err.s ** 2 + unumpy.nominal_values(data).std() ** 2) ** 0.5
        else:
            res = mean_w_err, np.std(data)

        return res

    def _update_hist_entries(self, server, beam_data):

        hist_data = {'meta': {'timestamp': beam_data['meta']['timestamp'], 'name': server, 'type': 'hist'},
                     'data': {}}

        # Update histograms
        # Beam position
        bp_h_idx = analysis.formulas.get_hist_idx(val=beam_data['data']['position']['h'],
                                                  bin_edges=self.data_hists[server]['beam_position']['meta']['edges'][0])
        bp_v_idx = analysis.formulas.get_hist_idx(val=beam_data['data']['position']['v'],
                                                  bin_edges=self.data_hists[server]['beam_position']['meta']['edges'][1])
        try:
            self.data_hists[server]['beam_position']['hist'][bp_h_idx, bp_v_idx] += 1
            hist_data['data']['beam_position_idxs'] = (bp_h_idx, bp_v_idx)
        except IndexError:
            pass
        # SEY fraction
        for plane in ('horizontal', 'vertical'):
            try:
                sey_frac = beam_data['data']['sey'][plane[0]] / beam_data['data']['sey']['sum'] * 100
                sey_idx = analysis.formulas.get_hist_idx(val=sey_frac,
                                                         bin_edges=self.data_hists[server]['sey_{}'.format(plane)]['meta']['edges'])
                self.data_hists[server]['sey_{}'.format(plane)]['hist'][sey_idx] += 1
                hist_data['data']['sey_{}_idx'.format(plane)] = sey_idx
            except (ZeroDivisionError, IndexError):
                pass

        return hist_data

    def _interpret_event(self, server, event, parameters):

        self.data_arrays[server]['event']['timestamp'] = time()
        self.data_arrays[server]['event']['event'] = event.encode('ascii')
        self.data_arrays[server]['event']['parameters'] = parameters.encode('ascii')

        self.data_flags[server]['event'] = True

    def _interpret_raw_data(self, server, data, meta):

        raw_data = {'meta': {'timestamp': meta['timestamp'], 'name': server, 'type': 'raw'},
                    'data': {'voltage': {}, 'current': {}}}

        # Get timestamp from data for beam and raw arrays
        self.data_arrays[server]['raw']['timestamp'] = meta['timestamp']

        for ch in data:

            # Fill raw data structured array first
            self.data_arrays[server]['raw'][ch] = data[ch]

            ch_idx = self.readout_setup[server]['channels'].index(ch)

            # Subtract offset from data; initially offset is 0 for all ch
            if self.readout_setup[server]['types'][ch_idx] in self._lookups[server]['offset_ch']:
                data[ch] -= self.data_arrays[server]['rawoffset'][ch][0]

                raw_data['data']['current'][ch] = analysis.formulas.v_sig_to_i_sig(v_sig=data[ch],
                                                                                   full_scale_current=self._get_full_scale_current(server, ch_idx, self.readout_setup[server]['device']),
                                                                                   full_scale_voltage=self._lookups[server]['full_scale_voltage'])

                if 'sem_sum' in self._lookups[server]['ro_type_idx'] and self._lookups[server]['ro_type_idx']['sem_sum'] == ch_idx:
                    raw_data['data']['current'][ch] *= 4

            raw_data['data']['voltage'][ch] = data[ch]

        # Append data to table within this interpretation cycle
        self.data_flags[server]['raw'] = True

        return raw_data

    def _interpret_beam_data(self, server, data, meta):

        beam_data = {'meta': {'timestamp': meta['timestamp'], 'name': server, 'type': 'beam'},
                     'data': {'position': {}, 'current': {}, 'sey': {}}}

        # Get timestamp from data for beam data arrays
        self.data_arrays[server]['beam']['timestamp'] = meta['timestamp']

        for dname in self.data_arrays[server]['beam'].dtype.names:

            # Beam position
            if 'position' in dname:

                plane = 'h' if dname.split('_')[0] == 'horizontal' else 'v'

                if plane == 'h' and self._lookups[server]['sem_h']:
                    idx_L, idx_R = self._lookups[server]['ro_type_idx']['sem_left'], self._lookups[server]['ro_type_idx']['sem_right']
                    sig_L, sig_R = data[self.readout_setup[server]['channels'][idx_L]], data[self.readout_setup[server]['channels'][idx_R]]

                    # Scale voltage signal to current; signals can have different R/O scales
                    sig_L = analysis.formulas.v_sig_to_i_sig(v_sig=sig_L,
                                                             full_scale_current=self._get_full_scale_current(server, idx_L, self.readout_setup[server]['device']),
                                                             full_scale_voltage=self._lookups[server]['full_scale_voltage'])
                    sig_R = analysis.formulas.v_sig_to_i_sig(v_sig=sig_R,
                                                             full_scale_current=self._get_full_scale_current(server, idx_R, self.readout_setup[server]['device']),
                                                             full_scale_voltage=self._lookups[server]['full_scale_voltage'])

                    beam_data['data']['sey']['h'] = sig_L + sig_R

                    rel_pos = analysis.formulas.rel_beam_position(sig_a=sig_L, sig_b=sig_R, plane=plane)

                elif plane == 'v' and self._lookups[server]['sem_v']:
                    idx_U, idx_D = self._lookups[server]['ro_type_idx']['sem_up'], self._lookups[server]['ro_type_idx']['sem_down']
                    sig_U, sig_D = data[self.readout_setup[server]['channels'][idx_U]], data[self.readout_setup[server]['channels'][idx_D]]

                    # Scale voltage signal to current; signals can have different R/O scales
                    sig_U = analysis.formulas.v_sig_to_i_sig(v_sig=sig_U,
                                                             full_scale_current=self._get_full_scale_current(server, idx_U, self.readout_setup[server]['device']),
                                                             full_scale_voltage=self._lookups[server]['full_scale_voltage'])
                    sig_D = analysis.formulas.v_sig_to_i_sig(v_sig=sig_D,
                                                             full_scale_current=self._get_full_scale_current(server, idx_D, self.readout_setup[server]['device']),
                                                             full_scale_voltage=self._lookups[server]['full_scale_voltage'])

                    beam_data['data']['sey']['v'] = sig_U + sig_D

                    rel_pos = analysis.formulas.rel_beam_position(sig_a=sig_U, sig_b=sig_D, plane=plane)

                else:
                    logging.warning("Beam position can not be calculated!")
                    rel_pos = np.nan

                self.data_arrays[server]['beam'][dname] = beam_data['data']['position'][plane] = rel_pos

            # Beam current
            elif 'beam_current' in dname:

                current = 0
                n_foils = len(self._lookups[server]['sem_foils'])

                if 'reconstructed' in dname:

                    if n_foils not in (2, 4):
                        msg = "Reconstructed beam current must be derived from 2 or 4 foils (currently {})".format(n_foils)
                        logging.warning(msg)

                    foil_idxs = [self._lookups[server]['ro_type_idx'][ch] for ch in self._lookups[server]['sem_foils']]

                    for idx in foil_idxs:
                        bc = analysis.formulas.calibrated_beam_current(beam_monitor_sig=data[self.readout_setup[server]['channels'][idx]],
                                                                       calibration_factor=self._daq_params[server]['lambda'][0],
                                                                       full_scale_current=self._get_full_scale_current(server=server, ch_idx=idx,
                                                                                                                       ro_device=self.readout_setup[server]['device']))
                        current += bc / n_foils

                else:
                    if 'sem_sum' in self._lookups[server]['ro_type_idx']:
                        sum_idx = self._lookups[server]['ro_type_idx']['sem_sum']
                        current = analysis.formulas.calibrated_beam_current(beam_monitor_sig=data[self.readout_setup[server]['channels'][sum_idx]],
                                                                            calibration_factor=self._daq_params[server]['lambda'][0],
                                                                            full_scale_current=self._get_full_scale_current(server=server, ch_idx=sum_idx,
                                                                                                                            ro_device=self.readout_setup[server]['device']))
                        if 'error' in dname:
                            # FIXME: calculate error according to uncertainty on calibration
                            # Error on current measurement is Delta I = 3.3% I + 1% R_FS
                            current *= 0.033
                            current += 0.01 * self._get_full_scale_current(server=server,
                                                                           ch_idx=self._lookups[server]['ro_type_idx']['sem_sum'],
                                                                           ro_device=self.readout_setup[server]['device'])
                        else:
                            # Calculate sum SE current
                            beam_data['data']['sey']['sum'] = analysis.formulas.v_sig_to_i_sig(v_sig=data[self.readout_setup[server]['channels'][sum_idx]] * n_foils,
                                                                                               full_scale_current=self._get_full_scale_current(server, sum_idx, self.readout_setup[server]['device']),
                                                                                               full_scale_voltage=self._lookups[server]['full_scale_voltage'])
                    else:
                        msg = "Beam current cannot be calculated from calibration due to calibration signal of type 'sem_sum' missing"
                        logging.warning(msg)

                self.data_arrays[server]['beam'][dname] = beam_data['data']['current'][dname] = current

            elif 'loss' in dname:
                if 'blm' in self._lookups[server]['ro_type_idx']:
                    blm_idx = self._lookups[server]['ro_type_idx']['blm']
                    blm_current = analysis.formulas.v_sig_to_i_sig(v_sig=data[self.readout_setup[server]['channels'][blm_idx]],
                                                                   full_scale_current=self._get_full_scale_current(server=server,
                                                                                                                   ch_idx=blm_idx,
                                                                                                                   ro_device=self.readout_setup[server]['device']),
                                                                   full_scale_voltage=self._lookups[server]['full_scale_voltage'])

                    # Only add beam loss to data if we have BLM data
                    beam_data['data']['current']['beam_loss'] = blm_current

                    # This should always be the case, at leasanything else is unphysical  
                    if blm_current <= self.data_arrays[server]['beam']['beam_current'][0]:
                        
                        try:
                            # Get beam loss
                            beam_loss = blm_current / self.data_arrays[server]['beam']['beam_current'][0]

                            # Warn when cut-off is detected
                            if beam_loss >= self._beam_cut_off_threshold:
                                logging.warning("Beam cut-off detected! Losing {:.2f} % of beam at extraction!".format(beam_loss * 100))

                            # Warn when extracted beam current is corrected
                            if beam_loss >= self._beam_correction_threshold:
                                extracted_current = self.data_arrays[server]['beam']['beam_current'][0] - blm_current
                                logging.warning("Correcting extracted beam current from {:.2E} A to {:.2E} A".format(self.data_arrays[server]['beam']['beam_current'][0],
                                                                                                                extracted_current))
                                self.data_arrays[server]['beam']['beam_current'] = extracted_current

                        except ZeroDivisionError:
                            pass
                    
                    # This case should not exist because blm_current can be at most beam current
                    # Due to different sampling timestamps for the ADC channels, this can occure in unstable beam conditions
                    # See https://github.com/SiLab-Bonn/irrad_control/issues/69
                    else:
                        self.data_arrays[server]['beam']['beam_current'] = 0

                else:
                    blm_current = np.nan

                self.data_arrays[server]['beam'][dname] = blm_current

        # Calc SEY fractions
        if 'sum' in beam_data['data']['sey']:
            try:
                if 'h' in beam_data['data']['sey']:
                    beam_data['data']['sey']['frac_h'] = beam_data['data']['sey']['h']/beam_data['data']['sey']['sum'] * 100
                if 'v' in beam_data['data']['sey']:
                    beam_data['data']['sey']['frac_v'] = beam_data['data']['sey']['v']/beam_data['data']['sey']['sum'] * 100
            except ZeroDivisionError:
                pass

        # Add to beam current container if stage is scanning
        if self.data_flags[server]['scanning']:
            self._scan_currents[server].append(ufloat(self.data_arrays[server]['beam']['beam_current'][0],
                                                      self.data_arrays[server]['beam']['beam_current_error'][0]))

        # Append data to table within this interpretation cycle
        self.data_flags[server]['beam'] = True

        return beam_data

    def _interpret_scan_data(self, server, data, meta):

        scan_data = None

        if data['status'] == 'scan_init':

            self.data_arrays[server]['irrad']['timestamp'] = meta['timestamp']
            self.data_arrays[server]['irrad']['row_separation'] = data['row_sep']
            self.data_arrays[server]['irrad']['n_rows'] = data['n_rows']
            self.data_arrays[server]['irrad']['aim_damage'] = data['aim_damage'].encode('ascii')
            self.data_arrays[server]['irrad']['aim_value'] = data['aim_value']
            self.data_arrays[server]['irrad']['min_scan_current'] = data['min_current']
            self.data_arrays[server]['irrad']['scan_origin_x'] = data['scan_origin'][0]
            self.data_arrays[server]['irrad']['scan_origin_y'] = data['scan_origin'][1]
            self.data_arrays[server]['irrad']['scan_area_start_x'] = data['scan_area_start'][0]
            self.data_arrays[server]['irrad']['scan_area_start_y'] = data['scan_area_start'][1]
            self.data_arrays[server]['irrad']['scan_area_stop_x'] = data['scan_area_stop'][0]
            self.data_arrays[server]['irrad']['scan_area_stop_y'] = data['scan_area_stop'][1]

            # Fluence hist
            self._row_fluence_hist[server] = [0] * data['n_rows']

            # Append data to table within this interpretation cycle
            self.data_flags[server]['irrad'] = True

            # Make sure we are recoding data when we initialize a scan
            self.interaction_flags[server]['write'].set()

        elif data['status'] == 'scan_start':

            del self._scan_currents[server][:]
            self.data_flags[server]['scanning'] = True

            self.data_arrays[server]['scan']['row_start_timestamp'] = meta['timestamp']

            self.data_arrays[server]['scan']['scan'] = data['scan']
            self.data_arrays[server]['scan']['row'] = data['row']
            self.data_arrays[server]['scan']['row_start_x'] = data['x_start']
            self.data_arrays[server]['scan']['row_start_y'] = data['y_start']
            self.data_arrays[server]['scan']['row_scan_speed'] = data['speed']
            self.data_arrays[server]['scan']['row_scan_accel'] = data['accel']

        elif data['status'] == 'scan_stop':

            self.data_flags[server]['scanning'] = False

            # Calculate mean row fluence and error
            row_mean_beam_current, row_mean_beam_current_err = self._calc_mean_and_error(data=self._scan_currents[server])

            row_proton_fluence = analysis.formulas.proton_fluence_scan(proton_current=ufloat(row_mean_beam_current, row_mean_beam_current_err),
                                                                       scan_step=self.data_arrays[server]['irrad']['row_separation'][0],
                                                                       scan_speed=self.data_arrays[server]['scan']['row_scan_speed'][0])

            row_proton_tid = analysis.formulas.tid_scan(proton_fluence=row_proton_fluence, stopping_power=self._daq_params[server]['stopping_power'])

            self.data_arrays[server]['scan']['row_stop_timestamp'] = meta['timestamp']
            self.data_arrays[server]['scan']['row_stop_x'] = data['x_stop']
            self.data_arrays[server]['scan']['row_stop_y'] = data['y_stop']
            self.data_arrays[server]['scan']['row_mean_beam_current'] = row_mean_beam_current
            self.data_arrays[server]['scan']['row_mean_beam_current_error'] = row_mean_beam_current_err
            self.data_arrays[server]['scan']['row_proton_fluence'] = row_proton_fluence.n
            self.data_arrays[server]['scan']['row_proton_fluence_error'] = row_proton_fluence.s
            self.data_arrays[server]['scan']['row_tid'] = row_proton_tid.n
            self.data_arrays[server]['scan']['row_tid_error'] = row_proton_tid.s

            # Log
            logging.info("Row {} of scan {}: ({:.2E} +- {:.2E}) protons / cm^2 and ({:.2E} +- {:.2E}) Mrad".format(self.data_arrays[server]['scan']['row'][0],
                                                                                                                   self.data_arrays[server]['scan']['scan'][0],
                                                                                                                   row_proton_fluence.n,
                                                                                                                   row_proton_fluence.s,
                                                                                                                   row_proton_tid.n,
                                                                                                                   row_proton_tid.s))

            # Add to overall fluence
            self._row_fluence_hist[server][self.data_arrays[server]['scan']['row'][0]] += row_proton_fluence

            # Append data to table within this interpretation cycle
            self.data_flags[server]['scan'] = True

            # ETA time and n_scans
            _mean_proton_fluence = np.mean(self._row_fluence_hist[server]).n
            row_scan_time = self.data_arrays[server]['scan']['row_stop_timestamp'][0] - self.data_arrays[server]['scan']['row_start_timestamp'][0]

            try:
                # Check damage type
                if self.data_arrays[server]['irrad']['aim_damage'][0] == bytes('NIEL', encoding='ascii'):
                    # Get remaining proton fluence
                    remainder_NIEL = self.data_arrays[server]['irrad']['aim_value'][0] / self._daq_params[server]['kappa'][0] - _mean_proton_fluence
                    eta_n_scans = int(remainder_NIEL / row_proton_fluence.n)
                else:
                    remainder_TID = self.data_arrays[server]['irrad']['aim_value'][0] - analysis.formulas.tid_scan(proton_fluence=_mean_proton_fluence,
                                                                                                                   stopping_power=self._daq_params[server]['stopping_power'])
                    eta_n_scans = int(remainder_TID / analysis.formulas.tid_scan(proton_fluence=row_proton_fluence.n,
                                                                                 stopping_power=self._daq_params[server]['stopping_power']))

                eta_seconds = eta_n_scans * row_scan_time * self.data_arrays[server]['irrad']['n_rows'][0]

            except (ZeroDivisionError, ValueError):  # ValueError if any of the values is np.nan
                eta_time = eta_n_scans = -1

            scan_data = {'meta': {'timestamp': meta['timestamp'], 'name': server, 'type': 'scan'},
                         'data': {'fluence_hist': unumpy.nominal_values(self._row_fluence_hist[server]).tolist(),
                                  'fluence_hist_err': unumpy.std_devs(self._row_fluence_hist[server]).tolist(),
                                  'row_mean_proton_fluence': (row_proton_fluence.n, row_proton_fluence.s),
                                  'row_mean_tid': (row_proton_tid.n, row_proton_tid.s),
                                  'row': int(self.data_arrays[server]['scan']['row'][0]),
                                  'eta_seconds': eta_seconds, 'eta_n_scans': eta_n_scans,
                                  'status': 'interpreted'}}

        elif data['status'] == 'scan_complete':

            # Get scan proton fluence in each row
            row_proton_fluences_last_scan = self.data_tables[server]['scan'].col('row_proton_fluence')[
                                            -self.data_arrays[server]['irrad']['n_rows'][0]:]

            # Get scan proton fluence error in each row
            row_proton_fluences_last_scan_err = self.data_tables[server]['scan'].col('row_proton_fluence_error')[
                                                -self.data_arrays[server]['irrad']['n_rows'][0]:]

            # Calculate mean proton fluence of last scan
            mean_scan_proton_fluence, mean_scan_proton_fluence_err = self._calc_mean_and_error(
                data=unumpy.uarray(row_proton_fluences_last_scan,
                                   row_proton_fluences_last_scan_err))

            # Calculate absolute delivered fluence with this scan
            abs_proton_fluence = ufloat(mean_scan_proton_fluence,
                                        mean_scan_proton_fluence_err) + ufloat(
                self.data_arrays[server]['damage']['scan_proton_fluence'][0],
                self.data_arrays[server]['damage']['scan_proton_fluence_error'][0])

            # Calculate absolute delivered TID with this scan
            abs_tid = analysis.formulas.tid_scan(proton_fluence=abs_proton_fluence,
                                                 stopping_power=self._daq_params[server]['stopping_power'])

            # Completed scan number and timestamp of completion
            self.data_arrays[server]['damage']['timestamp'] = meta['timestamp']
            self.data_arrays[server]['damage']['scan'] = data['scan']
            self.data_arrays[server]['damage']['scan_proton_fluence'] = abs_proton_fluence.n
            self.data_arrays[server]['damage']['scan_proton_fluence_error'] = abs_proton_fluence.s
            self.data_arrays[server]['damage']['scan_tid'] = abs_tid.n
            self.data_arrays[server]['damage']['scan_tid_error'] = abs_tid.s

            # Log
            logging.info(
                "Scan {}: ({:.2E} +- {:.2E}) protons / cm^2 and ({:.2E} +- {:.2E}) Mrad".format(data['scan'],
                                                                                                abs_proton_fluence.n,
                                                                                                abs_proton_fluence.s,
                                                                                                abs_tid.n,
                                                                                                abs_tid.s))

            # Append data to table within this interpretation cycle
            self.data_flags[server]['damage'] = True

            scan_data = {'meta': {'timestamp': meta['timestamp'], 'name': server, 'type': 'damage'},
                         'data': {'scan': data['scan'],
                                  'scan_proton_fluence': (abs_proton_fluence.n, abs_proton_fluence.s),
                                  'scan_tid': (abs_tid.n, abs_tid.s)}}

        elif data['status'] == 'scan_finished':

            self.data_arrays[server]['result']['timestamp'] = meta['timestamp']

            mean_result_proton_fluence = np.mean(self._row_fluence_hist[server])
            mean_result_tid = analysis.formulas.tid_scan(proton_fluence=mean_result_proton_fluence, stopping_power=analysis.constants.p_stop_Si)
            mean_result_neq_fluence = mean_result_proton_fluence * ufloat(*self._daq_params[server]['kappa'])

            self.data_arrays[server]['result']['proton_fluence'] = mean_result_proton_fluence.n
            self.data_arrays[server]['result']['proton_fluence_error'] = mean_result_proton_fluence.s
            self.data_arrays[server]['result']['tid'] = mean_result_tid.n
            self.data_arrays[server]['result']['tid_error'] = mean_result_tid.s
            self.data_arrays[server]['result']['neutron_fluence'] = mean_result_neq_fluence.n
            self.data_arrays[server]['result']['neutron_fluence_error'] = mean_result_neq_fluence.s

            # Append data to table within this interpretation cycle
            self.data_flags[server]['result'] = True

            scan_data = {'meta': {'timestamp': meta['timestamp'], 'name': server, 'type': 'result'},
                         'data': {'scan': int(self.data_arrays[server]['damage']['scan'][0]),
                                  'proton_fluence': (mean_result_proton_fluence.n, mean_result_proton_fluence.s),
                                  'tid': (mean_result_tid.n, mean_result_tid.s),
                                  'neutron_fluence': (mean_result_neq_fluence.n, mean_result_neq_fluence.s)}}

        return scan_data

    def _interpret_daq_board_ntc_data(self, server, data, meta):

        # Get NTC channel voltage
        ntc_voltage = data[self.readout_setup[server]['channels'][self._lookups[server]['ntc_group_idx']]]
        ntc_temp = analysis.formulas.get_ntc_temp(ntc_voltage=ntc_voltage, ref_voltage=ro.DAQ_BOARD_CONFIG['common']['voltages']['2V5p'])
        ntc_ch_name = self.readout_setup[server]['ntc'][str(meta['ntc_ch'])]

        self.data_arrays[server]['temp_daq_board']['timestamp'] = meta['timestamp']
        self.data_arrays[server]['temp_daq_board']['ntc_channel'] = ntc_ch_name.encode('ascii')
        self.data_arrays[server]['temp_daq_board']['temperature'] = ntc_temp

        # Append data to table within this interpretation cycle
        self.data_flags[server]['temp_daq_board'] = True

        self._ntc_temps[server][ntc_ch_name] = ntc_temp

        # Collect data of all NTCs and then send; easier for plotting wrt timestamp
        if len(self._ntc_temps[server]) == len(self.readout_setup[server]['ntc']):
            ntc_data = {'meta': {'timestamp': meta['timestamp'], 'name': server, 'type': 'temp_daq_board'},
                        'data': self._ntc_temps[server].copy()}
            self._ntc_temps[server] = {}

            return ntc_data

    def _interpret_arduino_temp_data(self, server, data, meta):

        temp_data = {'meta': {'timestamp': meta['timestamp'], 'name': server, 'type': 'temp_arduino'},
                     'data': {}}

        self.data_arrays[server]['temp_arduino']['timestamp'] = meta['timestamp']

        for temp in data:
            self.data_arrays[server]['temp_arduino'][temp] = temp_data['data'][temp] = data[temp]

        self.data_flags[server]['temp_arduino'] = True

        return temp_data

    def _interpret_rad_monitor_data(self, server, data, meta):

        rad_data = {'meta': {'timestamp': meta['timestamp'], 'name': server, 'type': 'dose_rate'},
                     'data': {}}
                     
        self.data_arrays[server]['rad_monitor']['timestamp'] = meta['timestamp']
        
        for rad in data:
            self.data_arrays[server]['rad_monitor'][rad] = rad_data['data'][rad] = data[rad]

        self.data_flags[server]['rad_monitor'] = True

        return rad_data

    def _store_axis_data(self, server, data, meta):

        axis_domain = 'motorstage_{}'.format(data['axis_domain'].lower())

        self.data_arrays[server][axis_domain]['timestamp'] = meta['timestamp']
        self.data_arrays[server][axis_domain]['axis'] = data['axis']
        self.data_arrays[server][axis_domain]['movement_status'] = data['status'].encode('ascii')
        self.data_arrays[server][axis_domain]['position'] = data['position']

        for prop in ('speed', 'accel', 'travel'):
            if prop in data:
                self.data_arrays[server][axis_domain][prop] = data[prop]

        self.data_flags[server][axis_domain] = True

    def interpret_data(self, raw_data):
        """Interpretation of the data"""

        # Make list of interpreted result data
        interpreted_data = []

        # Retrieve server IP , meta data and actual data from raw data dict
        server, meta_data, data = raw_data['meta']['name'], raw_data['meta'], raw_data['data']

        if meta_data['type'] == 'raw_data':

            ### Raw data ###

            intrprtd_raw_data = self._interpret_raw_data(server=server, data=data, meta=meta_data)

            interpreted_data.append(intrprtd_raw_data)

            # Get offsets
            if self.interaction_flags[server]['offset'].is_set():
                self._get_raw_offset(server=server, data=data)

            ### Beam data ###

            # Beam data
            beam_data = self._interpret_beam_data(server=server, data=data, meta=meta_data)

            interpreted_data.append(beam_data)

            # Histograms
            hist_data = self._update_hist_entries(server=server, beam_data=beam_data)

            interpreted_data.append(hist_data)

            # Get temperature data from NTC on IrradDAQBoard
            if 'ntc_ch' in meta_data:
                ntc_data = self._interpret_daq_board_ntc_data(server=server, data=data, meta=meta_data)

                if ntc_data:
                    interpreted_data.append(ntc_data)

        elif meta_data['type'] == 'scan':

            scan_data = self._interpret_scan_data(server=server, data=data, meta=meta_data)

            if scan_data:
                interpreted_data.append(scan_data)

        # Store temperature
        elif meta_data['type'] == 'temp':

            temp_data = self._interpret_arduino_temp_data(server=server, data=data, meta=meta_data)
            interpreted_data.append(temp_data)

        elif meta_data['type'] == 'rad_monitor':
            rad_data = self._interpret_rad_monitor_data(server=server, data=data, meta=meta_data)
            interpreted_data.append(rad_data)
            
        # A motorstage axis has send movement change data
        elif meta_data['type'] == 'axis':
            self._store_axis_data(server=server, data=data, meta=meta_data)

        # If event is not set, store data to hdf5 file
        if self.interaction_flags[server]['write'].is_set():
            self.store_data(server)
        else:
            logging.debug("Data of {} is not being recorded...".format(self.setup['server'][server]['name']))

        # Calc and add data rate to interpreted meta data
        for in_data in interpreted_data:
            self._calc_drate(server=server, meta=in_data['meta'])

        return interpreted_data

    def store_data(self, server):
        """Method which appends current data to table files. If tables are longer then self._max_buf_len,
        flush the buffer to hard drive"""

        # Store data that is not always available
        for storable_data, store_status in self.data_flags[server].items():

            if storable_data in self.data_tables[server] and store_status:
                self.data_tables[server][storable_data].append(self.data_arrays[server][storable_data])
                self.data_flags[server][storable_data] = False

        # Flush data to hard drive in fixed interval
        if self._last_data_flush is None or time() - self._last_data_flush >= self._data_flush_interval:
            logging.debug("Flushing data to hard disk...")
            self.output_table.flush()
            self._last_data_flush = time()

    def _start_interpreter(self, setup):
        """Sets up the interpreter process"""

        # Update setup
        self.setup = setup

        # Setup logging
        self._setup_logging()

        self._setup_daq()

        self.is_converter = True

        self.add_daq_stream(daq_stream=[self._tcp_addr(port=self.setup['server'][server]['ports']['data'], ip=server) for server in self.server])

        self.launch_thread(target=self.recv_data)

    def handle_cmd(self, target, cmd, data=None):
        """Handle all commands. After every command a reply must be send."""

        # Handle server commands
        if target == 'interpreter':

            if cmd == 'start':
                self._start_interpreter(data)
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=self.pid)

            elif cmd == 'shutdown':
                self.shutdown()

            elif cmd == 'zero_offset':
                self.interaction_flags[data]['offset'].set()

            elif cmd == 'record_data':
                server, record = data

                if record:  # We want to write
                    self.interaction_flags[server]['write'].set()
                else:
                    self.interaction_flags[server]['write'].clear()

                self._send_reply(reply=cmd, sender=target, _type='STANDARD', data=[server, self.interaction_flags[server]['write'].is_set()])

            elif cmd == 'update_group_ifs':
                server, ifs, group = data['server'], data['ifs'], data['group']
                self.readout_setup[server]['ro_group_scales'][group] = ifs
                self._interpret_event(server=server, event=cmd, parameters='{} {} nA'.format(group, ifs))

    def _close_tables(self):
        """Method to close the h5-files which were opened in the setup_daq method"""

        # User info
        logging.info('Closing output file {}'.format(self.output_table.filename))

        for server, server_setup in self.setup['server'].items():

            self.store_data(server=server)

            # Store histograms
            for hist_name in self.data_hists[server]:
                table_name = '{}{}'.format(*[n.capitalize() for n in hist_name.split('_')])
                self.output_table.create_array('/{}/Histogram/{}'.format(server_setup['name'], table_name), 'hist', self.data_hists[server][hist_name]['hist'])

        self.output_table.flush()

        self.output_table.close()

    def clean_up(self):

        # Close opened data files; AttributeError if DAQ hasn't started
        try:
            self._close_tables()
        except AttributeError:
            pass


def run(blocking=True):

    irrad_converter = IrradConverter()
    irrad_converter.start()
    
    if blocking:
        irrad_converter.join()


if __name__ == '__main__':
    run()
