from sqlalchemy import func
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import get_current_user, require_admin
from database import get_db
from models import EntryLog, Member, RFIDCard, User, WorkoutSession

router = APIRouter(tags=["dashboards"])


@router.get("/user/dashboard")
def user_dashboard(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    member = current_user.member
    if not member:
        raise HTTPException(status_code=404, detail="Member profile not found")

    entry_logs = (
        db.query(EntryLog)
        .filter(EntryLog.member_id == member.id)
        .order_by(EntryLog.created_at.desc())
        .limit(10)
        .all()
    )
    sessions = (
        db.query(WorkoutSession)
        .filter(WorkoutSession.member_id == member.id)
        .order_by(WorkoutSession.started_at.desc())
        .limit(10)
        .all()
    )
    total_visits = db.query(func.count(EntryLog.id)).filter(EntryLog.member_id == member.id, EntryLog.granted.is_(True)).scalar()

    return {
        "member": {
            "id": member.id,
            "full_name": member.full_name,
            "email": member.email,
            "membership_status": member.membership_status,
            "membership_plan": member.membership_plan,
            "joined_at": member.joined_at,
            "rfid_uid": member.rfid_cards[0].uid if member.rfid_cards else None,
        },
        "summary": {
            "total_visits": total_visits or 0,
            "last_entry_time": entry_logs[0].created_at if entry_logs else None,
            "session_count": len(sessions),
        },
        "entry_logs": [
            {
                "created_at": log.created_at,
                "granted": log.granted,
                "reason": log.reason,
                "source": log.source,
            }
            for log in entry_logs
        ],
        "sessions": [
            {
                "session_id": session.session_code,
                "machine_name": session.machine_name,
                "started_at": session.started_at,
                "total_reps": session.total_reps,
                "duration_ms": session.duration_ms,
                "average_rom": session.average_rom,
                "fatigue_level": session.prediction.fatigue_level if session.prediction else None,
                "form_score": session.prediction.form_score if session.prediction else None,
                "insight": session.prediction.insight if session.prediction else None,
            }
            for session in sessions
        ],
    }


@router.get("/admin/dashboard")
def admin_dashboard(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    members = db.query(Member).order_by(Member.full_name.asc()).all()
    recent_logs = db.query(EntryLog).order_by(EntryLog.created_at.desc()).limit(12).all()
    active_sessions = db.query(WorkoutSession).filter(WorkoutSession.status == "active").all()
    machine_usage = (
        db.query(WorkoutSession.machine_name, func.count(WorkoutSession.id))
        .group_by(WorkoutSession.machine_name)
        .all()
    )

    return {
        "stats": {
            "member_count": len(members),
            "active_memberships": sum(1 for member in members if member.membership_status == "active"),
            "rfid_assigned": db.query(func.count(RFIDCard.id)).scalar() or 0,
            "active_sessions": len(active_sessions),
        },
        "members": [
            {
                "id": member.id,
                "full_name": member.full_name,
                "membership_status": member.membership_status,
                "membership_plan": member.membership_plan,
                "rfid_uid": member.rfid_cards[0].uid if member.rfid_cards else None,
            }
            for member in members
        ],
        "recent_access_logs": [
            {
                "member_name": log.member.full_name if log.member else "Unknown",
                "rfid_uid": log.rfid_uid,
                "granted": log.granted,
                "reason": log.reason,
                "created_at": log.created_at,
            }
            for log in recent_logs
        ],
        "active_sessions": [
            {
                "member_name": session.member.full_name,
                "machine_name": session.machine_name,
                "started_at": session.started_at,
                "total_reps": session.total_reps,
            }
            for session in active_sessions
        ],
        "machine_usage": [{"machine_name": item[0], "sessions": item[1]} for item in machine_usage],
    }

@router.get("/admin/dashboard-public")
def admin_dashboard_public(db: Session = Depends(get_db)):
    # Same as admin_dashboard but without auth for demo purposes
    members = db.query(Member).order_by(Member.full_name.asc()).all()
    recent_logs = db.query(EntryLog).order_by(EntryLog.created_at.desc()).limit(12).all()
    active_sessions = db.query(WorkoutSession).filter(WorkoutSession.status == "active").all()
    machine_usage = (
        db.query(WorkoutSession.machine_name, func.count(WorkoutSession.id))
        .group_by(WorkoutSession.machine_name)
        .all()
    )

    return {
        "stats": {
            "member_count": len(members),
            "active_memberships": sum(1 for member in members if member.membership_status == "active"),
            "rfid_assigned": db.query(func.count(RFIDCard.id)).scalar() or 0,
            "active_sessions": len(active_sessions),
        },
        "members": [
            {
                "id": member.id,
                "full_name": member.full_name,
                "membership_status": member.membership_status,
                "membership_plan": member.membership_plan,
                "rfid_uid": member.rfid_cards[0].uid if member.rfid_cards else None,
            }
            for member in members
        ],
        "recent_access_logs": [
            {
                "member_name": log.member.full_name if log.member else "Unknown",
                "rfid_uid": log.rfid_uid,
                "granted": log.granted,
                "reason": log.reason,
                "created_at": log.created_at,
            }
            for log in recent_logs
        ],
        "active_sessions": [
            {
                "member_name": session.member.full_name,
                "machine_name": session.machine_name,
                "started_at": session.started_at,
                "total_reps": session.total_reps,
            }
            for session in active_sessions
        ],
        "machine_usage": [{"machine_name": item[0], "sessions": item[1]} for item in machine_usage],
    }
