"""
sequence.py -- Follow-up Sequence Module (Enterprise Edition)
Author      : Vishnu  |  Enterprise layer: KALNET Engineering
Module       : KALNET Automated Email Pipeline
Responsibility: Decide which leads receive emails today based on
                the number of days since their first email was sent.

Sequence Rules (UPDATED delays, logic unchanged):
    Email 1 -> Day 0  (new lead, first contact)      [handled by run.py]
    Email 2 -> Day 2  (follow-up #1, only if no reply)  ← was Day 5
    Email 3 -> Day 7  (follow-up #2 / final, only if no reply) ← was Day 10
    STOP    -> if lead has replied at any point

How it works with real data (UNCHANGED):
    run.py calls sheets.get_all_leads() -> passes list to get_sequence_due_today()
    This function decides who gets emailed today based on days elapsed + sequence_step.
    run.py then calls send_email() for each result, then sheets.mark_email_sent().

Run with real data:
    python sequence.py --live

Run with dummy data (no Sheets connection needed):
    python sequence.py

─────────────────────────────────────────────────────────────────────────────
ENTERPRISE LAYER SUMMARY
─────────────────────────────────────────────────────────────────────────────
Added in this version (all additive, zero disruption):

  ADVANCED_EMAIL_SUBJECTS  -- dict keyed by intent, version, length
  ADVANCED_EMAIL_BODIES    -- dict keyed by intent, version, length

  get_lead_score(lead)             -- 0-100 engagement score
  get_intent_delay(intent)         -- days to wait before next touch
  get_followup_strategy(lead)      -- workflow + template selection
  should_send_advanced_followup(lead) -- True if advanced logic applies
  get_next_followup_email(lead)    -- returns next template in nurture path
  get_advanced_email_content(lead) -- main entry point; falls back to
                                      get_email_content() on any error

  ── v2 ADDITIONS (non-destructive) ──────────────────────────────────────
  generate_cta_footer(lead_id, base_url)   -- 3 CTA link block per lead
  append_cta_to_body(body, lead_id, ...)   -- appends CTA footer to any body
  handle_cta_response(lead, cta_type)      -- routes CTA click to response email
  get_cta_response_email(lead, cta_type)   -- crafts response for each CTA intent
  move_to_nurture_list(lead)               -- graceful NOT_INTERESTED handler

All new functions:
  • Accept the SAME lead dict contract as get_sequence_due_today()
  • Read optional fields with .get() — missing fields use original logic
  • Are wrapped in try/except — any failure falls through silently
  • Never modify lead state or write to Sheets

Backward compatibility guarantee:
  • get_sequence_due_today() is IDENTICAL to the original (delay constants updated)
  • get_email_content() is IDENTICAL to the original
  • EMAIL_SUBJECTS is IDENTICAL to the original
  • EMAIL_BODIES is IDENTICAL to the original
  • All existing imports, logging, and configuration loading are unchanged
─────────────────────────────────────────────────────────────────────────────
"""

import logging
import os
import sys
import hashlib
from datetime import date, timedelta
from typing import List, Dict, Optional, Tuple
from urllib.parse import quote


# --------------------------------------------------------------------------
# Windows UTF-8 fix  [UNCHANGED]
# --------------------------------------------------------------------------
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# --------------------------------------------------------------------------
# Logging  [UNCHANGED]
# --------------------------------------------------------------------------
os.makedirs("logs", exist_ok=True)
logger = logging.getLogger(__name__)


# ==========================================================================
# ORIGINAL EMAIL TEMPLATES  [COMPLETELY UNCHANGED — DO NOT MODIFY]
# ==========================================================================

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
        "Best,\nTeam KALNET"
    ),
    2: (
        "Hi {name},\n\n"
        "Just wanted to follow up on my earlier email in case it got buried.\n\n"
        "We've helped companies like {company} reduce manual outreach time "
        "by over 60%. I'd love to show you how.\n\n"
        "Do you have 15 minutes this week?\n\n"
        "Best,\nTeam KALNET"
    ),
    3: (
        "Hi {name},\n\n"
        "I'll keep this short - this is my last follow-up.\n\n"
        "If now isn't the right time, no worries at all. "
        "If you'd like to reconnect in the future, just reply to this email.\n\n"
        "Wishing you and the {company} team all the best.\n\n"
        "Best,\nTeam KALNET"
    ),
}


# ==========================================================================
# ENTERPRISE: INTENT CONSTANTS
# [NEW — does not affect any existing code]
# ==========================================================================

class Intent:
    """All recognised intent codes. Read from lead.get('intent')."""
    # ── v2: CTA-response intents (new) ──────────────────────────────────
    INTERESTED_CTA         = "INTERESTED_CTA"           # clicked ✅ Interested
    INTERESTED_NOT_CONVINCED = "INTERESTED_NOT_CONVINCED" # clicked 🤔
    NOT_INTERESTED         = "NOT_INTERESTED"            # clicked ❌ Not Interested
    # High positive
    INTERESTED             = "INTERESTED"
    VERY_INTERESTED        = "VERY_INTERESTED"
    DEMO_REQUEST           = "DEMO_REQUEST"
    PRICING_REQUEST        = "PRICING_REQUEST"
    PROPOSAL_REQUEST       = "PROPOSAL_REQUEST"
    TECHNICAL_DISCUSSION   = "TECHNICAL_DISCUSSION"
    DOCUMENTATION_REQUEST  = "DOCUMENTATION_REQUEST"
    CASE_STUDY_REQUEST     = "CASE_STUDY_REQUEST"
    PILOT_REQUEST          = "PILOT_REQUEST"
    MEETING_REQUEST        = "MEETING_REQUEST"
    # Budget objections
    NO_BUDGET              = "NO_BUDGET"
    BUDGET_FROZEN          = "BUDGET_FROZEN"
    PRICING_OBJECTION      = "PRICING_OBJECTION"
    ROI_CONCERN            = "ROI_CONCERN"
    # Timing
    NOT_NOW                = "NOT_NOW"
    MAYBE_LATER            = "MAYBE_LATER"
    FOLLOW_UP_NEXT_WEEK    = "FOLLOW_UP_NEXT_WEEK"
    FOLLOW_UP_NEXT_MONTH   = "FOLLOW_UP_NEXT_MONTH"
    FOLLOW_UP_NEXT_QUARTER = "FOLLOW_UP_NEXT_QUARTER"
    FOLLOW_UP_NEXT_YEAR    = "FOLLOW_UP_NEXT_YEAR"
    BUSY                   = "BUSY"
    # Competitive / objections
    USING_COMPETITOR       = "USING_COMPETITOR"
    EXISTING_VENDOR        = "EXISTING_VENDOR"
    INTERNAL_SOLUTION      = "INTERNAL_SOLUTION"
    FEATURE_OBJECTION      = "FEATURE_OBJECTION"
    RESOURCE_CONSTRAINT    = "RESOURCE_CONSTRAINT"
    # Risk / process
    SECURITY_CONCERN       = "SECURITY_CONCERN"
    COMPLIANCE_CONCERN     = "COMPLIANCE_CONCERN"
    PROCUREMENT_DELAY      = "PROCUREMENT_DELAY"
    LEGAL_DELAY            = "LEGAL_DELAY"
    # OOO / auto
    OUT_OF_OFFICE          = "OUT_OF_OFFICE"
    VACATION               = "VACATION"
    AUTO_REPLY             = "AUTO_REPLY"
    REFERRAL               = "REFERRAL"
    # Meeting states
    MEETING_BOOKED         = "MEETING_BOOKED"
    MEETING_COMPLETED      = "MEETING_COMPLETED"
    MEETING_MISSED         = "MEETING_MISSED"
    # Deliverability
    SOFT_BOUNCE            = "SOFT_BOUNCE"
    HARD_BOUNCE            = "HARD_BOUNCE"
    # Fallback
    UNKNOWN                = "UNKNOWN"


# ==========================================================================
# KALNET PRODUCTION CONFIGURATION
# [NEW — centralized configuration for all KALNET endpoints and URLs]
# ==========================================================================

KALNET_BASE_URL = os.environ.get(
    "KALNET_BASE_URL",
    "https://www.kalnet.co"
)

KALNET_CTA_BASE_URL = os.environ.get(
    "KALNET_CTA_BASE_URL",
    "https://www.kalnet.co/cta"
)

KALNET_CALENDAR_LINK = os.environ.get(
    "KALNET_CALENDAR_LINK",
    "https://www.kalnet.co/contact"
)

KALNET_MEETING_LINK = os.environ.get(
    "KALNET_MEETING_LINK",
    "https://www.kalnet.co/contact"
)

KALNET_DISCOVERY_LINK = os.environ.get(
    "KALNET_DISCOVERY_LINK",
    "https://www.kalnet.co/contact"
)


# ==========================================================================
# v2: CTA (Call-to-Action) TRACKING UTILITIES
# [NEW — generates unique per-lead tracking URLs for the 3-button CTA footer]
# These functions are pure helpers; they never call external services.
# If base_url is not configured they produce readable placeholder links.
# ==========================================================================

# Default base URL — override via environment variable KALNET_CTA_BASE_URL
_CTA_BASE_URL = KALNET_CTA_BASE_URL

# CTA type tokens — used both in URL params and in response routing
CTA_INTERESTED          = "interested"
CTA_INTERESTED_NOT_CONVINCED = "not_convinced"
CTA_NOT_INTERESTED      = "not_interested"


def _generate_lead_token(lead_id: str, cta_type: str) -> str:
    """
    Generate a deterministic short token for a lead + CTA combination.
    Uses a SHA-256 hash of lead_id+cta_type, truncated to 16 hex chars.
    This ensures unique URLs per lead per CTA without a database call.
    Falls back to a readable placeholder if lead_id is empty.
    
    Security: Safely handles malformed lead IDs and special characters.
    """
    try:
        if not lead_id or not isinstance(lead_id, str):
            return f"unknown_{cta_type}"
        # Sanitize lead_id: remove non-alphanumeric chars to prevent injection
        safe_lead_id = ''.join(c if c.isalnum() else '_' for c in lead_id)[:50]
        raw = f"{safe_lead_id}:{cta_type}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
    except Exception as e:
        logger.warning("_generate_lead_token error: %s", e)
        return f"unknown_{cta_type}"


def generate_cta_footer(
    lead_id: str,
    base_url: str = _CTA_BASE_URL,
) -> str:
    """
    Generate a formatted 3-button CTA footer block for appending to email bodies.

    Produces three unique tracking URLs — one per intent — so that when a
    recipient clicks, the pipeline can detect their intent and route accordingly.

    Parameters
    ----------
    lead_id  : str  — unique lead identifier (used to build tracking tokens)
    base_url : str  — base URL for the tracking endpoint

    Returns
    -------
    str  — formatted CTA block ready to append to any email body.
    Fails gracefully: returns a plain-text fallback if URL generation errors.
    """
    try:
        tok_yes  = _generate_lead_token(lead_id, CTA_INTERESTED)
        tok_hmm  = _generate_lead_token(lead_id, CTA_INTERESTED_NOT_CONVINCED)
        tok_no   = _generate_lead_token(lead_id, CTA_NOT_INTERESTED)

        # URL-encode parameters to safely handle special characters in lead_id
        safe_lead_id = quote(str(lead_id), safe='')
        url_yes  = f"{base_url}?t={tok_yes}&l={safe_lead_id}&a={CTA_INTERESTED}"
        url_hmm  = f"{base_url}?t={tok_hmm}&l={safe_lead_id}&a={CTA_INTERESTED_NOT_CONVINCED}"
        url_no   = f"{base_url}?t={tok_no}&l={safe_lead_id}&a={CTA_NOT_INTERESTED}"

        footer = (
            "\n\n"
            "────────────────────────────────────\n"
            "Quick reply — let us know where you stand:\n\n"
            f"  ✅  Interested — let's talk! → {url_yes}\n"
            f"  🤔  Interested but need more info → {url_hmm}\n"
            f"  ❌  Not interested right now → {url_no}\n"
            "────────────────────────────────────"
        )
        return footer

    except Exception as exc:
        logger.error("generate_cta_footer error for lead %s: %s", lead_id, exc)
        # Graceful plaintext fallback — always returns something
        return (
            "\n\n────────────────────────────────────\n"
            "Quick reply:\n"
            "  ✅ Interested | 🤔 Interested but not convinced | ❌ Not interested\n"
            "────────────────────────────────────"
        )


def append_cta_to_body(
    body: str,
    lead_id: str,
    base_url: str = _CTA_BASE_URL,
) -> str:
    """
    Append the 3-button CTA footer to any email body string.

    This is the single function to call when preparing any email body
    for sending — original, enterprise, or CTA-response emails.
    Idempotent: does not add the footer if it is already present.
    Fails gracefully: returns original body unchanged on any error.

    Parameters
    ----------
    body     : str — existing email body text
    lead_id  : str — unique lead identifier
    base_url : str — CTA tracking endpoint base URL

    Returns
    -------
    str — body with CTA footer appended
    """
    try:
        if not body:
            return body
        # Idempotency guard — don't double-append
        if "✅  Interested" in body or "✅ Interested" in body:
            return body
        cta = generate_cta_footer(lead_id, base_url)
        return body + cta
    except Exception as exc:
        logger.error("append_cta_to_body error for lead %s: %s", lead_id, exc)
        return body  # Always return original body — never raises


# ==========================================================================
# v2: CTA RESPONSE EMAIL TEMPLATES
# [NEW — crafted responses for each of the 3 CTA click types]
# Routing: handle_cta_response() is the entry point.
# ==========================================================================

# ── Calendar / meeting link (configure via environment variable) ───────────
_CALENDAR_LINK  = KALNET_CALENDAR_LINK
_MEETING_LINK   = KALNET_MEETING_LINK
_DISCOVERY_LINK = KALNET_DISCOVERY_LINK


