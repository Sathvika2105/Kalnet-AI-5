# Kalnet AI-5 Dashboard — Build Summary (June 1, 2026)

## Overview
Built a full-stack web dashboard for the Kalnet AI-5 Email Automation Pipeline, replacing the Streamlit prototype with a production-ready React + FastAPI application.

---

## Architecture

```
Kalnet-AI-5/
├── api/                     # FastAPI backend (REST API)
│   ├── app.py              # Main server, SPA serving
│   ├── auth.py             # JWT authentication
│   ├── models.py           # SQLite models (users, settings, logs)
│   ├── config.py           # Config constants
│   └── routes/
│       ├── auth_routes.py  # Login/register
│       ├── metrics.py      # KPI data
│       ├── leads.py        # Leads CRUD with filters
│       ├── replies.py      # Reply data
│       ├── analytics.py    # Analytics & subject lines
│       ├── settings.py     # User settings CRUD
│       └── pipeline.py     # Run pipeline & logs
│
├── frontend/               # React + Vite + Tailwind
│   └── src/
│       ├── api/client.js   # Axios with JWT interceptor
│       ├── context/AuthContext.jsx
│       ├── hooks/usePolling.js  # Auto-refresh hook
│       ├── components/
│       │   ├── Layout.jsx  # Sidebar navigation
│       │   ├── KPICard.jsx # Metric display cards
│       │   └── DataTable.jsx # Sortable, searchable table
│       └── pages/
│           ├── Login.jsx
│           ├── Overview.jsx       # KPI cards, charts
│           ├── Leads.jsx          # Filterable leads table
│           ├── Replies.jsx        # Reply cards with snippets
│           ├── Analytics.jsx      # Charts & breakdowns
│           ├── SubjectLines.jsx   # Sent emails + performance
│           └── Settings.jsx       # Config, run pipeline, logs
│
├── dashboard/              # (deprecated Streamlit app)
├── start-dashboard.bat     # One-click launcher
└── requirements.txt        # Updated dependencies
```

## Features Built

### Backend (FastAPI)
- **JWT Authentication** — Protected all API routes
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
- **Sent Emails** — Table showing what was sent to each client (name, subject, email type, date, status) + subject line performance ranking
- **Settings** — Pipeline config editor, Run Pipeline button with status feedback, log viewer (pipeline, email, replies_summary)
- **Auto-refresh** — All pages poll every 30 seconds, manual refresh button available
- **Dark theme** — Professional dark UI with Tailwind CSS

### Pipeline Enhancements
- Added `reply_snippet` column (col K) to Google Sheets for storing reply text
- `mark_replied()` now saves the reply snippet to the sheet

### Bug Fixes
- **Date format parsing** — `normalize_date()` added to handle MM/DD/YYYY dates from Google Sheets (Python's `date.fromisoformat()` only accepts YYYY-MM-DD)
- **Sequence day matching** — Changed `days_elapsed == 5/10` to `days_elapsed >= 5/10` so follow-up emails fire even if the pipeline misses the exact scheduled day

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
**Login:** admin / admin123
