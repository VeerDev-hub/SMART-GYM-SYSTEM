from datetime import datetime, timedelta

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import create_access_token
from database import get_db
from models import LiveMachineState, Member, RFIDCard, VisionEvent, WorkoutSession, EntryLog
from schemas import ExerciseSelectRequest, MachineTapRequest

router = APIRouter(tags=["integration"])

AI_FEEDBACK = {
    0: {"title": "Perfect Form", "text": "Excellent control. Maintain this tempo."},
    1: {"title": "Asymmetry", "text": "Balance your grip. One side is lagging during the press."},
    2: {"title": "Posture Alert", "text": "Keep your back flat against the pad and brace your core."},
    3: {"title": "Half Rep", "text": "Increase range of motion and finish the full chest press arc."},
    4: {"title": "Weight Jerking", "text": "Too much momentum. Slow down and control both directions."},
    5: {"title": "Wrong Exercise", "text": "Only one arm is lifting. Use both hands together for chest press form."},
}


def get_or_create_live_state(db: Session) -> LiveMachineState:
    live_state = db.query(LiveMachineState).filter(LiveMachineState.id == 1).first()
    if not live_state:
        live_state = LiveMachineState(id=1)
        db.add(live_state)
        db.flush()
    return live_state


def reset_live_state(live_state: LiveMachineState) -> None:
    live_state.member_id = None
    live_state.rfid_uid = None
    live_state.user_label = "Awaiting Tap..."
    live_state.member_name = "Awaiting Tap..."
    live_state.rep_count = 0
    live_state.ai_state = 0
    live_state.ai_status = "Perfect Form"
    live_state.feedback_text = "Position yourself in front of the camera to begin form analysis."
    live_state.active_session_code = None
    live_state.machine_name = "Chest Press"
    live_state.station_id = "CHEST_PRESS_01"
    live_state.exercise_type = None
    live_state.exercise_status = "awaiting_rfid"
    live_state.source = "demo"
    live_state.updated_at = datetime.utcnow()


def resolve_member(db: Session, user_id: str | None = None, rfid_uid: str | None = None) -> Member | None:
    if rfid_uid:
        card = db.query(RFIDCard).filter(RFIDCard.uid == rfid_uid.upper()).first()
        return card.member if card else None

    if user_id:
        member = db.query(Member).filter(Member.full_name == user_id).first()
        if member:
            return member
        card = db.query(RFIDCard).filter(RFIDCard.uid == user_id.upper()).first()
        return card.member if card else None

    return None


def latest_session_for_member(db: Session, member_id: int | None) -> WorkoutSession | None:
    if not member_id:
        return None
    return (
        db.query(WorkoutSession)
        .filter(WorkoutSession.member_id == member_id)
        .order_by(WorkoutSession.started_at.desc())
        .first()
    )


def build_member_profile(member: Member | None) -> dict | None:
    if not member:
        return None

    card = member.rfid_cards[0].uid if member.rfid_cards else None
    return {
        "member_id": member.id,
        "username": member.user.username if member.user else None,
        "full_name": member.full_name,
        "email": member.email,
        "membership_status": member.membership_status,
        "membership_plan": member.membership_plan,
        "rfid_uid": card,
        "joined_at": member.joined_at.isoformat() if member.joined_at else None,
    }


def close_live_session_if_needed(db: Session, live_state: LiveMachineState, new_status: str = "cancelled") -> None:
    if not live_state.active_session_code:
        return

    active_session = (
        db.query(WorkoutSession)
        .filter(WorkoutSession.session_code == live_state.active_session_code)
        .first()
    )
    if active_session and active_session.status == "active":
        active_session.status = new_status
        active_session.ended_at = datetime.utcnow()


