from fastapi import APIRouter, Depends
from api.auth import get_current_user
from api.models import User
import os

router = APIRouter(prefix="/api", tags=["pipeline"])


@router.post("/pipeline/run")
def run_pipeline(current_user: User = Depends(get_current_user)):
    try:
        from pipeline.run import run_pipeline
        run_pipeline()
        return {"message": "Pipeline executed successfully"}
    except Exception as e:
        return {"error": str(e)}, 500


@router.get("/logs/{log_type}")
def get_logs(log_type: str, current_user: User = Depends(get_current_user)):
    log_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
    log_file = os.path.join(log_dir, f"{log_type}.log")

    if not os.path.exists(log_file):
        return {"content": "Log file not found"}

    with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    return {"content": "".join(lines[-200:])}
