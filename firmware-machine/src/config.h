// config.h — Smart Gym Machine Controller Configuration
// Update these values to match your local network and backend server.

#ifndef CONFIG_H
#define CONFIG_H

// ──── WiFi ────
const char *WIFI_SSID     = "Zero";
const char *WIFI_PASSWORD = "987654321";

// ──── Backend API ────
// Set this to the IP address of the machine running the FastAPI backend.
// Find it with `ipconfig` (Windows) or `ifconfig` / `ip addr` (Linux/Mac).
const char *BACKEND_URL = "http://172.22.12.52:8080";

// Device authentication key (must match DEVICE_API_KEY in backend/auth/security.py)
const char *DEVICE_KEY = "demo-device-key";

// ──── ThingSpeak (optional cloud logging) ────
const bool USE_THINGSPEAK          = true;
const char *THINGSPEAK_API_KEY     = "J3Y45VJY3AOW1DZ3";
const char *THINGSPEAK_URL         = "http://api.thingspeak.com/update";

// ──── Pin Mapping ────
static const byte SS_PIN      = 5;   // RFID SDA
static const byte RST_PIN     = 27;  // RFID RST
static const int  UART_RX_PIN = 16;  // Entrance UART RX
static const int  UART_TX_PIN = 17;  // Entrance UART TX
static const int  TRIG_PIN    = 32;  // Ultrasonic TRIG
static const int  ECHO_PIN    = 33;  // Ultrasonic ECHO

// ──── Timing ────
const unsigned long SAMPLE_INTERVAL_MS     = 150;
const unsigned long SESSION_TIMEOUT_MS     = 300000; // 5 minutes instead of 15 seconds
const unsigned long ENTRANCE_POLL_MS       = 60;
const unsigned long MACHINE_STATE_POLL_MS  = 1500;

// ──── Ultrasonic Thresholds ────
const float PUSH_THRESHOLD_CM = 67.0f;
const float RETURN_THRESHOLD_CM = 70.0f;
const float MIN_ROM_CM = 4.0f;

#endif // CONFIG_H
