import os
from dotenv import load_dotenv

load_dotenv()

PIPEDRIVE_API_KEY = os.environ.get("PIPEDRIVE_API_KEY") or os.environ.get("PIPEDRIVE_API_TOKEN", "")
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
LEXOFFICE_API_KEY = os.environ.get("LEXOFFICE_API_KEY", "")

PIPEDRIVE_BASE = "https://api.pipedrive.com/v1"
BREVO_BASE = "https://api.brevo.com/v3"

# Pipedrive User-ID für Aufgaben-Zuweisung
PIPEDRIVE_OWNER_USER_ID = int(os.environ.get("PIPEDRIVE_OWNER_USER_ID", "20546477"))

# Deal-Status-Mapping Pipedrive → Brevo
DEAL_STATUS_MAP = {
    "open": "Offen",
    "won": "Kunde",
    "lost": "Verloren",
    None: "Kein Interesse",
}

# Label-Mapping Pipedrive label_id → Klarname
# Wird durch step1_preflight.py vervollständigt – hier bekannte Werte als Fallback
LABEL_MAP: dict[int, str] = {
    8: "Büro",
    58: "Gesundheit/Medizin",
}
