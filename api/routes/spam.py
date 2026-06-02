from fastapi import APIRouter, Depends
from pydantic import BaseModel
from api.auth import get_current_user
from api.models import User
from pipeline.spam_check import analyze_email
from pipeline.sequence import EMAIL_SUBJECTS, EMAIL_BODIES

router = APIRouter(prefix="/api", tags=["spam"])


class CustomEmail(BaseModel):
    subject: str = ""
    body: str = ""


@router.get("/spam-score")
def get_spam_scores(current_user: User = Depends(get_current_user)):
    templates = []
    for step in [1, 2, 3]:
        subject = EMAIL_SUBJECTS.get(step, "").format(company="Acme Corp")
        body = EMAIL_BODIES.get(step, "").format(name="John", company="Acme Corp")
        result = analyze_email(subject, body)
        templates.append({
            "step": step,
            "subject": subject,
            "body": body,
            "score": result["score"],
            "label": result["label"],
            "findings": result["findings"],
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
