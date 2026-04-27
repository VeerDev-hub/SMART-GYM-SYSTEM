from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def build_training_data():
    rows = []
    labels = []
    rng = np.random.default_rng(42)

    for _ in range(350):
        total_reps = int(rng.integers(6, 26))
        avg_rep_duration = float(rng.uniform(0.9, 3.2))
        avg_rom = float(rng.uniform(260, 760))
        speed_consistency = float(rng.uniform(0.08, 0.95))
        rom_dropoff = float(rng.uniform(0, 220))

        fatigue = int(
            total_reps > 18
            or avg_rep_duration > 2.4
            or speed_consistency < 0.22
            or rom_dropoff > 120
        )

        rows.append([total_reps, avg_rep_duration, avg_rom, speed_consistency, rom_dropoff])
        labels.append(fatigue)

    return np.array(rows), np.array(labels)


def train_and_save_model(output_path: Path):
    features, labels = build_training_data()
    pipeline = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            ("model", RandomForestClassifier(n_estimators=160, max_depth=6, random_state=42)),
        ]
    )
    pipeline.fit(features, labels)
    joblib.dump(pipeline, output_path)
    return output_path


if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "fatigue_model.joblib"
    train_and_save_model(target)
    print(f"Saved model to {target}")

