# Kalnet AI-5 Dashboard — Build Summary (June 2, 2026)

## Overview
Full-stack web dashboard for the Kalnet AI-5 Email Automation Pipeline, replacing the Streamlit prototype with a production-ready React + FastAPI application.

---

## Architecture

```
Kalnet-AI-5/
├── api/                     # FastAPI backend (REST API)
│   ├── app.py              # Main server, SPA serving
│   ├── auth.py             # JWT authentication
│   ├── models.py           # SQLite models (users, settings, logs)
│   ├── config.py           # Config constants (SECRET_KEY required)
│   └── routes/
│       ├── auth_routes.py  # Login/register
│       ├── metrics.py      # KPI data
│       ├── leads.py        # Leads CRUD with filters
│       ├── replies.py      # Reply data
│       ├── analytics.py    # Analytics & subject lines
│       ├── settings.py     # User settings CRUD
│       └── pipeline.py     # Run pipeline & logs
│
├── pipeline/               # Email automation pipeline
│   ├── run.py             # Pipeline orchestrator (steps 1-6)
│   ├── check_replies.py   # IMAP reply detection
│   ├── sequence.py        # Follow-up sequence logic with dynamic delays
│   ├── sheets.py          # Google Sheets integration (google-auth)
│   └── send_email.py      # SMTP email sender with retry logic
│
├── analytics/
│   └── report.py          # Metrics calculation & formatting
│
├── config/
│   └── service_account.json  # Google service account (gitignored)
│
├── api/requirements.txt   # FastAPI backend deps
├── requirements.txt       # Full project deps
├── start-dashboard.bat    # One-click launcher (relative paths)
└── BUILD_SUMMARY.md       # This file
```

## Features Built

### Backend (FastAPI)
- **JWT Authentication** — Protected all API routes, PBKDF2 password hashing
- **Automatic Swagger Docs** at `/docs`
- **REST Endpoints** — metrics, leads, replies, analytics, subject lines, settings, pipeline execution
- **SQLite Database** — stores users, settings, pipeline run history
- **Serves built React app** — Single port (8000) for both API and frontend

### Frontend (React)
- **Login Page** — JWT-based authentication
- **Overview** — 5 KPI cards, email funnel bar chart, tier breakdown pie chart, pending actions
- **Leads** — Searchable/sortable/filterable table with pagination
- **Replies** — Reply cards with positive/unsubscribed filters
- **Analytics** — Charts for sequence steps and tier distribution
- **Sent Emails** — Table showing what was sent (name, subject, email type, datetime, status) + subject line performance ranking, sorted by timestamp
- **Settings** — Pipeline config editor, Run Pipeline button with status feedback, log viewer (pipeline, email, replies, sequence, replies_summary)
- **Auto-refresh** — All pages poll every 30 seconds, manual refresh button available
- **Dark theme** — Professional dark UI with Tailwind CSS

### Pipeline Enhancements
- Added `reply_snippet` column (col K) to Google Sheets for storing reply text
- `mark_replied()` saves the reply snippet to the sheet
- `mark_unsubscribed()` now sets replied + opt_out + reply_snippet columns
- Processed emails are auto-archived from INBOX (no re-scans)
- Replied leads re-checked for unsubscribe requests
- Sequence delay settings read from SQLite DB (email_2_delay_days, email_3_delay_days) — configurable via Settings page

## Production Cleanup (June 2)

### Deleted Dead Code
- `dashboard/` — Deprecated Streamlit prototype
- `tests/` — Test files
- `pipeline/unsubscribe.py` — Dead code (3 versions of is_unsubscribe_request existed)
- `config/config.py` — Useless stub
- `config/mock_google_sheets.py` — Mock mode disabled

### Security Fixes
- `SECRET_KEY` no longer has a hardcoded default — crashes at startup if missing in `.env`
- Email credential validation moved from module load to inside `send_email()` function
- Removed password placeholder hint from login page

### Logic Bug Fixes
- **Double emoji replacement** — Removed `ASCIIFormatter`, kept only `UTF8SafeStreamHandler`
- **Double logging** — Removed `basicConfig` from `send_email.py`, uses module logger
- **Redundant Sheets API calls** — `step_5_generate_analytics()` now accepts optional leads param
- **Missing `mail.close()`** — Added before `mail.logout()` in IMAP finally block
- **`print()` → logger** — All `print()` calls in `sheets.py` and `check_replies.py` replaced with proper logging

### Configuration
- `start-dashboard.bat` uses `%~dp0` for relative paths (works from any directory)
- `requirements.txt` — removed `pandas`, `streamlit`, `oauth2client`; added `google-auth*`
- `pipeline/sheets.py` — migrated from deprecated `oauth2client` to `google.auth`
- `sys.path.insert` centralized in `api/app.py` (removed from all route files)
- GitHub Actions workflow uses separate `EMAIL_USER` secret

### Frontend
- Log viewer dropdown includes `replies` and `sequence` logs
- Sent Emails table sorts by full timestamp (not just date)
- Leads filter: "All Opt-out" removed (only Active / Opted Out)
- Steps filter: Step 0 removed (only 1/2/3)
- Password field placeholder: generic instead of revealing default

## How to Run

**One-click launcher:**
```
start-dashboard.bat
```

**Manual:**
```bash
cd D:\programs\Python\Kalnet\Kalnet-AI-5
uvicorn api.app:app --reload --port 8000
```

**Open:** http://localhost:8000
**API Docs:** http://localhost:8000/docs

## Setup

**1. Generate a SECRET_KEY and add it to `.env`:**
```bash
# Windows (PowerShell)
python -c "import secrets; print(secrets.token_hex(32))"
```
Then add the output to `.env`:
```
SECRET_KEY=<paste_the_key_here>
```

**2. Run the dashboard:**
```bash
start-dashboard.bat
```
Or manually:
```bash
uvicorn api.app:app --reload --port 8000
```
