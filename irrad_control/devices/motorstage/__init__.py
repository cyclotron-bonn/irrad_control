from .zaber import ZaberStepAxis, ZaberMultiAxis
from .item import ItemLinearStage


class ScanStage(ZaberMultiAxis):
    """
    2-dimensional (XY-plane w.r.t beam axis (Z)) motorstage configuration used to scan DUTs through the beam.
    """

    # Init kwargs of individual Zaber axes used in the ScanStage
    axis_init = {
        'step': 0.1953125e-6,  # meter
        'travel': 300e-3,  # meter
        'model': 'LRQ300HL-E01T3A'  # https://www.zaber.com/products/linear-stages/LRQ-E/specs?part=LRQ300HL-E01T3A
    }
    
    def __init__(self, port, config=None):

        super(ScanStage, self).__init__(n_axis=2,
                                        port=port,
                                        dev_addrs=(1, 2),
                                        config=config,
                                        invert_axis=(1, ),
                                        **self.axis_init)


class SetupTableStage(ZaberStepAxis):
    """
    1-dimensional (Z-axis aka beam axis) motorstage which moves the setup table, on which the ScanStage is mounted,
    along the beam axis.
    """

    # Init kwargs of individual Zaber axis used in the SetupTableStage
    axis_init = {
        'step': 0.1953125e-6,  # meter
        'travel': 300e-3,  # meter
        'model': 'LRQ300HL-E01T3A'  # https://www.zaber.com/products/linear-stages/LRQ-E/specs?part=LRQ300HL-E01T3A
    }
    
    def __init__(self, port, config=None):
        
        super(SetupTableStage, self).__init__(port=port,
                                              dev_addr=3,
                                              config=config,
                                              **self.axis_init)


class ExternalCupStage(ItemLinearStage):
    """
    1-dimensional (Y-axis w.r.t beam axis (Z)) motorstage, carrying an external FaradayCup (FC) and
    fluorescence screen combination, allowing to move into and out of the beam directly behind extraction.
    """

    def __init__(self, host, port, udp=('131.220.221.224', '8802'), config=None):

        super(ExternalCupStage, self).__init__(host=host,
                                               port=port,
                                               udp=udp,
                                               config=config)
