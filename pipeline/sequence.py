"""
sequence.py -- Follow-up Sequence Module
Author      : Vishnu
Module       : AI-5 Automated Email Pipeline
Responsibility: Decide which leads receive emails today based on
                the number of days since their first email was sent.
 
Sequence Rules (unchanged from original spec):
    Email 1 -> Day 0  (new lead, first contact)      [handled by run.py]
    Email 2 -> Day 5  (follow-up #1, only if no reply)
    Email 3 -> Day 10 (follow-up #2 / final, only if no reply)
    STOP    -> if lead has replied at any point
 
How it works with real data:
    run.py calls sheets.get_all_leads() -> passes list to get_sequence_due_today()
    This function decides who gets emailed today based on days elapsed + sequence_step.
    run.py then calls send_email() for each result, then sheets.mark_email_sent().
 
Run with real data:
    python sequence.py --live
 
Run with dummy data (no Sheets connection needed):
    python sequence.py
"""
 
import logging
import os
import sys
from datetime import date, timedelta
 
# --------------------------------------------------------------------------
# Windows UTF-8 fix
# --------------------------------------------------------------------------
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
 
# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/sequence.log", mode="a", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)
 
 
# --------------------------------------------------------------------------
# Email templates
# --------------------------------------------------------------------------
 
EMAIL_SUBJECTS = {
    1: "Quick intro - {company}",
    2: "Following up - {company}",
    3: "Last follow-up - {company}",
}
 
EMAIL_BODIES = {
    1: (
        "Hi {name},\n\n"
        "I came across {company} and thought there might be a great fit "
        "between what we do and what your team is working on.\n\n"
        "We help businesses automate their outreach and follow-up process "
        "so no lead falls through the cracks.\n\n"
        "Would you be open to a quick 15-minute call this week?\n\n"
        "Best,\nTeam AI-5"
    ),
    2: (
        "Hi {name},\n\n"
        "Just wanted to follow up on my earlier email in case it got buried.\n\n"
        "We've helped companies like {company} reduce manual outreach time "
        "by over 60%. I'd love to show you how.\n\n"
        "Do you have 15 minutes this week?\n\n"
        "Best,\nTeam AI-5"
    ),
    3: (
        "Hi {name},\n\n"
        "I'll keep this short - this is my last follow-up.\n\n"
        "If now isn't the right time, no worries at all. "
        "If you'd like to reconnect in the future, just reply to this email.\n\n"
        "Wishing you and the {company} team all the best.\n\n"
        "Best,\nTeam AI-5"
    ),
}
 
 
# --------------------------------------------------------------------------
# Core function
# --------------------------------------------------------------------------
 
