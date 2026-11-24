import json

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from main import ASSETS, Controller
from src.flock import Flock
from src.storage import Store


def test_agumon_animation_frames_and_pixel_aligned_ground(tmp_path):
    app = QApplication.instance() or QApplication([])
    root = Store(tmp_path)
    key = "digimon:agumon"
    (tmp_path / "economy.json").write_text(json.dumps({
        "starter": key, "gold": 19, "cleared": 0, "owned": {key: 0}}))
    flock = Flock(app, ASSETS, root, Controller)
    try:
        controller = flock.controllers[key]
        desktop = controller.desktop
        controller.settings.roam = False
        controller.settings.fullscreen = False
        QTest.qWait(80)
        assert desktop.animation.state == "idle"
        animation = desktop.animation
        image = desktop.movie.currentImage()
        source_palette = {image.pixel(x, y) for x in range(image.width())
                          for y in range(image.height())}
        shot = desktop.grab().toImage()
        assert shot.pixelColor(0, 0).alpha() == 0
        assert {shot.pixelColor(x, y).rgba() for x in range(shot.width())
                for y in range(shot.height()) if shot.pixelColor(x, y).alpha()} <= source_palette
        for dpr in (1.0, 1.1, 1.5, 2.0):
            target = animation.bounds(image, 112, 112, dpr, 0.18, 0.04)
            assert abs(target.width() / target.height() - 1) < 1e-9
            assert abs(target.bottom() - 112) <= 0.51 / dpr

        controller.interact("feed", "🍎", "")
        QTest.qWait(170)
        assert animation.state == "feed"
        controller.toggle_sleep()
        QTest.qWait(120)
        assert animation.state == "sleep"
        assert desktop.movie.currentFrameNumber() in (22, 23)
        controller.toggle_sleep()
        desktop.use_skill()
        QTest.qWait(460)
        assert animation.state == "thunder"
        assert desktop.movie.currentFrameNumber() in (6, 7)
        desktop.care_action = ""
        controller.settings.roam = True
        desktop.movement.reset(desktop.base.x())
        desktop.movement.target = desktop.base.x() + 100
        QTest.qWait(160)
        assert animation.state == "walk"
        assert not desktop.movement.left
        desktop.movement.target = desktop.base.x() - 100
        QTest.qWait(160)
        assert desktop.movement.left
        assert flock.economy.gold == 19
        assert controller.store.load()[0].fullness == 100
    finally:
        flock.wild.stop()
        for controller in flock.controllers.values():
            controller.dispose()
        flock.tray.hide()
        app.aboutToQuit.disconnect(flock.shutdown)
