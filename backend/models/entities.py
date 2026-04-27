from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="member")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    member = relationship("Member", back_populates="user", uselist=False)
    admin_profile = relationship("AdminUser", back_populates="user", uselist=False)


class Member(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    membership_status: Mapped[str] = mapped_column(String(20), default="active")
    membership_plan: Mapped[str] = mapped_column(String(50), default="Monthly")
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="member")
    rfid_cards = relationship("RFIDCard", back_populates="member", cascade="all, delete-orphan")
    entry_logs = relationship("EntryLog", back_populates="member")
    workout_sessions = relationship("WorkoutSession", back_populates="member")
    vision_events = relationship("VisionEvent", back_populates="member")


class RFIDCard(Base):
    __tablename__ = "rfid_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"))
    uid: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    member = relationship("Member", back_populates="rfid_cards")


class EntryLog(Base):
    __tablename__ = "entry_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"), nullable=True)
    rfid_uid: Mapped[str] = mapped_column(String(32), nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str] = mapped_column(String(80), default="membership_active")
    source: Mapped[str] = mapped_column(String(40), default="entrance_station")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    member = relationship("Member", back_populates="entry_logs")


class WorkoutSession(Base):
    __tablename__ = "workout_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_code: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"))
    machine_name: Mapped[str] = mapped_column(String(80), default="Chest Press")
    station_id: Mapped[str] = mapped_column(String(80), default="CHEST_PRESS_01")
    exercise_type: Mapped[str] = mapped_column(String(80), default="chest_press")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_reps: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    average_rom: Mapped[float] = mapped_column(Float, default=0.0)
    speed_consistency: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="active")

    member = relationship("Member", back_populates="workout_sessions")
    rep_samples = relationship("RepSample", back_populates="session", cascade="all, delete-orphan")
    prediction = relationship("Prediction", back_populates="session", uselist=False)
    vision_events = relationship("VisionEvent", back_populates="session")


class RepSample(Base):
    __tablename__ = "rep_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("workout_sessions.id"))
    distance: Mapped[float] = mapped_column(Float)
    rep_count: Mapped[int] = mapped_column(Integer, default=0)
    rom: Mapped[float] = mapped_column(Float, default=0.0)
    rep_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    sampled_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session = relationship("WorkoutSession", back_populates="rep_samples")


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("workout_sessions.id"), unique=True)
    fatigue_level: Mapped[str] = mapped_column(String(30))
    fatigue_probability: Mapped[float] = mapped_column(Float, default=0.0)
    form_score: Mapped[float] = mapped_column(Float, default=0.0)
    insight: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session = relationship("WorkoutSession", back_populates="prediction")


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    title: Mapped[str] = mapped_column(String(60), default="Gym Staff")

    user = relationship("User", back_populates="admin_profile")


class LiveMachineState(Base):
    __tablename__ = "live_machine_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"), nullable=True)
    rfid_uid: Mapped[str | None] = mapped_column(String(32), nullable=True)
    user_label: Mapped[str] = mapped_column(String(120), default="Awaiting Tap...")
    member_name: Mapped[str] = mapped_column(String(120), default="Awaiting Tap...")
    rep_count: Mapped[int] = mapped_column(Integer, default=0)
    ai_state: Mapped[int] = mapped_column(Integer, default=0)
    ai_status: Mapped[str] = mapped_column(String(80), default="Perfect Form")
    feedback_text: Mapped[str] = mapped_column(Text, default="Position yourself in front of the camera to begin form analysis.")
    active_session_code: Mapped[str | None] = mapped_column(String(36), nullable=True)
    machine_name: Mapped[str] = mapped_column(String(80), default="Chest Press")
    station_id: Mapped[str] = mapped_column(String(80), default="CHEST_PRESS_01")
    exercise_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    exercise_status: Mapped[str] = mapped_column(String(40), default="awaiting_rfid")
    current_distance: Mapped[float] = mapped_column(Float, default=0.0)
    current_rom: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[str] = mapped_column(String(40), default="demo")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class VisionEvent(Base):
    __tablename__ = "vision_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"), nullable=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("workout_sessions.id"), nullable=True)
    ai_state: Mapped[int] = mapped_column(Integer, default=0)
    feedback_title: Mapped[str] = mapped_column(String(80), default="Perfect Form")
    feedback_text: Mapped[str] = mapped_column(Text, default="")
    rep_count: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(40), default="ai_vision")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    member = relationship("Member", back_populates="vision_events")
    session = relationship("WorkoutSession", back_populates="vision_events")
