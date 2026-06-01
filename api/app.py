from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from api.models import init_db, User, SessionLocal
from api.auth import hash_password
from api.routes import auth_routes, metrics, leads, replies, analytics, settings, pipeline

app = FastAPI(title="Kalnet AI-5 Dashboard", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router)
app.include_router(metrics.router)
app.include_router(leads.router)
app.include_router(replies.router)
app.include_router(analytics.router)
app.include_router(settings.router)
app.include_router(pipeline.router)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"


@app.on_event("startup")
def startup():
    init_db()
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            db.add(User(username="admin", password_hash=hash_password("admin123")))
            db.commit()
    finally:
        db.close()


if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        file_path = FRONTEND_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIR / "index.html")
