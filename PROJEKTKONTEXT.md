# Projektkontext – Angebotsautomatisierung GC Facility

> **Letzte Aktualisierung:** 25. März 2026, 15:30 Uhr
> **Status:** MVP live, Finalisierung ausstehend

---

## 1. Projektübersicht

### Was macht dieses Projekt?
Automatische Erstellung von Reinigungsangeboten für G+C Facility GmbH. Wenn ein Vertriebsmitarbeiter nach einem Vor-Ort-Termin einen Fragebogen (Superforms) ausfüllt, passiert automatisch:

1. **PDF-Angebot** wird generiert (6-seitige Präsentation im GC-Design)
2. **Pipedrive** Deal + Person + Aktivität werden angelegt
3. **Lexoffice** Kontakt + finalisiertes Angebot mit Einzelposten werden erstellt
4. **Google Drive** Ordner wird erstellt, beide PDFs hochgeladen
5. **Pipedrive-Notiz** mit Drive-Link wird hinzugefügt

### Technologie-Stack
- **Sprache:** Python 3.12
- **Framework:** FastAPI (Webhook-Server)
- **PDF-Engine:** Jinja2 (Templating) + WeasyPrint (HTML→PDF)
- **APIs:** Pipedrive, Lexoffice, Google Drive (OAuth2), Superforms (Webhook)
- **Hosting:** Railway (Docker)
- **Versionierung:** GitHub

---

## 2. Repositories & Deployment

### Code-Repository (Claude Code arbeitet hier)
- **Repo:** `Alexis-beep-debug/Brevo-Pipedrive-GC`
- **Branch:** `claude/fix-deployment-railway-14flp`
- **Hinweis:** Das Repo hieß ursprünglich "phyton-test" und wurde zu "Brevo-Pipedrive-GC" umbenannt

### Deploy-Repository (Railway deployt von hier)
- **Repo:** `Alexis-beep-debug/Angebots-Automatisierung`
- **Branch:** `main`
- **Railway URL:** `https://web-production-2f3af.up.railway.app`

### Deploy-Prozess
Claude Code kann nur auf `claude/*` Branches pushen, nicht auf `main`. Deshalb wird der Code manuell über das Terminal des Entwicklers ins Deploy-Repo übertragen:

```bash
cd ~
git clone https://github.com/Alexis-beep-debug/Brevo-Pipedrive-GC.git temp-code
cd temp-code
git fetch origin claude/fix-deployment-railway-14flp
git merge origin/claude/fix-deployment-railway-14flp --no-edit
git remote add angebot https://github.com/Alexis-beep-debug/Angebots-Automatisierung.git
git push angebot main --force
cd ~
rm -rf temp-code
```

### Railway Konfiguration
- **Builder:** Dockerfile
- **Custom Start Command:** Keiner (wird vom Dockerfile CMD gesteuert)
- **Dockerfile CMD:** `sh -c 'uvicorn webhook_server:app --host 0.0.0.0 --port ${PORT:-8000}'`
- **Region:** US West 2

### Railway Umgebungsvariablen
| Variable | Beschreibung |
|---|---|
| `PIPEDRIVE_API_TOKEN` | Pipedrive API Token (Code akzeptiert auch `PIPEDRIVE_API_KEY`) |
| `LEXOFFICE_API_KEY` | Lexoffice API Key |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Google Service Account (wird als Fallback genutzt) |
| `GOOGLE_OAUTH_CLIENT_ID` | Google OAuth Client ID (primär für Drive) |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Google OAuth Client Secret |
| `GOOGLE_OAUTH_REFRESH_TOKEN` | Google OAuth Refresh Token |
| `GOOGLE_DRIVE_PARENT_FOLDER_ID` | ID des Eltern-Ordners in Google Drive |
| `PIPEDRIVE_OWNER_USER_ID` | Pipedrive User-ID für Aufgaben-Zuweisung (Default: 20546477) |

---

## 3. Dateistruktur

