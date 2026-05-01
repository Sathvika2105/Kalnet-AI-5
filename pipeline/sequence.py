"""
sequence.py — Follow-up Sequence Module
Author      : Vishnu
Module       : AI-5 Automated Email Pipeline
Responsibility: Decide which leads receive FOLLOW-UP emails today.

Real pipeline flow (important — read this before editing):
    run.py sends Email 1 immediately when a new lead is added.
    By the time sequence.py runs, sequence_step is already 1.
    This module only handles follow-ups — Email 2 and Email 3.
    It NEVER sends Email 1. That is run.py's job.

Sequence Rules:
    Email 2 -> Day 5  after Email 1 (sequence_step == 1, days_elapsed == 5)
    Email 3 -> Day 10 after Email 1 (sequence_step == 2, days_elapsed == 10)
    STOP    -> if lead has replied at any point
    SKIP    -> sequence_step == 0  (Email 1 not sent yet -- not our job)
    SKIP    -> sequence_step == 3  (all 3 emails already sent -- sequence complete)

Two-condition check (BOTH must be true to send):
    1. days_elapsed matches the schedule (5 or 10)
    2. sequence_step matches what was last sent (1 or 2)
    This prevents double-sending if the pipeline ever re-runs on the same day.

Input  : list of lead dicts (provided by sheets.py -> get_all_leads())
Output : list of dicts with lead info + which email_number to send today
"""

from datetime import date
import logging
import os
import sys

# --------------------------------------------------------------------------
# Windows utf-8 fix
# Force stdout to utf-8 so the logger does not crash on Windows terminals
# that default to cp1252 (which cannot encode characters like the arrow used
# in log messages). This is a no-op on Mac/Linux.
# --------------------------------------------------------------------------
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# --------------------------------------------------------------------------
# Logger setup
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
# Core function
# --------------------------------------------------------------------------

def get_sequence_due_today(leads: list[dict]) -> list[dict]:
    """
    Evaluate every lead and return only those who should receive a
    FOLLOW-UP email today (Email 2 or Email 3 only).

    Email 1 is sent by run.py the moment a lead is created -- this
    function never returns email_number=1.

    Parameters
    ----------
    leads : list[dict]
        Each dict must contain:
            lead_id       (str)  -- unique row identifier from Google Sheets
            name          (str)  -- prospect's full name
            email         (str)  -- prospect's email address
            company       (str)  -- prospect's company name
            email_sent_at (str)  -- ISO date string "YYYY-MM-DD" of first email
            replied       (bool) -- True if lead has already replied
            sequence_step (int)  -- last email number successfully sent
                                   0 = Email 1 not sent yet (run.py hasn't run)
                                   1 = Email 1 sent, awaiting follow-up
                                   2 = Email 2 sent, awaiting final follow-up
                                   3 = Email 3 sent, sequence complete

    Returns
    -------
    list[dict]
        Each dict contains:
            lead_id      (str) -- same as input
            name         (str) -- same as input
            email        (str) -- same as input
            company      (str) -- same as input
            email_number (int) -- 2 or 3 only (never 1)
    """
    today = date.today()
    due_today = []

    logger.info(f"Running follow-up sequence check for {len(leads)} leads on {today}")

    for lead in leads:
        lead_id       = lead.get("lead_id", "unknown")
        name          = lead.get("name", "Unknown")
        sequence_step = int(lead.get("sequence_step", 0) or 0)

        # -- Guard: skip if lead has replied --------------------------------
        if lead.get("replied", False):
            logger.debug(f"SKIP (replied)      -> {name} [{lead_id}]")
            continue

        # -- Guard: skip if Email 1 hasn't been sent yet --------------------
        # sequence_step == 0 means run.py hasn't sent Email 1 yet.
        # That is run.py's job, not ours.
        if sequence_step == 0:
            logger.debug(f"SKIP (step=0, E1 not sent yet) -> {name} [{lead_id}]")
            continue

        # -- Guard: skip if sequence is already complete --------------------
        # sequence_step == 3 means Email 3 (final) was already sent.
        if sequence_step >= 3:
            logger.debug(f"SKIP (step={sequence_step}, sequence complete) -> {name} [{lead_id}]")
            continue

        # -- Guard: skip if email_sent_at is missing or invalid -------------
        raw_date = (lead.get("email_sent_at") or "").strip()
        if not raw_date:
            logger.warning(f"SKIP (no date)      -> {name} [{lead_id}] -- email_sent_at missing")
            continue

        try:
            sent_date = date.fromisoformat(raw_date)
        except ValueError:
            logger.warning(f"SKIP (bad date)     -> {name} [{lead_id}] -- invalid date '{raw_date}'")
            continue

        # -- Days since Email 1 was sent ------------------------------------
        days_elapsed = (today - sent_date).days

        # -- Follow-up decision: check BOTH day AND sequence_step -----------
        #
        # WHY check both?
        #   days_elapsed alone is not enough. If the pipeline re-runs on
        #   the same day (crash recovery, manual trigger), a lead already
        #   at step=2 would get Email 2 sent again on day 5 if we only
        #   check days. The sequence_step acts as an "already done" guard.
        #
        # sequence_step == 1 -> Email 1 was sent, Email 2 not yet sent
        # sequence_step == 2 -> Email 2 was sent, Email 3 not yet sent

        if days_elapsed == 5 and sequence_step == 1:
            email_number = 2          # Follow-up #1

        elif days_elapsed == 10 and sequence_step == 2:
            email_number = 3          # Follow-up #2 (final)

        else:
            logger.debug(
                f"SKIP (day={days_elapsed}, step={sequence_step}) -> {name} [{lead_id}]"
            )
            continue

        logger.info(
            f"DUE  email #{email_number} "
            f"(day={days_elapsed}, step={sequence_step}) "
            f"-> {name} <{lead['email']}> [{lead_id}]"
        )

        due_today.append({
            "lead_id":      lead_id,
            "name":         name,
            "email":        lead.get("email", ""),
            "company":      lead.get("company", ""),
            "email_number": email_number,
        })

    logger.info(f"Sequence check complete -- {len(due_today)} follow-up(s) due today")
    return due_today


