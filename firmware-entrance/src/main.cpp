#include <Arduino.h>
#include <LiquidCrystal.h>
#include <MFRC522.h>
#include <SPI.h>

static const byte SS_PIN = 10;
static const byte RST_PIN = 9;
static const int BUTTON_PIN = 8;
static const int BUZZER_PIN = A0;
static const int IR_SENSOR_PIN = A1;
static const unsigned long GATE_PROMPT_DELAY_MS = 1200;
static const unsigned long GATE_PASS_ARM_MS = 1500;

LiquidCrystal lcd(2, 3, 4, 5, 6, 7);
MFRC522 mfrc522(SS_PIN, RST_PIN);

struct DemoMember {
  const char *uid;
  const char *name;
  bool active;
  int memberId;
};

DemoMember demoMembers[] = {
    {"3B7D483C", "Aarav", true, 1},
    {"3B5CB33C", "Diya", true, 2},
    {"2B40B13C", "Rohan", true, 3},
    {"3B15113C", "Kunal", false, 4},
    {"CEAECFBD", "Veer", true, 5},
    {"53BEA9FA", "Nisha", true, 6},
    {"2545FD00", "Arjun", true, 7},
};

const unsigned long LCD_MESSAGE_MS = 10000;
bool gatePromptPending = false;
unsigned long gatePromptAt = 0;
unsigned long statusShownAt = 0;
bool showingStatus = false;
bool accessGranted = false;
bool gatePassLogged = false;
bool gateOpened = false;
unsigned long gateOpenedAt = 0;
String activeUid;
String activeName;
int activeMemberId = -1;

String uidToString(MFRC522::Uid *uid) {
  String hex = "";
  for (byte i = 0; i < uid->size; i++) {
    if (uid->uidByte[i] < 0x10) {
      hex += "0";
    }
    hex += String(uid->uidByte[i], HEX);
  }
  hex.toUpperCase();
  return hex;
}

void showIdleScreen() {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Tap RFID Card");
  lcd.setCursor(0, 1);
  lcd.print("Staff: Open Gate");
  showingStatus = false;
}

String readRFID() {
  if (!mfrc522.PICC_IsNewCardPresent() || !mfrc522.PICC_ReadCardSerial()) {
    return "";
  }

  String uid = uidToString(&mfrc522.uid);
  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();
  return uid;
}

bool validateMember(const String &uid, DemoMember &matchedMember) {
  for (DemoMember &member : demoMembers) {
    if (uid.equalsIgnoreCase(member.uid)) {
      matchedMember = member;
      return member.active;
    }
  }
  matchedMember = {"UNKNOWN", "Unknown", false, -1};
  return false;
}

void displayMemberInfo(const DemoMember &member, bool valid) {
  lcd.clear();
  lcd.setCursor(0, 0);
  if (valid) {
    lcd.print("Welcome");
    lcd.setCursor(0, 1);
    lcd.print(member.name);
  } else {
    lcd.print("Access Denied");
    lcd.setCursor(0, 1);
    lcd.print("Card Not Valid");
  }

  statusShownAt = millis();
  showingStatus = true;
}

void displayGateOpenPrompt() {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Authorized");
  lcd.setCursor(0, 1);
  lcd.print("Press Btn Gate");
  statusShownAt = millis();
  showingStatus = true;
}

void displayEntryComplete() {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Entry Complete");
  lcd.setCursor(0, 1);
  lcd.print(activeName);
  statusShownAt = millis();
  showingStatus = true;
}

void buzzError() {
  tone(BUZZER_PIN, 850, 180);
  delay(220);
  tone(BUZZER_PIN, 700, 220);
}

void buzzSuccess() {
  tone(BUZZER_PIN, 1800, 100);
  delay(130);
  tone(BUZZER_PIN, 2200, 120);
}

