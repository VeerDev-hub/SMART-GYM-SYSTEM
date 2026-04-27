import cv2
import json
import time
import requests
import numpy as np
import threading
from collections import deque
from ultralytics import YOLO

# --- Configuration ---
MODEL_PATH = "yolo26n-pose.pt"
BACKEND_URL = "http://127.0.0.1:8080/vision/update"
CONTEXT_URL = "http://127.0.0.1:8080/dashboard/live"
LOCAL_STATE_PATH = "../web-dashboard/live_state.json"

MISTAKE_TIME_THRESHOLD = 0.4 
COOLDOWN_TIME = 0.15
ASYMMETRY_LIMIT = 50
PREDICT_IMGSZ = 256
CAMERA_WIDTH = 424
CAMERA_HEIGHT = 240
PROCESS_EVERY_N_FRAMES = 4
REP_DOWN_THRESHOLD = 0.16
REP_UP_THRESHOLD = 0.14
MIN_REP_ROM_RATIO = 0.28
REP_CONFIRM_FRAMES = 3
REP_COOLDOWN_SECONDS = 0.7

model = YOLO(MODEL_PATH)
http_session = requests.Session()
baseline_torso = None
mistake_timers = {"ID 1": 0, "ID 2": 0}
last_alert_time = 0
current_direction = "NONE"
last_wrist_y = None
time_window = 0.25 
y_history = deque()
last_sent_state = None
rep_count = 0
rep_phase = "IDLE"
rep_top_y = None
rep_bottom_y = None
wrist_smooth_y = None
down_confirm_frames = 0
up_confirm_frames = 0
last_rep_timestamp = 0.0
last_backend_ok = False
backend_warned = False
post_thread = None
selected_exercise = "unselected"
exercise_status = "awaiting_rfid"
last_context_fetch = 0.0
last_session_id = None

KEYPOINT_INDEXES = [5, 6, 7, 8, 9, 10, 11, 12]
SKELETON_EDGES = [(5, 7), (7, 9), (6, 8), (8, 10), (5, 6), (5, 11), (6, 12), (11, 12)]
MISTAKE_LABELS = {
    "ID 1": "Asymmetry",
    "ID 2": "Posture Alert",
    "ID 3": "Half Rep",
    "ID 4": "Weight Jerking",
    "ID 5": "Wrong Exercise",
}
last_debug_print = 0.0

def get_angle(hip, shoulder, elbow):
    v_torso = np.array([hip[0] - shoulder[0], hip[1] - shoulder[1]])
    v_arm = np.array([elbow[0] - shoulder[0], elbow[1] - shoulder[1]])
    mag_torso = np.linalg.norm(v_torso)
    mag_arm = np.linalg.norm(v_arm)
    if mag_torso == 0 or mag_arm == 0: return 0
    cos_angle = np.dot(v_torso, v_arm) / (mag_torso * mag_arm)
    return np.degrees(np.arccos(np.clip(cos_angle, -1.0, 1.0)))

def detect_asymmetry(kp, now):
    diff = abs(kp[9][1] - kp[10][1])
    if diff > ASYMMETRY_LIMIT:
        if mistake_timers["ID 1"] == 0: mistake_timers["ID 1"] = now
        if now - mistake_timers["ID 1"] > MISTAKE_TIME_THRESHOLD: return "ID 1"
    else: mistake_timers["ID 1"] = 0
    return None

def detect_wrong_exercise(kp, now):
    left_shoulder_y = kp[5][1]
    right_shoulder_y = kp[6][1]
    left_wrist_y = kp[9][1]
    right_wrist_y = kp[10][1]

    left_active = abs(left_wrist_y - left_shoulder_y) > 35
    right_active = abs(right_wrist_y - right_shoulder_y) > 35

    if left_active ^ right_active:
        if mistake_timers.get("ID 5", 0) == 0:
            mistake_timers["ID 5"] = now
        if now - mistake_timers["ID 5"] > MISTAKE_TIME_THRESHOLD:
            return "ID 5"
    else:
        mistake_timers["ID 5"] = 0
    return None

