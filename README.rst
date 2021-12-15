=============================
Irrad_Control |test-status|
=============================

Introduction
============

``irrad_control`` is a **irradiation control**, **data acquisition** (DAQ) as well as **visualization** and analysis software for the proton irradiation site at the `Bonn isochronous cyclotron <https://www.zyklotron.hiskp.uni-bonn.de/zyklo_e/index.html>`_, located at the Helmholtz Institut für Strahlen- und Kernphysik (`HISKP <https://www.hiskp.uni-bonn.de/>`_), of Bonn University.
It consists of few Python-scripts which are running on a host PC (GUI-based around `PyQt <https://riverbankcomputing.com/software/pyqt/intro>`_) and on-site *Raspberry Pi* server(s) interfacing irradiation-related hardware.
Communication and DAQ is done via `pyZMQ <https://pyzmq.readthedocs.io/en/latest/>`_, all data is recorded and stored as binary data in `HDF5 <https://www.pytables.org/>`_.
For more information on the irradiation site at Bonn University please visit the `homepage <https://silab-bonn.github.io/irrad_control/>`_

.. _ImageLink: https://www.zyklotron.hiskp.uni-bonn.de/zyklo/images/hsr_exp_1_low.JPG

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

To be able to run the tests locallay, install the `pytest` package

.. code-block::

  pip install pytest

To finally install ``irrad_control`` on the DAQ PC run the setup script

.. code-block:: bash

   python setup.py develop

Once you start the application the server(s) are set up automatically. To add servers, they need to be prepared as stated below and added in the setup tab of ``irrad_control``.

Server Setup
============

The data acquisition and control of irradiation setup is done by one (or multiple) Raspberry Pi (RPi) server. Before first usage with `irrad_control`,
each server RPi needs to be aware of the ``ssh key`` of the host PC. Therefore, copy the hosts ``ssh key`` to each RPi server via

.. code-block::

   ssh-copy-id pi@ip-address-of-rpi

where ``ip-address-of-rpi`` is the IP address of the RPi within the network. In case you need to create a ``ssh key`` of the host PC first, you can do so by

.. code-block::

   ssh-keygen -b 2048 -t rsa

After launching ``irrad_control``, you can perform a first-time-setup of the server by adding it via its IP address. Aftr that,  you can add the server via its IP addressThe server is then automatically set up on first use with ``irrad_control``.

DAQ
===

During irradiations, the extracted beam current is measured continuously via a dedicated **s**\econdary **e**\lectron **m**\onitor (SEM) and R/O electronics.
An `ADDA board <https://www.waveshare.com/wiki/High-Precision_AD/DA_Board>`_ is used to digitize the beam current measurment with rates between 20 - 150 Hz.
A 2D-motorstage is used to scan devices inside a cooling box through the beam. Scan parameters such as scan speed and start/end positions are logged for each stage axis movement.
Furthermore, several NTCs are located inside the cooling box which is cooled via nitrogen gas. The NTCs are read out via the R/O electronics with ~ 1 Hz.
For more information please visit the `homepage <https://silab-bonn.github.io/irrad_control/>`_


.. |test-status| image:: https://github.com/Silab-Bonn/irrad_control/actions/workflows/main.yml/badge.svg?branch=development
    :target: https://github.com/SiLab-Bonn/irrad_control/actions
    :alt: Build status
