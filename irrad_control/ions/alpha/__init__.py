import os
from irrad_control.ions import IrradIon



alpha = IrradIon(name='alpha', n_charge=2, n_nucleon=4, data_path=os.path.dirname(__file__))
