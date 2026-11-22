#!/usr/bin/env python3
"""Download the MediaPipe hand landmark model (about 8 MB) into models/."""

import os
import urllib.request

URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
       "hand_landmarker/float16/1/hand_landmarker.task")
PATH = os.path.join("models", "hand_landmarker.task")

os.makedirs("models", exist_ok=True)
if os.path.exists(PATH):
    print(f"Model already present: {PATH}")
else:
    print("Downloading hand landmark model...")
    urllib.request.urlretrieve(URL, PATH)
    print(f"Saved to {PATH}")
