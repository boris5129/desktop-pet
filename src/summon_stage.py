import math

from PySide6.QtCore import QPointF, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QWidget


class SummonStage(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(215)
        self.kind = ""
        self.progress = 0.0
        self.image = QPixmap()
        self.animation = QVariantAnimation(self, duration=1650)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.valueChanged.connect(self.advance)

    def begin(self, kind, image):
        self.animation.stop()
        self.kind = kind
        self.image = image
        self.progress = 0.0
        self.animation.start()
        self.update()

    def advance(self, value):
        self.progress = value
        self.update()

    def set_image(self, image):
        self.image = image
        self.update()

    def paintEvent(self, event):
        with QPainter(self) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#14213b"))
            painter.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 15, 15)
            painter.translate(self.width() / 2, self.height() / 2)
            factor = min(self.width() / 390, self.height() / 215)
            painter.scale(factor, factor)
            accent = QColor("#a8f4ee" if self.kind == "digimon" else "#ffbe80")
            painter.setPen(QPen(QColor("#304464"), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for rx in (82, 116, 152):
                painter.drawEllipse(QPointF(0, 14), rx, rx * 0.49)
            if not self.kind:
                painter.setPen(QColor("#c6d3e8"))
                painter.setFont(QFont("Malgun Gothic", 12))
                painter.drawText(QRectF(-155, -16, 310, 32), Qt.AlignmentFlag.AlignCenter, "친구가 나타나는 곳")
                return

            t = self.progress
            charge = min(1.0, t / 0.53)
            reveal = max(0.0, min(1.0, (t - 0.54) / 0.42))
            rise = 1 - (1 - reveal) ** 3
            shake = math.sin(charge * math.pi * 8) * math.sin(math.pi * charge) * 7
            painter.save()
            painter.translate(shake, 12 + (1 - charge) ** 2 * 43 + 36 * rise)
            painter.setOpacity(1 - 0.42 * rise)
            if self.kind == "digimon":
                self.draw_device(painter, charge)
            else:
                self.draw_capsule(painter, rise)
            painter.restore()
            if reveal:
                self.draw_reveal(painter, accent, reveal, rise)

    @staticmethod
    def draw_capsule(painter, opening):
        painter.setPen(QPen(QColor("#542e47"), 2.5))
        for top, color in ((True, "#ef5868"), (False, "#fff0cb")):
            direction = -1 if top else 1
            painter.save()
            painter.translate(12 * opening * direction, 13 * opening * direction)
            painter.rotate(20 * opening * direction)
            part = QPainterPath()
            part.moveTo(-41, 0)
            part.arcTo(QRectF(-41, -41, 82, 82), 180, -180 if top else 180)
            part.closeSubpath()
            painter.setBrush(QColor(color))
            painter.drawPath(part)
            painter.restore()
        painter.setOpacity(painter.opacity() * (1 - opening))
        painter.setPen(QPen(QColor("#542e47"), 3))
        painter.drawLine(QPointF(-39, 0), QPointF(39, 0))
        painter.setBrush(QColor("#ffdf8c"))
        painter.drawPolygon(QPolygonF([QPointF(0, -10), QPointF(10, 0),
                                      QPointF(0, 10), QPointF(-10, 0)]))

    @staticmethod
    def draw_device(painter, charge):
        shape = QPolygonF([QPointF(-25, -41), QPointF(29, -41), QPointF(40, -28),
                           QPointF(40, 28), QPointF(25, 42), QPointF(-29, 42),
                           QPointF(-40, 28), QPointF(-40, -26)])
        painter.setPen(QPen(QColor("#233a62"), 3))
        painter.setBrush(QColor("#518aca"))
        painter.drawPolygon(shape)
        painter.setBrush(QColor("#182d49"))
        painter.drawRoundedRect(QRectF(-29, -29, 58, 35), 5, 5)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#9ff5da"))
        painter.drawRect(QRectF(-21, -11, 42 * charge, 4))
        painter.setBrush(QColor("#ffbf6b"))
        painter.drawRoundedRect(QRectF(-9, 17, 18, 18), 3, 3)
        painter.setBrush(QColor("#c3e0f7"))
        for x in (-24, 20):
            painter.drawEllipse(QPointF(x, 24), 4, 4)

    def draw_reveal(self, painter, accent, reveal, rise):
        painter.setPen(QPen(accent, 2))
        painter.setOpacity(0.66 * math.sin(math.pi * reveal))
        for i in range(12):
            angle = i * math.tau / 12
            radius = 41 + 64 * rise
            x, y = math.cos(angle), math.sin(angle) * 0.67
            painter.drawLine(QPointF(x * radius, -27 + y * radius),
                             QPointF(x * (radius + 14), -27 + y * (radius + 14)))
        painter.setOpacity(min(1.0, reveal * 4))
        if self.image.isNull():
            painter.setPen(QPen(accent, 3))
            painter.drawEllipse(QPointF(0, -18 - 17 * rise), 19 * rise, 19 * rise)
            return
        extent = 36 + 94 * rise
        ratio = min(extent / self.image.width(), extent / self.image.height())
        width = round(self.image.width() * ratio)
        height = round(self.image.height() * ratio)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.drawPixmap(QRectF(-width / 2, 43 - 17 * rise - height, width, height),
                           self.image, QRectF(self.image.rect()))
