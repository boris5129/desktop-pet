import json
import logging

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QIcon, QImageReader
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QDialog, QMenu, QMessageBox, QProgressDialog, QSystemTrayIcon

from src.roster import DEFAULT_ID, Picker, load_catalog
from src.battle import Tower
from src.daily_quest_window import DailyQuestWindow
from src.economy import Economy
from src.storage import Store
from src.summon_window import SummonWindow
from src.tower_field import TowerField
from src.wild_encounter import WildEncounters


class Flock:
    def __init__(self, app, assets, store, controller_class):
        self.app = app
        self.assets = assets
        self.store = store
        self.controller_class = controller_class
        self.catalog = load_catalog(assets)
        self.animations = json.loads((assets / "animation_profiles.json").read_text(encoding="utf-8-sig"))
        self.tower = Tower(assets / "battle_roster.json", store.directory / "tower.json")
        self.economy = Economy(store.directory / "economy.json", self.tower.profiles,
                               self.tower.cleared)
        self.tower.economy = self.economy
        self.tower.cleared = self.economy.cleared
        self.selection_path = store.directory / "roster.json"
        self.display_path = store.directory / "display.json"
        self.startup = store.load()[1].startup
        self.controllers = {}
        self.network = QNetworkAccessManager(app)
        self.progress = self.reply = None
        icon = QIcon(str(assets / "icons" / "pikachu.ico"))
        app.setWindowIcon(icon)
        self.tray = QSystemTrayIcon(icon, app)
        self.tray.setToolTip("데스크톱 펫")
        self.menu = QMenu()
        self.menu.addAction("친구 선택…", self.show_picker)
        self.menu.addAction("친구 뽑기…", self.show_summon)
        self.menu.addAction("일일 퀘스트…", self.show_daily_quests)
        self.tower_menu = self.menu.addMenu("배틀타워")
        self.tower_menu.aboutToShow.connect(self.refresh_tower_menu)
        self.visibility = self.menu.addAction("모두 숨기기", self.toggle_all)
        self.menu.addSeparator()
        self.menu.addAction("종료", app.quit)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self.tray_activated)
        self.menu.aboutToShow.connect(self.refresh_tray)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
        self.portraits = {key: self.assets / "tower" / f"{floor}.png"
                          for floor, key in enumerate(self.tower.floors, 1)}
        self.wild = WildEncounters(self, self.portraits)
        self.tower_field = TowerField(self)
        app.aboutToQuit.connect(self.shutdown)
        keys = self.load_selection()
        self.size = self.load_size(keys[0] if keys else self.economy.starter)
        available = [key for key in keys if self.sprite_path(self.catalog[key]).is_file()]
        if not available and not self.tray.isVisible():
            available = [self.economy.starter]
        self.apply(available, persist=False)
        if available != keys and keys:
            self.request_selection(keys)

    def set_startup(self, enabled):
        primary = self.controllers.get(DEFAULT_ID)
        if primary:
            primary.settings.startup = enabled
            primary.save()
        else:
            pet, settings = self.store.load()
            settings.startup = enabled
            self.store.save(pet, settings)
        self.startup = enabled

    def pet_store(self, key):
        if key == DEFAULT_ID:
            return self.store
        category, species = key.split(":")
        return Store(self.store.directory / "pets" / category / species)

    def load_size(self, first_key):
        try:
            value = json.loads(self.display_path.read_bytes())["size"]
            if type(value) is int and 64 <= value <= 240:
                return value
        except (OSError, ValueError, KeyError, TypeError):
            pass
        return self.pet_store(first_key).load()[1].size

    def resize_all(self, size):
        if size == self.size:
            return True
        try:
            Store.replace(self.display_path, json.dumps({"size": size}))
        except OSError:
            logging.exception("공통 크기 저장 실패")
            QMessageBox.warning(None, "크기 조절", "친구들의 크기를 저장하지 못했어요.")
            return False
        self.size = size
        for controller in self.controllers.values():
            controller.settings.size = size
            controller.desktop.apply_size(size)
            controller.save()
        if self.wild.window is not None:
            self.wild.window.place_near_partner()
            self.wild.window.reposition()
        if self.tower_field.active:
            self.tower_field.repaint()
        return True

    def refresh_tower_menu(self):
        self.tower_menu.clear()
        self.tower_field.add_actions(self.tower_menu)

    def show_summon(self):
        if SummonWindow(self).exec() == QDialog.DialogCode.Accepted:
            self.show_picker()

    def show_daily_quests(self):
        DailyQuestWindow(self.economy).exec()

    def load_selection(self):
        try:
            raw = json.loads(self.selection_path.read_bytes())
            if isinstance(raw, list):
                owned = list(dict.fromkeys(key for key in raw
                                           if isinstance(key, str) and key in self.economy.owned))
                return owned or ([self.economy.starter] if raw else [])
        except (OSError, ValueError):
            pass
        return [self.economy.starter]

    def sprite_path(self, character):
        if character.key == DEFAULT_ID:
            return self.assets / "sprites" / "pikachu.gif"
        bundled = self.assets / "friends" / character.category / character.filename
        if bundled.is_file():
            return bundled
        cached = self.store.directory / "sprites" / character.category / character.filename
        if (not cached.is_file() and character.key in self.economy.data.get("caught", ())
                and character.key in self.portraits):
            return self.portraits[character.key]
        return cached

    def show_picker(self):
        if self.progress is not None:
            self.progress.raise_()
            return
        dialog = Picker(self.catalog, self.controllers, self.economy.owned)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        keys = [*filter(dialog.selected.__contains__, self.controllers),
                *sorted(dialog.selected.difference(self.controllers))]
        if not keys and not self.tray.isVisible():
            QMessageBox.information(None, "친구 선택", "트레이가 없을 때는 친구를 한 마리 이상 선택해 주세요.")
            return
        self.request_selection(keys)

    def request_selection(self, keys):
        keys = [key for key in keys if key in self.economy.owned]
        self.requested = keys
        self.pending = [self.catalog[key] for key in keys
                        if not self.sprite_path(self.catalog[key]).is_file()]
        if not self.pending:
            self.apply(keys)
            return
        self.progress = QProgressDialog("스프라이트를 받는 중…", "취소", 0, len(self.pending))
        self.progress.setWindowTitle("친구 불러오기")
        self.progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.progress.setAutoClose(False)
        self.progress.setAutoReset(False)
        self.progress.setMinimumDuration(0)
        self.progress.canceled.connect(self.cancel_download)
        self.progress.show()
        self.download_next()

    def download_next(self):
        if not self.pending:
            self.close_progress()
            self.apply(self.requested)
            return
        entry = self.pending.pop(0)
        self.progress.setLabelText(f"{entry.name} 스프라이트를 받는 중…")
        request = QNetworkRequest(QUrl(entry.url))
        request.setTransferTimeout(20000)
        self.reply = self.network.get(request)
        self.reply.finished.connect(lambda entry=entry, reply=self.reply: self.downloaded(entry, reply))

    def downloaded(self, entry, reply):
        try:
            if reply is not self.reply:
                return
            self.reply = None
            if reply.error() != QNetworkReply.NetworkError.NoError:
                raise OSError(reply.errorString())
            self.cache_sprite(entry, bytes(reply.readAll()))
            self.progress.setValue(self.progress.value() + 1)
        except OSError as error:
            self.close_progress()
            QMessageBox.warning(None, "친구 불러오기", f"{entry.name} 이미지를 받지 못했습니다.\n{error}")
            return
        finally:
            reply.deleteLater()
        if self.progress is not None:
            self.download_next()

    def cache_sprite(self, entry, data):
        if not 0 < len(data) <= 8_000_000 or not data.startswith(
                (b"GIF87a", b"GIF89a", b"\x89PNG\r\n\x1a\n")):
            raise OSError("이미지 형식을 읽을 수 없습니다.")
        destination = self.store.directory / "sprites" / entry.category / entry.filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".download")
        try:
            temporary.write_bytes(data)
            if not QImageReader(str(temporary)).canRead():
                raise OSError("손상된 이미지입니다.")
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
        return destination

    def close_progress(self):
        progress, self.progress = self.progress, None
        if progress:
            progress.hide()
            progress.deleteLater()

    def cancel_download(self):
        reply, self.reply = self.reply, None
        self.close_progress()
        if reply is not None:
            reply.abort()

    def apply(self, keys, persist=True):
        keys = [key for key in keys if key in self.economy.owned]
        newly_added = {}
        try:
            used_slots = {controller.slot for controller in self.controllers.values()}
            for key in keys:
                if key in self.controllers:
                    continue
                entry = self.catalog[key]
                pet_store = self.pet_store(key)
                slot = next(index for index in range(len(used_slots) + 1) if index not in used_slots)
                used_slots.add(slot)
                newly_added[key] = self.controller_class(self.app, pet_store, entry=entry,
                    sprite=self.sprite_path(entry), flock=self, slot=slot)
            if persist:
                Store.replace(self.selection_path, json.dumps(keys, ensure_ascii=False))
        except (OSError, ValueError) as error:
            for controller in newly_added.values():
                controller.dispose()
            logging.exception("친구 목록 적용 실패")
            QMessageBox.warning(None, "친구 선택", str(error))
            return
        for key in tuple(self.controllers):
            if key not in keys:
                controller = self.controllers.pop(key)
                self.wild.remove_partner(controller)
                self.tower_field.remove_partner(controller)
                controller.dispose()
        self.controllers.update(newly_added)
        self.refresh_tray()

    def refresh_tray(self):
        self.tower_menu.setEnabled(bool(self.controllers))
        self.visibility.setEnabled(bool(self.controllers))
        visible = any(pet.desktop.isVisible() for pet in self.controllers.values())
        self.visibility.setText("모두 숨기기" if visible else "모두 표시")

    def toggle_all(self):
        hide = any(pet.desktop.isVisible() for pet in self.controllers.values())
        for controller in self.controllers.values():
            controller.desktop.manually_hidden = hide
            controller.desktop.refresh_visibility()
        self.refresh_tray()

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self.controllers:
                self.toggle_all()
            else:
                self.show_picker()

    def shutdown(self):
        self.tower_field.cancel()
        self.wild.stop()
        self.cancel_download()
        for controller in self.controllers.values():
            controller.shutdown()
        self.tray.hide()
