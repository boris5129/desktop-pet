import logging
import math
import time

from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QMovie, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

from src.battle import Battle, Fighter
from src.desktop import Overlay
from src.economy import STAGE_ODDS


MIN_WAIT = 60_000
MAX_WAIT = 600_000
CAPTURE_SECONDS = 15
CAPTURE_ODDS = (75, 60, 45, 30)


class WildStatus(Overlay):
    def __init__(self, enemy):
        super().__init__()
        self.resize(238, 48)
        self.enemy = enemy
        self.hp = enemy.stats.hp
        self.message = "자동 전투 · HP 40% 이하에서 포획"

    def paintEvent(self, event):
        with QPainter(self) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(23, 37, 54, 230))
            painter.drawRoundedRect(self.rect(), 7, 7)
            painter.setFont(QFont("Malgun Gothic", 9))
            painter.setPen(QColor("#f9f8f0"))
            name = f"야생 {self.enemy.name}  Lv.{self.enemy.level}  HP {self.hp}/{self.enemy.stats.hp}"
            self.draw_text(painter, QRect(5, 2, self.width() - 10, 17), name)
            width = self.width() - 16
            painter.fillRect(8, 20, width, 4, QColor("#4f6178"))
            painter.fillRect(8, 20, width * self.hp // self.enemy.stats.hp, 4, QColor("#f17865"))
            painter.setPen(QColor("#ffdf96"))
            self.draw_text(painter, QRect(5, 25, self.width() - 10, 19), self.message)

    @staticmethod
    def draw_text(painter, rect, text):
        text = painter.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, rect.width())
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)


