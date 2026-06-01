from fastapi import APIRouter, Depends
from api.auth import get_current_user
from api.models import User
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from pipeline import sheets
from analytics import report

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/analytics")
def get_analytics(current_user: User = Depends(get_current_user)):
    leads = sheets.get_all_leads()

    analytics_data = [{
        "lead_id": l.get("lead_id"),
        "email_sent_at": l.get("email_sent_at"),
        "replied": l.get("replied"),
        "tier": l.get("tier"),
        "subject_line": l.get("subject_line"),
    } for l in leads]

    metrics = report.generate_metrics(analytics_data)

    step_counts = {}
    for l in leads:
        if l.get("email_sent_at"):
            step = l.get("sequence_step", 0)
            step_counts[step] = step_counts.get(step, 0) + 1

    return {
        "overview": metrics,
        "sequence_steps": step_counts,
    }


@router.get("/subject-lines")
def get_subject_lines(current_user: User = Depends(get_current_user)):
    leads = sheets.get_all_leads()

    analytics_data = [{
        "lead_id": l.get("lead_id"),
        "email_sent_at": l.get("email_sent_at"),
        "replied": l.get("replied"),
        "tier": l.get("tier"),
        "subject_line": l.get("subject_line"),
    } for l in leads]

    metrics = report.generate_metrics(analytics_data)

    return {"subject_lines": metrics.get("best_subjects", [])}
