from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import get_current_user, hash_password, require_admin
from database import get_db
from models import Member, RFIDCard, User
from schemas import MemberCreate, MemberResponse, MemberUpdate

router = APIRouter(tags=["members"])


@router.post("/members", response_model=MemberResponse)
def create_member(payload: MemberCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    existing_user = db.query(User).filter(User.username == payload.username).first()
    existing_email = db.query(Member).filter(Member.email == payload.email).first()
    existing_card = db.query(RFIDCard).filter(RFIDCard.uid == payload.rfid_uid.upper()).first()
    if existing_user or existing_email or existing_card:
        raise HTTPException(status_code=400, detail="Username, email, or RFID UID already exists")

    user = User(username=payload.username, password_hash=hash_password(payload.password), role="member")
    db.add(user)
    db.flush()

    member = Member(
        user_id=user.id,
        full_name=payload.full_name,
        email=payload.email,
        membership_status=payload.membership_status,
        membership_plan=payload.membership_plan,
    )
    db.add(member)
    db.flush()

    card = RFIDCard(member_id=member.id, uid=payload.rfid_uid.upper(), is_active=True)
    db.add(card)
    db.commit()
    db.refresh(member)
    return member


@router.get("/members/{member_id}", response_model=MemberResponse)
def get_member(member_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    if current_user.role != "admin" and current_user.member and current_user.member.id != member_id:
        raise HTTPException(status_code=403, detail="You can only view your own member profile")
    return member


@router.put("/members/{member_id}", response_model=MemberResponse)
def update_member(
    member_id: int,
    payload: MemberUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    if payload.email and payload.email != member.email:
        existing_email = db.query(Member).filter(Member.email == payload.email).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Email already in use")
        member.email = payload.email

    if payload.full_name:
        member.full_name = payload.full_name
    if payload.membership_status:
        member.membership_status = payload.membership_status
    if payload.membership_plan:
        member.membership_plan = payload.membership_plan
    if payload.rfid_uid:
        card = member.rfid_cards[0] if member.rfid_cards else None
        existing_card = db.query(RFIDCard).filter(RFIDCard.uid == payload.rfid_uid.upper()).first()
        if existing_card and (not card or existing_card.id != card.id):
            raise HTTPException(status_code=400, detail="RFID UID already assigned")
        if card:
            card.uid = payload.rfid_uid.upper()
        else:
            db.add(RFIDCard(member_id=member.id, uid=payload.rfid_uid.upper(), is_active=True))

    db.commit()
    db.refresh(member)
    return member


@router.delete("/members/{member_id}")
def delete_member(
    member_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    user = db.query(User).filter(User.id == member.user_id).first()
    db.delete(member)
    if user:
        db.delete(user)
    db.commit()
    return {"message": "Member deleted"}
