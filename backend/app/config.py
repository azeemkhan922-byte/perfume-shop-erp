import os

# SQLite file for local use (zero install). For the cloud set DATABASE_URL to the Neon postgres:// URL.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///azeem.db")
# Long random string. REQUIRED in production; changing it logs the owner out.
SECRET_KEY = os.environ.get("SECRET_KEY", "")
TOKEN_HOURS = int(os.environ.get("TOKEN_HOURS", "12"))
# Browser addresses allowed to call the API (comma separated). Add your deployed frontend URL here.
CORS_ORIGINS = [o.strip() for o in os.environ.get(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
SHOP_NAME = os.environ.get("SHOP_NAME", "AZEEM FRAGRANCES")
# Shop local time as minutes ahead of UTC (India = 330). Decides which "day" a sale belongs to.
SHOP_UTC_OFFSET_MINUTES = int(os.environ.get("SHOP_UTC_OFFSET_MINUTES", "330"))
# Folder with the built React app (frontend/dist). When present, the backend serves it, so one service does everything.
from pathlib import Path
FRONTEND_DIST = os.environ.get("FRONTEND_DIST", str(Path(__file__).resolve().parents[2] / "frontend" / "dist"))
