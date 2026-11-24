import math


THUNDER_CHARGE = 0.42
ACTION_DURATION = {"feed": 1.45, "play": 1.26, "pet": 0.56, "thunder": 1.05, "solo_play": 1.2}
REST_POSE = (0.0, 0.0, 0.0)


def action_pose(action, age):
    """Return lift, compression and forward lean as fractions of sprite size."""
    duration = ACTION_DURATION.get(action, 0)
    if not 0 <= age < duration:
        return REST_POSE
    if action == "feed":
        bite = math.sin(math.pi * age / duration * 3) ** 2
        return 0.0, 0.17 * bite, 0.09 * bite
    if action == "play":
        hop = math.sin(math.pi * age / duration * 3) ** 2
        return 0.24 * hop, 0.085 * math.sin(math.pi * age / duration * 6) ** 2 * (1 - hop), 0.0
    if action == "solo_play":
        hop = math.sin(math.tau * age / duration) ** 2
        sway = math.sin(math.tau * age / duration)
        return 0.18 * hop, 0.06 * abs(sway) * (1 - hop), 0.05 * sway
    if action == "thunder":
        if age < THUNDER_CHARGE:
            return 0.0, 0.15 * age / THUNDER_CHARGE, 0.04 * age / THUNDER_CHARGE
        burst = (age - THUNDER_CHARGE) / (duration - THUNDER_CHARGE)
        return 0.12 * math.sin(math.pi * burst) ** 2, 0.15 * max(0, 1 - burst * 6), 0.0
    wiggle = math.sin(math.tau * age / duration * 2) * math.sin(math.pi * age / duration)
    return 0.0, 0.055 * abs(wiggle), 0.07 * wiggle


def sleep_pose(now, blend):
    breath = (1 - math.cos(math.tau * now / 3.2)) / 2
    return 0.0, (0.30 - 0.05 * breath) * blend, 0.0
