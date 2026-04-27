import sqlite3
import os

db_path = "f:/Projects/IoT/backend/gym_iot.db"

if os.path.exists(db_path):
    print(f"Connecting to {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("Adding current_distance column...")
        cursor.execute("ALTER TABLE live_machine_state ADD COLUMN current_distance FLOAT DEFAULT 0.0")
    except sqlite3.OperationalError:
        print("Column current_distance already exists.")

    try:
        print("Adding current_rom column...")
        cursor.execute("ALTER TABLE live_machine_state ADD COLUMN current_rom FLOAT DEFAULT 0.0")
    except sqlite3.OperationalError:
        print("Column current_rom already exists.")
        
    conn.commit()
    conn.close()
    print("Database updated successfully!")
else:
    print("Database file not found. It will be created automatically when you run the backend.")
