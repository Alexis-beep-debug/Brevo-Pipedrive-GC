#!/usr/bin/env python3
"""Generate a test PDF with sample data to preview the template."""
import sys
sys.path.insert(0, "/home/user/phyton-test")

from proposal_generator import generate_and_save

# Beispiel-Payload wie von Superforms
test_data = {
    # Kontaktdaten
    "Firmenname": "TechVision GmbH",
    "Anschrift": "Industriestraße 42",
    "field_YSXLd": "60329",
    "field_ayedY": "Frankfurt am Main",
    "first_name": "Sarah",
    "last_name": "Müller",
    "Telefonnummer": "+49 69 123 456 78",
    "Email": "s.mueller@techvision.de",
    # Rechnungsadresse (gleich)
    "Rechnungsadresse": "off",
    # Probleme (Checkboxen)
    "Möglichkeit_2_2": [
        "Ineffektive und Inkonsistente Reinigungsqualität",
        "fehlende Kontrolle",
        "Schlechte Urlaubs/ und Krankheitsvertretung",
    ],
    # Wünsche
    "field_cCLhd": [
        "Fachbetrieb / Meisterbetrieb",
        "Digitale Nachweis- und Kontrollsysteme",
        "Alles aus einer Hand",
    ],
    # Büro
    "Menge_2_3": 8,    # Büroräume
    "Menge_27o7": 24,   # Bürotische
    "Menge_2oipp": 24,  # Bürostühle
    "field_rtCTb": 12,  # Schränke
    "Menge_2_2": 320,   # Büro m²
    # Meeting
    "Menge_2uu": 3,     # Meetingräume
    "Menge_2_37o7_2": 3, # Meetingtische
    "Menge_2ioup": 18,  # Meetingstühle
    "field_LzyvM": 75,  # Meeting m²
    # Küche
    "Menge_2_3hgt": 2,
    "field_AJctI": 2,
    "Menge_2_37o7": 2,
    "Menge_2u55": 2,
    "field_cHSyM": 2,
    "field_fCOgh": 30,
    # Sanitär
    "Menge_2rr": 4,
    "Menge_2_3t7t7": 8,
    "Menge_2": 6,
    "Menge_2_267i67i": 4,
    "field_Nsaox": 2,
    "field_TgHWm": 3,
    "field_sWVLz": 45,
    # Weitere
    "Menge": 2,
    "Menge_2uzkiz": 16,
    "field_LZShT": 22,
    "field_FjaFR": 4,
    "field_wZosx": 30,
    # Intervalle
    "Möglichkeit": "5x Woche",
    "field_yhSgD": "3x Woche",
    "field_zHLCn": "5x Woche",
    "field_IsCve": "5x Woche",
    "field_LOxcA": "3x Woche",
    "field_pdGkr": "1x Woche",
    "field_khHLN": "2x Woche",
    # Services
    "field_MCsHM": "on",   # Kühlschrank
    "Menge_2_2gff": "on",  # Mikrowelle
    "field_kwRxo": "on",   # Kaffeemaschine
    "field_QPFfk": "on",   # Spülmaschine
    "field_cPdkX": "on",   # Papier/Seife
    "field_FEykX": "on",   # Pflanzenpflege
    "field_GtKat": "on",   # Duftservice
    "field_cHHIL": "on",   # Kabelmanagement
    "Menge_2_2_2": "on",   # Fensterreinigung
    # Manuelle Felder
    "datum_begehung": "20.03.2026",
    "angebots_id": "GC-2026-0042",
    "gesamtpreis_netto": "2.480,00",
    "preis_schreibtische": "168,00",
    "preis_buerostuehle": "72,00",
    "preis_muelleimer": "96,00",
    "preis_schraenke": "48,00",
    "preis_buero_boden": "640,00",
    "preis_meeting_boden": "225,00",
    "preis_weitere_boden": "90,00",
    "preis_wc": "320,00",
    "preis_waschbecken": "120,00",
    "preis_duschen": "80,00",
    "preis_kueche": "180,00",
    "objektbeschreibung": "Modernes Bürogebäude, 2. OG, Zugang über Haupteingang mit Schlüsselkarte. Bodenbeläge: 60% Teppich, 40% Hartboden (Vinyl). Sanitäranlagen frisch renoviert.",
    "gc_email": "info@gc-facility.de",
    "gc_telefon": "+49 69 987 654 32",
}

path = generate_and_save(test_data, "Test_Angebot_TechVision.pdf")
print(f"PDF erstellt: {path}")
