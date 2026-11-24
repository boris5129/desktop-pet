from dataclasses import dataclass, field
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Pet:
    name: str = "피카츄"
    level: int = 1
    xp: int = 0
    fullness: int = 80
    happiness: int = 80
    energy: int = 100
    clicks: int = 0
    interactions: int = 0
    created: str = field(default_factory=now)
    last_seen: str = field(default_factory=now)
    last_meal: str = ""
    state: str = "대기"
    elapsed: dict = field(default_factory=dict)

    @property
    def target(self):
        return 100 + 25 * (self.level - 1)

    def change(self, fullness=0, happiness=0, energy=0, xp=0):
        for key, delta in (("fullness", fullness), ("happiness", happiness), ("energy", energy)):
            setattr(self, key, max(0, min(100, getattr(self, key) + delta)))
        self.xp += xp
        previous = self.level
        while self.xp >= self.target:
            self.xp -= self.target
            self.level += 1
        return previous != self.level

    def interact(self, action):
        self.interactions += 1
        if action == "click":
            self.clicks += 1
        if action == "feed":
            self.last_meal = now()
        return self.change(*ACTIONS[action])

    def advance(self, seconds):
        changed = False
        for clock, stat, interval, delta in TIMERS:
            if clock == "sleep" and self.state != "수면":
                continue
            if clock == "active" and self.state == "수면":
                continue
            count, self.elapsed[clock] = divmod(self.elapsed.get(clock, 0) + seconds, interval)
            if count:
                self.change(**{stat: int(count) * delta})
                changed = True
        return changed


ACTIONS = {
    "click": (0, 2, 0, 1),
    "feed": (25, 5, 0, 0),
    "play": (-5, 20, -10, 10),
    "pet": (0, 5, 0, 1),
}
TIMERS = (
    ("fullness", "fullness", 600, -2),
    ("happiness", "happiness", 900, -1),
    ("active", "energy", 600, -1),
    ("sleep", "energy", 60, 5),
)


@dataclass
class Settings:
    size: int = 112
    speed: int = 100
    roam: bool = True
    on_top: bool = True
    bubbles: bool = True
    sound: bool = False
    startup: bool = False
    fullscreen: bool = True