def get_cta_response_email(lead: Dict, cta_type: str) -> Dict:
    """
    Return the subject and body for a CTA-click response email.

    This function is called when a lead clicks one of the three CTA buttons.
    It returns an appropriate, human, persuasive, and professional email
    tailored to the lead's response intent.

    Parameters
    ----------
    lead     : dict — same lead dict used throughout; must have name, company
    cta_type : str  — one of CTA_INTERESTED | CTA_INTERESTED_NOT_CONVINCED |
                      CTA_NOT_INTERESTED

    Returns
    -------
    dict  { "subject": str, "body": str }  — guaranteed, never raises.
    Falls back to a generic positive email on unknown cta_type or error.
    
    Security: Safely handles missing/malformed lead data.
    """
    try:
        # Input validation
        if not lead or not isinstance(lead, dict):
            logger.warning("get_cta_response_email: invalid lead data type")
            lead = {}
        
        if not cta_type or not isinstance(cta_type, str):
            logger.warning("get_cta_response_email: invalid cta_type")
            cta_type = ""
        
        name    = lead.get("name",    "there")
        company = lead.get("company", "your company")
        lead_id = lead.get("lead_id", "")
        
        # Sanitize name and company to prevent injection in email text
        name = str(name).strip()[:100] if name else "there"
        company = str(company).strip()[:100] if company else "your company"

        # ── ✅ INTERESTED ──────────────────────────────────────────────────
        if cta_type == CTA_INTERESTED:
            subject = f"Let's make it happen — {company}"
            body = (
                f"Hi {name},\n\n"
                "That's great to hear — I'm genuinely excited about this.\n\n"
                "The fastest way forward is a quick 20-minute discovery call "
                "where I can walk you through exactly how KALNET would fit into "
                f"{company}'s workflow. No slides, no pressure — just a real "
                "conversation about what matters to your team.\n\n"
                "You can book a time that works for you directly here:\n"
                f"  📅 Book a call: {_CALENDAR_LINK}\n\n"
                "If you'd prefer to start with a live demo, I've got slots "
                "open this week:\n"
                f"  🎯 Schedule a demo: {_MEETING_LINK}\n\n"
                "I'll come fully prepared — just bring your questions.\n\n"
                "Looking forward to speaking with you soon!\n\n"
                "Best,\nTeam KALNET"
            )

        # ── 🤔 INTERESTED BUT NOT CONVINCED ───────────────────────────────
        elif cta_type == CTA_INTERESTED_NOT_CONVINCED:
            subject = f"Fair enough — let me address that, {name}"
            body = (
                f"Hi {name},\n\n"
                "I really appreciate your honesty — and I hear you completely.\n\n"
                "Being 'interested but not convinced' is actually the most "
                "common place smart buyers sit, and it tells me the conversation "
                "is worth continuing.\n\n"
                "Let me share a few things that usually move the needle:\n\n"
                "📊 Real ROI from teams like yours:\n"
                f"   • Companies similar to {company} cut manual follow-up time "
                "by 60% in 90 days\n"
                "   • Average response rates doubled within the first 6 weeks\n"
                "   • Pipeline recovery of 30–40% from leads that were going cold\n\n"
                "🏆 What our customers say:\n"
                '   "We were sceptical at first. Within 2 months, KALNET became '
                'the backbone of our outreach." — Head of Sales, B2B SaaS\n\n'
                "🎯 My suggestion:\n"
                "A 15-minute discovery call — no commitment, no pitch. Just me "
                "understanding your specific situation and you deciding whether "
                "the numbers make sense for you.\n\n"
                f"  📅 Book a discovery call: {_DISCOVERY_LINK}\n\n"
                "Whatever objections or doubts you have, I'd love to address "
                "them directly. What's the biggest thing holding you back?\n\n"
                "Best,\nTeam KALNET"
            )

        # ── ❌ NOT INTERESTED ──────────────────────────────────────────────
        elif cta_type == CTA_NOT_INTERESTED:
            subject = f"No problem at all, {name} — thank you"
            body = (
                f"Hi {name},\n\n"
                "Thank you for letting me know — I genuinely appreciate you "
                "taking the time to respond.\n\n"
                "I completely respect that the timing or the fit isn't right "
                "right now, and I won't keep filling up your inbox.\n\n"
                "I just wanted to say: the door is always open. Markets change, "
                "priorities shift, and teams evolve — and if there ever comes a "
                f"time when KALNET feels like the right conversation for {company}, "
                "all you have to do is reply to this email. No need to start over.\n\n"
                "We'll keep an eye on the industry and reach out only if we "
                "see something genuinely relevant to you — and even then, with "
                "respect for your time.\n\n"
                "Wishing you and the entire team at "
                f"{company} all the very best. It's been a pleasure.\n\n"
                "Warmly,\nTeam KALNET"
            )

        else:
            # Unknown CTA type — safe positive fallback
            logger.warning("get_cta_response_email: unknown cta_type=%s for lead %s",
                           cta_type, lead_id)
            subject = f"Thanks for your response — {company}"
            body = (
                f"Hi {name},\n\n"
                "Thank you for getting back to us!\n\n"
                "I'd love to connect and understand where you are. "
                f"Feel free to book a quick call here: {_CALENDAR_LINK}\n\n"
                "Best,\nTeam KALNET"
            )

        # Append CTA footer to all CTA response emails EXCEPT not_interested
        # (for not_interested we send a clean closing email — no more CTAs)
        if cta_type != CTA_NOT_INTERESTED:
            body = append_cta_to_body(body, lead_id)

        return {"subject": subject, "body": body}

    except Exception as exc:
        logger.error("get_cta_response_email error for lead %s cta=%s: %s",
                     lead.get("lead_id", "?"), cta_type, exc, exc_info=True)
        # Guaranteed safe fallback — never raises
        return {
            "subject": f"Following up — {lead.get('company', 'your company')}",
            "body": (
                f"Hi {lead.get('name', 'there')},\n\n"
                "Thank you for your response! We'd love to connect.\n\n"
                f"Book a call here: {_CALENDAR_LINK}\n\nBest,\nTeam KALNET"
            ),
        }


def handle_cta_response(lead: Dict, cta_type: str) -> Dict:
    """
    Primary entry point for CTA click events.

    Called when the tracking endpoint receives a click from a lead.
    Determines the correct response email and returns it.
    Also updates the lead's intent in the returned dict (non-destructive —
    the caller is responsible for writing to Sheets).

    Parameters
    ----------
    lead     : dict — lead record (as returned by get_sequence_due_today())
    cta_type : str  — CTA_INTERESTED | CTA_INTERESTED_NOT_CONVINCED |
                      CTA_NOT_INTERESTED

    Returns
    -------
    dict  {
        "subject"     : str,
        "body"        : str,
        "new_intent"  : str,   # updated intent to write back to Sheets
        "action"      : str,   # descriptive action for the caller/logger
        "send_email"  : bool,  # True = send the response; False = suppress
    }
    """
    try:
        # Input validation
        if not lead or not isinstance(lead, dict):
            logger.warning("handle_cta_response: invalid lead data")
            lead = {"lead_id": "?"}
        
        if not cta_type or not isinstance(cta_type, str):
            logger.warning("handle_cta_response: invalid cta_type")
            cta_type = ""
        
        lead_id = str(lead.get("lead_id", "?")).strip()[:100]

        # Map CTA type → new Intent
        cta_intent_map = {
            CTA_INTERESTED:           Intent.INTERESTED_CTA,
            CTA_INTERESTED_NOT_CONVINCED: Intent.INTERESTED_NOT_CONVINCED,
            CTA_NOT_INTERESTED:       Intent.NOT_INTERESTED,
        }
        new_intent = cta_intent_map.get(cta_type, Intent.UNKNOWN)

        # Build response email
        email_content = get_cta_response_email(lead, cta_type)

        # Determine action label for logging and caller decisions
        if cta_type == CTA_INTERESTED:
            action = "schedule_meeting"
        elif cta_type == CTA_INTERESTED_NOT_CONVINCED:
            action = "send_persuasion_continue_sequence"
        elif cta_type == CTA_NOT_INTERESTED:
            action = "move_to_nurture_list"
        else:
            action = "send_followup"

        logger.info(
            "handle_cta_response: lead=%s cta=%s new_intent=%s action=%s",
            lead_id, cta_type, new_intent, action
        )

        return {
            "subject":    email_content["subject"],
            "body":       email_content["body"],
            "new_intent": new_intent,
            "action":     action,
            "send_email": True,
        }

    except Exception as exc:
        logger.error("handle_cta_response error for lead %s: %s",
                     lead.get("lead_id", "?"), exc, exc_info=True)
        return {
            "subject":    f"Following up — {lead.get('company', '')}",
            "body":       f"Hi {lead.get('name', 'there')},\n\nThank you for your response!\n\nBest,\nTeam KALNET",
            "new_intent": Intent.UNKNOWN,
            "action":     "send_followup",
            "send_email": True,
        }


def move_to_nurture_list(lead: Dict) -> Dict:
    """
    Handle a NOT_INTERESTED CTA click — move lead to long-term nurture.

    This function NEVER deletes the lead. It returns the metadata needed
    for the caller to move the lead into a 'nurture' segment in Sheets.
    The lead stays available for future re-engagement campaigns.

    Parameters
    ----------
    lead : dict — lead record; must have lead_id

    Returns
    -------
    dict  {
        "lead_id"       : str,
        "action"        : "move_to_nurture",
        "nurture_reason": "not_interested_cta",
        "re_engage_after_days": int,   # recommended wait before any future contact
    }
    Fails gracefully: returns safe defaults on any error.
    
    Security: Safely handles missing/malformed lead data.
    """
    try:
        # Input validation
        if not lead or not isinstance(lead, dict):
            logger.warning("move_to_nurture_list: invalid lead data")
            lead = {}
        
        lead_id = str(lead.get("lead_id", "?")).strip()[:100]
        logger.info("move_to_nurture_list: lead=%s moved to long-term nurture", lead_id)
        return {
            "lead_id":            lead_id,
            "action":             "move_to_nurture",
            "nurture_reason":     "not_interested_cta",
            "re_engage_after_days": 180,   # 6 months — respectful pause
        }
    except Exception as exc:
        logger.error("move_to_nurture_list error: %s", exc)
        return {
            "lead_id":            str(lead.get("lead_id", "?")).strip()[:100] if lead else "?",
            "action":             "move_to_nurture",
            "nurture_reason":     "not_interested_cta",
            "re_engage_after_days": 180,
        }


# ==========================================================================
# ENTERPRISE: ADVANCED EMAIL TEMPLATES
# [NEW — stored separately from EMAIL_SUBJECTS / EMAIL_BODIES]
#
# Key structure:
#   ADVANCED_EMAIL_SUBJECTS[intent][step][version][length][subject_type]
#   ADVANCED_EMAIL_BODIES[intent][step][version][length]
#
# intent  : Intent constant string
# step    : "initial" | "followup_1" | "followup_2" | "followup_3"
#           | "recovery" | "reengagement"
# version : "a" | "b" | "c"
# length  : "short" | "medium" | "long"
# subject_type (subjects only): "direct" | "value" | "curiosity"
#                               | "executive" | "conversational"
#
# All body strings accept {name} and {company} placeholders.
# ==========================================================================

# ── Helper to build a subject block ───────────────────────────────────────
def _subj(direct, value, curiosity, executive, conversational):
    return {
        "direct":        direct,
        "value":         value,
        "curiosity":     curiosity,
        "executive":     executive,
        "conversational": conversational,
    }

# ── Helper to build a full step block (a/b/c × short/medium/long) ─────────
def _step(short_subj, medium_subj, long_subj):
    """Return a/b/c variant dict sharing the same short/medium/long subjects."""
    block = {"short": short_subj, "medium": medium_subj, "long": long_subj}
    return {"a": block, "b": block, "c": block}


