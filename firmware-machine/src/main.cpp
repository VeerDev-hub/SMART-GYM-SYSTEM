#include <Arduino.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <MFRC522.h>
#include <SPI.h>
#include <WiFi.h>

#include "config.h"

MFRC522 mfrc522(SS_PIN, RST_PIN);

enum RepState { WAIT_FOR_PUSH, WAIT_FOR_RETURN };

struct SessionState {
  bool armed = false;
  bool tracking = false;
  String uid = "";
  String memberName = "";
  String sessionId = "";
  String exerciseType = "";
  unsigned long startedAt = 0;
  unsigned long lastMovementAt = 0;
  unsigned long lastSampleAt = 0;
  unsigned long lastStatePollAt = 0;
  unsigned long repStartedAt = 0;
  int repCount = 0;
  int totalSamples = 0;
  float lastDistance = 0.0f;
  float romAccumulator = 0.0f;
  float speedAccumulator = 0.0f;
  float peakDistance = 0.0f;
  float minDistance = 999.0f;
  RepState repState = WAIT_FOR_PUSH;
};

SessionState session;
String entranceBuffer = "";
unsigned long lastEntrancePollAt = 0;

String readRFID() {
  if (!mfrc522.PICC_IsNewCardPresent() || !mfrc522.PICC_ReadCardSerial()) {
    return "";
  }

  String uid = "";
  for (byte i = 0; i < mfrc522.uid.size; i++) {
    if (mfrc522.uid.uidByte[i] < 0x10) {
      uid += "0";
    }
    uid += String(mfrc522.uid.uidByte[i], HEX);
  }
  uid.toUpperCase();
  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();
  return uid;
}

float readDistanceCm() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(4);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  long duration = pulseIn(ECHO_PIN, HIGH, 30000);
  if (duration == 0) {
    return -1.0f;
  }
  return duration * 0.0343f / 2.0f;
}

void ensureWifi() {
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long started = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - started < 12000) {
    delay(250);
    Serial.print(".");
  }
  Serial.println();
}

bool postJson(const String &path, JsonDocument &doc, String *responseBody = nullptr) {
  ensureWifi();
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi unavailable, skipping request");
    return false;
  }

  HTTPClient http;
  String url = String(BACKEND_URL) + path;
  http.begin(url);
  http.setTimeout(5000);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("x-device-key", DEVICE_KEY);

  String payload;
  serializeJson(doc, payload);
  Serial.printf("POST %s -> %s\n", url.c_str(), payload.c_str());

  int statusCode = http.POST(payload);
  String body = http.getString();
  http.end();

  if (statusCode < 0) {
    Serial.printf("HTTP error: %d (%s)\n", statusCode, http.errorToString(statusCode).c_str());
    return false;
  }

  Serial.printf("HTTP %d: %s\n", statusCode, body.c_str());

  if (responseBody != nullptr) {
    *responseBody = body;
  }
  return statusCode >= 200 && statusCode < 300;
}

bool getJson(const String &path, JsonDocument &doc) {
  ensureWifi();
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }

  HTTPClient http;
  String url = String(BACKEND_URL) + path;
  http.begin(url);
  http.addHeader("x-device-key", DEVICE_KEY);
  int statusCode = http.GET();
  String body = http.getString();
  http.end();

  if (statusCode < 200 || statusCode >= 300) {
    return false;
  }

  return !deserializeJson(doc, body);
}

bool sendThingSpeakUpdate(int field1, int field2, float field3, float field4, const String &statusText) {
  if (!USE_THINGSPEAK || String(THINGSPEAK_API_KEY) == "YOUR_THINGSPEAK_WRITE_API_KEY") {
    return false;
  }

  ensureWifi();
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }

  HTTPClient http;
  String url = String(THINGSPEAK_URL) + "?api_key=" + THINGSPEAK_API_KEY + "&field1=" + String(field1) +
               "&field2=" + String(field2) + "&field3=" + String(field3, 2) + "&field4=" + String(field4, 2) +
               "&status=" + statusText;
  http.begin(url);
  int statusCode = http.GET();
  http.getString();
  http.end();
  return statusCode > 0 && statusCode < 400;
}

