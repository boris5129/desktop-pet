import logging
import math
import time

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap

from src.battle import Battle, FLOOR_COUNT
from src.desktop import Overlay


class TowerOverlay(Overlay):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("바탕화면 배틀타워")
        self.battle = None
        self.message = ""
        self.hit_at = 0.0
        self.hit_partner = False

    def place(self, desktop):
        pet = QRect(desktop.base, desktop.size())
        work = desktop.work_area(pet.center())
        edge = min(pet.width(), work.width() // 3, work.height() // 2)
        gap = 32
        right = work.right() - pet.right()
        left = pet.left() - work.left()
        enemy_left = right < edge + gap and left > right
        x = pet.left() - gap - edge if enemy_left else pet.right() + gap + 1
        x = max(work.left(), min(work.right() + 1 - edge, x))
        y = max(work.top(), pet.bottom() + 1 - edge)
        enemy = QRect(x, y, edge, edge)
        bounds = pet.united(enemy).adjusted(-74, -83, 74, 12).intersected(work)
        self.setGeometry(bounds)
        offset = bounds.topLeft()
        self.pet_rect = pet.translated(-offset)
        self.enemy_rect = enemy.translated(-offset)
        return enemy.center().x() < pet.center().x()

    def paintEvent(self, event):
        if self.battle is None:
            return
        with QPainter(self) as painter:
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
            painter.setFont(QFont("Malgun Gothic", 9, QFont.Weight.Bold))
            rect = self.enemy_rect
            age = time.monotonic() - self.hit_at
            direction = 1 if rect.center().x() > self.pet_rect.center().x() else -1
            if 0 <= age < 0.23:
                offset = math.sin(math.pi * age / 0.23) * (10 if self.hit_partner else -7)
                rect = rect.translated(round(-direction * offset), 0)
                if not self.hit_partner:
                    painter.setOpacity(0.5 + 0.5 * age / 0.23)
            if self.art.isNull():
                painter.setPen(QColor("#f0cb5e"))
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "?")
            else:
                size = self.art.size().scaled(rect.size(), Qt.AspectRatioMode.KeepAspectRatio)
                target = QRect(QPoint(rect.center().x() - size.width() // 2,
                                      rect.bottom() + 1 - size.height()), size)
                painter.save()
                if direction < 0:
                    painter.translate(target.left() + target.right() + 1, 0)
                    painter.scale(-1, 1)
                painter.drawPixmap(target, self.art, self.art.rect())
                painter.restore()
            painter.setOpacity(1)
            self.health(painter, self.pet_rect, self.battle.player, self.battle.hp, "#52d19a")
            self.health(painter, self.enemy_rect, self.battle.opponent, self.battle.enemy_hp, "#f17965")
            self.caption(painter)

    def health(self, painter, rect, fighter, hp, color):
        width = min(142, max(100, rect.width()))
        x = max(2, min(self.width() - width - 2, rect.center().x() - width // 2))
        y = max(24, rect.top() - 29)
        panel = QRect(x, y, width, 26)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(18, 32, 48, 232))
        painter.drawRoundedRect(panel, 5, 5)
        painter.setPen(QColor("#f5f8ff"))
        fm = painter.fontMetrics()
        title = fm.elidedText(f"{fighter.name}  {hp}/{fighter.stats.hp}",
                              Qt.TextElideMode.ElideRight, width - 8)
        painter.drawText(panel.adjusted(4, 0, -4, -8), Qt.AlignmentFlag.AlignCenter, title)
        painter.fillRect(x + 5, y + 19, width - 10, 4, QColor("#4b5e70"))
        painter.fillRect(x + 5, y + 19, (width - 10) * hp // fighter.stats.hp, 4, QColor(color))

    def caption(self, painter):
        panel = QRect(4, 1, self.width() - 8, 22)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(18, 32, 48, 232))
        painter.drawRoundedRect(panel, 5, 5)
        painter.setPen(QColor("#fff0bf"))
        text = painter.fontMetrics().elidedText(self.message, Qt.TextElideMode.ElideRight,
                                                panel.width() - 10)
        painter.drawText(panel, Qt.AlignmentFlag.AlignCenter, text)


class TowerField:
    def __init__(self, flock):
        self.flock = flock
        self.overlay = TowerOverlay()
        self.player = None
        self.battle = None
        self.floor = 0
        self.continuous = False
        self.timer = QTimer(flock.app, interval=680)
        self.timer.timeout.connect(self.advance)
        self.paint_timer = QTimer(flock.app, interval=34)
        self.paint_timer.timeout.connect(self.repaint)
        self.result_timer = QTimer(flock.app, interval=4700, singleShot=True)
        self.result_timer.timeout.connect(self.cancel)
        self.chain_timer = QTimer(flock.app, interval=1350, singleShot=True)
        self.chain_timer.timeout.connect(self.next_round)

    @property
    def active(self):
        return self.timer.isActive() or self.chain_timer.isActive()

    def fighter(self, key):
        return next((controller for character, controller in self.flock.controllers.items()
                     if (key is None or key == character) and controller.desktop.isVisible()
                     and controller.pet.state != "수면"), None)

    def add_actions(self, menu, key=None):
        if self.active:
            label = "자동 사냥 중단" if self.continuous else f"{self.floor}층 전투 중단"
            menu.addAction(label, self.cancel)
            return
        tower = self.flock.tower
        floor = tower.unlocked
        start = menu.addAction(f"{floor}층 도전", lambda: self.start(floor, key))
        enabled = self.fighter(key) is not None and self.flock.wild.window is None
        start.setEnabled(enabled)
        hunt = menu.addAction(f"자동 사냥 시작 · {floor}층",
                              lambda: self.start(floor, key, continuous=True))
        hunt.setEnabled(enabled)
        if not enabled:
            reason = "야생 전투가 끝나면 도전할 수 있어요." if self.flock.wild.window else "깨어 있는 친구가 필요해요."
            menu.addAction(reason).setEnabled(False)
        if tower.cleared:
            replay = menu.addMenu("클리어한 층")
            replay.setEnabled(enabled)
            for lower in range(1, tower.cleared + 1, 10):
                upper = min(lower + 9, tower.cleared)
                group = replay.addMenu(f"{lower}~{upper}층")
                for previous in range(lower, upper + 1):
                    action = group.addAction(f"{previous}층 재도전")
                    action.triggered.connect(lambda checked=False, floor=previous: self.start(floor, key))

    def start(self, floor, key=None, continuous=False):
        tower = self.flock.tower
        player = self.fighter(key)
        if (self.active or player is None or self.flock.wild.window is not None
                or not 1 <= floor <= tower.unlocked):
            return
        self.cancel()
        self.player = player
        self.continuous = continuous
        self.start_round(floor)

    def start_round(self, floor):
        tower = self.flock.tower
        player = self.player
        self.floor = floor
        self.battle = Battle(tower.player(player.character_key, player),
                             tower.opponent(floor, self.flock.catalog))
        desktop = player.desktop
        desktop.field_fighting = True
        desktop.movement.reset(desktop.base.x())
        desktop.movement.left = self.overlay.place(desktop)
        desktop.update()
        self.overlay.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, player.settings.on_top)
        self.overlay.battle = self.battle
        self.overlay.art = QPixmap(str(self.flock.assets / "tower" / f"{floor}.png"))
        mode = "자동 사냥" if self.continuous else "자동 전투"
        self.overlay.message = f"배틀타워 {floor}층 · {mode} 시작"
        self.overlay.hit_at = 0
        self.overlay.show()
        self.timer.start()
        self.paint_timer.start()

    def next_round(self):
        if (not self.continuous or self.player is None
                or self.fighter(self.player.character_key) is not self.player):
            self.cancel()
            return
        self.start_round(min(FLOOR_COUNT, self.floor + 1))

    def repaint(self):
        desktop = self.player.desktop
        if not desktop.isVisible() or self.player.pet.state == "수면":
            self.cancel()
            return
        desktop.movement.left = self.overlay.place(desktop)
        self.overlay.update()

    def advance(self):
        if not self.timer.isActive():
            return
        if not self.player.desktop.isVisible() or self.player.pet.state == "수면":
            self.cancel()
            return
        skill = not self.battle.cooldown
        if skill:
            self.player.desktop.reaction("thunder", "", f"{self.player.skill_name}!")
        else:
            self.player.desktop.jump_start = time.monotonic()
        before = self.battle.hp
        lines = self.battle.auto_act()
        self.overlay.hit_at = time.monotonic()
        self.overlay.hit_partner = self.battle.hp < before
        self.overlay.message = f"{self.floor}층 · {lines[0]}"
        if self.battle.outcome:
            self.finish()

    def finish(self):
        self.timer.stop()
        self.paint_timer.stop()
        continue_hunt = False
        if self.battle.outcome == "lose":
            message = f"{self.floor}층 패배 · 자동 사냥 종료" if self.continuous else (
                f"{self.floor}층 패배 · 우클릭으로 다시 도전")
        else:
            before = self.flock.economy.gold
            was_cleared = self.flock.tower.cleared
            try:
                xp = self.flock.tower.record_win(self.floor)
            except OSError:
                logging.exception("배틀타워 진행 저장 실패")
                message = "승리했지만 진행을 저장하지 못했어요."
            else:
                leveled = self.player.pet.change(xp=xp)
                self.player.save()
                gold = self.flock.economy.gold - before
                title = "100층 정복!" if self.floor == FLOOR_COUNT and was_cleared < FLOOR_COUNT else (
                    f"{self.floor}층 승리!")
                message = f"{title}  +{gold}골드  +{xp}경험치" + ("  레벨 업!" if leveled else "")
                continue_hunt = self.continuous
        self.overlay.hit_at = 0
        self.overlay.message = message
        self.overlay.update()
        if continue_hunt:
            self.chain_timer.start()
        else:
            self.continuous = False
            self.player.desktop.field_fighting = False
            self.result_timer.start()

    def cancel(self):
        self.timer.stop()
        self.paint_timer.stop()
        self.result_timer.stop()
        self.chain_timer.stop()
        self.continuous = False
        self.overlay.hide()
        self.overlay.battle = None
        if self.player is not None:
            self.player.desktop.field_fighting = False
        self.player = self.battle = None

    def remove_partner(self, player):
        if player is self.player:
            self.cancel()
