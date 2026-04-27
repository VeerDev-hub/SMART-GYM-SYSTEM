#include <Arduino.h>
#include <LiquidCrystal.h>
#include <MFRC522.h>
#include <SPI.h>

static const byte SS_PIN = 10;
static const byte RST_PIN = 9;
static const int BUTTON_PIN = 8;
static const int BUZZER_PIN = A0;
static const int IR_SENSOR_PIN = A1;
static const int IR_TRIGGER_THRESHOLD = 450;

static const unsigned long UART_HEARTBEAT_MS = 3000;
static const unsigned long IR_SAMPLE_MS = 600;
static const unsigned long TEMP_SCREEN_MS = 2200;
static const unsigned long STATUS_ROTATE_MS = 1800;
static const unsigned long UART_TIMEOUT_MS = 7000;

LiquidCrystal lcd(2, 3, 4, 5, 6, 7);
MFRC522 mfrc522(SS_PIN, RST_PIN);

struct DiagnosticsState {
  bool lcdOk = false;
  bool buzzerOk = false;
  bool buttonOk = false;
  bool irOk = false;
  bool rfidOk = false;
  bool uartRxOk = false;
  bool uartAckOk = false;
  int lastIrValue = 0;
};

DiagnosticsState diag;
unsigned long lastHeartbeatAt = 0;
unsigned long lastIrSampleAt = 0;
unsigned long lastScreenAt = 0;
unsigned long lastTempScreenAt = 0;
unsigned long lastEsp32MessageAt = 0;
unsigned long lastIrTriggerAt = 0;
bool tempScreenActive = false;
uint8_t screenIndex = 0;
bool allChecksAnnounced = false;

String uidToString(const MFRC522::Uid &uid) {
  String value = "";
  for (byte i = 0; i < uid.size; i++) {
    if (uid.uidByte[i] < 0x10) {
      value += "0";
    }
    value += String(uid.uidByte[i], HEX);
  }
  value.toUpperCase();
  return value;
}

void buzzOk() {
  tone(BUZZER_PIN, 1800, 70);
  delay(100);
  tone(BUZZER_PIN, 2200, 90);
}

void buzzWarn() {
  tone(BUZZER_PIN, 700, 150);
}

void setScreen(const String &line1, const String &line2, bool temporary) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(line1.substring(0, 16));
  lcd.setCursor(0, 1);
  lcd.print(line2.substring(0, 16));
  tempScreenActive = temporary;
  if (temporary) {
    lastTempScreenAt = millis();
  }
}

void sendPacket(const String &message) {
  Serial.println(message);
}

void sendEvent(const String &eventType, const String &value) {
  sendPacket("ARDUINO|" + eventType + "|" + value);
}

int completedChecks() {
  return int(diag.buttonOk) + int(diag.irOk) + int(diag.rfidOk) + int(diag.uartAckOk);
}

bool allChecksPassed() {
  return diag.buttonOk && diag.irOk && diag.rfidOk && diag.uartAckOk;
}

void showRotatingStatus() {
  if (tempScreenActive) {
    return;
  }
  if (millis() - lastScreenAt < STATUS_ROTATE_MS) {
    return;
  }

  lastScreenAt = millis();
  bool uartOnline = diag.uartRxOk && (millis() - lastEsp32MessageAt <= UART_TIMEOUT_MS);

  switch (screenIndex % 4) {
    case 0:
      setScreen("Diag: Arduino", "Pass " + String(completedChecks()) + "/4", false);
      break;
    case 1:
      setScreen("BTN:" + String(diag.buttonOk ? "OK" : "WAIT"),
                "IR:" + String(diag.irOk ? "OK" : "WAIT") + " " + String(diag.lastIrValue), false);
      break;
    case 2:
      setScreen("RFID:" + String(diag.rfidOk ? "OK" : "WAIT"),
                "UART:" + String(uartOnline ? "LINK" : "WAIT"), false);
      break;
    default:
      setScreen("Pins 0/1 -> ESP", uartOnline ? "Replies OK" : "Need reply", false);
      break;
  }
  screenIndex++;
}

