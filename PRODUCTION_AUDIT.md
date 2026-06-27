# Production Audit — Kalnet AI-5

> Generated: 2026-06-27
> Audited by: opencode
> **Status: All critical and high-priority items fixed as of 2026-06-27**

---

## 🔴 CRITICAL (will crash in production)

### 1. CORS blocks all frontend traffic
**File:** `api/app.py:17`
```python
allow_origins=[]  # ← empty list
```
`allow_origins=[]` means no origin is permitted. The frontend served from any domain/port (including dev server on `localhost:5173`) will be blocked by CORS. The dashboard is inaccessible.

---

### 2. `bulk_add_leads` return type mismatch
**File:** `api/routes/leads.py:88-92`, `pipeline/sheets.py:245`
`bulk_add_leads()` returns `False` on error (a `bool`), but the caller expects a `dict` and accesses `result['added']` / `result['skipped']`. A transient Sheets API failure crashes the endpoint with `TypeError: 'bool' object is not subscriptable`.

---

### 3. `int()` crash on bad `sequence_step` data
**File:** `pipeline/sequence.py:2542`
```python
sequence_step = int(lead.get("sequence_step", 0) or 0)
```
If a lead row contains a non-numeric string (e.g. `"abc"`), `int()` raises `ValueError` and crashes the entire pipeline run.

---

### 4. NameError in `check_replies` import handler
**File:** `pipeline/check_replies.py:17-19`
```python
except ImportError:
    log.error("Cannot import sheets.py...")  # ← `log` not defined until line 46
    sys.exit(1)
```
The `except` block references `log` before it is defined. If the `sheets` import fails, this handler itself crashes with `NameError: name 'log' is not defined`.

---

### 5. Polling interval leaked on unmount (Overview)
**File:** `frontend/src/pages/Overview.jsx:37-61`
`pollRef` (the 2-second pipeline status interval) is never cleared when the user navigates away. The interval continues calling `setRunning`, `setPipelineMsg`, `refresh` on an unmounted component — causing React state-update warnings and wasted API calls.

---

### 6. Settings fetch has no error handler
**File:** `frontend/src/pages/Settings.jsx:26`
```js
api.get('/settings').then(res => {
    setSettings(res.data);
    setLoading(false);
})  // ← no .catch()
```
If the API call fails, `loading` is never set to `false`. The user sees a perpetual `SkeletonPage` with no way to recover.

---

### 7. `.toFixed(1)` on undefined value (SubjectLines)
**File:** `frontend/src/pages/SubjectLines.jsx:159,170`
```js
{s.rate.toFixed(1)}%
style={{ width: `${Math.min(s.rate, 100)}%` }}
```
If the API response omits `rate` for a subject line, `s.rate` is `undefined`. `undefined.toFixed(1)` throws a runtime error that crashes the entire page.

---

### 8. `|| ''` masks zero values (Settings)
**File:** `frontend/src/pages/Settings.jsx:215,225,236,245,254`
```js
value={settings.delay_between_emails || ''}
```
If the value is `0` (a valid setting meaning "no delay"), the expression evaluates to `''`. The input appears empty, and on save the backend receives an empty string instead of `0`.

---

### 9. Destructure crash on missing key (Analytics)
**File:** `frontend/src/pages/Analytics.jsx:15`
```js
const { overview, sequence_steps } = data
```
If the API returns a response without an `overview` key, `Object.entries(overview.tier_breakdown || {})` crashes because `overview` is `undefined`. The `if (!data)` check doesn't protect against shape mismatch.

---

### 10. Missing `onAction` guard (EmptyState)
**File:** `frontend/src/components/EmptyState.jsx:3`
```js
{action && <button onClick={onAction} ...>}
```
`onAction` is optional in destructuring, but if `action` is truthy and the consumer doesn't pass `onAction`, clicking the button throws `undefined is not a function`.

---

## 🟡 HIGH

### 11. Dead conditional branch (sequence.py)
**File:** `pipeline/sequence.py:1249-1266`
```python
if Intent.INTERESTED in {}:  # ← always False
```
The entire branch never executes. Dead code.

---

### 12. Overwritten dict entries (sequence.py)
**File:** `pipeline/sequence.py:1553-1586`
Inline definitions for `ADVANCED_EMAIL_SUBJECTS` and `ADVANCED_EMAIL_BODIES` are defined across ~350 lines, then immediately overwritten by loop assignments. The initial definitions are wasted computation.