@router.post("/machine/tap")
def machine_tap(payload: MachineTapRequest, db: Session = Depends(get_db)):
    print(f"[Backend] Machine tap received: RFID={payload.rfid_uid}")
    member = resolve_member(db, rfid_uid=payload.rfid_uid)
    if not member or member.membership_status != "active":
        raise HTTPException(status_code=404, detail="Active member not found for this RFID")

    twelve_hours_ago = datetime.utcnow() - timedelta(hours=12)
    recent_entry = (
        db.query(EntryLog)
        .filter(EntryLog.member_id == member.id)
        .filter(EntryLog.granted == True)
        .filter(EntryLog.created_at >= twelve_hours_ago)
        .order_by(EntryLog.created_at.desc())
        .first()
    )
    
    live_state = get_or_create_live_state(db)
    
    if not recent_entry:
        live_state.user_label = "Access Denied"
        live_state.member_name = member.full_name
        live_state.feedback_text = "Please tap your card at the gym entrance before starting the exercise."
        live_state.ai_status = "Access Denied"
        live_state.exercise_status = "awaiting_rfid"
        live_state.rfid_uid = None
        live_state.updated_at = datetime.utcnow()
        db.commit()
        raise HTTPException(status_code=403, detail="Please tap at the gym entrance first")
    
    # CLEAR old vision alerts so they don't leak into the next user
    from models import VisionEvent
    db.query(VisionEvent).filter(VisionEvent.member_id == live_state.member_id).delete()

    # FORCED RESET for next user
    live_state.member_id = member.id
    live_state.rfid_uid = payload.rfid_uid.upper()
    live_state.user_label = member.full_name
    live_state.member_name = member.full_name
    live_state.rep_count = 0
    live_state.ai_state = 0
    live_state.ai_status = "Ready"
    live_state.feedback_text = "Tapped in as " + member.full_name + ". Start your set!"
    live_state.active_session_code = None
    live_state.machine_name = payload.machine_name
    live_state.station_id = payload.station_id
    live_state.exercise_type = None
    live_state.exercise_status = "awaiting_exercise"
    live_state.current_distance = 0.0
    live_state.current_rom = 0.0
    live_state.source = "machine_rfid"
    live_state.updated_at = datetime.utcnow()
    
    db.commit()
    return {"status": "success", "member_name": member.full_name}

    token = create_access_token({"sub": member.user.username, "role": member.user.role})
    return {
        "status": "success",
        "member_name": member.full_name,
        "rfid_uid": payload.rfid_uid.upper(),
        "exercise_status": live_state.exercise_status,
        "access_token": token,
        "role": member.user.role,
        "member": build_member_profile(member),
    }


@router.post("/machine/select-exercise")
def machine_select_exercise(payload: ExerciseSelectRequest, db: Session = Depends(get_db)):
    live_state = get_or_create_live_state(db)
    if not live_state.member_id or not live_state.rfid_uid:
        raise HTTPException(status_code=400, detail="Tap RFID card first")

    active_session = None
    if live_state.active_session_code:
        active_session = db.query(WorkoutSession).filter(WorkoutSession.session_code == live_state.active_session_code).first()

    if not active_session:
        session_code = str(uuid.uuid4())
        active_session = WorkoutSession(
            session_code=session_code,
            member_id=live_state.member_id,
            machine_name=payload.machine_name,
            station_id=payload.station_id,
            exercise_type=payload.exercise_type,
            status="active",
        )
        db.add(active_session)
        db.flush()
        live_state.active_session_code = session_code
    else:
        active_session.machine_name = payload.machine_name
        active_session.station_id = payload.station_id
        active_session.exercise_type = payload.exercise_type

    live_state.machine_name = payload.machine_name
    live_state.station_id = payload.station_id
    live_state.exercise_type = payload.exercise_type
    live_state.exercise_status = "tracking"
    live_state.ai_status = "Exercise Selected"
    live_state.feedback_text = f"Tracking form for {payload.exercise_type.replace('_', ' ')}."
    live_state.updated_at = datetime.utcnow()
    db.commit()

    return {
        "status": "success",
        "session_id": live_state.active_session_code,
        "member_name": live_state.member_name,
        "exercise_type": live_state.exercise_type,
    }


@router.post("/machine/reset")
def machine_reset(db: Session = Depends(get_db)):
    live_state = get_or_create_live_state(db)
    close_live_session_if_needed(db, live_state)
    reset_live_state(live_state)
    db.commit()
    return {"status": "success"}


@router.get("/machine/current")
def machine_current(db: Session = Depends(get_db)):
    live_state = get_or_create_live_state(db)
    member = db.query(Member).filter(Member.id == live_state.member_id).first() if live_state.member_id else None
    return {
        "member_name": live_state.member_name,
        "rfid_uid": live_state.rfid_uid,
        "rep_count": live_state.rep_count,
        "active_session_code": live_state.active_session_code,
        "machine_name": live_state.machine_name,
        "station_id": live_state.station_id,
        "exercise_type": live_state.exercise_type,
        "exercise_status": live_state.exercise_status,
        "updated_at": live_state.updated_at.isoformat() if live_state.updated_at else None,
        "member": build_member_profile(member),
    }


@router.post("/simulator/update")
def update_simulator_state(payload: dict, db: Session = Depends(get_db)):
    member = resolve_member(db, payload.get("user_id"), payload.get("rfid_uid"))
    live_state = get_or_create_live_state(db)
    session = latest_session_for_member(db, member.id if member else None)

    live_state.member_id = member.id if member else None
    live_state.rfid_uid = member.rfid_cards[0].uid if member and member.rfid_cards else payload.get("rfid_uid")
    live_state.user_label = member.full_name if member else payload.get("user_id", "Awaiting Tap...")
    live_state.member_name = live_state.user_label
    live_state.rep_count = int(payload.get("rep_count", live_state.rep_count))
    live_state.active_session_code = session.session_code if session else None
    live_state.exercise_status = "tracking" if live_state.active_session_code else "awaiting_exercise"
    live_state.source = payload.get("source", "demo_simulator")
    live_state.updated_at = datetime.utcnow()
    db.commit()

    return {"status": "success"}


