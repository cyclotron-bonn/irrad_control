from collections import namedtuple
from irrad_control.utils.tools import location, load_yaml, make_path

DAQ_BOARD_CONFIG = load_yaml(make_path(location(__file__), "daq_board_config.yaml"))
RO_ELECTRONICS_CONFIG = load_yaml(make_path(location(__file__), "ro_electronics_config.yaml"))
BEAM_MONITOR_CONFIG = load_yaml(make_path(location(__file__), "beam_monitor_config.yaml"))

RO_DEVICES = namedtuple("ReadoutDevices", "ReadoutElectronics DAQBoard")(
    ReadoutElectronics="ReadoutElectronics", DAQBoard="DAQBoard"
)

RO_TYPES = ("sem_left", "sem_right", "sem_up", "sem_down", "sem_sum", "cup", "blm", "ntc", "general_purpose")

RO_DEFAULTS = {
    "ch_names": ("Left", "Right", "Up", "Down", "Sum", "BLM", "FC"),
    "ch_types": ("sem_left", "sem_right", "sem_up", "sem_down", "sem_sum", "blm", "cup"),
    "ch_groups": ("sem", "sem", "sem", "sem", "sem", "ch12", "ch12"),
}