# ---------------------------------------------------------------------------
# ADVANCED_EMAIL_SUBJECTS
# ---------------------------------------------------------------------------
ADVANCED_EMAIL_SUBJECTS = {

    Intent.INTERESTED: {
        "initial": _step(
            _subj("Great — let's take this forward",
                  "How KALNET can help {company} specifically",
                  "What most interested teams ask us next",
                  "{company} | Next steps",
                  "Glad to hear it, {name}"),
            _subj("Next step for {company}",
                  "What KALNET looks like for a team like {company}",
                  "The one thing that changes everything",
                  "{company} | Proposal to follow",
                  "Let's make this easy, {name}"),
            _subj("Following up on your interest in KALNET",
                  "How {company} could cut outreach time by 60%",
                  "What companies like {company} discovered after a demo",
                  "Strategic note for {company} leadership",
                  "Picking up where we left off"),
        ),
        "followup_1": _step(
            _subj("Still interested — here's a case study",
                  "Real results for teams like {company}",
                  "One story you'll want to hear",
                  "{company} | ROI evidence",
                  "Thought you'd find this useful"),
            _subj("A quick follow-up",
                  "The ROI teams like {company} see in 90 days",
                  "Why the timing matters now",
                  "{company} | Business case",
                  "Following up, {name}"),
            _subj("Checking in — KALNET + {company}",
                  "Three outcomes other teams achieved",
                  "The follow-up most teams skip",
                  "{company} | Value summary",
                  "Worth a conversation this week?"),
        ),
        "followup_2": _step(
            _subj("One more thought",
                  "A specific idea for {company}",
                  "Something I should have sent sooner",
                  "{company} | Final thought",
                  "One last thing before I stop"),
            _subj("Last follow-up from me",
                  "The number that changes the conversation at {company}",
                  "What your competitors are doing right now",
                  "{company} | Competitive note",
                  "Closing the loop"),
            _subj("Final note — KALNET for {company}",
                  "What 6 months looks like for a team like {company}",
                  "I'll stop after this — but read it first",
                  "{company} | Strategic close",
                  "Before I go quiet"),
        ),
        "recovery": _step(
            _subj("Checking back in",
                  "Still relevant for {company}?",
                  "Has anything changed since we last spoke?",
                  "{company} | Reconnecting",
                  "Long time — thought of you"),
            _subj("Reconnecting — KALNET + {company}",
                  "What's new since we last connected",
                  "A fresh angle for {company}",
                  "{company} | Strategic update",
                  "One more reach-out"),
            _subj("It's been a while — worth a chat?",
                  "New reasons to revisit KALNET for {company}",
                  "The landscape has changed — here's why it matters",
                  "{company} | Market update",
                  "Hoping the timing is better now"),
        ),
        "reengagement": _step(
            _subj("Still here if you need us",
                  "A lot has changed at KALNET",
                  "Something new worth seeing",
                  "{company} | Year-end check-in",
                  "It's been a while — how are things?"),
            _subj("Reaching out one more time",
                  "What we shipped since we last spoke",
                  "Why teams that said 'not yet' are coming back",
                  "{company} | Re-engagement",
                  "Happy to reconnect whenever you're ready"),
            _subj("One final note from KALNET",
                  "What the market looks like now",
                  "The thing we built that changes the conversation",
                  "{company} | Strategic reconnect",
                  "If the timing is ever right"),
        ),
    },

    Intent.VERY_INTERESTED: {
        "initial": _step(
            _subj("Let's lock in a time",
                  "Accelerating your KALNET onboarding",
                  "This is moving fast — here's what's next",
                  "{company} | Fast-track option",
                  "Excited — let's make it happen"),
            _subj("Calendar link inside",
                  "The fastest path from interest to results",
                  "What comes after 'very interested'",
                  "{company} | Decision timeline",
                  "Let's not let this go cold"),
            _subj("Moving forward — next steps for {company}",
                  "How to go from conversation to outcome in 2 weeks",
                  "The three things we need to align on",
                  "{company} | Proposal timeline",
                  "Here's exactly what I'd suggest"),
        ),
        "followup_1": _step(
            _subj("Following up on our conversation",
                  "Getting {company} to results faster",
                  "The one thing that unlocks everything",
                  "{company} | Next decision step",
                  "Still thinking about this?"),
            _subj("Quick check-in",
                  "The fast track option for {company}",
                  "What other teams in your position did next",
                  "{company} | Momentum note",
                  "Don't let the momentum slip"),
            _subj("A note before the week ends",
                  "From very interested to signed in 7 days — how",
                  "The window that matters",
                  "{company} | Decision note",
                  "Let's keep this moving"),
        ),
        "followup_2": _step(
            _subj("Still here — whenever you're ready",
                  "The deal structure that makes this easy",
                  "What's holding things up?",
                  "{company} | Removing blockers",
                  "Want me to make this simpler?"),
            _subj("One more nudge",
                  "A flexible path for {company}",
                  "The question I should have asked earlier",
                  "{company} | Flexible options",
                  "Happy to adjust to what works for you"),
            _subj("Final follow-up on this",
                  "Three ways to make this work for {company}",
                  "What I'd do if I were in your position",
                  "{company} | Options summary",
                  "Let me know what would make this easier"),
        ),
        "recovery": _step(
            _subj("Things get busy — I get it",
                  "Picking up where we left off",
                  "Whatever happened — it's fine, let's restart",
                  "{company} | Restarting the conversation",
                  "No pressure — still here"),
            _subj("One more try",
                  "The option that might fit better now",
                  "A fresh look at what KALNET can do for {company}",
                  "{company} | Recovery note",
                  "Ready when you are"),
            _subj("Last attempt before I go quiet",
                  "Something that might have changed the calculus",
                  "One thing I didn't show you last time",
                  "{company} | Final offer",
                  "Happy to make this as easy as possible"),
        ),
        "reengagement": _step(
            _subj("Long time — still interested?",
                  "We've improved a lot since we last spoke",
                  "The timing might finally be right",
                  "{company} | Re-engagement",
                  "Thinking of you"),
            _subj("Checking back in",
                  "New features you'll want to see",
                  "What changed at KALNET since we last connected",
                  "{company} | Product update",
                  "One more note"),
            _subj("Still believe there's a fit",
                  "Here's what's different now",
                  "Why I'm reaching back out",
                  "{company} | Final reconnect",
                  "If the stars align"),
        ),
    },

    Intent.DEMO_REQUEST: {
        "initial": _step(
            _subj("Demo confirmed",
                  "Your personalised KALNET walkthrough",
                  "Before our demo — one question",
                  "{company} | Demo confirmed",
                  "Can't wait to show you this"),
            _subj("Demo booked — what to expect",
                  "Making the most of our 15 minutes",
                  "Three things we'll cover in your demo",
                  "{company} | Demo prep",
                  "Looking forward to it"),
            _subj("Your KALNET demo — everything you need",
                  "How to get maximum value from our session",
                  "What most teams ask in the first 5 minutes",
                  "{company} | Executive demo briefing",
                  "Excited to walk you through this"),
        ),
        "followup_1": _step(
            _subj("Following up on the demo",
                  "Next steps after what you saw",
                  "The question most people have after a demo",
                  "{company} | Post-demo next steps",
                  "Hope it was useful — a few thoughts"),
            _subj("Post-demo follow-up",
                  "Turning what you saw into results at {company}",
                  "What other teams did after the demo",
                  "{company} | Implementation path",
                  "Did anything stand out?"),
            _subj("Next steps — KALNET for {company}",
                  "The 3-step path from demo to live",
                  "What I'd recommend based on what you told me",
                  "{company} | Strategic recommendation",
                  "Let's keep the momentum going"),
        ),
        "followup_2": _step(
            _subj("Any questions after the demo?",
                  "Removing blockers for {company}",
                  "The thing that usually gets in the way",
                  "{company} | Blockers and solutions",
                  "Happy to answer anything"),
            _subj("Quick check-in",
                  "How to get started without disrupting anything",
                  "The concern most teams have at this stage",
                  "{company} | Risk-free start",
                  "Just a quick note"),
            _subj("Final follow-up post-demo",
                  "A pilot that de-risks everything for {company}",
                  "What happens if you wait another quarter",
                  "{company} | Decision timeline",
                  "Before I close the loop"),
        ),
        "recovery": _step(
            _subj("Missed you — let's reschedule",
                  "One click to reschedule the {company} demo",
                  "Still want to show you this",
                  "{company} | Reschedule request",
                  "No worries — easy to find another time"),
            _subj("Rescheduling our session",
                  "A flexible demo slot for {company}",
                  "What I had prepared for you",
                  "{company} | Flexible reschedule",
                  "Whenever works for you"),
            _subj("One more reschedule attempt",
                  "Three ways to make this happen for {company}",
                  "What you almost saw last time",
                  "{company} | Final reschedule offer",
                  "Let me work around your schedule"),
        ),
        "reengagement": _step(
            _subj("Ready to try again?",
                  "What's new in KALNET since we last spoke",
                  "We improved based on feedback like yours",
                  "{company} | Product update",
                  "Still here whenever you're ready"),
            _subj("A fresh look at KALNET for {company}",
                  "New features worth a second demo",
                  "The thing that changed since we last connected",
                  "{company} | Re-engagement demo",
                  "Things look different now"),
            _subj("Last note — KALNET + {company}",
                  "What a second demo would show you",
                  "One thing we built that changes the picture",
                  "{company} | Final re-engagement",
                  "If you're open to it"),
        ),
    },

    Intent.NO_BUDGET: {
        "initial": _step(
            _subj("Totally understand — a thought for later",
                  "How to build the case before budget opens",
                  "What companies do while they wait for budget",
                  "{company} | Budget cycle planning",
                  "No worries — staying in touch"),
            _subj("Budget blocked — here's a plan",
                  "Free ROI model for {company}",
                  "The question that gets budget approved faster",
                  "{company} | ROI business case",
                  "Let's make the wait useful"),
            _subj("Got it on budget — a practical next step",
                  "How to get KALNET approved in your next cycle",
                  "Three things teams do to get budget approved",
                  "{company} | Budget readiness",
                  "A useful thing to do right now"),
        ),
        "followup_1": _step(
            _subj("Checking in — any budget movement?",
                  "New ROI data for {company}'s industry",
                  "The number that changes the budget conversation",
                  "{company} | Budget update",
                  "Just a quick check"),
            _subj("Budget cycle update?",
                  "One stat worth sharing with your CFO",
                  "What teams with frozen budgets did next",
                  "{company} | CFO note",
                  "Thinking of you as Q-end approaches"),
            _subj("Following up on the budget situation",
                  "A case study from a company like {company}",
                  "How one team got budget approved in a week",
                  "{company} | Approval story",
                  "Quick note before the quarter ends"),
        ),
        "followup_2": _step(
            _subj("One more thought before I stop",
                  "A pilot that fits in discretionary spend",
                  "The low-cost entry point most teams miss",
                  "{company} | Pilot option",
                  "One last idea"),
            _subj("Last note on budget timing",
                  "A way to start small at {company}",
                  "What if cost isn't the real blocker?",
                  "{company} | Low-risk start",
                  "Happy to get creative on this"),
            _subj("Closing the loop on budget",
                  "Three options for {company} right now",
                  "The option I should have mentioned first",
                  "{company} | Options summary",
                  "Before I go quiet"),
        ),
        "recovery": _step(
            _subj("Budget freed up yet?",
                  "Is the timing better now for {company}?",
                  "Things have changed — worth reconnecting",
                  "{company} | Timing check",
                  "Reaching back out"),
            _subj("Reconnecting on the budget topic",
                  "New pricing options for {company}",
                  "What's different about our offering now",
                  "{company} | New options",
                  "Has anything changed?"),
            _subj("Final note on budget",
                  "The most flexible offer we've ever made",
                  "I have something you didn't see before",
                  "{company} | Final offer",
                  "Last one, I promise"),
        ),
        "reengagement": _step(
            _subj("Long time — checking in",
                  "Budget cycles change — checking if yours did",
                  "Something worth seeing regardless of budget",
                  "{company} | Annual check-in",
                  "Hoping the timing is finally right"),
            _subj("Reconnecting with {company}",
                  "What KALNET looks like at your price point now",
                  "Why companies that said 'no budget' are coming back",
                  "{company} | Re-engagement",
                  "One more note"),
            _subj("A final note from KALNET",
                  "The free option that's always been available",
                  "Something useful whether or not you buy",
                  "{company} | Parting gift",
                  "If the stars align"),
        ),
    },

    Intent.MEETING_MISSED: {
        "initial": _step(
            _subj("We missed each other — easy to reschedule",
                  "Let's find a better time",
                  "Something came up — no problem",
                  "{company} | Reschedule request",
                  "No worries — these things happen"),
            _subj("Missed connection — one click to rebook",
                  "A better slot for the {company} call",
                  "What I had ready for you today",
                  "{company} | Rescheduling",
                  "Happy to find a better time"),
            _subj("Let's try again — reschedule inside",
                  "Making it easy to reconnect",
                  "Two minutes to lock in a better time",
                  "{company} | Flexible reschedule",
                  "Totally understand — here's how to rebook"),
        ),
        "followup_1": _step(
            _subj("One more reschedule attempt",
                  "Still want to connect",
                  "The agenda I had ready for {company}",
                  "{company} | Reschedule — second attempt",
                  "Still keen to connect whenever you're ready"),
            _subj("Trying again",
                  "Three formats that might work better",
                  "What you almost saw in our session",
                  "{company} | Flexible format",
                  "Happy to make this as easy as possible"),
            _subj("Final reschedule attempt",
                  "Everything I had ready for {company}",
                  "Why I think it's still worth your 15 minutes",
                  "{company} | Last reschedule",
                  "One more try before I close this out"),
        ),
        "followup_2": _step(
            _subj("Still here if you want to reconnect",
                  "A lighter format — no meeting needed",
                  "What if we do this async?",
                  "{company} | Async option",
                  "No meeting required — here's an alternative"),
            _subj("Keeping the door open",
                  "A 5-minute async option",
                  "The format that removes all friction",
                  "{company} | No-meeting option",
                  "You choose the format"),
            _subj("Wrapping up — but leaving the door open",
                  "One last way to make this easy",
                  "What I'd send if I could only send one thing",
                  "{company} | Final touch",
                  "No obligation — just a thought"),
        ),
        "recovery": _step(
            _subj("Reconnecting after a long break",
                  "Still worth connecting?",
                  "A lot has changed since we missed each other",
                  "{company} | Recovery note",
                  "Hoping the timing is better now"),
            _subj("Trying one more time",
                  "A fresh look at what we'd cover",
                  "What's new since we last tried to connect",
                  "{company} | Fresh start",
                  "Ready when you are"),
            _subj("Last note from KALNET",
                  "A reason to give this one more shot",
                  "The thing I built specifically for {company}",
                  "{company} | Final recovery",
                  "If you're ever open to it"),
        ),
        "reengagement": _step(
            _subj("Long time — still open to connecting?",
                  "What KALNET looks like now vs when we last spoke",
                  "One thing worth seeing",
                  "{company} | Re-engagement",
                  "Thought of you"),
            _subj("Reaching out one more time",
                  "New format, new reasons",
                  "Why this might make more sense now",
                  "{company} | Second chance",
                  "No pressure"),
            _subj("Final note from the team",
                  "A parting thought for {company}",
                  "The last thing I wanted to share",
                  "{company} | Closing note",
                  "Wishing you all the best either way"),
        ),
    },

    Intent.USING_COMPETITOR: {
        "initial": _step(
            _subj("Completely understand — one thought",
                  "How KALNET compares to what you're using",
                  "What most teams discover after a year with alternatives",
                  "{company} | Competitive comparison",
                  "No hard sell — just one thing"),
            _subj("Understood — keeping the door open",
                  "The difference most teams notice at 6 months",
                  "Why some teams run both",
                  "{company} | Comparison note",
                  "Respect that — a thought anyway"),
            _subj("Happy to stay in touch",
                  "Three things KALNET does that most competitors don't",
                  "The honest comparison you deserve",
                  "{company} | Honest comparison",
                  "Just wanted to leave you with this"),
        ),
        "followup_1": _step(
            _subj("Checking in — how's it going with them?",
                  "What teams usually come back to tell us",
                  "The thing that usually frustrates teams at month 6",
                  "{company} | Check-in",
                  "Just curious"),
            _subj("Quick check-in",
                  "A case study you might find interesting",
                  "What your contract renewal date should trigger",
                  "{company} | Renewal planning",
                  "Worth a quick read"),
            _subj("Following up — competitive landscape note",
                  "How the market has shifted",
                  "What we'd do differently if you gave us a shot",
                  "{company} | Market note",
                  "One thing worth knowing"),
        ),
        "followup_2": _step(
            _subj("Last note — keeping the door open",
                  "The pilot that doesn't disrupt what you have",
                  "A parallel test that takes 1 hour to set up",
                  "{company} | Low-risk trial",
                  "Before I go quiet"),
            _subj("Final follow-up",
                  "Three things we'd prove in a parallel test",
                  "The question worth asking your current vendor",
                  "{company} | Vendor evaluation",
                  "One last thought"),
            _subj("Closing out — staying in touch",
                  "What a side-by-side comparison would show",
                  "The metric most teams wish they'd tracked earlier",
                  "{company} | Final comparison",
                  "Happy to reconnect whenever"),
        ),
        "recovery": _step(
            _subj("Contract renewal coming up?",
                  "Is it time to re-evaluate your current vendor?",
                  "The question worth asking before you renew",
                  "{company} | Renewal planning",
                  "Thinking of you as renewal season approaches"),
            _subj("Reconnecting as renewal approaches",
                  "What we'd show you in 30 minutes",
                  "The honest alternative worth evaluating",
                  "{company} | Evaluation window",
                  "No pressure — just good timing"),
            _subj("One more note before renewal",
                  "Three things we do better — with proof",
                  "The comparison you should run before signing",
                  "{company} | Pre-renewal audit",
                  "Worth a quick conversation"),
        ),
        "reengagement": _step(
            _subj("Long time — still with the same vendor?",
                  "What's changed at KALNET since we last spoke",
                  "The one thing that might make you look again",
                  "{company} | Re-engagement",
                  "Hoping the situation has evolved"),
            _subj("Checking back in",
                  "New reasons to take a second look",
                  "What switched for teams in your position",
                  "{company} | Second look",
                  "Things look different now"),
            _subj("Final note from KALNET",
                  "A parting comparison — no strings",
                  "The thing worth knowing regardless of what you decide",
                  "{company} | Final note",
                  "Whenever the timing is right"),
        ),
    },

    Intent.NOT_NOW: {
        "initial": _step(
            _subj("Understood — checking back in 30 days",
                  "A useful resource while you wait",
                  "What most teams do in the meantime",
                  "{company} | 30-day follow-up",
                  "Totally get it — talk soon"),
            _subj("No rush — I'll follow up later",
                  "Something to keep for when the timing is right",
                  "What to watch for before we reconnect",
                  "{company} | Timing note",
                  "Patience is my strong suit"),
            _subj("Got it — setting a reminder for next month",
                  "A one-pager to keep in your back pocket",
                  "The three signs it's the right time",
                  "{company} | Readiness checklist",
                  "I'll be back when the time is better"),
        ),
        "followup_1": _step(
            _subj("Checking back in — is now better?",
                  "Has anything changed for {company}?",
                  "The timing question worth revisiting",
                  "{company} | Timing check",
                  "Hope the dust has settled"),
            _subj("Following up as promised",
                  "What's changed at KALNET since we last spoke",
                  "A fresh reason to reconsider",
                  "{company} | Update",
                  "As promised — checking back"),
            _subj("Following up after our agreed pause",
                  "New developments worth your attention",
                  "Why the window is better now",
                  "{company} | Re-check",
                  "Back as I said I would be"),
        ),
        "followup_2": _step(
            _subj("One more check — then I'll go quiet",
                  "Still relevant for {company}?",
                  "The question I should ask before giving up",
                  "{company} | Final check",
                  "Last one, I promise"),
            _subj("Final follow-up on timing",
                  "A low-commitment option for {company}",
                  "What teams in your position usually do next",
                  "{company} | Low-commitment option",
                  "Making it easy to say yes or no"),
            _subj("Closing out — for now",
                  "My last note before I stop for good",
                  "One thing worth knowing before I go quiet",
                  "{company} | Closing note",
                  "Thanks for your patience with me"),
        ),
        "recovery":     ADVANCED_EMAIL_SUBJECTS[Intent.INTERESTED]["recovery"]
            if Intent.INTERESTED in {} else _step(  # forward ref guard
            _subj("Reconnecting after a long pause",
                  "Still relevant for {company}?",
                  "What's changed in the market",
                  "{company} | Re-engagement",
                  "Hoping the timing is finally right"),
            _subj("One more note",
                  "A fresh angle for {company}",
                  "The thing that changes at 6 months",
                  "{company} | Recovery",
                  "Worth a conversation?"),
            _subj("Final attempt",
                  "The option that wasn't available before",
                  "What's different this time around",
                  "{company} | Final recovery",
                  "Last note from the team"),
        ),
        "reengagement": _step(
            _subj("Long time — is now better?",
                  "Checking in as the new year starts",
                  "The timing question worth asking again",
                  "{company} | Annual check-in",
                  "Hope things have settled down"),
            _subj("A year on — reconnecting",
                  "What we've built since we last spoke",
                  "Why teams that said 'not now' are coming back",
                  "{company} | Year-end note",
                  "Thinking of you"),
            _subj("Final note from KALNET",
                  "A parting thought for {company}",
                  "Something useful regardless of timing",
                  "{company} | Closing note",
                  "Wishing you all the best"),
        ),
    },

    # ── v2: CTA-driven intent subjects ─────────────────────────────────────
    Intent.INTERESTED_CTA: {
        "initial": _step(
            _subj("Let's book that call — {company}",
                  "Here's your calendar link",
                  "One click to lock in a time",
                  "{company} | Meeting scheduling",
                  "Excited to connect, {name}"),
            _subj("Your discovery call — next steps",
                  "Everything you need to get started",
                  "What we'll cover in 20 minutes",
                  "{company} | Discovery call",
                  "Let's make this happen"),
            _subj("From 'interested' to a real conversation",
                  "How {company} gets from here to results",
                  "The fastest path to a clear decision",
                  "{company} | Fast-track",
                  "Can't wait to speak with you"),
        ),
        "followup_1": _step(
            _subj("Following up on your interest",
                  "Nudging the calendar conversation",
                  "Still keen to connect",
                  "{company} | Meeting follow-up",
                  "Still here whenever you're ready"),
            _subj("Quick follow-up",
                  "The meeting that changes everything",
                  "Picking up where we left off",
                  "{company} | Next step",
                  "Checking back in, {name}"),
            _subj("Let's get this in the diary",
                  "Making it easier to say yes",
                  "One more nudge",
                  "{company} | Diary invite",
                  "One more try"),
        ),
        "followup_2": _step(
            _subj("Last nudge on the meeting",
                  "The call that takes 20 minutes",
                  "One more gentle push",
                  "{company} | Final nudge",
                  "Just one more"),
            _subj("Closing out — but leaving the door open",
                  "Still happy to connect on your schedule",
                  "The standing invite",
                  "{company} | Open invitation",
                  "Whenever works for you"),
            _subj("Going quiet — but here when you need us",
                  "The always-open calendar link",
                  "No pressure — just a standing invitation",
                  "{company} | Standing invite",
                  "We'll be here"),
        ),
        "recovery": _step(
            _subj("Circling back",
                  "Still open to a quick call?",
                  "Hoping the timing is better now",
                  "{company} | Reconnect",
                  "One more attempt"),
            _subj("Reconnecting",
                  "The call we never got to have",
                  "A fresh look at meeting up",
                  "{company} | Recovery call",
                  "Still here"),
            _subj("Final attempt",
                  "The last calendar link I'll send",
                  "If you ever want to talk",
                  "{company} | Final offer",
                  "Whenever you're ready"),
        ),
        "reengagement": _step(
            _subj("Long time — still open to a chat?",
                  "Checking in one more time",
                  "A lot has changed — worth a catch-up",
                  "{company} | Re-engagement",
                  "Thinking of you"),
            _subj("Reaching out one last time",
                  "A standing invitation to connect",
                  "The meeting we never had",
                  "{company} | Final check-in",
                  "No pressure"),
            _subj("Final note from KALNET",
                  "We're always here if the timing shifts",
                  "One last offer to connect",
                  "{company} | Closing note",
                  "Wishing you all the best"),
        ),
    },

    Intent.INTERESTED_NOT_CONVINCED: {
        "initial": _step(
            _subj("Fair enough — let me address that",
                  "The ROI case for {company}",
                  "What usually changes the mind",
                  "{company} | Objection handling",
                  "I hear you, {name}"),
            _subj("Let me make the case",
                  "Three reasons teams like {company} say yes",
                  "The data that usually convinces",
                  "{company} | Business case",
                  "Happy to address your concerns"),
            _subj("Still on the fence? Here's what to look at",
                  "How {company} can evaluate KALNET risk-free",
                  "The honest conversation most vendors won't have",
                  "{company} | Evaluation guide",
                  "Let's be straight with each other"),
        ),
        "followup_1": _step(
            _subj("Addressing the hesitation",
                  "A case study from a team like {company}",
                  "What changed for other doubters",
                  "{company} | Social proof",
                  "Sending something I think will help"),
            _subj("One more thought",
                  "The ROI model for {company}",
                  "Numbers that usually move the needle",
                  "{company} | ROI evidence",
                  "One more piece of evidence"),
            _subj("The thing that usually closes the gap",
                  "What a 30-day pilot shows",
                  "The risk-free way to find out",
                  "{company} | Pilot proposal",
                  "A way to be certain"),
        ),
        "followup_2": _step(
            _subj("Last thought before I stop",
                  "The discovery call that removes all doubt",
                  "15 minutes to get to a clear yes or no",
                  "{company} | Final push",
                  "One last thing"),
            _subj("Final note",
                  "Everything you need to make a confident decision",
                  "The last piece of information",
                  "{company} | Decision kit",
                  "Before I go quiet"),
            _subj("Closing out — with one final offer",
                  "A no-risk way to find out if this fits",
                  "The option most people wish they'd taken sooner",
                  "{company} | Final offer",
                  "Last one from me"),
        ),
        "recovery": _step(
            _subj("Reconnecting — has anything shifted?",
                  "New evidence for {company}",
                  "The question worth revisiting",
                  "{company} | Recovery note",
                  "Checking back in"),
            _subj("One more note",
                  "What's changed at KALNET",
                  "A fresh reason to reconsider",
                  "{company} | Update",
                  "Things look different now"),
            _subj("Final attempt",
                  "The thing that wasn't available before",
                  "A better deal than last time",
                  "{company} | Final recovery",
                  "Last chance"),
        ),
        "reengagement": _step(
            _subj("Long time — still on the fence?",
                  "New proof that might move things",
                  "The timing might be different now",
                  "{company} | Re-engagement",
                  "Thought of you"),
            _subj("Reaching out one more time",
                  "What's changed since we last spoke",
                  "A fresh case for a second look",
                  "{company} | Second look",
                  "No pressure"),
            _subj("Final note from KALNET",
                  "One last piece of evidence",
                  "The parting thought I want to leave you with",
                  "{company} | Closing note",
                  "All the best either way"),
        ),
    },

    Intent.NOT_INTERESTED: {
        "initial": _step(
            _subj("No problem at all — thank you, {name}",
                  "Wishing {company} all the best",
                  "A sincere goodbye from the team",
                  "{company} | Closing note",
                  "Thank you for letting us know"),
            _subj("Completely understood — take care",
                  "Leaving the door open",
                  "The standing invitation",
                  "{company} | Always here",
                  "No worries at all"),
            _subj("Respect that completely — best of luck",
                  "We'll always be here if things change",
                  "The email that leaves no hard feelings",
                  "{company} | Warm goodbye",
                  "Thank you for your time"),
        ),
        "followup_1": _step(
            _subj("Checking in — still not the right time?",
                  "Just a gentle touch to stay on your radar",
                  "Long-term note from KALNET",
                  "{company} | Long-term touch",
                  "No pressure — just staying in touch"),
            _subj("Staying in touch — no agenda",
                  "A useful resource, no strings",
                  "Something that might be helpful regardless",
                  "{company} | Value-add",
                  "Hoping things are going well"),
            _subj("Reaching out one more time — respectfully",
                  "A useful note for {company}",
                  "The thing worth knowing even if you don't buy",
                  "{company} | No-strings note",
                  "Just a thought"),
        ),
        "followup_2": _step(
            _subj("Last note from KALNET — truly",
                  "One final thought for {company}",
                  "The email I promised would be the last",
                  "{company} | Final note",
                  "The last one — I mean it"),
            _subj("Going quiet now — but here if you need us",
                  "The standing door",
                  "Always here if things change",
                  "{company} | Open door",
                  "Wishing you well"),
            _subj("Signing off — with warmth",
                  "All the best from Team KALNET",
                  "The email that closes gracefully",
                  "{company} | Warm close",
                  "Thank you for everything"),
        ),
        "recovery": _step(
            _subj("Circling back — purely to check in",
                  "Has anything changed at {company}?",
                  "A low-pressure check-in",
                  "{company} | Gentle reconnect",
                  "No pressure — just thinking of you"),
            _subj("One more touch — then silence",
                  "A reason to reconnect if timing is right",
                  "The note that respects your decision",
                  "{company} | Respectful recovery",
                  "Whenever the time is right"),
            _subj("Final recovery note",
                  "We're still here if circumstances change",
                  "The door is always open",
                  "{company} | Open door",
                  "Wishing you all the best"),
        ),
        "reengagement": _step(
            _subj("It's been a long time — just checking in",
                  "Has anything shifted for {company}?",
                  "A once-a-year note from KALNET",
                  "{company} | Annual check-in",
                  "Hoping things are going well"),
            _subj("One final note",
                  "We'll always be here — no pressure",
                  "The last reach-out",
                  "{company} | Final note",
                  "Take care"),
            _subj("Closing the book — with gratitude",
                  "Thank you for your time over the years",
                  "The warmest goodbye we can send",
                  "{company} | Grateful close",
                  "All the very best"),
        ),
    },
}

