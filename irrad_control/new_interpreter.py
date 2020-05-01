import time
import threading
import logging
import yaml
import numpy as np
import tables as tb
from irrad_control import daq_config, xy_stage_config, xy_stage_config_yaml
from irrad_control.utils import IrradProcess
from collections import defaultdict
from copy import deepcopy


class IrradConverter(IrradProcess):
    """Interpreter process for irradiation site data"""

    def __init__(self, name=None):

        # Set name of this interpreter process
        name = 'interpreter' if name is None else name

        # Dict of known commands; flag to indicate when cmd is busy
        commands = {'interpreter': ['shutdown', 'zero_offset', 'record_data', 'start']}

        # Call init of super class
        super(IrradConverter, self).__init__(name=name, commands=commands)

        self.stage_config = deepcopy(xy_stage_config)

        # Event set if stage needs maintenance
        self.state_flags['xy_stage_maintenance'] = threading.Event()

    def _setup_daq(self):

        # Flush data to hard drive every second
        self._data_flush_interval = 1.0
        self._last_data_flush = None

        # General setup
        self.server = list(self.setup['server'].keys())

        # ADC/temp setup per server
        self.adc_setup = {}
        self.ch_type_idx = {}
        self.temp_setup = {}
        self.daq_setup = {}

        # Special dicts needed for all ADCs on the servers
        for server in self.server:
            if 'adc' in self.setup['server'][server]['devices']:
                self.adc_setup[server] = self.setup['server'][server]['devices']['adc']
                self.daq_setup[server] = self.setup['server'][server]['devices']['daq']
                self.ch_type_idx[server] = dict([(x, self.adc_setup[server]['types'].index(x)) for x in daq_config['adc_channels']
                                                 if x in self.adc_setup[server]['types']])

            if 'temp' in self.setup['server'][server]['devices']:
                self.temp_setup[server] = self.setup['server'][server]['devices']['temp']

            # Per server interactions
            self.stop_flags['write_{}'.format(server)] = threading.Event()
            self.state_flags['offset_{}'.format(server)] = threading.Event()

        # Data writing
        # Open only one output file and organize its data in groups
        self.output_table = tb.open_file(self.setup['session']['outfile'] + '.h5', 'w')

        # Store three tables per ADC
        self.raw_table = {}
        self.beam_table = {}
        self.fluence_table = {}
        self.result_table = {}
        self.offset_table = {}
        self.temp_table = {}

        # Store data per interpretation cycle and ADC
        self.raw_data = {}
        self.beam_data = {}
        self.fluence_data = {}
        self.result_data = {}
        self.zero_offset_data = {}
        self._zero_offset_vals = {}
        self.temp_data = {}

        # Possible channels from which to get the beam positions
        self.pos_types = {'h': {'digital': ['sem_left', 'sem_right'], 'analog': ['sem_h_shift']},
                          'v': {'digital': ['sem_up', 'sem_down'], 'analog': ['sem_v_shift']}}

        # Possible channels from which to get the beam current
        self.current_types = {'digital': [('sem_left', 'sem_right'), ('sem_up', 'sem_down')], 'analog': 'sem_sum'}

        # Dtype for fluence data
        fluence_dtype = [('scan', '<i4'), ('row', '<i4'), ('current_mean', '<f4'), ('current_std', '<f4'),
                         ('current_err', '<f4'), ('speed', '<f4'), ('step', '<f4'), ('p_fluence', '<f8'),
                         ('p_fluence_err', '<f8'), ('timestamp_start', '<f8'), ('x_start', '<f4'), ('y_start', '<f4'),
                         ('timestamp_stop', '<f8'), ('x_stop', '<f4'), ('y_stop', '<f4')]

        result_dtype = [('p_fluence_mean', '<f8'), ('p_fluence_err', '<f8'), ('p_fluence_std', '<f8')]

        # Dict with lists to append beam current values to during scanning
        self._beam_currents = defaultdict(list)

        # Current factor
        self.nA = 1e-9

        # Elementary charge
        self.qe = 1.60217733e-19

        # XY stage stuff
        self.n_rows = None
        self.y_step = None

        # Attributes indicating start and stop of stage
        self._stage_scanning = False
        self._store_fluence_data = False
        self._store_temp_data = False

        # Fluence
        self._fluence = {}
        self._fluence_err = {}

        # Open respective table files per server and check which data will be interpreted
        for server in self.server:

            # This server has an ADC so will send raw data to interpret
            if server in self.adc_setup:

                # Make structured arrays for data organization when dropping to table
                raw_dtype = [('timestamp', '<f8')] + [(ch, '<f4') for ch in self.adc_setup[server]['channels']]
                beam_dtype = [('timestamp', '<f8')]

                # Check which data will be interpreted
                # Beam position
                for pos_type in self.pos_types:
                    for sig in self.pos_types[pos_type]:
                        if all(t in self.ch_type_idx[server] for t in self.pos_types[pos_type][sig]):
                            beam_dtype.append(('position_{}_{}'.format(pos_type, sig), '<f4'))

                # Beam current
                for curr_type in self.current_types:
                    if curr_type == 'digital':
                        if any(all(s in self.ch_type_idx[server] for s in t) for t in self.current_types[curr_type]):
                            beam_dtype.append(('current_{}'.format(curr_type), '<f4'))
                    else:
                        if self.current_types[curr_type] in self.ch_type_idx[server]:
                            beam_dtype.append(('current_{}'.format(curr_type), '<f4'))

                # Make arrays with given dtypes
                self.raw_data[server] = np.zeros(shape=1, dtype=raw_dtype)
                self.beam_data[server] = np.zeros(shape=1, dtype=beam_dtype)
                self.fluence_data[server] = np.zeros(shape=1, dtype=fluence_dtype)
                self.result_data[server] = np.zeros(shape=1, dtype=result_dtype)

                # Auto zeroing offset
                self.zero_offset_data[server] = np.zeros(shape=1, dtype=raw_dtype)
                self._zero_offset_vals[server] = defaultdict(list)

                # Create new group for respective server
                self.output_table.create_group(self.output_table.root, self.setup['server'][server]['name'])

                # Create data tables
                self.raw_table[server] = self.output_table.create_table('/{}'.format(self.setup['server'][server]['name']),
                                                                        description=self.raw_data[server].dtype,
                                                                        name='Raw')
                self.beam_table[server] = self.output_table.create_table('/{}'.format(self.setup['server'][server]['name']),
                                                                         description=self.beam_data[server].dtype,
                                                                         name='Beam')
                self.fluence_table[server] = self.output_table.create_table('/{}'.format(self.setup['server'][server]['name']),
                                                                            description=self.fluence_data[server].dtype,
                                                                            name='Fluence')
                self.result_table[server] = self.output_table.create_table('/{}'.format(self.setup['server'][server]['name']),
                                                                           description=self.result_data[server].dtype,
                                                                           name='Result')
                self.offset_table[server] = self.output_table.create_table('/{}'.format(self.setup['server'][server]['name']),
                                                                           description=self.zero_offset_data[server].dtype,
                                                                           name='RawOffset')

            if server in self.temp_setup:
                temp_dtype = [('timestamp', '<f8')] + [(temp, '<f2') for temp in self.temp_setup[server].values()]
                self.temp_data[server] = np.zeros(shape=1, dtype=temp_dtype)
                self.temp_table[server] = self.output_table.create_table('/{}'.format(self.setup['server'][server]['name']),
                                                                         description=self.temp_data[server].dtype,
                                                                         name='Temperature')

    def interpret_data(self, raw_data):
        """Interpretation of the data"""

        # Retrieve server IP , meta data and actual data from raw data dict
        server, meta_data, data = raw_data['meta']['name'], raw_data['meta'], raw_data['data']

        if meta_data['type'] == 'raw':

            ### Raw data ###

            # Get timestamp from data for beam and raw arrays
            self.raw_data[server]['timestamp'] = self.beam_data[server]['timestamp'] = meta_data['timestamp']

            # Fill raw data structured array first
            for ch in data:
                self.raw_data[server][ch] = data[ch]
                # Subtract offset from data; initially offset is 0 for all ch
                data[ch] -= self.zero_offset_data[server][ch][0]

            # Get offsets
            if self.state_flags['offset_{}'.format(server)].is_set():
                # Loop over data until sufficient data for mean is collected
                for ch in data:
                    self._zero_offset_vals[server][ch].append(self.raw_data[server][ch][0])
                    if len(self._zero_offset_vals[server][ch]) == 40:
                        self.zero_offset_data[server][ch] = np.mean(self._zero_offset_vals[server][ch])
                # If all offsets have been found, clear signal and reset list
                if all(len(self._zero_offset_vals[server][ch]) >= 40 for ch in data):
                    self.state_flags['offset_{}'.format(server)].clear()
                    self._zero_offset_vals[server] = defaultdict(list)
                    self.zero_offset_data[server]['timestamp'] = time.time()
                    self.offset_table[server].append(self.zero_offset_data[server])

            ### Interpretation of data ###

            # Beam data dict to publish to ZMQ in order to visualize
            beam_data = {'meta': {'timestamp': meta_data['timestamp'], 'name': server, 'type': 'beam'},
                         'data': {'position': {'digital': {}, 'analog': {}}, 'current': {'digital': 0, 'analog': 0}}}

            # Loop over names in structured array which determine the data available
            for dname in self.beam_data[server].dtype.names:

                # Extract the signal type from the dname; either analog or digital
                sig_type = dname.split('_')[-1]

                # Get beam position info of ADC
                if 'position' in dname:

                    # Extract position type which is either h or v for horizontal/vertical respectively
                    pos_type = dname.split('_')[1]

                    # Calculate shift from digitized signals of foils
                    if sig_type == 'digital':
                        # Digital shift is normalized; from -1 to 1
                        shift = self._calc_digital_shift(data, server, self.pos_types[pos_type][sig_type], m=pos_type)

                    # Get shift from analog signal
                    else:
                        shift = data[self.adc_setup[server]['channels'][self.ch_type_idx[server][self.pos_types[pos_type][sig_type][0]]]]
                        shift *= 1. / 5.  # Analog shift from -5 to 5 V; divide by 5 V to normalize

                    # Shift to percent
                    shift *= 100.

                    # Write to dict to send out and to array to store
                    beam_data['data']['position'][sig_type][pos_type] = self.beam_data[server][dname] = shift

                # Get beam current
                elif 'current' in dname:

                    # Calculate current from digitized signals of foils
                    if sig_type == 'digital':

                        # Get all channels present which represent individual foils
                        dig_chs = [ch for cch in self.current_types[sig_type] for ch in cch if ch in self.ch_type_idx[server]]

                        # Number of foils
                        n_foils = len(dig_chs)

                        if n_foils not in (2, 4):
                            msg = "Digital current must be derived from 2 OR 4 foils, now it's {}".format(n_foils)
                            logging.warning(msg)

                        # Sum and divide by amount of foils
                        current = sum([data[self.adc_setup[server]['channels'][self.ch_type_idx[server][c]]] * self.adc_setup[server]['ro_scales'][
                            self.ch_type_idx[server][c]] for c in dig_chs])
                        current /= n_foils

                    # Get current from analog signal
                    else:
                        _idx = self.ch_type_idx[server][self.current_types[sig_type]]
                        current = data[self.adc_setup[server]['channels'][_idx]] * self.adc_setup[server]['ro_scales'][_idx]

                    # Up to here *current* is actually a voltage between 0 and 5 V which is now converted to nano ampere
                    current *= self.daq_setup[server]['lambda'] * self.nA

                    # Write to dict to send out and to array to store
                    beam_data['data']['current'][sig_type] = self.beam_data[server][dname] = current

            self.io_q['out'].put(beam_data)

        elif meta_data['type'] == 'stage':

            if data['status'] == 'init':
                self.y_step = data['y_step']
                self.n_rows = data['n_rows']
                self._fluence[server] = [0] * self.n_rows
                self._fluence_err[server] = [0] * self.n_rows

            elif data['status'] == 'start':
                del self._beam_currents[server][:]
                self._stage_scanning = True
                self.fluence_data[server]['timestamp_start'] = meta_data['timestamp']

                for prop in ('scan', 'row', 'speed', 'x_start', 'y_start'):
                    self.fluence_data[server][prop] = data[prop]

            elif data['status'] == 'stop':
                self._stage_scanning = False
                self.fluence_data[server]['timestamp_stop'] = meta_data['timestamp']

                for prop in ('x_stop', 'y_stop'):
                    self.fluence_data[server][prop] = data[prop]

                # Do fluence calculation
                # Mean current over scanning time
                mean_current, std_current = np.mean(self._beam_currents[server]), np.std(self._beam_currents[server])
                current_ro_scale = self.adc_setup[server]['ro_scales'][self.ch_type_idx[server][self.current_types['analog']]]

                # Error on current measurement is Delta I = 3.3% I + 1% R_FS
                actual_current_error = 0.033 * mean_current + 0.01 * current_ro_scale * self.nA

                # Quadratically add the measurement error and beam current fluctuation
                p_f_err = np.sqrt(std_current ** 2. + actual_current_error ** 2.)

                # Fluence and its error; speed and step_size are in mm; factor 1e-2 to convert to cm^2
                p_fluence = mean_current / (self.y_step * self.fluence_data[server]['speed'][0] * self.qe * 1e-2)
                p_fluence_err = p_f_err / (self.y_step * self.fluence_data[server]['speed'][0] * self.qe * 1e-2)

                # Write to array
                self.fluence_data[server]['current_mean'] = mean_current
                self.fluence_data[server]['current_std'] = std_current
                self.fluence_data[server]['current_err'] = actual_current_error
                self.fluence_data[server]['p_fluence'] = p_fluence
                self.fluence_data[server]['p_fluence_err'] = p_fluence_err
                self.fluence_data[server]['step'] = self.y_step

                # User feedback
                logging.info('Fluence row {}: ({:.2E} +- {:.2E}) protons / cm^2'.format(self.fluence_data[server]['row'][0], p_fluence, p_fluence_err))

                # Add to overall fluence
                self._fluence[server][self.fluence_data[server]['row'][0]] += self.fluence_data[server]['p_fluence'][0]

                # Update the error a la Gaussian error propagation
                old_fluence_err = self._fluence_err[server][self.fluence_data[server]['row'][0]]
                current_fluence_err = self.fluence_data[server]['p_fluence_err'][0]
                new_fluence_err = np.sqrt(old_fluence_err ** 2.0 + current_fluence_err ** 2.0)

                # Update
                self._fluence_err[server][self.fluence_data[server]['row'][0]] = new_fluence_err

                fluence_data = {'meta': {'timestamp': meta_data['timestamp'], 'name': server, 'type': 'fluence'},
                                'data': {'hist': self._fluence[server], 'hist_err': self._fluence_err[server]}}

                self._store_fluence_data = True

                self.io_q['out'].put(fluence_data)

                self._update_xy_stage_config(server)

            elif data['status'] == 'finished':

                # The stage is finished; append the overall fluence to the result and get the sigma by the std dev
                self.result_data[server]['p_fluence_mean'] = np.mean(self._fluence[server])
                self.result_data[server]['p_fluence_err'] = np.sqrt(np.sum(np.power(np.array(self._fluence_err[server]) / len(self._fluence[server]), 2.)))
                self.result_data[server]['p_fluence_std'] = np.std(self._fluence[server])
                self.result_table[server].append(self.result_data[server])

                # Write everything to the file
                self.output_table.flush()

        # Store temperature
        elif meta_data['type'] == 'temp':

            self.temp_data[server]['timestamp'] = meta_data['timestamp']
            for temp in data:
                self.temp_data[server][temp] = data[temp]

            self._store_temp_data = True

        # During scan, store all beam currents in order to get mean current over scanned row
        if self._stage_scanning:
            self._beam_currents[server].append(self.beam_data[server]['current_analog'][0])

        # If event is not set, store data to hdf5 file
        if not self.stop_flags['write_{}'.format(server)].is_set():
            self.store_data(server)
        else:
            logging.debug("Data of {} is not being recorded...".format(self.setup['server'][server]['name']))

    def _update_xy_stage_config(self, server):

        # Add to xy stage stats
        # This iterations travel
        x_travel = float(abs(self.fluence_data[server]['x_stop'][0] - self.fluence_data[server]['x_start'][0]))
        y_travel = float(self.fluence_data[server]['step'][0] * 1e-3)

        # Add to total
        self.stage_config['total_travel']['x'] += x_travel
        self.stage_config['total_travel']['y'] += y_travel

        # Add to interval
        self.stage_config['interval_travel']['x'] += x_travel
        self.stage_config['interval_travel']['y'] += y_travel

        # Check if any axis has reached interval travel
        for axis in ('x', 'y'):
            if self.stage_config['interval_travel'][axis] > self.stage_config['maintenance_interval']:
                self.stage_config['interval_travel'][axis] = 0.0
                self.state_flags['xy_stage_maintenance'].set()
                logging.warning("{}-axis of XY-stage reached service interval travel! "
                                "See https://www.zaber.com/wiki/Manuals/X-LRQ-E#Precautions".format(axis))

        self.stage_config['last_update'] = time.asctime()

    def _calc_digital_shift(self, data, server, ch_types, m='h'):
        """Calculate the beam displacement on the secondary electron monitor from the digitized foil signals"""

        # Get indices of respective foil signals in data and extract
        idx_a, idx_b = self.ch_type_idx[server][ch_types[0]], self.ch_type_idx[server][ch_types[1]]
        a, b = data[self.adc_setup[server]['channels'][idx_a]], data[self.adc_setup[server]['channels'][idx_b]]

        # Convert to currents since ADC channels can have different R/O scales
        a = a / 5.0 * self.adc_setup[server]['ro_scales'][idx_a]
        b = b / 5.0 * self.adc_setup[server]['ro_scales'][idx_b]

        # Do calc and catch ZeroDivisionError
        try:
            res = float(a - b) / float(a + b)
        except ZeroDivisionError:
            res = 0.0

        # If we don't have beam, sometimes results get large and cause problems with displaying the data, therefore limit
        res = 1 if res > 1 else -1 if res < -1 else res

        # Horizontally, if we are shifted to the left the graph should move to the left, therefore * -1
        return -1 * res if m == 'h' else res

    def store_data(self, server):
        """Method which appends current data to table files. If tables are longer then self._max_buf_len,
        flush the buffer to hard drive"""

        self.raw_table[server].append(self.raw_data[server])
        self.beam_table[server].append(self.beam_data[server])

        # If the stage scanned, append data
        if self._store_fluence_data:
            self.fluence_table[server].append(self.fluence_data[server])
            self._store_fluence_data = False

        if self._store_temp_data:
            self.temp_table[server].append(self.temp_data[server])
            self._store_temp_data = False

        # Flush data to hard drive in fixed interval
        if self._last_data_flush is None or time.time() - self._last_data_flush >= self._data_flush_interval:
            self._last_data_flush = time.time()
            logging.debug("Flushing data to hard disk...")
            self.output_table.flush()

    def _start_interpreter(self, setup):
        """Sets up the interpreter process"""

        # Update setup
        self.setup = setup

        # Setup logging
        self._setup_logging()

        self._setup_daq()

        self.is_converter = True

        self.start_converter(daq_stream=[self._tcp_addr(port=self.setup['ports']['data'], ip=server) for server in self.server])

    def handle_cmd(self, target, cmd, cmd_data=None):
        """Handle all commands. After every command a reply must be send."""

        # Handle server commands
        if target == 'interpreter':

            if cmd == 'start':
                self._start_interpreter(cmd_data)

            elif cmd == 'shutdown':
                self.shutdown()

            elif cmd == 'zero_offset':
                self.state_flags['offset_{}'.format(cmd_data)].set()

            elif cmd == 'record_data':
                if self.stop_flags['write_{}'.format(cmd_data)].is_set():
                    self.stop_flags['write_{}'.format(cmd_data)].clear()
                else:
                    self.stop_flags['write_{}'.format(cmd_data)].set()
                self._send_reply(reply=cmd, sender=target, _type='STANDARD', data=[cmd_data, not self.stop_flags['write_{}'.format(cmd_data)].is_set()])

    def _close_tables(self):
        """Method to close the h5-files which were opened in the setup_daq method"""

        # User info
        logging.info('Closing output file {}'.format(self.output_table.filename))

        self.output_table.close()

    def clean_up(self):

        # Close opened data files
        self._close_tables()

        try:
            # Open xy config an update info
            with open(xy_stage_config_yaml, 'r') as _xys_r:
                _xy_stage_config_tmp = yaml.safe_load(_xys_r)

            # Positions could have changed during session
            self.stage_config['positions'].update(_xy_stage_config_tmp['positions'])

            # Overwrite xy stage stats
            with open(xy_stage_config_yaml, 'w') as _xys_w:
                yaml.safe_dump(self.stage_config, _xys_w, default_flow_style=False)

        except (OSError, IOError):
            logging.warning("Could not update XY-Stage configuration file at {}. Maybe it is opened by another process?".format(xy_stage_config_yaml))


def main():

    irrad_converter = IrradConverter()
    irrad_converter.start()
    irrad_converter.join()


if __name__ == '__main__':
    main()
