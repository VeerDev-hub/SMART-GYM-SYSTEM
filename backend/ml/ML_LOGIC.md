# GymOS Biomechanical Analysis Engine (ML Logic)

This document details the technical implementation and physiological logic behind the Machine Learning engine used in the GymOS IoT ecosystem.

## 1. System Overview
The goal of the ML engine is to translate raw ultrasonic distance and timing data from the ESP32 into actionable human performance metrics: **Fatigue Level** and **Form Score**.

## 2. The Dataset (`gym_biomechanics_study.csv`)
The model is trained on a biomechanical dataset containing 500 samples. Each sample represents a completed workout set and consists of 5 primary features:

| Feature | Description | Physiological Significance |
| :--- | :--- | :--- |
| `reps` | Total repetition count | Volume indicator for muscle exhaustion. |
| `avg_duration` | Mean time per rep (sec) | Increases as Type II muscle fibers fatigue (Concentric slowdown). |
| `avg_rom` | Mean Range of Motion (cm) | Standardized depth of movement. |
| `consistency` | Tempo stability (0.0-1.0) | Decreases as neuromuscular control degrades. |
| `rom_dropoff` | Delta between early/late reps | Primary indicator of mechanical failure/short-repping. |

## 3. Model Architecture
*   **Algorithm**: Random Forest Classifier (Ensemble Method)
*   **Estimators**: 250 Decision Trees
*   **Preprocessing**: `StandardScaler` (Z-score normalization)
*   **Export Format**: `joblib` serialized pipeline

## 4. Inference & Scoring Logic (`service.py`)

### Fatigue Classification
The model outputs a probability $P(fatigue)$. This is mapped to three distinct zones:
- **Low Fatigue**: $P < 0.40$
- **Moderate Fatigue**: $0.40 \le P < 0.70$
- **High Fatigue**: $P \ge 0.70$

### Form Score Calculation
The **Form Score (0-100)** is a composite metric calculated using a weighted efficiency algorithm:

1.  **ROM Efficiency (40%)**: Calculated by comparing the user's `avg_rom` against the exercise target (7.0 cm for Chest Press).
2.  **Speed Efficiency (40%)**: Calculated by comparing the `avg_duration` against a target tempo of 1.5s per rep.
3.  **Consistency Bonus (20%)**: A direct reward for maintaining a stable rhythm ($SpeedConsistency \times 20$).

$$FormScore = (ROM_{eff} \times 40) + (Speed_{eff} \times 40) + (Consistency \times 20)$$

## 5. AI Insights Generation
The engine includes a heuristic layer that provides real-time feedback based on the ML results:
- **Mechanical Failure Alert**: Triggered if ROM dropoff exceeds 20% of the initial range.
- **Pacing Feedback**: Triggered if the speed consistency falls below a 0.60 threshold.
- **Recovery Suggestion**: Triggered if Fatigue Level is "High," recommending increased rest intervals.
