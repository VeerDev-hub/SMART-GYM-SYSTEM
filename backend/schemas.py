from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class LoginRequest(BaseModel):
    username: str
    password: str


class RFIDLoginRequest(BaseModel):
    rfid_uid: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str


class MemberCreate(BaseModel):
    username: str
    password: str
    full_name: str
    email: str
    membership_status: str = "active"
    membership_plan: str = "Monthly"
    rfid_uid: str


class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    membership_status: str
    membership_plan: str
    joined_at: datetime


class MemberUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    membership_status: Optional[str] = None
    membership_plan: Optional[str] = None
    rfid_uid: Optional[str] = None


class EntryLogCreate(BaseModel):
    rfid_uid: str
    granted: bool
    reason: str = "membership_active"
    source: str = "entrance_station"


class SessionStartRequest(BaseModel):
    rfid_uid: str
    machine_name: str = "Chest Press"
    station_id: str = "CHEST_PRESS_01"
    exercise_type: str = "chest_press"


class SessionSampleRequest(BaseModel):
    session_id: str
    distance: float
    rep_count: int
    rom: float = 0.0
    rep_completed: bool = False


class SessionEndRequest(BaseModel):
    session_id: str
    total_reps: int
    duration_ms: int
    average_rom: float = 0.0
    speed_consistency: float = 0.0
    machine_name: str = "Chest Press"


class MachineTapRequest(BaseModel):
    rfid_uid: str
    machine_name: str = "Chest Press"
    station_id: str = "CHEST_PRESS_01"


class ExerciseSelectRequest(BaseModel):
    exercise_type: str
    machine_name: str = "Chest Press"
    station_id: str = "CHEST_PRESS_01"


class PredictRequest(BaseModel):
    total_reps: int = Field(..., ge=0)
    average_rep_duration: float = Field(..., ge=0)
    average_rom: float = Field(..., ge=0)
    speed_consistency: float = Field(..., ge=0)
    rom_dropoff: float = Field(..., ge=0)


class PredictionResponse(BaseModel):
    fatigue_level: str
    fatigue_probability: float
    form_score: float
    insight: str


class DashboardSession(BaseModel):
    session_id: str
    machine_name: str
    started_at: datetime
    total_reps: int
    duration_ms: int
    average_rom: float
    fatigue_level: Optional[str] = None
    form_score: Optional[float] = None
