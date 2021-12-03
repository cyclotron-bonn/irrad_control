=============================
Irrad_Control |`https://github.com/Silab-Bonn/pylandau/actions/workflows/tests.yml/badge.svg?branch=master`_|
=============================

Introduction
============

``irrad_control`` is a **irradiation control**, **data acquisition** (DAQ) as well as **visualization** and analysis software for the proton irradiation site at the `Bonn isochronous cyclotron <https://www.zyklotron.hiskp.uni-bonn.de/zyklo_e/index.html>`_, located at the Helmholtz Institut für Strahlen- und Kernphysik (`HISKP <https://www.hiskp.uni-bonn.de/>`_), of Bonn University.
It consists of few Python-scripts which are running on a host PC (GUI-based around `PyQt <https://riverbankcomputing.com/software/pyqt/intro>`_) and on-site *Raspberry Pi* server(s) interfacing irradiation-related hardware.
Communication and DAQ is done via `pyZMQ <https://pyzmq.readthedocs.io/en/latest/>`_, all data is recorded and stored as binary data in `HDF5 <https://www.pytables.org/>`_.
For more information on the irradiation site at Bonn University please visit the `homepage <https://silab-bonn.github.io/irrad_control/>`_

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

It's recommended to use a Python environment like `Miniconda <https://conda.io/miniconda.html>`_. After installation you can use Minicondas package manager ``conda`` to install the required packages

.. code-block:: bash

   conda install numpy pyyaml pytables pyqt pyzmq pyqtgraph paramiko matplotlib

To install the `uncertainties` package use `pip`

.. code-block::

  pip install uncertainties

To finally install ``irrad_control`` on the DAQ PC run the setup script

.. code-block:: bash

   python setup.py develop

Once you start the application the server(s) are set up automatically. To add servers, they need to be prepared as stated below and added in the setup tab of ``irrad_control``.

Setup Control
=============

The irradiation setup is controlled and monitored from one (or multiple) Raspberry Pi server(s). For this,
``ssh key`` of the host PC must be copied to each server Raspberry Pi. Create and copy a key via

.. code-block::

   ssh-keygen -b 2048 -t rsa
   ssh-copy-id pi@ip

where ``ip`` is the ip of the Raspberry Pi within the network. The server is then automatically set up on first use with ``irrad_control``.

DAQ
===

During irradiations, the extracted beam current is measured continuously via a dedicated **s**\econdary **e**\lectron **m**\onitor (SEM) and R/O electronics.
An `ADDA board <https://www.waveshare.com/wiki/High-Precision_AD/DA_Board>`_ is used to digitize the beam current measurment with rates between 20 - 150 Hz.
A 2D-motorstage is used to scan devices inside a cooling box through the beam. Scan parameters such as scan speed and start/end positions are logged for each stage axis movement.
Furthermore, several NTCs are located inside the cooling box which is cooled via nitrogen gas. The NTCs are read out via the R/O electronics with ~ 1 Hz.
For more information please visit the `homepage <https://silab-bonn.github.io/irrad_control/>`_


.. |travis-status| image:: https://api.travis-ci.com/SiLab-Bonn/irrad_control.svg?branch=development
    :target: https://travis-ci.com/SiLab-Bonn/irrad_control
    :alt: Build status