```
├── Dockerfile                  # Python 3.12 + WeasyPrint System-Dependencies
├── railway.json                # Railway Build-Konfiguration (DOCKERFILE builder)
├── Procfile                    # Fallback Start-Command
├── requirements.txt            # Python Dependencies
├── .env.example                # Beispiel Umgebungsvariablen
├── .gitignore                  # output/, *.pdf, .env, __pycache__
│
├── config.py                   # Zentrale Konfiguration (Env-Vars laden)
├── webhook_server.py           # FastAPI Server + /webhook/generate-proposal Endpoint
├── proposal_generator.py       # Superforms→Template Mapping + Preiskalkulation + PDF
├── lexoffice_client.py         # Lexoffice API (Kontakte, Angebote, PDF-Download)
├── pipedrive_client.py         # Pipedrive API (Personen, Deals, Notizen, Aktivitäten)
├── google_drive_client.py      # Google Drive (Ordner erstellen, PDF uploaden)
├── brevo_client.py             # Brevo API (aus altem Projekt, wird nicht aktiv genutzt)
│
├── templates/
│   └── angebot.html            # Jinja2 HTML-Template für die 6-seitige Angebots-PDF
│
├── brand_design_guide.html     # Brand Design Dokument (6 Seiten)
├── generate_test_pdf.py        # Test-Script für lokale PDF-Generierung
├── setup_gc_test.py            # Setup-Script für lokale Tests
│
├── PROJEKTDOKUMENTATION.md     # Projektdokumentation
├── PROJEKTKONTEXT.md           # Diese Datei
│
├── bulk_sync.py                # Alt: Brevo-Sync (nicht relevant)
├── sync_helpers.py             # Alt: Brevo-Sync (nicht relevant)
├── cron_deals.py               # Alt: Brevo-Sync (nicht relevant)
├── cron_persons.py             # Alt: Brevo-Sync (nicht relevant)
├── step1_preflight.py          # Alt: Brevo-Sync (nicht relevant)
└── railway.toml                # Alt: Kommentare zu Cron-Services
```

---

## 4. Webhook-Flow im Detail

### Endpoint: `POST /webhook/generate-proposal`

**Trigger:** Superforms-Formular wird abgesendet → Webhook wird aufgerufen

**Ablauf:**
1. Request kommt rein → **sofort 200 OK** zurückgeben (Superforms hat 5s Timeout)
2. Verarbeitung läuft als `asyncio.create_task(_process_proposal(payload))` im Hintergrund
3. Superforms-Payload wird entpackt:
   - `payload["data"]` extrahieren (Wrapper entfernen)
   - Nested Objects `{name, value, option_label, type}` → flach machen
   - Bei Checkboxen/Radios: `option_label` statt `value` nutzen (lesbare Texte)
4. PDF generieren (Jinja2 Template → WeasyPrint → PDF bytes)
5. Pipedrive: Person suchen/anlegen, Deal suchen/anlegen, verknüpfen
6. Lexoffice: Kontakt anlegen, Angebot mit Einzelposten erstellen (finalize=true), PDF downloaden
7. Google Drive: Ordner erstellen, beide PDFs hochladen
8. Pipedrive: Notiz + Aktivität mit Drive-Link erstellen

### Superforms Payload-Format
```json
{
  "files": [],
  "data": {
    "Firmenname": {
      "name": "Firmenname",
      "value": "Bethke & Partner",
      "label": "Firmenname",
      "exclude": 0,
      "type": "var"
    },
    "Möglichkeit_2_2": {
      "name": "Möglichkeit_2_2",
      "value": "zweite Wahl",
      "type": "var",
      "option_label": "Schlechte Urlaubs/ und Krankheitsvertretung"
    }
  }
}
```

**Wichtig:** Checkboxen senden nur den LETZTEN angekreuzten Wert, nicht alle!

---

## 5. Superforms Feld-Mapping

### Kontaktdaten
| Superforms-Feld | Beschreibung |
|---|---|
| `Firmenname` | Firmenname |
| `Anschrift` | Straße / Nummer |
| `field_YSXLd` | PLZ |
| `field_ayedY` | Stadt |
| `first_name` | Ansprechpartner Vorname |
| `last_name` | Ansprechpartner Nachname |
| `Telefonnummer` | Telefon |
| `Email` | Email |
| `Rechnungsadresse` | Toggle (on/off) für andere Rechnungsadresse |

