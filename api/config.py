import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY must be set in .env — generate one with: python -c 'import secrets; print(secrets.token_hex(32))'"
    )
if len(SECRET_KEY) < 32:
    raise RuntimeError("SECRET_KEY must be at least 32 characters long")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

DATABASE_URL = f"sqlite:///{Path(__file__).parent / 'dashboard.db'}"

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
if not ADMIN_USERNAME:
    raise RuntimeError("ADMIN_USERNAME must be set in .env")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    raise RuntimeError("ADMIN_PASSWORD must be set in .env")
if len(ADMIN_PASSWORD) < 8:
    raise RuntimeError("ADMIN_PASSWORD must be at least 8 characters long")