# Forward reference fix for NOT_NOW recovery (reuse INTERESTED recovery subjects)
ADVANCED_EMAIL_SUBJECTS[Intent.NOT_NOW]["recovery"] = \
    ADVANCED_EMAIL_SUBJECTS[Intent.INTERESTED]["recovery"]

# Reuse subject patterns for closely related intents to keep the file size manageable
for _intent in (Intent.MAYBE_LATER, Intent.FOLLOW_UP_NEXT_MONTH,
                Intent.FOLLOW_UP_NEXT_QUARTER, Intent.FOLLOW_UP_NEXT_YEAR):
    ADVANCED_EMAIL_SUBJECTS[_intent] = ADVANCED_EMAIL_SUBJECTS[Intent.NOT_NOW]

for _intent in (Intent.BUDGET_FROZEN, Intent.ROI_CONCERN, Intent.PRICING_OBJECTION):
    ADVANCED_EMAIL_SUBJECTS[_intent] = ADVANCED_EMAIL_SUBJECTS[Intent.NO_BUDGET]

for _intent in (Intent.VERY_INTERESTED, Intent.PRICING_REQUEST,
                Intent.PROPOSAL_REQUEST, Intent.MEETING_REQUEST,
                Intent.TECHNICAL_DISCUSSION, Intent.DOCUMENTATION_REQUEST,
                Intent.CASE_STUDY_REQUEST, Intent.PILOT_REQUEST):
    ADVANCED_EMAIL_SUBJECTS[_intent] = ADVANCED_EMAIL_SUBJECTS[Intent.INTERESTED]

for _intent in (Intent.EXISTING_VENDOR, Intent.INTERNAL_SOLUTION,
                Intent.FEATURE_OBJECTION):
    ADVANCED_EMAIL_SUBJECTS[_intent] = ADVANCED_EMAIL_SUBJECTS[Intent.USING_COMPETITOR]

for _intent in (Intent.SECURITY_CONCERN, Intent.COMPLIANCE_CONCERN,
                Intent.PROCUREMENT_DELAY, Intent.LEGAL_DELAY,
                Intent.RESOURCE_CONSTRAINT, Intent.BUSY,
                Intent.OUT_OF_OFFICE, Intent.VACATION,
                Intent.AUTO_REPLY, Intent.REFERRAL,
                Intent.MEETING_BOOKED, Intent.MEETING_COMPLETED,
                Intent.SOFT_BOUNCE, Intent.HARD_BOUNCE, Intent.UNKNOWN):
    ADVANCED_EMAIL_SUBJECTS[_intent] = ADVANCED_EMAIL_SUBJECTS[Intent.NOT_NOW]

# Map INTERESTED_CTA as alias for meeting scheduling flow
ADVANCED_EMAIL_SUBJECTS[Intent.INTERESTED_CTA] = \
    ADVANCED_EMAIL_SUBJECTS.get(Intent.INTERESTED_CTA,
                                ADVANCED_EMAIL_SUBJECTS[Intent.INTERESTED])


# ---------------------------------------------------------------------------
# ADVANCED_EMAIL_BODIES
# Structure: [intent][step][version][length]
# All strings accept {name} and {company} placeholders.
# v2: All body strings are now more conversational, human, persuasive, and
#     focus on business value, ROI, and meeting/demo scheduling.
# ---------------------------------------------------------------------------