def detect_posture_issue(kp, now):
    global baseline_torso
    s_y = (kp[5][1] + kp[6][1]) / 2
    h_y = (kp[11][1] + kp[12][1]) / 2
    current_torso = abs(s_y - h_y)
    if baseline_torso is None or baseline_torso < 10:
        baseline_torso = current_torso
        return None
    if current_torso < (baseline_torso * 0.75):
        if mistake_timers["ID 2"] == 0: mistake_timers["ID 2"] = now
        if now - mistake_timers["ID 2"] > MISTAKE_TIME_THRESHOLD: return "ID 2"
    else: mistake_timers["ID 2"] = 0
    return None

def detect_half_rep_angle(kp):
    global current_direction, last_wrist_y
    mid_shoulder = [(kp[5][0] + kp[6][0])/2, (kp[5][1] + kp[6][1])/2]
    mid_hip = [(kp[11][0] + kp[12][0])/2, (kp[11][1] + kp[12][1])/2]
    mid_elbow = [(kp[7][0] + kp[8][0])/2, (kp[7][1] + kp[8][1])/2]
    wrist_y = (kp[9][1] + kp[10][1])/2
    if last_wrist_y is None:
        last_wrist_y = wrist_y
        return None
    dy = wrist_y - last_wrist_y
    new_direction = current_direction
    if dy > 3: new_direction = "DOWN"
    elif dy < -3: new_direction = "UP"
    result = None
    if new_direction != current_direction and current_direction != "NONE":
        angle = get_angle(mid_hip, mid_shoulder, mid_elbow)
        if 65 <= angle <= 120: result = "ID 3"
    current_direction = new_direction
    last_wrist_y = wrist_y
    return result

def detect_jerk_normalized(kp, now):
    wrist_y = (kp[9][1] + kp[10][1]) / 2
    s_y = (kp[5][1] + kp[6][1]) / 2
    h_y = (kp[11][1] + kp[12][1]) / 2
    torso_length = abs(s_y - h_y)
    y_history.append((now, wrist_y))
    while y_history and now - y_history[0][0] > time_window: y_history.popleft()
    if len(y_history) < 2 or torso_length == 0: return None
    y_vals = [y for t, y in y_history]
    if ((max(y_vals) - min(y_vals)) / torso_length) > 0.60: return "ID 4"
    return None

def draw_pose_overlay(frame, kp):
    for a, b in SKELETON_EDGES:
        ax, ay = int(kp[a][0]), int(kp[a][1])
        bx, by = int(kp[b][0]), int(kp[b][1])
        if ay > 0 and by > 0:
            cv2.line(frame, (ax, ay), (bx, by), (0, 220, 255), 2)

    for idx in KEYPOINT_INDEXES:
        x, y = int(kp[idx][0]), int(kp[idx][1])
        if y > 0:
            cv2.circle(frame, (x, y), 4, (0, 255, 0), -1)


def humanize_mistakes(mistakes):
    if not mistakes:
        return ["Perfect Form"]
    return [MISTAKE_LABELS.get(item, item) for item in mistakes]


def refresh_context():
    global selected_exercise, exercise_status, last_context_fetch, last_session_id, rep_count
    if time.time() - last_context_fetch < 1.0:
        return
    last_context_fetch = time.time()
    try:
        response = http_session.get(CONTEXT_URL, timeout=0.25)
        if response.status_code >= 300:
            return
        payload = response.json()
        current = payload.get("current", {})
        selected_exercise = current.get("exercise_type") or "unselected"
        exercise_status = current.get("exercise_status") or "awaiting_rfid"
        new_sid = current.get("active_session_code")
        
        # RESET logic: If session ID changed or cleared, wipe local reps
        if new_sid != last_session_id:
            if last_session_id is not None:
                print(f"[Vision] Session changed from {last_session_id} to {new_sid}. Resetting reps.")
                rep_count = 0
            last_session_id = new_sid
        
        # If explicitly logged out, reset
        if exercise_status == "awaiting_rfid":
            rep_count = 0
            
    except Exception:
        pass


