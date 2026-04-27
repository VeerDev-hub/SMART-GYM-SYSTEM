# Smart Gym Membership Management using RFID

This monorepo contains a demo-ready college IoT project that combines RFID-based gym access control, chest press rep tracking, a FastAPI cloud backend, a React dashboard, and simple ML-based workout quality insights.

## Project Layout

- `firmware-entrance/`: PlatformIO project for the Arduino Uno entrance station
- `firmware-machine/`: PlatformIO project for the ESP32 chest press node
- `backend/`: FastAPI API, SQLite storage, authentication, and ML inference
- `frontend/`: React dashboard for members and staff
- `docs/sample-payloads.json`: Sample firmware payloads

## Entrance Station Hardware

The Arduino Uno firmware keeps the exact fixed wiring requested:

- LCD: `LiquidCrystal lcd(2, 3, 4, 5, 6, 7)`
- RFID RC522: `SS=10`, `RST=9`
- Button: `8`
- Buzzer: `A0`
- IR sensor: `A1`

Main firmware functions:

- `readRFID()`
- `validateMember()`
- `displayMemberInfo()`
- `buzzError()`
- `sendEntryLog()`

The sketch performs local demo validation against a small RFID list and sends JSON-style serial logs that can be bridged to Wi-Fi by an ESP32 or PC serial listener.

## Machine Node Hardware

The ESP32 node:

- reads RFID to identify the athlete
- registers the tap with `/machine/tap`
- waits for the selected exercise and active session from the cloud with `/machine/current`
- samples an ultrasonic distance sensor on `GPIO32/GPIO33`
- counts reps using threshold + hysteresis logic
- streams samples to `/session/sample`
- ends and summarizes a session through `/session/end`

Rep counting is deliberately sensor-logic based, not ML-based.

### ThingSpeak-ready preparation

The ESP32 firmware is also prepared for optional ThingSpeak cloud logging:

- set `USE_THINGSPEAK = true` in `firmware-machine/src/main.cpp`
- add your `THINGSPEAK_API_KEY`
- the node can mirror session start, rep-complete events, and session summaries to ThingSpeak fields

Suggested ThingSpeak field mapping:

- `field1`: rep count
- `field2`: raw distance or sample count
- `field3`: range of motion
- `field4`: speed consistency or average speed

## Backend

The backend uses:

- FastAPI
- SQLite with SQLAlchemy ORM
- JWT login for user/admin accounts
- hashed passwords with `passlib`
- device-key header for firmware endpoints
- Random Forest model for fatigue/form insight inference

### Database entities

- `users`
- `members`
- `rfid_cards`
- `entry_logs`
- `workout_sessions`
- `rep_samples`
- `predictions`
- `admin_users`

### Seeded demo accounts

- Member: `member1 / member123`
- Member: `member2 / member223`
- Member: `member3 / member323`
- Member: `member4 / member423`
- Admin: `admin / admin123`
- Demo RFID UIDs:
  - `3B7D483C` -> Aarav Sharma
  - `3B5CB33C` -> Diya Patel
  - `2B40B13C` -> Rohan Mehta
  - `3B15113C` -> Kunal Verma (`inactive`, should be denied)
  - `CEAECFBD` -> Veer Pratap Singh
  - `53BEA9FA` -> Nisha Kapoor
  - `2545FD00` -> Arjun Malhotra

### Run backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload
```

The first startup creates `gym_iot.db`, seeds demo users, and auto-generates the ML model file if it is missing.

## Frontend

The React dashboard provides:

- login/logout
- member dashboard with membership details, visits, session history, and charts
- admin dashboard with members, access logs, active sessions, and equipment usage

### Run frontend

```bash
cd frontend
npm install
npm run dev
```

The UI expects the backend at `http://localhost:8000`.

## Firmware-to-Backend Flow

1. Member taps RFID at entrance station.
2. Arduino validates locally, shows status on the LCD, buzzes if invalid, and emits entry JSON logs.
3. Serial bridge or ESP32 forwards the log to `POST /entry-log` with `x-device-key: demo-device-key`.
4. Member taps RFID on the chest press node.
5. ESP32 calls `POST /machine/tap`, and the web dashboard auto-signs in that member using the RFID UID.
6. Staff or the athlete chooses the exercise on the dashboard, which creates the live session through `POST /machine/select-exercise`.
7. ESP32 polls `GET /machine/current` until the exercise is armed, then starts ultrasonic rep tracking.
8. Rep samples are posted to `POST /session/sample`.
9. Session summary is posted to `POST /session/end`.
10. Backend stores all records and runs ML inference for fatigue/form insight.
11. Dashboards read `GET /user/dashboard`, `GET /admin/dashboard`, `GET /sessions/{userId}`, and `GET /dashboard/live`.

## API Summary

- `POST /auth/login`
- `POST /auth/logout`
- `GET /auth/me`
- `POST /members`
- `GET /members/{id}`
- `POST /entry-log`
- `POST /auth/rfid-login`
- `POST /machine/tap`
- `GET /machine/current`
- `POST /machine/select-exercise`
- `POST /machine/reset`
- `POST /session/start`
- `POST /session/sample`
- `POST /session/end`
- `GET /sessions/{userId}`
- `POST /predict`
- `GET /admin/dashboard`
- `GET /user/dashboard`

## Demo Notes

- Update Wi-Fi credentials and backend IP in `firmware-machine/src/main.cpp`.
- For a polished live demo, run a tiny serial bridge on a laptop to convert Arduino Uno serial output into backend `POST /entry-log` requests.
- The backend is structured so SQLite can later be replaced with PostgreSQL/MySQL by changing the SQLAlchemy connection string.
