"""
Google Drive Service – Kundenordner mit 4 Unterordnern anlegen.
"""
from __future__ import annotations

import json

from google.oauth2 import service_account
from googleapiclient.discovery import build

from config import GOOGLE_SERVICE_ACCOUNT_JSON, GOOGLE_DRIVE_PARENT_FOLDER_ID

_SCOPES = ["https://www.googleapis.com/auth/drive"]

SUBFOLDERS = [
    "01_Verträge",
    "02_Rechnungen",
    "03_Berichte",
    "04_Kommunikation",
]


def _drive_service():
    sa_info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
    creds = service_account.Credentials.from_service_account_info(sa_info, scopes=_SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def create_client_folder(client_name: str) -> dict:
    service = _drive_service()

    main = service.files().create(
        body={
            "name": client_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [GOOGLE_DRIVE_PARENT_FOLDER_ID],
        },
        fields="id,name,webViewLink",
    ).execute()

    main_id: str = main["id"]
    subfolder_ids: dict[str, str] = {}

    for name in SUBFOLDERS:
        sub = service.files().create(
            body={
                "name": name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [main_id],
            },
            fields="id,name",
        ).execute()
        subfolder_ids[name] = sub["id"]

    return {
        "main_folder_id": main_id,
        "main_folder_url": main["webViewLink"],
        "subfolders": subfolder_ids,
    }
