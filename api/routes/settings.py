from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from api.auth import get_current_user
from api.models import User, Setting, get_db
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api", tags=["settings"])


class SettingsUpdate(BaseModel):
    delay_between_emails: Optional[int] = None
    max_emails_per_run: Optional[int] = None
    email_1_delay_days: Optional[int] = None
    email_2_delay_days: Optional[int] = None
    email_3_delay_days: Optional[int] = None
    gmail_address: Optional[str] = None
    rishav_phone: Optional[str] = None


DEFAULT_SETTINGS = {
    "delay_between_emails": "30",
    "max_emails_per_run": "50",
    "email_1_delay_days": "0",
    "email_2_delay_days": "5",
    "email_3_delay_days": "10",
    "gmail_address": "",
    "rishav_phone": "",
}


@router.get("/settings")
def get_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    settings = {}
    for key, default in DEFAULT_SETTINGS.items():
        row = db.query(Setting).filter(Setting.key == key).first()
        settings[key] = row.value if row else default
    return settings


@router.put("/settings")
def update_settings(
    update: SettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    update_dict = update.dict(exclude_none=True)
    for key, value in update_dict.items():
        row = db.query(Setting).filter(Setting.key == key).first()
        if row:
            row.value = str(value)
        else:
            db.add(Setting(key=key, value=str(value)))
    db.commit()
    return {"message": "Settings updated"}
