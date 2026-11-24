import json
from dataclasses import dataclass
from datetime import date
from random import SystemRandom

from src.storage import Store


STARTERS = ("pokemon:charmander", "pokemon:squirtle", "pokemon:bulbasaur",
            "digimon:agumon", "digimon:gabumon")
DRAW_COST = 120
DUPLICATE_REFUND = DRAW_COST // 2
STAGE_ODDS = (70, 22, 7, 1)
DAILY_QUESTS = {
    "feed": ("밥 주기", 3, 35),
    "play": ("같이 놀기", 2, 35),
    "pet": ("쓰다듬기", 3, 20),
}


@dataclass(frozen=True)
class Draw:
    key: str
    duplicate: bool
    upgrades: int
    refund: int


class Economy:
    def __init__(self, path, profiles, legacy_floor=0, random=None):
        self.path = path
        self.backup = path.with_name("economy.backup.json")
        self.profiles = profiles
        self.random = random or SystemRandom()
        self.pools = tuple(tuple(key for key, profile in profiles.items()
                                 if min(3, profile.stage) == tier)
                           for tier in range(len(STAGE_ODDS)))
        for candidate in (self.path, self.backup):
            try:
                data = json.loads(candidate.read_bytes())
                self.validate(data)
                self.data = data
                return
            except (OSError, ValueError, KeyError, TypeError):
                continue
        if self.path.exists() or self.backup.exists():
            raise ValueError("친구 보유 목록이나 골드 저장 파일을 읽을 수 없습니다.")
        starter = self.random.choice(STARTERS)
        self.data = {"starter": starter, "gold": 0, "cleared": legacy_floor,
                     "owned": {starter: 0}}
        self.commit(self.data)

    def validate(self, data):
        if not isinstance(data, dict):
            raise ValueError("invalid economy")
        if data["starter"] not in STARTERS:
            raise ValueError("invalid starter")
        for key in ("gold", "cleared"):
            if type(data[key]) is not int or data[key] < 0:
                raise ValueError("invalid balance")
        if data["cleared"] > 100:
            raise ValueError("invalid floor")
        owned = data["owned"]
        if not isinstance(owned, dict) or data["starter"] not in owned:
            raise ValueError("invalid collection")
        if any(key not in self.profiles or type(count) is not int or count < 0
               for key, count in owned.items()):
            raise ValueError("invalid upgrade count")
        if "daily" in data:
            daily = data["daily"]
            date.fromisoformat(daily["date"])
            counts = daily["counts"]
            if not isinstance(counts, dict) or any(
                action not in DAILY_QUESTS or type(count) is not int
                or not 0 <= count <= DAILY_QUESTS[action][1]
                for action, count in counts.items()
            ):
                raise ValueError("invalid daily quest progress")
        caught = data.get("caught", [])
        if not isinstance(caught, list) or any(not isinstance(key, str) or key not in owned
                                               for key in caught):
            raise ValueError("invalid captured collection")

    def commit(self, data):
        Store.replace(self.backup, json.dumps(self.data))
        Store.replace(self.path, json.dumps(data))
        self.data = data

    @property
    def starter(self):
        return self.data["starter"]

    @property
    def gold(self):
        return self.data["gold"]

    @property
    def cleared(self):
        return self.data["cleared"]

    @property
    def owned(self):
        return self.data["owned"]

    def win(self, floor):
        if not 1 <= floor <= min(100, self.cleared + 1):
            raise ValueError("아직 도전할 수 없는 층입니다.")
        first_win = floor > self.cleared
        gold = 40 + floor * 2 if first_win else 16 + floor // 2
        self.commit({**self.data, "gold": self.gold + gold,
                     "cleared": max(self.cleared, floor)})
        return gold

    def daily_counts(self, today=None):
        today = today or date.today()
        saved = self.data.get("daily")
        if saved is not None and date.fromisoformat(saved["date"]) >= today:
            return saved["counts"].copy()
        return {}

    def record_care(self, action, today=None):
        if action not in DAILY_QUESTS:
            return 0
        today = today or date.today()
        saved = self.data.get("daily")
        if saved is not None and date.fromisoformat(saved["date"]) > today:
            return 0
        counts = self.daily_counts(today)
        _, target, gold = DAILY_QUESTS[action]
        count = counts.get(action, 0)
        if count >= target:
            return 0
        counts[action] = count + 1
        reward = gold if counts[action] == target else 0
        self.commit({**self.data, "gold": self.gold + reward,
                     "daily": {"date": today.isoformat(), "counts": counts}})
        return reward

    def capture(self, key):
        if key not in self.profiles or key in self.owned:
            return False
        self.commit({**self.data, "owned": {**self.owned, key: 0},
                     "caught": [*self.data.get("caught", ()), key]})
        return True

    def draw(self):
        if self.gold < DRAW_COST:
            raise ValueError("골드가 부족합니다.")
        roll = self.random.randrange(100)
        for tier, chance in enumerate(STAGE_ODDS):
            if roll < chance:
                break
            roll -= chance
        key = self.random.choice(self.pools[tier])
        owned = self.owned.copy()
        duplicate = key in owned
        owned[key] = owned[key] + 1 if duplicate else 0
        refund = DUPLICATE_REFUND if duplicate else 0
        self.commit({**self.data, "owned": owned, "gold": self.gold - DRAW_COST + refund})
        return Draw(key, duplicate, owned[key], refund)