class Encounter(QWidget):
    finished = Signal()

    def __init__(self, manager, controller, key):
        flags = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                 | Qt.WindowType.WindowDoesNotAcceptFocus)
        if controller.settings.on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("야생 친구")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.manager = manager
        self.controller = controller
        self.key = key
        self.deadline = None
        self.finished_round = False
        self.roam_started = time.monotonic()
        self.left = True
        self.chance = CAPTURE_ODDS[min(3, manager.flock.tower.profiles[key].stage)]
        flock = manager.flock
        tower = flock.tower
        player = tower.player(controller.character_key, controller)
        entry = flock.catalog[key]
        profile = tower.profiles[key]
        level = max(1, player.level + flock.economy.random.randint(-2, 1))
        enemy = Fighter(entry.name, entry.skill, level, profile.stage, profile.stats(level, 84))
        self.battle = Battle(player, enemy, capture_mode=True)
        self.status = WildStatus(enemy)
        self.status.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, controller.settings.on_top)

        art = flock.sprite_path(entry)
        self.movie = QMovie(str(art), parent=self) if art.suffix.lower() == ".gif" and art.is_file() else None
        self.art = QPixmap(str(manager.portraits[key]))
        if self.movie is not None and self.movie.isValid():
            self.movie.frameChanged.connect(lambda _: self.update())
            self.movie.start()
        else:
            self.movie = None

        self.place_near_partner()
        self.motion_timer = QTimer(self, interval=34)
        self.motion_timer.timeout.connect(self.reposition)
        self.motion_timer.start()
        self.timer = QTimer(self, interval=720)
        self.timer.timeout.connect(self.tick)
        self.timer.start()
        self.close_timer = QTimer(self, interval=3600, singleShot=True)
        self.close_timer.timeout.connect(self.close)
        self.reposition()

    def place_near_partner(self):
        desktop = self.controller.desktop
        self.work = desktop.work_area(desktop.geometry().center())
        size = min(desktop.width(), self.work.width(), self.work.height())
        self.setFixedSize(size, size)
        right = self.work.right() + 1 - (desktop.x() + desktop.width())
        left = desktop.x() - self.work.left()
        direction = -1 if right < size + 65 and left > right else 1
        self.left = direction > 0
        self.anchor_x = (desktop.x() + desktop.width() + 53 if direction > 0
                         else desktop.x() - size - 53)
        self.ground = min(self.work.bottom() + 1, desktop.base.y() + desktop.height())
        desktop.field_fighting = True
        desktop.movement.left = direction < 0
        desktop.update()

    def reposition(self):
        if not self.controller.desktop.isVisible():
            self.close()
            return
        age = time.monotonic() - self.roam_started
        wave = age * math.tau / 4.8
        if not self.finished_round:
            self.left = math.cos(wave) < 0
        range_px = min(29, max(0, self.width() // 3))
        x = self.anchor_x + round(range_px * math.sin(wave))
        lift = round(4 * math.sin(age * 12) ** 2)
        right = self.work.right() + 1
        x = max(self.work.left(), min(right - self.width(), x))
        self.move(x, max(self.work.top(), self.ground - self.height() - lift))
        status_x = min(right - self.status.width(), self.geometry().center().x() - self.status.width() // 2)
        self.status.move(max(self.work.left(), status_x),
                         max(self.work.top(), self.y() - self.status.height() - 5))
        self.update()

    def paintEvent(self, event):
        frame = self.movie.currentPixmap() if self.movie is not None else self.art
        if frame.isNull():
            frame = self.art
        fitted = frame.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        with QPainter(self) as painter:
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
            if not self.left:
                painter.translate(self.width(), 0)
                painter.scale(-1, 1)
            target = QRect(QPoint((self.width() - fitted.width()) // 2,
                                  self.height() - fitted.height()), fitted)
            painter.drawPixmap(target, frame, frame.rect())

    def can_capture(self):
        return not self.finished_round and self.deadline is not None and time.monotonic() < self.deadline

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.try_capture()
            event.accept()

    def set_message(self, message):
        self.status.message = message
        self.status.update()

    def tick(self):
        if not self.controller.desktop.isVisible() or self.controller.pet.state == "수면":
            self.close()
            return
        if self.deadline is not None:
            seconds = math.ceil(self.deadline - time.monotonic())
            if seconds <= 0:
                self.finish_round("시간이 지나 야생 친구가 달아났어요.")
            else:
                self.set_message(f"클릭해 포획 · {self.chance}% · {seconds}초")
            return
        if not self.battle.cooldown:
            desktop = self.controller.desktop
            desktop.movement.left = self.x() < desktop.x()
            desktop.reaction("thunder", "", f"{self.controller.skill_name}!")
        self.battle.auto_act()
        self.status.hp = self.battle.enemy_hp
        self.set_message("자동 전투 · HP 40% 이하에서 포획")
        if self.battle.outcome == "lose":
            self.finish_round("파트너가 쓰러져 야생 친구가 달아났어요.")
        elif self.battle.outcome == "capture":
            self.deadline = time.monotonic() + CAPTURE_SECONDS
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.set_message(f"클릭해 포획 · {self.chance}% · {CAPTURE_SECONDS}초")
            self.timer.setInterval(250)

    def try_capture(self):
        if not self.can_capture():
            return
        economy = self.manager.flock.economy
        if economy.random.randrange(100) >= self.chance:
            self.finish_round("포획에 실패했어요. 야생 친구가 달아났어요.")
            return
        try:
            caught = economy.capture(self.key)
        except OSError:
            logging.exception("야생 친구 저장 실패")
            self.finish_round("포획 결과를 저장하지 못했어요.")
            return
        if caught:
            self.finish_round(f"{self.battle.opponent.name} 포획 성공!")
        else:
            self.finish_round("이미 보유한 친구예요.")

    def finish_round(self, message):
        self.finished_round = True
        self.timer.stop()
        self.motion_timer.stop()
        self.unsetCursor()
        self.set_message(message)
        self.close_timer.start()

    def closeEvent(self, event):
        self.timer.stop()
        self.motion_timer.stop()
        self.close_timer.stop()
        self.controller.desktop.field_fighting = False
        self.status.hide()
        self.status.deleteLater()
        self.finished.emit()
        event.accept()



class WildEncounters:
    def __init__(self, flock, portraits):
        self.flock = flock
        self.portraits = portraits
        self.window = None
        self.stopped = False
        self.timer = QTimer(flock.app, singleShot=True)
        self.timer.timeout.connect(self.spawn)
        self.schedule()

    def schedule(self):
        if not self.stopped:
            self.timer.start(self.flock.economy.random.randint(MIN_WAIT, MAX_WAIT))

    def choose_key(self):
        economy = self.flock.economy
        pools = [[], [], [], []]
        for key in self.portraits:
            if key not in economy.owned:
                pools[min(3, self.flock.tower.profiles[key].stage)].append(key)
        available = [(pool, weight) for pool, weight in zip(pools, STAGE_ODDS) if pool]
        if not available:
            return None
        roll = economy.random.randrange(sum(weight for _, weight in available))
        for pool, weight in available:
            if roll < weight:
                return economy.random.choice(pool)
            roll -= weight

    def spawn(self):
        if self.stopped or self.window is not None:
            return
        active = [controller for controller in self.flock.controllers.values()
                  if controller.desktop.isVisible() and controller.pet.state != "수면"]
        if (not active or QApplication.activeModalWidget() is not None
                or self.flock.tower_field.active):
            self.timer.start(15_000)
            return
        key = self.choose_key()
        if key is None:
            self.schedule()
            return
        controller = self.flock.economy.random.choice(active)
        window = Encounter(self, controller, key)
        self.window = window
        window.finished.connect(self.closed)
        window.show()
        window.status.show()

    def closed(self):
        window, self.window = self.window, None
        if window is not None:
            window.deleteLater()
        self.schedule()

    def remove_partner(self, controller):
        if self.window is not None and self.window.controller is controller:
            self.window.close()

    def stop(self):
        self.stopped = True
        self.timer.stop()
        if self.window is not None:
            self.window.close()

