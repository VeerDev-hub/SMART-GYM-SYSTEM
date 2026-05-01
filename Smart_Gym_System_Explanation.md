# Smart Gym IoT System: Comprehensive Code & Workflow Explanation

This document provides a detailed breakdown of the Smart Gym IoT system, designed specifically to help you present the project to your faculty. It covers the overall architecture, step-by-step workflows, and a detailed explanation of the core code in each component.

---

## 1. System Architecture Overview

The system is a fully integrated IoT solution consisting of four main components that communicate with each other to provide a seamless gym experience.

1.  **Entrance Controller (Arduino Uno):** Manages the physical entrance. It uses an RFID reader to identify members, an LCD to display status, a buzzer for audio feedback, a button for manual override, and an IR sensor to detect when a person passes through the gate.
2.  **Machine Node (ESP32):** Attached to gym equipment (e.g., Chest Press). It uses an Ultrasonic sensor to track the Range of Motion (ROM) and count reps. It also has its own RFID reader for machine login. It connects to the local WiFi to talk to the backend. *Note: It also acts as a bridge for the Entrance Controller, receiving UART messages from the Arduino and forwarding them to the backend via WiFi.*
3.  **FastAPI Backend (Python):** The central nervous system. It provides REST APIs for hardware and frontend. It manages the SQLite database (members, logs, sessions), handles business logic, synchronizes live state between hardware and the dashboard, and integrates a machine learning module for form and fatigue analysis.
4.  **Web Dashboard (HTML/JS/CSS):** A real-time interface for the user working out. It polls the backend continuously to display live reps, ROM, timer, and AI coach feedback.

---

## 2. Component 1: Entrance Controller (`firmware-entrance/src/main.cpp`)

This code runs on an Arduino and is responsible for physical access control.

### Key Hardware Interfaces:
*   `MFRC522`: Reads RFID cards (SPI).
*   `LiquidCrystal`: Displays text.
*   `BUTTON_PIN`, `BUZZER_PIN`, `IR_SENSOR_PIN`: Physical inputs/outputs.

