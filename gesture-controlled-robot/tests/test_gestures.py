"""
Tests use synthetic hand landmarks built from simple geometry, so they run
without a camera or the MediaPipe model.
"""

import math
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
from gesture import Debouncer, RobotArm, classify  # noqa: E402


def make_hand(thumb, index, middle, ring, pinky, tilt_deg=0):
    """
    Build 21 (x, y) landmarks for an upright hand, then rotate by tilt_deg.
    Extended fingers point straight up; folded fingers curl back towards the palm.
    """
    wrist = (0.0, 0.0)
    pts = [wrist] + [None] * 20
    # thumb: CMC, MCP, IP, TIP
    if thumb:
        pts[1:5] = [(-0.08, -0.05), (-0.16, -0.10), (-0.24, -0.15), (-0.32, -0.20)]
    else:
        pts[1:5] = [(-0.06, -0.05), (-0.08, -0.10), (-0.04, -0.14), (0.0, -0.16)]
    bases = {5: -0.06, 9: 0.0, 13: 0.06, 17: 0.12}  # x of each knuckle
    for (mcp, state) in zip((5, 9, 13, 17), (index, middle, ring, pinky)):
        x = bases[mcp]
        pts[mcp] = (x, -0.30)
        pts[mcp + 1] = (x, -0.40)                 # PIP
        if state:
            pts[mcp + 2] = (x, -0.48)             # DIP
            pts[mcp + 3] = (x, -0.55)             # TIP
        else:
            pts[mcp + 2] = (x, -0.33)
            pts[mcp + 3] = (x, -0.26)             # curled back below the PIP
    t = math.radians(tilt_deg)
    rot = [(x * math.cos(t) - y * math.sin(t), x * math.sin(t) + y * math.cos(t)) for x, y in pts]
    return [(0.5 + x, 0.8 + y) for x, y in rot]


class TestClassifier(unittest.TestCase):
    def check(self, fingers, expected, tilt=0):
        gesture, _ = classify(make_hand(*fingers, tilt_deg=tilt))
        self.assertEqual(gesture, expected)

    def test_fist(self):
        self.check((0, 0, 0, 0, 0), "FIST")

    def test_open_palm(self):
        self.check((1, 1, 1, 1, 1), "OPEN_PALM")

    def test_point(self):
        self.check((0, 1, 0, 0, 0), "POINT")

    def test_peace(self):
        self.check((0, 1, 1, 0, 0), "PEACE")

    def test_three(self):
        self.check((0, 1, 1, 1, 0), "THREE")

    def test_thumbs_up(self):
        self.check((1, 0, 0, 0, 0), "THUMBS_UP")

    def test_works_when_hand_is_tilted(self):
        self.check((0, 1, 1, 0, 0), "PEACE", tilt=35)

    def test_unmapped_pattern_is_unknown(self):
        self.check((0, 0, 0, 0, 1), "UNKNOWN")

    def test_wrong_landmark_count_rejected(self):
        with self.assertRaises(ValueError):
            classify([(0, 0)] * 5)


class TestDebouncer(unittest.TestCase):
    def test_needs_consecutive_frames(self):
        d = Debouncer(frames=3)
        self.assertIsNone(d.update("FIST"))
        self.assertIsNone(d.update("FIST"))
        self.assertEqual(d.update("FIST"), "FIST")

    def test_flicker_resets_count(self):
        d = Debouncer(frames=3)
        d.update("FIST"); d.update("FIST"); d.update("POINT")
        self.assertIsNone(d.update("FIST"))


class TestArm(unittest.TestCase):
    def setUp(self):
        self.arm = RobotArm.from_file(os.path.join(ROOT, "gesture_map.json"))

    def test_step_command(self):
        cmd = self.arm.apply("PEACE")
        self.assertEqual((cmd["command"], cmd["from"], cmd["to"]), ("BASE_RIGHT", 90, 95))

    def test_target_command(self):
        cmd = self.arm.apply("FIST")
        self.assertEqual((cmd["command"], cmd["to"]), ("GRIPPER_CLOSE", 10))

    def test_joint_limit_enforced(self):
        for _ in range(50):
            cmd = self.arm.apply("THUMBS_UP")
        self.assertEqual(cmd["to"], 165)
        self.assertTrue(cmd["at_limit"])

    def test_unmapped_gesture_ignored(self):
        self.assertIsNone(self.arm.apply("UNKNOWN"))

    def test_serial_line_format(self):
        self.assertEqual(self.arm.serial_line(), "base:90,shoulder:90,elbow:90,gripper:90\n")


if __name__ == "__main__":
    unittest.main()
