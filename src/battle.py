import json
from dataclasses import dataclass

from src.storage import Store


FLOOR_COUNT = 100


@dataclass(frozen=True)
class Stats:
    hp: int
    attack: int
    defense: int


@dataclass(frozen=True)
class Profile:
    stage: int
    hp: int
    attack: int
    defense: int

    def stats(self, level, scale=100):
        hp = 44 + self.hp * 3 // 10 + level * 4 + self.stage * 10
        attack = 13 + self.attack * 17 // 100 + level * 2 + self.stage * 6
        defense = 6 + self.defense * 12 // 100 + level + self.stage * 4
        return Stats(hp * scale // 100, attack * scale // 100, defense * scale // 100)


@dataclass(frozen=True)
class Fighter:
    name: str
    skill: str
    level: int
    stage: int
    stats: Stats
    upgrades: int = 0


class Tower:
    def __init__(self, asset_file, save_path):
        data = json.loads(asset_file.read_bytes())
        self.profiles = {key: Profile(*value) for key, value in data["profiles"].items()}
        self.floors = data["floors"]
        self.save_path = save_path
        self.economy = None
        self.cleared = 0
        try:
            value = json.loads(save_path.read_bytes())["cleared"]
            if type(value) is int and 0 <= value <= FLOOR_COUNT:
                self.cleared = value
        except (OSError, ValueError, TypeError, KeyError):
            pass

    @property
    def unlocked(self):
        return min(FLOOR_COUNT, self.cleared + 1)

    def record_win(self, floor):
        if not 1 <= floor <= self.unlocked:
            raise ValueError("아직 도전할 수 없는 층입니다.")
        first_win = floor > self.cleared
        if self.economy is not None:
            self.economy.win(floor)
            self.cleared = self.economy.cleared
        elif first_win:
            Store.replace(self.save_path, json.dumps({"cleared": floor}))
            self.cleared = floor
        if first_win:
            return 76 + 15 * floor
        return 24 + 5 * floor

    def player(self, key, controller):
        level = controller.pet.level
        profile = self.profiles[key]
        upgrades = self.economy.owned.get(key, 0) if self.economy is not None else 0
        base = profile.stats(level)
        stats = Stats(base.hp + upgrades * 2, base.attack + upgrades, base.defense + upgrades)
        return Fighter(controller.pet.name, controller.skill_name, level, profile.stage,
                       stats, upgrades)

    def opponent(self, floor, catalog):
        key = self.floors[floor - 1]
        entry = catalog[key]
        profile = self.profiles[key]
        level = 1 + 3 * (floor - 1) // 4
        scale = 66 + 42 * floor // FLOOR_COUNT
        return Fighter(entry.name, entry.skill, level, profile.stage, profile.stats(level, scale))


class Battle:
    def __init__(self, player, opponent, capture_mode=False):
        self.player = player
        self.opponent = opponent
        self.hp = player.stats.hp
        self.enemy_hp = opponent.stats.hp
        self.turn = 1
        self.cooldown = 0
        self.outcome = ""
        self.capture_mode = capture_mode

    @property
    def enemy_using_skill(self):
        return self.turn % 3 == 0

    @staticmethod
    def damage(attacker, defender, skill, guard=False):
        power = attacker.stats.attack * (138 if skill else 100) // 100
        amount = max(1, power - defender.stats.defense * 55 // 100)
        return max(1, amount // 2) if guard else amount

    def auto_act(self):
        return self.act("skill" if not self.cooldown else "attack")

    def act(self, action):
        if self.outcome or action not in ("attack", "skill", "guard"):
            return []
        if action == "skill" and self.cooldown:
            return []
        if action == "guard":
            notes = [f"{self.player.name} 방어 자세"]
        else:
            skill = action == "skill"
            damage = self.damage(self.player, self.opponent, skill)
            damage = min(damage, self.enemy_hp - int(self.capture_mode))
            self.enemy_hp -= damage
            name = self.player.skill if skill else "기본 공격"
            notes = [f"{self.player.name} · {name} · 피해 {damage}"]
            if self.capture_mode and self.enemy_hp * 5 <= self.opponent.stats.hp * 2:
                self.outcome = "capture"
                return notes
            if self.enemy_hp == 0:
                self.outcome = "win"
                return notes
        defending = action == "guard"
        enemy_skill = self.enemy_using_skill
        damage = self.damage(self.opponent, self.player, enemy_skill, defending)
        self.hp = max(0, self.hp - damage)
        name = self.opponent.skill if enemy_skill else "기본 공격"
        notes.append(f"{self.opponent.name} · {name} · 피해 {damage}")
        self.cooldown = 2 if action == "skill" else max(0, self.cooldown - 1)
        self.turn += 1
        if self.hp == 0:
            self.outcome = "lose"
        return notes
