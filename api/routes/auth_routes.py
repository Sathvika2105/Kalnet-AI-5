from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
from api.models import User, get_db
from api.auth import verify_password, create_access_token, get_current_user
from api.config import ACCESS_TOKEN_EXPIRE_MINUTES
from collections import defaultdict
import logging
import os
import time

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

IP_RATE_LIMIT = 15
USER_RATE_LIMIT = 5
WINDOW = 60
LOCKOUT_DURATION = 300

_ip_attempts = defaultdict(list)
_user_attempts = defaultdict(list)
_locked_users = {}

def _check_login_rate(ip: str, username: str):
    now = time.time()

    if username in _locked_users:
        unlock = _locked_users[username]
        if now < unlock:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Account temporarily locked. Try again later.",
            )
        del _locked_users[username]

    cutoff = now - WINDOW

    ip_window = [t for t in _ip_attempts[ip] if t > cutoff]
    _ip_attempts[ip] = ip_window
    if len(ip_window) >= IP_RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please wait before trying again.",
        )

    user_window = [t for t in _user_attempts[username] if t > cutoff]
    _user_attempts[username] = user_window
    if len(user_window) >= USER_RATE_LIMIT:
        _locked_users[username] = now + LOCKOUT_DURATION
        logger.warning("User %s locked out for %ss (from %s)", username, LOCKOUT_DURATION, ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Account temporarily locked due to too many failed attempts.",
        )


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), response: Response = None, request: Request = None, db: Session = Depends(get_db)):
    ip = request.client.host if request else "unknown"
    username = form_data.username

    try:
        _check_login_rate(ip, username)
    except HTTPException:
        raise

    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        _user_attempts[username].append(time.time())
        logger.warning("Failed login for user %s from %s", username, ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    _user_attempts[username] = []
    if username in _locked_users:
        del _locked_users[username]

    access_token = create_access_token(data={"sub": user.username})
    max_age = ACCESS_TOKEN_EXPIRE_MINUTES * 60
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=os.getenv("RENDER", "") or not os.getenv("DEV"),
    )
    logger.info("Successful login for user %s from %s", username, ip)
    return TokenResponse(access_token=access_token, username=user.username)


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key="access_token", httponly=True, samesite="lax")
    return {"message": "Logged out"}


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {"username": current_user.username}
