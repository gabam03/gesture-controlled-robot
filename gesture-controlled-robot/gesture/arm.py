"""
Maps gestures to robot-arm commands and keeps track of joint angles.

The mapping lives in gesture_map.json so it can be changed without editing code.
Commands are produced as JSON and, optionally, sent over serial to the
Arduino servo controller in arduino/servo_controller.
"""

import json

DEFAULT_LIMITS = {          # joint: (min, max, start) in degrees
    "base": (0, 180, 90),
    "shoulder": (15, 165, 90),
    "elbow": (0, 180, 90),
    "gripper": (10, 90, 90),
}


class RobotArm:
    def __init__(self, mapping, limits=None):
        self.mapping = mapping
        self.limits = limits or DEFAULT_LIMITS
        self.angles = {j: lim[2] for j, lim in self.limits.items()}

    @classmethod
    def from_file(cls, path):
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f))

    def apply(self, gesture):
        """
        Apply a gesture. Returns a command dict, or None if the gesture isn't mapped.
        Mapping entries use either "step" (move by N degrees) or "target" (go to N degrees).
        """
        rule = self.mapping.get(gesture)
        if rule is None:
            return None
        joint = rule["joint"]
        lo, hi, _ = self.limits[joint]
        before = self.angles[joint]
        if "target" in rule:
            after = rule["target"]
        else:
            after = before + rule.get("step", 0)
        after = max(lo, min(hi, after))
        self.angles[joint] = after
        return {
            "gesture": gesture,
            "command": rule["command"],
            "joint": joint,
            "from": before,
            "to": after,
            "at_limit": after in (lo, hi) and after != rule.get("target"),
            "angles": dict(self.angles),
        }

    def serial_line(self):
        """Line format understood by the Arduino: base:90,shoulder:90,elbow:90,gripper:90"""
        return ",".join(f"{j}:{a}" for j, a in self.angles.items()) + "\n"
