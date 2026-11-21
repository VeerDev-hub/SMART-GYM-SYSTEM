// secrets.example.h — template for secrets.h
//
// Copy this file to secrets.h (same folder) and fill in your values:
//   cp secrets.example.h secrets.h
// secrets.h is ignored by git, so your credentials never get committed.

#ifndef SECRETS_H
#define SECRETS_H

// ──── WiFi ────
#define SECRET_WIFI_SSID      "your-wifi-ssid"
#define SECRET_WIFI_PASSWORD  "your-wifi-password"

// ──── Device key (must match DEVICE_API_KEY in backend/auth/security.py) ────
#define SECRET_DEVICE_KEY     "demo-device-key"

// ──── ThingSpeak write keys (leave as-is if USE_THINGSPEAK is false) ────
#define SECRET_THINGSPEAK_KEY_ENTRANCE "YOUR_ENTRANCE_WRITE_KEY"
#define SECRET_THINGSPEAK_KEY_MACHINE  "YOUR_MACHINE_WRITE_KEY"

#endif // SECRETS_H