void resetLocalSession() {
  session = SessionState();
  digitalWrite(TRIG_PIN, LOW);
}

void postEntranceEvent(JsonDocument &eventDoc) {
  const char *eventType = eventDoc["event"] | "";
  if (String(eventType) == "entry_log") {
    DynamicJsonDocument payload(384);
    payload["rfid_uid"] = eventDoc["rfid_uid"] | "";
    payload["granted"] = eventDoc["granted"] | false;
    payload["reason"] = eventDoc["reason"] | "membership_active";
    payload["source"] = "entrance_station_uart";
    postJson("/entry-log", payload);
    sendThingSpeakUpdate(payload["granted"] ? 1 : 0, 0, 0.0f, 0.0f,
                         String("entry_") + payload["rfid_uid"].as<const char *>());
  } else if (String(eventType) == "gate_opened" || String(eventType) == "entry_completed") {
    sendThingSpeakUpdate(0, 0, 0.0f, 0.0f, String(eventType) + "_" + String(eventDoc["rfid_uid"] | ""));
  }
}

void processEntranceUart() {
  if (millis() - lastEntrancePollAt < ENTRANCE_POLL_MS) {
    return;
  }
  lastEntrancePollAt = millis();

  while (Serial2.available()) {
    char c = char(Serial2.read());
    if (c == '\n') {
      entranceBuffer.trim();
      if (entranceBuffer.length() > 0) {
        DynamicJsonDocument eventDoc(512);
        DeserializationError err = deserializeJson(eventDoc, entranceBuffer);
        if (!err) {
          Serial.print("Entrance UART: ");
          Serial.println(entranceBuffer);
          postEntranceEvent(eventDoc);
        } else {
          Serial.print("Invalid entrance payload: ");
          Serial.println(entranceBuffer);
        }
      }
      entranceBuffer = "";
    } else if (c != '\r') {
      entranceBuffer += c;
    }
  }
}

bool postMachineTap(const String &uid) {
  Serial.printf("\n=== RFID Card Detected: %s ===\n", uid.c_str());
  Serial.printf("Backend URL: %s\n", BACKEND_URL);
  Serial.printf("WiFi status: %s (IP: %s)\n",
    WiFi.status() == WL_CONNECTED ? "Connected" : "Disconnected",
    WiFi.localIP().toString().c_str());

  DynamicJsonDocument doc(384);
  doc["rfid_uid"] = uid;
  doc["machine_name"] = "Chest Press";
  doc["station_id"] = "CHEST_PRESS_01";

  String response;
  bool ok = postJson("/machine/tap", doc, &response);
  if (!ok) {
    Serial.println("Machine tap FAILED — check backend URL and WiFi");
    return false;
  }

  DynamicJsonDocument responseDoc(512);
  if (deserializeJson(responseDoc, response)) {
    Serial.println("Machine tap response parse failed");
    return false;
  }

  resetLocalSession();
  session.armed = true;
  session.uid = uid;
  session.memberName = responseDoc["member_name"] | "";
  Serial.printf("RFID tapped: %s\n", uid.c_str());
  if (session.memberName.length() > 0) {
    Serial.printf("Member identified: %s\n", session.memberName.c_str());
  }
  Serial.println("Waiting for exercise selection from dashboard/cloud");
  sendThingSpeakUpdate(0, 0, 0.0f, 0.0f, "member_tapped");
  return true;
}

void beginTracking(const String &sessionCode, const String &exerciseType) {
  session.tracking = true;
  session.sessionId = sessionCode;
  session.exerciseType = exerciseType;
  session.startedAt = millis();
  session.lastMovementAt = millis();
  session.lastSampleAt = 0;
  session.repStartedAt = 0;
  session.repCount = 0;
  session.totalSamples = 0;
  session.lastDistance = 0.0f;
  session.romAccumulator = 0.0f;
  session.speedAccumulator = 0.0f;
  session.peakDistance = 0.0f;
  session.minDistance = 999.0f;
  session.repState = WAIT_FOR_PUSH;

  Serial.printf("Tracking enabled for %s, session=%s\n", exerciseType.c_str(), sessionCode.c_str());
  sendThingSpeakUpdate(1, 0, 0.0f, 0.0f, "tracking_started");
}

