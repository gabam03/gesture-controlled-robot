#!/usr/bin/env python3
"""
Gesture-controlled robot arm.

  python run.py                       # webcam + on-screen simulated arm
  python run.py --serial COM3         # also drive real servos via Arduino (Linux: /dev/ttyUSB0)
  python run.py --demo                # no camera: run a scripted gesture sequence

Every accepted gesture prints one JSON command line, for example:
  {"gesture": "PEACE", "command": "BASE_RIGHT", "joint": "base", "from": 90, "to": 95, ...}
"""

import argparse
import json
import math
import os
import sys
import time

from gesture import Debouncer, RobotArm, classify

MODEL_PATH = os.path.join("models", "hand_landmarker.task")
HAND_LINKS = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (5, 9), (9, 10),
              (10, 11), (11, 12), (9, 13), (13, 14), (14, 15), (15, 16), (13, 17), (17, 18),
              (18, 19), (19, 20), (0, 17)]


def open_serial(port):
    if not port:
        return None
    import serial  # pyserial
    s = serial.Serial(port, 115200, timeout=0.1)
    time.sleep(2)  # Arduino resets when the port opens
    return s


def emit(cmd, arm, ser):
    print(json.dumps(cmd))
    if ser:
        ser.write(arm.serial_line().encode())


def draw_arm(frame, angles, origin):
    """Draw a simple side view of the arm: shoulder and elbow links plus gripper opening."""
    import cv2
    ox, oy = origin
    cv2.rectangle(frame, (ox - 40, oy), (ox + 40, oy + 20), (90, 90, 90), -1)
    s = math.radians(angles["shoulder"])
    e = math.radians(angles["shoulder"] + angles["elbow"] - 90)
    p1 = (int(ox + 110 * math.cos(s)), int(oy - 110 * math.sin(s)))
    p2 = (int(p1[0] + 90 * math.cos(e)), int(p1[1] - 90 * math.sin(e)))
    cv2.line(frame, (ox, oy), p1, (100, 56, 31), 10)
    cv2.line(frame, p1, p2, (100, 56, 31), 8)
    gap = int(4 + angles["gripper"] / 90 * 18)
    cv2.line(frame, p2, (p2[0] + 18, p2[1] - gap), (0, 140, 255), 4)
    cv2.line(frame, p2, (p2[0] + 18, p2[1] + gap), (0, 140, 255), 4)
    for p in ((ox, oy), p1, p2):
        cv2.circle(frame, p, 7, (255, 255, 255), -1)
    y = oy + 45
    for j, a in angles.items():
        cv2.putText(frame, f"{j}: {a} deg", (ox - 60, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        y += 20


def run_camera(arm, ser, camera_index):
    import cv2
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision

    if not os.path.exists(MODEL_PATH):
        sys.exit(f"Model not found at {MODEL_PATH}. Run: python download_model.py")

    options = vision.HandLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.6,
        min_tracking_confidence=0.5,
    )
    landmarker = vision.HandLandmarker.create_from_options(options)
    cap = cv2.VideoCapture(camera_index)
    debounce = Debouncer(frames=5)
    last_accepted = None
    start = time.time()

    print("Show a gesture to the camera. Press q to quit.")
    while cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            break
        frame = cv2.flip(frame, 1)  # mirror view feels natural
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = landmarker.detect_for_video(
            mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), int((time.time() - start) * 1000))

        label = "No hand"
        if result.hand_landmarks:
            pts = [(p.x, p.y) for p in result.hand_landmarks[0]]
            gesture, states = classify(pts)
            label = f"{gesture}  {''.join(map(str, states))}"
            px = [(int(x * w), int(y * h)) for x, y in pts]
            for a, b in HAND_LINKS:
                cv2.line(frame, px[a], px[b], (0, 200, 0), 2)
            for p in px:
                cv2.circle(frame, p, 4, (0, 0, 255), -1)

            accepted = debounce.update(gesture)
            # step gestures repeat while held; target gestures fire once
            if accepted and (accepted != last_accepted or "step" in arm.mapping.get(accepted, {})):
                cmd = arm.apply(accepted)
                if cmd:
                    emit(cmd, arm, ser)
            last_accepted = accepted
        else:
            debounce.update(None)
            last_accepted = None

        cv2.rectangle(frame, (0, 0), (w, 40), (0, 0, 0), -1)
        cv2.putText(frame, label, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        draw_arm(frame, arm.angles, (w - 170, h - 140))
        cv2.imshow("Gesture-controlled robot", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


def run_demo(arm, ser):
    """Scripted sequence through the same debounce + mapping logic, no camera needed."""
    script = ["OPEN_PALM"] * 6 + ["PEACE"] * 12 + ["THUMBS_UP"] * 10 + ["FIST"] * 6 + ["UNKNOWN"] * 3 + ["POINT"] * 7
    debounce = Debouncer(frames=5)
    last = None
    for g in script:
        accepted = debounce.update(g)
        if accepted and (accepted != last or "step" in arm.mapping.get(accepted, {})):
            cmd = arm.apply(accepted)
            if cmd:
                emit(cmd, arm, ser)
        last = accepted
    print("Final angles:", json.dumps(arm.angles))


def main():
    p = argparse.ArgumentParser(description="Gesture-controlled robot arm")
    p.add_argument("--serial", help="serial port of the Arduino servo controller")
    p.add_argument("--camera", type=int, default=0)
    p.add_argument("--map", default="gesture_map.json")
    p.add_argument("--demo", action="store_true", help="run without a camera")
    args = p.parse_args()

    arm = RobotArm.from_file(args.map)
    ser = open_serial(args.serial)
    if args.demo:
        run_demo(arm, ser)
    else:
        run_camera(arm, ser, args.camera)


if __name__ == "__main__":
    main()
