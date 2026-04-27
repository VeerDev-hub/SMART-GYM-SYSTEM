# demo-simulator/simulator.py
import requests
import time
import random

URL = "http://127.0.0.1:8000/simulator/update"

print("=== Hardware Simulator: Reps & Access Mode ===")

while True:
    user = random.choice(
        [
            {"user_id": "Aarav Sharma", "rfid_uid": "3B7D483C"},
            {"user_id": "Diya Patel", "rfid_uid": "3B5CB33C"},
            {"user_id": "Veer Pratap Singh", "rfid_uid": "CEAECFBD"},
        ]
    )
    print(f"\nUser {user['user_id']} detected at machine.")
    
    for rep in range(1, 11):
        requests.post(URL, json={"user_id": user["user_id"], "rfid_uid": user["rfid_uid"], "rep_count": rep, "source": "demo_simulator"})
        print(f"   [IR SENSOR] Count: {rep}")
        time.sleep(3) # Simulating rep time
        
    print("Set finished. Resting...")
    requests.post(URL, json={"user_id": user["user_id"], "rfid_uid": user["rfid_uid"], "rep_count": 0, "source": "demo_simulator"})
    time.sleep(10)
