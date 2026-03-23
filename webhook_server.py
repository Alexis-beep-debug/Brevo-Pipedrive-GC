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
import google_client as gc
from config import GOOGLE_PROBLEM_SLIDE_ID, PIPEDRIVE_OWNER_USER_ID

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
    Empfängt Kundendaten und führt die gesamte Angebotsautomatisierung aus:

    1. Pipedrive Person + Deal anlegen
    2. Google Drive Ordner erstellen
    3. Google Slides Template kopieren + befüllen
    4. Dynamische Problem-Slides erzeugen
    5. PDF exportieren + hochladen
    6. Lexoffice Kontakt anlegen (MIT Billing-Adresse!)
    7. Pipedrive Notiz + Aufgabe erstellen

    Erwarteter Payload:
    {
        "company_name": "Firma GmbH",
        "contact_first_name": "Max",
        "contact_last_name": "Mustermann",
        "email": "max@firma.de",
        "phone": "+49 123 456",
        "street": "Musterstr. 1",
        "zip_code": "12345",
        "city": "Berlin",
        "deal_title": "Angebot Webseite",
        "deal_value": 5000,
        "problems": [
            {"title": "Problem 1", "description": "...", "solution": "..."},
            ...
        ],
        "extra_replacements": {"{{CUSTOM}}": "Wert"}
    }
    """
    payload: dict[str, Any] = await request.json()

    company = payload.get("company_name", "Unbekannt")
    first_name = payload.get("contact_first_name", "")
    last_name = payload.get("contact_last_name", "")
    email = payload.get("email", "")
    phone = payload.get("phone", "")
    street = payload.get("street", "")
    zip_code = payload.get("zip_code", "")
    city = payload.get("city", "")
    deal_title = payload.get("deal_title", f"Angebot – {company}")
    deal_value = payload.get("deal_value", 0)
    problems = payload.get("problems", [])
    extra_replacements = payload.get("extra_replacements", {})

    results: dict[str, Any] = {}

    # --- 1. Pipedrive: Person anlegen / finden ---
    person = None
    if email:
        person = await pd.search_person_by_email(email)
    if not person:
        person = (await _create_pipedrive_person(first_name, last_name, email, phone, company))
    person_id = person["id"]
    results["person_id"] = person_id

    # --- 2. Pipedrive: Deal anlegen ---
    deal = await _create_pipedrive_deal(person_id, deal_title, deal_value)
    results["deal_id"] = deal["id"]

    # --- 3+4+5. Google: Ordner → Slides → PDF ---
    contact_name = f"{first_name} {last_name}".strip()
    replacements = {
        "{{FIRMA}}": company,
        "{{ANSPRECHPARTNER}}": contact_name,
        "{{EMAIL}}": email,
        "{{TELEFON}}": phone,
        "{{STRASSE}}": street,
        "{{PLZ}}": zip_code,
        "{{STADT}}": city,
        "{{DATUM}}": _now_str().split(" ")[0],
        "{{DEAL_TITEL}}": deal_title,
        **extra_replacements,
    }
    try:
        google_result = gc.generate_proposal_pdf(
            company_name=company,
            contact_name=contact_name,
            replacements=replacements,
            problems=problems,
            problem_slide_id=GOOGLE_PROBLEM_SLIDE_ID,
        )
        results["google"] = google_result
        logger.info("Google proposal generated: %s", google_result)
    except Exception as exc:
        logger.error("Google proposal generation failed: %s", exc)
        results["google_error"] = str(exc)

    # --- 6. Lexoffice: Kontakt anlegen (mit Billing-Adresse!) ---
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
        results["lexoffice_contact_id"] = lx_contact.get("id") or lx_contact.get("resourceUri", "")
        logger.info("Lexoffice contact: %s", results["lexoffice_contact_id"])
    except Exception as exc:
        logger.error("Lexoffice contact creation failed: %s", exc)
        results["lexoffice_error"] = str(exc)

    # --- 7. Pipedrive: Notiz + Aufgabe ---
    ts = _now_str()
    note_text = (
        f"[{ts}] Angebot automatisch erstellt für {company}\n"
        f"Deal: {deal_title}\n"
    )
    if results.get("google"):
        note_text += f"Google Drive Ordner: {results['google']['folder_id']}\n"
        note_text += f"PDF: {results['google']['pdf_file_id']}\n"

    await pd.add_note(person_id=person_id, content=note_text)
    await pd.add_activity(
        person_id=person_id,
        subject=f"Angebot prüfen & versenden: {company}",
        note=f"Automatisch erstelltes Angebot für {deal_title}. Bitte prüfen und an den Kunden senden.",
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
