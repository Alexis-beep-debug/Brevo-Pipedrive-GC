"""
Async wrapper für die Close CRM REST API v1.

Authentifizierung: HTTP Basic Auth (API Key als Username, Passwort leer).
Docs: https://developer.close.com/
"""
from __future__ import annotations

import hashlib
import hmac

import httpx
from config import CLOSE_API_KEY, CLOSE_WEBHOOK_SECRET

_BASE = "https://api.close.com/api/v1"
_TIMEOUT = httpx.Timeout(30.0)


def _auth() -> httpx.BasicAuth:
    return httpx.BasicAuth(username=CLOSE_API_KEY, password="")


def verify_webhook_signature(body: bytes, signature_header: str) -> bool:
    if not CLOSE_WEBHOOK_SECRET:
        return True
    expected = hmac.new(
        CLOSE_WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


async def get_lead(lead_id: str) -> dict | None:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(f"{_BASE}/lead/{lead_id}/", auth=_auth())
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()


async def get_contact(contact_id: str) -> dict | None:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(f"{_BASE}/contact/{contact_id}/", auth=_auth())
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()


async def get_opportunity(opportunity_id: str) -> dict | None:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(f"{_BASE}/opportunity/{opportunity_id}/", auth=_auth())
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()


async def create_task(lead_id: str, text: str, due_date: str | None = None) -> dict:
    payload: dict = {"lead_id": lead_id, "text": text, "type": "lead", "is_complete": False}
    if due_date:
        payload["due_date"] = due_date
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(f"{_BASE}/task/", auth=_auth(), json=payload)
        r.raise_for_status()
        return r.json()


async def create_note(lead_id: str, note: str) -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(
            f"{_BASE}/activity/note/",
            auth=_auth(),
            json={"lead_id": lead_id, "note": note},
        )
        r.raise_for_status()
        return r.json()


def extract_primary_contact(lead: dict) -> dict:
    contacts: list[dict] = lead.get("contacts") or []
    if not contacts:
        return {"name": "", "first_name": "", "last_name": "", "email": "", "phone": ""}
    c = contacts[0]
    name: str = c.get("name") or ""
    parts = name.split(" ", 1)
    first = parts[0] if parts else ""
    last = parts[1] if len(parts) > 1 else ""
    email = next(
        (e["email"] for e in (c.get("emails") or []) if e.get("email")), ""
    )
    phone = next(
        (p["phone"] for p in (c.get("phones") or []) if p.get("phone")), ""
    )
    return {"name": name, "first_name": first, "last_name": last, "email": email, "phone": phone}


def extract_address(lead: dict) -> str:
    addresses: list[dict] = lead.get("addresses") or []
    if not addresses:
        return ""
    a = addresses[0]
    parts = [a.get("address_1", ""), a.get("address_2", ""), a.get("city", ""),
             a.get("state", ""), a.get("zipcode", ""), a.get("country", "")]
    return ", ".join(p for p in parts if p)
