from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
from api.models import User, get_db
from api.auth import verify_password, create_access_token, hash_password, get_current_user
from api.config import ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter(prefix="/api/auth", tags=["auth"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class RegisterRequest(BaseModel):
    username: str
    password: str


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), response: Response = None, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    access_token = create_access_token(data={"sub": user.username})
    max_age = ACCESS_TOKEN_EXPIRE_MINUTES * 60
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
    )
    return TokenResponse(access_token=access_token, username=user.username)


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key="access_token", httponly=True, samesite="lax")
    return {"message": "Logged out"}


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {"username": current_user.username}


@router.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == req.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    user = User(username=req.username, password_hash=hash_password(req.password))
    db.add(user)
    db.commit()
    return {"message": "User created"}
