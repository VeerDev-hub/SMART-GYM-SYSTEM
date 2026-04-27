import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

from backend.database import DATABASE_URL
from backend.models import EntryLog, WorkoutSession, RepSample, Prediction, VisionEvent, LiveMachineState

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def hard_reset():
    db = SessionLocal()
    
    tables_to_clear = [
        ("RepSamples", RepSample),
        ("Predictions", Prediction),
        ("VisionEvents", VisionEvent),
        ("WorkoutSessions", WorkoutSession),
        ("EntryLogs", EntryLog),
        ("LiveMachineState", LiveMachineState)
    ]
    
    for name, model in tables_to_clear:
        try:
            print(f"Clearing {name}...")
            db.query(model).delete()
            db.commit()
        except Exception as e:
            print(f"Skipping {name}: {e}")
            db.rollback()
            
    try:
        # recreate live machine state
        state = LiveMachineState(id=1)
        db.add(state)
        db.commit()
        print("Database hard reset successful. Kept Users, Members, and AdminUsers.")
    except Exception as e:
        print(f"Error resetting database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    hard_reset()
