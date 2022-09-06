from .zaber import ZaberStepAxis, ZaberMultiAxis
from .item import ItemLinearStage
from irrad_control.devices import DEVICES_CONFIG


class ScanStage(ZaberMultiAxis):
    """
    2-dimensional (XY-plane w.r.t beam axis (Z)) motorstage configuration used to scan DUTs through the beam.
    """
    def __init__(self, **kwargs):

        # Get init kwargs from config
        init = DEVICES_CONFIG[type(self).__name__]['init']

        # Update init kwargs if *kwargs* are given
        init.update(kwargs)

        super(ScanStage, self).__init__(**init)


class SetupTableStage(ZaberStepAxis):
    """
    1-dimensional (Z-axis aka beam axis) motorstage which moves the setup table, on which the ScanStage is mounted,
    along the beam axis.
    """
    def __init__(self, **kwargs):

        # Get init kwargs from config
        init = DEVICES_CONFIG[type(self).__name__]['init']

        # Update init kwargs if *kwargs* are given
        init.update(kwargs)

        super(SetupTableStage, self).__init__(**init)


class ExternalCupStage(ItemLinearStage):
    """
    1-dimensional (Y-axis w.r.t beam axis (Z)) motorstage, carrying an external FaradayCup (FC) and
    fluorescence screen combination, allowing to move into and out of the beam directly behind extraction.
    """

    def __init__(self, **kwargs):

        # Get init kwargs from config
        init = DEVICES_CONFIG[type(self).__name__]['init']

        # Update init kwargs if *kwargs* are given
        init.update(kwargs)

        super(ExternalCupStage, self).__init__(**init)