def write_local_state(person_detected, current_reps, mistakes):
    payload = {
        "current": {
            "user_id": "Person Detected" if person_detected else "No Person",
            "member_name": "Person Detected" if person_detected else "No Person",
            "rep_count": current_reps,
            "ai_state": 0 if not mistakes else mistakes[0],
            "ai_status": humanize_mistakes(mistakes)[0],
            "feedback_text": humanize_mistakes(mistakes)[0],
            "active_session_code": None,
            "machine_name": "Chest Press",
            "station_id": "CHEST_PRESS_01",
            "exercise_type": selected_exercise if selected_exercise != "unselected" else None,
            "exercise_status": exercise_status,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        },
        "feeds": [
            {
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "field1": "Person Detected" if person_detected else "No Person",
                "field2": current_reps,
                "field4": 0 if not mistakes else int(mistakes[0].replace("ID ", "")),
            }
        ],
        "history": [],
    }
    try:
        with open(LOCAL_STATE_PATH, "w", encoding="utf-8") as file:
            json.dump(payload, file)
    except Exception:
        pass

def detect_rep(kp):
    global rep_count, rep_phase, rep_top_y, rep_bottom_y, last_wrist_y
    global wrist_smooth_y, down_confirm_frames, up_confirm_frames, last_rep_timestamp

    wrist_y = (kp[9][1] + kp[10][1]) / 2
    s_y = (kp[5][1] + kp[6][1]) / 2
    h_y = (kp[11][1] + kp[12][1]) / 2
    torso_length = abs(s_y - h_y)

    if torso_length < 10:
        return rep_count

    if wrist_smooth_y is None:
        wrist_smooth_y = wrist_y
    else:
        wrist_smooth_y = (0.75 * wrist_smooth_y) + (0.25 * wrist_y)

    if rep_top_y is None:
        rep_top_y = wrist_smooth_y
        rep_bottom_y = wrist_smooth_y
        return rep_count

    rep_top_y = min(rep_top_y, wrist_smooth_y)
    rep_bottom_y = max(rep_bottom_y, wrist_smooth_y)

    if last_wrist_y is None:
        last_wrist_y = wrist_smooth_y
        return rep_count

    delta = wrist_smooth_y - last_wrist_y
    down_threshold = torso_length * REP_DOWN_THRESHOLD
    up_threshold = torso_length * REP_UP_THRESHOLD
    rom_ratio = (rep_bottom_y - rep_top_y) / torso_length

    if rep_phase in ["IDLE", "UP"]:
        if delta > down_threshold:
            down_confirm_frames += 1
        else:
            down_confirm_frames = 0

        if down_confirm_frames >= REP_CONFIRM_FRAMES:
            rep_phase = "DOWN"
            rep_bottom_y = wrist_smooth_y
            down_confirm_frames = 0
            up_confirm_frames = 0

    elif rep_phase == "DOWN":
        rep_bottom_y = max(rep_bottom_y, wrist_smooth_y)

        if delta < -up_threshold:
            up_confirm_frames += 1
        else:
            up_confirm_frames = 0

        if (
            up_confirm_frames >= REP_CONFIRM_FRAMES
            and rom_ratio >= MIN_REP_ROM_RATIO
            and (time.time() - last_rep_timestamp) >= REP_COOLDOWN_SECONDS
        ):
            rep_phase = "UP"
            rep_count += 1
            last_rep_timestamp = time.time()
            rep_top_y = wrist_smooth_y
            rep_bottom_y = wrist_smooth_y
            up_confirm_frames = 0
            down_confirm_frames = 0

    last_wrist_y = wrist_smooth_y
    return rep_count

def _post_payload(payload):
    global last_backend_ok, backend_warned
    try:
        response = http_session.post(BACKEND_URL, json=payload, timeout=0.35)
        if response.status_code >= 300:
            if not backend_warned:
                print(f"[Vision->Backend] HTTP {response.status_code}: {response.text}")
                backend_warned = True
            last_backend_ok = False
            return
        if not last_backend_ok:
            print("[Vision->Backend] Connected")
        last_backend_ok = True
        backend_warned = False
    except Exception as exc:
        if not backend_warned:
            print(f"[Vision->Backend] Offline: {exc}")
            backend_warned = True
        last_backend_ok = False

