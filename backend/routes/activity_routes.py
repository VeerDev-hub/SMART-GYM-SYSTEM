import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import get_current_user, verify_device_key
from database import get_db
from ml.service import predict_session_features
from models import EntryLog, LiveMachineState, Member, Prediction, RepSample, RFIDCard, User, WorkoutSession
from schemas import (
    EntryLogCreate,
    PredictRequest,
    PredictionResponse,
    SessionEndRequest,
    SessionSampleRequest,
    SessionStartRequest,
)

router = APIRouter(tags=["activity"])


def get_or_create_live_state(db: Session) -> LiveMachineState:
    live_state = db.query(LiveMachineState).filter(LiveMachineState.id == 1).first()
    if not live_state:
        live_state = LiveMachineState(id=1)
        db.add(live_state)
        db.flush()
    return live_state


def get_member_by_uid(db: Session, uid: str) -> Member | None:
    card = db.query(RFIDCard).filter(RFIDCard.uid == uid.upper(), RFIDCard.is_active.is_(True)).first()
    return card.member if card else None


@router.post("/entry-log")
def create_entry_log(
    payload: EntryLogCreate,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_key),
):
    member = get_member_by_uid(db, payload.rfid_uid)
    log = EntryLog(
        member_id=member.id if member else None,
        rfid_uid=payload.rfid_uid.upper(),
        granted=payload.granted and bool(member and member.membership_status == "active"),
        reason=payload.reason,
        source=payload.source,
    )
    db.add(log)
    db.commit()
    return {"message": "Entry log stored", "member_name": member.full_name if member else None}


@router.post("/session/start")
def session_start(
    payload: SessionStartRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_key),
):
    member = get_member_by_uid(db, payload.rfid_uid)
    if not member or member.membership_status != "active":
        raise HTTPException(status_code=404, detail="Active member not found for this RFID")

    session_code = str(uuid.uuid4())
    session = WorkoutSession(
        session_code=session_code,
        member_id=member.id,
        machine_name=payload.machine_name,
        station_id=payload.station_id,
        exercise_type=payload.exercise_type,
    )
    db.add(session)
    
    # Sync with Dashboard
    live_state = get_or_create_live_state(db)
    live_state.active_session_code = session_code
    live_state.exercise_type = payload.exercise_type
    live_state.exercise_status = "tracking"
    live_state.updated_at = datetime.utcnow()
    
    db.commit()
    return {"message": "Session started", "session_id": session_code, "member_name": member.full_name}


@router.post("/session/sample")
def session_sample(
    payload: SessionSampleRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_key),
):
    session = db.query(WorkoutSession).filter(WorkoutSession.session_code == payload.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    sample = RepSample(
        session_id=session.id,
        distance=payload.distance,
        rep_count=payload.rep_count,
        rom=payload.rom,
        rep_completed=payload.rep_completed,
    )
    db.add(sample)
    session.total_reps = max(session.total_reps, payload.rep_count)
    
    # Sync with Dashboard
    live_state = get_or_create_live_state(db)
    if live_state.active_session_code == payload.session_id:
        # User requested: DO NOT use distance sensor for rep count, only AI vision.
        # live_state.rep_count = payload.rep_count 
        live_state.current_distance = payload.distance
        live_state.current_rom = payload.rom
        live_state.updated_at = datetime.utcnow()
        
    db.commit()
    return {"message": "Sample stored"}


@router.post("/session/end")
def session_end(
    payload: SessionEndRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_key),
):
    session = db.query(WorkoutSession).filter(WorkoutSession.session_code == payload.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    samples = db.query(RepSample).filter(RepSample.session_id == session.id).all()
    completed_samples = [sample for sample in samples if sample.rep_completed]
    average_rep_duration = payload.duration_ms / max(payload.total_reps, 1) / 1000.0
    early_rom = completed_samples[0].rom if completed_samples else payload.average_rom
    late_rom = completed_samples[-1].rom if completed_samples else payload.average_rom
    rom_dropoff = max(0.0, early_rom - late_rom)

    live_state = get_or_create_live_state(db)

    session.ended_at = datetime.utcnow()
    # Use AI vision rep count as the source of truth, ignoring machine's payload
    session.total_reps = live_state.rep_count
    session.duration_ms = payload.duration_ms
    session.average_rom = payload.average_rom
    session.speed_consistency = payload.speed_consistency
    session.status = "completed"

    prediction_data = predict_session_features(
        {
            "total_reps": session.total_reps,
            "average_rep_duration": average_rep_duration,
            "average_rom": payload.average_rom,
            "speed_consistency": payload.speed_consistency,
            "rom_dropoff": rom_dropoff,
        }
    )
    
    # Avoid duplicate predictions
    existing_pred = db.query(Prediction).filter(Prediction.session_id == session.id).first()
    if not existing_pred:
        prediction = Prediction(session_id=session.id, **prediction_data)
        db.add(prediction)
    
    # Sync with Dashboard
    live_state = get_or_create_live_state(db)
    if live_state.active_session_code == payload.session_id:
        live_state.exercise_status = "completed"
        live_state.ai_status = f"Fatigue: {prediction_data['fatigue_level']}"
        live_state.feedback_text = prediction_data["insight"]
        live_state.rep_count = payload.total_reps
        live_state.updated_at = datetime.utcnow()
        
    db.commit()

    return {"message": "Session completed", "prediction": prediction_data}


@router.get("/sessions/{user_id}")
def get_sessions(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    member = db.query(Member).filter(Member.user_id == user_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found for user")

    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="You can only view your own sessions")

    sessions = (
        db.query(WorkoutSession)
        .filter(WorkoutSession.member_id == member.id)
        .order_by(WorkoutSession.started_at.desc())
        .all()
    )
    return [
        {
            "session_id": session.session_code,
            "machine_name": session.machine_name,
            "started_at": session.started_at,
            "ended_at": session.ended_at,
            "total_reps": session.total_reps,
            "duration_ms": session.duration_ms,
            "average_rom": session.average_rom,
            "prediction": {
                "fatigue_level": session.prediction.fatigue_level,
                "form_score": session.prediction.form_score,
                "insight": session.prediction.insight,
            }
            if session.prediction
            else None,
        }
        for session in sessions
    ]


@router.post("/predict", response_model=PredictionResponse)
def predict(payload: PredictRequest):
    return predict_session_features(payload.model_dump())
