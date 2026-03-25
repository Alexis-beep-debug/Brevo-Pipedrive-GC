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
    net_amount: float = 0.0,
) -> dict:
    """Create a Lexoffice quote (Angebot) for a contact."""
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00.000+01:00")
    expiry = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00.000+01:00")

    items = line_items or [
        {
            "type": "custom",
            "name": "Unterhaltsreinigung (monatlich)",
            "quantity": 1,
            "unitName": "Monat",
            "unitPrice": {
                "currency": currency,
                "netAmount": net_amount,
                "taxRatePercentage": 19.0,
            },
        }
    ]

    payload = {
        "voucherDate": today,
        "expirationDate": expiry,
        "address": {"contactId": contact_id},
        "lineItems": items,
        "totalPrice": {"currency": currency},
        "taxConditions": {"taxType": "net"},
        "title": title,
        "introduction": introduction,
        "remark": "Dieses Angebot wurde automatisch erstellt.",
    }

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(
            f"{_BASE}/quotations",
            headers=_headers(),
            json=payload,
        )
        if r.status_code >= 400:
            print(f"Lexoffice quote error {r.status_code}: {r.text}", flush=True)
        r.raise_for_status()
        return r.json()


async def render_document(document_id: str, doc_type: str = "quotations") -> None:
    """Trigger PDF rendering for a Lexoffice document (required before download)."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(
            f"{_BASE}/{doc_type}/{document_id}/document",
            headers=_headers(),
        )
        r.raise_for_status()


async def download_pdf(document_id: str) -> bytes:
    """Download a rendered Lexoffice document as PDF bytes."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
        # First render the document
        render_r = await client.get(
            f"{_BASE}/quotations/{document_id}/document",
            headers=_headers(),
        )
        render_r.raise_for_status()
        render_data = render_r.json()
        document_file_id = render_data.get("documentFileId", "")

        if not document_file_id:
            raise ValueError("No documentFileId returned from Lexoffice")

        # Download the PDF
        pdf_r = await client.get(
            f"{_BASE}/files/{document_file_id}",
            headers=_headers(),
        )
        pdf_r.raise_for_status()
        return pdf_r.content
