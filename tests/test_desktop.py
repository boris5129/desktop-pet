import ctypes
from ctypes import wintypes
import sys

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from main import Controller
from src.dialogs import SettingsWindow
from src.model import Settings
from src.storage import Store
from src import windows


def test_desktop_interactions(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    store = Store(tmp_path)
    controller = Controller(app, store)
    desktop = controller.desktop
    controller.settings.roam = False
    controller.settings.fullscreen = False
    QTest.qWait(180)
    assert desktop.movie.frameCount() == 33
    assert desktop.movie.currentFrameNumber() > 0
    assert desktop.movie.currentImage().pixelColor(0, 0).alpha() == 0
    assert desktop.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert desktop.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus
    assert desktop.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert desktop.work_area(desktop.geometry().center()).contains(desktop.geometry())

    center = desktop.rect().center()
    QTest.mouseClick(desktop, Qt.MouseButton.LeftButton, pos=center)
    QTest.mouseClick(desktop, Qt.MouseButton.LeftButton, pos=center)
    assert controller.pet.clicks == 1
    assert desktop.effect.icon == "♥"
    before = desktop.x()
    QTest.mousePress(desktop, Qt.MouseButton.LeftButton, pos=center)
    QTest.mouseMove(desktop, center + QPoint(45, -30))
    QTest.mouseRelease(desktop, Qt.MouseButton.LeftButton, pos=center)
    assert desktop.x() > before
    assert controller.pet.clicks == 1

    opened = []

    def choose_feed():
        menu = app.activePopupWidget()
        if not isinstance(menu, QMenu):
            desktop.findChild(QMenu).close()
            return
        opened.append(desktop.menu_open)
        menu.actions()[0].trigger()
        menu.close()

    QTimer.singleShot(100, choose_feed)
    QApplication.sendEvent(desktop, QContextMenuEvent(
        QContextMenuEvent.Reason.Mouse, center, desktop.mapToGlobal(center)))
    assert opened == [True]
    assert controller.pet.fullness == 100
    assert desktop.care_action == "feed"
    bite_poses = []
    for _ in range(9):
        QTest.qWait(35)
        bite_poses.append(desktop.care_pose)
    assert any(pose[1] > 0.05 and pose[2] > 0 for pose in bite_poses)
    controller.interact("play", "♥", "신난다!", jump=True)
    assert (controller.pet.fullness, controller.pet.energy) == (95, 90)
    hop_heights = set()
    for _ in range(9):
        QTest.qWait(35)
        hop_heights.add(desktop.base.y() - desktop.y())
    assert max(hop_heights) >= 15
    controller.toggle_sleep()
    assert controller.pet.state == "수면"
    assert store.load()[0].state == "수면"
    QTest.qWait(430)
    assert desktop.sleep_blend == 1
    assert desktop.care_pose[1] >= 0.25
    assert desktop.effect.icon == "Zzz"
    controller.toggle_sleep()
    assert controller.pet.state == "대기"
    QTest.qWait(320)
    assert desktop.sleep_blend == 0
    assert desktop.care_pose == (0, 0, 0)

    def choose_skill():
        menu = desktop.findChild(QMenu)
        next(action for action in menu.actions() if action.text() == "기술 사용").trigger()
        menu.close()

    QTimer.singleShot(100, choose_skill)
    QApplication.sendEvent(desktop, QContextMenuEvent(
        QContextMenuEvent.Reason.Mouse, center, desktop.mapToGlobal(center)))
    started = desktop.care_started
    assert desktop.care_action == "thunder"
    desktop.use_skill()
    assert desktop.care_started == started
    QTest.qWait(200)
    assert 0 < desktop.effect.lightning_age < 0.42
    assert not desktop.lightning.isVisible()
    QTest.qWait(520)
    assert desktop.effect.lightning_age >= 0.42
    assert desktop.lightning.isVisible()
    assert desktop.lightning.height() > desktop.height()
    assert desktop.lightning.x() + desktop.lightning.landing_x < desktop.base.x()
    assert desktop.lightning.geometry().bottom() == desktop.base.y() + desktop.height() - 1
    effect_image = desktop.lightning.grab().toImage()
    scale = effect_image.devicePixelRatio()
    landing = desktop.lightning.landing_x
    assert any(effect_image.pixelColor(round(x * scale), round(y * scale)).alpha() > 0
               for x in range(landing - 3, landing + 4)
               for y in range(desktop.lightning.height() - 9, desktop.lightning.height() - 2))
    QTest.qWait(420)
    assert desktop.effect.lightning_age is None
    assert not desktop.effect.isVisible()
    assert not desktop.lightning.isVisible()
    desktop.movement.left = False
    desktop.use_skill()
    QTest.qWait(530)
    assert desktop.lightning.x() + desktop.lightning.landing_x >= desktop.base.x() + desktop.width()
    desktop.care_action = ""
    desktop.tick()
    controller.show_status()
    assert controller.status.isVisible()
    assert controller.status.bars["energy"].value() == 90
    assert controller.status.grab().save(str(tmp_path / "status-render.png"))
    controller.status.close()
    assert desktop.isVisible()

    desktop.toggle_visible()
    assert not desktop.isVisible()
    desktop.toggle_visible()
    assert desktop.isVisible()
    def save_settings():
        dialog = app.activeModalWidget()
        assert isinstance(dialog, SettingsWindow)
        dialog.controls["size"].setValue(144)
        dialog.controls["speed"].setValue(120)
        dialog.controls["fullscreen"].setChecked(False)
        dialog.accept()

    QTimer.singleShot(100, save_settings)
    controller.show_settings()
    assert desktop.width() == 144
    assert store.load()[1] == controller.settings
    feet = desktop.base.y() + desktop.height()
    selected_sizes = []

    def choose_size():
        menu = desktop.findChild(QMenu)
        try:
            submenu = menu.findChild(QMenu)
            selected_sizes.extend(action.text() for action in submenu.actions())
            next(action for action in submenu.actions() if action.text() == "88 px").trigger()
        finally:
            menu.close()

    QTimer.singleShot(100, choose_size)
    QApplication.sendEvent(desktop, QContextMenuEvent(
        QContextMenuEvent.Reason.Mouse, center, desktop.mapToGlobal(center)))
    assert "88 px" in selected_sizes
    assert desktop.width() == 88
    assert desktop.base.y() + desktop.height() == feet
    assert store.load()[1].size == 88
    desktop.jump_start = -1.0
    controller.settings.roam = True
    start_x = desktop.x()
    desktop.movement.target = start_x + 100
    heights = set()
    for _ in range(10):
        QTest.qWait(25)
        heights.add(desktop.base.y() - desktop.y())
    assert start_x < desktop.x() < start_x + 100
    assert not desktop.movement.left
    assert max(heights) >= 3
    assert desktop.work_area(desktop.geometry().center()).contains(desktop.geometry())
    controller.settings.roam = False
    QTest.qWait(250)
    assert desktop.y() == desktop.base.y()
    assert desktop.walk_strength == 0

    controller.settings.roam = True
    desktop.movement.reset(desktop.base.x())
    desktop.movement.until = 0
    interactions = controller.pet.interactions
    with monkeypatch.context() as chance:
        chance.setattr("src.movement.random.choice", lambda options: "혼자 놀기")
        desktop.tick()
    assert controller.pet.state == "혼자 놀기"
    assert desktop.effect.icon == "♪"
    QTest.qWait(275)
    assert desktop.y() < desktop.base.y()
    assert controller.pet.interactions == interactions
    QTest.qWait(1050)
    assert controller.pet.state == "대기"
    assert desktop.y() == desktop.base.y()

    desktop.effect.hide()
    desktop.hide()
    controller.shutdown()
    desktop.timer.stop()
    desktop.visibility_timer.stop()
    controller.stats_timer.stop()
    controller.save_timer.stop()


def test_windows_layered_hit_test(tmp_path, monkeypatch):
    if sys.platform != "win32":
        return
    app = QApplication.instance() or QApplication([])
    backing = QWidget(None, Qt.WindowType.WindowStaysOnTopHint)
    backing.show()
    store = Store(tmp_path)
    store.save(store.load()[0], Settings(roam=False, fullscreen=False))
    controller = Controller(app, store)
    desktop = controller.desktop
    backing.setGeometry(desktop.geometry().adjusted(-10, -10, 10, 10))
    backing.activateWindow()
    QTest.qWait(120)
    user32 = ctypes.WinDLL("user32")
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.WindowFromPoint.argtypes = (wintypes.POINT,)
    user32.WindowFromPoint.restype = wintypes.HWND
    user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
    hwnd = int(desktop.winId())
    background = int(backing.winId())
    foreground = user32.GetForegroundWindow()
    desktop.toggle_visible()
    desktop.toggle_visible()
    QTest.qWait(120)
    assert user32.GetForegroundWindow() == foreground
    assert foreground != hwnd
    bounds = wintypes.RECT()
    assert user32.GetWindowRect(hwnd, ctypes.byref(bounds))
    transparent_hit = user32.WindowFromPoint(wintypes.POINT(bounds.left + 1, bounds.top + 1))
    assert transparent_hit == background, (transparent_hit, background, hwnd, foreground)
    pixmap = desktop.grab()
    image = pixmap.toImage()
    point = next((x, y) for y in range(image.height() // 3, image.height() * 2 // 3)
                 for x in range(image.width() // 3, image.width() * 2 // 3)
                 if image.pixelColor(x, y).alpha() == 255)
    assert user32.WindowFromPoint(wintypes.POINT(bounds.left + point[0], bounds.top + point[1])) == hwnd
    assert pixmap.save(str(tmp_path / "sprite-render.png"))
    backing.showFullScreen()
    backing.activateWindow()
    QTest.qWait(200)
    if user32.GetForegroundWindow() != background:
        monkeypatch.setattr(windows.user32, "GetForegroundWindow", lambda: background)
    assert windows.fullscreen_on_pet_monitor(hwnd)
    controller.settings.fullscreen = True
    desktop.refresh_visibility()
    assert not desktop.isVisible()
    backing.showNormal()
    QTest.qWait(200)
    desktop.refresh_visibility()
    assert desktop.isVisible()
    desktop.hide()
    backing.close()
    controller.shutdown()





def test_running_instance_blocks_source_launch(tmp_path):
    import os
    from pathlib import Path
    import subprocess

    from PySide6.QtCore import QLockFile

    directory = tmp_path / "PikachuDesktopPet"
    directory.mkdir()
    lock = QLockFile(str(directory / "instance.lock"))
    assert lock.tryLock(0)
    try:
        script = Path(__file__).resolve().parents[1] / "main.py"
        environment = {**os.environ, "LOCALAPPDATA": str(tmp_path)}
        result = subprocess.run([sys.executable, str(script)], env=environment,
                                capture_output=True, timeout=20)
        assert result.returncode == 0, result.stderr
        assert not (directory / "pet.json").exists()
    finally:
        lock.unlock()
