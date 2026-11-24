import json
from types import SimpleNamespace

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMenu

from main import ASSETS, Controller
from src.battle import Battle, FLOOR_COUNT, Tower
from src.flock import Flock
from src.model import Pet
from src.roster import DEFAULT_ID, load_catalog
from src.storage import Store


def test_all_tower_floors_unlock_and_reward_training(tmp_path):
    tower = Tower(ASSETS / "battle_roster.json", tmp_path / "tower.json")
    catalog = load_catalog(ASSETS)
    assert len(tower.profiles) == len(catalog)
    assert len(tower.floors) == FLOOR_COUNT
    assert len(set(tower.floors)) == FLOOR_COUNT
    assert {key.split(":")[0] for key in tower.floors} == {"pokemon", "digimon"}
    assert [tower.opponent(floor, catalog).stage for floor in range(1, 101)] == [
        stage for stage in range(4) for _ in range(25)]
    assert all((ASSETS / "tower" / f"{floor}.png").is_file() for floor in range(1, 101))
    profile = tower.profiles[DEFAULT_ID]
    higher = profile.stats(10)
    lower = profile.stats(1)
    assert higher.hp > lower.hp and higher.attack > lower.attack and higher.defense > lower.defense
    assert tower.profiles["pokemon:charizard"].stage > tower.profiles["pokemon:charmander"].stage
    assert tower.profiles["digimon:wargreymon"].stage > tower.profiles["digimon:agumon"].stage

    pet = Pet()
    player = SimpleNamespace(pet=pet, skill_name="번개")
    for floor in range(1, 101):
        assert tower.unlocked == floor
        opponent = tower.opponent(floor, catalog)
        for attempt in range(15):
            battle = Battle(tower.player(DEFAULT_ID, player), opponent)
            while not battle.outcome:
                battle.act("skill" if not battle.cooldown else "attack")
            if battle.outcome == "win":
                pet.change(xp=tower.record_win(floor))
                assert battle.act("attack") == []
                break
            assert tower.cleared == floor - 1
            pet.change(xp=tower.record_win(max(1, floor - 1)))
        else:
            raise AssertionError(f"{floor}층에서 성장 후에도 승리하지 못함")
    assert Tower(ASSETS / "battle_roster.json", tower.save_path).cleared == 100


def test_desktop_tower_unlocks_next_floor_and_saves_xp(tmp_path):
    app = QApplication.instance() or QApplication([])
    root = Store(tmp_path)
    pet, settings = root.load()
    pet.xp = 35
    root.save(pet, settings)
    (tmp_path / "economy.json").write_text(json.dumps({
        "starter": "digimon:agumon", "gold": 0, "cleared": 0,
        "owned": {DEFAULT_ID: 0, "digimon:agumon": 0}}))
    (tmp_path / "roster.json").write_text(json.dumps([DEFAULT_ID]))
    flock = Flock(app, ASSETS, root, Controller)
    try:
        flock.request_selection([DEFAULT_ID, "digimon:agumon"])
        field = flock.tower_field
        field.timer.setInterval(55)
        desktop = flock.controllers[DEFAULT_ID].desktop
        menu = QMenu()
        field.add_actions(menu, DEFAULT_ID)
        assert menu.actions()[0].text() == "1층 도전"
        menu.actions()[0].trigger()
        assert desktop.field_fighting
        assert field.overlay.isVisible()
        assert not field.overlay.art.isNull()
        assert field.overlay.windowFlags() & Qt.WindowType.WindowTransparentForInput
        assert desktop.work_area(desktop.geometry().center()).contains(field.overlay.geometry())
        assert not field.overlay.pet_rect.intersects(field.overlay.enemy_rect)
        field.battle.hp = 1
        field.battle.cooldown = 2
        QTest.qWait(140)
        assert field.battle.outcome == "lose"
        assert not field.active
        assert not desktop.field_fighting
        assert flock.tower.cleared == 0
        assert flock.economy.gold == 0
        field.start(1, DEFAULT_ID)
        QTest.qWait(180)
        assert field.battle.outcome == "win"
        assert "승리" in field.overlay.message
        assert not field.active
        assert flock.tower.cleared == 1
        assert flock.economy.gold == 42
        assert root.load()[0].level == 2
        assert flock.controllers["digimon:agumon"].pet.xp == 0
        menu.clear()
        field.add_actions(menu, DEFAULT_ID)
        assert [action.text() for action in menu.actions()] == [
            "2층 도전", "자동 사냥 시작 · 2층", "클리어한 층"]
        menu.actions()[0].trigger()
        assert field.floor == 2
        assert field.active
        field.cancel()
        assert not field.active
        assert not field.overlay.isVisible()
        assert flock.economy.gold == 42

        field.timer.setInterval(2500)
        field.chain_timer.setInterval(45)
        menu.actions()[1].trigger()
        assert field.continuous and field.floor == 2
        field.battle.enemy_hp = 1
        field.advance()
        assert field.active and field.chain_timer.isActive()
        assert flock.economy.gold == 86
        menu.clear()
        field.add_actions(menu, DEFAULT_ID)
        assert menu.actions()[0].text() == "자동 사냥 중단"
        QTest.qWait(140)
        assert field.floor == 3 and field.timer.isActive()
        field.battle.hp = 1
        field.battle.cooldown = 1
        field.battle.enemy_hp = field.battle.opponent.stats.hp
        field.advance()
        assert not field.active and not field.continuous
        assert "자동 사냥 종료" in field.overlay.message
        assert flock.tower.cleared == 2 and flock.economy.gold == 86

        flock.economy.commit({**flock.economy.data, "cleared": 99})
        flock.tower.cleared = 99
        field.start(100, DEFAULT_ID, continuous=True)
        field.battle.enemy_hp = 1
        field.advance()
        assert flock.tower.cleared == 100
        QTest.qWait(140)
        assert field.floor == 100 and field.active
        field.cancel()
        assert not field.active and not field.chain_timer.isActive()
    finally:
        flock.tower_field.cancel()
        for controller in flock.controllers.values():
            controller.dispose()
        flock.tray.hide()
        app.aboutToQuit.disconnect(flock.shutdown)
