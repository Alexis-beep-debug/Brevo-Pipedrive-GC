"""
Gmail Service – Willkommensmail und Rechnungsversand via OAuth2.
"""
from __future__ import annotations

import base64
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from config import (
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REFRESH_TOKEN,
    YOUR_EMAIL,
    YOUR_NAME,
)

_SCOPES = ["https://mail.google.com/"]


def _gmail_service():
    creds = Credentials(
        token=None,
        refresh_token=GOOGLE_REFRESH_TOKEN,
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=_SCOPES,
    )
    creds.refresh(Request())
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _send_raw(msg: MIMEMultipart) -> str:
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    result = _gmail_service().users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()
    return result["id"]


def send_welcome_email(
    client_email: str,
    client_name: str,
    client_company: str,
    drive_folder_url: str | None = None,
) -> str:
    subject = f"Willkommen bei {YOUR_NAME} – Ihr Onboarding startet jetzt"

    folder_section = ""
    if drive_folder_url:
        folder_section = f"""
    <p style="margin-top:16px;">
      Ihre persönliche Projektablage finden Sie hier:<br>
      <a href="{drive_folder_url}" style="color:#c8a96e;">{drive_folder_url}</a>
    </p>"""

    html_body = f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <style>
    body {{ margin:0; padding:0; background:#f5f5f5; font-family:'DM Sans',Arial,sans-serif; color:#1a1a2e; }}
    .wrap {{ max-width:600px; margin:32px auto; background:#fff; border-radius:4px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,.08); }}
    .header {{ background:#1a1a2e; padding:32px 40px; text-align:center; }}
    .header h1 {{ margin:0; font-family:Georgia,'Cormorant Garamond',serif; font-size:26px; color:#c8a96e; letter-spacing:.05em; }}
    .header p {{ margin:6px 0 0; font-size:12px; color:#8888aa; letter-spacing:.15em; text-transform:uppercase; }}
    .content {{ padding:36px 40px; font-size:15px; line-height:1.7; }}
    .content p {{ margin:0 0 14px; }}
    .footer {{ padding:20px 40px; background:#f9f9f9; border-top:1px solid #eee; font-size:11px; color:#aaa; text-align:center; }}
    a {{ color:#c8a96e; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="header">
      <h1>Bethke &amp; Partner</h1>
      <p>Unternehmensberatung</p>
    </div>
    <div class="content">
      <p>Sehr geehrte/r {client_name},</p>
      <p>herzlich willkommen bei <strong>{YOUR_NAME}</strong>. Wir freuen uns sehr, Sie{' und ' + client_company if client_company else ''} als neuen Mandanten begrüßen zu dürfen.</p>
      <p>Ihr Onboarding ist nun gestartet. In den nächsten Tagen erhalten Sie alle notwendigen Unterlagen, Zugänge und erste Ergebnisse unserer Zusammenarbeit.</p>
      {folder_section}
      <p>Bei Fragen und Anmerkungen stehe ich Ihnen jederzeit persönlich zur Verfügung.</p>
      <p>Mit freundlichen Grüßen,<br><strong>{YOUR_NAME}</strong></p>
    </div>
    <div class="footer">
      {YOUR_NAME} · Bethke &amp; Partner · <a href="mailto:{YOUR_EMAIL}">{YOUR_EMAIL}</a>
    </div>
  </div>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{YOUR_NAME} <{YOUR_EMAIL}>"
    msg["To"] = client_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    return _send_raw(msg)


def send_invoice_email(
    client_email: str,
    client_name: str,
    invoice_number: str,
    pdf_bytes: bytes,
) -> str:
    msg = MIMEMultipart()
    msg["Subject"] = f"Ihre Rechnung {invoice_number} – {YOUR_NAME}"
    msg["From"] = f"{YOUR_NAME} <{YOUR_EMAIL}>"
    msg["To"] = client_email

    body = (
        f"Sehr geehrte/r {client_name},\n\n"
        f"anbei erhalten Sie Ihre Rechnung {invoice_number}.\n\n"
        f"Bitte überweisen Sie den Betrag fristgerecht unter Angabe der Rechnungsnummer.\n\n"
        f"Bei Rückfragen stehe ich Ihnen gerne zur Verfügung.\n\n"
        f"Mit freundlichen Grüßen,\n{YOUR_NAME}"
    )
    msg.attach(MIMEText(body, "plain", "utf-8"))

    attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
    attachment.add_header(
        "Content-Disposition", "attachment", filename=f"{invoice_number}.pdf"
    )
    msg.attach(attachment)
    return _send_raw(msg)
