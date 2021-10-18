from .zaber import ZaberStepAxis, ZaberMultiAxis
from .item import ItemLinearStage


class ScanStage(ZaberMultiAxis):
    """
    2-dimensional (XY-plane w.r.t beam axis (Z)) motorstage configuration used to scan DUTs through the beam.
    """
    pass


class SetupTableStage(ZaberStepAxis):
    """
    1-dimensional (Z-axis aka beam axis) motorstage which moves the setup table, on which the ScanStage is mounted,
    along the beam axis.
    """
    pass


class ExternalCupStage(ItemLinearStage):
    """
    1-dimensional (Y-axis w.r.t beam axis (Z)) motorstage, carrying an external FaradayCup (FC) and
    fluorescence screen combination, allowing to move into and out of the beam directly behind extraction.
    """
    pass
