#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include "config.h"

struct LessonStep {
  int number;
  const char* description;
  const char* instruction;
};

static const char* LESSON_NAME = "Wiring_an_LED_with_ESP32-C3";
static const LessonStep LESSON_STEPS[] = {
  {1, "Gather required components", "Collect the following components: ESP32-C3 development board, one LED (any color), one 330Ω resistor (or similar), and two jumper wires. Verify the LED polarity - the longer lead is the anode (positive) and the shorter lead is the cathode (negative)."},
  {2, "Connect resistor to LED anode", "Insert one lead of the 330Ω resistor into the same row as the LED's anode (longer lead). Bend the resistor leads to secure the connection. This resistor limits current flow to protect the LED from burning out."},
  {3, "Wire to ESP32-C3 GPIO pin", "Connect one jumper wire from the free end of the resistor to GPIO2 (or any available GPIO pin) on the ESP32-C3. This wire carries the signal voltage from the microcontroller to control the LED."},
  {4, "Connect ground wire to complete circuit", "Connect a second jumper wire from the LED's cathode (shorter lead, negative) directly to the GND pin on the ESP32-C3. This completes the circuit. The circuit path is: GPIO2 → Resistor → LED Anode → LED Cathode → GND. Your LED is now wired and ready for programming."}
};
static const size_t LESSON_STEP_COUNT = sizeof(LESSON_STEPS) / sizeof(LESSON_STEPS[0]);

size_t currentStepIndex = 0;
unsigned long lastPing = 0;

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  Serial.printf("Connecting to Wi-Fi '%s'...\n", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print('.');
    if (millis() - start > 20000) {
      Serial.println("\nFailed to connect within 20s");
      return;
    }
  }
  Serial.println();
  Serial.printf("Connected, IP: %s\n", WiFi.localIP().toString().c_str());
}

String getDeviceId() {
  uint64_t mac = ESP.getEfuseMac();
  char buf[32];
  sprintf(buf, "%012llX", mac);
  return String(buf);
}

String buildPayload(const LessonStep& step) {
  String payload = "{";
  payload += "\"msg\":\"lesson_step\",";
  payload += "\"device\":\"esp32c3\",";
  payload += "\"id\":\"" + getDeviceId() + "\",";
  payload += "\"lesson\":\"" + String(LESSON_NAME) + "\",";
  payload += "\"step\":" + String(step.number) + ",";
  payload += "\"step_description\":\"" + String(step.description) + "\",";
  payload += "\"instruction\":\"" + String(step.instruction) + "\"";
  payload += "}";
  return payload;
}

void sendLessonStepPing() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Not connected to Wi-Fi, skipping ping");
    return;
  }

  if (LESSON_STEP_COUNT == 0) {
    Serial.println("No lesson steps available");
    return;
  }

  const LessonStep& step = LESSON_STEPS[currentStepIndex];
  HTTPClient http;
  http.begin(SERVER_ENDPOINT);
  http.addHeader("Content-Type", "application/json");

  String payload = buildPayload(step);
  int httpCode = http.POST(payload);
  if (httpCode > 0) {
    String resp = http.getString();
    Serial.printf(
      "STEP %d/%d -> code: %d resp: %s\n",
      step.number,
      (int)LESSON_STEP_COUNT,
      httpCode,
      resp.c_str()
    );
    currentStepIndex = (currentStepIndex + 1) % LESSON_STEP_COUNT;
  } else {
    Serial.printf("STEP ping failed, error: %s\n", http.errorToString(httpCode).c_str());
  }
  http.end();
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.printf(
    "ESP32-C3 lesson firmware starting (lesson: %s, steps: %d)\n",
    LESSON_NAME,
    (int)LESSON_STEP_COUNT
  );
  connectWiFi();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  unsigned long now = millis();
  if (now - lastPing >= PING_INTERVAL_MS) {
    lastPing = now;
    sendLessonStepPing();
  }
  delay(100);
}
