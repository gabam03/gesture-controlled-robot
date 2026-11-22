/*
  Servo controller for the gesture-controlled robot arm.

  Receives lines over USB serial (115200 baud) from run.py, e.g.
      base:95,shoulder:90,elbow:90,gripper:10
  and moves each servo smoothly to its new angle.

  Wiring (Arduino Uno):
      base     servo signal -> pin 3
      shoulder servo signal -> pin 5
      elbow    servo signal -> pin 6
      gripper  servo signal -> pin 9
  Power the servos from a separate 5-6 V supply (not the Arduino's 5 V pin),
  with its ground connected to Arduino GND.
*/

#include <Servo.h>

const int NUM_JOINTS = 4;
const char* JOINT_NAMES[NUM_JOINTS] = {"base", "shoulder", "elbow", "gripper"};
const int   JOINT_PINS[NUM_JOINTS]  = {3, 5, 6, 9};
const int   MIN_ANGLE[NUM_JOINTS]   = {0, 15, 0, 10};
const int   MAX_ANGLE[NUM_JOINTS]   = {180, 165, 180, 90};
const int   STEP_DELAY_MS = 8;   // smaller = faster movement

Servo servos[NUM_JOINTS];
int current[NUM_JOINTS] = {90, 90, 90, 90};
int target[NUM_JOINTS]  = {90, 90, 90, 90};
String buffer = "";

int jointIndex(const String& name) {
  for (int i = 0; i < NUM_JOINTS; i++) if (name == JOINT_NAMES[i]) return i;
  return -1;
}

// Parse "base:95,shoulder:90,..." and update targets
void parseLine(String line) {
  line.trim();
  int start = 0;
  while (start < (int)line.length()) {
    int comma = line.indexOf(',', start);
    if (comma == -1) comma = line.length();
    String pair = line.substring(start, comma);
    int colon = pair.indexOf(':');
    if (colon > 0) {
      int j = jointIndex(pair.substring(0, colon));
      if (j >= 0) target[j] = constrain(pair.substring(colon + 1).toInt(), MIN_ANGLE[j], MAX_ANGLE[j]);
    }
    start = comma + 1;
  }
}

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < NUM_JOINTS; i++) {
    servos[i].attach(JOINT_PINS[i]);
    servos[i].write(current[i]);
  }
  Serial.println("Servo controller ready");
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') { parseLine(buffer); buffer = ""; }
    else if (buffer.length() < 80) buffer += c;
  }
  // Move each servo one degree towards its target for smooth motion
  for (int i = 0; i < NUM_JOINTS; i++) {
    if (current[i] != target[i]) {
      current[i] += (target[i] > current[i]) ? 1 : -1;
      servos[i].write(current[i]);
    }
  }
  delay(STEP_DELAY_MS);
}
