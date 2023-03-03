from enum import Enum
from threading import Event
from time import time


class BaseEvent(Event):

    @property
    def active(self):
        return self.is_set()

    @active.setter
    def active(self, status):
        if status:
            self.set()
        else:
            self.clear()

    def __init__(self, cooldown=0, description=''):
        super().__init__()
        
        self.cooldown = cooldown
        self.description = description

        self._last_triggered = None

    def set(self):
        super().set()
        self._last_triggered = time()

    def ready(self):
        return True if self._last_triggered is None else time() - self._last_triggered > self.cooldown

    
class IrradEvents(Enum):

    # Beam-related events
    BeamOff = BaseEvent(cooldown=1, description="Beam current below measureable resolution")
    BeamUnstable = BaseEvent(cooldown=1, description="Beam current fluctuates")
    BeamLoss = BaseEvent(cooldown=1, description="Beam current lost at extraction")
    BeamDrift = BaseEvent(cooldown=1, description="Beam position deviates from center")
    BeamLow = BaseEvent(cooldown=1, description="Beam current below threshold")

    # Temperature
    DUTTempHigh = BaseEvent(cooldown=20, description="Temperature of DUT high")
    BLMTempHigh = BaseEvent(cooldown=20, description="Temperature of beam loss monitor high")

    # Misc
    DoseRateHigh = BaseEvent(cooldown=60, description="Dose rate high")
