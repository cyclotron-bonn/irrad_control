import os
import logging
import unittest


class TestAnalysisCLI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        cls.fixture_path = os.path.join(os.path.dirname(__file__), '../fixtures')
        cls.fixtures = {'calibration': os.path.join(cls.fixture_path, 'test_calibration'),
                        'irradiation': os.path.join(cls.fixture_path, 'test_irradiation'),
                        'multipart': [os.path.join(cls.fixture_path, f'test_irradiation_multipart_part_{i}') for i in '12']}
        
        # Make output dir
        cls.output_dir = os.path.join(os.path.dirname(__file__), 'output')
        if not os.path.isdir(cls.output_dir):
            os.mkdir(cls.output_dir)


    @classmethod
    def tearDownClass(cls):
        
        # Delete files
        for root, _, files in os.walk(cls.output_dir):
            for fname in files:
                os.remove(os.path.join(root, fname))
        os.rmdir(cls.output_dir)

    def _run_cli_analysis(self, analysis, infile, flags=None, cli_str=None):

        if cli_str is not None:
            # Run CLI and check return status
            success = os.system(f'{cli_str}')
            
            # Check return value
            assert success == 0

        else: 
            # Create output file
            outfile = os.path.join(self.output_dir, f'test_{analysis}.pdf')

            infile = infile if isinstance(infile, list) else [infile]    
            
            # Run CLI and check return status
            success = os.system("irrad_analyse -f {} --{} -o {} {}".format(' '.join(infile), analysis, outfile, '' if flags is None else ' '.join(flags)))
            
            # Check return value
            assert success == 0
            
            # Check file exists and has content
            assert os.path.isfile(outfile) and os.path.getsize(outfile) > 0

    def test_entrypoint(self):
        self._run_cli_analysis(analysis=None, infile=None, cli_str='irrad_analyse --help')

    def test_calibration(self):
        self._run_cli_analysis(analysis='calibration', infile=self.fixtures['calibration'])

    def test_beam(self):
        self._run_cli_analysis(analysis='beam', infile=self.fixtures['calibration'])

    def test_scan(self):
        self._run_cli_analysis(analysis='scan', infile=self.fixtures['irradiation'])

    def test_damage(self):
        self._run_cli_analysis(analysis='damage', infile=self.fixtures['irradiation'])

    def test_multipart_damage(self):
        self._run_cli_analysis(analysis='damage', infile=self.fixtures['multipart'], flags=['--multipart'])

    def test_irradiation(self):
        self._run_cli_analysis(analysis='irradiation', infile=self.fixtures['irradiation'])

    def test_multifile_analysis(self):
        cli_str = 'irrad_analyse -f {} --scan -o {}'.format(' '.join(self.fixtures['multipart']), ' '.join([os.path.join(self.output_dir, x) for x in ['test_mutlifile_scan1.pdf', 'test_mutlifile_scan2.pdf']]))
        self._run_cli_analysis(analysis=None, infile=None, cli_str=cli_str)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")
    suite = unittest.TestSuite()
    suite.addTest(TestAnalysisCLI)
    unittest.TextTestRunner(verbosity=2).run(suite)
