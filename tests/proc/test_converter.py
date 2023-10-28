import os
import time
import logging
import unittest
import zmq
import numpy as np

from irrad_control import pid_file
from irrad_control.utils.tools import load_yaml
from irrad_control.analysis.utils import load_irrad_data
from irrad_control.processes.converter import IrradConverter 



class TestConverter(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        cls.context = zmq.Context()

        cls.fixture_path = os.path.join(os.path.dirname(__file__), '../fixtures')
        cls.test_base = os.path.join(cls.fixture_path, f'test_irradiation')

        # Load the data
        cls.data, cls.config = load_irrad_data(data_file=cls.test_base+'.h5',
                                               config_file=cls.test_base+'.yaml',
                                               subtract_raw_offset=False)
        
        # Make output dir
        cls.output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'output'))
        if not os.path.isdir(cls.output_dir):
            os.mkdir(cls.output_dir)

        # Create and start process
        cls.converter = IrradConverter(name='TestConverterProcess')
        cls.converter.start()

        # Wait until process is created with irrad_control.pid file
        start = time.time()
        while not os.path.isfile(pid_file):
            time.sleep(1)

            # Wait max 30 seconds
            if time.time() - start > 30:
                break

        assert os.path.isfile(pid_file)

        cls.pid_content = load_yaml(pid_file)

        # Overwrite outfile in session
        cls.config['session']['outfile'] = os.path.join(cls.output_dir, 'test_converter_outfile')

        # Overwrite server ip to localhsot
        cls.config['server']['localhost'] = cls.config['server']['131.220.221.103']
        del cls.config['server']['131.220.221.103']
        cls.server = 'HSR'

        # Open socket for reqests aka send commands
        cls.cmd_req = cls.context.socket(zmq.REQ)
        cls.cmd_req.connect(f"tcp://localhost:{cls.pid_content['ports']['cmd']}")
        cls.data_pub = cls.context.socket(zmq.PUB)
        cls.data_pub.setsockopt(zmq.LINGER, 1000)  # Wait 1 second before closing socket for messages to leave
        cmd_port = cls.data_pub.bind_to_random_port(addr='tcp://*')
        # Add 'ports' to config so the converter knows where the data comes from 
        cls.config['server']['localhost']['ports'] = {'data': cmd_port}

    @classmethod
    def tearDownClass(cls):
        
        # Delete files
        #for root, _, files in os.walk(cls.output_dir):
        #    for fname in files:
        #        os.remove(os.path.join(root, fname))
        #os.rmdir(cls.output_dir)

        time.sleep(1)

    @classmethod
    def _send_cmd_get_reply(self, target, cmd, cmd_data=None,):
        
        # Send command dict and wait for reply
        self.cmd_req.send_json({'target': target, 'cmd': cmd, 'data': cmd_data})

        return self.cmd_req.recv_json()
    
    def _start_converter(self):

        # Start converter interpretation loop
        converter_start_reply = self._send_cmd_get_reply(target='interpreter', cmd='start', cmd_data=self.config)
        
        # Allow some time for converter to setup sockets etc
        time.sleep(2)

        # Assert that PIDs are the same
        assert converter_start_reply['data'] == self.pid_content['pid']

    def _shutdown_converter(self):

        # Send shutdown command
        self._send_cmd_get_reply(target='interpreter', cmd='shutdown')    
        
        # Wait for converter to finish
        self.converter.join()

        # Check pid file is gone
        assert not os.path.isfile(pid_file)

    def _check_output_data(self):

        # Open output file
        out_data, _ = load_irrad_data(data_file=self.config['session']['outfile']+'.h5',
                                      config_file=self.test_base+'.yaml',
                                      subtract_raw_offset=False)

        assert len(out_data[self.server]) == len(self.data[self.server])

        for data in ('Raw', 'Beam', 'See', 'Scan', 'Damage', 'Irrad', 'Result'):

            # Check all the arrays are not empty
            for dname in out_data[self.server][data].dtype.names:
                assert out_data[self.server][data][dname].size > 0
            
            # Check data is same length
            if data in ('Raw', 'Beam', 'See'):
                assert 0.9 * len(self.data[self.server][data]) <= len(out_data[self.server][data]) <= len(self.data[self.server][data])
            else:
                assert len(out_data[self.server][data]) == len(self.data[self.server][data])

    def _send_raw_data(self, raw):

        # Create raw data to be sent
        meta = {'timestamp': float(raw['timestamp']), 'name': 'localhost', 'type': 'raw_data'}
        data = {dtname: float(raw[dtname]) for dtname in self.config['server']['localhost']['readout']['channels']}

        self.data_pub.send_json({'meta': meta, 'data': data})

    def _send_scan_data(self, status, scan_idx=None):

        if status == 'scan_init':

            meta = {'timestamp': float(self.data[self.server]['Irrad']['timestamp'][0]), 'name': 'localhost', 'type': 'scan'}
            data = {'status': status,
                    'row_sep': float(self.data[self.server]['Irrad']['row_separation'][0]),
                    'n_rows': int(self.data[self.server]['Irrad']['n_rows'][0]),
                    'aim_damage': str(self.data[self.server]['Irrad']['aim_damage'][0].decode()),
                    'aim_value': float(self.data[self.server]['Irrad']['aim_value'][0]),
                    'min_current': float(self.data[self.server]['Irrad']['min_scan_current'][0]),
                    'scan_origin': (float(self.data[self.server]['Irrad']['scan_origin_x'][0]), float(self.data[self.server]['Irrad']['scan_origin_y'][0])),
                    'scan_area_start': (float(self.data[self.server]['Irrad']['scan_area_start_x'][0]), float(self.data[self.server]['Irrad']['scan_area_start_y'][0])),
                    'scan_area_stop': (float(self.data[self.server]['Irrad']['scan_area_stop_x'][0]), float(self.data[self.server]['Irrad']['scan_area_stop_y'][0])),
                    'dut_rect_start': (float(self.data[self.server]['Irrad']['dut_rect_start_x'][0]), float(self.data[self.server]['Irrad']['dut_rect_start_y'][0])),
                    'dut_rect_stop': (float(self.data[self.server]['Irrad']['dut_rect_stop_x'][0]), float(self.data[self.server]['Irrad']['dut_rect_stop_y'][0])),
                    'beam_fwhm': (float(self.data[self.server]['Irrad']['beam_fwhm_x'][0]), float(self.data[self.server]['Irrad']['beam_fwhm_y'][0]))}

        elif status == 'scan_start':
            
            # Publish data
            meta = {'timestamp': float(self.data[self.server]['Scan']['row_start_timestamp'][scan_idx]), 'name': 'localhost', 'type': 'scan'}
            data = {'status': status,
                    'scan': int(self.data[self.server]['Scan']['scan'][scan_idx]),
                    'row': int(self.data[self.server]['Scan']['row'][scan_idx]),
                    'speed': float(self.data[self.server]['Scan']['row_scan_speed'][scan_idx]),
                    'accel': float(self.data[self.server]['Scan']['row_scan_accel'][scan_idx]),
                    'x_start': float(self.data[self.server]['Scan']['row_start_x'][scan_idx]),
                    'y_start': float(self.data[self.server]['Scan']['row_start_y'][scan_idx])}
            
        elif status == 'scan_stop':
            
            # Publish stop data
            meta = {'timestamp': float(self.data[self.server]['Scan']['row_stop_timestamp'][scan_idx]), 'name': 'localhost', 'type': 'scan'}
            data = {'status': status,
                    'x_stop': float(self.data[self.server]['Scan']['row_stop_x'][scan_idx]),
                    'y_stop': float(self.data[self.server]['Scan']['row_stop_y'][scan_idx])}
                
        
        elif status == 'scan_complete':
            # Publish data
            if scan_idx >= self.data[self.server]['Damage']['timestamp'].shape[0]:
                ts = float(self.data[self.server]['Scan']['row_stop_timestamp'][scan_idx])
                sn = int(self.data[self.server]['Scan']['scan'][scan_idx])
            else:
                ts = float(self.data[self.server]['Damage']['timestamp'][scan_idx])
                sn = int(self.data[self.server]['Damage']['scan'][scan_idx])

            meta = {'timestamp': ts, 'name': 'localhost', 'type': 'scan'}
            data = {'status': status, 'scan': sn}

        elif status == 'scan_finished':
            # Put finished data
            meta = {'timestamp': float(self.data[self.server]['Result']['timestamp'][0]), 'name': 'localhost', 'type': 'scan'}
            data = {'status': status}
        
        self.data_pub.send_json({'meta': meta, 'data': data})

    def test_interpretation(self):

        self._start_converter()

        time.sleep(1)

        scan_start = False
        scan_start_idx = 0
        scan_stop_idx = 0
        scan_idx = 0

        # Loop over raw data
        for i, raw in enumerate(self.data[self.server]['Raw']):

            self._send_raw_data(raw)
        
            time.sleep(5e-3)  # Emulate ~133 Hz data rate

            raw_ts = raw['timestamp']

            if not scan_start:
                
                # Initiate scan
                if raw_ts >= self.data[self.server]['Irrad']['timestamp'][0]:
                    self._send_scan_data(status='scan_init')
                    scan_start = True

            else:

                # Terminate scan and leave loop
                if scan_stop_idx == self.data[self.server]['Scan']['scan'].shape[0]:
                    self._send_scan_data(status='scan_complete', scan_idx=scan_idx)
                    break

                # Check if we have reached a new can already; if so send comletion
                if self.data[self.server]['Scan']['scan'][scan_stop_idx] != -1:
                    if self.data[self.server]['Damage']['scan'][scan_idx] != self.data[self.server]['Scan']['scan'][scan_stop_idx]:
                        self._send_scan_data(status='scan_complete', scan_idx=scan_idx)
                        print(f"Current {scan_idx}")
                        scan_idx += 1

                # We have not sent th start row scan or have just sent a stop row and nee to find a new one
                if scan_start_idx == scan_stop_idx:

                    # Check if it is time to send out a scan start / stop
                    if raw_ts >= self.data[self.server]['Scan']['row_start_timestamp'][scan_start_idx]:
                        self._send_scan_data(status='scan_start', scan_idx=scan_start_idx)
                        scan_start_idx += 1

                else:

                    # Check if it is time to send out a scan stop
                    if raw_ts >= self.data[self.server]['Scan']['row_stop_timestamp'][scan_stop_idx]:
                        self._send_scan_data(status='scan_stop', scan_idx=scan_stop_idx)
                        scan_stop_idx += 1

        time.sleep(1)

        self._send_scan_data(status='scan_finished')

        self._shutdown_converter()

        self._check_output_data()
        
           
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestConverter)
    unittest.TextTestRunner(verbosity=2).run(suite)
