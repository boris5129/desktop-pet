from datetime import date

from PySide6.QtWidgets import QApplication

from main import ASSETS, Controller
from src.battle import Tower
from src.daily_quest_window import DailyQuestWindow
from src.economy import DAILY_QUESTS, Economy
from src.flock import Flock
from src.storage import Store


def test_daily_rewards_reset_at_midnight_and_persist(tmp_path):
    tower = Tower(ASSETS / "battle_roster.json", tmp_path / "tower.json")
    path = tmp_path / "economy.json"
    economy = Economy(path, tower.profiles)
    first = date(2026, 11, 24)
    next_day = date(2026, 11, 25)
    assert economy.record_care("click", first) == 0
    assert economy.record_care("solo_play", first) == 0
    assert economy.daily_counts(first) == {}
    total = 0
    for action, (_, target, reward) in DAILY_QUESTS.items():
        assert [economy.record_care(action, first) for _ in range(target + 1)] == (
            [0] * (target - 1) + [reward, 0])
        total += reward
    assert economy.gold == total == 90
    
    restored = Economy(path, tower.profiles)
    assert restored.gold == total
    assert restored.daily_counts(first) == {"feed": 3, "play": 2, "pet": 3}
    assert restored.record_care("feed", first) == 0
    assert restored.daily_counts(next_day) == {}
    assert restored.record_care("feed", next_day) == 0
    assert restored.record_care("feed", first) == 0
    assert restored.daily_counts(next_day) == {"feed": 1}
    assert restored.gold == total
    assert [restored.record_care("feed", next_day) for _ in range(2)] == [0, 35]
    assert restored.gold == 125


def test_care_counts_across_partners_and_in_quest_window(tmp_path):
    app = QApplication.instance() or QApplication([])
    flock = Flock(app, ASSETS, Store(tmp_path), Controller)
    try:
        starter = flock.economy.starter
        other = "pokemon:charmander" if starter != "pokemon:charmander" else "digimon:agumon"
        flock.economy.commit({**flock.economy.data, "owned": {starter: 0, other: 0}})
        flock.request_selection([starter, other])
        assert any(action.text() == "일일 퀘스트…" for action in flock.menu.actions())
        window = DailyQuestWindow(flock.economy)
        for key in (starter, other, starter, other):
            flock.controllers[key].interact("feed", "🍎", "밥")
        flock.controllers[other].interact("click", "♥", "")
        window.refresh()
        label, bar = window.rows["feed"]
        assert "지급 완료" in label.text()
        assert bar.value() == 3
        assert flock.economy.gold == 35
        assert flock.economy.daily_counts() == {"feed": 3}
    finally:
        for controller in flock.controllers.values():
            controller.dispose()
        flock.tray.hide()
        app.aboutToQuit.disconnect(flock.shutdown)
