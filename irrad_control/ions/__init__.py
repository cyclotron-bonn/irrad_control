import os
import logging
import time
import numpy as np
from importlib import import_module

from irrad_control.analysis.constants import elementary_charge
from irrad_control.analysis.formulas import bethe_bloch_Si


class IrradIon(object):

    EKIN_RANGE_PER_NUCLEON = (7., 14.)  # valid for all ions

    def __init__(self, name, n_charge, n_nucleon, data_path=None):

        self.name = name
        self.n_charge = n_charge
        self.n_nucleon = n_nucleon
        self.data_path = os.path.join(os.path.dirname(__file__), name) if data_path is None else data_path

        self._load_data_sets()

    def __repr__(self):
        return f"{self.name.capitalize()}(Z={self.n_charge}, A={self.n_nucleon})"

    def __lt__(self, other):
        return self.n_nucleon < other.n_nucleon
    
    def _load_data_sets(self):

        self._data_sets = {'calibration': 'calibration.dat',
                           'hardness': 'hardness_factor.dat',
                           'stopping': 'stopping_power.dat',
                           'energy': 'dut_energy.dat'}

        self._data = {}

        for dset, dfile in self._data_sets.items():
            dpath = os.path.join(self.data_path, dfile)
            if os.path.isfile(dpath):
                self._data[dset] = np.loadtxt(dpath, delimiter=',', ndmin=2)  # At least 2 dims so you can loop over e.g. calibrations even if there is only one dset
            else:
                self._data[dset] = None

    def _to_dict(self, data):

        helper = lambda d: {'nominal': float(d[1]), 'sigma': float(d[2]), 'energy': float(d[0]), 'date': time.asctime(time.gmtime(d[3]))}

        if isinstance(data, list):
                _data = {i: helper(dat) for i, dat in enumerate(data)}
        elif isinstance(data, np.ndarray):
            _data = helper(data)
        else:
            raise ValueError('Cannot pack data to dict')

        # Get calibration factor for given energy
        return _data

    def _select_data(self, data_type, at_energy=None, at_index=None, as_dict=False, return_index=False):
        
        if self._data[data_type] is None:
            logging.warning(f"No {data_type} data available for ion {self.name}")
            return None
        
        if at_energy is not None:
            closest_idx = (np.abs(self._data[data_type][:,0] - at_energy)).argmin()
            _data = self._data[data_type][closest_idx] if not return_index else closest_idx

        elif at_index is not None:
            _data = self._data[data_type][at_index]

        else:
            _data = [calib for calib in self._data[data_type]]

        if as_dict:
            _data = self._to_dict(_data)

        return _data
    
    def mass(self):
        # TODO: binding energy
        m_proton, m_neutron = 938.272, 939.565  # MeV, MeV
        return self.n_charge * m_proton + (self.n_nucleon - self.n_charge) * m_neutron

    def rate(self, current):
        """
        Returns the *rate* in particles / second, calculated from *current* in Ampere.
        For IrradIons with n_charge = 1 current / elementary charge and rate are the same

        Parameters
        ----------
        current : float
            Ion beam current in Ampere

        Returns
        -------
        ion rate
            Number of ions per second
        """
        # Ions per second
        return current / (self.n_charge * elementary_charge)

    def ekin_range(self):
        """
        Return kinetic energy range as a tuple in MeV

        Returns
        -------
        tuple
            Kinetic energy range in MeV
        """
        return tuple(self.n_nucleon * x  for x in self.EKIN_RANGE_PER_NUCLEON)

    def ekin_at_dut(self, energy):

        if self._data['energy'] is not None:
            return float(np.interp(x=energy, xp=self._data['energy'][:,0], fp=self._data['energy'][:,1]))
        
        logging.warning(f"No simulation data available for {self.name}s. Using input energy of {energy} MeV instead.")
        return float(energy)

    def stopping_power(self, energy, at_dut=False):
        
        tmp_energy = energy if not at_dut else self.ekin_at_dut(energy=energy)

        # Get data from e.g. NIST tables 
        if self._data['stopping'] is not None:
            return float(np.interp(x=tmp_energy, xp=self._data['stopping'][:,0], fp=self._data['stopping'][:,1]))
        
        logging.info(f"No stopping power data available for {self.name}s. Calculate from Bethe-Bloch")
        return bethe_bloch_Si(charge=self.n_charge, mass=self.mass, energy=tmp_energy)

    def calibration(self, at_energy=None, at_index=None, as_dict=False, return_index=False):
        
        return self._select_data(data_type='calibration', at_energy=at_energy, at_index=at_index, as_dict=as_dict, return_index=return_index)

    def hardness_factor(self, at_energy=None, at_index=None, as_dict=False, return_index=False):

        return self._select_data(data_type='hardness', at_energy=at_energy, at_index=at_index, as_dict=as_dict, return_index=return_index)


# Generate all ions
def get_ions():
    """
    Returns a dict with all available IrradIon.name, IrradIon key-value pairs

    Returns
    -------
    dict
        dict with IrradIon.names as keys and the respective IrradIon as value
    """
    ions = []
    for ion in os.listdir(os.path.dirname(__file__)):
        try:
            ions.append(getattr(import_module(f'irrad_control.ions.{ion}'), ion))
        except (ModuleNotFoundError, AttributeError):
            pass
    ions.sort()
    return {ion.name: ion for ion in ions}
