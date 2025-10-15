=============================
Irrad_Control |test-status|
=============================

Introduction
============

``irrad_control`` is the control, data acquisition and analysis software, written in Python, of the `proton irradiation site <https://www.zyklotron.hiskp.uni-bonn.de/zyklo/experiments_cyclotron_EN.html#one>`_
at the `Bonn isochronous cyclotron <https://www.zyklotron.hiskp.uni-bonn.de/zyklo/index_EN.html>`_, located at the Helmholtz Institut für Strahlen- und Kernphysik (`HISKP <https://www.hiskp.uni-bonn.de/>`_), of Bonn University.
The software allows control and data acquisition of all relevant components of an irradiation setup and is designed to be easily adaptable for different setups.
It consists of three main components

- A graphical user interface (GUI) for data visualization and setup control
- A (or multiple) server processes interfacing the hardware components of the setup 
- An converter process, analysing and storing the data of all servers for visualization and setup feedback

This design enables to run multiple irradiation setups from one, centralized, GUI-interface simultaneously.
During irradiation, ion beam characteristics and radiation-related quantities such as primary or 1 MeV neutron equivalent fluence,
total-ionizing dose as well as ion currents are monitored in real-time, allowing high-uniformity damage distributions.

Conventionally, the an ``irrad_control`` server is hosted on a RaspberryPi (RPi) single-board computer, interfacing the setup components via Serial, I2C, etc.
Scripts to setup such servers on RPis are integrated in ``irrad_control``.

Data acquired during irradiations is stored in binary `HDF5 <https://www.pytables.org/>`_ files. The software furthermore provides a set of offline
analysis methods for irradiation datasets which produce comprehensive plots.

For a list of publications using ``irrad_control`` see `here <https://www.zyklotron.hiskp.uni-bonn.de/zyklo/publications_EN.html>`_ or in the `Publications` section below.

Installation
============

Prerequisites
-------------

``irrad_control`` requires Python >= 3.11 (3.11 and latest (3.X) are tested). When installing using the ``install.sh`` script (see below), the current active Python environment is used to create a virtual environment.
However, it is recommended to use a Python interpreter isolated from your system Python such as `Miniconda <https://conda.io/miniconda.html>`_. After installation, the included ``conda`` package manager
allows to easily create new, isolated environments and activate them using the ``conda activate YourEnvName`` command.

Install script
--------------

Download the `install.sh <./scripts/install.sh>`_ script, make it executable by typing ``chmod +x install.sh`` and run

.. code-block:: bash

   ./install.sh

This will download ``irrad_control`` to the current directory, create a virtual Python envirnoment at ``.venv`` and install ``irrad_control`` in it.
If you alrady have a copy of ``irrad_control`` (e.g. in your version control) you can point to it instead of downloading a new copy by passing the ``--ic_path`` flag

.. code-block:: bash

   ./install.sh --ic_path=/path/to/irrad_control

If you want to install ``irrad_control`` without wanting the script to create a virtual environment for you (e.g. because you use your own isolated ``conda`` environment),
pass the ``--no_venv`` flag to directly install into the active Python environment

.. code-block:: bash

   ./install.sh --no_venv

To see an overview of options call ``./install --help``. The software is now available via

.. code-block:: bash

   irrad_control

Manual installation
-------------------

To install ``irrad_control``, first clone the repository, then move into its root directory and run

.. code-block:: bash

   pip install -e .

which installs into the activate Python envoronment in editable mode, allowing to make changes to the code if needed. The software is now available via

.. code-block:: bash

   irrad_control

Quick Setup
============

The data acquisition and control of irradiation setup is done by one (or multiple) Raspberry Pi (RPi) server. Before first usage with `irrad_control`,
each server RPi needs to be aware of the ``ssh key`` of the host PC. Therefore, copy the hosts ``ssh key`` to each RPi server via

.. code-block::

   ssh-copy-id pi@ip-address-of-rpi

where ``ip-address-of-rpi`` is the IP address of the RPi within the network. In case you need to create a ``ssh key`` of the host PC first, you can do so by

