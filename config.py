import os
from dotenv import load_dotenv

load_dotenv()

# ── CRM + Email Marketing ─────────────────────────────────────────────────────
PIPEDRIVE_API_KEY = os.environ.get("PIPEDRIVE_API_KEY", "")
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")

PIPEDRIVE_BASE = "https://api.pipedrive.com/v1"
BREVO_BASE = "https://api.brevo.com/v3"

DEAL_STATUS_MAP = {
    "open": "Offen",
    "won": "Kunde",
    "lost": "Verloren",
    None: "Kein Interesse",
}

LABEL_MAP: dict[int, str] = {
    8: "Büro",
    58: "Gesundheit/Medizin",
}

# ── Google Service Account (Drive + Sheets) ───────────────────────────────────
GOOGLE_SERVICE_ACCOUNT_JSON: str = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
GOOGLE_DRIVE_PARENT_FOLDER_ID: str = os.environ.get("GOOGLE_DRIVE_PARENT_FOLDER_ID", "")

# ── Google OAuth2 (Gmail-Versand) ─────────────────────────────────────────────
GOOGLE_CLIENT_ID: str = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET: str = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REFRESH_TOKEN: str = os.environ.get("GOOGLE_REFRESH_TOKEN", "")

# ── Absender-Informationen ────────────────────────────────────────────────────
YOUR_NAME: str = os.environ.get("YOUR_NAME", "Bethke & Partner")
YOUR_ADDRESS: str = os.environ.get("YOUR_ADDRESS", "")
YOUR_EMAIL: str = os.environ.get("YOUR_EMAIL", "")
YOUR_TAX_ID: str = os.environ.get("YOUR_TAX_ID", "")

# ── Close CRM (Onboarding-Webhook) ───────────────────────────────────────────
CLOSE_API_KEY: str = os.environ.get("CLOSE_API_KEY", "")
CLOSE_WEBHOOK_SECRET: str = os.environ.get("CLOSE_WEBHOOK_SECRET", "")

# ── Onboarding ────────────────────────────────────────────────────────────────
ONBOARDING_UI_URL: str = os.environ.get("ONBOARDING_UI_URL", "http://localhost:5173")

# ── CORS ──────────────────────────────────────────────────────────────────────
ALLOWED_ORIGINS: list[str] = [
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if o.strip()
]
