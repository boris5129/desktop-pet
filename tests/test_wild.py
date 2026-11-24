import time

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from main import ASSETS, Controller
from src.battle import Battle, Fighter, Stats
from src.flock import Flock
from src.storage import Store
from src.wild_encounter import MAX_WAIT, MIN_WAIT


class OutcomeRandom:
    def __init__(self, roll):
        self.roll = roll

    def randint(self, low, high):
        return low

    def randrange(self, upper):
        assert 0 <= self.roll < upper
        return self.roll

    def choice(self, candidates):
        return candidates[0]


def test_capture_mode_spares_wild_at_or_below_forty_percent():
    player = Fighter("친구", "기술", 1, 0, Stats(50, 360, 4))
    wild = Fighter("야생", "기술", 1, 0, Stats(50, 999, 1))
    battle = Battle(player, wild, capture_mode=True)
    battle.act("skill")
    assert battle.outcome == "capture"
    assert 0 < battle.enemy_hp <= wild.stats.hp * 0.4
    assert battle.hp == player.stats.hp
    assert battle.act("attack") == []


def test_encounter_spawn_click_failure_capture_and_offline_activation(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    store = Store(tmp_path)
    flock = Flock(app, ASSETS, store, Controller)
    try:
        assert MIN_WAIT <= flock.wild.timer.interval() <= MAX_WAIT
        assert {key.split(":")[0] for key in flock.wild.portraits} == {"pokemon", "digimon"}
        starter = flock.economy.starter
        controller = flock.controllers[starter]
        controller.pet.level = 5
        controller.settings.fullscreen = False
        key = flock.tower.floors[0]
        monkeypatch.setattr(flock.wild, "choose_key", lambda: key)
        flock.economy.random = OutcomeRandom(99)

        def reach_threshold():
            flock.wild.timer.stop()
            flock.wild.spawn()
            encounter = flock.wild.window
            assert encounter.isVisible() and not encounter.can_capture()
            assert not isinstance(encounter, QDialog)
            assert encounter.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            assert encounter.status.windowFlags() & Qt.WindowType.WindowTransparentForInput
            initial_x = encounter.x()
            encounter.roam_started -= 0.8
            encounter.reposition()
            assert encounter.x() != initial_x
            assert encounter.work.contains(encounter.geometry())
            QTest.mouseClick(encounter, Qt.MouseButton.LeftButton, pos=encounter.rect().center())
            assert key not in flock.economy.owned
            for _ in range(20):
                if encounter.can_capture():
                    return encounter
                encounter.tick()
            raise AssertionError("포획 기회가 열리지 않았습니다.")

        encounter = reach_threshold()
        assert encounter.battle.enemy_hp * 5 <= encounter.battle.opponent.stats.hp * 2
        QTest.mouseClick(encounter, Qt.MouseButton.LeftButton, pos=encounter.rect().center())
        assert "실패" in encounter.status.message
        assert key not in flock.economy.owned
        encounter.close()

        encounter = reach_threshold()
        encounter.deadline = time.monotonic() - 1
        encounter.tick()
        QTest.mouseClick(encounter, Qt.MouseButton.LeftButton, pos=encounter.rect().center())
        assert "달아났어요" in encounter.status.message
        assert key not in flock.economy.owned
        encounter.close()

        flock.economy.random = OutcomeRandom(0)
        encounter = reach_threshold()
        QTest.mouseClick(encounter, Qt.MouseButton.LeftButton, pos=encounter.rect().center())
        assert "포획 성공" in encounter.status.message
        assert flock.economy.owned[key] == 0
        encounter.try_capture()
        assert flock.economy.gold == 0
        encounter.close()
        assert not controller.desktop.field_fighting
        assert flock.wild.timer.isActive()
        flock.request_selection([starter, key])
        assert flock.controllers[key].sprite.suffix == ".png"
        assert not flock.controllers[key].desktop.static_frame.isNull()
        progress = type(flock.economy)(flock.economy.path, flock.tower.profiles)
        assert key in progress.owned and key in progress.data["caught"]
    finally:
        flock.wild.stop()
        for controller in flock.controllers.values():
            controller.dispose()
        flock.tray.hide()
        app.aboutToQuit.disconnect(flock.shutdown)
