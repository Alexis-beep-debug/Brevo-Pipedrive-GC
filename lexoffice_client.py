"""Async wrapper for the Lexoffice API – contacts & invoices."""
from __future__ import annotations

import httpx
from config import LEXOFFICE_API_KEY

_BASE = "https://api.lexoffice.io/v1"
_TIMEOUT = httpx.Timeout(30.0)


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {LEXOFFICE_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


# ---------------------------------------------------------------------------
# Kontakte
# ---------------------------------------------------------------------------

async def find_contact_by_email(email: str) -> dict | None:
    """Search for an existing Lexoffice contact by email."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(
            f"{_BASE}/contacts",
            headers=_headers(),
            params={"email": email},
        )
        r.raise_for_status()
        data = r.json()
        contacts = data.get("content") or []
        return contacts[0] if contacts else None


async def create_contact(
    *,
    company_name: str,
    first_name: str = "",
    last_name: str = "",
    email: str = "",
    phone: str = "",
    street: str = "",
    zip_code: str = "",
    city: str = "",
    country_code: str = "DE",
) -> dict:
    """
    Create a Lexoffice contact (company) WITH billing address.

    FIX for 406 "0 billing addresses found":
    Lexoffice requires at least one billing address when creating invoices.
    We always send street, zip, and city to ensure this.
    """
    payload: dict = {
        "version": 0,
        "roles": {
            "customer": {},
        },
        "company": {
            "name": company_name,
        },
        "addresses": {
            "billing": [
                {
                    "street": street or "–",
                    "zip": zip_code or "00000",
                    "city": city or "–",
                    "countryCode": country_code,
                }
            ],
        },
    }

    # Optional: Ansprechpartner
    if first_name or last_name:
        payload["company"]["contactPersons"] = [
            {
                "firstName": first_name,
                "lastName": last_name,
                "emailAddress": email,
                "phoneNumber": phone,
            }
        ]

    # Optional: Email-Adressen auf Company-Ebene
    if email:
        payload["emailAddresses"] = {"business": [email]}

    if phone:
        payload["phoneNumbers"] = {"business": [phone]}

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(
            f"{_BASE}/contacts",
            headers=_headers(),
            json=payload,
        )
        r.raise_for_status()
        return r.json()


async def get_or_create_contact(
    *,
    company_name: str,
    email: str = "",
    first_name: str = "",
    last_name: str = "",
    phone: str = "",
    street: str = "",
    zip_code: str = "",
    city: str = "",
    country_code: str = "DE",
) -> dict:
    """Find contact by email or create a new one (with billing address)."""
    if email:
        existing = await find_contact_by_email(email)
        if existing:
            return existing

    return await create_contact(
        company_name=company_name,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        street=street,
        zip_code=zip_code,
        city=city,
        country_code=country_code,
    )


# ---------------------------------------------------------------------------
# Angebote (Quotes)
# ---------------------------------------------------------------------------

async def create_quote(
    *,
    contact_id: str,
    title: str = "Angebot",
    introduction: str = "",
    line_items: list[dict] | None = None,
    currency: str = "EUR",
) -> dict:
    """Create a Lexoffice quote (Angebot) for a contact."""
    items = line_items or [
        {
            "type": "custom",
            "name": title,
            "quantity": 1,
            "unitName": "Stück",
            "unitPrice": {"currency": currency, "netAmount": 0.0, "taxRatePercentage": 19.0},
        }
    ]

    payload = {
        "voucherDate": None,  # Lexoffice sets to today if None
        "address": {"contactId": contact_id},
        "lineItems": items,
        "totalPrice": {"currency": currency},
        "taxConditions": {"taxType": "net"},
        "title": title,
        "introduction": introduction,
    }
    # Remove None values
    payload = {k: v for k, v in payload.items() if v is not None}

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(
            f"{_BASE}/quotations",
            headers=_headers(),
            json=payload,
        )
        r.raise_for_status()
        return r.json()
