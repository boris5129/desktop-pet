import json

from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from main import ASSETS, Controller
from src.flock import Flock
from src.roster import DEFAULT_ID, Picker
from src.storage import Store


def test_select_and_care_for_pokemon_and_digimon(tmp_path):
    app = QApplication.instance() or QApplication([])
    root = Store(tmp_path)
    pet, settings = root.load()
    pet.xp = 42
    root.save(pet, settings)
    selection = [DEFAULT_ID, "pokemon:charmander", "digimon:agumon"]
    (tmp_path / "economy.json").write_text(json.dumps({
        "starter": "pokemon:charmander", "gold": 0, "cleared": 0,
        "owned": {key: 0 for key in selection}}))
    (tmp_path / "roster.json").write_text(json.dumps([DEFAULT_ID]))
    flock = Flock(app, ASSETS, root, Controller)
    try:
        assert flock.controllers[DEFAULT_ID].pet.xp == 42
        assert len(flock.catalog) > 1500
        assert sum(entry.category == "digimon" for entry in flock.catalog.values()) == 233
        picker = Picker(flock.catalog, flock.controllers, flock.economy.owned)
        picker.search.setText("파이리")
        assert picker.list.count() >= 1
        picker.list.item(0).setCheckState(Qt.CheckState.Checked)
        picker.category.setCurrentIndex(picker.category.findData("digimon"))
        picker.search.setText("아구몬")
        assert picker.list.count() >= 1
        picker.list.item(0).setCheckState(Qt.CheckState.Checked)
        assert picker.selected == set(selection)
        picker.category.setCurrentIndex(picker.category.findData(""))
        picker.search.setText("꼬부기")
        locked = picker.list.item(0)
        assert locked.data(Qt.ItemDataRole.CheckStateRole) is None
        locked.setCheckState(Qt.CheckState.Checked)
        assert "pokemon:squirtle" not in picker.selected
        flock.request_selection(selection)
        assert list(flock.controllers) == selection
        assert flock.load_selection() == selection
        pikachu, charmander, agumon = flock.controllers.values()
        for controller in flock.controllers.values():
            controller.settings.fullscreen = False
            controller.settings.roam = False
        assert len({controller.desktop.base.x() for controller in flock.controllers.values()}) == 3
        assert all(controller.desktop.isVisible() for controller in flock.controllers.values())
        assert all(controller.tray is flock.tray for controller in flock.controllers.values())

        charmander.interact("feed", "🍎", "")
        assert charmander.pet.fullness == 100 and pikachu.pet.fullness == 80
        assert charmander.skill_name == "불꽃세례" and agumon.skill_name == "작은 불꽃"
        assert agumon.desktop.movie.isValid()
        agumon.desktop.use_skill()
        QTest.qWait(650)
        assert agumon.desktop.lightning.isVisible()
        assert agumon.desktop.lightning.color is not None

        foot_positions = [controller.desktop.base.y() + controller.desktop.height()
                          for controller in flock.controllers.values()]
        charmander.resize_pet(88)
        assert {controller.desktop.width() for controller in flock.controllers.values()} == {88}
        assert [controller.desktop.base.y() + controller.desktop.height()
                for controller in flock.controllers.values()] == foot_positions

        def change_custom_size():
            dialog = app.activeModalWidget()
            dialog.controls["size"].setValue(139)
            dialog.accept()

        QTimer.singleShot(80, change_custom_size)
        agumon.show_settings()
        assert {controller.desktop.width() for controller in flock.controllers.values()} == {139}
        assert flock.load_size(DEFAULT_ID) == 139

        flock.apply([DEFAULT_ID])
        assert list(flock.controllers) == [DEFAULT_ID]
        flock.apply(selection)
        assert {controller.desktop.width() for controller in flock.controllers.values()} == {139}
        assert flock.controllers["pokemon:charmander"].pet.fullness == 100
        assert flock.controllers[DEFAULT_ID].pet.xp == 42
    finally:
        for controller in tuple(flock.controllers.values()):
            controller.dispose()
        flock.controllers.clear()
        flock.tray.hide()
        app.aboutToQuit.disconnect(flock.shutdown)

