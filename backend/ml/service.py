from pathlib import Path

import joblib
import numpy as np

MODEL_PATH = Path(__file__).resolve().parent / "fatigue_model.joblib"


def ensure_model():
    if MODEL_PATH.exists():
        return
    from ml.train_model import train_and_save_model

    train_and_save_model(MODEL_PATH)


def load_model():
    ensure_model()
    return joblib.load(MODEL_PATH)


def predict_session_features(features: dict) -> dict:
    model = load_model()
    vector = np.array(
        [
            [
                features["total_reps"],
                features["average_rep_duration"],
                features["average_rom"],
                features["speed_consistency"],
                features["rom_dropoff"],
            ]
        ]
    )
    probability = float(model.predict_proba(vector)[0][1])
    fatigue_level = "High" if probability >= 0.7 else "Moderate" if probability >= 0.4 else "Low"

    # Realistic override for empty or very short sets
    if features["total_reps"] == 0:
        fatigue_level = "Low"
        probability = 0.0

    # Dynamic Form Score Calculation
    # Target ROM is ~7cm (from 72cm to 65cm)
    target_rom = 7.0
    rom_efficiency = min(features["average_rom"] / target_rom, 1.2) # Up to 120% efficiency
    
    # Speed efficiency (Target ~1.5s per rep)
    target_speed = 1.5
    speed_efficiency = 1.0 - min(abs(features["average_rep_duration"] - target_speed) / 2.0, 0.5)
    
    # Consistency penalty
    consistency_bonus = features["speed_consistency"] # Closer to 1.0 is better
    
    form_score = round(max(0.0, min(100.0, (rom_efficiency * 40 + speed_efficiency * 40 + consistency_bonus * 20))), 2)

    if features["total_reps"] == 0:
        insight = "No full reps detected. Ensure you are completing the full range of motion."
    elif fatigue_level == "High":
        insight = "Performance is fading. Reduce load slightly or extend rest before the next set."
    elif form_score >= 75:
        insight = "Strong range of motion and stable tempo. Current chest press form looks consistent."
    else:
        insight = "Movement quality dipped during the set. Focus on controlled return and full extension."

    return {
        "fatigue_level": fatigue_level,
        "fatigue_probability": round(probability, 4),
        "form_score": form_score,
        "insight": insight,
    }

