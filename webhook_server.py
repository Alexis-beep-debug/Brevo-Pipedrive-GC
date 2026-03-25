#!/usr/bin/env python3
"""
Schritt 4 – FastAPI Webhook-Server.

Empfängt Brevo-Email-Events und schreibt Notizen / Aktivitäten nach Pipedrive.

Starten lokal:  uvicorn webhook_server:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import logging

from fastapi import FastAPI, Request, HTTPException
import pipedrive_client as pd
import lexoffice_client as lx
import proposal_generator
import google_drive_client as gdrive
from config import PIPEDRIVE_OWNER_USER_ID

logger = logging.getLogger(__name__)

app = FastAPI(title="Pipedrive↔Brevo Sync Webhook Server")

BOT_CLICK_THRESHOLD_SECONDS = 4  # Klicks kürzer als dies = Bot-Klick → ignorieren


def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


async def _resolve_person(email: str) -> dict | None:
    """Look up Pipedrive person by email. Returns person dict or None."""
    return await pd.search_person_by_email(email)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "timestamp": _now_str()}


# ---------------------------------------------------------------------------
# 4a: Email geöffnet
# ---------------------------------------------------------------------------

@app.post("/webhook/email-opened")
async def email_opened(request: Request) -> dict:
    """
    Brevo sendet bei jedem 'opened'-Event einen POST.
    Payload-Felder (Brevo Marketing Email Events):
      - email: Empfänger-Email
      - subject: Betreff der Kampagne
      - campaign_name / message_id (optional)
    """
    payload: dict[str, Any] = await request.json()

    email: str = payload.get("email", "")
    subject: str = payload.get("subject", "unbekannte Kampagne")

    if not email:
        raise HTTPException(status_code=400, detail="'email' fehlt im Payload")

    person = await _resolve_person(email)
    if not person:
        # Kontakt existiert nicht in Pipedrive – still ignorieren
        return {"status": "skipped", "reason": "person not found", "email": email}

    note_content = f"[{_now_str()}] Email geöffnet: {subject}"
    await pd.add_note(person_id=person["id"], content=note_content)

    return {"status": "ok", "person_id": person["id"], "note": note_content}


# ---------------------------------------------------------------------------
# 4b: Link geklickt
# ---------------------------------------------------------------------------

@app.post("/webhook/link-clicked")
async def link_clicked(request: Request) -> dict:
    """
    Brevo sendet bei jedem 'clicked'-Event einen POST.
    Payload-Felder:
      - email: Empfänger-Email
      - subject: Betreff
      - link: geklickte URL
      - time_since_delivery: Sekunden seit Zustellung (für Bot-Filter)
    """
    payload: dict[str, Any] = await request.json()

    email: str = payload.get("email", "")
    subject: str = payload.get("subject", "unbekannter Betreff")
    link: str = payload.get("link", "")
    time_since_delivery = payload.get("time_since_delivery")

    if not email:
        raise HTTPException(status_code=400, detail="'email' fehlt im Payload")

    # Bot-Klick-Filter
    if time_since_delivery is not None:
        try:
            if float(time_since_delivery) < BOT_CLICK_THRESHOLD_SECONDS:
                return {"status": "skipped", "reason": "bot_click_filtered"}
        except (TypeError, ValueError):
            pass

    person = await _resolve_person(email)
    if not person:
        return {"status": "skipped", "reason": "person not found", "email": email}

    person_name = f"{person.get('first_name', '')} {person.get('last_name', '')}".strip() or email
    ts = _now_str()

    note_content = f"[{ts}] Link geklickt: {link} in Email \"{subject}\""
    activity_subject = f"Heißer Lead: {person_name} hat Link geklickt"
    activity_note = f"Geklickter Link: {link}\nEmail-Betreff: {subject}"

    await pd.add_note(person_id=person["id"], content=note_content)
    await pd.add_activity(person_id=person["id"], subject=activity_subject, note=activity_note, user_id=20546477)

    return {
        "status": "ok",
        "person_id": person["id"],
        "note": note_content,
        "activity": activity_subject,
    }


# ---------------------------------------------------------------------------
# 5: Angebotsautomatisierung – kompletter Flow
# ---------------------------------------------------------------------------

@app.post("/webhook/generate-proposal")
async def generate_proposal(request: Request) -> dict:
    """
    Empfängt Superforms-Webhook-Daten und führt die Angebotsautomatisierung aus:

    1. PDF aus Superforms-Daten generieren (HTML/Jinja2 + WeasyPrint)
    2. Pipedrive Person + Deal anlegen
    3. Lexoffice Kontakt anlegen (MIT Billing-Adresse)
    4. Pipedrive Notiz + Aufgabe erstellen

    Payload: Direkt das Superforms-Webhook-JSON mit Feldnamen wie
    Firmenname, Anschrift, first_name, last_name, Email, etc.
    """
    # Accept both JSON and form-urlencoded (Superforms may send either)
    import json
    content_type = request.headers.get("content-type", "")
    print(f"=== CONTENT-TYPE: {content_type} ===", flush=True)

    if "application/json" in content_type:
        payload: dict[str, Any] = await request.json()
    else:
        form_data = await request.form()
        payload = dict(form_data)

    print("=== RAW WEBHOOK PAYLOAD ===", flush=True)
    print(json.dumps(payload, indent=2, default=str, ensure_ascii=False), flush=True)
    print("=== END PAYLOAD ===", flush=True)

    # Superforms wraps fields in {"files": [], "data": {...fields...}}
    if "data" in payload and isinstance(payload["data"], dict):
        payload = payload["data"]

    # Superforms sends nested objects: {"field": {"value": "...", "option_label": "...", ...}}
    # For checkboxes/radios, use option_label (human-readable) instead of value (internal)
    # Flatten to simple key-value: {"field": "value or option_label"}
    flat_payload: dict[str, Any] = {}
    for key, val in payload.items():
        if isinstance(val, dict) and "value" in val:
            # Use option_label for checkboxes/radios (has the readable text)
            if "option_label" in val and val["option_label"]:
                flat_payload[key] = val["option_label"]
            else:
                flat_payload[key] = val["value"]
        else:
            flat_payload[key] = val
    payload = flat_payload
    print("=== FLATTENED PAYLOAD ===", flush=True)
    print(json.dumps(payload, indent=2, default=str, ensure_ascii=False), flush=True)

    # Map Superforms fields to readable names
    template_data = proposal_generator.map_superforms_to_template(payload)
    company = template_data["firma_name"] or "Unbekannt"
    first_name = payload.get("first_name", "")
    last_name = payload.get("last_name", "")
    email = template_data["email"]
    phone = template_data["telefon"]
    street = template_data["rech_strasse"]
    zip_code = template_data["rech_plz"]
    city = template_data["rech_stadt"]
    deal_title = f"Unterhaltsreinigung – {company}"

    results: dict[str, Any] = {}

    # --- 1. PDF generieren ---
    try:
        pdf_path = proposal_generator.generate_and_save(payload)
        results["pdf_path"] = str(pdf_path)
        logger.info("PDF generated: %s", pdf_path)
    except Exception as exc:
        logger.error("PDF generation failed: %s", exc)
        results["pdf_error"] = str(exc)

    # --- 2. Pipedrive: Person anlegen / finden ---
    person = None
    if email:
        person = await pd.search_person_by_email(email)
    if not person:
        person = await _create_pipedrive_person(first_name, last_name, email, phone, company)
    person_id = person["id"]
    results["person_id"] = person_id

    # --- 3. Pipedrive: Deal anlegen / finden ---
    existing_deals = await pd.get_person_deals(person_id)
    deal = None
    for d in existing_deals:
        if d.get("title", "").startswith("Unterhaltsreinigung"):
            deal = d
            break
    if not deal:
        deal = await _create_pipedrive_deal(person_id, deal_title)
    deal_id = deal["id"]
    results["deal_id"] = deal_id

    # --- 4. Lexoffice: Kontakt + Angebot anlegen ---
    lexoffice_pdf_bytes = None
    try:
        lx_contact = await lx.get_or_create_contact(
            company_name=company,
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            street=street,
            zip_code=zip_code,
            city=city,
        )
        contact_id = lx_contact.get("id") or ""
        if not contact_id and lx_contact.get("resourceUri"):
            contact_id = lx_contact["resourceUri"].rstrip("/").split("/")[-1]
        results["lexoffice_contact_id"] = contact_id
        print(f"Lexoffice contact: {contact_id}", flush=True)

        # Lexoffice Angebot erstellen (mit berechnetem Preis)
        if contact_id:
            # Gesamtpreis aus Template-Daten extrahieren
            preis_str = template_data.get("gesamtpreis_netto", "0")
            try:
                net_total = float(preis_str.replace(".", "").replace(",", ".").replace("–", "0"))
            except (ValueError, AttributeError):
                net_total = 0.0

            quote = await lx.create_quote(
                contact_id=contact_id,
                title="Unterhaltsreinigung",
                introduction=f"Angebot für die Unterhaltsreinigung am Standort {template_data['objekt_adresse']}.",
                net_amount=net_total,
            )
            quote_id = quote.get("id", "")
            results["lexoffice_quote_id"] = quote_id
            print(f"Lexoffice quote created: {quote_id}", flush=True)

            # PDF herunterladen
            if quote_id:
                import asyncio
                await asyncio.sleep(2)  # Lexoffice braucht kurz zum Rendern
                try:
                    lexoffice_pdf_bytes = await lx.download_pdf(quote_id)
                    print(f"Lexoffice PDF downloaded: {len(lexoffice_pdf_bytes)} bytes", flush=True)
                except Exception as pdf_exc:
                    print(f"Lexoffice PDF download failed: {pdf_exc}", flush=True)

    except Exception as exc:
        print(f"Lexoffice failed: {exc}", flush=True)
        results["lexoffice_error"] = str(exc)

    # --- 5. Google Drive: Ordner erstellen + PDFs hochladen ---
    drive_link = ""
    try:
        folder_name = f"Angebot – {company}"
        folder_id = gdrive.create_folder(folder_name)
        drive_link = gdrive.get_folder_link(folder_id)
        results["drive_folder"] = drive_link
        print(f"Drive folder created: {drive_link}", flush=True)

        # Upload Angebots-PDF (unsere generierte Version)
        if results.get("pdf_path"):
            from pathlib import Path
            pdf_file = Path(results["pdf_path"])
            if pdf_file.exists():
                pdf_bytes = pdf_file.read_bytes()
                gdrive.upload_pdf(pdf_bytes, pdf_file.name, folder_id)
                print(f"Uploaded Angebots-PDF to Drive", flush=True)

        # Upload Lexoffice-PDF
        if lexoffice_pdf_bytes:
            lx_filename = f"Lexoffice_Angebot_{company.replace(' ', '_')}.pdf"
            gdrive.upload_pdf(lexoffice_pdf_bytes, lx_filename, folder_id)
            print(f"Uploaded Lexoffice-PDF to Drive", flush=True)

    except Exception as exc:
        print(f"Google Drive failed: {exc}", flush=True)
        results["drive_error"] = str(exc)

    # --- 6. Pipedrive: Notiz + Aufgabe (mit Drive-Link) ---
    ts = _now_str()
    note_text = (
        f"[{ts}] Angebot automatisch erstellt für {company}\n"
        f"Deal: {deal_title}\n"
    )
    if drive_link:
        note_text += f"📁 Google Drive: {drive_link}\n"
    if results.get("pdf_path"):
        note_text += f"PDF: {results['pdf_path']}\n"

    await pd.add_note(person_id=person_id, content=note_text)

    activity_note = f"Automatisch erstelltes Angebot für {deal_title}. Bitte prüfen und an den Kunden senden."
    if drive_link:
        activity_note += f"\n\n📁 Google Drive Ordner: {drive_link}"

    await _add_activity_with_deal(
        person_id=person_id,
        deal_id=deal_id,
        subject=f"Angebot prüfen & versenden: {company}",
        note=activity_note,
        user_id=PIPEDRIVE_OWNER_USER_ID,
    )

    return {"status": "ok", "results": results}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_pipedrive_person(
    first_name: str, last_name: str, email: str, phone: str, org_name: str
) -> dict:
    """Create a new person in Pipedrive."""
    from config import PIPEDRIVE_API_KEY, PIPEDRIVE_BASE
    import httpx
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        payload: dict[str, Any] = {
            "name": f"{first_name} {last_name}".strip() or org_name,
        }
        if email:
            payload["email"] = [{"value": email, "primary": True}]
        if phone:
            payload["phone"] = [{"value": phone, "primary": True}]
        r = await client.post(
            f"{PIPEDRIVE_BASE}/persons",
            params={"api_token": PIPEDRIVE_API_KEY},
            json=payload,
        )
        r.raise_for_status()
        return r.json()["data"]


async def _add_activity_with_deal(
    person_id: int, deal_id: int, subject: str, note: str = "", user_id: int | None = None
) -> dict:
    """Create a Pipedrive activity linked to both person AND deal."""
    from config import PIPEDRIVE_API_KEY, PIPEDRIVE_BASE
    import httpx
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        payload: dict[str, Any] = {
            "subject": subject,
            "type": "task",
            "person_id": person_id,
            "deal_id": deal_id,
            "done": 0,
            "note": note,
        }
        if user_id:
            payload["user_id"] = user_id
        r = await client.post(
            f"{PIPEDRIVE_BASE}/activities",
            params={"api_token": PIPEDRIVE_API_KEY},
            json=payload,
        )
        r.raise_for_status()
        return r.json()["data"]


async def _create_pipedrive_deal(person_id: int, title: str, value: float = 0) -> dict:
    """Create a new deal in Pipedrive linked to a person."""
    from config import PIPEDRIVE_API_KEY, PIPEDRIVE_BASE
    import httpx
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        payload: dict[str, Any] = {
            "title": title,
            "person_id": person_id,
            "value": value,
            "currency": "EUR",
        }
        r = await client.post(
            f"{PIPEDRIVE_BASE}/deals",
            params={"api_token": PIPEDRIVE_API_KEY},
            json=payload,
        )
        r.raise_for_status()
        return r.json()["data"]
