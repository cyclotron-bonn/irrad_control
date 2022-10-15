import os
from irrad_control.ions import IrradIon


proton = IrradIon(name='proton', n_charge=1, n_nucleon=1, data_path=os.path.dirname(__file__))