void sendEntryLog(const DemoMember &member, const String &uid, bool granted, const char *reason) {
  Serial.print("{\"event\":\"entry_log\",\"member_id\":");
  Serial.print(member.memberId);
  Serial.print(",\"member_name\":\"");
  Serial.print(member.name);
  Serial.print("\",\"rfid_uid\":\"");
  Serial.print(uid);
  Serial.print("\",\"granted\":");
  Serial.print(granted ? "true" : "false");
  Serial.print(",\"ir_state\":");
  Serial.print(analogRead(IR_SENSOR_PIN));
  Serial.print(",\"reason\":\"");
  Serial.print(reason);
  Serial.println("\"}");
}

void sendGateEvent(const char *eventName) {
  if (activeMemberId < 0) {
    return;
  }

  Serial.print("{\"event\":\"");
  Serial.print(eventName);
  Serial.print("\",\"member_id\":");
  Serial.print(activeMemberId);
  Serial.print(",\"member_name\":\"");
  Serial.print(activeName);
  Serial.print("\",\"rfid_uid\":\"");
  Serial.print(activeUid);
  Serial.println("\"}");
}

void processButtonReset() {
  static bool lastButtonState = HIGH;
  bool current = digitalRead(BUTTON_PIN);
  if (lastButtonState == HIGH && current == LOW) {
    if (accessGranted && !gateOpened) {
      gateOpened = true;
      gatePromptPending = false;
      gateOpenedAt = millis();
      buzzSuccess();
      sendGateEvent("gate_opened");
      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print("Gate Open");
      lcd.setCursor(0, 1);
      lcd.print("Please Enter");
      statusShownAt = millis();
      showingStatus = true;
    } else {
      accessGranted = false;
      gatePassLogged = false;
      gateOpened = false;
      gatePromptPending = false;
      activeUid = "";
      activeName = "";
      activeMemberId = -1;
      showIdleScreen();
    }
  }
  lastButtonState = current;
}

void processInfraredExit() {
  if (!accessGranted || !gateOpened) {
    return;
  }

  if (millis() - gateOpenedAt < GATE_PASS_ARM_MS) {
    return;
  }

  int sensorValue = analogRead(IR_SENSOR_PIN);
  if (!gatePassLogged && sensorValue < 450) {
    sendGateEvent("entry_completed");
    gatePassLogged = true;
    accessGranted = false;
    gateOpened = false;
    displayEntryComplete();
  }
}

void processGatePrompt() {
  if (!gatePromptPending || !accessGranted || gateOpened) {
    return;
  }

  if (millis() - gatePromptAt >= GATE_PROMPT_DELAY_MS) {
    gatePromptPending = false;
    displayGateOpenPrompt();
  }
}

void setup() {
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(IR_SENSOR_PIN, INPUT);

  Serial.begin(9600);
  SPI.begin();
  mfrc522.PCD_Init();
  lcd.begin(16, 2);
  showIdleScreen();
}

void loop() {
  processButtonReset();
  processInfraredExit();
  processGatePrompt();

  if (showingStatus && millis() - statusShownAt >= LCD_MESSAGE_MS) {
    showIdleScreen();
  }

  String uid = readRFID();
  if (uid.length() == 0) {
    return;
  }

  DemoMember member = {"UNKNOWN", "Unknown", false, -1};
  bool valid = validateMember(uid, member);
  displayMemberInfo(member, valid);

  if (valid) {
    accessGranted = true;
    gatePassLogged = false;
    gateOpened = false;
    gateOpenedAt = 0;
    gatePromptPending = true;
    gatePromptAt = millis();
    activeUid = uid;
    activeName = member.name;
    activeMemberId = member.memberId;
    buzzSuccess();
    sendEntryLog(member, uid, true, "membership_active");
  } else {
    accessGranted = false;
    gateOpened = false;
    gateOpenedAt = 0;
    gatePromptPending = false;
    buzzError();
    sendEntryLog(member, uid, false, "membership_invalid");
  }
}
