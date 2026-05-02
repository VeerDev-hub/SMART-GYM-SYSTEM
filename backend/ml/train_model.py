import joblib
import csv
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from pathlib import Path

def load_biomechanical_study_data(csv_path: Path):
    """
    Loads pre-collected biomechanical study data from a CSV file.
    The dataset contains correlated features from resistance training subjects.
    """
    X = []
    y = []
    
    if not csv_path.exists():
        raise FileNotFoundError(f"Training dataset not found at {csv_path}")

    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            X.append([
                float(row['reps']),
                float(row['avg_duration']),
                float(row['avg_rom']),
                float(row['consistency']),
                float(row['rom_dropoff'])
            ])
            y.append(int(row['fatigue']))

    return np.array(X), np.array(y)

def train_and_save_model(output_path: Path, data_path: Path):
    """
    Trains a Random Forest Classifier on the pre-collected dataset.
    Uses a Pipeline to ensure scaling is consistent during real-time inference.
    """
    print(f"[INFO] Loading training dataset from {data_path.name}...")
    X, y = load_biomechanical_study_data(data_path)
    
    # Random Forest is ideal for identifying non-linear patterns in fatigue
    pipeline = Pipeline(steps=[
        ('scaler', StandardScaler()),
        ('classifier', RandomForestClassifier(
            n_estimators=250, 
            max_depth=8, 
            min_samples_leaf=3,
            random_state=42
        ))
    ])
    
    print(f"[INFO] Training model on {len(X)} biomechanical samples...")
    pipeline.fit(X, y)
    
    joblib.dump(pipeline, output_path)
    return output_path

if __name__ == "__main__":
    current_dir = Path(__file__).resolve().parent
    data_file = current_dir / "gym_biomechanics_study.csv"
    model_file = current_dir / "fatigue_model.joblib"
    
    train_and_save_model(model_file, data_file)
    print(f"[SUCCESS] Fatigue analysis model exported: {model_file}")

