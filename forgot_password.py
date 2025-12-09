from fastapi import APIRouter, Form, HTTPException, Depends
from sqlmodel import Session, select
from tokens import create_reset_token, verify_reset_token
from email_utils import send_reset_email
from config import API_BASE
from app import User, get_session
from security import hash_password

router = APIRouter()

@router.post("/forgot-password")
def forgot_password(
    username: str = Form(...),
    session: Session = Depends(get_session)
):
    user = session.exec(select(User).where(User.username == username)).first()
    if not user:
        raise HTTPException(400, "User not found")

    token = create_reset_token(user.username)

    send_reset_email(user.username, user.username + "@email.com", token)

    return {"success": True, "message": "Reset link sent"}

@router.post("/reset-password")
def reset_password(
    token: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session)
):
    username = verify_reset_token(token)
    if not username:
        raise HTTPException(400, "Invalid or expired token")

    user = session.exec(select(User).where(User.username == username)).first()
    if not user:
        raise HTTPException(400, "User not found")

    user.hashed_password = hash_password(password)
    session.add(user)
    session.commit()

    return {"success": True, "message": "Password updated"}