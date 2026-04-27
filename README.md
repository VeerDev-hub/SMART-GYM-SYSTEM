# 🏋️ Smart Gym IoT Intelligence System

A **real-time gym monitoring platform** that integrates RFID access control, ultrasonic rep tracking, AI-powered form analysis (YOLOv8 Pose), and machine-learning fatigue prediction into a unified IoT ecosystem.

---

## 📐 Architecture Overview

```
┌──────────────┐  UART   ┌──────────────────────┐  HTTP   ┌────────────────┐
│  Entrance    │────────►│   Machine Controller  │────────►│  FastAPI       │
│  (Arduino)   │         │   (ESP32)             │         │  Backend       │
│  RFID + LCD  │         │  RFID + Ultrasonic    │         │  + SQLite      │
└──────────────┘         └──────────────────────┘         │  + ML Model    │
                                                           └───────┬────────┘
                                                                   │
                              ┌─────────────────┐                  │
                              │  AI Vision      │──── HTTP ────────┤
                              │  (YOLOv8 Pose)  │                  │
                              │  Camera + CV2   │                  │
                              └─────────────────┘                  │
                                                                   │
                              ┌─────────────────┐                  │
                              │  Web Dashboard  │◄── Polling ──────┘
                              │  (HTML/JS)      │
                              └─────────────────┘
```

---

## 🗂️ Project Structure

```
IoT/
├── backend/                  # FastAPI server, database, ML engine
│   ├── auth/                 # JWT authentication & device key verification
│   ├── models/               # SQLAlchemy ORM entities
│   ├── routes/               # API route handlers
│   ├── ml/                   # Scikit-learn fatigue prediction model
│   ├── main.py               # Application entry point
│   └── requirements.txt
├── Smart-Gym/
│   ├── ai-vision/            # YOLOv8 pose estimation & form analysis
│   ├── web-dashboard/        # Real-time monitoring dashboard (HTML/CSS/JS)
│   └── demo-simulator/       # Hardware simulator for testing without devices
├── firmware-machine/         # ESP32 PlatformIO project (machine controller)
│   └── src/
│       ├── config.h          # ← Edit this before flashing
│       └── main.cpp
├── firmware-entrance/        # Arduino project (entrance gate controller)
│   └── src/main.cpp
├── run.py                    # Unified launcher script
└── README.md                 # ← You are here
```

---

## 🚀 Quick Start (Software Only)

### Prerequisites
- Python 3.10+
- pip

### 1. Install Backend Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2. Launch Everything
```bash
# From the project root:
python run.py
```

This starts:
- **Backend API** at `http://127.0.0.1:8000`
- **Dashboard** at `http://127.0.0.1:3000`

### 3. (Optional) Start AI Vision
```bash
pip install opencv-python ultralytics numpy requests
python run.py --with-vision
```

### 4. Open the Dashboard
Navigate to **http://127.0.0.1:3000** in your browser.

---

## 🔌 Hardware Setup

### Components Required

| Component           | Quantity | Used For                      |
|---------------------|----------|-------------------------------|
| ESP32 DevKit        | 1        | Machine controller + WiFi     |
| Arduino Uno/Nano    | 1        | Entrance gate controller      |
| MFRC522 RFID Reader | 2        | Member identification         |
| HC-SR04 Ultrasonic  | 1        | Rep counting (distance)       |
| 16x2 LCD            | 1        | Entrance display              |
| IR Sensor            | 1        | Gate pass-through detection   |
| Buzzer              | 1        | Audio feedback                |
| Push Button         | 1        | Gate open trigger             |

### Wiring Summary

#### ESP32 (Machine Controller)
| ESP32 Pin | Component      |
|-----------|----------------|
| GPIO 5    | RFID SDA       |
| GPIO 27   | RFID RST       |
| GPIO 16   | Entrance UART RX |
| GPIO 17   | Entrance UART TX |
| GPIO 32   | Ultrasonic TRIG |
| GPIO 33   | Ultrasonic ECHO |

