from .zaber import ZaberStepAxis, ZaberMultiStage
from .item import ItemLinearStage


class ScanStage(ZaberMultiStage):
    
    def __init__(self, port, config=None):
        
        super(ScanStage, self).__init__(n_axis=2, port=port, config=config, invert_axis=(1, ))


class SetupTableStage(ZaberStepAxis):
    
    def __init__(self, port):
        
        super(SetupTableStage, self).__init__()


class ExternalCupStage(ItemLinearStage):
    pass
