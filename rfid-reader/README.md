# RFID Card Reader Utility

Use this small PlatformIO project to scan all RFID cards first and note down their UIDs before assigning them to gym members.

## Folder

- `rfid-reader/`

## Hardware

This utility uses the same RC522 wiring as your entrance Arduino setup:

- `SS_PIN = 10`
- `RST_PIN = 9`
- `MOSI = 11`
- `MISO = 12`
- `SCK = 13`

## How to use

1. Open the `rfid-reader` folder in PlatformIO.
2. Upload the sketch to the Arduino Uno.
3. Open the serial monitor at `115200`.
4. Tap each RFID card on the RC522 reader.
5. Copy the printed UID values and keep them for member registration.

## Example output

```text
Card detected
UID: DEADBEEF
UID bytes: 4
------------------------------
```

## Where to use the UID later

You can use the scanned UID:

- in the backend when creating members through `POST /members`
- in demo data like `DEADBEEF`
- in firmware test lists for validation
