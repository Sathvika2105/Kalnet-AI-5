from fastapi import APIRouter, Depends
from api.auth import get_current_user
from api.models import User

from pipeline import sheets
from analytics import report

router = APIRouter(prefix="/api", tags=["metrics"])


@router.get("/metrics")
def get_metrics(current_user: User = Depends(get_current_user)):
    leads = sheets.get_all_leads()
    analytics_data = [{
        "lead_id": l.get("lead_id"),
        "email_sent_at": l.get("email_sent_at"),
        "replied": l.get("replied"),
        "tier": l.get("tier"),
        "subject_line": l.get("subject_line"),
    } for l in leads]

    metrics = report.generate_metrics(analytics_data)

    opt_out_count = sum(1 for l in leads if l.get("opt_out"))
    pending_count = sum(1 for l in leads if not l.get("email_sent_at") and not l.get("replied") and not l.get("opt_out"))

    return {
        "total_leads": len(leads),
        "emails_sent": metrics["total_sent"],
        "total_replies": metrics["total_replies"],
        "reply_rate": metrics["reply_rate"],
        "opt_outs": opt_out_count,
        "pending": pending_count,
        "tier_breakdown": metrics["tier_breakdown"],
    }