void pollMachineState() {
  if (!session.armed) {
    return;
  }
  if (millis() - session.lastStatePollAt < MACHINE_STATE_POLL_MS) {
    return;
  }
  session.lastStatePollAt = millis();

  DynamicJsonDocument doc(768);
  if (!getJson("/machine/current", doc)) {
    Serial.println("Machine state poll failed");
    return;
  }

  const char *rfidUid = doc["rfid_uid"] | "";
  const char *exerciseStatus = doc["exercise_status"] | "";
  const char *sessionCode = doc["active_session_code"] | "";
  const char *exerciseType = doc["exercise_type"] | "";

  // DEBUG PRINT
  if (String(rfidUid).length() > 0) {
    Serial.printf("[Poll] User: %s, Status: %s, Session: %s\n", rfidUid, exerciseStatus, sessionCode);
  }

  if (String(rfidUid).length() == 0 || String(exerciseStatus) == "awaiting_rfid") {
    Serial.println("Dashboard reset detected - resetting machine");
    resetLocalSession();
    return;
  }

  if (!session.tracking && session.uid.equalsIgnoreCase(rfidUid) && String(exerciseStatus) == "tracking" && String(sessionCode).length() > 0) {
    Serial.printf("Dashboard signal received: Starting tracking for %s\n", exerciseType);
    beginTracking(String(sessionCode), String(exerciseType));
  }
}

void resetRemoteMachineState() {
  DynamicJsonDocument doc(16);
  postJson("/machine/reset", doc);
}

float sampleDistance() {
  float value = readDistanceCm();
  if (value < 0) {
    return -1.0f;
  }
  session.totalSamples++;
  session.lastDistance = value;
  session.peakDistance = max(session.peakDistance, value);
  session.minDistance = min(session.minDistance, value);
  return value;
}

void sendTelemetry(float distanceValue, bool repCompleted) {
  if (!session.tracking || session.sessionId.isEmpty()) {
    return;
  }

  DynamicJsonDocument doc(384);
  doc["session_id"] = session.sessionId;
  doc["distance"] = distanceValue;
  doc["rep_count"] = session.repCount;
  doc["rom"] = session.peakDistance - session.minDistance;
  doc["rep_completed"] = repCompleted;
  postJson("/session/sample", doc);

  if (repCompleted) {
    sendThingSpeakUpdate(session.repCount, int(distanceValue * 10), session.peakDistance - session.minDistance, 0.0f,
                         "rep_completed");
  }
}

void countRep(float distanceValue) {
  if (!session.tracking || distanceValue < 0) {
    return;
  }

  bool repCompleted = false;
  if (session.repState == WAIT_FOR_PUSH && distanceValue <= PUSH_THRESHOLD_CM) {
    session.repState = WAIT_FOR_RETURN;
    session.repStartedAt = millis();
    session.lastMovementAt = millis();
  } else if (session.repState == WAIT_FOR_RETURN && distanceValue >= RETURN_THRESHOLD_CM) {
    float rom = session.peakDistance - session.minDistance;
    if (rom >= MIN_ROM_CM) {
      session.repState = WAIT_FOR_PUSH;
      session.repCount++;
      unsigned long repDuration = millis() - session.repStartedAt;
      float speed = repDuration > 0 ? rom / (float(repDuration) / 1000.0f) : 0.0f;
      session.romAccumulator += rom;
      session.speedAccumulator += speed;
      session.lastMovementAt = millis();
      session.peakDistance = distanceValue;
      session.minDistance = distanceValue;
      repCompleted = true;
      Serial.printf("Rep %d complete, duration=%lu ms, rom=%.1f cm\n", session.repCount, repDuration, rom);
    } else {
      session.repState = WAIT_FOR_PUSH;
      session.peakDistance = distanceValue;
      session.minDistance = distanceValue;
    }
  }

  sendTelemetry(distanceValue, repCompleted);
}