def get_sequence_due_today(leads: List[Dict]) -> List[Dict]:
    """
    Evaluate every lead and return only those who should receive an email today.
 
    Uses TWO conditions to decide (not just days alone):
        days_elapsed == 0  AND sequence_step == 0  -> Email 1
        days_elapsed == 5  AND sequence_step == 1  -> Email 2
        days_elapsed == 10 AND sequence_step == 2  -> Email 3
 
    Checking sequence_step alongside days_elapsed prevents double-sends
    if the pipeline restarts or runs twice in one day.
 
    Parameters
    ----------
    leads : list[dict]
        Each dict must contain:
            lead_id       (str)  -- unique row identifier from Google Sheets
            name          (str)  -- prospect's full name
            email         (str)  -- prospect's email address
            company       (str)  -- prospect's company name
            email_sent_at (str)  -- ISO date "YYYY-MM-DD" of Email 1 send date
                                    (empty string if Email 1 not sent yet)
            replied       (bool) -- True if lead has already replied
            sequence_step (int)  -- last email number sent (0 if none yet)
 
    Returns
    -------
    list[dict]
        Each dict contains:
            lead_id      (str)
            name         (str)
            email        (str)
            company      (str)
            email_number (int) -- which email to send: 1, 2, or 3
    """
    today     = date.today()
    due_today = []
 
    logger.info("Sequence check started -- %d leads -- date: %s", len(leads), today)
 
    for lead in leads:
        lead_id       = lead.get("lead_id", "unknown")
        name          = lead.get("name", "Unknown")
        sequence_step = int(lead.get("sequence_step", 0) or 0)
 
        # -- Guard: skip if lead has replied --------------------------------
        if lead.get("replied", False):
            logger.debug("SKIP (replied)      -- %s [%s]", name, lead_id)
            continue
 
        # -- Guard: skip if sequence already complete ----------------------
        if sequence_step >= 3:
            logger.debug("SKIP (complete)     -- %s [%s] step=%d", name, lead_id, sequence_step)
            continue
 
        # -- Branch A: brand-new lead (no email sent yet) ------------------
        # email_sent_at is empty, sequence_step == 0
        raw_date = (lead.get("email_sent_at") or "").strip()
 
        if not raw_date and sequence_step == 0:
            # Email 1: lead was just added to the sheet today
            logger.info(
                "DUE  email #1 (new lead)           -- %s <%s> [%s]",
                name, lead.get("email", ""), lead_id,
            )
            due_today.append({
                "lead_id":      lead_id,
                "name":         name,
                "email":        lead.get("email", ""),
                "company":      lead.get("company", ""),
                "email_number": 1,
            })
            continue
 
        # -- Guard: skip if date is missing but step != 0 ------------------
        if not raw_date:
            logger.warning(
                "SKIP (no date)      -- %s [%s] step=%d",
                name, lead_id, sequence_step,
            )
            continue
 
        # -- Parse date -----------------------------------------------------
        try:
            sent_date = date.fromisoformat(raw_date)
        except ValueError:
            logger.warning(
                "SKIP (bad date)     -- %s [%s] date='%s'",
                name, lead_id, raw_date,
            )
            continue
 
        # -- Guard: future date --------------------------------------------
        if sent_date > today:
            logger.warning(
                "SKIP (future date)  -- %s [%s] date='%s'",
                name, lead_id, raw_date,
            )
            continue
 
        # -- Days since Email 1 --------------------------------------------
        days_elapsed = (today - sent_date).days
 
        # -- Sequence decision: day AND step must both match ---------------
        if days_elapsed == 5 and sequence_step == 1:
            email_number = 2
 
        elif days_elapsed == 10 and sequence_step == 2:
            email_number = 3
 
        else:
            logger.debug(
                "SKIP (day=%d step=%d) -- %s [%s]",
                days_elapsed, sequence_step, name, lead_id,
            )
            continue
 
        logger.info(
            "DUE  email #%d (day=%d, step=%d) -- %s <%s> [%s]",
            email_number, days_elapsed, sequence_step,
            name, lead.get("email", ""), lead_id,
        )
 
        due_today.append({
            "lead_id":      lead_id,
            "name":         name,
            "email":        lead.get("email", ""),
            "company":      lead.get("company", ""),
            "email_number": email_number,
        })
 
    logger.info(
        "Sequence check complete -- %d email(s) due today", len(due_today)
    )
    return due_today
 
 
# --------------------------------------------------------------------------
# Email content helper
# --------------------------------------------------------------------------
 
def get_email_content(lead: Dict) -> Dict:
    """
    Return the subject and body for a lead due for an email today.
 
    Parameters
    ----------
    lead : dict  Must contain: name, company, email_number
 
    Returns
    -------
    dict with keys: subject (str), body (str)
    """
    n       = int(lead.get("email_number", 1))
    name    = lead.get("name", "there")
    company = lead.get("company", "your company")
 
    subject = EMAIL_SUBJECTS.get(n, "Hello from Team AI-5").format(company=company)
    body    = EMAIL_BODIES.get(n, "").format(name=name, company=company)
 
    return {"subject": subject, "body": body}
 
 
# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------
 
def _run_with_real_data() -> None:
    """Fetch real leads from Google Sheets and run the sequence check."""
    from sheets import get_all_leads
 
    print("\n" + "=" * 60)
    print("  SEQUENCE.PY -- Live Run (Real Google Sheets Data)")
    print("=" * 60)
 
    leads   = get_all_leads()
    results = get_sequence_due_today(leads)
 
    print(f"\nLeads due for email today: {len(results)}\n")
    if results:
        print(f"  {'#':<4} {'Name':<20} {'Email':<30}")
        print("  " + "-" * 58)
        for r in results:
            print(f"  {r['email_number']:<4} {r['name']:<20} {r['email']:<30}")
        print()
 
 
