from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth import get_current_user, hash_password
from database import Base, SessionLocal, engine
from models import AdminUser, Member, RFIDCard, User
from routes.activity_routes import router as activity_router
from routes.auth_routes import router as auth_router
from routes.dashboard_routes import router as dashboard_router
from routes.integration_routes import router as integration_router
from routes.member_routes import router as member_router

app = FastAPI(title="Smart Gym IoT Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def seed_demo_data():
    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            return

        admin_user = User(username="admin", password_hash=hash_password("admin123"), role="admin")
        db.add(admin_user)
        db.flush()
        db.add(AdminUser(user_id=admin_user.id, title="Gym Manager"))

        demo_members = [
            {
                "username": "member1",
                "password": "member123",
                "full_name": "Aarav Sharma",
                "email": "aarav@example.com",
                "membership_status": "active",
                "membership_plan": "Quarterly",
                "rfid_uid": "3B7D483C",
            },
            {
                "username": "member2",
                "password": "member223",
                "full_name": "Diya Patel",
                "email": "diya@example.com",
                "membership_status": "active",
                "membership_plan": "Monthly",
                "rfid_uid": "3B5CB33C",
            },
            {
                "username": "member3",
                "password": "member323",
                "full_name": "Rohan Mehta",
                "email": "rohan@example.com",
                "membership_status": "active",
                "membership_plan": "Annual",
                "rfid_uid": "2B40B13C",
            },
            {
                "username": "member4",
                "password": "member423",
                "full_name": "Kunal Verma",
                "email": "kunal@example.com",
                "membership_status": "inactive",
                "membership_plan": "Monthly",
                "rfid_uid": "3B15113C",
            },
            {
                "username": "member5",
                "password": "member523",
                "full_name": "Veer Pratap Singh",
                "email": "veer@example.com",
                "membership_status": "active",
                "membership_plan": "Annual",
                "rfid_uid": "CEAECFBD",
            },
            {
                "username": "member6",
                "password": "member623",
                "full_name": "Nisha Kapoor",
                "email": "nisha@example.com",
                "membership_status": "active",
                "membership_plan": "Monthly",
                "rfid_uid": "53BEA9FA",
            },
            {
                "username": "member7",
                "password": "member723",
                "full_name": "Arjun Malhotra",
                "email": "arjun@example.com",
                "membership_status": "active",
                "membership_plan": "Quarterly",
                "rfid_uid": "2545FD00",
            },
        ]

        for member_data in demo_members:
            user = User(
                username=member_data["username"],
                password_hash=hash_password(member_data["password"]),
                role="member",
            )
            db.add(user)
            db.flush()

            member = Member(
                user_id=user.id,
                full_name=member_data["full_name"],
                email=member_data["email"],
                membership_status=member_data["membership_status"],
                membership_plan=member_data["membership_plan"],
            )
            db.add(member)
            db.flush()
            db.add(RFIDCard(member_id=member.id, uid=member_data["rfid_uid"], is_active=True))

        db.commit()
    finally:
        db.close()


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    seed_demo_data()


app.include_router(auth_router)
app.include_router(member_router)
app.include_router(activity_router)
app.include_router(dashboard_router, prefix="/dashboard")
app.include_router(integration_router)


@app.get("/")
def health():
    return {"message": "Smart Gym Membership Management API is running"}


@app.get("/me")
def me_proxy(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "username": current_user.username, "role": current_user.role}