void endSession(bool completed) {
  if (!session.armed) {
    resetLocalSession();
    return;
  }
  session.armed = false; 

  if (session.tracking && !session.sessionId.isEmpty()) {
    float avgRom = session.repCount > 0 ? session.romAccumulator / session.repCount : 0.0f;
    float avgSpeed = session.repCount > 0 ? session.speedAccumulator / session.repCount : 0.0f;
    unsigned long durationMs = millis() - session.startedAt;
    int finalReps = session.repCount;
    String sid = session.sessionId;

    DynamicJsonDocument doc(512);
    doc["session_id"] = sid;
    doc["total_reps"] = finalReps;
    doc["duration_ms"] = durationMs;
    doc["average_rom"] = avgRom;
    doc["speed_consistency"] = avgSpeed;
    doc["machine_name"] = "Chest Press";
    
    // Reset LOCAL immediately so the next tap doesn't see old reps
    resetLocalSession();
    Serial.println("Session reset locally. Syncing with backend...");

    postJson("/session/end", doc);
    sendThingSpeakUpdate(finalReps, 0, avgRom, avgSpeed, completed ? "session_completed" : "session_stopped");

    Serial.printf("Session ended successfully, reps=%d\n", finalReps);
  } else {
    resetLocalSession();
  }
  
  resetRemoteMachineState();
}

void setup() {
  Serial.begin(115200);
  Serial2.begin(9600, SERIAL_8N1, UART_RX_PIN, UART_TX_PIN);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  digitalWrite(TRIG_PIN, LOW);
  SPI.begin(18, 19, 23, SS_PIN);
  mfrc522.PCD_Init();
  delay(100);

  // Verify RFID reader is responsive
  byte version = mfrc522.PCD_ReadRegister(mfrc522.VersionReg);
  Serial.printf("MFRC522 firmware version: 0x%02X", version);
  if (version == 0x91 || version == 0x92) {
    Serial.println(" (OK)");
  } else if (version == 0x00 || version == 0xFF) {
    Serial.println(" (ERROR: reader not detected, check SPI wiring!)");
  } else {
    Serial.println(" (unknown version)");
  }

  WiFi.mode(WIFI_STA);
  ensureWifi();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("WiFi connected, IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("WiFi connection FAILED");
  }
  Serial.printf("Backend target: %s\n", BACKEND_URL);
  Serial.println("ESP32 Smart Gym node ready");
  Serial.println("UART bridge on RX2=16 TX2=17");
  Serial.println("Ultrasonic on TRIG=32 ECHO=33");
}

void loop() {
  processEntranceUart();
  pollMachineState();

  String uid = readRFID();
  if (uid.length() > 0) {
    if (!session.armed) {
      postMachineTap(uid);
    } else if (uid == session.uid) {
      if (session.tracking) {
        Serial.printf("RFID tapped again by %s\n", session.memberName.length() > 0 ? session.memberName.c_str() : uid.c_str());
        endSession(true);
      } else {
        Serial.println("Same member tapped again before exercise start");
        endSession(false);
      }
    } else {
      Serial.println("Another member card was tapped while the machine is busy.");
      Serial.println("Checking with backend if machine is actually busy...");
      
      DynamicJsonDocument checkDoc(768);
      if (getJson("/machine/current", checkDoc)) {
        const char *backendUid = checkDoc["rfid_uid"] | "";
        if (String(backendUid).length() == 0 || String(backendUid) == "Awaiting Tap...") {
          Serial.println("Backend is actually free! Resetting and allowing new tap.");
          resetLocalSession();
          postMachineTap(uid);
        } else {
          Serial.println("Backend confirms machine is still busy. Reset or finish first.");
        }
      } else {
        Serial.println("Backend unreachable. Cannot verify status.");
      }
    }
  }

  if (!session.tracking) {
    digitalWrite(TRIG_PIN, LOW);
    delay(40);
    return;
  }

  if (millis() - session.lastSampleAt >= SAMPLE_INTERVAL_MS) {
    session.lastSampleAt = millis();
    float distanceValue = sampleDistance();
    if (distanceValue > 0) {
      Serial.printf("Distance: %.1f cm\n", distanceValue);
    }
    countRep(distanceValue);
  }

  if (millis() - session.lastMovementAt >= SESSION_TIMEOUT_MS) {
    Serial.println("Session timeout reached");
    endSession(true);
  }
}
