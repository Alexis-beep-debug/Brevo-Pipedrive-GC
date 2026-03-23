"""
Google Sheets Service – Kunden-Dashboard anlegen.
"""
from __future__ import annotations

import json
from datetime import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build

from config import GOOGLE_SERVICE_ACCOUNT_JSON

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _creds():
    sa_info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
    return service_account.Credentials.from_service_account_info(sa_info, scopes=_SCOPES)


def _sheets():
    return build("sheets", "v4", credentials=_creds(), cache_discovery=False)


def _drive():
    return build("drive", "v3", credentials=_creds(), cache_discovery=False)


def create_client_dashboard(
    client_name: str,
    client_email: str,
    client_company: str,
    deal_title: str,
    deal_value: float,
    currency: str,
    drive_folder_id: str | None = None,
    share_with_email: str | None = None,
) -> dict:
    today = datetime.now().strftime("%d.%m.%Y")
    title = f"Dashboard – {client_name} – {today}"

    spreadsheet = _sheets().spreadsheets().create(
        body={
            "properties": {"title": title},
            "sheets": [
                {"properties": {"title": "Projektübersicht", "sheetId": 0, "index": 0}},
                {"properties": {"title": "Rechnungen", "sheetId": 1, "index": 1}},
                {"properties": {"title": "Kommunikation", "sheetId": 2, "index": 2}},
            ],
        },
        fields="spreadsheetId,spreadsheetUrl",
    ).execute()

    sid = spreadsheet["spreadsheetId"]
    url = spreadsheet["spreadsheetUrl"]
    svc = _sheets()

    overview = [
        ["BETHKE & PARTNER – KUNDEN-DASHBOARD", ""],
        [""],
        ["KUNDENDATEN", ""],
        ["Name", client_name],
        ["Unternehmen", client_company],
        ["E-Mail", client_email],
        [""],
        ["PROJEKTDATEN", ""],
        ["Projekt", deal_title],
        ["Wert (netto)", f"{deal_value:,.2f} {currency}".replace(",", "X").replace(".", ",").replace("X", ".")],
        ["Onboarding-Datum", today],
        ["Status", "Aktiv"],
    ]
    svc.spreadsheets().values().update(
        spreadsheetId=sid, range="Projektübersicht!A1",
        valueInputOption="RAW", body={"values": overview},
    ).execute()

    svc.spreadsheets().values().update(
        spreadsheetId=sid, range="Rechnungen!A1",
        valueInputOption="RAW",
        body={"values": [["Rechnungsnummer", "Datum", "Beschreibung", f"Betrag ({currency}, netto)", "Status"]]},
    ).execute()

    svc.spreadsheets().values().update(
        spreadsheetId=sid, range="Kommunikation!A1",
        valueInputOption="RAW",
        body={"values": [
            ["Datum", "Art", "Betreff", "Notizen"],
            [today, "Onboarding", "Willkommensmail gesendet", "Automatisch via Onboarding-System"],
        ]},
    ).execute()

    _apply_header_formatting(svc, sid)

    drive_svc = _drive()

    if drive_folder_id:
        file_meta = drive_svc.files().get(fileId=sid, fields="parents").execute()
        prev_parents = ",".join(file_meta.get("parents", []))
        drive_svc.files().update(
            fileId=sid, addParents=drive_folder_id,
            removeParents=prev_parents, fields="id,parents",
        ).execute()

    if share_with_email:
        drive_svc.permissions().create(
            fileId=sid,
            body={"type": "user", "role": "writer", "emailAddress": share_with_email},
            sendNotificationEmail=False,
        ).execute()

    return {"spreadsheet_id": sid, "spreadsheet_url": url}


def _apply_header_formatting(svc, spreadsheet_id: str) -> None:
    navy = {"red": 26 / 255, "green": 26 / 255, "blue": 46 / 255}
    gold = {"red": 200 / 255, "green": 169 / 255, "blue": 110 / 255}

    requests = []
    for sheet_id in [0, 1, 2]:
        requests.append({
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                "cell": {"userEnteredFormat": {
                    "backgroundColor": navy,
                    "textFormat": {"bold": True, "foregroundColor": gold},
                }},
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }
        })

    requests.append({
        "repeatCell": {
            "range": {"sheetId": 0, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": 2},
            "cell": {"userEnteredFormat": {
                "backgroundColor": navy,
                "textFormat": {"bold": True, "fontSize": 13, "foregroundColor": gold},
            }},
            "fields": "userEnteredFormat(backgroundColor,textFormat)",
        }
    })

    svc.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id, body={"requests": requests},
    ).execute()
