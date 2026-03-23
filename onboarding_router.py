"""
Onboarding Router – alle Endpunkte für das Kunden-Onboarding.

Endpoints:
  POST /webhook/deal-won              ← Close CRM Webhook (Opportunity → Won)
  GET  /onboarding/session/{token}    ← Frontend lädt vorausgefüllte Daten
  POST /onboarding/drive              ← Google Drive Ordner anlegen
  POST /onboarding/email              ← Willkommensmail senden
  POST /onboarding/invoice            ← Rechnung generieren (PDF-Download)
  POST /onboarding/dashboard          ← Google Sheet Dashboard anlegen
  POST /onboarding/all                ← Alle Aktionen auf einmal

Close CRM Webhook-Setup:
  URL:    https://<deine-railway-url>/webhook/deal-won
  Event:  opportunity.status_changed
  Secret: CLOSE_WEBHOOK_SECRET (wird als X-Close-Signature Header gesendet)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

import close_client as crm
from config import CLOSE_WEBHOOK_SECRET, ONBOARDING_UI_URL, YOUR_EMAIL
from session_store import create_session, get_session, mark_action_done, update_session_data

router = APIRouter()


class OnboardingRequest(BaseModel):
    token: str


class InvoiceRequest(OnboardingRequest):
    line_items: list[dict] | None = None
    invoice_number: str | None = None
    send_email: bool = False


def _require_session(token: str) -> dict:
    session = get_session(token)
    if not session:
        raise HTTPException(status_code=404, detail="Session nicht gefunden oder abgelaufen")
    return session


def _default_invoice_number(opportunity_id: str) -> str:
    short_id = opportunity_id.replace("oppo_", "")[:8].upper()
    return f"RE-{datetime.now().strftime('%Y%m%d')}-{short_id}"


@router.post("/webhook/deal-won")
async def deal_won_webhook(request: Request) -> dict:
    body = await request.body()

    if CLOSE_WEBHOOK_SECRET:
        sig = request.headers.get("X-Close-Signature", "")
        if not crm.verify_webhook_signature(body, sig):
            raise HTTPException(status_code=401, detail="Ungültige Webhook-Signatur")

    payload: dict[str, Any] = await request.json() if not body else __import__("json").loads(body)
    event = payload.get("event", "")
    data = payload.get("data") or payload

    opportunity: dict = {}
    if "opportunity" in data:
        opportunity = data["opportunity"]
    elif event == "opportunity.status_changed":
        opportunity = data
    else:
        return {"status": "skipped", "reason": f"unbekanntes Event: {event}"}

    if opportunity.get("status_type") != "won":
        return {"status": "skipped", "reason": "Opportunity nicht gewonnen"}

    opportunity_id: str = opportunity.get("id", "")
    lead_id: str = opportunity.get("lead_id", "")

    if not lead_id:
        raise HTTPException(status_code=400, detail="lead_id fehlt im Payload")

    lead = await crm.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} nicht gefunden")

    contact = crm.extract_primary_contact(lead)
    address = crm.extract_address(lead)

    client_data = {
        **contact,
        "company": lead.get("display_name", ""),
        "address": address,
        "deal_title": opportunity.get("note") or opportunity.get("status_label", ""),
        "deal_value": float(opportunity.get("value") or 0) / 100,
        "currency": opportunity.get("value_currency", "EUR"),
    }

    token = create_session(
        deal_id=opportunity_id,
        person_id=lead_id,
        client_data=client_data,
    )

    onboarding_url = f"{ONBOARDING_UI_URL}?token={token}"

    await crm.create_task(
        lead_id=lead_id,
        text=(
            f"Onboarding starten: {client_data['name']}\n\n"
            f"Onboarding-Link (gültig 7 Tage):\n{onboarding_url}"
        ),
    )

    return {
        "status": "ok",
        "opportunity_id": opportunity_id,
        "lead_id": lead_id,
        "client": client_data["name"],
        "onboarding_url": onboarding_url,
    }


@router.get("/onboarding/session/{token}")
async def get_onboarding_session(token: str) -> dict:
    session = _require_session(token)
    return {
        "token": token,
        "client": session["client"],
        "completed_actions": session["completed_actions"],
        "created_at": session["created_at"],
        "expires_at": session["expires_at"],
    }


@router.post("/onboarding/drive")
async def create_drive_folders(req: OnboardingRequest) -> dict:
    session = _require_session(req.token)
    client = session["client"]
    from services.drive_service import create_client_folder
    folder_name = client["company"] or client["name"]
    result = create_client_folder(folder_name)
    update_session_data(req.token, "drive", result)
    mark_action_done(req.token, "drive")
    return {"status": "ok", "drive": result}


@router.post("/onboarding/email")
async def send_welcome_email(req: OnboardingRequest) -> dict:
    session = _require_session(req.token)
    client = session["client"]
    if not client.get("email"):
        raise HTTPException(status_code=400, detail="Keine E-Mail-Adresse für diesen Kunden")
    from services.gmail_service import send_welcome_email as _send
    drive_info = session.get("drive")
    folder_url = drive_info["main_folder_url"] if drive_info else None
    message_id = _send(
        client_email=client["email"],
        client_name=client["name"],
        client_company=client["company"],
        drive_folder_url=folder_url,
    )
    mark_action_done(req.token, "email")
    return {"status": "ok", "gmail_message_id": message_id}


@router.post("/onboarding/invoice")
async def generate_invoice(req: InvoiceRequest) -> Response:
    session = _require_session(req.token)
    client = session["client"]
    from services.invoice_service import generate_invoice as _gen
    invoice_number = req.invoice_number or _default_invoice_number(session["deal_id"])
    line_items = req.line_items or [
        {"description": client["deal_title"] or "Beratungsleistungen", "amount": client["deal_value"]}
    ]
    pdf_bytes = _gen(
        client_name=client["name"],
        client_company=client["company"],
        client_address=client["address"],
        client_email=client["email"],
        invoice_number=invoice_number,
        line_items=line_items,
        currency=client["currency"],
    )
    if req.send_email and client.get("email"):
        from services.gmail_service import send_invoice_email
        send_invoice_email(client["email"], client["name"], invoice_number, pdf_bytes)
    mark_action_done(req.token, "invoice")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{invoice_number}.pdf"'},
    )


@router.post("/onboarding/dashboard")
async def create_dashboard(req: OnboardingRequest) -> dict:
    session = _require_session(req.token)
    client = session["client"]
    from services.sheets_service import create_client_dashboard
    drive_info = session.get("drive")
    folder_id = drive_info["main_folder_id"] if drive_info else None
    result = create_client_dashboard(
        client_name=client["name"],
        client_email=client["email"],
        client_company=client["company"],
        deal_title=client["deal_title"],
        deal_value=client["deal_value"],
        currency=client["currency"],
        drive_folder_id=folder_id,
        share_with_email=YOUR_EMAIL or None,
    )
    mark_action_done(req.token, "dashboard")
    return {"status": "ok", "dashboard": result}


@router.post("/onboarding/all")
async def run_all_actions(req: OnboardingRequest) -> dict:
    session = _require_session(req.token)
    client = session["client"]
    results: dict[str, Any] = {}

    try:
        from services.drive_service import create_client_folder
        drive_result = create_client_folder(client["company"] or client["name"])
        update_session_data(req.token, "drive", drive_result)
        mark_action_done(req.token, "drive")
        results["drive"] = {"status": "ok", **drive_result}
    except Exception as exc:
        results["drive"] = {"status": "error", "detail": str(exc)}

    try:
        from services.gmail_service import send_welcome_email as _send_welcome
        session = _require_session(req.token)
        drive_info = session.get("drive")
        msg_id = _send_welcome(
            client_email=client["email"],
            client_name=client["name"],
            client_company=client["company"],
            drive_folder_url=drive_info["main_folder_url"] if drive_info else None,
        )
        mark_action_done(req.token, "email")
        results["email"] = {"status": "ok", "gmail_message_id": msg_id}
    except Exception as exc:
        results["email"] = {"status": "error", "detail": str(exc)}

    try:
        from services.invoice_service import generate_invoice as _gen
        from services.gmail_service import send_invoice_email
        invoice_number = _default_invoice_number(session["deal_id"])
        pdf_bytes = _gen(
            client_name=client["name"],
            client_company=client["company"],
            client_address=client["address"],
            client_email=client["email"],
            invoice_number=invoice_number,
            line_items=[{"description": client["deal_title"] or "Beratungsleistungen", "amount": client["deal_value"]}],
            currency=client["currency"],
        )
        if client.get("email"):
            send_invoice_email(client["email"], client["name"], invoice_number, pdf_bytes)
        mark_action_done(req.token, "invoice")
        results["invoice"] = {"status": "ok", "invoice_number": invoice_number, "sent_by_email": bool(client.get("email"))}
    except Exception as exc:
        results["invoice"] = {"status": "error", "detail": str(exc)}

    try:
        from services.sheets_service import create_client_dashboard
        session = _require_session(req.token)
        drive_info = session.get("drive")
        dashboard_result = create_client_dashboard(
            client_name=client["name"],
            client_email=client["email"],
            client_company=client["company"],
            deal_title=client["deal_title"],
            deal_value=client["deal_value"],
            currency=client["currency"],
            drive_folder_id=drive_info["main_folder_id"] if drive_info else None,
            share_with_email=YOUR_EMAIL or None,
        )
        mark_action_done(req.token, "dashboard")
        results["dashboard"] = {"status": "ok", **dashboard_result}
    except Exception as exc:
        results["dashboard"] = {"status": "error", "detail": str(exc)}

    overall = "ok" if all(r["status"] == "ok" for r in results.values()) else "partial"
    return {"status": overall, "results": results}
