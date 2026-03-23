"""
Google Drive + Slides client for proposal automation.

Features:
  - Create folder in Drive
  - Copy Slides template
  - Fill placeholders in presentation
  - Duplicate + fill problem slides dynamically
  - Export presentation as PDF
  - Upload PDF to Drive folder
"""
from __future__ import annotations

import io
import logging
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from config import (
    GOOGLE_SERVICE_ACCOUNT_INFO,
    GOOGLE_SLIDES_TEMPLATE_ID,
    GOOGLE_DRIVE_PARENT_FOLDER_ID,
)

logger = logging.getLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/presentations",
]


def _get_credentials() -> service_account.Credentials:
    return service_account.Credentials.from_service_account_info(
        GOOGLE_SERVICE_ACCOUNT_INFO, scopes=_SCOPES
    )


def _drive_service():
    return build("drive", "v3", credentials=_get_credentials(), cache_discovery=False)


def _slides_service():
    return build("slides", "v1", credentials=_get_credentials(), cache_discovery=False)


# ---------------------------------------------------------------------------
# Google Drive
# ---------------------------------------------------------------------------

def create_folder(name: str, parent_id: str | None = None) -> str:
    """Create a folder in Google Drive. Returns the folder ID."""
    parent = parent_id or GOOGLE_DRIVE_PARENT_FOLDER_ID
    metadata: dict[str, Any] = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent:
        metadata["parents"] = [parent]

    drive = _drive_service()
    folder = drive.files().create(body=metadata, fields="id").execute()
    folder_id = folder["id"]
    logger.info("Created Drive folder '%s' → %s", name, folder_id)
    return folder_id


def upload_pdf(file_bytes: bytes, filename: str, folder_id: str) -> str:
    """Upload a PDF file to a Google Drive folder. Returns the file ID."""
    drive = _drive_service()
    metadata: dict[str, Any] = {
        "name": filename,
        "parents": [folder_id],
    }
    media = MediaIoBaseUpload(
        io.BytesIO(file_bytes),
        mimetype="application/pdf",
        resumable=False,
    )
    uploaded = drive.files().create(
        body=metadata, media_body=media, fields="id"
    ).execute()
    file_id = uploaded["id"]
    logger.info("Uploaded PDF '%s' → %s", filename, file_id)
    return file_id


# ---------------------------------------------------------------------------
# Google Slides
# ---------------------------------------------------------------------------

def copy_template(new_title: str, dest_folder_id: str) -> str:
    """Copy the Slides template into dest_folder_id. Returns new presentation ID."""
    drive = _drive_service()
    copy = drive.files().copy(
        fileId=GOOGLE_SLIDES_TEMPLATE_ID,
        body={"name": new_title, "parents": [dest_folder_id]},
        fields="id",
    ).execute()
    pres_id = copy["id"]
    logger.info("Copied template → presentation %s", pres_id)
    return pres_id


def fill_presentation(presentation_id: str, replacements: dict[str, str]) -> None:
    """
    Replace all {{PLACEHOLDER}} tags in a presentation.

    replacements: {"{{FIRMA}}": "Acme GmbH", "{{DATUM}}": "2026-03-23", ...}
    """
    slides_svc = _slides_service()
    requests = [
        {
            "replaceAllText": {
                "containsText": {"text": tag, "matchCase": True},
                "replaceText": value,
            }
        }
        for tag, value in replacements.items()
    ]
    if requests:
        slides_svc.presentations().batchUpdate(
            presentationId=presentation_id, body={"requests": requests}
        ).execute()
        logger.info("Filled %d placeholders in %s", len(requests), presentation_id)


def duplicate_slide(presentation_id: str, slide_object_id: str) -> str:
    """Duplicate a slide within the presentation. Returns the new slide's object ID."""
    slides_svc = _slides_service()
    response = slides_svc.presentations().batchUpdate(
        presentationId=presentation_id,
        body={
            "requests": [
                {"duplicateObject": {"objectId": slide_object_id}}
            ]
        },
    ).execute()
    # The reply contains the new object ID mapping
    reply = response["replies"][0]["duplicateObject"]["objectId"]
    logger.info("Duplicated slide %s → %s", slide_object_id, reply)
    return reply


def fill_problem_slides(
    presentation_id: str,
    template_slide_id: str,
    problems: list[dict[str, str]],
) -> None:
    """
    Dynamically create one slide per problem by duplicating the template slide.

    Each problem dict: {"title": "...", "description": "...", "solution": "..."}
    The template slide should contain {{PROBLEM_TITLE}}, {{PROBLEM_DESC}}, {{PROBLEM_SOLUTION}}.
    """
    slides_svc = _slides_service()

    for i, problem in enumerate(problems):
        if i == 0:
            # Use the original template slide for the first problem
            slide_id = template_slide_id
        else:
            slide_id = duplicate_slide(presentation_id, template_slide_id)

        # Fill placeholders on this specific slide
        requests = [
            {
                "replaceAllText": {
                    "containsText": {"text": tag, "matchCase": True},
                    "replaceText": value,
                    "pageObjectIds": [slide_id],
                }
            }
            for tag, value in {
                "{{PROBLEM_TITLE}}": problem.get("title", ""),
                "{{PROBLEM_DESC}}": problem.get("description", ""),
                "{{PROBLEM_SOLUTION}}": problem.get("solution", ""),
            }.items()
        ]
        if requests:
            slides_svc.presentations().batchUpdate(
                presentationId=presentation_id, body={"requests": requests}
            ).execute()

    logger.info("Created %d problem slides in %s", len(problems), presentation_id)


def export_as_pdf(presentation_id: str) -> bytes:
    """Export a Google Slides presentation as PDF. Returns raw PDF bytes."""
    drive = _drive_service()
    pdf_bytes = drive.files().export(
        fileId=presentation_id, mimeType="application/pdf"
    ).execute()
    logger.info("Exported presentation %s as PDF (%d bytes)", presentation_id, len(pdf_bytes))
    return pdf_bytes


# ---------------------------------------------------------------------------
# High-level: full proposal generation
# ---------------------------------------------------------------------------

def generate_proposal_pdf(
    *,
    company_name: str,
    contact_name: str,
    replacements: dict[str, str],
    problems: list[dict[str, str]] | None = None,
    problem_slide_id: str = "",
    folder_name: str | None = None,
) -> dict[str, str]:
    """
    End-to-end proposal generation:
    1. Create Drive folder
    2. Copy Slides template
    3. Fill placeholders
    4. Create dynamic problem slides
    5. Export as PDF
    6. Upload PDF to folder

    Returns {"folder_id": ..., "presentation_id": ..., "pdf_file_id": ...}
    """
    folder_title = folder_name or f"Angebot – {company_name}"
    folder_id = create_folder(folder_title)
    pres_id = copy_template(f"Angebot {company_name}", folder_id)

    fill_presentation(pres_id, replacements)

    if problems and problem_slide_id:
        fill_problem_slides(pres_id, problem_slide_id, problems)

    pdf_bytes = export_as_pdf(pres_id)
    pdf_name = f"Angebot_{company_name.replace(' ', '_')}.pdf"
    pdf_file_id = upload_pdf(pdf_bytes, pdf_name, folder_id)

    return {
        "folder_id": folder_id,
        "presentation_id": pres_id,
        "pdf_file_id": pdf_file_id,
    }