void showStartupSequence() {
  setScreen("LCD TEST", "Buzzer beep...", true);
  diag.lcdOk = true;
  buzzOk();
  diag.buzzerOk = true;
  delay(450);
  setScreen("UART Pins", "0=RX 1=TX", true);
}

void checkButton() {
  static bool lastState = HIGH;
  bool currentState = digitalRead(BUTTON_PIN);
  if (lastState == HIGH && currentState == LOW) {
    diag.buttonOk = true;
    buzzOk();
    setScreen("Button OK", "UART send BTN", true);
    sendEvent("BUTTON", "PRESSED");
  }
  lastState = currentState;
}

void checkIrSensor() {
  if (millis() - lastIrSampleAt < IR_SAMPLE_MS) {
    return;
  }

  lastIrSampleAt = millis();
  diag.lastIrValue = analogRead(IR_SENSOR_PIN);
  if (diag.lastIrValue < IR_TRIGGER_THRESHOLD && millis() - lastIrTriggerAt > 1200) {
    lastIrTriggerAt = millis();
    diag.irOk = true;
    setScreen("IR Triggered", String(diag.lastIrValue), true);
    sendEvent("IR", "TRIGGERED:" + String(diag.lastIrValue));
  }
}

void checkRfid() {
  if (!mfrc522.PICC_IsNewCardPresent() || !mfrc522.PICC_ReadCardSerial()) {
    return;
  }

  String uid = uidToString(mfrc522.uid);
  diag.rfidOk = true;
  setScreen("RFID OK", uid, true);
  buzzOk();
  sendEvent("RFID", uid);

  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();
  delay(350);
}

void handleEsp32Message(const String &message) {
  if (message.length() == 0) {
    return;
  }

  diag.uartRxOk = true;
  lastEsp32MessageAt = millis();

  if (message == "HELLO_FROM_ESP32" || message.startsWith("ACK:")) {
    diag.uartAckOk = true;
  }

  if (message == "HELLO_FROM_ESP32") {
    setScreen("ESP32 Online", "UART heartbeat", true);
  } else if (message.startsWith("ACK:")) {
    setScreen("UART ACK", message.substring(4), true);
  } else if (message.startsWith("ULTRA:")) {
    setScreen("ESP32 Ultra", message.substring(6), true);
  } else {
    setScreen("ESP32 Reply", message, true);
  }
}

void checkEsp32Messages() {
  static String buffer = "";
  while (Serial.available()) {
    char c = char(Serial.read());
    if (c == '\n') {
      buffer.trim();
      handleEsp32Message(buffer);
      buffer = "";
    } else if (c != '\r') {
      buffer += c;
    }
  }
}

void sendHeartbeat() {
  if (millis() - lastHeartbeatAt < UART_HEARTBEAT_MS) {
    return;
  }
  lastHeartbeatAt = millis();
  sendEvent("HEARTBEAT", "HELLO_FROM_ARDUINO");
}

void updateTemporaryScreen() {
  if (tempScreenActive && millis() - lastTempScreenAt > TEMP_SCREEN_MS) {
    tempScreenActive = false;
  }
}

void announceAllChecksPassed() {
  if (allChecksAnnounced || !allChecksPassed()) {
    return;
  }

  allChecksAnnounced = true;
  buzzOk();
  setScreen("Arduino PASS", "All checks OK", true);
  sendEvent("PASS", "ALL_CHECKS_OK");
}

void setup() {
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(IR_SENSOR_PIN, INPUT);

  Serial.begin(9600);
  SPI.begin();
  mfrc522.PCD_Init();
  lcd.begin(16, 2);

  showStartupSequence();
}

void loop() {
  checkButton();
  checkIrSensor();
  checkRfid();
  checkEsp32Messages();
  sendHeartbeat();
  updateTemporaryScreen();
  announceAllChecksPassed();
  showRotatingStatus();

  bool uartStale = diag.uartRxOk && (millis() - lastEsp32MessageAt > UART_TIMEOUT_MS);
  if (uartStale) {
    diag.uartAckOk = false;
  }
}
