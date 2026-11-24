import math
import random
import time

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QMovie, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from src.movement import Movement
from src.poses import ACTION_DURATION, REST_POSE, THUNDER_CHARGE, action_pose, sleep_pose
from src.sprite_animation import SpriteAnimation
from src.windows import fullscreen_on_pet_monitor


SKILL_COLORS = {
    "normal": "#fff4cc", "fire": "#ff7438", "water": "#44c9ff", "grass": "#78d652",
    "ice": "#9af0ff", "fighting": "#f98c66", "poison": "#c276e8", "ground": "#d9a569",
    "flying": "#b5b8ff", "psychic": "#ff79c4", "bug": "#afd74a", "rock": "#d1be86",
    "ghost": "#b195ea", "dragon": "#a082ff", "dark": "#aa82a8", "steel": "#acd4e5",
    "fairy": "#ffb4e5",
}


class Overlay(QWidget):
    def __init__(self):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowDoesNotAcceptFocus
                         | Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)


class LightningStrike(Overlay):
    DROP_TIME = 0.19

    def __init__(self):
        super().__init__()
        self.age = 0.0
        self.left = True
        self.landing_x = 0
        self.color = None

    def show_at(self, target, work, height, left, age):
        width = min(96, work.width())
        x = max(work.left(), min(target.x() - width // 2, work.right() + 1 - width))
        top = max(work.top(), target.y() - height + 1)
        self.setGeometry(x, top, width, target.y() - top + 1)
        self.landing_x = target.x() - x
        self.left = left
        self.age = age
        self.color = None
        self.show()
        self.update()

    def show_projectile(self, origin, work, left, age, effect):
        width = min(208, work.width())
        x = max(work.left(), min(origin.x() - (width if left else 0),
                                 work.right() + 1 - width))
        y = max(work.top(), min(origin.y() - 38, work.bottom() - 75))
        self.setGeometry(x, y, width, min(76, work.height()))
        self.landing_x = origin.x() - x
        self.left = left
        self.age = age
        self.color = QColor(SKILL_COLORS.get(effect, SKILL_COLORS["normal"]))
        self.show()
        self.update()

    def paintEvent(self, event):
        if self.color is not None:
            self.paint_projectile()
            return
        ground = self.height() - 5
        direction = -1 if self.left else 1
        offsets = (-17, 9, -14, 13, -7, 0)
        points = [QPointF(self.landing_x + direction * offset, 3 + (ground - 3) * i / 5)
                  for i, offset in enumerate(offsets)]
        progress = min(1.0, self.age / self.DROP_TIME)
        with QPainter(self) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            fade = max(0.0, 1 - (self.age - self.DROP_TIME) / 0.44)
            painter.setOpacity(min(1.0, fade))
            for color, width in (("#bc6c24", 8), ("#ffce47", 5), ("#fffbd5", 2)):
                painter.setPen(QPen(QColor(color), width))
                for i, (start, end) in enumerate(zip(points, points[1:])):
                    fraction = max(0.0, min(1.0, progress * 5 - i))
                    if fraction:
                        painter.drawLine(start, start + (end - start) * fraction)
            if progress == 1:
                painter.setPen(QPen(QColor("#ffdf64"), 2))
                for offset in (-30, -19, 19, 30):
                    painter.drawLine(QPointF(self.landing_x, ground),
                                     QPointF(self.landing_x + offset, ground - abs(offset) / 4))

    def paint_projectile(self):
        direction = -1 if self.left else 1
        travel = min(1.0, self.age / 0.38)
        reach = self.landing_x if self.left else self.width() - self.landing_x
        distance = min(158, max(0, reach - 14))
        x = self.landing_x + direction * (7 + distance * travel)
        y = self.height() / 2 - 9 * math.sin(travel * math.pi)
        with QPainter(self) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setOpacity(max(0, min(1, 1 - (self.age - 0.38) / 0.25)))
            painter.setPen(QPen(self.color, 3))
            for offset in (8, 16, 24):
                painter.drawLine(QPointF(x - direction * offset, y),
                                 QPointF(x - direction * (offset + 8), y + (offset - 16) / 3))
            painter.setBrush(self.color)
            painter.drawEllipse(QPointF(x, y), 12, 8)
            painter.setPen(QPen(QColor("#fff9ea"), 2))
            painter.drawEllipse(QPointF(x + 2 * direction, y - 1), 5, 4)


class Effect(Overlay):
    def __init__(self):
        super().__init__()
        self.resize(180, 58)
        self.icon = self.message = ""
        self.lightning_age = None

    def paintEvent(self, event):
        with QPainter(self) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            if self.message:
                painter.setPen(QColor("#d6a557"))
                painter.setBrush(QColor("#fff9e4"))
                painter.drawRoundedRect(QRect(1, 1, 178, 29), 10, 10)
                painter.setPen(QColor("#4d3424"))
                painter.drawText(QRect(3, 1, 174, 29), Qt.AlignmentFlag.AlignCenter, self.message)
            if self.lightning_age is None:
                painter.setPen(QColor("#d94a61"))
                painter.setFont(QFont("Malgun Gothic", 15, QFont.Weight.Bold))
                painter.drawText(QRect(0, 30, 180, 28), Qt.AlignmentFlag.AlignCenter, self.icon)
            elif self.lightning_age < THUNDER_CHARGE:
                painter.setPen(QPen(QColor("#ffc238"), 3))
                for direction in (-1, 1):
                    for index in range(3):
                        x = 90 + direction * (16 + index * 11)
                        y = 45 + round(5 * math.sin(self.lightning_age * 16 + index))
                        painter.drawPoint(x, y)


class DesktopPet(QWidget):
    def __init__(self, controller, sprite, faces_left):
        super().__init__()
        self.controller = controller
        self.setWindowTitle(f"{controller.pet.name} 데스크톱 펫")
        self.faces_left = faces_left
        self.movement = Movement()
        self.effect = Effect()
        self.lightning = LightningStrike()
        self.manually_hidden = False
        self.menu_open = False
        self.field_fighting = False
        self.press = None
        self.dragged = False
        self.last_click = -1.0
        self.effect_until = 0
        self.jump_start = -1.0
        self.walk_phase = 0.0
        self.walk_strength = 0.0
        self.care_action = ""
        self.care_started = 0.0
        self.sleep_blend = float(controller.pet.state == "수면")
        self.care_pose = sleep_pose(time.monotonic(), self.sleep_blend)
        self.previous_frame = time.monotonic()
        self.movie = QMovie(str(sprite)) if sprite.suffix.lower() == ".gif" else None
        self.animation = None
        self.static_frame = QPixmap(str(sprite)) if self.movie is None else QPixmap()
        if self.movie is not None:
            if not self.movie.isValid():
                raise ValueError(f"{controller.pet.name} GIF를 읽을 수 없습니다.")
            self.movie.frameChanged.connect(lambda _: self.update())
            if controller.animation_profile:
                self.animation = SpriteAnimation(self.movie, controller.animation_profile)
            else:
                self.movie.start()
        elif self.static_frame.isNull():
            raise ValueError(f"{controller.pet.name} 이미지를 읽을 수 없습니다.")
        self.apply_settings()
        work = QApplication.primaryScreen().availableGeometry()
        lane = (controller.slot + 1) // 2 * (-1 if controller.slot % 2 else 1)
        offset = lane * (self.width() + 25)
        start = work.left() + (work.width() - self.width()) // 2
        if lane:
            start = work.left() + (start - work.left() + offset) % max(1, work.width() - self.width())
        self.base = QPoint(start,
                           work.bottom() - self.height() + 1)
        self.reposition()
        self.show()
        self.timer = QTimer(self, interval=33)
        self.timer.timeout.connect(self.tick)
        self.timer.start()
        self.visibility_timer = QTimer(self, interval=400)
        self.visibility_timer.timeout.connect(self.refresh_visibility)
        self.visibility_timer.start()

    def apply_settings(self):
        flags = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                 | Qt.WindowType.WindowDoesNotAcceptFocus)
        if self.controller.settings.on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.effect.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,
                                  self.controller.settings.on_top)
        self.lightning.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,
                                     self.controller.settings.on_top)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.apply_size(self.controller.settings.size)
        if hasattr(self, "base"):
            self.refresh_visibility()

    def apply_size(self, size):
        old_width, old_height = self.width(), self.height()
        self.setFixedSize(size, size)
        if hasattr(self, "base"):
            self.base += QPoint((old_width - size) // 2, old_height - size)
            self.reposition()
            self.movement.reset(self.base.x())

    def work_area(self, point):
        screen = QApplication.screenAt(point) or QApplication.primaryScreen()
        return screen.availableGeometry()

    def reposition(self, point=None, anchor=None):
        if point is not None:
            self.base = point
        work = self.work_area(anchor if anchor is not None else self.base + self.rect().center())
        high_x = max(work.left(), work.right() + 1 - self.width())
        high_y = max(work.top(), work.bottom() + 1 - self.height())
        self.base.setX(max(work.left(), min(high_x, self.base.x())))
        self.base.setY(max(work.top(), min(high_y, self.base.y())))
        age = time.monotonic() - self.jump_start
        lift = round(21 * math.sin(math.pi * age / 0.42)) if 0 <= age < 0.42 else 0
        walk_lift = round(self.height() * 0.055 * self.walk_strength * self.walk_rise)
        care_lift = round(self.height() * self.care_pose[0])
        self.move(self.base.x(), max(work.top(), self.base.y() - max(lift, walk_lift, care_lift)))
        if self.effect.isVisible():
            x = max(work.left(), min(work.right() + 1 - self.effect.width(),
                                     self.x() + (self.width() - self.effect.width()) // 2))
            y = self.y() - self.effect.height()
            if y < work.top():
                y = min(self.y() + self.height(), work.bottom() + 1 - self.effect.height())
            self.effect.move(x, max(work.top(), y))

    def refresh_visibility(self):
        hide = self.manually_hidden or (
            self.controller.settings.fullscreen and not self.menu_open and self.press is None
            and fullscreen_on_pet_monitor(int(self.winId()))
        )
        if self.isVisible() == hide:
            self.setVisible(not hide)
            self.pause_sprite(hide or self.controller.pet.state == "수면")
            if hide:
                self.effect.hide()
                self.lightning.hide()
            else:
                self.reposition()

    def toggle_visible(self):
        self.manually_hidden = self.isVisible()
        self.refresh_visibility()
        self.controller.refresh_tray()

    def pause_sprite(self, paused):
        if self.movie is not None and self.animation is None:
            self.movie.setPaused(paused)

    def paintEvent(self, event):
        frame = self.movie.currentPixmap() if self.movie is not None else self.static_frame
        if frame.isNull():
            return
        size = frame.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        _, care_squash, lean = self.care_pose
        squash = max(care_squash, 0.055 * self.walk_strength * (1 - self.walk_rise) ** 3)
        height = max(1, round(size.height() * (1 - squash)))
        inset = round(size.width() * abs(lean))
        width = max(1, size.width() - 2 * inset)
        offset = -round(size.width() * lean) if self.faces_left else round(size.width() * lean)
        x = (self.width() - width) // 2 + offset
        y = self.height() - height
        target = QRectF(x, y, width, height)
        if self.animation is not None:
            direction = -1 if self.faces_left else 1
            target = self.animation.bounds(frame, self.width(), self.height(), self.devicePixelRatioF(),
                                           care_squash, direction * lean)
        with QPainter(self) as painter:
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
            if self.faces_left != self.movement.left:
                painter.translate(self.width(), 0)
                painter.scale(-1, 1)
            painter.drawPixmap(target, frame, QRectF(frame.rect()))

    @property
    def walk_rise(self):
        return (1 - math.cos(self.walk_phase)) / 2

    def animate_walk(self, walking, speed, dt):
        was_moving = self.walk_strength > 0
        if walking:
            self.walk_strength = min(1.0, self.walk_strength + dt / 0.12)
        else:
            self.walk_strength = max(0.0, self.walk_strength - dt / 0.16)
        if self.walk_strength:
            steps_per_second = max(2.8, min(5.5, speed / 27))
            self.walk_phase = (self.walk_phase + math.tau * steps_per_second * dt) % math.tau
        else:
            self.walk_phase = 0.0
        if walking or was_moving:
            self.update()

    def tick(self):
        now = time.monotonic()
        dt = min(0.1, now - self.previous_frame)
        self.previous_frame = now
        if not self.isVisible() or self.press is not None:
            return
        pet = self.controller.pet
        settings = self.controller.settings
        asleep = pet.state == "수면"
        if self.care_action == "solo_play" and not settings.roam:
            self.care_action = ""
            self.effect_until = 0
        elapsed = now - self.care_started
        performing = elapsed < ACTION_DURATION.get(self.care_action, 0)
        if pet.state == "혼자 놀기" and not performing:
            self.care_action = ""
            self.controller.set_state("대기")
        sleep_delta = dt / 0.3 if asleep else -dt / 0.25
        self.sleep_blend = max(0.0, min(1.0, self.sleep_blend + sleep_delta))
        pose = (sleep_pose(now, self.sleep_blend) if self.sleep_blend
                else action_pose(self.care_action, elapsed))
        if pose != self.care_pose:
            self.care_pose = pose
            self.update()
        walking = False
        if (not self.menu_open and settings.roam
                and not (asleep or performing or self.sleep_blend or self.field_fighting)):
            work = self.work_area(self.base + self.rect().center())
            x, state = self.movement.step(self.base.x(), work.left(),
                                          max(work.left(), work.right() + 1 - self.width()),
                                          settings.speed, dt)
            self.base.setX(x)
            walking = state == "이동"
            if state == "혼자 놀기":
                self.reaction("solo_play", "♪")
            if state is not None:
                self.controller.set_state(state)
        self.animate_walk(walking, settings.speed, dt)
        if self.animation is not None:
            clip = "sleep" if asleep else self.care_action if performing else "walk" if walking else "idle"
            self.animation.update(clip, now)
        active = now < self.effect_until
        lightning_age = elapsed if performing and self.care_action == "thunder" else None
        if lightning_age != self.effect.lightning_age:
            self.effect.lightning_age = lightning_age
            self.effect.update()
        if asleep and not active and (self.effect.icon != "Zzz" or self.effect.message):
            self.effect.icon, self.effect.message = "Zzz", ""
            self.effect.update()
        self.effect.setVisible(active or asleep)
        self.reposition()
        if lightning_age is not None and lightning_age >= THUNDER_CHARGE:
            work = self.work_area(self.base + self.rect().center())
            left = self.movement.left
            age = lightning_age - THUNDER_CHARGE
            if self.controller.skill_effect == "electric":
                gap = self.width() // 3
                x = self.base.x() - gap if left else self.base.x() + self.width() + gap
                target = QPoint(max(work.left(), min(work.right(), x)),
                                self.base.y() + self.height() - 1)
                self.lightning.show_at(target, work, max(180, self.height() * 2), left, age)
            else:
                origin = QPoint(self.x() if left else self.x() + self.width() - 1,
                                self.y() + self.height() * 2 // 3)
                self.lightning.show_projectile(origin, work, left, age, self.controller.skill_effect)
        else:
            self.lightning.hide()

    def reaction(self, action, icon, message="", jump=False):
        self.effect.icon = icon
        self.effect.message = message if self.controller.settings.bubbles else ""
        now = time.monotonic()
        self.effect_until = now + 1.8
        if self.controller.pet.state != "수면":
            if action in ACTION_DURATION:
                self.care_action = action
                self.care_started = now
                self.jump_start = -1.0
                if action != "solo_play":
                    self.movement.reset(self.base.x())
                    self.controller.set_state("대기")
            elif jump:
                self.jump_start = now
        self.effect.update()

    def use_skill(self):
        if self.controller.pet.state == "수면":
            return
        if (self.care_action == "thunder"
                and time.monotonic() - self.care_started < ACTION_DURATION["thunder"]):
            return
        self.reaction("thunder", "", f"{self.controller.skill_name}!")
        self.effect_until = self.care_started + ACTION_DURATION["thunder"]

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.press = event.globalPosition().toPoint()
            self.drag_offset = self.press - self.pos()
            self.dragged = False
            event.accept()

    def mouseMoveEvent(self, event):
        if self.press is not None:
            point = event.globalPosition().toPoint()
            if self.dragged or (point - self.press).manhattanLength() >= QApplication.startDragDistance():
                self.dragged = True
                self.jump_start = -1
                self.care_action = ""
                self.lightning.hide()
                if not self.sleep_blend:
                    self.care_pose = REST_POSE
                self.walk_phase = self.walk_strength = 0.0
                self.update()
                self.reposition(point - self.drag_offset, anchor=point)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.press is not None:
            self.press = None
            now = time.monotonic()
            if self.dragged:
                self.movement.reset(self.base.x())
                if self.controller.pet.state != "수면":
                    self.controller.set_state("대기")
            elif now - self.last_click >= 0.4:
                self.last_click = now
                self.controller.interact("click", "♥", random.choice(
                    ("피카피카!", "기분이 좋아!", "같이 놀자!", "반가워!")), jump=True)
            event.accept()

    def closeEvent(self, event):
        event.accept()
        QApplication.quit()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addAction("밥 주기", lambda: self.controller.interact("feed", "🍎", "잘 먹겠습니다!"))
        menu.addAction("같이 놀기", lambda: self.controller.interact("play", "♥", "신난다!", jump=True))
        menu.addAction("쓰다듬기", lambda: self.controller.interact("pet", "♥", "피카피카!"))
        menu.addAction("기술 사용", self.use_skill).setEnabled(self.controller.pet.state != "수면")
        menu.addAction("깨우기" if self.controller.pet.state == "수면" else "재우기",
                       self.controller.toggle_sleep)
        menu.addSeparator()
        menu.addAction("상태 확인", self.controller.show_status)
        if self.controller.flock:
            menu.addAction("친구 선택…", self.controller.flock.show_picker)
            menu.addAction("친구 뽑기…", self.controller.flock.show_summon)
            menu.addAction("일일 퀘스트…", self.controller.flock.show_daily_quests)
            tower = menu.addMenu("배틀타워")
            self.controller.flock.tower_field.add_actions(tower, self.controller.character_key)
        size_menu = menu.addMenu("크기 조절")
        for size in (64, 88, 112, 152, 200, 240):
            action = size_menu.addAction(f"{size} px")
            action.setCheckable(True)
            action.setChecked(size == self.controller.settings.size)
            action.triggered.connect(lambda checked=False, size=size: self.controller.resize_pet(size))
        size_menu.addSeparator()
        size_menu.addAction("직접 조절…", self.controller.show_settings)
        menu.addAction("설정", self.controller.show_settings)
        menu.addAction("잠시 숨기기", self.toggle_visible).setEnabled(self.controller.tray.isVisible())
        menu.addAction("종료", QApplication.quit)
        self.menu_open = True
        try:
            menu.exec(event.globalPos())
        finally:
            self.menu_open = False
            menu.deleteLater()


