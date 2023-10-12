import os
import sys
import logging
import unittest

from irrad_control import package_path


class TestExamples(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        # get all example files
        cls.example_dir = os.path.join(package_path, '../examples')
        cls.examples = [example for example in os.listdir(cls.example_dir) if example.endswith('.py')]

    @classmethod
    def tearDownClass(cls):
        pass

    def test_examples(self):

        for example in self.examples:
            success = os.system(f"{sys.executable} {os.path.join(self.example_dir, example)}")
            assert success == 0, f"Examples {example} failed!"


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")
    suite = unittest.TestSuite()
    suite.addTest(TestExamples)
    unittest.TextTestRunner(verbosity=2).run(suite)
