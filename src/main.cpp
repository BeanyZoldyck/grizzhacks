#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include "config.h"

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
  // Use MAC-based ID (efuse MAC)
  uint64_t mac = ESP.getEfuseMac();
  char buf[32];
  sprintf(buf, "%012llX", mac);
  return String(buf);
}

void sendPing() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Not connected to Wi-Fi, skipping ping");
    return;
  }

  HTTPClient http;
  http.begin(SERVER_ENDPOINT);
  http.addHeader("Content-Type", "application/json");

  String payload = "{";
  payload += "\"msg\":\"hello\",";
  payload += "\"device\":\"esp32c3\",";
  payload += "\"id\":\"" + getDeviceId() + "\"";
  payload += "}";

  int httpCode = http.POST(payload);
  if (httpCode > 0) {
    String resp = http.getString();
    Serial.printf("PING -> code: %d resp: %s\n", httpCode, resp.c_str());
  } else {
    Serial.printf("PING failed, error: %s\n", http.errorToString(httpCode).c_str());
  }
  http.end();
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("ESP32-C3 Ping Client starting");
  connectWiFi();
}

unsigned long lastPing = 0;

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  unsigned long now = millis();
  if (now - lastPing >= PING_INTERVAL_MS) {
    lastPing = now;
    sendPing();
  }
  delay(100);
}