### Räume
| Feld | Beschreibung |
|---|---|
| `Menge_2_3` | Büroräume (Anzahl) |
| `Menge_27o7` | Bürotische |
| `Menge_2oipp` | Bürostühle |
| `field_rtCTb` | Schränke/Regale |
| `Menge_2_2` | Büro m² |
| `Menge_2uu` | Meetingräume |
| `Menge_2_37o7_2` | Meetingtische |
| `Menge_2ioup` | Meetingstühle |
| `field_LzyvM` | Meeting m² |
| `Menge_2_3hgt` | Küchen |
| `field_AJctI` | Spüle |
| `Menge_2_37o7` | Küchenzeile |
| `Menge_2u55` | Spülmaschine |
| `field_cHSyM` | Kaffeemaschine |
| `field_fCOgh` | Küche m² |
| `Menge_2rr` | Sanitärräume |
| `Menge_2_3t7t7` | WC |
| `Menge_2` | Waschbecken |
| `Menge_2_267i67i` | Spiegel |
| `field_Nsaox` | Duschen |
| `field_TgHWm` | Pissoirs |
| `field_sWVLz` | Sanitär m² |
| `Menge` | Weitere Räume |
| `Menge_2uzkiz` | Mülleimer |
| `field_LZShT` | Türen |
| `field_FjaFR` | Glastüren |
| `field_wZosx` | Weitere m² |

### Reinigungsintervalle
| Feld | Beschreibung |
|---|---|
| `Möglichkeit` | Müll entsorgen (1-7x Woche) |
| `field_yhSgD` | Tische reinigen |
| `field_zHLCn` | Küche |
| `field_IsCve` | Sanitär |
| `field_LOxcA` | Boden Staubsaugen |
| `field_pdGkr` | Schränke/Regale/Drucker |
| `field_khHLN` | Griffspuren |

### Services (Toggles)
| Feld | Beschreibung |
|---|---|
| `field_MCsHM` | Kühlschrank (on/off) |
| `Menge_2_2gff` | Mikrowelle |
| `field_kwRxo` | Kaffeemaschinenpflege |
| `field_QPFfk` | Spülmaschinenservice |
| `field_cPdkX` | Papier/Seife |
| `field_FEykX` | Pflanzenpflege |
| `field_GtKat` | Duftservice |
| `field_cHHIL` | Kabelmanagement |
| `Menge_2_2_2` | Fensterreinigung nötig (on/off) |

### Probleme & Wünsche (Checkboxen – nur 1 Wert kommt an!)
| Feld | Beschreibung |
|---|---|
| `Möglichkeit_2_2` | Probleme der jetzigen Reinigung |
| `field_cCLhd` | Wünsche und Ziele |

**Die 6 Probleme:**
1. Ineffektive und Inkonsistente Reinigungsqualität
2. Schlechte Urlaubs/ und Krankheitsvertretung
3. fehlende Kontrolle
4. Intransparenz bei Leistung, Kosten und Prozessen
5. Mangelnde Zuverlässigkeit (Reliabilität)
6. Schlechtes Beschwerdemanagement

**Die 6 Wünsche:**
1. Fachbetrieb / Meisterbetrieb
2. Nachhaltigkeit und Compliance
3. Proaktivität in Beratung und Ausführung
4. Digitale Nachweis- und Kontrollsysteme
5. Kein Zeitverlust durch ständiges kontrollieren
6. Alles aus einer Hand

---

## 6. Preiskalkulation

**Stundensatz:** €36,00/h netto = €0,60/Minute

**Formel:** `Monatspreis = Anzahl × Minuten/Einheit × €0,60 × Frequenz-Faktor`

