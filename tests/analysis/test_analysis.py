import os
import logging
import unittest


class TestAnalysisCLI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        cls.fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures')
        cls.fixtures = {'calibration': os.path.join(cls.fixture_path, 'test_calibration'),
                        'irradiation': os.path.join(cls.fixture_path, 'test_irradiation'),
                        'multipart': [os.path.join(cls.fixture_path, f'test_irradiation_multipart_part_{i}') for i in '12']}
        
        # Make output dir
        cls.output_dir = os.path.abspath(os.path.join(cls.fixture_path, '../output'))
        if not os.path.isdir(cls.output_dir):
            os.mkdir(cls.output_dir)


    @classmethod
    def tearDownClass(cls):
        
        # Delete files
        for root, _, files in os.walk(cls.output_dir):
            for fname in files:
                os.remove(os.path.join(root, fname))
        os.rmdir(cls.output_dir)

    def test_entrypoint_CLI(self):

        success = os.system('irrad_analyse --help')
        assert success == 0

    def test_calibration_analysis_CLI(self):

        outfile = os.path.join(self.output_dir, 'test_calibration.pdf')
        success = os.system(f"irrad_analyse -f {self.fixtures['calibration']} --calibration -o {outfile}")
        assert success == 0
        assert os.path.isfile(outfile) and os.path.getsize(outfile) > 0

    def test_multi_calibration_analysis_CLI(self):

        outfile = [os.path.join(self.output_dir, f'test_calibration_multi_{i}.pdf') for i in '12']
        success = os.system("irrad_analyse -f {0} {0} --calibration -o {1} {2} ".format(self.fixtures['calibration'], *outfile))
        assert success == 0
        for o in outfile:
            assert os.path.isfile(o) and os.path.getsize(o) > 0

    def test_damage_analysis_CLI(self):

        outfile = os.path.join(self.output_dir, 'test_damage.pdf')
        success = os.system(f"irrad_analyse -f {self.fixtures['irradiation']} --damage -o {outfile}")
        assert success == 0
        assert os.path.isfile(outfile) and os.path.getsize(outfile) > 0

    def test_beam_analysis_CLI(self):

        outfile = os.path.join(self.output_dir, 'test_beam.pdf')
        success = os.system(f"irrad_analyse -f {self.fixtures['irradiation']} --beam -o {outfile}")
        assert success == 0
        assert os.path.isfile(outfile) and os.path.getsize(outfile) > 0

    def test_scan_analysis_CLI(self):

        outfile = os.path.join(self.output_dir, 'test_scan.pdf')
        success = os.system(f"irrad_analyse -f {self.fixtures['irradiation']} --scan -o {outfile}")
        assert success == 0
        assert os.path.isfile(outfile) and os.path.getsize(outfile) > 0

    def test_multipart_damage_analysis_CLI(self):

        outfile = os.path.join(self.output_dir, 'test_multipart_damage.pdf')
        success = os.system("irrad_analyse -f {0} {1} --damage --multipart -o {2}".format(*self.fixtures['multipart'], outfile))
        assert success == 0
        assert os.path.isfile(outfile) and os.path.getsize(outfile) > 0


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")
    suite = unittest.TestSuite()
    suite.addTest(TestAnalysisCLI)
    unittest.TextTestRunner(verbosity=2).run(suite)