### Core Logic & Functions:
*   **Demo Data (`demoMembers`):** Instead of fetching from a database (which Arduino can't do easily without WiFi), it uses a hardcoded struct array of valid UIDs and their statuses.
*   **`loop()`**: The main infinite loop continuously checks for three things: Button presses, IR sensor triggers (someone walked through), and new RFID cards.
*   **`readRFID()`**: Scans for a card. If found, returns its UID as a Hex String.
*   **`validateMember(uid)`**: Loops through `demoMembers` to see if the tapped UID exists and has `active == true`.
*   **Access Granted Workflow:**
    1.  If valid, `accessGranted` becomes `true`.
    2.  `buzzSuccess()` plays a happy tone.
    3.  `sendEntryLog(...)` formats a JSON string and prints it to `Serial`. *This is physically wired to the ESP32's `Serial2` (UART).*
    4.  It waits for the admin to press the `BUTTON_PIN` (simulating opening a physical gate) -> `processButtonReset()`.
    5.  Once the button is pressed, `gateOpened` becomes `true`, and it waits for the `IR_SENSOR_PIN` to drop below 450 (meaning a person blocked the IR beam while walking through) -> `processInfraredExit()`.
    6.  Sends `entry_completed` JSON over Serial.

**What to tell the faculty:** *"The Arduino handles the physical layer of the entrance. It validates the RFID locally for speed, drives the LCD and buzzer, and sends JSON event packets via Serial TX to the ESP32, which acts as a WiFi bridge to our cloud."*

---

## 3. Component 2: Machine Node (`firmware-machine/src/main.cpp`)

This ESP32 handles the workout tracking and acts as the bridge for the entrance.

### Key Hardware Interfaces:
*   `Ultrasonic Sensor (TRIG/ECHO)`: Measures distance in cm.
*   `MFRC522`: Machine's RFID reader (SPI).
*   `Serial2`: Hardware UART connected to the Entrance Arduino.
*   `WiFi & HTTPClient`: For backend and ThingSpeak communication.

### Core Logic & Functions:
*   **`processEntranceUart()`**: Reads the `Serial2` buffer. If it receives a full JSON string from the Arduino (like an entry log), it parses it and uses `postJson()` to send it via WiFi to the FastAPI backend (`/entry-log`).
*   **Machine Login (`postMachineTap`)**: When a user taps their RFID on the machine, it POSTs to `/machine/tap`. The backend registers the user at this machine.
*   **State Polling (`pollMachineState`)**: The ESP32 constantly GETs `/machine/current`. It is looking for the dashboard to signal that an exercise has been selected. If the backend says `exercise_status == "tracking"`, the ESP32 calls `beginTracking()`.
*   **Tracking (`sampleDistance` & `countRep`)**:
    1.  `sampleDistance()` pings the ultrasonic sensor and returns distance in cm.
    2.  `countRep(distance)` runs state machine logic:
        *   `WAIT_FOR_PUSH`: If distance is `<= PUSH_THRESHOLD_CM`, switch to `WAIT_FOR_RETURN`.
        *   `WAIT_FOR_RETURN`: If distance returns to `>= RETURN_THRESHOLD_CM`, a rep is counted!
    3.  Calculates ROM (Peak Distance - Min Distance) and Speed.
    4.  Calls `sendTelemetry()` which POSTs the live distance and rep count to `/session/sample`.
*   **`endSession()`**: Triggered by timeout or tapping the card again. Posts final stats to `/session/end` and resets local state.

**What to tell the faculty:** *"The ESP32 is the IoT edge node. It polls the ultrasonic sensor to track mechanical movement, converting distance into reps and range of motion. It doesn't decide when to start; it waits for the backend to signal 'tracking' state, ensuring the hardware is perfectly synchronized with the user's web dashboard."*

---

## 4. Component 3: Backend API (`backend/routes/activity_routes.py` & `main.py`)

Built with FastAPI, this handles all data flow and state management.

### Key Concepts:
*   **Database (`models.py`)**: Uses SQLAlchemy to define tables (`User`, `Member`, `WorkoutSession`, `RepSample`, `LiveMachineState`).
*   **`LiveMachineState`**: A single-row database table that acts as a clipboard between the hardware and the frontend. Hardware writes reps to it, frontend reads reps from it. Frontend writes exercise selection to it, hardware reads exercise selection from it.

### Core Endpoints:
*   **`POST /entry-log`**: Receives JSON from ESP32 (originating from Arduino). Saves the entry record to the database for history.
*   **`POST /machine/tap`** *(in integration_routes.py)*: Sets the `LiveMachineState` to `awaiting_exercise` and associates the RFID with the machine.
*   **`POST /session/start`**: Called by the **Dashboard**. Generates a unique `session_code`. Updates `LiveMachineState` to `tracking`. (This is what the ESP32 polls for to start counting).
*   **`POST /session/sample`**: Called by the **ESP32** continuously during a workout. Updates the database with the raw distance data and updates the `LiveMachineState.current_distance` so the Dashboard UI ROM bar updates live.
*   **`POST /session/end`**: Ends the session, calculates final averages, and calls `predict_session_features()` to generate AI feedback (fatigue, form score) which is saved to the database.
*   **`GET /dashboard/live`** *(in dashboard_routes.py)*: Returns the entire `LiveMachineState` object.

**What to tell the faculty:** *"The backend is stateless REST, except for the `LiveMachineState` table which acts as a real-time message broker. This architecture decouples the hardware from the frontend, meaning the dashboard and the ESP32 never talk directly, they only talk through the backend, ensuring data integrity and security."*

---

## 5. Component 4: Web Dashboard (`Smart-Gym/web-dashboard/script.js`)

The front-end user interface.

### Core Logic & Functions:
*   **Polling Loop (`startPolling` & `updateDashboard`)**: Every 250 milliseconds (`CONFIG.POLL_INTERVAL`), it calls `apiFetch('/dashboard/live')`.
*   **UI Synchronization**: Based on the response, it updates:
    *   `updateRepHero()`: The giant rep counter.
    *   `updateROMTracker()`: Fills the CSS progress bar based on `current.current_distance`.
    *   `updateAICoach()`: Displays the form analysis and fatigue warnings.
*   **`handleStartExercise()`**: When the user clicks "Start", it initiates a 3-second visual countdown. Once it hits zero, it makes the API call to `/machine/select-exercise`, which signals the backend, which in turn signals the ESP32 to start tracking.

**What to tell the faculty:** *"The frontend relies on a high-frequency polling architecture to achieve near real-time telemetry. By fetching the state every 250ms, we provide instantaneous visual feedback to the user on their rep count and form without needing complex WebSockets."*

---

## End-to-End Workflow Summary (The "Elevator Pitch" for your presentation)

1.  **Entry:** Member taps card at the door. Arduino validates, opens the gate, and tells the ESP32 via UART. ESP32 tells the Cloud.
2.  **Machine Login:** Member goes to the Chest Press and taps their card on the ESP32. ESP32 tells the Cloud "Member X is here".
3.  **UI Sync:** The Web Dashboard sees Member X is there and asks them what exercise they want to do.
4.  **Start:** Member selects "Chest Press" and clicks Start. The Dashboard tells the Cloud. The ESP32, which is constantly asking the cloud "Should I start?", sees the signal and turns on the ultrasonic sensor.
5.  **Tracking:** As the member pushes the bar, the ultrasonic sensor tracks the distance. Every time a push and return completes, it registers a Rep. It sends this data to the Cloud multiple times a second.
6.  **Live Feedback:** The Dashboard pulls this data from the Cloud and animates the screen, showing live reps, a moving Range of Motion bar, and AI feedback.
7.  **Finish:** Member stops or taps card again. ESP32 tells Cloud it's done. Cloud runs an ML algorithm to score their form and logs the workout in their history. Dashboard resets for the next person.