**Frequenz-Faktoren (pro Monat):**
| Frequenz | Faktor |
|---|---|
| 1x/Woche | 4,33 |
| 2x/Woche | 8,67 |
| 3x/Woche | 13,0 |
| 4x/Woche | 17,33 |
| 5x/Woche | 21,67 |
| 6x/Woche | 26,0 |
| 7x/Woche | 30,33 |
| 1x/Monat | 1,0 |
| 1x/3 Monate | 0,333 |

**Kalkulationslogik in** `proposal_generator.py` → `_calculate_prices()`

---

## 7. Brand Design

| Element | Wert |
|---|---|
| **Primary (Dunkelblau)** | `#0B426E` |
| **Accent (Rot/CTA)** | `#E7515A` |
| **Secondary (Grau-Blau)** | `#6C7A85` |
| **Green (Success)** | `#1EAF58` |
| **Hellblau** | `#8DCCFF` |
| **Gold** | `#FFB700` |
| **Text** | `#464646` |
| **Body-Text** | `#333333` |
| **Background Light** | `#F4F7FA` |
| **Body Font** | Roboto (400/500/600/700) |
| **Heading Font** | Roboto Slab (400/600/700) |
| **Website Heading** | Work Sans |
| **Greeting** | "Guten Tag" (NICHT "Sehr geehrte(r)") |
| **Logo URL** | `https://drive.google.com/uc?export=view&id=1RoInI8le_q6bx2Wo3kScu-229zQ7ZTBo` |

---

## 8. PDF-Struktur (6 Seiten, A4 Landscape)

| Seite | Inhalt | Status |
|---|---|---|
| 1 | **Deckblatt** – Logo, "ANGEBOT", Datum, Angebots-Nr, Objekt, Ansprechpartner + Anschreiben rechts | ✅ Funktioniert |
| 2 | **Optimierungspotenzial** – Probleme + G+C-Lösungen in 2-Spalten-Cards | ⚠️ Nur 1 Problem/Wunsch, individuelle Texte fehlen |
| 3 | **Daten & Fakten** – 3 Info-Cards (m², Räume, Schreibtische) + Objektbeschreibung | ⚠️ Zeigt nicht alle Elemente |
| 4 | **Kalkulation im Detail** – Tabelle mit Einzelposten + Gesamtpreis | ✅ Funktioniert |
| 5 | **Zusatzmodule** – Dynamisch basierend auf Services (2x2 Grid) | ✅ Funktioniert |
| 6 | **Closing** – "Gemeinsam für ein sauberes Ergebnis" + Kontakt | ✅ Funktioniert |

---

## 9. Bekannte Bugs & Limitationen

| Problem | Beschreibung | Priorität |
|---|---|---|
| Checkbox-Limitation | Superforms sendet nur den letzten Checkbox-Wert, nicht alle | Mittel |
| Cover-Overflow | Bei langen Adressen kann "Ansprechpartner" auf Seite 2 überlaufen | Niedrig |
| Debug-Logging | `print()` Statements erzeugen viel Output → Railway Rate Limit 500 logs/sec | Niedrig |
| Logo-Darstellung | Logo wird von Google Drive geladen, bei Netzwerkproblemen fehlt es | Niedrig |

---

## 10. Was als nächstes gemacht werden muss

### Sprint 1: Angebotsautomatisierung finalisieren

**1. Deal-Phase in Pipedrive**
- Wenn Deal neu angelegt wird → automatisch in Phase "Angebotserstellung" setzen
- Pipedrive Pipeline-Phasen müssen abgefragt werden (stage_id ermitteln)

**2. Objektzusammenfassung (Seite 3) erweitern**
- Aktuell: nur Büro m², Räume gesamt, Schreibtische
- SOLL: Alle Elemente als komplette Objektzusammenfassung (Bürotische, Stühle, Schränke, Meetingräume, -tische, -stühle, Küchen, Spüle, Küchenzeile, Spülmaschine, Kaffeemaschine, WC, Waschbecken, Spiegel, Duschen, Pissoirs, Mülleimer, Türen, Glastüren etc.)