---

### 13. N+1 API calls to Google Sheets
**File:** `pipeline/sheets.py:262-278`
`mark_email_sent` makes 4 separate `update_cell` calls per lead instead of a single batch update. Same pattern in `mark_replied` (lines 311-323). This wastes API quota and is ~4× slower.

---

### 14. TOCTOU race condition in pipeline trigger
**File:** `api/routes/pipeline.py:56-61`
The threading lock is released before `threading.Thread.start()`. Between releasing the lock and the thread starting (which acquires the lock to set `running=True`), another request could also pass the `running` check and start a second pipeline instance.

---

### 15. Global state without locks in sheets.py
**File:** `pipeline/sheets.py:21-42`
`_sheets_client` and `_sheets_sheet` are module-level globals mutated inside `_get_sheets()` without any threading lock. Under concurrent requests, two threads could both pass the `if _sheets_sheet is not None` check and initialize simultaneously.

---

### 16. Default admin password
**File:** `api/config.py:19`
```python
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
```
If the env var is unset in production, the password is trivially guessable.

---

### 17. No rate limiting on login
**File:** `api/routes/auth_routes.py:22`
`POST /api/auth/login` has no throttling — brute-force attacks are unmitigated.

---

### 18. Pipeline run logic duplicated 3×
**Files:** `Layout.jsx:40-76`, `Overview.jsx:30-65`, `Settings.jsx:89-126`
The entire `runPipeline` function (API POST, 2s polling, status checks, success/failure handling, sound effects, toasts) is copy-pasted across three files with only cosmetic differences.

---

### 19. Fragile dual-loop logic in useKeyboardShortcuts
**File:** `frontend/src/hooks/useKeyboardShortcuts.js:7-16`
The first loop over shortcuts can `continue` past a matching shortcut when the user is focused on an input, bypassing the `allowInput` check. The interaction between the two loops is hard to reason about.

---

## 🔵 MEDIUM

### 20. Duplicate `Depends` import
**File:** `api/routes/settings.py:7`
`from fastapi import Depends` appears on both line 1 and line 7.

---

### 21. Array index as React `key`
**Files:** `DataTable.jsx:80`, `SubjectLines.jsx:91,158`, `Replies.jsx:75`, `BulkUploadModal.jsx:217`
Using array index as `key` defeats React reconciliation and causes unnecessary DOM re-renders when data changes order or is filtered.

---

### 22. No caching on `get_all_leads()`
**File:** `pipeline/sheets.py:142-155`
Every API route that needs lead data re-fetches the entire sheet independently. Multiple routes (`metrics`, `leads`, `replies`, `analytics`) all call `get_all_leads()` per request without any caching.

---

### 23. JWT stored in localStorage
**File:** `frontend/src/api/client.js:8`
`localStorage.getItem('token')` exposes the auth token to any JavaScript running on the same origin (XSS vulnerability). `HttpOnly` cookies are the safer alternative.

---

### 24. `sys.path.insert` pollution
**Files:** `api/app.py:2`, `api/routes/leads.py:9`, `pipeline/check_replies.py:13`, `analytics/report.py:3`, `pipeline/run.py:43`
Every file prepends to `sys.path`, making it longer on each import. Breaks if the project is packaged or the directory structure changes.

---

### 25. Keyboard shortcuts re-registered every render
**Files:** `Layout.jsx:78-80`, `Settings.jsx:84-87`
Inline array literal in `useKeyboardShortcuts` creates a new reference every render, causing the effect to re-run (addEventListener/removeEventListener) on every render cycle.

---

### 26. Unused import
**File:** `frontend/src/pages/Settings.jsx:8`
`Radio` is imported from `lucide-react` but never used.

---

## 🟣 ADDITIONAL OBSERVATIONS

| # | File | Issue |
|---|------|-------|
| 27 | `pipeline/run.py:105-106` | Hardcoded `DELAY_BETWEEN_EMAILS` (30s) and `MAX_EMAILS_PER_RUN` (50) duplicate DB settings loaded in `sequence.py` |
| 28 | `api/models.py:6` | `check_same_thread=False` disables SQLite thread-safety — concurrent writes can cause `database is locked` errors |
| 29 | `pipeline/check_replies.py:269,289,326` | Silent `pass` on IMAP `store()` failures — errors swallowed |
| 30 | `pipeline/sheets.py:61-65` | `_safe_int` silently masks bad data (returns `0` instead of flagging the error) |