def send_to_backend(mistakes, current_reps, person_detected):
    global last_alert_time, last_sent_state, post_thread
    if time.time() - last_alert_time < COOLDOWN_TIME:
        return
    priority = {"ID 5": 5, "ID 4": 4, "ID 1": 1, "ID 2": 2, "ID 3": 3}
    target_id = 0 if not mistakes else priority[sorted(mistakes, key=lambda x: priority.get(x, 99))[0]]
    user_label = "Person Detected" if person_detected else "No Person"
    state_signature = f"{target_id}:{current_reps}:{user_label}"
    if last_sent_state == state_signature and time.time() - last_alert_time < 0.5:
        return
    if post_thread is not None and post_thread.is_alive():
        return

    payload = {
        "ai_state": target_id,
        "rep_count": current_reps,
        "user_id": user_label,
        "source": "ai_vision_yolo",
    }
    post_thread = threading.Thread(target=_post_payload, args=(payload,), daemon=True)
    post_thread.start()
    last_alert_time = time.time()
    last_sent_state = state_signature

def main():
    global last_debug_print
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    print("=== Smart Gym AI Vision: BACKEND MODE ===")
    frame_index = 0
    display_frame = None
    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            break

        frame_index += 1
        if frame_index % PROCESS_EVERY_N_FRAMES != 0:
            cv2.imshow("Smart Gym - Monitor", display_frame if display_frame is not None else frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            continue

        now = time.time()
        refresh_context()
        results = model.predict(frame, conf=0.55, imgsz=PREDICT_IMGSZ, verbose=False)
        current_mistakes = []
        person_detected = False
        annotated_frame = frame

        for r in results:
            if not r.keypoints or len(r.keypoints.xy) == 0:
                continue
            person_detected = True
            kp = r.keypoints.xy[0].cpu().numpy()
            if kp[9][1] == 0 or kp[11][1] == 0 or kp[7][1] == 0:
                continue
            draw_pose_overlay(annotated_frame, kp)
            if exercise_status == "tracking" and selected_exercise == "chest_press":
                detect_rep(kp)
            m1 = detect_asymmetry(kp, now)
            m2 = detect_posture_issue(kp, now)
            m3 = detect_half_rep_angle(kp)
            m4 = detect_jerk_normalized(kp, now)
            m5 = detect_wrong_exercise(kp, now)
            for m in [m1, m2, m3, m4, m5]:
                if m:
                    current_mistakes.append(m)

        send_to_backend(current_mistakes, rep_count, person_detected)
        write_local_state(person_detected, rep_count, current_mistakes)
        status_text = f"{'Person Detected' if person_detected else 'No Person'} | Reps: {rep_count}"
        cv2.putText(annotated_frame, status_text, (16, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 0), 2)
        pretty_mistakes = humanize_mistakes(current_mistakes)
        cv2.putText(annotated_frame, f"AI State: {pretty_mistakes[0]}", (16, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 200, 0), 2)
        cv2.putText(annotated_frame, f"Exercise: {selected_exercise.replace('_', ' ')}", (16, 84), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (120, 220, 255), 2)
        cv2.putText(annotated_frame, f"Session: {exercise_status}", (16, 112), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (120, 220, 255), 2)
        cv2.putText(annotated_frame, f"Backend: {'Connected' if last_backend_ok else 'Offline'}", (16, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (120, 220, 255), 2)
        if time.time() - last_debug_print > 1.0:
            print(f"[Vision] exercise={selected_exercise} session={exercise_status} detected={person_detected} reps={rep_count} mistakes={pretty_mistakes}")
            last_debug_print = time.time()
        display_frame = annotated_frame
        cv2.imshow("Smart Gym - Monitor", display_frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__": main()