.. code-block::

   ssh-keygen -b 2048 -t rsa

After launching ``irrad_control``, you can perform a first-time-setup of the server by adding it via its IP address.
The server is then automatically set up on first use with ``irrad_control``.


Offline Analysis
================

From version v1.3.0 onwards, ``irrad_control`` ships with offline analysis utilities, allowing to analyse e.g. irradiation or calibration data.
The output of ``irrad_control`` are two different file types with the same base name (e.g. ``my_irrad_file``), one containing the configuration (*YAML*) and the other the actual data (*HDF5*).
Both files are required to be present in the same directory.

**Note**: *Irradiation output files recorded with version 1.3.0 are not compatible with the analysis of versions 2.x.x and greater.
Please check out the software to the respective version to analyse older files!*

To analyse irradiation data (e.g. NIEL / TID / fluence) use the ``irrad_analyse`` CLI:

.. code-block:: bash

   irrad_analyse -f my_irrad_file  # No file ending required; --damage (NIEL, TID) is default analysis flag 

which will generate a ``my_irrad_file_analysis_damage.pdf`` output file. Optionally, the ``-o my_custom_output_file.pdf`` option / value pair can be given to give a custom output file name.
To analyse multiple files at once, pass them individually to the `-f` otpion

.. code-block:: bash

   irrad_analyse -f my_irrad_file_0 my_irrad_file_1 my_irrad_file_2
   irrad_analyse -f *.h5  # Analyse all HDF5 files in the current directory

Furthermore, irradiations which were carried out in multiple sessions (e.g. multiple output config / data files) can be analysed by passing the ``--multipart`` flag.
To analyse an multi-file irradiation, pass the list of file base names

.. code-block:: bash

   irrad_analyse -f my_irrad_file_0 my_irrad_file_1 my_irrad_file_2 --multipart
   irrad_analyse -f *.h5 --multipart  # Take all HDF5 files in the current directory

To analyse beam monitor calibration measurements, pass the ``--calibration`` flag.

.. code-block:: bash

   irrad_analyse -f my_calibration_file --calibration
   irrad_analyse -f *.h5 --calibration  # Take all HDF5 files in the current directory

To see the CLI options type

.. code-block:: bash

   irrad_analyse --help

Fluence Distributions
---------------------

1 MeV neutron equivalent fluence distribution with their respective uncertainties, generated by the ``irrad_analyse`` CLI,
from irradiation data of an ITkPixV1 Si-pixel detector, irradiatied to 1e16 neq/cm².

.. list-table::

    * - .. figure:: ../assets/ITkPixV1_1e16_scan_neq_nominal.jpg?raw=true

           1 MeV neutron equivalent fluence, scan area, 1e16 neq/cm²

      - .. figure:: ../assets/ITkPixV1_1e16_scan_neq_error.jpg?raw=true

           1 MeV neutron equivalent fluence uncertainty, scan area, , 1e16 neq/cm²

    * - .. figure:: ../assets/ITkPixV1_1e16_dut_neq_nominal.jpg?raw=true

           1 MeV neutron equivalent fluence, DUT area, , 1e16 neq/ cm²

      - .. figure:: ../assets/ITkPixV1_1e16_dut_neq_error.jpg?raw=true

           1 MeV neutron equivalent fluence uncertainty, DUT area, , 1e16 neq/cm²

Changelog
=========

