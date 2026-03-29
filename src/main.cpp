#include <Arduino.h>

/*
Might make an LED blink...
*/
int ledPin = 8; // D8

void setup() {
  Serial.begin(9600);
  pinMode(ledPin, OUTPUT);
}

void loop() {
  digitalWrite(ledPin, HIGH);
  delay(3000);
  digitalWrite(ledPin, LOW);
  delay(3000);
}