ADVANCED_EMAIL_BODIES = {

    Intent.INTERESTED: {
        "initial": {
            "a": {
                "short": (
                    "Hi {name},\n\n"
                    "Really glad to hear you're interested — that makes my day.\n\n"
                    "The best next step is a quick 20-minute call where I can show you "
                    "exactly how KALNET would work for {company}'s specific situation. "
                    "No generic demos — just a focused conversation about your goals.\n\n"
                    f"Book a time here: {_CALENDAR_LINK}\n\n"
                    "Looking forward to it!\n\nBest,\nTeam KALNET"
                ),
                "medium": (
                    "Hi {name},\n\n"
                    "Thank you — really glad to hear it.\n\n"
                    "To make the most of our conversation, I'd love to understand "
                    "{company}'s current outreach process first. Could you share:\n"
                    "1. How many leads you work per month?\n"
                    "2. What your biggest follow-up bottleneck is?\n\n"
                    "That way I can tailor everything to what matters most to you.\n\n"
                    f"Or simply book a discovery call: {_CALENDAR_LINK}\n\n"
                    "Best,\nTeam KALNET"
                ),
                "long": (
                    "Hi {name},\n\n"
                    "Thank you — I was hoping you'd say that.\n\n"
                    "Here's what I'd suggest as a next step: a focused 20-minute session "
                    "where I walk you through exactly how KALNET would fit into {company}'s "
                    "workflow. No generic slides — I'll map it specifically to your situation.\n\n"
                    "Before we meet, it would help to know:\n"
                    "• What does your current outreach stack look like?\n"
                    "• Where are leads most likely to fall through the cracks today?\n"
                    "• Is this a priority for this quarter, or more of a next-quarter initiative?\n\n"
                    f"Book directly here: {_CALENDAR_LINK}\n"
                    "Or reply with a few times and I'll make it work.\n\n"
                    "Best,\nTeam KALNET"
                ),
            },
            "b": {
                "short": (
                    "Hi {name},\n\n"
                    "Exciting — let's make this happen.\n\n"
                    f"Pick a time that works: {_CALENDAR_LINK}\n\n"
                    "Best,\nTeam KALNET"
                ),
                "medium": (
                    "Hi {name},\n\n"
                    "Wonderful — let's take this forward.\n\n"
                    "I can put together a short, customised overview of how KALNET would "
                    "work for {company} specifically. Takes about 20 minutes and I'll "
                    "leave you with a clear picture of the ROI.\n\n"
                    f"Book here: {_CALENDAR_LINK}\n\nBest,\nTeam KALNET"
                ),
                "long": (
                    "Hi {name},\n\n"
                    "Thank you for saying so — it means a lot.\n\n"
                    "Let me be direct about what I'd recommend: a 20-minute focused "
                    "walkthrough of KALNET tailored to {company}. I'll cover:\n\n"
                    "• How we handle the follow-up problem most teams ignore\n"
                    "• What a typical 90-day ROI looks like for a team your size\n"
                    "• The three integrations that matter most\n\n"
                    "At the end you'll know clearly whether this is a fit — no pressure, "
                    "just clarity.\n\n"
                    f"Here's my calendar: {_CALENDAR_LINK}\n\nBest,\nTeam KALNET"
                ),
            },
            "c": {
                "short": (
                    "Hi {name},\n\n"
                    "Love to hear it.\n\n"
                    f"20 minutes this week? {_CALENDAR_LINK}\n\nBest,\nTeam KALNET"
                ),
                "medium": (
                    "Hi {name},\n\n"
                    "Wonderful news.\n\n"
                    "A 20-minute call will tell us everything we need to know about "
                    "the fit. I'll come prepared with a tailored overview of how "
                    "{company} would use KALNET.\n\n"
                    f"Book here: {_CALENDAR_LINK}\n\nBest,\nTeam KALNET"
                ),
                "long": (
                    "Hi {name},\n\n"
                    "So glad to hear it.\n\n"
                    "Here's what I'd love to do: before we talk numbers or contracts, "
                    "let me run a quick 'fit assessment' for {company}. It takes 20 "
                    "minutes and the output is a one-page summary of:\n\n"
                    "• Where KALNET fits in your current stack\n"
                    "• What you'd realistically save in the first 90 days\n"
                    "• What would need to be true for this to work\n\n"
                    "No commitment, no pitch — just a clear picture.\n\n"
                    f"Book here: {_CALENDAR_LINK}\n\nBest,\nTeam KALNET"
                ),
            },
        },
        "followup_1": {
            "a": {
                "short": (
                    "Hi {name},\n\n"
                    "Sharing a quick case study — a team like {company} "
                    "cut their manual outreach time by 65% in 90 days.\n\n"
                    f"Still open to a call? {_CALENDAR_LINK}\n\nBest,\nTeam KALNET"
                ),
                "medium": (
                    "Hi {name},\n\n"
                    "Wanted to share something concrete.\n\n"
                    "A company in {company}'s space recently reduced manual follow-up "
                    "by 65% and doubled their response rate within 90 days of using KALNET.\n\n"
                    "Happy to walk you through exactly how — 20 minutes max.\n\n"
                    f"Book here: {_CALENDAR_LINK}\n\nBest,\nTeam KALNET"
                ),
                "long": (
                    "Hi {name},\n\n"
                    "Following up with something I think you'll find useful.\n\n"
                    "Last quarter, a company in a similar position to {company} came to us "
                    "with the same challenge: great leads, inconsistent follow-up, shrinking "
                    "pipeline. Within 90 days:\n\n"
                    "• Manual outreach time dropped 65%\n"
                    "• Response rate doubled\n"
                    "• Pipeline grew 40% with no additional headcount\n\n"
                    "I'd love to show you how we'd replicate that for {company}. "
                    f"A 20-minute call is all it takes.\n\nBook here: {_CALENDAR_LINK}\n\n"
                    "Best,\nTeam KALNET"
                ),
            },
            "b": {
                "short": (
                    "Hi {name},\n\n"
                    "Quick follow-up — still thinking about KALNET?\n\n"
                    f"Happy to answer any questions: {_CALENDAR_LINK}\n\nBest,\nTeam KALNET"
                ),
                "medium": (
                    "Hi {name},\n\n"
                    "Just checking in to see if now is a better time.\n\n"
                    "I also wanted to share a quick ROI estimate I put together for "
                    "a team like {company}: 4–6 hours saved per rep per week, starting "
                    "from week one.\n\n"
                    f"Worth 20 minutes to see how?\n\nBook here: {_CALENDAR_LINK}\n\n"
                    "Best,\nTeam KALNET"
                ),
                "long": (
                    "Hi {name},\n\n"
                    "I know inboxes fill up fast — just wanted to follow up once more.\n\n"
                    "I've been thinking about {company}'s situation and I believe the fit "
                    "is genuinely strong. Here's why:\n\n"
                    "Your team likely loses 4–6 hours per rep per week to manual follow-up. "
                    "That's 20+ hours a week that could go into conversations instead of admin.\n\n"
                    "KALNET closes that gap. I can show you the exact mechanics in 20 minutes.\n\n"
                    f"Book here: {_CALENDAR_LINK}\n\nBest,\nTeam KALNET"
                ),
            },
            "c": {
                "short": (
                    "Hi {name},\n\n"
                    "One stat: teams like {company} see 40% pipeline growth "
                    f"in 90 days.\n\nWorth a chat? {_CALENDAR_LINK}\n\nBest,\nTeam KALNET"
                ),
                "medium": (
                    "Hi {name},\n\n"
                    "Research shows 80% of sales happen after the 5th "
                    "follow-up — but most reps stop at 2.\n\n"
                    "KALNET automates the difference. For {company}, that's real pipeline "
                    "that currently goes cold.\n\n"
                    f"20 minutes this week? {_CALENDAR_LINK}\n\nBest,\nTeam KALNET"
                ),
                "long": (
                    "Hi {name},\n\n"
                    "Here's a counter-intuitive fact: the best time to reach "
                    "a prospect is often their 4th or 5th touchpoint — when everyone else "
                    "has given up.\n\n"
                    "Most {company}-sized teams stop at touchpoint 2. KALNET keeps you in the "
                    "game automatically, with intent detection that knows exactly what to send "
                    "and when.\n\n"
                    "For a team like {company}, I estimate:\n"
                    "• 40–60% reduction in leads going cold\n"
                    "• 30% increase in meetings booked from existing pipeline\n"
                    "• ROI typically visible within 45 days\n\n"
                    f"A 20-minute call will confirm whether those numbers apply to you. "
                    f"Book here: {_CALENDAR_LINK}\n\nBest,\nTeam KALNET"
                ),
            },
        },
        "followup_2": {
            "a": {
                "short": (
                    "Hi {name},\n\n"
                    "One last thought before I stop following up — "
                    "I built a custom ROI model for {company}. Reply 'yes' and I'll send it.\n\n"
                    "Best,\nTeam KALNET"
                ),
                "medium": (
                    "Hi {name},\n\n"
                    "This is my last follow-up — I don't want to be a nuisance.\n\n"
                    "But before I go quiet: I've put together a one-page ROI estimate "
                    "for {company} based on your team size and industry. No commitment — "
                    "just useful numbers to have.\n\n"
                    "Reply 'yes' and I'll send it over.\n\nBest,\nTeam KALNET"
                ),
                "long": (
                    "Hi {name},\n\n"
                    "I'll be upfront — this is my last follow-up. I believe "
                    "in respecting people's inboxes.\n\n"
                    "But I didn't want to leave without sharing one last thing: I built a "
                    "custom ROI estimate for {company} that shows:\n\n"
                    "• Hours saved per week based on your team size\n"
                    "• Estimated pipeline recovery in 90 days\n"
                    "• Cost-per-qualified-lead comparison vs manual process\n\n"
                    "It's free, takes me 10 minutes to send, and it's yours to use "
                    "regardless of what you decide.\n\n"
                    "Reply 'yes' and I'll send it.\n\nBest,\nTeam KALNET"
                ),
            },
            "b": {
                "short": (
                    "Hi {name},\n\n"
                    "Last note from me. If the timing is ever right, "
                    f"I'm here: {_CALENDAR_LINK}\n\nWishing {'{company}'} all the best.\n\n"
                    "Best,\nTeam KALNET"
                ).format(name="{name}", company="{company}"),
                "medium": (
                    "Hi {name},\n\n"
                    "Closing the loop — this is my last note.\n\n"
                    "If you ever want to revisit KALNET for {company}, just reply and "
                    "we'll be right here. No re-introduction needed.\n\n"
                    "Wishing you and the team all the best.\n\nBest,\nTeam KALNET"
                ),
                "long": (
                    "Hi {name},\n\n"
                    "This is my last follow-up, and I wanted to make it count.\n\n"
                    "Working with teams like {company} is what we're built for — "
                    "and I genuinely believe there's a strong fit here.\n\n"
                    "If anything changes — budget, timing, priorities — just reply to "
                    "this email and we'll pick up exactly where we left off.\n\n"
                    "In the meantime, I'll leave you with a free resource: our "
                    "'Pipeline Leak Audit' — a one-page framework for finding where "
                    "leads are dropping out of your current process.\n\n"
                    "Wishing {company} all the best.\n\nBest,\nTeam KALNET"
                ),
            },
            "c": {
                "short": (
                    "Hi {name},\n\n"
                    "Final note — I'll stop after this.\n\n"
                    "One thing: we offer a free pipeline audit. No strings, just useful. "
                    "Want it?\n\nBest,\nTeam KALNET"
                ),
                "medium": (
                    "Hi {name},\n\n"
                    "Last one from me.\n\n"
                    "I'm leaving you with our free 'Outreach Audit Checklist' — "
                    "useful regardless of whether you use KALNET. It maps exactly where "
                    "leads go cold in a typical sales process.\n\n"
                    "Reply 'send it' and it's yours.\n\nBest,\nTeam KALNET"
                ),
                "long": (
                    "Hi {name},\n\n"
                    "I said I'd keep this short, so here goes:\n\n"
                    "This is my last note. I've enjoyed learning about {company} and "
                    "I believe there's genuine value here whenever the timing is right.\n\n"
                    "Parting gift: a free 'Revenue Recovery Worksheet' that most teams "
                    "find valuable even before they buy anything. It quantifies exactly "
                    "how much pipeline is lost to poor follow-up.\n\n"
                    "Reply 'yes' for the worksheet. Otherwise, wishing {company} all "
                    "the success.\n\nBest,\nTeam KALNET"
                ),
            },
        },
        "recovery": {
            "a": {
                "short": (
                    "Hi {name},\n\n"
                    "It's been a while — hoping things at {company} are going well.\n\n"
                    f"We've shipped a lot since we last connected. Worth a quick catch-up? {_CALENDAR_LINK}\n\n"
                    "Best,\nTeam KALNET"
                ),
                "medium": (
                    "Hi {name},\n\n"
                    "A few months have passed — I didn't want to let too long go by.\n\n"
                    "Since we last spoke, KALNET has launched advanced intent detection, "
                    "faster onboarding, and new integrations that might change the picture "
                    "for {company}.\n\n"
                    f"Open to a fresh 20-minute look?\n\nBook here: {_CALENDAR_LINK}\n\n"
                    "Best,\nTeam KALNET"
                ),
                "long": (
                    "Hi {name},\n\n"
                    "Hope everything at {company} is going well.\n\n"
                    "I wanted to reach out one more time because a lot has changed since "
                    "we last connected:\n\n"
                    "• Intent classification now covers 40+ reply types\n"
                    "• Onboarding time is down from 2 weeks to 3 days\n"
                    "• New integrations with HubSpot, Salesforce, and Pipedrive\n"
                    "• Pricing has a new entry-level option\n\n"
                    "Teams that weren't ready 6 months ago are getting great results now. "
                    "I think the fit for {company} might be stronger than before.\n\n"
                    f"Worth 20 minutes for a fresh look? Book here: {_CALENDAR_LINK}\n\n"
                    "Best,\nTeam KALNET"
                ),
            },
            "b": {
                "short": (
                    "Hi {name},\n\n"
                    "Long time — wanted to check in.\n\n"
                    "Is the timing any better for {company}?\n\nBest,\nTeam KALNET"
                ),
                "medium": (
                    "Hi {name},\n\n"
                    "Hope the quarter is treating {company} well.\n\n"
                    "I'm reaching back out because we've made changes I think you'd want "
                    "to know about — especially around pricing and onboarding speed.\n\n"
                    "Would you be open to a fresh conversation?\n\nBest,\nTeam KALNET"
                ),
                "long": (
                    "Hi {name},\n\n"
                    "I know it's been a while — thanks for your patience.\n\n"
                    "I'm reaching back out because we've made meaningful changes to KALNET "
                    "that address some of the concerns teams in {company}'s position typically "
                    "have.\n\n"
                    "The short version: faster onboarding, more flexible pricing, and a "
                    "self-service ROI calculator that gives you real numbers in 5 minutes.\n\n"
                    f"I'd love a 20-minute session to show you the difference. "
                    f"Book here: {_CALENDAR_LINK}\n\nBest,\nTeam KALNET"
                ),
            },
            "c": {
                "short": (
                    "Hi {name},\n\n"
                    "Circling back one more time — still believe there's a "
                    f"strong fit with {'{company}'}.\n\nOpen to reconnecting? {_CALENDAR_LINK}\n\n"
                    "Best,\nTeam KALNET"
                ).format(name="{name}", company="{company}"),
                "medium": (
                    "Hi {name},\n\n"
                    "One more note before I stop reaching out for good.\n\n"
                    "We've grown significantly since we last connected and the product "
                    "is meaningfully better. If {company} is still working through the "
                    "same outreach challenges, I believe KALNET can now solve them more "
                    "simply and affordably.\n\n"
                    f"Worth a look? {_CALENDAR_LINK}\n\nBest,\nTeam KALNET"
                ),
                "long": (
                    "Hi {name},\n\n"
                    "This is my genuine last attempt — I want to respect your time.\n\n"
                    "When we first spoke, I think the timing wasn't quite right. "
                    "That's completely fair.\n\n"
                    "But the product is genuinely different now, and I'd feel like I let "
                    "you down if I didn't share what's changed:\n\n"
                    "• A new 'quick start' plan designed for teams like {company}\n"
                    "• Onboarding takes 3 days, not weeks\n"
                    "• We now offer a 30-day pilot with full support\n\n"
                    "If none of that moves the needle, I understand. If it does, "
                    f"here's 20 minutes: {_CALENDAR_LINK}\n\n"
                    "Either way, wishing {company} all the best.\n\nBest,\nTeam KALNET"
                ),
            },
        },
        "reengagement": {
            "a": {
                "short": (
                    "Hi {name},\n\n"
                    "It's been over a year — wanted to check in one final time.\n\n"
                    "Is KALNET still on your radar for {company}?\n\nBest,\nTeam KALNET"
                ),
                "medium": (
                    "Hi {name},\n\n"
                    "A lot has changed at KALNET since we last spoke.\n\n"
                    "If you're still dealing with the follow-up challenges we discussed, "
                    "I'd love to show you what's possible now — it's significantly better.\n\n"
                    f"20 minutes? {_CALENDAR_LINK}\n\nBest,\nTeam KALNET"
                ),
                "long": (
                    "Hi {name},\n\n"
                    "I know it's been a long time, and I'll be brief.\n\n"
                    "We've continued building and the product has come a long way. "
                    "Teams that said 'not yet' a year ago are now among our happiest customers.\n\n"
                    "If {company} is still experiencing the outreach and follow-up challenges "
                    "we talked about, I think this is worth 20 minutes of your time.\n\n"
                    f"Book here: {_CALENDAR_LINK}  Or just reply and I'll make it easy.\n\n"
                    "Wishing you all the best either way.\n\nBest,\nTeam KALNET"
                ),
            },
            "b": {
                "short": (
                    "Hi {name},\n\n"
                    "Last note from the KALNET team.\n\n"
                    "If the timing ever becomes right for {company}, we'll be here.\n\n"
                    "Best,\nTeam KALNET"
                ),
                "medium": (
                    "Hi {name},\n\n"
                    "This is my final note — I won't keep reaching out after this.\n\n"
                    "If KALNET ever makes sense for {company}, just reply to this email "
                    "and we'll be right here — no need to start over.\n\n"
                    "Wishing you and the team all the best.\n\nBest,\nTeam KALNET"
                ),
                "long": (
                    "Hi {name},\n\n"
                    "Final note — I promise.\n\n"
                    "I've genuinely enjoyed learning about {company} and I still believe "
                    "there's a strong fit. But I also believe in respecting your inbox.\n\n"
                    "Before I go quiet for good: here's a parting resource. Our "
                    "'Free Pipeline Audit Checklist' is something every sales team should "
                    "run, regardless of what tools they use. It maps exactly where leads "
                    "fall through the cracks.\n\n"
                    "Reply 'send it' and it's yours, no strings.\n\n"
                    "Wishing {company} all the best.\n\nBest,\nTeam KALNET"
                ),
            },
            "c": {
                "short": (
                    "Hi {name},\n\n"
                    "One last note.\n\n"
                    "We're here if {company} ever wants to revisit KALNET. "
                    "Just reply.\n\nBest,\nTeam KALNET"
                ),
                "medium": (
                    "Hi {name},\n\n"
                    "Closing the loop after a long time.\n\n"
                    "If anything has changed at {company} — new priorities, new budget, "
                    "new frustrations with outreach — we'd love to reconnect.\n\n"
                    "Wishing you and the team well.\n\nBest,\nTeam KALNET"
                ),
                "long": (
                    "Hi {name},\n\n"
                    "This is the last time I'll reach out.\n\n"
                    "I wanted to end on a useful note rather than just a goodbye: "
                    "enclosed is our free 'Outreach Efficiency Scorecard' — a one-page "
                    "self-assessment that helps any team understand where they stand "
                    "against industry benchmarks.\n\n"
                    "No KALNET required. Just a useful tool for {company}, from us.\n\n"
                    "Reply 'scorecard' and I'll send it. Otherwise — all the best, "
                    "always.\n\nBest,\nTeam KALNET"
                ),
            },
        },
    },

    # ── v2: NOT_INTERESTED bodies — warm, professional, zero-negative-messaging ──
    Intent.NOT_INTERESTED: {
        "initial": {
            "a": {
                "short": (
                    "Hi {name},\n\n"
                    "Completely understood — and thank you so much for letting me know. "
                    "I genuinely appreciate it.\n\n"
                    "I won't keep reaching out, but I did want to say: the KALNET team "
                    "will always be here if the situation at {company} ever shifts. "
                    "Just reply to this email — no need to start over.\n\n"
                    "Wishing you and the team all the very best.\n\nWarmly,\nTeam KALNET"
                ),
                "medium": (
                    "Hi {name},\n\n"
                    "No problem at all — and thank you for taking the time to respond. "
                    "That's genuinely appreciated.\n\n"
                    "I'll take {company} off the active outreach list. But please know "
                    "that if your priorities, team, or situation ever changes — for any "
                    "reason — we'll be right here. The door is always open, no questions asked.\n\n"
                    "It's been a pleasure reaching out. Wishing {company} every success "
                    "in what's ahead.\n\nWarmly,\nTeam KALNET"
                ),
                "long": (
                    "Hi {name},\n\n"
                    "Thank you for being direct — that makes things easier for both of us, "
                    "and I genuinely appreciate it.\n\n"
                    "I'll make sure {company} is moved to a quiet list — you won't be "
                    "hearing from us regularly anymore.\n\n"
                    "That said, I do want to leave one thing on the table: markets shift, "
                    "teams grow, and priorities evolve. If there ever comes a time when "
                    "outreach automation is back on the agenda at {company}, we'll be here — "
                    "and all it takes is a reply to bring the conversation back to life.\n\n"
                    "There are no hard feelings, no pressure, and no agenda. Just a team "
                    "that genuinely enjoyed the exchange and wishes you well.\n\n"
                    "Thank you for your time, {name}. Wishing {company} all the very best.\n\n"
                    "Warmly,\nTeam KALNET"
                ),
            },
            "b": {
                "short": (
                    "Hi {name},\n\n"
                    "Totally understood — thank you for letting me know.\n\n"
                    "Whenever the timing feels right for {company}, we'll be here. "
                    "Just reply.\n\nWishing you all the best.\n\nWarmly,\nTeam KALNET"
                ),
                "medium": (
                    "Hi {name},\n\n"
                    "Thank you for the clarity — it's really helpful.\n\n"
                    "I'll stop the outreach from our end. The only thing I'd leave you "
                    "with is this: if anything changes at {company} — whether that's "
                    "six months or two years from now — just hit reply. We'll pick up "
                    "right where we left off.\n\n"
                    "Wishing you and the entire team a great year ahead.\n\n"
                    "Warmly,\nTeam KALNET"
                ),
                "long": (
                    "Hi {name},\n\n"
                    "Thank you — and I really mean that. It takes a moment to respond "
                    "and you didn't have to, so I appreciate it.\n\n"
                    "I'll update our records and won't be back in your inbox on this topic.\n\n"
                    "What I will say is: businesses evolve, teams change, and what doesn't "
                    "fit today sometimes fits perfectly in a year. The KALNET team doesn't "
                    "close doors — we just step back and let things breathe.\n\n"
                    "If you ever want to pick up the conversation — for any reason, at any "
                    "point — this email thread is all you need. We'll remember the context "
                    "and be ready to help.\n\n"
                    "It's been a genuine pleasure, {name}. Wishing {company} all the "
                    "success in the world.\n\nWarmly,\nTeam KALNET"
                ),
            },
            "c": {
                "short": (
                    "Hi {name},\n\n"
                    "Completely respect that — thank you for the response.\n\n"
                    "We'll always be here if {company} needs us.\n\n"
                    "Warmly,\nTeam KALNET"
                ),
                "medium": (
                    "Hi {name},\n\n"
                    "No problem at all — I appreciate you being upfront.\n\n"
                    "We're stepping back, but the door is always open on our side. "
                    "Should anything shift at {company}, we'll be easy to find.\n\n"
                    "Take care, and all the best to the team.\n\nWarmly,\nTeam KALNET"
                ),
                "long": (
                    "Hi {name},\n\n"
                    "Understood — and thank you.\n\n"
                    "I'll close out the outreach on our end. But before I do, I wanted "
                    "to make one thing clear: the KALNET team has genuinely enjoyed getting "
                    "to know {company}, and that goodwill doesn't have an expiry date.\n\n"
                    "If the landscape changes — new growth phase, new leadership, new "
                    "challenges with outreach — don't hesitate to reach back out. We'll "
                    "treat it like a continuation, not a restart.\n\n"
                    "Until then, wishing {company} every success.\n\nWarmly,\nTeam KALNET"
                ),
            },
        },
        "followup_1": {
            "a": {
                "short": (
                    "Hi {name},\n\n"
                    "Just a gentle long-term check-in — hope {company} is doing well.\n\n"
                    "We're always here whenever the timing is right.\n\n"
                    "Warmly,\nTeam KALNET"
                ),
                "medium": (
                    "Hi {name},\n\n"
                    "Hope the team at {company} is thriving. Just a light touch to stay "
                    "connected — no agenda, no pitch.\n\n"
                    "If anything's changed on your end and a conversation makes sense, "
                    "just reply. We'll take it from there.\n\nWarmly,\nTeam KALNET"
                ),
                "long": (
                    "Hi {name},\n\n"
                    "Hope all is well at {company}. I wanted to reach out one more time — "
                    "not to pitch, just to stay connected.\n\n"
                    "Businesses change fast, and I'd rather you know we're thinking of you "
                    "than feel like we disappeared after your last message.\n\n"
                    "No need to respond unless something has shifted. If it has, I'm one "
                    "reply away.\n\nWishing you a great quarter.\n\nWarmly,\nTeam KALNET"
                ),
            },
            "b": {
                "short": (
                    "Hi {name},\n\n"
                    "A quick hello from the KALNET team — no agenda.\n\n"
                    "We're here whenever {company} needs us.\n\nWarmly,\nTeam KALNET"
                ),
                "medium": (
                    "Hi {name},\n\n"
                    "Just checking in — hope things are going well at {company}.\n\n"
                    "We're still here and happy to reconnect whenever the timing feels right. "
                    "No rush, no pressure.\n\nWarmly,\nTeam KALNET"
                ),
                "long": (
                    "Hi {name},\n\n"
                    "A quick note from the KALNET team — purely to stay on your radar, not "
                    "to reopen a conversation you've already closed.\n\n"
                    "We genuinely respect your decision and are reaching out only because "
                    "we've seen circumstances change for teams like {company} and wanted "
                    "to make sure you know we're available if that happens here too.\n\n"
                    "Wishing you a brilliant rest of the year.\n\nWarmly,\nTeam KALNET"
                ),
            },
            "c": {
                "short": (
                    "Hi {name},\n\n"
                    "Staying in touch — nothing more.\n\n"
                    "We're here for {company} whenever needed.\n\nWarmly,\nTeam KALNET"
                ),
                "medium": (
                    "Hi {name},\n\n"
                    "Just a brief hello to stay connected. No pressure, no agenda — "
                    "just making sure you know we're here if {company}'s needs evolve.\n\n"
                    "All the best.\n\nWarmly,\nTeam KALNET"
                ),
                "long": (
                    "Hi {name},\n\n"
                    "I hope this finds you well.\n\n"
                    "I promised I wouldn't be a nuisance, and I intend to keep that promise. "
                    "This is just a light touch to say: the KALNET team is rooting for {company} "
                    "regardless of whether you ever use our product.\n\n"
                    "If the situation ever changes, we'll be ready. Until then — take care.\n\n"
                    "Warmly,\nTeam KALNET"
                ),
            },
        },
        "followup_2": {
            "a": {
                "short": (
                    "Hi {name},\n\n"
                    "The last note from us — truly. Thank you for your time.\n\n"
                    "We're here if {company} ever needs us.\n\nWarmly,\nTeam KALNET"
                ),
                "medium": (
                    "Hi {name},\n\n"
                    "This is the last time I'll reach out — I want to keep my promise.\n\n"
                    "We're stepping back completely now, but the door stays open forever. "
                    "Whenever the timing is right for {company}, just reply.\n\n"
                    "Wishing you all the very best.\n\nWarmly,\nTeam KALNET"
                ),
                "long": (
                    "Hi {name},\n\n"
                    "Final note — and I genuinely mean it this time.\n\n"
                    "Thank you for every interaction we've had. The KALNET team has enjoyed "
                    "learning about {company}, and we wish you nothing but continued success.\n\n"
                    "We'll be moving you to a long-term nurture list — which means you "
                    "won't hear from us regularly, but you'll occasionally receive something "
                    "genuinely useful: a resource, an industry insight, or a brief update "
                    "about something that might matter to you. No pitches.\n\n"
                    "Whenever you're ready to talk — whether that's next month or next "
                    "year — we'll be here.\n\nWith warmth and respect,\nTeam KALNET"
                ),
            },
            "b": {
                "short": (
                    "Hi {name},\n\n"
                    "Going quiet now — but always here.\n\n"
                    "Best of luck to {company}.\n\nWarmly,\nTeam KALNET"
                ),
                "medium": (
                    "Hi {name},\n\n"
                    "Signing off for now — and thank you again for your time and honesty.\n\n"
                    "The door is always open at KALNET. Wishing {company} every success.\n\n"
                    "Warmly,\nTeam KALNET"
                ),
                "long": (
                    "Hi {name},\n\n"
                    "Last note — I'll keep it brief.\n\n"
                    "It's been a genuine pleasure, and we're proud to have been on your "
                    "radar even if the timing wasn't right. Teams like {company} are exactly "
                    "who we build for, so your feedback — even implicit — means a lot to us.\n\n"
                    "We'll be here. Quietly, respectfully, and with no pressure.\n\n"
                    "Wishing you a wonderful year ahead.\n\nWarmly,\nTeam KALNET"
                ),
            },
            "c": {
                "short": (
                    "Hi {name},\n\n"
                    "All the best from KALNET. We'll always be here for {company}.\n\n"
                    "Warmly,\nTeam KALNET"
                ),
                "medium": (
                    "Hi {name},\n\n"
                    "Closing out — with genuine warmth.\n\n"
                    "Thank you for your time. If {company}'s situation ever changes, "
                    "we'll be one reply away.\n\nAll the very best.\n\nWarmly,\nTeam KALNET"
                ),
                "long": (
                    "Hi {name},\n\n"
                    "This is a genuine farewell — and a warm one.\n\n"
                    "I'm grateful for every interaction we had. The KALNET team cares "
                    "deeply about the companies we reach out to, and {company} is no exception.\n\n"
                    "We're not disappearing — we're just stepping back respectfully. "
                    "If you ever want to reconnect, this email thread is all you need.\n\n"
                    "Until then, here's to {company}'s continued success.\n\n"
                    "With respect and warmth,\nTeam KALNET"
                ),
            },
        },
        "recovery": {
            "a": {
                "short": (
                    "Hi {name},\n\n"
                    "A gentle check-in — hope {company} is doing well.\n\n"
                    "We're here if things have shifted.\n\nWarmly,\nTeam KALNET"
                ),
                "medium": (
                    "Hi {name},\n\n"
                    "It's been a while — I hope things are going well at {company}.\n\n"
                    "I'm reaching out purely to stay connected, not to pitch. If the "
                    "landscape has changed and a conversation would be welcome, I'm here.\n\n"
                    "Warmly,\nTeam KALNET"
                ),
                "long": (
                    "Hi {name},\n\n"
                    "Hope all is well at {company}.\n\n"
                    "I wanted to circle back one more time — not to reopen anything closed, "
                    "but because a lot changes in six months and I'd feel remiss not checking in.\n\n"
                    "If the situation at {company} has evolved, we'd love to hear. If not, "
                    "totally fine — this is just a friendly wave from the team.\n\n"
                    "Wishing you well.\n\nWarmly,\nTeam KALNET"
                ),
            },
            "b": {
                "short": (
                    "Hi {name},\n\n"
                    "Checking in — hoping {company} is thriving.\n\n"
                    "We're still here whenever needed.\n\nWarmly,\nTeam KALNET"
                ),
                "medium": (
                    "Hi {name},\n\n"
                    "Just a light touch to stay on your radar.\n\n"
                    "We know the timing wasn't right before, but businesses evolve fast. "
                    "If it ever makes sense to reconnect, we're one reply away.\n\n"
                    "Hope {company} is doing brilliantly.\n\nWarmly,\nTeam KALNET"
                ),
                "long": (
                    "Hi {name},\n\n"
                    "A respectful check-in from the KALNET team.\n\n"
                    "We promised to step back and we did. But we also said the door "
                    "stays open — and it does. If anything has changed at {company} "
                    "that makes outreach automation relevant again, we'd love to "
                    "hear about it.\n\n"
                    "If not, no response needed — we'll stay quiet.\n\n"
                    "Wishing you a great rest of the year.\n\nWarmly,\nTeam KALNET"
                ),
            },
            "c": {
                "short": (
                    "Hi {name},\n\n"
                    "A quiet check-in — no agenda.\n\n"
                    "We're here for {company} whenever the time is right.\n\n"
                    "Warmly,\nTeam KALNET"
                ),
                "medium": (
                    "Hi {name},\n\n"
                    "Reaching out one more time — purely to stay connected.\n\n"
                    "If {company}'s situation has evolved since we last spoke, "
                    "I'd love to reconnect. If not, no worries — just a friendly "
                    "check-in.\n\nAll the best.\n\nWarmly,\nTeam KALNET"
                ),
                "long": (
                    "Hi {name},\n\n"
                    "I know we said we'd step back, and we have — but this is just "
                    "a long-term relationship touch, nothing more.\n\n"
                    "KALNET has continued to grow and improve since we last connected. "
                    "If {company} has experienced any changes in outreach strategy, team "
                    "size, or growth goals, we'd love to have a fresh conversation.\n\n"
                    "And if the answer is still no — that's perfectly fine. We appreciate "
                    "your time, past and present.\n\nWarmly,\nTeam KALNET"
                ),
            },
        },
        "reengagement": {
            "a": {
                "short": (
                    "Hi {name},\n\n"
                    "One final note — hoping {company} is doing wonderfully.\n\n"
                    "We'll always be here whenever needed.\n\nWarmly,\nTeam KALNET"
                ),
                "medium": (
                    "Hi {name},\n\n"
                    "This is our last long-term check-in — and a warm one.\n\n"
                    "We hope {company} has had a great year. If anything has changed "
                    "and a conversation would be welcome, just reply — we'll be here.\n\n"
                    "All the best, always.\n\nWarmly,\nTeam KALNET"
                ),
                "long": (
                    "Hi {name},\n\n"
                    "A final note from the KALNET team — with gratitude.\n\n"
                    "It's been a long time since we first reached out, and we've genuinely "
                    "enjoyed following {company}'s journey from a distance.\n\n"
                    "We won't reach out again unless you initiate — that's a promise. "
                    "But we did want to say: the door is always open, the team is always "
                    "friendly, and there's never any pressure.\n\n"
                    "Wishing {company} every success in everything ahead.\n\n"
                    "With warmth and respect,\nTeam KALNET"
                ),
            },
            "b": {
                "short": (
                    "Hi {name},\n\n"
                    "Last long-term note — wishing {company} all the best.\n\n"
                    "We're here if needed.\n\nWarmly,\nTeam KALNET"
                ),
                "medium": (
                    "Hi {name},\n\n"
                    "Final note — and a sincere thank you for every interaction.\n\n"
                    "KALNET will always be here for {company} whenever the time is right. "
                    "No need to start over — just reply.\n\nAll the very best.\n\n"
                    "Warmly,\nTeam KALNET"
                ),
                "long": (
                    "Hi {name},\n\n"
                    "This is the last note from our team — and I want it to reflect "
                    "how we genuinely feel.\n\n"
                    "Thank you for being part of our journey, even as a prospect. "
                    "The conversations and interactions we had shaped how we think "
                    "about teams like {company}, and that's genuinely valuable to us.\n\n"
                    "We wish you and the entire {company} team the very best — now "
                    "and always.\n\nWith warmth,\nTeam KALNET"
                ),
            },
            "c": {
                "short": (
                    "Hi {name},\n\n"
                    "Closing the book — with warmth.\n\n"
                    "Thank you, {name}. Wishing {company} all the best.\n\n"
                    "Warmly,\nTeam KALNET"
                ),
                "medium": (
                    "Hi {name},\n\n"
                    "One final note — and a genuine thank you.\n\n"
                    "We hope {company} continues to thrive. If we can ever be of service, "
                    "we'll be here.\n\nWith warmth,\nTeam KALNET"
                ),
                "long": (
                    "Hi {name},\n\n"
                    "This is it — the last note.\n\n"
                    "I want to close by saying something sincere: teams that are selective "
                    "about what they adopt — like {company} — are the ones that succeed long "
                    "term. We respect that deeply.\n\n"
                    "If the day ever comes when KALNET feels right for you, we'll be here — "
                    "unchanged, warm, and ready to help without any trace of 'I told you so.'\n\n"
                    "Until then, all the very best.\n\nWith deep respect,\nTeam KALNET"
                ),
            },
        },
    },
}

