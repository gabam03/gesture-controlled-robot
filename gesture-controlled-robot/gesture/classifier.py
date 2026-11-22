"""
Hand-gesture classification from MediaPipe hand landmarks.

MediaPipe returns 21 landmarks per hand (x, y in 0-1 image coordinates):
    0 wrist
    1-4   thumb  (CMC, MCP, IP, TIP)
    5-8   index  (MCP, PIP, DIP, TIP)
    9-12  middle
    13-16 ring
    17-20 pinky

A finger counts as "extended" when its tip is clearly further from the wrist
than its middle joint (PIP). Using distances from the wrist, instead of
"tip is above joint", means it still works when the hand is tilted.
"""

import math

FINGERS = {            # name: (PIP joint, TIP)
    "index": (6, 8),
    "middle": (10, 12),
    "ring": (14, 16),
    "pinky": (18, 20),
}
EXTEND_RATIO = 1.15     # tip must be 15% further from the wrist than the PIP joint
THUMB_RATIO = 0.55      # thumb tip distance from index knuckle, relative to palm size

# Finger pattern (thumb, index, middle, ring, pinky) -> gesture name
GESTURES = {
    (0, 0, 0, 0, 0): "FIST",
    (1, 1, 1, 1, 1): "OPEN_PALM",
    (0, 1, 1, 1, 1): "OPEN_PALM",   # thumb tucked still counts as an open hand
    (0, 1, 0, 0, 0): "POINT",
    (0, 1, 1, 0, 0): "PEACE",
    (0, 1, 1, 1, 0): "THREE",
    (1, 0, 0, 0, 0): "THUMBS_UP",
}


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def finger_states(landmarks):
    """
    landmarks: list of 21 (x, y) tuples.
    Returns a tuple of 0/1 for (thumb, index, middle, ring, pinky).
    """
    if len(landmarks) != 21:
        raise ValueError(f"Expected 21 landmarks, got {len(landmarks)}")
    wrist = landmarks[0]
    palm = _dist(wrist, landmarks[9]) or 1e-6      # wrist to middle knuckle = hand scale

    states = []
    thumb_out = _dist(landmarks[4], landmarks[5]) / palm > THUMB_RATIO
    states.append(int(thumb_out))
    for pip, tip in FINGERS.values():
        states.append(int(_dist(wrist, landmarks[tip]) > EXTEND_RATIO * _dist(wrist, landmarks[pip])))
    return tuple(states)


def classify(landmarks):
    """Return (gesture_name, finger_states). Unknown patterns return 'UNKNOWN'."""
    states = finger_states(landmarks)
    return GESTURES.get(states, "UNKNOWN"), states


class Debouncer:
    """
    Only accept a gesture once it has been seen for `frames` frames in a row.
    Stops the robot reacting to the in-between shapes while the hand changes gesture.
    """

    def __init__(self, frames=5):
        self.frames = frames
        self.candidate = None
        self.count = 0

    def update(self, gesture):
        if gesture == self.candidate:
            self.count += 1
        else:
            self.candidate, self.count = gesture, 1
        return gesture if self.count >= self.frames else None
