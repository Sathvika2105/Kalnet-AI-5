from fastapi import APIRouter, Depends, Header, HTTPException
from api.auth import get_current_user
from api.models import User
import os
import threading
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["pipeline"])

# ── Thread-safe pipeline status tracker ──────────────
_pipeline_status = {"running": False, "success": None, "message": "", "error": "", "timestamp": None}
_status_lock = threading.Lock()


def _set_status(running=None, success=None, message=None, error=None):
    with _status_lock:
        if running is not None:
            _pipeline_status["running"] = running
        if success is not None:
            _pipeline_status["success"] = success
        if message is not None:
            _pipeline_status["message"] = message
        if error is not None:
            _pipeline_status["error"] = error
        _pipeline_status["timestamp"] = datetime.now().isoformat()


def run_pipeline_task():
    _set_status(running=True, success=None, message="Pipeline is running...", error="")
    try:
        from pipeline.run import run_pipeline
        run_pipeline()
        _set_status(running=False, success=True, message="Pipeline completed successfully", error="")
    except Exception as e:
        import traceback
        error_msg = str(e)
        tb = traceback.format_exc()
        logger.error(f"Pipeline task failed: {error_msg}\n{tb}")
        _set_status(running=False, success=False, message="Pipeline failed", error=error_msg)


# ── Pipeline status (for UI polling) ───────────────
@router.get("/pipeline/status")
def get_pipeline_status(current_user: User = Depends(get_current_user)):
    with _status_lock:
        return dict(_pipeline_status)


def _trigger_pipeline():
    with _status_lock:
        if _pipeline_status["running"]:
            return False
        _pipeline_status["running"] = True
        _pipeline_status["success"] = None
        _pipeline_status["message"] = "Pipeline is running..."
        _pipeline_status["error"] = ""
        _pipeline_status["timestamp"] = datetime.now().isoformat()
    thread = threading.Thread(target=run_pipeline_task)
    thread.daemon = True
    thread.start()
    return True


# ── For UI (requires login) ──────────────────────────
@router.post("/pipeline/run")
def run_pipeline_ui(current_user: User = Depends(get_current_user)):
    if not _trigger_pipeline():
        return {"message": "Pipeline is already running"}
    return {"message": "Pipeline triggered successfully"}


# ── For GitHub Actions (requires secret header) ──────
@router.post("/trigger-pipeline")
def trigger_pipeline(x_pipeline_secret: str = Header(None)):
    secret = os.getenv("PIPELINE_TRIGGER_SECRET")
    if not secret or x_pipeline_secret != secret:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not _trigger_pipeline():
        return {"status": "Pipeline already running"}
    return {"status": "Pipeline triggered successfully"}


# ── Logs ─────────────────────────────────────────────
@router.get("/logs/{log_type}")
def get_logs(log_type: str, current_user: User = Depends(get_current_user)):
    log_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
    log_file = os.path.join(log_dir, f"{log_type}.log")
    if not os.path.exists(log_file):
        return {"content": "Log file not found - run the pipeline first. Logs are also available in Render's runtime logs."}
    with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()
    return {"content": "".join(lines[-200:])}