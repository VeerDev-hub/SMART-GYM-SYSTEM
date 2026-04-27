#include <Arduino.h>
#include <MFRC522.h>
#include <SPI.h>

static const byte SS_PIN = 10;
static const byte RST_PIN = 9;

MFRC522 mfrc522(SS_PIN, RST_PIN);

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

void printCardDetails(const MFRC522::Uid &uid) {
  String uidString = uidToString(uid);

  Serial.println("Card detected");
  Serial.print("UID: ");
  Serial.println(uidString);
  Serial.print("UID bytes: ");
  Serial.println(uid.size);
  Serial.println("------------------------------");
}

void setup() {
  Serial.begin(115200);
  SPI.begin();
  mfrc522.PCD_Init();

  Serial.println();
  Serial.println("RFID Reader Ready");
  Serial.println("Tap cards on the RC522 reader to capture UIDs");
  Serial.println("Wiring:");
  Serial.println("SDA/SS -> D10");
  Serial.println("RST    -> D9");
  Serial.println("MOSI   -> D11");
  Serial.println("MISO   -> D12");
  Serial.println("SCK    -> D13");
  Serial.println("------------------------------");
}

void loop() {
  if (!mfrc522.PICC_IsNewCardPresent()) {
    delay(30);
    return;
  }

  if (!mfrc522.PICC_ReadCardSerial()) {
    delay(30);
    return;
  }

  printCardDetails(mfrc522.uid);
  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();

  delay(800);
}