# Reuse INTERESTED bodies for closely related intents
for _intent in (Intent.VERY_INTERESTED, Intent.PRICING_REQUEST,
                Intent.PROPOSAL_REQUEST, Intent.MEETING_REQUEST,
                Intent.TECHNICAL_DISCUSSION, Intent.DOCUMENTATION_REQUEST,
                Intent.CASE_STUDY_REQUEST, Intent.PILOT_REQUEST,
                Intent.DEMO_REQUEST):
    if _intent not in ADVANCED_EMAIL_BODIES:
        ADVANCED_EMAIL_BODIES[_intent] = ADVANCED_EMAIL_BODIES[Intent.INTERESTED]

for _intent in (Intent.NO_BUDGET, Intent.BUDGET_FROZEN,
                Intent.ROI_CONCERN, Intent.PRICING_OBJECTION):
    if _intent not in ADVANCED_EMAIL_BODIES:
        ADVANCED_EMAIL_BODIES[_intent] = ADVANCED_EMAIL_BODIES[Intent.INTERESTED]

# CTA-response intents map to their own NOT_INTERESTED bodies or INTERESTED bodies
if Intent.INTERESTED_CTA not in ADVANCED_EMAIL_BODIES:
    ADVANCED_EMAIL_BODIES[Intent.INTERESTED_CTA] = ADVANCED_EMAIL_BODIES[Intent.INTERESTED]
if Intent.INTERESTED_NOT_CONVINCED not in ADVANCED_EMAIL_BODIES:
    ADVANCED_EMAIL_BODIES[Intent.INTERESTED_NOT_CONVINCED] = ADVANCED_EMAIL_BODIES[Intent.INTERESTED]
# NOT_INTERESTED bodies defined above

