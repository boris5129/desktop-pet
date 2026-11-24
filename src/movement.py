import random
import time


class Movement:
    def __init__(self):
        self.x = None
        self.target = None
        self.until = 0
        self.left = True

    def reset(self, x=None):
        self.x = x
        self.target = None
        self.until = time.monotonic() + random.uniform(1, 3)

    def step(self, x, low, high, speed, dt):
        now = time.monotonic()
        if self.x is None:
            self.x = x
        self.x = max(low, min(high, self.x))
        if self.target is None and now >= self.until:
            choice = random.choice(("이동", "이동", "이동", "대기", "휴식", "혼자 놀기"))
            if choice == "혼자 놀기":
                self.until = now + random.uniform(7, 12)
                return round(self.x), choice
            if choice != "이동" or high == low:
                self.until = now + random.uniform(2, 6)
                return round(self.x), "휴식" if choice == "휴식" else "대기"
            offset = random.choice((-1, 1)) * random.uniform(70, 240)
            if not low <= self.x + offset <= high:
                offset = -offset
            self.target = max(low, min(high, self.x + offset))
        if self.target is None:
            return round(self.x), None
        self.target = max(low, min(high, self.target))
        distance = self.target - self.x
        if abs(distance) <= speed * dt:
            self.x = self.target
            self.reset(self.x)
            return round(self.x), "대기"
        self.left = distance < 0
        self.x += -speed * dt if self.left else speed * dt
        return round(self.x), "이동"
