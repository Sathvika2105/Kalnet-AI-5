from fastapi import APIRouter, Depends, Header, HTTPException
from api.auth import get_current_user
from api.models import User
import os
import threading
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["pipeline"])


def run_pipeline_task():
    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        from pipeline.run import run_pipeline
        run_pipeline()
    except Exception as e:
        logger.error(f"Pipeline task failed: {e}")


# ── For UI (requires login) ──────────────────────────
@router.post("/pipeline/run")
def run_pipeline_ui(current_user: User = Depends(get_current_user)):
    thread = threading.Thread(target=run_pipeline_task)
    thread.daemon = True
    thread.start()
    return {"message": "Pipeline triggered successfully"}


# ── For GitHub Actions (requires secret header) ──────
@router.post("/trigger-pipeline")
def trigger_pipeline(x_pipeline_secret: str = Header(None)):
    secret = os.getenv("PIPELINE_TRIGGER_SECRET")
    if not secret or x_pipeline_secret != secret:
        raise HTTPException(status_code=401, detail="Unauthorized")
    thread = threading.Thread(target=run_pipeline_task)
    thread.daemon = True
    thread.start()
    return {"status": "Pipeline triggered successfully"}


# ── Logs ─────────────────────────────────────────────
@router.get("/logs/{log_type}")
def get_logs(log_type: str, current_user: User = Depends(get_current_user)):
    log_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
    log_file = os.path.join(log_dir, f"{log_type}.log")
    if not os.path.exists(log_file):
        return {"content": "Log file not found"}
    with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()
    return {"content": "".join(lines[-200:])}