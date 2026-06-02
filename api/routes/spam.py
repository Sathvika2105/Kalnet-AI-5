from fastapi import APIRouter, Depends
from pydantic import BaseModel
from api.auth import get_current_user
from api.models import User
from pipeline.spam_check import analyze_email
from pipeline import sheets

router = APIRouter(prefix="/api", tags=["spam"])


class CustomEmail(BaseModel):
    subject: str = ""
    body: str = ""


@router.get("/spam-score")
def get_spam_scores(current_user: User = Depends(get_current_user)):
    leads = sheets.get_all_leads()

    by_step = {1: [], 2: [], 3: []}
    for lead in leads:
        step = lead.get("sequence_step", 0)
        if step not in (1, 2, 3):
            continue

        subject = lead.get("subject_line", "")
        body = lead.get("email_body", "")

        if not subject:
            continue

        by_step[step].append({
            "lead_id": lead.get("lead_id", ""),
            "name": lead.get("name", ""),
            "email": lead.get("email", ""),
            "company": lead.get("company", ""),
            "subject": subject,
            "body": body,
        })

    templates = []
    for step in [1, 2, 3]:
        recipients = by_step[step]
        if not recipients:
            continue

        scored = []
        for r in recipients:
            result = analyze_email(r["subject"], r["body"])
            scored.append({
                "lead_id": r["lead_id"],
                "name": r["name"],
                "email": r["email"],
                "company": r["company"],
                "score": result["score"],
                "label": result["label"],
                "findings": result["findings"],
            })

        avg_score = round(sum(s["score"] for s in scored) / len(scored)) if scored else 0
        worst = max(scored, key=lambda s: s["score"]) if scored else None
        best = min(scored, key=lambda s: s["score"]) if scored else None

        templates.append({
            "step": step,
            "recipient_count": len(recipients),
            "avg_score": avg_score,
            "worst": worst,
            "best": best,
            "recipients": scored,
        })

    return {"templates": templates}


@router.post("/spam-score")
def check_custom_email(
    email: CustomEmail,
    current_user: User = Depends(get_current_user),
):
    result = analyze_email(email.subject, email.body)
    return {
        "subject": email.subject,
        "body": email.body,
        "score": result["score"],
        "label": result["label"],
        "findings": result["findings"],
    }
