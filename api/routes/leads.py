from fastapi import APIRouter, Depends, Query
from typing import Optional
from api.auth import get_current_user
from api.models import User
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from pipeline import sheets

router = APIRouter(prefix="/api", tags=["leads"])


@router.get("/leads")
def get_leads(
    replied: Optional[str] = None,
    opt_out: Optional[str] = None,
    step: Optional[int] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    leads = sheets.get_all_leads()

    if replied == "true":
        leads = [l for l in leads if l.get("replied")]
    elif replied == "false":
        leads = [l for l in leads if not l.get("replied")]

    if opt_out == "true":
        leads = [l for l in leads if l.get("opt_out")]
    elif opt_out == "false":
        leads = [l for l in leads if not l.get("opt_out")]

    if step is not None:
        leads = [l for l in leads if l.get("sequence_step") == step]

    if search:
        search_lower = search.lower()
        leads = [l for l in leads if
                 search_lower in (l.get("name", "").lower()) or
                 search_lower in (l.get("email", "").lower()) or
                 search_lower in (l.get("company", "").lower())]

    return {"leads": leads, "total": len(leads)}


@router.get("/leads/{lead_id}")
def get_lead(lead_id: str, current_user: User = Depends(get_current_user)):
    lead = sheets.get_lead_by_id(lead_id)
    if not lead:
        return {"error": "Lead not found"}, 404
    return lead