# --------------------------------------------------------------------------
# Subject line and body helpers (used by run.py when sending emails)
# --------------------------------------------------------------------------

EMAIL_SUBJECTS = {
    1: "Quick intro - {company}",
    2: "Following up - {company}",
    3: "Last follow-up - {company}",
}

EMAIL_BODIES = {
    1: """\
Hi {name},

I came across {company} and thought there might be a great fit between \
what we do and what your team is working on.

We help businesses automate their outreach and follow-up process so no \
lead falls through the cracks.

Would you be open to a quick 15-minute call this week?

Best,
Team AI-5
""",

    2: """\
Hi {name},

Just wanted to follow up on my earlier email in case it got buried.

We've helped companies like {company} reduce manual outreach time by \
over 60%. I'd love to show you how.

Do you have 15 minutes this week?

Best,
Team AI-5
""",

    3: """\
Hi {name},

I'll keep this short - this is my last follow-up.

If now isn't the right time, no worries at all. If you'd like to \
reconnect in the future, just reply to this email.

Wishing you and the {company} team all the best.

Best,
Team AI-5
""",
}


def get_email_content(lead: dict) -> dict:
    """
    Return the subject and body for a scheduled lead.

    Parameters
    ----------
    lead : dict
        Must contain: name, company, email_number

    Returns
    -------
    dict with keys: subject (str), body (str)
    """
    n = lead.get("email_number", 2)
    subject = EMAIL_SUBJECTS.get(n, "Hello from Team AI-5").format(
        company=lead.get("company", "your company")
    )
    body = EMAIL_BODIES.get(n, "").format(
        name=lead.get("name", "there"),
        company=lead.get("company", "your company"),
    )
    return {"subject": subject, "body": body}


# --------------------------------------------------------------------------
# Manual test runner  --  python sequence.py
# --------------------------------------------------------------------------

