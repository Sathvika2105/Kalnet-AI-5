from fastapi import APIRouter, Depends
from api.auth import get_current_user
from api.models import User

from pipeline import sheets

router = APIRouter(prefix="/api", tags=["replies"])


@router.get("/replies")
def get_replies(current_user: User = Depends(get_current_user)):
    leads = sheets.get_all_leads()
    replied = [l for l in leads if l.get("replied")]

    positive = [l for l in replied if not l.get("opt_out")]
    unsubscribed = [l for l in replied if l.get("opt_out")]

    return {
        "replies": replied,
        "total": len(replied),
        "positive": len(positive),
        "unsubscribed": len(unsubscribed),
    }
