from types import SimpleNamespace

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from main import ASSETS, Controller
from src.battle import Battle, Tower
from src.economy import DRAW_COST, STARTERS, Economy
from src.flock import Flock
from src.roster import DEFAULT_ID, load_catalog
from src.storage import Store
from src.summon_window import SummonWindow


class FixedRandom:
    def __init__(self, choice, roll=0):
        self.selected = choice
        self.roll = roll

    def choice(self, options):
        assert self.selected in options
        return self.selected

    def randrange(self, n):
        assert n == 100
        return self.roll


def test_starter_win_gold_draw_duplicate_and_reload(tmp_path):
    tower = Tower(ASSETS / "battle_roster.json", tmp_path / "tower.json")
    starter = "pokemon:charmander"
    path = tmp_path / "economy.json"
    random = FixedRandom(starter)
    economy = Economy(path, tower.profiles, random=random)
    assert economy.owned == {starter: 0}
    assert economy.gold == 0
    with pytest.raises(ValueError):
        economy.draw()
    with pytest.raises(ValueError):
        economy.win(2)
    assert [economy.win(floor) for floor in (1, 2, 3)] == [42, 44, 46]
    assert economy.gold == 132

    first = economy.draw()
    assert (first.key, first.duplicate, first.refund, first.upgrades) == (starter, True, 60, 1)
    assert economy.gold == 72
    for _ in range(3):
        assert economy.win(1) == 16
    assert economy.gold == DRAW_COST
    random.selected = "pokemon:charizardmegax"
    random.roll = 99
    second = economy.draw()
    assert not second.duplicate and second.refund == 0
    assert economy.gold == 0

    restored = Economy(path, tower.profiles, random=FixedRandom("digimon:agumon"))
    assert restored.starter == starter
    assert restored.cleared == 3
    assert restored.owned == {starter: 1, second.key: 0}
    tower.economy = restored
    controller = SimpleNamespace(pet=SimpleNamespace(name="파이리", level=1), skill_name="불꽃세례")
    bonus = tower.player(starter, controller)
    base = tower.profiles[starter].stats(1)
    assert bonus.upgrades == 1
    assert (bonus.stats.hp, bonus.stats.attack, bonus.stats.defense) == (
        base.hp + 2, base.attack + 1, base.defense + 1)


def test_all_starters_can_win_floor_one(tmp_path):
    tower = Tower(ASSETS / "battle_roster.json", tmp_path / "tower.json")
    catalog = load_catalog(ASSETS)
    for key in STARTERS:
        entry = catalog[key]
        controller = SimpleNamespace(pet=SimpleNamespace(name=entry.name, level=1),
                                     skill_name=entry.skill)
        battle = Battle(tower.player(key, controller), tower.opponent(1, catalog))
        while not battle.outcome:
            battle.act("skill" if not battle.cooldown else "attack")
        assert battle.outcome == "win", key


def test_migration_locks_other_pets_and_summon_ui(tmp_path):
    app = QApplication.instance() or QApplication([])
    store = Store(tmp_path)
    saved, settings = store.load()
    saved.xp = 63
    store.save(saved, settings)
    (tmp_path / "roster.json").write_text('["pokemon:pikachu"]')
    (tmp_path / "tower.json").write_text('{"cleared": 3}')
    flock = Flock(app, ASSETS, store, Controller)
    try:
        starter = flock.economy.starter
        assert starter in STARTERS
        assert list(flock.controllers) == [starter]
        assert flock.tower.cleared == 3
        assert store.load()[0].xp == 63
        flock.request_selection([starter, DEFAULT_ID])
        assert list(flock.controllers) == [starter]
        window = SummonWindow(flock)
        window.stage.animation.setDuration(85)
        assert not window.buy.isEnabled()
        for _ in range(8):
            flock.tower.record_win(1)
        window.refresh()
        assert window.buy.isEnabled()
        flock.economy.random = FixedRandom(DEFAULT_ID)
        # Pikachu is a first evolution and therefore uses the 22% pool.
        flock.economy.random.roll = 70
        window.buy.click()
        assert DEFAULT_ID in flock.economy.owned
        assert window.stage.kind == "pokemon"
        assert not window.stage.image.isNull()
        assert not window.buy.isEnabled()
        QTest.qWait(150)
        assert "새 친구" in window.result.text()
        flock.request_selection([starter, DEFAULT_ID])
        assert flock.controllers[DEFAULT_ID].pet.xp == 63
    finally:
        for controller in flock.controllers.values():
            controller.dispose()
        flock.tray.hide()
        app.aboutToQuit.disconnect(flock.shutdown)

def test_digimon_summon_shows_device_and_duplicate_after_animation(tmp_path):
    app = QApplication.instance() or QApplication([])
    root = Store(tmp_path)
    key = "digimon:agumon"
    (tmp_path / "economy.json").write_text(
        '{"starter":"digimon:agumon","gold":240,"cleared":0,"owned":{"digimon:agumon":0}}')
    flock = Flock(app, ASSETS, root, Controller)
    try:
        flock.economy.random = FixedRandom(key)
        window = SummonWindow(flock)
        window.stage.animation.setDuration(105)
        window.buy.click()
        assert window.stage.kind == "digimon" and not window.stage.image.isNull()
        assert "강화" not in window.result.text()
        window.pull()
        assert flock.economy.gold == 180
        QTest.qWait(180)
        assert "강화 +1" in window.result.text()
        assert "60골드 환급" in window.result.text()
        assert flock.economy.owned[key] == 1
        assert window.buy.isEnabled()
    finally:
        flock.wild.stop()
        for controller in flock.controllers.values():
            controller.dispose()
        flock.tray.hide()
        app.aboutToQuit.disconnect(flock.shutdown)