**3. Optimierungspotenzial (Seite 2) individualisieren**
- Für jedes der 6 Probleme einen eigenen individuellen Text schreiben
- Text soll zeigen "wir verstehen euer Problem", nicht nur den Checkbox-Text wiederholen
- Wenn 1 Problem angekreuzt → alle 3 Kategorien trotzdem zeigen
- Problem→Lösung Mapping in `proposal_generator.py` → `PROBLEM_SOLUTION_MAP`

**4. Automatische Angebotsemail versenden**
- Nach PDF-Generierung + Drive-Upload
- Betreff: "Unser Angebot: Reinigungsqualität, auf die Sie zählen können."
- Body-Text:
```
Guten Tag [Herr/Frau] [Nachname],

Im Anhang erhalten Sie unser individuelles Angebot für die gewünschten Reinigungsleistungen.

Unser Versprechen: Verabschieden Sie sich endlich von Reinigungsbeschwerden.
Über 50 zufriedene Großkunden in Berlin mit Reinigungsflächen von 500 m² - 15000 m² können das bestätigen.

Ich freue mich auf Ihre Rückmeldung und eine mögliche Zusammenarbeit.

Mit freundlichen Grüßen
```
- PDF als Anhang oder Drive-Link

### Sprint 2: Automatische Lead-Anreicherung (separates Railway-Modul)
- Neuer Service in Railway (eigene Codebasis, eigenes Deployment)
- Agent recherchiert Firmen-Website + Kontaktperson
- Schreibt Ergebnisse in Pipedrive-Notizen
- Trigger: Wenn neuer Lead/Person in Pipedrive angelegt wird

### Was wir NICHT machen
- Terminvorbereitungs-Email (macht der Vertriebler manuell)
- Phase Nachfassen (nicht unsere Aufgabe)
- Große PDF-Überarbeitung (nur die genannten Punkte)

---

## 11. Kunden-Pipeline (Gesamtbild)

```
Cold Lead → Anfrage Lead → Vor-Ort Termin → Angebotserstellung → Nachfassen → Gewonnen/Verloren → Kunden
    │            │              │                  │                  │                              │
    │            │              │                  │                  │                              │
    ▼            ▼              ▼                  ▼                  ▼                              ▼
  [Sprint 2]  [Sprint 2]   [Superforms]      [✅ UMGESETZT]    [Manuell]                    [30-Tage
  Lead-Agent  Email→PD     Fragebogen        PDF+PD+LX+Drive   Vertriebler                  Feedback]
                                              + [TODO: Email]
```

---

## 12. Curl-Befehl für Tests

```bash
curl -X POST https://web-production-2f3af.up.railway.app/webhook/generate-proposal \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "Firmenname": {"name": "Firmenname", "value": "Testfirma GmbH", "type": "var"},
      "Anschrift": {"name": "Anschrift", "value": "Teststr. 1", "type": "var"},
      "field_YSXLd": {"name": "field_YSXLd", "value": "90443", "type": "var"},
      "field_ayedY": {"name": "field_ayedY", "value": "Nürnberg", "type": "var"},
      "first_name": {"name": "first_name", "value": "Max", "type": "var"},
      "last_name": {"name": "last_name", "value": "Mustermann", "type": "var"},
      "Telefonnummer": {"name": "Telefonnummer", "value": "+49123456", "type": "var"},
      "Email": {"name": "Email", "value": "test@test.de", "type": "var"},
      "Möglichkeit_2_2": {"name": "Möglichkeit_2_2", "value": "zweite Wahl", "type": "var", "option_label": "Schlechte Urlaubs/ und Krankheitsvertretung"},
      "Menge_2_3": {"name": "Menge_2_3", "value": "5", "type": "var"},
      "Menge_27o7": {"name": "Menge_27o7", "value": "5", "type": "var"},
      "Menge_2_2": {"name": "Menge_2_2", "value": "500", "type": "var"},
      "Menge_2rr": {"name": "Menge_2rr", "value": "2", "type": "var"},
      "Menge_2_3t7t7": {"name": "Menge_2_3t7t7", "value": "2", "type": "var"},
      "Rechnungsadresse": {"name": "Rechnungsadresse", "value": "off", "type": "var"}
    },
    "files": []
  }'
```
