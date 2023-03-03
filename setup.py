#!/usr/bin/env python
import sys
from setuptools import setup, find_packages  # This setup relies on setuptools since distutils is insufficient and badly hacked code

# Figure out if we're installing on control PC or on server
_server = 'server' in sys.argv

# Remove "server" from sys.argv
if _server:
    sys.argv.remove('server')

version = '2.0.1'
author = 'Pascal Wolf'
author_email = 'wolf@physik.uni-bonn.de'

with open('requirements.txt' if not _server else 'requirements_server.txt') as f:
    required = f.read().splitlines()

# Make dict to pass to setup
setup_kwargs = {'name': 'irrad_control',
                'version': version,
                'description': 'Control, DAQ and analysis software for the irradiation facility at HISKP cyclotron at Bonn University',
                'url': 'https://github.com/Cyclotron-Bonn/irrad_control',
                'license': 'MIT License',
                'long_description': '',
                'author': author,
                'maintainer': author,
                'author_email': author_email,
                'maintainer_email': author_email,
                'packages': find_packages(),
                'setup_requires': ['setuptools'],
                'install_requires': required,
                'include_package_data': True,  # accept all data files and directories matched by MANIFEST.in or found in source control
                'package_data': {'': ['README.*', 'VERSION'], 'docs': ['*'], 'examples': ['*']},
                'keywords': ['radiation damage', 'NIEL', 'silicon', 'irradiation', 'proton', 'fluence'],
                'platforms': 'any',
                'entry_points': {'console_scripts': ['irrad_control = irrad_control.main:main', 'irrad_analyse = irrad_control.analysis.main:main']}
                }

# Setup
setup(**setup_kwargs)
