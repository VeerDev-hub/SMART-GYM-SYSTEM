#include <Arduino.h>
#include <MFRC522.h>
#include <SPI.h>

static const byte SS_PIN = 5;
static const byte RST_PIN = 27;
static const int UART_RX_PIN = 16;
static const int UART_TX_PIN = 17;
static const int TRIG_PIN = 32;
static const int ECHO_PIN = 33;

static const unsigned long UART_HEARTBEAT_MS = 3000;
static const unsigned long SENSOR_REPORT_MS = 1200;
static const unsigned long SUMMARY_REPORT_MS = 5000;
static const unsigned long UART_TIMEOUT_MS = 7000;

MFRC522 mfrc522(SS_PIN, RST_PIN);

struct DiagnosticsState {
  bool uartRxOk = false;
  bool uartTxOk = false;
  bool uartLinkOk = false;
  bool ultrasonicOk = false;
  bool rfidOk = false;
  float lastDistanceCm = -1.0f;
  unsigned long lastArduinoMessageAt = 0;
};

DiagnosticsState diag;
unsigned long lastHeartbeatAt = 0;
unsigned long lastSensorReportAt = 0;
unsigned long lastSummaryAt = 0;
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

void sendUart(const String &message) {
  Serial2.println(message);
  diag.uartTxOk = true;
}

void logEvent(const String &source, const String &eventType, const String &value) {
  Serial.print("[");
  Serial.print(millis());
  Serial.print(" ms] ");
  Serial.print(source);
  Serial.print(" | ");
  Serial.print(eventType);
  Serial.print(" | ");
  Serial.println(value);
}

float readDistanceCm() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(4);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  long duration = pulseIn(ECHO_PIN, HIGH, 30000);
  if (duration <= 0) {
    return -1.0f;
  }
  return duration * 0.0343f / 2.0f;
}

void reportSummary() {
  Serial.println("---- ESP32 Diagnostics ----");
  Serial.printf("UART RX: %s\n", diag.uartRxOk ? "OK" : "WAIT");
  Serial.printf("UART TX: %s\n", diag.uartTxOk ? "OK" : "WAIT");
  Serial.printf("UART LINK: %s\n", diag.uartLinkOk ? "OK" : "WAIT");
  Serial.printf("RFID: %s\n", diag.rfidOk ? "OK" : "WAIT");
  Serial.printf("ULTRASONIC: %s", diag.ultrasonicOk ? "OK" : "WAIT");
  if (diag.lastDistanceCm >= 0) {
    Serial.printf(" (%.1f cm)\n", diag.lastDistanceCm);
  } else {
    Serial.println(" (no echo)");
  }
  Serial.println("---------------------------");
}

bool allChecksPassed() {
  return diag.uartRxOk && diag.uartTxOk && diag.uartLinkOk && diag.ultrasonicOk && diag.rfidOk;
}

void checkUartInput() {
  static String buffer = "";
  while (Serial2.available()) {
    char c = char(Serial2.read());
    if (c == '\n') {
      buffer.trim();
      if (buffer.length() > 0) {
        diag.uartRxOk = true;
        diag.uartLinkOk = true;
        diag.lastArduinoMessageAt = millis();
        logEvent("UART_RX", "RAW", buffer);
        sendUart("ACK:" + buffer);
        if (buffer == "ARDUINO|PASS|ALL_CHECKS_OK") {
          logEvent("ARDUINO", "PASS", "ALL_CHECKS_OK");
        }
      }
      buffer = "";
    } else if (c != '\r') {
      buffer += c;
    }
  }

  if (diag.uartLinkOk && millis() - diag.lastArduinoMessageAt > UART_TIMEOUT_MS) {
    diag.uartLinkOk = false;
  }
}

void sendHeartbeat() {
  if (millis() - lastHeartbeatAt < UART_HEARTBEAT_MS) {
    return;
  }
  lastHeartbeatAt = millis();
  sendUart("HELLO_FROM_ESP32");
  logEvent("ESP32", "HEARTBEAT", "HELLO_FROM_ESP32");
}

void checkUltrasonic() {
  if (millis() - lastSensorReportAt < SENSOR_REPORT_MS) {
    return;
  }
  lastSensorReportAt = millis();

  diag.lastDistanceCm = readDistanceCm();
  if (diag.lastDistanceCm > 0) {
    diag.ultrasonicOk = true;
    logEvent("ESP32", "ULTRASONIC", String(diag.lastDistanceCm, 1) + "cm");
    sendUart("ULTRA:" + String(diag.lastDistanceCm, 1) + "cm");
  } else {
    logEvent("ESP32", "ULTRASONIC", "NO_ECHO");
  }
}

void checkRfid() {
  if (!mfrc522.PICC_IsNewCardPresent() || !mfrc522.PICC_ReadCardSerial()) {
    return;
  }

  String uid = uidToString(mfrc522.uid);
  diag.rfidOk = true;
  logEvent("ESP32", "RFID", uid);
  sendUart("ESP32_RFID:" + uid);

  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();
  delay(250);
}

void setup() {
  Serial.begin(115200);
  Serial2.begin(9600, SERIAL_8N1, UART_RX_PIN, UART_TX_PIN);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  SPI.begin(18, 19, 23, SS_PIN);
  mfrc522.PCD_Init();

  Serial.println("ESP32 diagnostics ready");
  Serial.println("UART RX2=16 TX2=17");
  Serial.println("RFID SS=5 RST=27");
  Serial.println("Ultrasonic TRIG=32 ECHO=33");
  Serial.println("Waiting for UART, RFID, and ultrasonic checks...");
  Serial.println("Structured logs: [time ms] SOURCE | EVENT | VALUE");
}

void loop() {
  checkUartInput();
  sendHeartbeat();
  checkUltrasonic();
  checkRfid();

  if (millis() - lastSummaryAt >= SUMMARY_REPORT_MS) {
    lastSummaryAt = millis();
    reportSummary();
  }

  if (!allChecksAnnounced && allChecksPassed()) {
    allChecksAnnounced = true;
    logEvent("ESP32", "PASS", "UART, RFID, ULTRASONIC OK");
    sendUart("ESP32:ALL_CHECKS_OK");
  }
}