@router.post("/vision/update")
def update_vision_state(payload: dict, db: Session = Depends(get_db)):
    live_state = get_or_create_live_state(db)
    
    if live_state.user_label == "Access Denied" and live_state.updated_at:
        age_seconds = (datetime.utcnow() - live_state.updated_at).total_seconds()
        if age_seconds < 8.0:
            return {"status": "ignored_due_to_access_denied"}

    ai_state = int(payload.get("ai_state", 0))
    feedback = AI_FEEDBACK.get(ai_state, AI_FEEDBACK[0])
    member = resolve_member(db, payload.get("user_id"), payload.get("rfid_uid"))

    if member:
        live_state.member_id = member.id
        live_state.rfid_uid = member.rfid_cards[0].uid if member.rfid_cards else live_state.rfid_uid
        live_state.user_label = member.full_name
        live_state.member_name = member.full_name
    elif payload.get("user_id") and payload.get("user_id") not in {"Person Detected", "No Person"}:
        live_state.user_label = payload.get("user_id")
        live_state.member_name = payload.get("user_id")
        live_state.member_id = None

    if payload.get("rep_count") is not None:
        live_state.rep_count = int(payload["rep_count"])

    live_state.ai_state = ai_state
    live_state.ai_status = feedback["title"]
    live_state.feedback_text = feedback["text"]
    live_state.source = payload.get("source", "ai_vision_yolo")
    live_state.updated_at = datetime.utcnow()

    session = latest_session_for_member(db, live_state.member_id)
    if session:
        live_state.active_session_code = session.session_code
        if session.exercise_type:
            live_state.exercise_type = session.exercise_type
            live_state.exercise_status = "tracking"

    latest_event = db.query(VisionEvent).order_by(VisionEvent.created_at.desc()).first()
    should_store_event = True
    if latest_event and latest_event.ai_state == ai_state:
        age = (datetime.utcnow() - latest_event.created_at).total_seconds()
        if age < 1.0:
            should_store_event = False

    if should_store_event:
        event = VisionEvent(
            member_id=live_state.member_id,
            session_id=session.id if session else None,
            ai_state=ai_state,
            feedback_title=feedback["title"],
            feedback_text=feedback["text"],
            rep_count=live_state.rep_count,
            source=live_state.source,
        )
        db.add(event)
    db.commit()
    return {"status": "success", "ai_state": ai_state}


@router.get("/dashboard/live")
def live_dashboard(db: Session = Depends(get_db)):
    live_state = get_or_create_live_state(db)
    events = db.query(VisionEvent).order_by(VisionEvent.created_at.desc()).limit(20).all()
    history = db.query(WorkoutSession).order_by(WorkoutSession.started_at.desc()).limit(8).all()
    member = db.query(Member).filter(Member.id == live_state.member_id).first() if live_state.member_id else None

    return {
        "current": {
            "user_id": live_state.user_label,
            "member_name": live_state.member_name,
            "rep_count": live_state.rep_count,
            "ai_state": live_state.ai_state,
            "ai_status": live_state.ai_status,
            "feedback_text": live_state.feedback_text,
            "rfid_uid": live_state.rfid_uid,
            "active_session_code": live_state.active_session_code,
            "machine_name": live_state.machine_name,
            "station_id": live_state.station_id,
            "exercise_type": live_state.exercise_type,
            "exercise_status": live_state.exercise_status,
            "current_distance": live_state.current_distance,
            "current_rom": live_state.current_rom,
            "updated_at": live_state.updated_at,
            "member_profile": build_member_profile(member),
            "auto_login_ready": bool(member and live_state.rfid_uid),
        },
        "feeds": [
            {
                "created_at": event.created_at.isoformat(),
                "field1": event.member.full_name if event.member else live_state.user_label,
                "field2": event.rep_count,
                "field4": event.ai_state,
                "feedback_title": event.feedback_title,
                "feedback_text": event.feedback_text,
            }
            for event in reversed(events)
        ],
        "history": [
            {
                "session_id": session.session_code,
                "member_name": session.member.full_name,
                "started_at": session.started_at.isoformat(),
                "reps": session.total_reps,
                "fatigue_level": session.prediction.fatigue_level if session.prediction else "Pending",
                "form_score": session.prediction.form_score if session.prediction else None,
            }
            for session in history
        ],
    }
