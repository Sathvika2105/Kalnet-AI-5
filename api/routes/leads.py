from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
from api.auth import get_current_user
from api.models import User
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from pipeline import sheets

router = APIRouter(prefix="/api", tags=["leads"])

# new data model for bulk upload
class NewLead(BaseModel):
    name: str
    email: str
    company: str
    tier: int
    subject_line: str

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


# new endpoint for bulk upload
@router.post("/leads/bulk")
def bulk_upload_leads(leads: List[NewLead], current_user: User = Depends(get_current_user)):
    try:
        formatted_leads_for_sheets = []
        
        for lead in leads:
            # Generate a new lead_id (e.g., L-20260611123456-0)
            new_id = f"L-{datetime.now().strftime('%Y%m%d%H%M%S')}-{len(formatted_leads_for_sheets)}"
            
            row = [
                new_id,                 # col 1: lead_id
                lead.name,              # col 2: name
                lead.email,             # col 3: email
                lead.company,           # col 4: company
                "",                     # col 5: email_sent_at
                0,                      # col 6: sequence_step
                False,                  # col 7: replied
                lead.tier,              # col 8: tier
                lead.subject_line,      # col 9: subject_line
                False                   # col 10: opt_out
            ]
            formatted_leads_for_sheets.append(row)
        
        # Hand off the formatted list to the database module
        result = sheets.bulk_add_leads(formatted_leads_for_sheets)

        if result is False:
            raise HTTPException(status_code=500, detail="Failed to add leads to Google Sheets")

        msg = f"Successfully added {result['added']} lead(s)."
        if result["skipped"] > 0:
            msg += f" {result['skipped']} duplicate(s) skipped."
        
        return {"status": "success", "message": msg, **result}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
