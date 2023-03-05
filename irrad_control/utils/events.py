from enum import Enum
from threading import Event
from time import time


class BaseEvent(object):

    @property
    def active(self):
        return self._active_event.is_set()

    @active.setter
    def active(self, status):
        if status:
            self._active_event.set()
            self._last_triggered = time()
        else:
            self._active_event.clear()

    @property
    def disabled(self):
        return self._disabled_event.is_set()

    @disabled.setter
    def disabled(self, disabled):
        if disabled:
            self._disabled_event.set()
        else:
            self._disabled_event.clear()

    def __init__(self, cooldown=0, description=''):
        super().__init__()
        
        self.cooldown = cooldown
        self.description = description

        self._last_triggered = None
        self._active_event = Event()
        self._disabled_event = Event()

    def wait_for_active(self, timeout=None):
        return self._active_event.wait(timeout=timeout)

    def is_ready(self):
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

    @classmethod
    def beam_events(cls):
        return Enum('BeamEvents', [(ev.name, ev.value) for ev in cls if 'Beam' in ev.name])

    @classmethod
    def beam_ok(cls):
        return not any(ev.value.active for ev in cls.beam_events() if not ev.value.disabled)

    @classmethod
    def to_dict(cls, event):
        try:
            return {'event': cls[event].name,
                    'active': cls[event].value.active,
                    'disabled': cls[event].value.disabled,
                    'description': cls[event].value.description}
        except KeyError:
            raise KeyError(f"'{event}' not in IrradEvents! \
                             Available events: {', '.join(ev.name for ev in cls)}")