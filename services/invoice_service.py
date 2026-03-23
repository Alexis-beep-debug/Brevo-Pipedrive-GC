"""
Invoice Service – PDF-Rechnung mit fpdf2 generieren.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fpdf import FPDF

from config import YOUR_ADDRESS, YOUR_EMAIL, YOUR_NAME, YOUR_TAX_ID


class _InvoicePDF(FPDF):
    def header(self) -> None:
        self.set_font("Helvetica", "B", 18)
        self.set_text_color(26, 26, 46)
        self.cell(0, 10, "Bethke & Partner", new_x="LMARGIN", new_y="NEXT", align="R")
        self.set_font("Helvetica", "", 9)
        self.set_text_color(120, 120, 120)
        if YOUR_ADDRESS:
            self.cell(0, 5, YOUR_ADDRESS, new_x="LMARGIN", new_y="NEXT", align="R")
        if YOUR_EMAIL:
            self.cell(0, 5, YOUR_EMAIL, new_x="LMARGIN", new_y="NEXT", align="R")
        self.ln(6)

    def footer(self) -> None:
        self.set_y(-22)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(160, 160, 160)
        footer_parts = []
        if YOUR_TAX_ID:
            footer_parts.append(f"Steuernummer: {YOUR_TAX_ID}")
        footer_parts.append(f"Seite {self.page_no()}")
        self.cell(0, 5, "  ·  ".join(footer_parts), align="C")


def generate_invoice(
    client_name: str,
    client_company: str,
    client_address: str,
    client_email: str,
    invoice_number: str,
    line_items: list[dict],
    currency: str = "EUR",
) -> bytes:
    pdf = _InvoicePDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=28)

    today = datetime.now()
    today_str = today.strftime("%d.%m.%Y")
    due_str = (today + timedelta(days=14)).strftime("%d.%m.%Y")

    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(26, 26, 46)
    pdf.cell(0, 10, "RECHNUNG", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    y_block = pdf.get_y()
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(50, 50, 50)
    recipient_lines = [ln for ln in [client_name, client_company, client_address, client_email] if ln]
    for line in recipient_lines:
        pdf.cell(100, 5.5, line, new_x="LMARGIN", new_y="NEXT")

    right_x = 120.0
    pdf.set_xy(right_x, y_block)

    def _detail_row(label: str, value: str) -> None:
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(42, 6, label)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(30, 30, 30)
        pdf.cell(0, 6, value, new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(right_x)

    _detail_row("Rechnungsnummer:", invoice_number)
    _detail_row("Rechnungsdatum:", today_str)
    _detail_row("Fälligkeitsdatum:", due_str)
    pdf.ln(10)

    pdf.set_fill_color(26, 26, 46)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(130, 8, "  Leistungsbeschreibung", fill=True)
    pdf.cell(0, 8, f"Betrag ({currency})  ", fill=True, align="R", new_x="LMARGIN", new_y="NEXT")

    total = 0.0
    for i, item in enumerate(line_items):
        fill_color = (248, 248, 250) if i % 2 == 0 else (255, 255, 255)
        pdf.set_fill_color(*fill_color)
        pdf.set_text_color(40, 40, 40)
        pdf.set_font("Helvetica", "", 10)
        amount = float(item.get("amount", 0))
        total += amount
        amount_str = _fmt(amount)
        pdf.cell(130, 7.5, f"  {item.get('description', '')}", fill=True)
        pdf.cell(0, 7.5, f"{amount_str}  ", fill=True, align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(2)
    pdf.set_draw_color(200, 200, 210)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(26, 26, 46)
    pdf.cell(130, 8, "Gesamtbetrag (netto)")
    pdf.cell(0, 8, f"{_fmt(total)} {currency}  ", align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(130, 130, 130)
    pdf.multi_cell(0, 5, "Gemäß §19 UStG wird keine Umsatzsteuer berechnet.")

    pdf.ln(6)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(60, 60, 60)
    pdf.multi_cell(
        0, 5,
        f"Bitte überweisen Sie den Betrag bis zum {due_str} unter Angabe der "
        f"Rechnungsnummer {invoice_number}.",
    )

    return bytes(pdf.output())


def _fmt(value: float) -> str:
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
