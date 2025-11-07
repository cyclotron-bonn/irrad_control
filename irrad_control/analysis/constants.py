"""Collection of constants needed"""

# Elementary charge
elementary_charge = 1.60217733e-19  # Coulomb

# Kelvin
kelvin = 273.15  # Degree Celsius

# nano prefix
nano = 1e-9

# Conversion factor for MeV/g to Mrad, 1 eV = 1.602e-19 J, 1 rad = 0.01 J/kg
# -> MeV / g = 1e6 * 1.602e-19 J / 1e-3 kg
# -> MeV / g = 1e9 * 1.602e-19 J / kg
# -> MeV / g = 1e9 * 1.602e-19 * 1e2 rad
# -> MeV / g = 1e11 * 1.602e-19 rad
# -> Mev / g = 1e5 * 1.602e-19 Mrad
# -> Mev / g = 1e5 * elementary_charge * Mrad
MEV_PER_GRAM_TO_MRAD = 1e5 * elementary_charge

# Masses
m_e = 0.511  # MeV/c^2
m_p = 938.272  # MeV/c^2
m_n = 939.565  # MeV/c^2
