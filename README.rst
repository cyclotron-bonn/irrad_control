=============================
Irrad_Control |test-status|
=============================

Introduction
============

``irrad_control`` is a Python package for data acquisition and control of the proton irradiation site at the 
`Bonn isochronous cyclotron <https://www.zyklotron.hiskp.uni-bonn.de/zyklo/index_EN.html>`_, 
located at the Helmholtz Institut für Strahlen- und Kernphysik (`HISKP <https://www.hiskp.uni-bonn.de/>`_), of Bonn University.
The software features a graphical user interface (GUI), based on `PyQt <https://riverbankcomputing.com/software/pyqt/intro>`_, 
from which the individual setup components can be managed and irradiations can be conducted. Furthermore, the GUI offers online data
visualization of proton beam characteristics and irradiation-specific quantities such as e.g. proton fluence.
The setup control and data acquisition is provided by a (or multiple) Raspberry Pi (RPi) server which is managed by ``irrad_control``,
all acquired data is stored in the binary `HDF5 <https://www.pytables.org/>`_ format. The software furthermore provides a set of analysis methods
for irradiation datasets which produce comprehensive plots.

Installation
============

You have to have Python >= 3.7 with the following packages installed:

- numpy
- pyyaml
- pyzmq
- pytables
- pyqt
- `pyqtgraph <http://pyqtgraph.org/>`_
- matplotlib
- paramiko
- uncertainties

It's recommended to use a Python environment separate from your system Python. To do so, please install `Miniconda <https://conda.io/miniconda.html>`_.
After installation you can use the package manager ``conda`` to install the required packages

.. code-block:: bash

   conda install numpy pyyaml pytables pyqt pyzmq pyserial pyqtgraph paramiko matplotlib

To install the required packages that are not available via ``conda``, use `pip`

.. code-block::

  pip install uncertainties bitstring pytest

To finally install ``irrad_control`` run the setup script

.. code-block:: bash

   python setup.py develop

When you start the application you can add RPi servers in the **setup** tab. Each server needs to be set up before usage.
The procedure is explained in the following section.

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


.. |test-status| image:: https://github.com/Silab-Bonn/irrad_control/actions/workflows/main.yml/badge.svg?branch=development
    :target: https://github.com/SiLab-Bonn/irrad_control/actions
    :alt: Build status