- v2.4.3: Big fixes and maintenance, see see `release <https://github.com/Cyclotron-Bonn/irrad_control/releases/tag/v2.4.3>`_
- v2.4.2: Big fixes and maintenance, see see `release <https://github.com/Cyclotron-Bonn/irrad_control/releases/tag/v2.4.2>`_
- v2.4.1: Big fixes and maintenance, see see `release <https://github.com/Cyclotron-Bonn/irrad_control/releases/tag/v2.4.1>`_
- v2.4.0: Maintenance and minor bugs, see see `release <https://github.com/Cyclotron-Bonn/irrad_control/releases/tag/v2.4.0>`_
- v2.3.1: Bug fixes and maintenance, see see `release <https://github.com/Cyclotron-Bonn/irrad_control/releases/tag/v2.3.1>`_
- v2.3.0: Extended analysis capabilities and SEE data acquisition, see `release <https://github.com/Cyclotron-Bonn/irrad_control/releases/tag/v2.3.0>`_
- v2.2.1: Bug fixes and maintenance, see `release <https://github.com/Cyclotron-Bonn/irrad_control/releases/tag/v2.2.1>`_
- v2.2.0: Event distribution system and Bethe-Bloch stopping power calculation for arbitrary ions, bug fixes, see `release <https://github.com/Cyclotron-Bonn/irrad_control/releases/tag/v2.2.0>`_
- v2.1.0: Separate monitor GUI, ``.desktop``-file allowing to launch from activieties, bug fixes, see `release <https://github.com/Cyclotron-Bonn/irrad_control/releases/tag/v2.1.0>`_
- v2.0.1: Bug fixes, see `release <https://github.com/Cyclotron-Bonn/irrad_control/releases/tag/v2.0.1>`_
- v2.0.0: Full support for the updated irradiation setup, major restructure, flexible irradiation procedures, new features, see `release <https://github.com/Cyclotron-Bonn/irrad_control/releases/tag/v2.0.0>`_
- v1.3.0: Included module for offline analysis of e.g. irradiation data, see `release <https://github.com/SiLab-Bonn/irrad_control/releases/tag/v1.3.0>`_
- v1.2.0: First version with partial support for updated irradiation setup running on Python 3, see `release <https://github.com/SiLab-Bonn/irrad_control/releases/tag/v1.2.0>`_
- v1.1.0: Deprecated version supporting Python 2/3 as well as deprecated irradiation setup, see `release <https://github.com/SiLab-Bonn/irrad_control/releases/tag/v1.1.0>`_
- v1.0.1: Initial release with semantic versioning, see `release <https://github.com/SiLab-Bonn/irrad_control/releases/tag/v1.0.1>`_

Documentation
=============

For information on the software structure, data formats and general usage please see the wiki. (TBD)

Proton Irradiation Site
=======================

The proton irradiation site for silicon devices at Bonn University is in operation since early 2020. Typically, a proton beam of 14 MeV kinetic energy, a current of 1 µA and a diameter of a few mm
is used to irradiate devices-under-test (DUTs) in a temperature-controlled box. To achieve homogeneous irradiation, the DUT is scanned through the beam in a row-wise grid, using a two-dimensional 
motorstage. The fluence is determined via online measurement of the beam current at extraction to the DUT during the irradiation procedure. A picture of the setup can be seen below. For further
information on the setup, the irradiation procedure & characteristics or addiational material please visit the `homepage <https://www.zyklotron.hiskp.uni-bonn.de/zyklo/experiments_cyclotron_EN.html#one/>`_

.. image:: https://www.zyklotron.hiskp.uni-bonn.de/zyklo/images/hsr_exp_1_low.JPG
   :width: 800
   :align: center

Publications
============

Publications related to the proton irradiation site can be found `here <https://www.zyklotron.hiskp.uni-bonn.de/publications_EN.html>`_, on the the cyclotron homepage. If you are publishing results obtained by performing
irradiations or test beams at the proton irradiation site at Bonn university, please cite he paper below:

`P. Wolf, D. Sauerland, R. Beck and J. Dingfelder, “A beam-driven proton irradiation setup for precision radiation damage tests of silicon detectors”, NIMA Volume 1064, July 2024, doi:10.1016/j.nima.2024.169358 <https://www.sciencedirect.com/science/article/pii/S0168900224002845>`_


.. |test-status| image:: https://github.com/Cyclotron-Bonn/irrad_control/actions/workflows/main.yml/badge.svg?branch=main
    :target: https://github.com/Cyclotron-Bonn/irrad_control/actions
    :alt: Build status