#### Arduino (Entrance Controller)
| Arduino Pin | Component     |
|-------------|---------------|
| Pin 10      | RFID SDA      |
| Pin 9       | RFID RST      |
| Pin 8       | Push Button   |
| A0          | Buzzer        |
| A1          | IR Sensor     |
| Pins 2-7   | LCD (RS,E,D4-D7) |

### Flashing the Firmware

1. **Edit configuration** — open `firmware-machine/src/config.h` and set:
   - `WIFI_SSID` and `WIFI_PASSWORD` to your WiFi network
   - `BACKEND_URL` to the IP of the machine running the backend (find with `ipconfig`)

2. **Flash ESP32** — open `firmware-machine/` in PlatformIO and upload.

3. **Flash Arduino** — open `firmware-entrance/` in Arduino IDE / PlatformIO and upload.

4. **Connect UART** — wire the Arduino TX to ESP32 RX (GPIO 16) and Arduino GND to ESP32 GND.

---

## 📡 API Endpoints Reference

### Authentication
| Method | Endpoint         | Description               |
|--------|------------------|---------------------------|
| POST   | `/auth/login`    | Username/password login   |
| POST   | `/auth/rfid-login` | Login via RFID UID      |
| GET    | `/auth/me`       | Current user info         |

### Machine Integration (from ESP32 / Dashboard)
| Method | Endpoint                 | Description                    |
|--------|--------------------------|--------------------------------|
| POST   | `/machine/tap`           | RFID tap at machine            |
| POST   | `/machine/select-exercise` | Choose exercise to track     |
| POST   | `/machine/reset`         | Reset machine state            |
| GET    | `/machine/current`       | Get current machine state      |

### Session Tracking (from ESP32 ultrasonic)
| Method | Endpoint           | Description                        |
|--------|--------------------|------------------------------------|
| POST   | `/session/start`   | Start a new workout session        |
| POST   | `/session/sample`  | Log a distance/rep sample          |
| POST   | `/session/end`     | End session & trigger ML prediction|

### AI Vision (from camera script)
| Method | Endpoint          | Description                    |
|--------|--------------------|-------------------------------|
| POST   | `/vision/update`   | Push form analysis state      |

### Dashboards
| Method | Endpoint              | Description                  |
|--------|-----------------------|------------------------------|
| GET    | `/dashboard/live`     | Live machine + vision state  |
| GET    | `/user/dashboard`     | Member personal dashboard    |
| GET    | `/admin/dashboard`    | Admin overview               |

---

## 🧠 ML Prediction

After each workout session ends, the backend calculates:

- **Fatigue Level** (Low / Moderate / High) — using a scikit-learn classifier
- **Form Score** (0–100) — composite of ROM, speed consistency, and ROM dropoff
- **Insight** — personalized textual feedback

The model auto-trains on first run using synthetic data and is saved as `fatigue_model.joblib`.

---

## 🧪 Testing Without Hardware

Use the built-in **demo simulator** to test the full flow:

```bash
# Terminal 1 — Start the system
python run.py

# Terminal 2 — Run the simulator
cd Smart-Gym/demo-simulator
python simulator.py
```

Or use the **Dashboard UI** directly:
1. Open `http://127.0.0.1:3000`
2. Type an RFID UID (e.g., `CEAECFBD`) and click **Tap RFID**
3. Select an exercise and click **Start Exercise**

---

## 👥 Demo Accounts

| Name              | Username  | RFID UID   | Plan      | Status   |
|-------------------|-----------|------------|-----------|----------|
| Aarav Sharma      | member1   | 3B7D483C   | Quarterly | Active   |
| Diya Patel        | member2   | 3B5CB33C   | Monthly   | Active   |
| Rohan Mehta       | member3   | 2B40B13C   | Annual    | Active   |
| Kunal Verma       | member4   | 3B15113C   | Monthly   | Inactive |
| Veer Pratap Singh | member5   | CEAECFBD   | Annual    | Active   |
| Nisha Kapoor      | member6   | 53BEA9FA   | Monthly   | Active   |
| Arjun Malhotra    | member7   | 2545FD00   | Quarterly | Active   |

**Admin**: `admin` / `admin123`

---

## 📄 License

This project was built as an IoT academic / portfolio project.
