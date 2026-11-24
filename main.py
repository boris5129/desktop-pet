import json
import logging
import os
from pathlib import Path
import sys
import time

from PySide6.QtCore import QLockFile, QStandardPaths, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QDialog, QMenu, QMessageBox, QSystemTrayIcon

from src.desktop import DesktopPet
from src.dialogs import SettingsWindow, StatusWindow
from src.flock import Flock
from src.storage import Store
from src.windows import sync_startup


ASSETS = Path(__file__).resolve().parent / "assets"


class Controller:
    def __init__(self, app, store, entry=None, sprite=None, flock=None, slot=0):
        self.app = app
        self.store = store
        self.flock = flock
        self.slot = slot
        self.character_key = entry.key if entry else "pokemon:pikachu"
        self.animation_profile = flock.animations.get(self.character_key) if flock else None
        self.pet, self.settings = store.load()
        if flock:
            self.settings.size = flock.size
        character = json.loads((ASSETS / "character.json").read_text(encoding="utf-8-sig"))
        if not store.path.exists() and not store.backup.exists():
            self.pet.name = entry.name if entry else character["name"]
        self.sprite = sprite or ASSETS / character["sprite"]
        self.skill_name = entry.skill if entry else "번개"
        self.skill_effect = entry.effect if entry else "electric"
        self.status = None
        self.previous = time.monotonic()
        self.tray = flock.tray if flock else self.create_tray()
        self.desktop = DesktopPet(self, self.sprite, character["faces_left"])
        self.desktop.pause_sprite(self.pet.state == "수면")
        if not flock:
            self.init_tray()
            app.aboutToQuit.connect(self.shutdown)
        if not self.tray.isVisible():
            self.settings.fullscreen = False
        self.stats_timer = QTimer(app, interval=1000)
        self.stats_timer.timeout.connect(self.advance)
        self.stats_timer.start()
        self.save_timer = QTimer(app, interval=30000)
        self.save_timer.timeout.connect(self.save)
        self.save_timer.start()
        self.save()

    def create_tray(self):
        icon = QIcon(str(ASSETS / "icons" / "pikachu.ico"))
        self.app.setWindowIcon(icon)
        return QSystemTrayIcon(icon, self.app)

    def init_tray(self):
        self.tray.setToolTip(self.pet.name)
        self.tray_menu = QMenu()
        self.toggle_action = self.tray_menu.addAction("", self.desktop.toggle_visible)
        self.tray_menu.addAction("상태 확인", self.show_status)
        self.tray_menu.addAction("설정", self.show_settings)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction("종료", self.app.quit)
        self.tray.setContextMenu(self.tray_menu)
        self.tray_menu.aboutToShow.connect(self.refresh_tray)
        self.tray.activated.connect(self.tray_activated)
        self.refresh_tray()
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

    def refresh_tray(self):
        if self.flock:
            self.flock.refresh_tray()
            return
        self.toggle_action.setText("피카츄 숨기기" if self.desktop.isVisible() else "피카츄 표시")

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.desktop.toggle_visible()

    def save(self):
        try:
            self.store.save(self.pet, self.settings)
        except OSError:
            logging.exception("저장 실패")
        if self.status is not None and self.status.isVisible():
            self.status.refresh(self.pet)

    def advance(self):
        current = time.monotonic()
        elapsed = current - self.previous
        self.previous = current
        if self.pet.advance(elapsed):
            self.save()

    def set_state(self, state):
        if self.pet.state != state:
            self.advance()
            self.pet.state = state
            self.save()

    def interact(self, action, icon, message, jump=False):
        self.advance()
        leveled = self.pet.interact(action)
        reward = 0
        if self.flock:
            try:
                reward = self.flock.economy.record_care(action)
            except OSError:
                logging.exception("일일 퀘스트 저장 실패")
        if leveled:
            icon, message, jump = "★", f"레벨 {self.pet.level} 달성!", True
        elif reward:
            icon, message = "★", f"일일 퀘스트 +{reward}골드"
        if self.settings.sound and sys.platform == "win32":
            import winsound
            try:
                winsound.PlaySound(str(ASSETS / "sounds" / "chime.wav"),
                                   winsound.SND_FILENAME | winsound.SND_ASYNC)
            except RuntimeError:
                logging.exception("효과음을 재생할 수 없습니다.")
        self.desktop.reaction(action, icon, message, jump)
        self.save()

    def toggle_sleep(self):
        asleep = self.pet.state != "수면"
        self.set_state("수면" if asleep else "대기")
        self.desktop.movement.reset()
        self.desktop.effect_until = 0
        self.desktop.care_action = ""
        self.desktop.jump_start = -1.0
        self.desktop.pause_sprite(asleep or not self.desktop.isVisible())

    def show_status(self):
        if self.status is None:
            self.status = StatusWindow(self.sprite)
            self.status.setWindowTitle(f"{self.pet.name} 상태")
        self.status.refresh(self.pet)
        self.status.show()
        self.status.raise_()
        self.status.activateWindow()

    def resize_pet(self, size):
        if self.flock:
            self.flock.resize_all(size)
            return
        self.settings.size = size
        self.desktop.apply_size(size)
        self.save()

    def show_settings(self):
        if self.flock:
            self.settings.startup = self.flock.startup
        dialog = SettingsWindow(self.settings)
        dialog.setWindowTitle(f"{self.pet.name} 설정")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        settings = dialog.values()
        if self.flock and not self.flock.resize_all(settings.size):
            settings.size = self.flock.size
        if not self.tray.isVisible():
            settings.fullscreen = False
        if settings.startup != self.settings.startup:
            try:
                sync_startup(settings.startup)
                if self.flock:
                    self.flock.set_startup(settings.startup)
            except OSError:
                settings.startup = self.settings.startup
                QMessageBox.warning(dialog, "자동 실행", "Windows 자동 실행 설정을 변경할 수 없습니다.")
        self.settings = settings
        self.desktop.apply_settings()
        if not settings.roam and self.pet.state != "수면":
            self.set_state("대기")
        self.save()

    def shutdown(self):
        self.advance()
        self.save()
        if not self.flock:
            self.tray.hide()

    def dispose(self):
        self.shutdown()
        for timer in (self.stats_timer, self.save_timer, self.desktop.timer,
                      self.desktop.visibility_timer):
            timer.stop()
            timer.deleteLater()
        self.desktop.pause_sprite(True)
        for widget in (self.desktop, self.desktop.effect, self.desktop.lightning, self.status):
            if widget is not None:
                widget.hide()
                widget.deleteLater()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PikachuDesktopPet")
    app.setQuitOnLastWindowClosed(False)
    root = os.environ.get("LOCALAPPDATA")
    directory = (Path(root) / app.applicationName() if root else
                 Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)))
    try:
        store = Store(directory)
        lock = QLockFile(str(directory / "instance.lock"))
        if not lock.tryLock(0):
            return 0
        logging.basicConfig(filename=directory / "app.log", encoding="utf-8", level=logging.WARNING)
        flock = Flock(app, ASSETS, store, Controller)
        return app.exec()
    except (OSError, ValueError, KeyError) as error:
        QMessageBox.critical(None, "피카츄 시작 실패", str(error))
        return 1


if __name__ == "__main__":
    sys.exit(main())


