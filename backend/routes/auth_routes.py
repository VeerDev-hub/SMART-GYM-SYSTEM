from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import create_access_token, get_current_user, verify_password
from database import get_db
from models import RFIDCard, User
from schemas import LoginRequest, RFIDLoginRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token({"sub": user.username, "role": user.role})
    return TokenResponse(access_token=token, role=user.role)


@router.post("/rfid-login")
def rfid_login(payload: RFIDLoginRequest, db: Session = Depends(get_db)):
    card = (
        db.query(RFIDCard)
        .filter(RFIDCard.uid == payload.rfid_uid.upper(), RFIDCard.is_active.is_(True))
        .first()
    )
    if not card or not card.member or card.member.membership_status != "active":
        raise HTTPException(status_code=404, detail="Active member not found for this RFID")

    user = card.member.user
    token = create_access_token({"sub": user.username, "role": user.role})
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role,
        "member": {
            "id": card.member.id,
            "username": user.username,
            "full_name": card.member.full_name,
            "membership_status": card.member.membership_status,
            "membership_plan": card.member.membership_plan,
            "rfid_uid": card.uid,
        },
    }


@router.post("/logout")
def logout():
    return {"message": "Logout handled client-side by discarding the JWT"}


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user