def _run_with_dummy_data() -> None:
    """Run the sequence check against hardcoded dummy leads (no Sheets needed)."""
    today = date.today()
 
    print("\n" + "=" * 60)
    print("  SEQUENCE.PY -- Dummy Data Test")
    print("=" * 60)
 
    dummy_leads = [
        # -- SHOULD be included -------------------------------------------
        {   # Email 1: brand new, no email_sent_at yet
            "lead_id": "row_1", "name": "Priya Sharma",
            "email": "priya@techcorp.com", "company": "TechCorp",
            "email_sent_at": "", "replied": False, "sequence_step": 0,
        },
        {   # Email 2: Day 5, step=1
            "lead_id": "row_2", "name": "Arjun Mehta",
            "email": "arjun@startup.io", "company": "Startup IO",
            "email_sent_at": str(today - timedelta(days=5)),
            "replied": False, "sequence_step": 1,
        },
        {   # Email 3: Day 10, step=2
            "lead_id": "row_3", "name": "Divya Nair",
            "email": "divya@bigco.com", "company": "BigCo",
            "email_sent_at": str(today - timedelta(days=10)),
            "replied": False, "sequence_step": 2,
        },
        # -- SHOULD be SKIPPED --------------------------------------------
        {   # replied=True
            "lead_id": "row_4", "name": "Kiran Patel",
            "email": "kiran@replied.com", "company": "Replied Inc",
            "email_sent_at": str(today - timedelta(days=5)),
            "replied": True, "sequence_step": 1,
        },
        {   # wrong day (day 3)
            "lead_id": "row_5", "name": "Meera Rao",
            "email": "meera@random.com", "company": "Random Corp",
            "email_sent_at": str(today - timedelta(days=3)),
            "replied": False, "sequence_step": 1,
        },
        {   # day 5 but step=2 -- double-send guard
            "lead_id": "row_6", "name": "Ravi Kumar",
            "email": "ravi@skip.com", "company": "Skip Ltd",
            "email_sent_at": str(today - timedelta(days=5)),
            "replied": False, "sequence_step": 2,
        },
        {   # bad date format
            "lead_id": "row_7", "name": "Sneha Iyer",
            "email": "sneha@bad.com", "company": "BadDate Co",
            "email_sent_at": "not-a-date", "replied": False, "sequence_step": 1,
        },
    ]
 
    results = get_sequence_due_today(dummy_leads)
 
    print(f"\nLeads due for email today: {len(results)}\n")
    print(f"  {'#':<4} {'Name':<20} {'Email':<30}")
    print("  " + "-" * 58)
    for r in results:
        print(f"  {r['email_number']:<4} {r['name']:<20} {r['email']:<30}")
 
    print("\n--- Email previews ---\n")
    for r in results:
        c = get_email_content(r)
        print(f"  To      : {r['name']} <{r['email']}>")
        print(f"  Subject : {c['subject']}")
        print(f"  Body    : {c['body'][:70].strip()}...")
        print()
 
    # Assertions
    ids = [r["lead_id"] for r in results]
    assert "row_1" in ids,     "FAIL: row_1 (Email 1) should be included"
    assert "row_2" in ids,     "FAIL: row_2 (Email 2) should be included"
    assert "row_3" in ids,     "FAIL: row_3 (Email 3) should be included"
    assert "row_4" not in ids, "FAIL: row_4 (replied) must be skipped"
    assert "row_5" not in ids, "FAIL: row_5 (day 3) must be skipped"
    assert "row_6" not in ids, "FAIL: row_6 (double-send guard) must be skipped"
    assert "row_7" not in ids, "FAIL: row_7 (bad date) must be skipped"
 
    nums = {r["lead_id"]: r["email_number"] for r in results}
    assert nums["row_1"] == 1, "FAIL: row_1 must get Email 1"
    assert nums["row_2"] == 2, "FAIL: row_2 must get Email 2"
    assert nums["row_3"] == 3, "FAIL: row_3 must get Email 3"
 
    print("=" * 60)
    print("  ALL ASSERTIONS PASSED")
    print("=" * 60 + "\n")
 
 
if __name__ == "__main__":
    if "--live" in sys.argv:
        _run_with_real_data()
    else:
        _run_with_dummy_data()
