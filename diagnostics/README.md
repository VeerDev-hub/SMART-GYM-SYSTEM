# Board Diagnostics

These are separate test projects so your main firmware stays untouched.

## Folders

- `diagnostics-arduino/`
- `diagnostics-esp32/`

## What the tests check

### Arduino diagnostics

- LCD works
- buzzer works
- button works
- IR sensor works
- RC522 RFID reads card UIDs
- UART link to ESP32 works and shows ACK replies on the LCD

### ESP32 diagnostics

- UART link to Arduino works
- RC522 RFID reads card UIDs
- ultrasonic sensor returns distance values
- prints a rolling pass/fail summary for UART, RFID, and ultrasonic

## Recommended UART test wiring

Use Arduino hardware UART pins `0/1` for this version of the diagnostics.

### Arduino Uno

- `0` = UART RX
- `1` = UART TX

### ESP32 DEVKIT V1

- `GPIO16` = UART RX2
- `GPIO17` = UART TX2

### UART connections

- Arduino `GND` -> ESP32 `GND`
- Arduino `1 (TX)` -> ESP32 `GPIO16 (RX2)` through a voltage divider
- Arduino `0 (RX)` <- ESP32 `GPIO17 (TX2)`

Important:
- disconnect the UART wires from Arduino pins `0/1` before uploading to the Arduino Uno
- reconnect them after upload for runtime testing
- while `0/1` are connected to ESP32, the Arduino USB Serial Monitor is not reliable

## Voltage divider for Arduino TX -> ESP32 RX

- Arduino `1` -> `1k resistor` -> junction
- junction -> ESP32 `GPIO16`
- junction -> `2k resistor` -> `GND`

## Arduino fixed entrance wiring

- LCD: `2, 3, 4, 5, 6, 7`
- RFID RC522: `SS=10`, `RST=9`, SPI on `11,12,13`
- Button: `8`
- Buzzer: `A0`
- IR sensor: `A1`

## ESP32 sensor wiring for diagnostics

### RC522

- `SDA/SS` -> `GPIO5`
- `RST` -> `GPIO27`
- `MOSI` -> `GPIO23`
- `MISO` -> `GPIO19`
- `SCK` -> `GPIO18`
- `3.3V` -> `3V3`
- `GND` -> `GND`

### Ultrasonic sensor

- `TRIG` -> `GPIO32`
- `ECHO` -> `GPIO33`
- `VCC` -> `VIN`
- `GND` -> `GND`

Important:
- if your ultrasonic module outputs `5V` on `ECHO`, add a voltage divider before ESP32 `GPIO33`

## Expected test behavior

### Arduino

- LCD rotates through pass/fail status for button, IR, RFID, and UART
- buzzer beeps at startup
- button press sends `BTN:PRESSED`
- IR trigger sends `IR:TRIGGERED:<value>`
- RFID scan sends `RFID:<uid>`
- every few seconds Arduino sends `HELLO_FROM_ARDUINO`
- ESP32 replies appear on the LCD as `UART ACK`, `ESP32 Online`, or `ESP32 Ultra`

### ESP32

- prints ultrasonic distance or `no echo`
- echoes UART packets back as `ACK:<message>`
- every few seconds sends `HELLO_FROM_ESP32`
- RFID scan sends `ESP32_RFID:<uid>`
- prints a 5-second summary showing `UART RX`, `UART TX`, `UART LINK`, `RFID`, and `ULTRASONIC`
- prints structured logs in this format:

```text
[12540 ms] ESP32 | ULTRASONIC | 18.4cm
[15102 ms] UART_RX | RAW | ARDUINO|BUTTON|PRESSED
[17750 ms] ESP32 | RFID | CEAECFBD
```

## How to test

1. Upload `diagnostics-arduino` to the Arduino Uno.
2. Upload `diagnostics-esp32` to the ESP32 DEVKIT V1.
3. Connect the UART wires and shared ground.
4. Open the ESP32 serial monitor.
5. Confirm the Arduino LCD shows `ESP32 Online` or `UART ACK`, and the ESP32 monitor logs `UART RX <- ...`.
6. Test button, IR, RFID, and ultrasonic one by one until both boards show all checks as `OK`.

## Logging before full integration

Use the ESP32 Serial Monitor as your central test log before integrating backend, frontend, YOLO, ML, and cloud.

Recommended fields to track manually from the ESP32 monitor:

- time
- source board
- event type
- value

Example events you can record:

- button press timing
- IR trigger timing
- Arduino RFID reads
- ESP32 RFID reads
- ultrasonic distances
- UART heartbeat gaps
- PASS / FAIL milestones