if __name__ == "__main__":
    from datetime import timedelta

    today = date.today()

    print("\n" + "=" * 60)
    print("  SEQUENCE.PY -- Manual Test Run")
    print("  (follow-ups only: Email 2 and Email 3)")
    print("=" * 60)

    dummy_leads = [

        # -- SHOULD be included ---------------------------------------------

        {   # Day 5, step=1 -> Email 2 due
            "lead_id": "row_1", "name": "Arjun Mehta",
            "email": "arjun@startup.io", "company": "Startup IO",
            "email_sent_at": str(today - timedelta(days=5)),
            "replied": False, "sequence_step": 1,
        },
        {   # Day 10, step=2 -> Email 3 due
            "lead_id": "row_2", "name": "Divya Nair",
            "email": "divya@bigco.com", "company": "BigCo",
            "email_sent_at": str(today - timedelta(days=10)),
            "replied": False, "sequence_step": 2,
        },

        # -- SHOULD be SKIPPED ----------------------------------------------

        {   # replied=True -> always skip
            "lead_id": "row_3", "name": "Kiran Patel",
            "email": "kiran@replied.com", "company": "Replied Inc",
            "email_sent_at": str(today - timedelta(days=5)),
            "replied": True, "sequence_step": 1,
        },
        {   # sequence_step=0 -> Email 1 not sent yet, run.py's job
            "lead_id": "row_4", "name": "Priya Sharma",
            "email": "priya@techcorp.com", "company": "TechCorp",
            "email_sent_at": str(today),
            "replied": False, "sequence_step": 0,
        },
        {   # sequence_step=3 -> sequence already complete
            "lead_id": "row_5", "name": "Meera Rao",
            "email": "meera@done.com", "company": "Done Corp",
            "email_sent_at": str(today - timedelta(days=12)),
            "replied": False, "sequence_step": 3,
        },
        {   # Day 5 but step=2 -> already sent Email 2, would be double-send
            "lead_id": "row_6", "name": "Ravi Kumar",
            "email": "ravi@skip.com", "company": "Skip Ltd",
            "email_sent_at": str(today - timedelta(days=5)),
            "replied": False, "sequence_step": 2,
        },
        {   # Day 3 -> not scheduled yet
            "lead_id": "row_7", "name": "Sneha Iyer",
            "email": "sneha@wait.com", "company": "Wait Co",
            "email_sent_at": str(today - timedelta(days=3)),
            "replied": False, "sequence_step": 1,
        },
        {   # Missing email_sent_at
            "lead_id": "row_8", "name": "Vikram Das",
            "email": "vikram@nodate.com", "company": "NoDate",
            "email_sent_at": "", "replied": False, "sequence_step": 1,
        },
    ]

    results = get_sequence_due_today(dummy_leads)

    print(f"\nFollow-ups due today: {len(results)}\n")
    print(f"{'Email#':<8} {'Name':<18} {'Email':<28} {'Step was'}")
    print("-" * 65)
    for r in results:
        orig_step = next(l["sequence_step"] for l in dummy_leads if l["lead_id"] == r["lead_id"])
        print(f"  #{r['email_number']:<5} {r['name']:<18} {r['email']:<28} step={orig_step}")

    print("\n--- Email previews ---\n")
    for r in results:
        content = get_email_content(r)
        print(f"To      : {r['name']} <{r['email']}>")
        print(f"Subject : {content['subject']}")
        print(f"Body    : {content['body'][:80].strip()}...")
        print()

    # -- Assertions ---------------------------------------------------------
    result_ids = [r["lead_id"] for r in results]

    assert "row_1" in result_ids,     "FAIL: row_1 (day5, step1) must get Email 2"
    assert "row_2" in result_ids,     "FAIL: row_2 (day10, step2) must get Email 3"
    assert "row_3" not in result_ids, "FAIL: row_3 (replied) must be skipped"
    assert "row_4" not in result_ids, "FAIL: row_4 (step=0) must be skipped -- Email 1 is run.py's job"
    assert "row_5" not in result_ids, "FAIL: row_5 (step=3) must be skipped -- sequence complete"
    assert "row_6" not in result_ids, "FAIL: row_6 (day5 but step=2) must be skipped -- would double-send"
    assert "row_7" not in result_ids, "FAIL: row_7 (day3) must be skipped -- not scheduled"
    assert "row_8" not in result_ids, "FAIL: row_8 (no date) must be skipped"

    email_nums = {r["lead_id"]: r["email_number"] for r in results}
    assert email_nums["row_1"] == 2,  "FAIL: row_1 should receive email #2"
    assert email_nums["row_2"] == 3,  "FAIL: row_2 should receive email #3"
    assert 1 not in email_nums.values(), "FAIL: Email #1 must NEVER be returned by sequence.py"

    print("=" * 60)
    print("  ALL ASSERTIONS PASSED")
    print("  Email 1 never returned. Only follow-ups 2 and 3.")
    print("=" * 60 + "\n")