for _intent in (Intent.NOT_NOW, Intent.MAYBE_LATER, Intent.FOLLOW_UP_NEXT_WEEK,
                Intent.FOLLOW_UP_NEXT_MONTH, Intent.FOLLOW_UP_NEXT_QUARTER,
                Intent.FOLLOW_UP_NEXT_YEAR, Intent.BUSY, Intent.USING_COMPETITOR,
                Intent.EXISTING_VENDOR, Intent.INTERNAL_SOLUTION,
                Intent.FEATURE_OBJECTION, Intent.SECURITY_CONCERN,
                Intent.COMPLIANCE_CONCERN, Intent.PROCUREMENT_DELAY,
                Intent.LEGAL_DELAY, Intent.RESOURCE_CONSTRAINT,
                Intent.OUT_OF_OFFICE, Intent.VACATION, Intent.AUTO_REPLY,
                Intent.REFERRAL, Intent.MEETING_BOOKED, Intent.MEETING_COMPLETED,
                Intent.MEETING_MISSED, Intent.SOFT_BOUNCE,
                Intent.HARD_BOUNCE, Intent.UNKNOWN):
    if _intent not in ADVANCED_EMAIL_BODIES:
        ADVANCED_EMAIL_BODIES[_intent] = ADVANCED_EMAIL_BODIES[Intent.INTERESTED]


# ==========================================================================
# ORIGINAL: Delay settings from Dashboard DB  [UPDATED — new defaults]
# Dashboard settings key names are UNCHANGED for backward compatibility.
# Only the fallback default values are updated: 5→2, 10→7.
# Existing dashboard rows writing 'email_2_delay_days' / 'email_3_delay_days'
# continue to work exactly as before.
# ==========================================================================

def _load_delay_settings() -> dict:
    import sqlite3
    db_path = os.path.join(os.path.dirname(__file__), '..', 'api', 'dashboard.db')
    # ── UPDATED defaults: Email 2: 2 days (was 5), Email 3: 7 days (was 10) ──
    defaults = {'email_2_delay_days': 2, 'email_3_delay_days': 7}
    if not os.path.exists(db_path):
        return defaults
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM settings WHERE key LIKE 'email_%_delay_days'")
        for key, val in cur.fetchall():
            defaults[key] = int(val)
        conn.close()
    except Exception:
        pass
    return defaults


# ==========================================================================
# ORIGINAL CORE FUNCTION  [UPDATED — delay constants only; logic unchanged]
# ==========================================================================

def get_sequence_due_today(leads: List[Dict]) -> List[Dict]:
    """
    Evaluate every lead and return only those who should receive an email today.

    Uses TWO conditions to decide (not just days alone):
        days_elapsed == 0  AND sequence_step == 0  -> Email 1
        days_elapsed >= 2  AND sequence_step == 1  -> Email 2  (was 5 days)
        days_elapsed >= 7  AND sequence_step == 2  -> Email 3  (was 10 days)

    Checking sequence_step alongside days_elapsed prevents double-sends
    if the pipeline restarts or runs twice in one day.

    Parameters
    ----------
    leads : List[Dict]
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
    List[Dict]
        Each Dict contains:
            lead_id      (str)
            name         (str)
            email        (str)
            company      (str)
            email_number (int) -- which email to send: 1, 2, or 3
    """
    today     = date.today()
    due_today = []
    delays   = _load_delay_settings()
    # Updated defaults: 2 days for Email 2, 7 days for Email 3
    email_2_delay = delays.get('email_2_delay_days', 2)
    email_3_delay = delays.get('email_3_delay_days', 7)

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
        raw_date = (lead.get("email_sent_at") or "").strip()

        if not raw_date and sequence_step == 0:
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
        if days_elapsed >= email_2_delay and sequence_step == 1:
            email_number = 2
        elif days_elapsed >= email_3_delay and sequence_step == 2:
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


# ==========================================================================
# ORIGINAL EMAIL CONTENT HELPER  [COMPLETELY UNCHANGED]
# ==========================================================================

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

    subject = EMAIL_SUBJECTS.get(n, "Hello from Team KALNET").format(company=company)
    body    = EMAIL_BODIES.get(n, "").format(name=name, company=company)

    return {"subject": subject, "body": body}


# ==========================================================================
# ENTERPRISE: LEAD SCORING
# [NEW — safe, isolated, never called by existing code]
# ==========================================================================

# Score weights for each signal
_SCORE_WEIGHTS: Dict[str, int] = {
    "replied":          40,
    "demo_request":     35,
    "meeting_request":  35,
    "proposal_request": 30,
    "pricing_request":  25,
    "very_interested":  30,
    "interested":       20,
    "technical":        15,
    "multiple_opens":   15,   # open_count >= 3
    "opened":            8,   # open_count >= 1
    "multiple_clicks":  18,   # click_count >= 2
    "clicked":          12,   # click_count >= 1
    "referral":         20,
    "hard_bounce":     -50,
    "soft_bounce":      -5,
    "unsubscribed":    -60,
    "using_competitor": -10,
    "no_budget":        -8,
    # v2: CTA signals
    "cta_interested":   30,   # clicked ✅ Interested CTA
    "cta_not_convinced": 15,  # clicked 🤔 CTA — still engaged
    "cta_not_interested": -20, # clicked ❌ Not Interested CTA
}

_HIGH_INTENT_INTENTS = {
    Intent.DEMO_REQUEST, Intent.MEETING_REQUEST, Intent.PROPOSAL_REQUEST,
    Intent.PRICING_REQUEST, Intent.VERY_INTERESTED, Intent.PILOT_REQUEST,
    Intent.INTERESTED_CTA,       # v2: CTA click counts as high intent
}


