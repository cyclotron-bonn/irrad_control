__all__ = ["DaqInfoWidget",
           "LoggingWidget",
           "EventWidget"]

from .daq_info_widget import DaqInfoWidget
from .logging_widget import LoggingWidget
from .event_widget import EventWidget
from .plot_widgets import *  # Justified in this case because it makes all plot widgets available
from .sub_windows import *  # Justified in this case because it makes all sub windows available
from .util_widgets import *  # Justified in this case because it makes all util widgets available

