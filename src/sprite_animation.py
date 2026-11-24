from dataclasses import dataclass

from PySide6.QtCore import QRectF
from PySide6.QtGui import QMovie


@dataclass(frozen=True)
class Clip:
    frames: tuple
    seconds: float


class SpriteAnimation:
    def __init__(self, movie, profile):
        self.movie = movie
        self.ground = profile["ground"]
        self.clips = {
            name: Clip(tuple(clip["frames"]), clip["frame_ms"] / 1000)
            for name, clip in profile["clips"].items()
        }
        self.state = ""
        self.started = 0
        self.movie.setCacheMode(QMovie.CacheMode.CacheAll)
        # Decode each frame sequentially so GIF disposal and transparency are honored.
        last = max(index for clip in self.clips.values() for index in clip.frames)
        for index in range(last + 1):
            if not self.movie.jumpToFrame(index):
                raise ValueError("스프라이트 프레임을 읽을 수 없습니다.")
        self.movie.jumpToFrame(self.clips["idle"].frames[0])

    def update(self, state, now):
        state = state if state in self.clips else "idle"
        if state != self.state:
            self.state = state
            self.started = now
        clip = self.clips[state]
        offset = max(0, int((now - self.started) / clip.seconds))
        frame = clip.frames[offset % len(clip.frames)]
        if frame == self.movie.currentFrameNumber():
            return False
        return self.movie.jumpToFrame(frame)

    def bounds(self, frame, width, height, dpr, compression, lean):
        native_width, native_height = frame.width(), frame.height()
        available = min(width * dpr / native_width, height * dpr / native_height)
        factor = int(available) if available >= 1 else available
        scale = factor * (1 - compression) / dpr
        draw_width = native_width * scale
        draw_height = native_height * scale
        dx = max(0, (width - draw_width) / 2)
        x = dx + max(-dx, min(dx, lean * width))
        y = height - self.ground * scale
        return QRectF(round(x * dpr) / dpr, round(y * dpr) / dpr, draw_width, draw_height)
