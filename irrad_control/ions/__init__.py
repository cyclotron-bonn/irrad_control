import os
import logging
import time
import numpy as np
from dataclasses import dataclass
from importlib import import_module


@dataclass
class IrradIon:
    
    name: str  # Ion name
    n_charge: int  # Number of elementary charges
    n_nucleon: int  # Number of nucleons
    _energy_range_per_nucleon: tuple = (7., 14.)  # 7 to 14 MeV per nucleon

    def __post_init__(self):

        self._load_data_sets()
    
    def _load_data_sets(self):

        self._data_sets = {'calibration': 'calibration.dat',
                           'hardness': 'hardness_factor.dat',
                           'stopping': 'stopping_power.dat',
                           'energy': 'dut_energy.dat'}

        self._data = {}

        for dset, dfile in self._data_sets.items():
            if os.path.isfile(dfile):
                self._data[dset] = np.loadtxt(dfile, delimiter=',', ndmin=2)  # At least 2 dims so you can loop over e.g. calibrations even if there is only one dset
            else:
                self._data[dset] = None

    def _to_dict(self, data):

        # Get calibration factor for given energy
        return {'nominal': data[1], 'sigma': data[2], 'energy': data[0], 'date': time.asctime(time.gmtime(data[3]))}

    def ekin_range(self):
        """
        Return kinetic energy range as a tuple in MeV

        Returns
        -------
        tuple
            Kinetic energy range in MeV
        """
        return tuple(self.n_nucleon * x  for x in self._energy_range_per_nucleon)

    def ekin_at_dut(self, energy):

        if self._data['energy'] is not None:
            return np.interp(x=energy, xp=self._data['energy'][:,0], fp=self._data['energy'][:,1])
        
        logging.warning(f"No simulation data available for {self.name}s. Using input energy of {energy} MeV instead.")
        return energy

    def stopping_power_at_dut(self, energy):
        
        if self._data['stopping'] is not None:
            return np.interp(x=energy, xp=self._data['stopping'][:,0], fp=self._data['stopping'][:,1])
        
        logging.warning(f"No stopping power data available for {self.name}s.")
        return None

    def calibrations(self):
        if self._data['calibration'] is not None:
            return [calib for calib in self._data['calibration']]

    def calibration_data(self, energy, return_idx=False):

        if self._data['calibration'] is not None:
            # Get calibration factor for given energy
            closest_idx = (np.abs(self._data['calibration'][:,0] - energy)).argmin()
            return self._data['calibration'][closest_idx] if not return_idx else closest_idx

    def calibration_to_dict(self, cal_data):
        return self._to_dict(data=cal_data)

    def hardness_factors(self):
        if self._data['hardness'] is not None:
            return [kappa for kappa in self._data['hardness']]

    def hardness_factor_data(self, energy, return_idx=False):
        if self._data['hardness'] is not None:
            # Get calibration factor for given energy
            closest_idx = (np.abs(self._data['hardness'][:,0] - energy)).argmin()
            return self._data['hardness'][closest_idx] if not return_idx else closest_idx

    def hardness_factor_to_dict(self, kappa_data):
        # Get calibration factor for given energy
        return self._to_dict(data=kappa_data)


# Generate all ions
ions = []
for ion in os.listdir(os.path.dirname(__file__)):
    try:
        ions.append(getattr(import_module(f'irrad_control.ions.{ion}'), ion))
    except (ModuleNotFoundError, AttributeError):
        pass
