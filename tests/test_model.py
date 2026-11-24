from src.model import Pet, Settings
from src.movement import Movement
from src.storage import Store


def test_care_and_leveling():
    pet = Pet(xp=98)
    assert not pet.interact("feed")
    assert (pet.fullness, pet.happiness, pet.energy) == (100, 85, 100)
    assert pet.last_meal
    assert pet.interact("play")
    assert (pet.fullness, pet.happiness, pet.energy) == (95, 100, 90)
    assert (pet.level, pet.xp, pet.target) == (2, 8, 125)
    pet.interact("pet")
    pet.interact("click")
    assert (pet.interactions, pet.clicks, pet.xp) == (4, 1, 10)


def test_active_and_sleep_timers():
    pet = Pet(energy=80)
    assert not pet.advance(599)
    pet.advance(1)
    assert (pet.fullness, pet.happiness, pet.energy) == (78, 80, 79)
    pet.state = "수면"
    pet.advance(300)
    assert (pet.fullness, pet.happiness, pet.energy) == (78, 79, 100)
    pet.state = "대기"
    pet.advance(60000)
    assert (pet.fullness, pet.happiness, pet.energy) == (0, 13, 0)


def test_restore_and_corrupt_primary(tmp_path):
    store = Store(tmp_path)
    pet, settings = Pet(), Settings(size=140, roam=False)
    pet.last_seen = "2000-01-01T00:00:00+00:00"
    pet.advance(90)
    store.save(pet, settings)
    assert store.load() == (pet, settings)
    pet.interact("click")
    store.save(pet, settings)
    assert store.load()[0].clicks == 1
    store.path.write_text("broken", encoding="utf-8")
    restored, preferences = store.load()
    assert restored.clicks == 0
    assert restored.fullness == 80
    assert restored.elapsed == {"fullness": 90, "happiness": 90, "active": 90}
    assert restored.created == pet.created
    assert preferences == settings
    store.save(restored, preferences)
    assert store.load() == (restored, preferences)


def test_movement_bounds_and_flip():
    move = Movement()
    move.target = 500
    x, state = move.step(10, 0, 100, 80, 0.05)
    assert (x, state, move.left) == (14, "이동", False)
    move.target = -60
    x, state = move.step(x, 0, 100, 80, 0.05)
    assert (x, state, move.left) == (10, "이동", True)
    assert move.step(x, 0, 100, 80, 1)[0] == 0
