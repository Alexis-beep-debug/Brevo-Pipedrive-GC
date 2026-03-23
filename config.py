import json
import os
from dotenv import load_dotenv

load_dotenv()

PIPEDRIVE_API_KEY = os.environ["PIPEDRIVE_API_KEY"]
BREVO_API_KEY = os.environ["BREVO_API_KEY"]
LEXOFFICE_API_KEY = os.environ.get("LEXOFFICE_API_KEY", "")

PIPEDRIVE_BASE = "https://api.pipedrive.com/v1"
BREVO_BASE = "https://api.brevo.com/v3"

# Google – Service-Account-JSON als Env-Var (Base64 oder raw JSON)
_gsa_raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "{}")
GOOGLE_SERVICE_ACCOUNT_INFO: dict = json.loads(_gsa_raw)

# Google Slides Template & Drive Folder
GOOGLE_SLIDES_TEMPLATE_ID = os.environ.get("GOOGLE_SLIDES_TEMPLATE_ID", "")
GOOGLE_DRIVE_PARENT_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_PARENT_FOLDER_ID", "")
GOOGLE_PROBLEM_SLIDE_ID = os.environ.get("GOOGLE_PROBLEM_SLIDE_ID", "")

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