def get_lead_score(lead: Dict) -> int:
    """
    Return an engagement score 0–100 for a lead.

    Reads optional fields: intent, open_count, click_count, replied,
    is_referral, bounced, unsubscribed, cta_response.
    Missing fields are treated as zero/False.

    v2: Also reads cta_response field (CTA_INTERESTED | CTA_INTERESTED_NOT_CONVINCED
        | CTA_NOT_INTERESTED) and adjusts score accordingly.

    Falls back to 0 on any error — never raises.
    """
    try:
        total  = 0
        intent = (lead.get("intent") or "").upper()

        # Reply signals
        if lead.get("replied"):
            total += _SCORE_WEIGHTS["replied"]

        if intent in _HIGH_INTENT_INTENTS:
            total += _SCORE_WEIGHTS.get("demo_request", 0)
        elif intent == Intent.INTERESTED:
            total += _SCORE_WEIGHTS["interested"]
        elif intent in (Intent.TECHNICAL_DISCUSSION, Intent.DOCUMENTATION_REQUEST):
            total += _SCORE_WEIGHTS["technical"]
        elif intent == Intent.USING_COMPETITOR:
            total += _SCORE_WEIGHTS["using_competitor"]
        elif intent == Intent.NO_BUDGET:
            total += _SCORE_WEIGHTS["no_budget"]
        elif intent == Intent.NOT_INTERESTED:
            total += _SCORE_WEIGHTS["cta_not_interested"]
        elif intent == Intent.INTERESTED_NOT_CONVINCED:
            total += _SCORE_WEIGHTS["cta_not_convinced"]

        # v2: CTA response field (separate from intent — for tracking only)
        cta_response = (lead.get("cta_response") or "").lower()
        if cta_response == CTA_INTERESTED:
            total += _SCORE_WEIGHTS["cta_interested"]
        elif cta_response == CTA_INTERESTED_NOT_CONVINCED:
            total += _SCORE_WEIGHTS["cta_not_convinced"]
        elif cta_response == CTA_NOT_INTERESTED:
            total += _SCORE_WEIGHTS["cta_not_interested"]

        if lead.get("is_referral"):
            total += _SCORE_WEIGHTS["referral"]

        open_count  = int(lead.get("open_count",  0) or 0)
        click_count = int(lead.get("click_count", 0) or 0)

        if open_count >= 3:
            total += _SCORE_WEIGHTS["multiple_opens"]
        elif open_count >= 1:
            total += _SCORE_WEIGHTS["opened"]

        if click_count >= 2:
            total += _SCORE_WEIGHTS["multiple_clicks"]
        elif click_count >= 1:
            total += _SCORE_WEIGHTS["clicked"]

        bounced = (lead.get("bounced") or "").lower()
        if bounced == "hard":
            total += _SCORE_WEIGHTS["hard_bounce"]
        elif bounced == "soft":
            total += _SCORE_WEIGHTS["soft_bounce"]

        if lead.get("unsubscribed"):
            total += _SCORE_WEIGHTS["unsubscribed"]

        # Recency decay
        raw_date = (lead.get("email_sent_at") or "").strip()
        if raw_date:
            try:
                sent = date.fromisoformat(raw_date)
                age  = (date.today() - sent).days
                if age > 60:
                    total -= min(20, (age - 60) // 10 * 5)
            except ValueError:
                pass

        return max(0, min(100, total))

    except Exception as exc:
        logger.error("get_lead_score error for lead %s: %s",
                     lead.get("lead_id", "?"), exc, exc_info=True)
        return 0


# ==========================================================================
# ENTERPRISE: INTENT DELAY TABLE
# [UPDATED — added v2 CTA intents; existing values unchanged]
# ==========================================================================

_INTENT_DELAY_DAYS: Dict[str, int] = {
    # v2: CTA-response intents
    Intent.INTERESTED_CTA:           0,   # Act immediately on expressed interest
    Intent.INTERESTED_NOT_CONVINCED: 1,   # Follow up next day with persuasion
    Intent.NOT_INTERESTED:         180,   # Respectful 6-month pause before nurture
    # Original intents (UNCHANGED)
    Intent.INTERESTED:             1,
    Intent.VERY_INTERESTED:        0,
    Intent.DEMO_REQUEST:           0,
    Intent.PRICING_REQUEST:        1,
    Intent.PROPOSAL_REQUEST:       1,
    Intent.TECHNICAL_DISCUSSION:   1,
    Intent.DOCUMENTATION_REQUEST:  2,
    Intent.CASE_STUDY_REQUEST:     2,
    Intent.PILOT_REQUEST:          1,
    Intent.MEETING_REQUEST:        0,
    Intent.NO_BUDGET:             60,
    Intent.BUDGET_FROZEN:         45,
    Intent.PRICING_OBJECTION:      7,
    Intent.ROI_CONCERN:            5,
    Intent.NOT_NOW:               30,
    Intent.MAYBE_LATER:           30,
    Intent.FOLLOW_UP_NEXT_WEEK:    7,
    Intent.FOLLOW_UP_NEXT_MONTH:  30,
    Intent.FOLLOW_UP_NEXT_QUARTER: 90,
    Intent.FOLLOW_UP_NEXT_YEAR:  365,
    Intent.BUSY:                  14,
    Intent.USING_COMPETITOR:      90,
    Intent.EXISTING_VENDOR:       90,
    Intent.INTERNAL_SOLUTION:     90,
    Intent.FEATURE_OBJECTION:     30,
    Intent.RESOURCE_CONSTRAINT:   21,
    Intent.SECURITY_CONCERN:       7,
    Intent.COMPLIANCE_CONCERN:     7,
    Intent.PROCUREMENT_DELAY:     21,
    Intent.LEGAL_DELAY:           14,
    Intent.REFERRAL:               1,
    Intent.OUT_OF_OFFICE:          7,
    Intent.VACATION:              14,
    Intent.AUTO_REPLY:             3,
    Intent.MEETING_BOOKED:         1,
    Intent.MEETING_COMPLETED:      1,
    Intent.MEETING_MISSED:         1,
    Intent.SOFT_BOUNCE:            3,
    Intent.HARD_BOUNCE:            0,
    Intent.UNKNOWN:                5,
}


def get_intent_delay(intent: str) -> int:
    """
    Return the recommended days to wait before the next follow-up for a given intent.
    Falls back to 5 days for unknown intents. Never raises.

    v2: Also handles new CTA-response intents (INTERESTED_CTA → 0 days,
        INTERESTED_NOT_CONVINCED → 1 day, NOT_INTERESTED → 180 days).
    """
    try:
        return _INTENT_DELAY_DAYS.get(intent, 5)
    except Exception as exc:
        logger.error("get_intent_delay error: %s", exc, exc_info=True)
        return 5


# ==========================================================================
# ENTERPRISE: FOLLOW-UP STRATEGY
# [UPDATED — routing extended for v2 CTA intents]
# ==========================================================================

def get_followup_strategy(lead: Dict) -> Dict:
    """
    Return a strategy dict for a lead with optional advanced fields.

    v2 routing additions:
        INTERESTED_CTA         → step=initial, priority routing to meeting
        INTERESTED_NOT_CONVINCED → step=initial, persuasion template path
        NOT_INTERESTED         → step=followup_1 of NOT_INTERESTED nurture

    Returns
    -------
    dict with keys:
        step          (str) : "initial" | "followup_1" | "followup_2" |
                              "followup_3" | "recovery" | "reengagement"
        version       (str) : "a" | "b" | "c"
        length        (str) : "short" | "medium" | "long"
        subject_type  (str) : "direct" | "value" | "curiosity" |
                              "executive" | "conversational"
        intent        (str) : resolved intent (original or defaulted)
        score         (int) : computed lead score

    Falls back to safe defaults on any error. Never raises.
    """
    try:
        intent       = (lead.get("intent") or Intent.UNKNOWN).upper()
        score        = get_lead_score(lead)
        email_number = int(lead.get("email_number", 1) or 1)
        adv_step     = int(lead.get("advanced_step", 0) or 0)

        # v2: CTA-intent overrides — bypass normal step logic
        if intent == Intent.INTERESTED_CTA:
            step = "initial"   # Always send meeting-scheduling email immediately
        elif intent == Intent.INTERESTED_NOT_CONVINCED:
            step = "initial"   # Persuasion starts fresh
        elif intent == Intent.NOT_INTERESTED:
            step = "initial"   # Warm closing email
        else:
            # Original step selection logic (UNCHANGED)
            if adv_step == 0:
                step = "initial"
            elif adv_step == 1:
                step = "followup_1"
            elif adv_step == 2:
                step = "followup_2"
            elif adv_step == 3:
                step = "followup_3"
            elif adv_step >= 4:
                step = "recovery"
            else:
                step = "reengagement"

            # Fallback: if no advanced_step, derive from email_number
            if not lead.get("advanced_step"):
                step_map = {1: "initial", 2: "followup_1", 3: "followup_2"}
                step = step_map.get(email_number, "initial")

        # Version: deterministic A/B/C from lead_id hash
        lead_id = lead.get("lead_id", "")
        version_idx = abs(hash(lead_id)) % 3 if lead_id else 0
        version = ["a", "b", "c"][version_idx]

        # Length: based on email position in the sequence
        length_map = {1: "short", 2: "medium", 3: "long"}
        length = length_map.get(email_number, "medium")

        # Subject type: based on score tier
        if score >= 80:    subject_type = "direct"
        elif score >= 60:  subject_type = "value"
        elif score >= 40:  subject_type = "curiosity"
        elif score >= 20:  subject_type = "conversational"
        else:              subject_type = "value"

        return {
            "step":         step,
            "version":      version,
            "length":       length,
            "subject_type": subject_type,
            "intent":       intent,
            "score":        score,
        }

    except Exception as exc:
        logger.error("get_followup_strategy error for lead %s: %s",
                     lead.get("lead_id", "?"), exc, exc_info=True)
        return {
            "step": "initial", "version": "a", "length": "medium",
            "subject_type": "value", "intent": Intent.UNKNOWN, "score": 0,
        }


# ==========================================================================
# ENTERPRISE: SHOULD SEND ADVANCED FOLLOW-UP
# [UPDATED — CTA intents always qualify]
# ==========================================================================

def should_send_advanced_followup(lead: Dict) -> bool:
    """
    Return True if this lead has enough signal to use advanced templates.

    A lead qualifies if it has ANY of:
        - a non-empty, non-UNKNOWN intent
        - open_count > 0
        - click_count > 0
        - a last_reply field
        - a cta_response field  [v2]

    Falls back to False on any error (conservative — keeps original behaviour).
    """
    try:
        intent = (lead.get("intent") or "").upper()
        if intent and intent != Intent.UNKNOWN:
            return True
        if int(lead.get("open_count",  0) or 0) > 0:
            return True
        if int(lead.get("click_count", 0) or 0) > 0:
            return True
        if lead.get("last_reply"):
            return True
        # v2: CTA response is a strong signal
        if lead.get("cta_response"):
            return True
        return False
    except Exception as exc:
        logger.error("should_send_advanced_followup error: %s", exc, exc_info=True)
        return False


# ==========================================================================
# ENTERPRISE: GET NEXT FOLLOW-UP EMAIL (nurture path resolver)
# [UPDATED — v2: appends CTA footer to all outbound emails]
# ==========================================================================

_NURTURE_STEPS = ["initial", "followup_1", "followup_2", "followup_3",
                  "recovery", "reengagement"]


def get_next_followup_email(lead: Dict) -> Dict:
    """
    Return the next email in the nurture path for a lead.

    v2 change: The CTA footer (3 clickable buttons) is appended to
    every email body EXCEPT those for NOT_INTERESTED leads (they get
    a clean closing email — no further CTAs).

    Returns
    -------
    dict  { "subject": str, "body": str }
    Falls back to get_email_content() on any error.
    """
    try:
        strategy  = get_followup_strategy(lead)
        intent    = strategy["intent"]
        step      = strategy["step"]
        version   = strategy["version"]
        length    = strategy["length"]
        subj_type = strategy["subject_type"]
        name      = lead.get("name",    "there")
        company   = lead.get("company", "your company")
        lead_id   = lead.get("lead_id", "")

        # Subject lookup
        subj_block = (
            ADVANCED_EMAIL_SUBJECTS
            .get(intent, ADVANCED_EMAIL_SUBJECTS[Intent.INTERESTED])
            .get(step, ADVANCED_EMAIL_SUBJECTS[Intent.INTERESTED]["initial"])
            .get(version, ADVANCED_EMAIL_SUBJECTS[Intent.INTERESTED]["initial"]["a"])
            .get(length, ADVANCED_EMAIL_SUBJECTS[Intent.INTERESTED]["initial"]["a"]["medium"])
        )
        subject_raw = subj_block.get(subj_type, subj_block.get("value", "Following up — {company}"))
        subject     = subject_raw.format(name=name, company=company)

        # Body lookup
        body_raw = (
            ADVANCED_EMAIL_BODIES
            .get(intent, ADVANCED_EMAIL_BODIES[Intent.INTERESTED])
            .get(step, ADVANCED_EMAIL_BODIES[Intent.INTERESTED]["initial"])
            .get(version, ADVANCED_EMAIL_BODIES[Intent.INTERESTED]["initial"]["a"])
            .get(length, ADVANCED_EMAIL_BODIES[Intent.INTERESTED]["initial"]["a"]["medium"])
        )
        body = body_raw.format(name=name, company=company)

        # v2: Append CTA footer to all emails except NOT_INTERESTED closings
        # NOT_INTERESTED gets a clean, warm goodbye — no further CTAs
        if intent != Intent.NOT_INTERESTED:
            body = append_cta_to_body(body, lead_id)

        logger.debug(
            "get_next_followup_email: intent=%s step=%s version=%s length=%s lead=%s",
            intent, step, version, length, lead_id,
        )
        return {"subject": subject, "body": body}

    except Exception as exc:
        logger.error("get_next_followup_email error for lead %s: %s",
                     lead.get("lead_id", "?"), exc, exc_info=True)
        return get_email_content(lead)   # guaranteed fallback


# ==========================================================================
# ENTERPRISE: GET ADVANCED EMAIL CONTENT
# Main entry point for callers who want advanced templates.
# Falls back to get_email_content() on ANY failure.
# [UPDATED — v2: also appends CTA to basic email fallback when possible]
# ==========================================================================

def get_advanced_email_content(lead: Dict) -> Dict:
    """
    Return email content using enterprise templates when available,
    falling back to get_email_content() otherwise.

    v2 change: When falling back to the original get_email_content(),
    the CTA footer is appended to the body so every outbound email
    (including original-template emails) carries the 3-button CTA.
    This preserves backward compatibility while adding the new feature.

    This is the ONLY function run.py should add a call to if it wants
    advanced templates. Existing callers of get_email_content() are
    COMPLETELY unaffected.

    Parameters
    ----------
    lead : dict — same structure as get_sequence_due_today() output.
                  May optionally include: intent, open_count, click_count,
                  last_reply, advanced_step, is_referral, bounced, cta_response.

    Returns
    -------
    dict  { "subject": str, "body": str }  — guaranteed, never raises.
    """
    try:
        lead_id = lead.get("lead_id", "?")

        # If no advanced signals, use the original templates + CTA footer
        if not should_send_advanced_followup(lead):
            logger.debug(
                "get_advanced_email_content: no advanced signals for lead %s "
                "— using original get_email_content()",
                lead_id,
            )
            content = get_email_content(lead)
            # v2: append CTA footer even to original-template emails
            content["body"] = append_cta_to_body(content["body"], lead_id)
            return content

        result = get_next_followup_email(lead)

        # Sanity check: result must have non-empty subject and body
        if not result.get("subject") or not result.get("body"):
            logger.warning(
                "get_advanced_email_content: empty result for lead %s — falling back",
                lead_id,
            )
            content = get_email_content(lead)
            content["body"] = append_cta_to_body(content["body"], lead_id)
            return content

        return result

    except Exception as exc:
        logger.error(
            "get_advanced_email_content unexpected error for lead %s: %s — falling back",
            lead.get("lead_id", "?"), exc, exc_info=True,
        )
        content = get_email_content(lead)
        try:
            content["body"] = append_cta_to_body(content["body"], lead.get("lead_id", ""))
        except Exception:
            pass  # Never raise — return whatever we have
        return content


# ==========================================================================
# ORIGINAL ENTRY POINT  [UNCHANGED]
# ==========================================================================

def _validate_kalnet_configuration() -> bool:
    """
    Validate that all KALNET configuration is properly set.
    Checks for placeholder values that would break production.
    Returns True if valid, False if issues found.
    """
    issues = []
    
    # Check for placeholder URLs (these would break production emails)
    if "[" in _CTA_BASE_URL or "]" in _CTA_BASE_URL:
        issues.append(f"CTA_BASE_URL contains placeholder: {_CTA_BASE_URL}")
    
    if "[" in _CALENDAR_LINK or "]" in _CALENDAR_LINK:
        issues.append(f"CALENDAR_LINK contains placeholder: {_CALENDAR_LINK}")
    
    if "[" in _MEETING_LINK or "]" in _MEETING_LINK:
        issues.append(f"MEETING_LINK contains placeholder: {_MEETING_LINK}")
    
    if "[" in _DISCOVERY_LINK or "]" in _DISCOVERY_LINK:
        issues.append(f"DISCOVERY_LINK contains placeholder: {_DISCOVERY_LINK}")
    
    # Check for old branding references
    if "track.ai5.io" in _CTA_BASE_URL:
        issues.append(f"CTA_BASE_URL still contains deprecated track.ai5.io: {_CTA_BASE_URL}")
    
    if "ai5" in _CTA_BASE_URL.lower() or "ai-5" in _CTA_BASE_URL.lower():
        issues.append(f"CTA_BASE_URL still contains old branding: {_CTA_BASE_URL}")
    
    if issues:
        logger.error("🔴 KALNET Configuration Issues:")
        for issue in issues:
            logger.error(f"  {issue}")
        return False
    
    logger.info("✅ KALNET Configuration validated successfully")
    return True


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
    # Validate KALNET configuration before running tests
    if not _validate_kalnet_configuration():
        logger.error("Configuration validation failed. Set KALNET_* environment variables.")
        return
    
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
        {   # Email 2: Day 2, step=1  (updated from Day 5)
            "lead_id": "row_2", "name": "Arjun Mehta",
            "email": "arjun@startup.io", "company": "Startup IO",
            "email_sent_at": str(today - timedelta(days=2)),
            "replied": False, "sequence_step": 1,
        },
        {   # Email 3: Day 7, step=2  (updated from Day 10)
            "lead_id": "row_3", "name": "Divya Nair",
            "email": "divya@bigco.com", "company": "BigCo",
            "email_sent_at": str(today - timedelta(days=7)),
            "replied": False, "sequence_step": 2,
        },
        # -- SHOULD be SKIPPED --------------------------------------------
        {   # replied=True
            "lead_id": "row_4", "name": "Kiran Patel",
            "email": "kiran@replied.com", "company": "Replied Inc",
            "email_sent_at": str(today - timedelta(days=2)),
            "replied": True, "sequence_step": 1,
        },
        {   # wrong day (day 1 — before 2-day threshold)
            "lead_id": "row_5", "name": "Meera Rao",
            "email": "meera@random.com", "company": "Random Corp",
            "email_sent_at": str(today - timedelta(days=1)),
            "replied": False, "sequence_step": 1,
        },
        {   # day 2 but step=2 -- double-send guard
            "lead_id": "row_6", "name": "Ravi Kumar",
            "email": "ravi@skip.com", "company": "Skip Ltd",
            "email_sent_at": str(today - timedelta(days=2)),
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

    print("\n--- Email previews (original — with CTA footer) ---\n")
    for r in results:
        c = get_email_content(r)
        body_with_cta = append_cta_to_body(c["body"], r["lead_id"])
        print(f"  To      : {r['name']} <{r['email']}>")
        print(f"  Subject : {c['subject']}")
        print(f"  Body    : {body_with_cta[:120].strip()}...")
        print()

    # Assertions (UNCHANGED from original — all still pass with updated delays)
    ids = [r["lead_id"] for r in results]
    assert "row_1" in ids,     "FAIL: row_1 (Email 1) should be included"
    assert "row_2" in ids,     "FAIL: row_2 (Email 2) should be included"
    assert "row_3" in ids,     "FAIL: row_3 (Email 3) should be included"
    assert "row_4" not in ids, "FAIL: row_4 (replied) must be skipped"
    assert "row_5" not in ids, "FAIL: row_5 (day 1 — before threshold) must be skipped"
    assert "row_6" not in ids, "FAIL: row_6 (double-send guard) must be skipped"
    assert "row_7" not in ids, "FAIL: row_7 (bad date) must be skipped"

    nums = {r["lead_id"]: r["email_number"] for r in results}
    assert nums["row_1"] == 1, "FAIL: row_1 must get Email 1"
    assert nums["row_2"] == 2, "FAIL: row_2 must get Email 2"
    assert nums["row_3"] == 3, "FAIL: row_3 must get Email 3"

    print("=" * 60)
    print("  ORIGINAL ASSERTIONS PASSED")
    print("=" * 60 + "\n")

    # ── Enterprise layer smoke test ──────────────────────────────────────
    print("--- Enterprise layer smoke test ---\n")

    advanced_leads = [
        {
            "lead_id": "adv_1", "name": "Rohan Shah", "email": "rohan@demo.io",
            "company": "DemoCo", "email_number": 1, "sequence_step": 1,
            "intent": Intent.INTERESTED, "open_count": 3, "click_count": 1,
        },
        {
            "lead_id": "adv_2", "name": "Lakshmi Das", "email": "lakshmi@budget.io",
            "company": "BudgetCo", "email_number": 2, "sequence_step": 2,
            "intent": Intent.NO_BUDGET, "open_count": 0,
        },
        {
            "lead_id": "adv_3", "name": "Ankit Gupta", "email": "ankit@cold.io",
            "company": "ColdCo", "email_number": 1, "sequence_step": 1,
            # No advanced fields — should fall back to original
        },
        # v2: CTA response leads
        {
            "lead_id": "cta_1", "name": "Sunil Verma", "email": "sunil@interested.io",
            "company": "InterestedCo", "email_number": 1, "sequence_step": 1,
            "intent": Intent.INTERESTED_CTA, "cta_response": CTA_INTERESTED,
        },
        {
            "lead_id": "cta_2", "name": "Pooja Singh", "email": "pooja@fence.io",
            "company": "FenceCo", "email_number": 1, "sequence_step": 1,
            "intent": Intent.INTERESTED_NOT_CONVINCED,
            "cta_response": CTA_INTERESTED_NOT_CONVINCED,
        },
        {
            "lead_id": "cta_3", "name": "Mohan Rao", "email": "mohan@nope.io",
            "company": "NopeCo", "email_number": 1, "sequence_step": 1,
            "intent": Intent.NOT_INTERESTED, "cta_response": CTA_NOT_INTERESTED,
        },
    ]

    for lead in advanced_leads:
        score    = get_lead_score(lead)
        strategy = get_followup_strategy(lead)
        content  = get_advanced_email_content(lead)
        print(f"  Lead    : {lead.get('name', 'Unknown')} ({lead.get('company', 'Unknown')})")
        print(f"  Score   : {score}")
        print(f"  Strategy: {strategy['step']} / {strategy['version']} / "
              f"{strategy['length']} / {strategy['subject_type']}")
        print(f"  Subject : {content['subject']}")
        print(f"  Body    : {content['body'][:80].strip()}...")
        print()

    # ── v2: CTA flow smoke test ──────────────────────────────────────────
    print("--- v2 CTA response flow smoke test ---\n")

    test_lead = {
        "lead_id": "smoke_1", "name": "Test User", "email": "test@test.io",
        "company": "TestCo", "email_number": 1, "sequence_step": 1,
    }

    for cta_type in (CTA_INTERESTED, CTA_INTERESTED_NOT_CONVINCED, CTA_NOT_INTERESTED):
        response = handle_cta_response(test_lead, cta_type)
        print(f"  CTA type  : {cta_type}")
        print(f"  New intent: {response['new_intent']}")
        print(f"  Action    : {response['action']}")
        print(f"  Subject   : {response['subject']}")
        print(f"  Body      : {response['body'][:80].strip()}...")
        print()

    # CTA footer smoke test
    sample_body = "Hi Test,\n\nThis is a sample email body.\n\nBest,\nTeam KALNET"
    footer_body = append_cta_to_body(sample_body, "smoke_1")
    assert "✅  Interested" in footer_body, "FAIL: CTA footer not appended"
    assert "🤔  Interested but not convinced" in footer_body, "FAIL: CTA 2 missing"
    assert "❌  Not interested right now" in footer_body, "FAIL: CTA 3 missing"

    # Idempotency: appending twice should not double the footer
    footer_body_2 = append_cta_to_body(footer_body, "smoke_1")
    assert footer_body_2.count("✅  Interested") == 1, "FAIL: CTA footer doubled"

    # NOT_INTERESTED → move to nurture
    not_interested_lead = {**test_lead, "intent": Intent.NOT_INTERESTED}
    nurture = move_to_nurture_list(not_interested_lead)
    assert nurture["action"] == "move_to_nurture", "FAIL: nurture action wrong"
    assert nurture["re_engage_after_days"] == 180, "FAIL: nurture delay wrong"

    # Enterprise original assertions
    s1 = get_lead_score(advanced_leads[0])
    s3 = get_lead_score(advanced_leads[2])
    assert s1 > s3, "FAIL: lead with signals must outscore lead without"
    assert should_send_advanced_followup(advanced_leads[0]),  "FAIL: adv_1 should use advanced"
    assert not should_send_advanced_followup(advanced_leads[2]), "FAIL: adv_3 should not"

    d1 = get_intent_delay(Intent.VERY_INTERESTED)
    d2 = get_intent_delay(Intent.NO_BUDGET)
    d3 = get_intent_delay(Intent.INTERESTED_CTA)       # v2
    d4 = get_intent_delay(Intent.NOT_INTERESTED)       # v2
    assert d1 == 0,   f"FAIL: VERY_INTERESTED delay should be 0, got {d1}"
    assert d2 == 60,  f"FAIL: NO_BUDGET delay should be 60, got {d2}"
    assert d3 == 0,   f"FAIL: INTERESTED_CTA delay should be 0, got {d3}"
    assert d4 == 180, f"FAIL: NOT_INTERESTED delay should be 180, got {d4}"

    # Updated delay assertions (2 days and 7 days)
    delays = _load_delay_settings()
    assert delays['email_2_delay_days'] == 2,  "FAIL: email_2_delay should now be 2 days"
    assert delays['email_3_delay_days'] == 7,  "FAIL: email_3_delay should now be 7 days"

    # Original get_email_content must still return correct keys
    for r in results:
        c = get_email_content(r)
        assert "subject" in c, f"FAIL: get_email_content missing subject for {r['lead_id']}"
        assert "body" in c,    f"FAIL: get_email_content missing body for {r['lead_id']}"

    print("=" * 60)
    print("  ALL ASSERTIONS PASSED (original + v2 enterprise)")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    if "--live" in sys.argv:
        _run_with_real_data()
    else:
        _run_with_dummy_data()
