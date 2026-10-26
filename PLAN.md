# Applify – Projektplan

> Persönlicher Bewerbungsassistent: findet täglich passende Stellen, bewertet sie gegen das eigene Profil und erzeugt auf Zusage ein fertiges Bewerbungspaket.

Stand: 26.10.2026 · Status: M0–M3 umgesetzt, M4 umgesetzt (Abnahme offen: ≥ 50 Firmen mit Feed, Abdeckungsmessung), M5 Marktanalyse in Arbeit

---

## 1. Ziel und Rahmen

| | |
|---|---|
| **MVP-Nutzer** | Eine Person (Entwickler selbst), lokal auf Windows 11 |
| **Perspektive** | Später Mehrnutzer-Produkt, gehostet, mit automatischem Zeitplan – Architektur bereitet das vor, MVP baut es nicht |
| **Budget** | ca. 86 h, keine harte Deadline |
| **Erfolgskriterien** | **Präzision:** In den Top 10 des Rankings sind ≥ 7 Stellen, die der Nutzer selbst als passend einstuft. **Abdeckung:** Von 30 passenden Stellen, die der Nutzer manuell auf StepStone/LinkedIn & Co. findet, hat Applify ≥ 70 % ebenfalls gefunden (§5.7). |
| **Grundsatz** | Nichts wird ohne ausdrückliche Freigabe des Nutzers abgeschickt. Im MVP wird überhaupt nichts automatisch versendet. |

### Beispielprofil (Referenz für Tests)
Fullstack-Webentwickler, 2,5 Jahre Erfahrung · Orte: Leipzig, Dresden, Berlin, Hamburg (jeweils mit Radius) · Mindestgehalt 50.000 € brutto/Jahr · Deutsch Muttersprache, Englisch B2.

---

## 2. Anforderungen

### 2.1 Funktional (MVP)

**Profil & Dokumente**
- F1 Upload von Lebenslauf (PDF), Zeugnissen (PDF, mehrere) und optional einem Beispielanschreiben (PDF oder Text).
- F2 Nach dem Lebenslauf-Upload liest das **lokale LLM** den Lebenslauf aus und liefert einen strukturierten Profilvorschlag (Kontaktdaten, Wunschrollen, Skills, Sprachen, Stationen, Berufsjahre). Code prüft und normalisiert das Ergebnis (siehe §5.4). Neue Angaben werden direkt ins Profil eingetragen; Werte, die von bestehenden Angaben abweichen, erscheinen als Diff (F4). Alle Felder bleiben editierbar und erweiterbar.
- F3 Das Profil umfasst:
  - Wunschrollen (mehrere, z. B. „Fullstack Developer“, „Frontend Developer“)
  - Skills mit **Gewichtung** (`Pflicht` / `gern` / `will ich nicht`) und optional Level
  - Orte mit **Radius in km** pro Ort; **Remote** als eigene Option (`nein` / `hybrid ok` / `voll remote ok`)
  - Mindestgehalt (brutto/Jahr), Sprachen mit Niveau (GER), Seniorität / Berufsjahre
  - Ausschlusswörter (z. B. „Zeitarbeit“, „SAP“), bevorzugte/ausgeschlossene Firmen
  - Anschreiben-Einstellungen: Ton (frei wählbar), Beispielanschreiben, feste Stichpunkte
- F4 Lebenslauf kann jederzeit erneut ausgelesen werden; Änderungen werden als Diff zum aktuellen Profil angezeigt und einzeln übernommen, damit manuelle Anpassungen nicht überschrieben werden.

**Stellensuche**
- F5 Suchlauf wird **manuell** per Button ausgelöst; Fortschritt ist im UI sichtbar.
- F6 Quelle **Bundesagentur für Arbeit** über die Jobsuche-API; Suchbegriffe werden aus Wunschrollen und Pflicht-Skills abgeleitet, Orte + Radius werden direkt übergeben.
- F7 Quelle **Karriereseiten**: Stellen werden direkt von den Karriereseiten der Firmen auf einer **Firmen-Watchlist** abgerufen – über öffentliche Feeds der Bewerbermanagement-Systeme (ATS: Personio, Greenhouse, Lever, Recruitee, SmartRecruiters, Workday) oder generisch über eingebettetes `schema.org/JobPosting` (JSON-LD), wobei Stellen-URLs zusätzlich über die `sitemap.xml` gefunden werden.
- F7a **Firmen-Watchlist**: füllt sich automatisch (Status `Kandidat`) mit Firmen aus allen Stellen-Treffern, aus **GitHub-Organisationen** mit Standort in den Profil-Orten und aus **Wikidata** (Unternehmen mit Sitz in den Profil-Orten). Der Nutzer kann Karriere-URLs manuell hinzufügen. Das ATS wird automatisch erkannt. Firmen lassen sich `beobachten` oder `ignorieren`.
- F7b Quelle **Aggregator-APIs**: Adzuna und Arbeitnow für zusätzliche Breite.
- F7c Quelle **öffentlicher Dienst**: Stellenangebote von service.bund.de per RSS.
- F7d Alle Quellen sind einzeln **aktivier-/deaktivierbar**; pro Lauf zeigt das UI je Quelle: gefundene, neue, duplizierte Stellen und Fehler.
- F8 Stellen ohne Volltext (z. B. BA ohne Detailtext, Aggregator-Snippet) werden als **„nur Kurzinfo“** markiert. Auf der Detailseite kann der Nutzer den Anzeigentext manuell einfügen → Stelle wird neu bewertet.
- F9 **Deduplizierung**: Dieselbe Stelle aus mehreren Quellen wird zu einem Eintrag zusammengeführt (alle Quellen-Links bleiben erhalten).
- F10 Bereits gesehene Stellen werden bei späteren Läufen nicht erneut als „neu“ angezeigt.
- F10a **Abdeckungs-Check**: Der Nutzer trägt manuell gefundene Stellen ein (URL oder Firma + Titel). Applify prüft per Dedup-Logik, ob die Stelle im Bestand ist, über welche Quelle, und zeigt die Abdeckungsquote sowie die verpassten Stellen (§5.7).

**Matching & Ranking**
- F11 Harte Filter per Code, Soft-Score 0–100 per Code (siehe §5.3).
- F12 Jede Stelle zeigt Score **plus nachvollziehbare Begründung** (✓ Treffer, ✗ Abzüge, ? unbekannt).
- F13 Fehlende Angaben (z. B. Gehalt) wirken **neutral** – weder Abzug noch Bonus.

**Bewerbung**
- F14 Nutzer kann einer Stelle **zusagen**.
- F15 Daraufhin erzeugt das lokale LLM ein deutsches Anschreiben aus: Profil, Stellentext, Ton, Beispielanschreiben (Stilvorlage), Pflicht-Stichpunkten.
- F16 Anschreiben ist im Browser **editierbar**, kann neu generiert werden (optional mit Zusatzhinweis).
- F17 Ergebnis ist ein **Bewerbungspaket** mit **einzelnen** Dateien: `Anschreiben.pdf`, `Lebenslauf.pdf`, `Zeugnisse*.pdf` – als ZIP-Download und als Ordner auf der Platte.
- F18 **Kopierhilfe**: Seite mit allen Daten zum Einfügen in Portalformulare (Name, Kontakt, Gehaltswunsch, Eintrittsdatum, Anschreiben-Text, Link zur Anzeige, ggf. Bewerbungs-E-Mail-Adresse) jeweils mit Kopier-Button.
- F19 Bewerbungsstatus: `neu` → `gesehen` → `zugesagt` → `Paket fertig` → `abgeschickt` (manuell gesetzt) → `Antwort erhalten`.

**Marktanalyse** (§5.8)
- F20 Jeder Suchlauf legt jede gesehene Stelle **append-only** als Sichtung ab (Rohdaten mit Zeitstempel, nie überschrieben). So bleibt die Historie erhalten: wann eine Anzeige zuerst und zuletzt gesehen wurde, wie sich die Nachfrage über die Zeit entwickelt.
- F21 Aus jeder Stelle werden Merkmale gewonnen: Rollenfamilie, Seniorität, geforderte Berufsjahre, Gehalt (normalisiert auf brutto/Jahr), Skills aus der Taxonomie plus neue Skill-Kandidaten, Sprachen, Abschluss. Zuerst per Regeln, für Lücken per lokalem LLM (Budget pro Lauf). Pro Feld ist sichtbar, ob es per Regel, LLM oder gar nicht bestimmt wurde.
- F22 Eine ELT-Pipeline (Dagster + dbt) baut daraus nach jedem Suchlauf automatisch ein Sternschema mit fertigen Aggregaten; Datenqualität per dbt-Tests und Asset-Checks.
- F23 **Markt-Dashboard**: Verteilung und Trend der Skills, Skill-Kombinationen, Abgleich mit dem eigenen Profil (gefragte Skills, die fehlen), geforderte Erfahrung und Seniorität je Rollenfamilie, Gehälter je Rolle/Seniorität – jeweils mit Datenabdeckung (n). Filter: Zeitraum, Umfang (eigene Orte / Deutschland / alle), Rollenfamilie, Seniorität, Quelle.

### 2.2 Ansichten (SPA)
1. **Dashboard / Tagesliste** – gerankte Stellen, Filter „nur neue“, Suchlauf starten, Fortschritt
2. **Stellendetail** – Volltext/Kurzinfo, Score-Aufschlüsselung, Quellen-Links, Volltext einfügen, Zusagen
3. **Profil** – Formular inkl. Skill-Gewichtung, Orte/Radius, Remote, Gehalt, Sprachen, Ausschlüsse
4. **Dokumente** – Upload/Verwaltung Lebenslauf, Zeugnisse, Beispielanschreiben
5. **Bewerbungen** – Liste mit Status; Editor für Anschreiben; Paket-Download; Kopierhilfe
6. **Firmen** – Watchlist mit Status (Kandidat / beobachtet / ignoriert), erkanntem ATS, letztem Abruf und Fehlern; Karriere-URL hinzufügen
7. **Abdeckung** – Stichprobe eintragen, Quote gesamt und je Quelle, verpasste Stellen mit vermutetem Grund
8. **Einstellungen** – Quellen an/aus, API-Keys (Adzuna, optional GitHub-Token), LLM-Modell, Suchparameter, Abruf-Limits
9. **Markt** – Dashboard der Marktanalyse (F23), Datenstand der Pipeline, Skill-Kandidaten in die Taxonomie übernehmen

### 2.3 Nicht-funktional
- N1 **Datenschutz**: Im MVP verlassen keine persönlichen Daten den Rechner (Anfragen an Stellen- und Discovery-Quellen enthalten nur Suchbegriffe und Orte; Abrufe von Karriereseiten enthalten keine Nutzerdaten). LLM läuft lokal.
- N2 **Persistenz**: Datenbank und Dateien liegen als Bind-Mount unter `./data/` und überleben `docker compose down`.
- N3 **Mehrnutzer-vorbereitet**: Jede nutzerbezogene Tabelle hat `user_id`. Im MVP existiert genau ein Nutzer, kein Login.
- N4 **Austauschbarkeit**: Jobquellen und LLM-Anbieter sind Plugins hinter Interfaces.
- N5 **Reproduzierbarkeit**: Ranking ist deterministisch (gleiche Eingabe → gleicher Score) und per Unit-Tests abgesichert.
- N6 **Höfliches Abrufen**: `robots.txt` wird beachtet, eindeutiger User-Agent mit Kontaktadresse, max. 1 Anfrage/s pro Host, Caching per `ETag`/`Last-Modified`, nur öffentliche Seiten ohne Login.
- N7 **Start** mit einem Befehl: `docker compose up` (Ollama läuft separat nativ).

### 2.4 Bewusst nicht im MVP
Automatischer Zeitplan · Versand per Mail · Quellen der Stufe 2 und 3 (§5.1) – u. a. Remote-Jobbörsen, HN „Who is hiring?“, OpenStreetMap-Discovery, weitere ATS-Adapter, Interamt/Länderportale, LLM-Fallback für Karriereseiten ohne Feed/JSON-LD, Websuche-API · Ablehnen mit Feedback/Lernen · Login & Mehrnutzer · Cloud-LLM (Claude API) · OCR für gescannte PDFs · Browser-Erweiterung · weitere Jobquellen · Hosting.

---

## 3. Designentscheidungen

| # | Entscheidung | Begründung | Verworfen |
|---|---|---|---|
| D1 | **Deterministisches Ranking, LLM für Text-Verstehen und Text-Erzeugen** | LLM wird für Lebenslauf-Extraktion und Anschreiben genutzt – dort ist freie Struktur bzw. Sprache gefragt. Filter und Ranking bleiben Code: schnell, testbar, erklärbar, reproduzierbar. | LLM-basiertes Ranking (langsam, nicht reproduzierbar); regelbasierte CV-Extraktion (bei freien Layouts zu fehleranfällig) |
| D2 | **Lokales LLM: Ollama + `qwen3:14b`** (Q4) | Passt in 16 GB VRAM der RX 7800 XT, gute Deutschqualität für die Größe, kostenlos, keine Daten in der Cloud. | 32b-Modell (passt nicht in VRAM), Cloud-API im MVP |
| D3 | **Ollama nativ unter Windows**, nicht in Docker | Docker Desktop reicht AMD-GPUs unter Windows nicht durch. Zugriff per `http://host.docker.internal:11434`. | Ollama-Container (nur CPU) |
| D4 | **LLM-Abstraktion** `LLMProvider` (`generate`, `generate_structured(schema)`) | Claude API oder andere später ohne Umbau. Hinweis: Ein Claude-Pro-Abo kann **nicht** als API-Backend genutzt werden; dafür ist ein API-Key nötig. | Direkte Ollama-Aufrufe im Code |
| D5 | **Strukturierte LLM-Ausgabe** über Ollamas `format`-Parameter mit JSON-Schema, abgeleitet aus Pydantic-Modellen | Erzwingt valides JSON, Ergebnis wird direkt per Pydantic validiert; ein Retry bei Validierungsfehler. | Freitext-Antwort + Regex |
| D6 | **Keine Portal-Logins / kein Scraping von Jobbörsen** (LinkedIn, XING, StepStone, Indeed, Glassdoor, Monster) und kein Abgreifen von Google for Jobs | AGB-Verstoß, Datenbankherstellerrecht (§ 87b UrhG) – für das spätere Produkt ein Haftungsrisiko –, dazu IP-Sperren/Captchas und Kontosperrung. Öffentliche Karriereseiten der Arbeitgeber selbst und Quellen mit offizieller API/RSS sind davon nicht betroffen. Die meisten Portal-Anzeigen stammen ohnehin aus einem ATS und werden dort erfasst. Rest: manuelles Einfügen, später Browser-Erweiterung. | Gespeicherte Zugangsdaten + Headless-Browser; SERP-Scraping-Dienste für Google for Jobs |
| D7 | **Backend: Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2** | Leichtgewichtig, typisiert, automatisches OpenAPI-Schema. | Django (zu schwer für reine API) |
| D8 | **Frontend: SvelteKit im SPA-Modus** (`adapter-static`), TypeScript | Passt zum Web-Dev-Hintergrund, skaliert mit wachsender Komplexität. Typen werden per `openapi-typescript` aus dem Backend generiert. | HTMX (weniger flexibel), React |
| D9 | **PostgreSQL 16** in Docker, Daten in `./data/postgres` | Mehrnutzer-tauglich, JSONB für Rohdaten und Score-Aufschlüsselung, `pg_trgm` für Fuzzy-Dedup. | SQLite (Umzug später nötig) |
| D10 | **Hintergrundjobs im MVP in-process** (Thread + Tabelle `search_runs` mit Status/Fortschritt, Polling aus dem UI) | Keine zusätzliche Infrastruktur. Schnittstelle so geschnitten, dass später ein Worker (arq/Redis) oder Scheduler (APScheduler) übernimmt. Gilt auch für CV-Extraktion und Anschreiben-Generierung (dauern Sekunden bis eine Minute). | Celery/Redis im MVP |
| D11 | **Geodaten offline**: GeoNames-Datensatz DE (Orte + PLZ), per `python -m applify.build_geonames` zu zwei kompakten TSV-Dateien in `resources/` aufbereitet (~0,8 MB, CC BY 4.0) und beim Start in den Speicher geladen; Distanz per Haversine | Keine externen Geocoding-Aufrufe, keine Rate-Limits, schnell. | Nominatim/Google Geocoding |
| D12 | **Skill-Taxonomie als YAML** im Repo (kanonischer Name, Synonyme, Kategorie) | Gemeinsame Sprache für CV-Extraktion und Matching: LLM-Ausgabe wird darauf normalisiert („JS“ → „JavaScript“, „Vue.js“ → „Vue“), Stellentexte ebenso. Unbekannte Skills bleiben als Freitext erhalten. | ESCO komplett (zu groß für MVP, aber später als Quelle nutzbar) |
| D13 | **PDF-Erzeugung: HTML-Template + WeasyPrint** im Container | Anschreiben-Layout mit Jinja2/CSS gestaltbar; WeasyPrint läuft unter Linux problemlos. | LaTeX, reportlab |
| D14 | **PDF-Textextraktion: `pdfplumber`** (Fallback `pypdf`), Text geht dann ans LLM | Gute Ergebnisse bei Text-PDFs, auch mit Spalten-Layout; OCR bewusst ausgelassen. | Tesseract im MVP; PDF direkt an ein Vision-Modell |
| D15 | **Karriereseiten über ATS-Feeds statt HTML-Scraping**: ein Adapter pro ATS (Personio XML, Greenhouse/Lever/Recruitee/SmartRecruiters/Workday JSON), generischer Fallback über `schema.org/JobPosting` (JSON-LD) mit Stellen-URLs aus `sitemap.xml`. Gespeicherte Feed-/Seiten-Antworten als Test-Fixtures. | Feeds sind stabile, strukturierte Schnittstellen mit Volltext; JSON-LD pflegen viele Firmen ohnehin für Google for Jobs. Wenige Adapter decken sehr viele Firmen ab. | Gmail-Empfehlungsmails (Auswahl durch Portal-Algorithmus, nur Kurzinfo, fragile Parser, OAuth-Token läuft alle 7 Tage ab); freier Web-Crawler; HTML-Scraper pro Firma |
| D16 | **Firmen-Discovery über eine Watchlist** statt freiem Crawlen: Firmen aus allen Stellen-Treffern, GitHub-Organisationen und Wikidata werden Kandidaten, Karriereseite und ATS werden einmalig erkannt, danach wird direkt der Feed abgefragt | Das schwierige Problem ist, *welche* Firmen man ansieht, nicht das Auslesen. Stellenquellen liefern die Liste gratis mit; GitHub-Orgs sind fast immer Tech-Firmen (passt zum Profil); Wikidata ergänzt größere Unternehmen. Alle drei mit offizieller API. | Websuche-API im MVP (Key, Kosten, Anbieterlage unklar → Ausblick); LLM-Agent mit Websuche (langsam, nicht reproduzierbar, widerspricht D1); Common Crawl (zu groß, nicht tagesaktuell) |
| D17 | **Viele Quellen als Plugins, in Stufen eingeführt** (§5.1): MVP = BA, 2 Aggregatoren, service.bund.de, 6 ATS-Adapter, JSON-LD + Sitemap, Discovery über Treffer/GitHub/Wikidata | Maximale Abdeckung bei begrenztem Budget; jede weitere Quelle ist ein kleines Plugin. Welche Quelle als nächste kommt, entscheidet die Abdeckungsmessung (§5.7), nicht das Bauchgefühl. | Alle Quellen auf einmal (sprengt das Budget); nur eine Quelle (zu große Lücken) |
| D18 | **Python-Tooling: `uv`, `ruff`, `pytest`, `mypy`**; Frontend: `pnpm`, `vitest`, `eslint`/`prettier` | Schnell, modern, wenig Konfiguration. | – |
| D19 | **Marktanalyse als ELT: Rohdaten in Postgres, Transformation mit `dbt-core`** in Schichten (staging → intermediate → marts, Sternschema) | Branchenstandard, SQL-Modelle mit Tests, Doku und Lineage; dieselbe Datenbank, aber eigene Schemas (`raw`, `features`, `staging`, `marts`) – App-Tabellen bleiben unberührt. Doppeltes Ziel: nützliches Dashboard **und** lehrbuchmäßiger Aufbau. | Eigene Python-/SQL-Views (wenig Struktur); DuckDB als separates Warehouse (zweiter Datenspeicher, Abgleich nötig) |
| D20 | **Orchestrierung mit Dagster**, nur für die Analyse-Seite, lokal per `uv` (`dagster dev`) | Asset-orientiert, erstklassige dbt-Integration (jedes Modell ein Asset mit Lineage), Sensoren, Asset-Checks, gute lokale UI. Die Suche bleibt in Applify (Button, Live-Fortschritt); ein Sensor startet die Pipeline nach jedem fertigen Suchlauf. Grenze: App = operativ, Dagster = analytisch. | Prefect (dbt-Anbindung schwächer); Airflow (schwergewichtig, unter Windows nur per Docker); Suche ebenfalls in Dagster (Umbau der App-Logik) |
| D21 | **Raw-Schicht append-only, von Applify geschrieben**: `raw.job_sightings` je Lauf und Stelle, `raw.job_versions` mit Roh-JSON und Text nur bei geändertem Inhalt | Nur der Suchlauf weiß, was in welchem Lauf gesehen wurde. Append-only erlaubt Historie (first/last seen, Trends) und jederzeit neues Transformieren; Versionen statt Volltext je Sichtung halten das Wachstum klein. | Pipeline liest die App-Tabellen (Rohdaten werden dort überschrieben, Historie nur per Snapshot) |
| D22 | **Merkmals-Extraktion: Regeln zuerst, LLM-Fallback mit Budget** (max. 50 Stellen pro Lauf), Ergebnisse versioniert (`extractor_version`) und je Text-Hash + Prompt-Version gecacht | Regeln sind schnell, deterministisch und testbar; das LLM füllt nur Lücken (v. a. Gehalt, Abschluss, unklare Rollen) und belegt die GPU begrenzt. Abweichung von D1 ist bewusst: Es geht um Text-Verstehen, nicht um Ranking. | Nur Regeln (lückenhaft); LLM für alles (Stunden GPU-Zeit initial) |
| D23 | **Dashboard in Applify, Metabase optional** als Container (Compose-Profil `analytics`) mit Nur-Lese-Rolle auf `marts` | Feste Kennzahlen gehören in die App; Metabase dient zum Erkunden und zur Kontrolle der Pipeline, ohne Profil- oder Bewerbungsdaten zu sehen. | Nur BI-Tool (Dashboards nicht im Repo); nur App (keine Ad-hoc-Analysen) |

---

## 4. Architektur

```
┌──────────────────────── Browser ────────────────────────┐
│  SvelteKit SPA (statisch, von FastAPI ausgeliefert)      │
└───────────────┬──────────────────────────────────────────┘
                │ JSON/REST (OpenAPI)
┌───────────────▼──────────── Docker: app ─────────────────┐
│ FastAPI                                                  │
│  ├─ api/            Router: profile, documents, jobs,    │
│  │                  runs, applications, companies,       │
│  │                  coverage, settings                   │
│  ├─ services/                                            │
│  │   ├─ profile_extraction  (CV → LLM → Profilvorschlag) │
│  │   ├─ search_runner       (orchestriert Quellen)       │
│  │   ├─ normalization+dedup                              │
│  │   ├─ coverage            (Abdeckungs-Check)           │
│  │   ├─ matching            (Filter + Score + Begründung)│
│  │   ├─ cover_letter        (Prompt, LLM, Revisionen)    │
│  │   └─ packaging           (PDF, ZIP, Kopierhilfe)      │
│  ├─ sources/   JobSource-Interface (ein Plugin je Quelle)│
│  │   ├─ arbeitsagentur.py                                │
│  │   ├─ aggregators/   adzuna.py, arbeitnow.py           │
│  │   ├─ public/        service_bund.py                   │
│  │   └─ careers/       jsonld.py, sitemap.py,            │
│  │                     ats/{personio,greenhouse,lever,   │
│  │                     recruitee,smartrecruiters,        │
│  │                     workday}.py                       │
│  ├─ discovery/ CompanySource-Interface                   │
│  │   ├─ from_jobs.py, github.py, wikidata.py             │
│  │   └─ detect.py      (Karriereseite + ATS erkennen)    │
│  ├─ llm/       LLMProvider-Interface → ollama.py,        │
│  │             prompts/ (versionierte Prompt-Templates)  │
│  └─ db/        SQLAlchemy-Modelle, Alembic               │
└──────┬───────────────────────┬──────────────────┬────────┘
       │                       │                  │
┌──────▼──────┐   ┌────────────▼─────┐   ┌────────▼─────────┐
│ Docker: db  │   │ Ollama (Windows, │   │ Extern:          │
│ Postgres 16 │   │ nativ, GPU)      │   │ BA Jobsuche-API, │
│ ./data/pg   │   │ qwen3:14b        │   │ Adzuna,Arbeitnow,│
│             │   │                  │   │ service.bund.de, │
│             │   │                  │   │ Karriereseiten / │
│             │   │                  │   │ ATS-Feeds,       │
│             │   │                  │   │ GitHub, Wikidata │
└─────────────┘   └──────────────────┘   └──────────────────┘
Dateien: ./data/files/{user_id}/documents|packages
```

**Analyse-Seite (M5, §5.8):**
```
Suchlauf ──E+L──▶ raw.job_sightings / raw.job_versions        (Applify, append-only)
                     │
Dagster (lokal)      │  Sensor: Suchlauf fertig
                     ▼
  features.job_features   Python-Asset: Regeln → LLM-Fallback (Ollama, Budget)
                     ▼
  dbt build               staging → intermediate → marts (+ Tests, Asset-Checks)
                     ▼
  marts.*  ──▶ Applify-Seite „Markt“ (API)  ·  Metabase (optional, nur lesend)
```

### 4.1 Projektstruktur
```
applify/
├─ PLAN.md
├─ docker-compose.yml
├─ .env.example
├─ data/                 # gitignored, persistente Daten
├─ backend/
│  ├─ pyproject.toml
│  ├─ alembic/
│  ├─ applify/           # Pakete wie in §4
│  ├─ resources/         # skills.yaml, geonames, PDF-Templates
│  └─ tests/             # inkl. fixtures/feeds, fixtures/pages, fixtures/cvs
├─ analytics/            # eigenes uv-Projekt (M5)
│  ├─ applify_analytics/ # Dagster-Definitionen, Merkmals-Extraktion
│  ├─ dbt/               # dbt-Projekt: models/{staging,intermediate,marts}, seeds, tests
│  ├─ resources/         # roles.yaml
│  └─ tests/
└─ frontend/
   ├─ package.json
   └─ src/
      ├─ lib/api/        # generierte Typen + Client
      └─ routes/         # dashboard, jobs/[id], profile, documents,
                         # applications, companies, coverage, settings
```

### 4.2 Datenmodell (Kern)

| Tabelle | Wichtige Felder |
|---|---|
| `users` | id, name, email, created_at |
| `profiles` | user_id, roles[], seniority_years, salary_min, remote_pref, exclude_keywords[], exclude_companies[], tone, cover_letter_bullets[], contact (JSONB), experience (JSONB: Stationen) |
| `profile_skills` | profile_id, skill (kanonisch oder Freitext), weight (`must`/`nice`/`avoid`), level, source (`cv`/`user`) |
| `profile_locations` | profile_id, name, lat, lon, radius_km |
| `profile_languages` | profile_id, language, level (A1–C2, native) |
| `documents` | id, user_id, type (`cv`/`certificate`/`sample_letter`), filename, path, extracted_text, extraction_result (JSONB), uploaded_at |
| `companies` | id, name, name_norm, website, careers_url, ats_type (`personio`/`greenhouse`/`lever`/`recruitee`/`smartrecruiters`/`workday`/`jsonld`/`unknown`), ats_token, discovered_from (`jobs`/`github`/`wikidata`/`user`), detection_status (`pending`/`done`/`failed`), last_checked_at, last_error, etag |
| `user_companies` | user_id, company_id, status (`candidate`/`watch`/`ignore`), added_at |
| `jobs` | id, company_id, title, company, location_raw, lat, lon, remote_type, salary_min, salary_max, description, has_full_text, fingerprint, first_seen_at |
| `job_sources` | job_id, source (`ba`/`adzuna`/`arbeitnow`/`service_bund`/`ats:<typ>`/`jsonld`/`manual`), external_id, url, raw (JSONB), fetched_at — **unique(source, external_id)** |
| `source_settings` | user_id, source, enabled, config (JSONB, z. B. API-Key-Referenz, Limits) |
| `search_runs` | id, user_id, started_at, finished_at, status, progress, stats (JSONB), errors (JSONB) |
| `job_matches` | user_id, job_id, score, breakdown (JSONB), excluded_reason, status, seen_at, run_id |
| `applications` | id, match_id, status, cover_letter_text, generation_inputs (JSONB), package_path, created_at, sent_at |
| `cover_letter_revisions` | application_id, text, source (`llm`/`user`), created_at |
| `coverage_samples` | id, user_id, url, company, title, found_via (Portal, z. B. `stepstone`), matched_job_id, matched_sources[], miss_reason, checked_at |

**Analyse-Schemas (M5):**

| Tabelle | Wichtige Felder |
|---|---|
| `raw.job_sightings` | id, run_id, seen_at, source, external_id, job_id, content_hash — append-only |
| `raw.job_versions` | content_hash (PK), source, external_id, job_id, title, description, payload (JSONB), first_seen_at |
| `features.job_features` | job_id, content_hash, extractor_version, role_family, seniority, years_min, years_max, salary_min/max_eur_year, salary_currency, salary_period, skills[], skill_candidates[], languages (JSONB), degree, origin (JSONB: Feld → `rule`/`llm`/`none`), extracted_at |
| `features.llm_cache` | content_hash, prompt_version, result (JSONB), created_at |
| `marts.*` | `fct_job_postings`, `bridge_job_skills`, `dim_skill`, `dim_role_family`, `dim_region`, `dim_date`, Aggregate `agg_*` (von dbt gebaut) |

`jobs` und `companies` sind bewusst **nicht** nutzerbezogen (eine Stelle oder Firma ist für alle Nutzer dieselbe), `job_matches` und `user_companies` schon – das spart später doppelte Abrufe.

---

## 5. Kernlogik

### 5.1 Jobquellen

**Quellen-Stufen** (alle mit offizieller API, RSS oder als öffentliche Arbeitgeberseite; siehe D6, D17)

| Stufe | Stellenquellen | Firmen-Discovery |
|---|---|---|
| **MVP** | BA · Adzuna · Arbeitnow · service.bund.de (RSS) · ATS: Personio, Greenhouse, Lever, Recruitee, SmartRecruiters, Workday · JSON-LD + Sitemap | aus Stellen-Treffern · GitHub-Organisationen · Wikidata · manuell |
| **Stufe 2** (direkt nach MVP) | Remote-Jobbörsen mit API/RSS (Remotive, RemoteOK mit Quellenangabe, We Work Remotely, Himalayas) · Berlin Startup Jobs (RSS) · HN „Who is hiring?“ (HN-/Algolia-API, LLM strukturiert den Freitext) · ATS: Ashby, Teamtailor, Join, Workable, softgarden, d.vinci, rexx, SuccessFactors · Interamt, Karriereportale Sachsen/Berlin/Hamburg · LLM-Fallback für Karriereseiten ohne Struktur · Jooble, Careerjet (Partner-Registrierung) | OpenStreetMap (Overpass-API, z. B. `office=it`/`office=company` mit `website`) |
| **Später** | Browser-Erweiterung für Portal-Anzeigen | Websuche-API (z. B. `site:jobs.personio.de <Stadt>`) |
| **Ausgeschlossen** | StepStone, Indeed, LinkedIn, XING, Glassdoor, Monster, Google for Jobs (D6) | – |

Die Reihenfolge innerhalb von Stufe 2 richtet sich nach den verpassten Stellen der Abdeckungsmessung (§5.7).

**Bundesagentur für Arbeit**
- Suche: `GET https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs`, Header `X-API-Key: jobboerse-jobsuche` (öffentlicher Schlüssel, Doku: bund.dev / github.com/bundesAPI/jobsuche-api). **Spike 21.10.2026:** `v4/jobs` antwortet inzwischen mit 403, `v6` funktioniert (Liste heißt jetzt `ergebnisliste`).
- Parameter: `was` (Suchbegriff), `wo` (Ort), `umkreis` (km), `angebotsart=1` (Arbeit), `veroeffentlichtseit` (Tage), `page`, `size` (≤ 100 sinnvoll; zu tiefe Seiten → 400 „Ergebnismenge überschritten“).
- Die Suche liefert bereits Koordinaten (`breite`/`laenge`), Gehalt (`festgehalt` bzw. `gehaltsspanneVon/Bis` mit `verguetungsangabe` Jahr/Monat/Stunde), Homeoffice (`homeofficemoeglich`, `homeofficeprozent`), `externeURL` und `istArbeitnehmerUeberlassung` (Zeitarbeit).
- Pro Lauf: Kreuzprodukt aus abgeleiteten Suchbegriffen × Orten, Ergebnis über `referenznummer` dedupliziert.
- Bei Remote-Präferenz „voll remote ok“ zusätzlich je Suchbegriff eine deutschlandweite Suche mit `homeoffice=prozentual_100` (v6-Filter: Mindestanteil Homeoffice in Prozent, `nv_true` = „nach Vereinbarung“; das v4-`arbeitszeit=ho` liefert in v6 keine Treffer mehr).
- Detail/Volltext: `GET …/pc/v4/jobdetails/{base64(referenznummer)}` liefert `stellenangebotsBeschreibung` (Markdown, meist mehrere tausend Zeichen), auch für Anzeigen mit externer URL. `v6/jobdetails` antwortet mit 403. Abruf nur für neue Anzeigen; bei Fehler bleibt die Kurzinfo + Link.

**Spike-Ergebnis (M2, 21.10.2026) für die übrigen Quellen**

| Quelle | Ergebnis |
|---|---|
| Arbeitnow | `GET https://www.arbeitnow.com/api/job-board-api?page=N` → 200, 300 Stellen pro Seite, `description` als HTML (escaped), Felder `remote`, `location`, `tags`, `created_at`. Nutzungsbedingung: „free public API, please do not abuse“, Rücklink erwünscht. |
| Adzuna | Ohne Key 400 (erwartet) – Key beantragen. |
| service.bund.de | M2 nicht erreichbar; **M4 (22.10.2026):** RSS über das Suchformular mit `jobsrss=true` und `templateQueryString=<Begriff>` → 200, bis 100 Einträge. Der Begriff filtert, die Ortsparameter nicht → lokaler Vorfilter. Einträge enthalten nur Arbeitgeber, PLZ/Ort und Frist; die Detailseiten haben kein JSON-LD → Kurzinfo. |
| Greenhouse | `boards-api.greenhouse.io/v1/boards/{token}/jobs` → 200 (gitlab, n26, celonis). |
| Lever | `api.lever.co/v0/postings/{token}?mode=json` → 200 (spotify, palantir), Volltext als `descriptionPlain`. |
| Personio | `{token}.jobs.personio.de/xml` → 200 (chrono24, 1komma5grad); falsche Tokens → 404 – Token muss aus der Karriereseite erkannt werden. |
| Recruitee | `{token}.recruitee.com/api/offers` → 200 (bunq). |
| SmartRecruiters | `api.smartrecruiters.com/v1/companies/{id}/postings` → 200 (BoschGroup; unbekannte Firma: 200 mit leerer Liste). |
| Workday | `POST …/wday/cxs/{tenant}/{site}/jobs` → 200 (Deutsche Bank `db/DBWebsite`), 401 bei falscher Site – Site-Name muss erkannt werden. |
| GitHub | `/search/users?q=type:org+location:Leipzig` → 200 ohne Token (257 Orgs, viele Forschungs-/Open-Source-Orgs). |
| Wikidata | SPARQL `P159` (Hauptsitz) + `P856` (Website) → 200 in < 1 s; ohne Filter auf Unternehmen (`P31/P279* Q4830453`) kommen auch Vereine/Parteien – der Unterklassen-Pfad lief in den Timeout, daher in M4 mit konkreten Klassen (z. B. `Q4830453`, `Q6881511`) filtern. **M4:** Umkreissuche (`wikibase:around` auf die Koordinaten des Hauptsitzes) funktioniert; der Endpunkt antwortet 403, wenn der User-Agent keine Kontaktadresse enthält → Wikidata-Discovery nur mit Kontaktadresse (Einstellungen). |

**Aggregator-APIs**
- **Adzuna**: kostenloser API-Key, Land `de`, Suche nach Begriff + Ort + Distanz; liefert meist nur einen Textauszug → Kurzinfo, Volltext ggf. per Dedup mit Karriereseite.
- **Arbeitnow**: öffentliche Job-Board-API mit deutschen Stellen (speist sich selbst aus ATS-Feeds), seitenweise abrufen und lokal nach Ort/Remote filtern.
- Gleiche Suchbegriffe und Orte wie bei der BA. Limits und Nutzungsbedingungen im Spike (M2) prüfen.

**Öffentlicher Dienst – service.bund.de**
- RSS-Feed der Stellensuche (Suchparameter in der Feed-URL), Einträge mit Link zur Ausschreibung; Volltext über die verlinkte Seite (JSON-LD, sonst Kurzinfo). Feed-Format im Spike (M2) prüfen.

**Firmen-Discovery** (Ergebnis in `companies`, über `name_norm` bzw. Website-Domain dedupliziert)
- **Quellen für Kandidaten:**
  - *Stellen-Treffer*: jede Firma aus BA, Aggregatoren, service.bund.de.
  - *GitHub*: `GET /search/users?q=type:org+location:<Ort>` je Profil-Ort, danach `GET /orgs/{org}` für das Feld `blog` (Website). Ohne Token ist das Such-Limit sehr niedrig → optionaler persönlicher Token in den Einstellungen.
  - *Wikidata*: SPARQL-Abfrage auf Unternehmen mit Hauptsitz (`P159`) im Profil-Ort und offizieller Website (`P856`); einmalig bzw. wöchentlich, Ergebnis gecacht.
  - *Manuell*: Karriere-URL eintragen.
- **Erkennung** (`detect.py`, einmalig pro Firma, max. ~50 neue Firmen pro Lauf, Rest in der Warteschlange):
  1. Karriereseite finden: Links in der Anzeige, Website der Firma + typische Pfade (`/karriere`, `/jobs`, `/careers`, `/stellenangebote`) und Links mit diesen Wörtern auf der Startseite.
  2. ATS erkennen über URL-Muster und eingebettete Links/Skripte (`*.jobs.personio.de`/`.com`, `boards.greenhouse.io`, `jobs.lever.co`, `*.recruitee.com`, `jobs.smartrecruiters.com`, `*.myworkdayjobs.com`); daraus `ats_token` ableiten.
  3. Sonst: enthält die Karriereseite oder eine aus `sitemap.xml` gefundene Stellen-URL `JobPosting`-JSON-LD → `jsonld`, sonst `unknown`.
- GitHub- und Wikidata-Kandidaten ohne erkannte Karriereseite werden nicht angezeigt, um die Firmen-Ansicht übersichtlich zu halten.

**Karriereseiten (ATS-Feeds + JSON-LD)**
- **Abruf** pro Lauf für alle Firmen mit Status `watch` (und `candidate`, sofern ATS bekannt):
  - Personio: `https://{token}.jobs.personio.de/xml`
  - Greenhouse: `https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true`
  - Lever: `https://api.lever.co/v0/postings/{token}?mode=json`
  - Recruitee: `https://{token}.recruitee.com/api/offers`
  - SmartRecruiters: `https://api.smartrecruiters.com/v1/companies/{token}/postings` (Detail mit Volltext: `/postings/{id}`)
  - Workday: `POST https://{tenant}.{wdN}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs` mit `searchText`/`limit`/`offset`, Detail über `externalPath` – **öffentlich, aber undokumentiert**, daher besonders fehlertolerant implementieren
  - JSON-LD: Karriereseite, verlinkte Stellenseiten und Stellen-URLs aus `sitemap.xml` (gefiltert nach Mustern wie `/job`, `/stelle`, `/karriere/`) laden, alle `JobPosting`-Objekte extrahieren (`title`, `jobLocation`, `baseSalary`, `datePosted`, `validThrough`, `description`, `employmentType`, `jobLocationType`)
  - **Endpunkte im Spike (M2) gegen echte Firmen verifizieren.**
- Vorfilter vor dem Speichern: nur Stellen, deren Ort in einem Radius liegt oder die remote-kompatibel sind (Feeds liefern alle Stellen einer Firma).
- Fehler pro Firma werden in `last_error` gespeichert und in der Firmen-Ansicht angezeigt, der Lauf läuft weiter.
- Etikette laut N6; bedingte Requests (`ETag`), damit unveränderte Feeds kaum Last erzeugen.

**Suchbegriffe** = Wunschrollen + Kombinationen „Rolle + Top-Pflicht-Skill“ (z. B. „Fullstack Entwickler“, „Fullstack Python“), begrenzt auf max. ~8 Begriffe pro Ort, um Rate-Limits zu schonen.

### 5.2 Normalisierung & Deduplizierung
1. Titel/Firma normalisieren (Kleinschreibung, Rechtsformen wie „GmbH“ entfernen, „(m/w/d)“ entfernen).
2. Ort → Koordinaten über GeoNames; „Remote“/„Homeoffice“-Erkennung per Schlüsselwörter.
3. Gehalt per Regex (Spannen, „k“, Monats-→Jahreswert).
4. `fingerprint = hash(firma_norm + titel_norm + ort_norm)`; zusätzlich Fuzzy-Abgleich (`pg_trgm`, Ähnlichkeit ≥ 0,85) gegen Stellen der letzten 30 Tage → Zusammenführen, bessere Daten (Volltext) gewinnen.

### 5.3 Matching

**Harte Filter** (Stelle wird ausgeblendet, Grund wird gespeichert und ist einsehbar):
- Ausschlusswort im Titel/Text, ausgeschlossene Firma
- Ort bekannt **und** außerhalb aller Radien **und** nicht remote-kompatibel
- Gehalt bekannt **und** Obergrenze < Mindestgehalt
- Geforderte Sprache/Niveau nicht erfüllt (nur wenn explizit erkannt)
- „will ich nicht“-Skill als Kernanforderung im Titel

**Soft-Score** (0–100), gewichtete Komponenten:

| Komponente | Gewicht | Berechnung |
|---|---|---|
| Skills | 45 | Vor allem der Anteil der geforderten Technologien, die zum Profil passen (Pflicht voll, gern halb); fremde Kerntechnologien ziehen runter, Cloud/DevOps/Testing halb, Tools/Methoden/Design gar nicht. Dazu, wie viele Wunsch-Skills genannt sind; avoid-Skills geben Abzug. Keine konkreten Technologien erkennbar (Volltext oder Kurzinfo) → neutral (50 %) |
| Rolle/Titel | 20 | Ähnlichkeit Titel ↔ Wunschrollen (Token-Overlap + Synonyme) |
| Seniorität | 15 | Junior/Mid passt zu 2,5 J.; „Senior/Lead/Principal“ oder „5+ Jahre“ → Abzug |
| Ort/Remote | 10 | Distanz innerhalb Radius, Bonus für passende Remote-Option |
| Gehalt | 10 | Über Mindestgehalt → voll, knapp darunter → teilweise |

- **Neutralität (F13):** Unbekannte Komponente wird **aus der Gewichtung genommen**, die übrigen werden auf 100 renormiert. Die Begründung zeigt „? Gehalt unbekannt“. Ausnahme Skills: Sie zählen unbekannt mit 50 %, sonst erreichen Kurzinfos allein über Titel und Ort 100.
- **Kurzinfo-Stellen** (ohne Volltext) bekommen ein Badge „geringe Datenbasis“; Score basiert dann v. a. auf Titel, Ort, Seniorität.
- `breakdown` (JSONB) speichert pro Komponente Punkte + Belege → Grundlage für UI-Begründung und Tests.
- **Später optional:** semantische Ähnlichkeit per lokalem Embedding-Modell (z. B. `bge-m3` über Ollama) als zusätzliche Komponente.

### 5.4 Lebenslauf-Extraktion (lokales LLM)
1. **Text** per `pdfplumber` aus dem PDF (bei leerem Text: Hinweis „gescanntes PDF – bitte Text-PDF hochladen“).
2. **LLM-Aufruf** mit `generate_structured`: Prompt + JSON-Schema aus Pydantic-Modell `CvExtraction`:
   - `contact` (Name, E-Mail, Telefon, Adresse)
   - `roles` (abgeleitete Berufsbezeichnungen)
   - `skills[]` (Name, Kategorie, Evidenz = Textstelle aus dem CV)
   - `languages[]` (Sprache, Niveau)
   - `experience[]` (Arbeitgeber, Rolle, von, bis)
   - `education[]`
3. **Validierung & Normalisierung per Code:**
   - Pydantic-Validierung, bei Fehler ein Retry mit Fehlermeldung im Prompt
   - Skills auf `skills.yaml` normalisieren; Skills ohne Evidenz im Originaltext werden verworfen (Schutz gegen Halluzinationen)
   - E-Mail/Telefon per Regex gegenprüfen
   - Berufsjahre aus `experience[]` per Code berechnen (nicht vom LLM schätzen lassen)
   - Niveaus auf GER mappen („verhandlungssicher“ → C1 usw.)
4. **Vorschlag im UI**: Felder mit Quelle „aus Lebenslauf“ markiert; Skills starten mit Gewicht `gern`, Nutzer stuft hoch/runter. Bei erneutem Auslesen → Diff (F4).

Prompt-Templates liegen versioniert unter `llm/prompts/`; Test mit 2–3 anonymisierten Beispiel-CVs als Fixtures (Abnahme: Felder gegen erwartete Werte, Toleranz für Formulierungen).

### 5.5 Anschreiben
- Prompt-Bausteine: Systemrolle (deutsches Bewerbungsanschreiben, max. 1 Seite, keine erfundenen Fakten), Profil (nur relevante Felder), Stellentext, Ton, Beispielanschreiben als **Stilreferenz** (nicht kopieren), Pflicht-Stichpunkte (müssen vorkommen).
- Nach Generierung: Prüfung per Code, ob alle Pflicht-Stichpunkte enthalten sind (Fuzzy) → Warnung im Editor statt stiller Fehler.
- Jede Generierung und jede Nutzerbearbeitung wird als Revision gespeichert.
- PDF über HTML-Template mit Briefkopf aus Profil-Kontaktdaten, Datum, Empfänger (Firma, sofern bekannt), Betreff.

### 5.6 Bewerbungspaket
```
data/files/<user>/packages/<datum>_<firma>_<titel>/
├─ Anschreiben.pdf
├─ Lebenslauf.pdf
├─ Zeugnisse_01_<name>.pdf …
└─ (ZIP aller Dateien zum Download)
```
Plus Kopierhilfe-Ansicht (F18). Status wechselt auf „Paket fertig“; „abgeschickt“ setzt der Nutzer manuell.

### 5.7 Abdeckungsmessung
- **Stichprobe**: Der Nutzer sucht auf StepStone, LinkedIn, Indeed & Co. von Hand 30 passende Stellen in seinen Orten und trägt sie ein (URL oder Firma + Titel + Ort). Applify ruft dabei **keine** Portalseiten ab – die Angaben kommen vom Nutzer.
- **Abgleich** über die Dedup-Logik aus §5.2 (Fingerprint + Fuzzy) gegen alle Stellen der letzten 30 Tage, auch gefilterte.
- **Ergebnis**: Quote gesamt, Anteil je Quelle (welche Quelle hat die Stelle geliefert, welche allein), Liste der verpassten Stellen mit vermutetem Grund:
  - Firma unbekannt → Discovery-Lücke
  - Firma bekannt, ATS `unknown` → Adapter- oder LLM-Fallback-Lücke
  - Firma beobachtet, Stelle fehlt → Fehler im Adapter oder Vorfilter
  - Stelle gefunden, aber per hartem Filter ausgeblendet → Filter zu streng
- Die Messung wird nach M4 und danach monatlich wiederholt; die häufigsten Gründe bestimmen die nächste Quelle aus Stufe 2.

### 5.8 Marktanalyse (ELT)

**Extract + Load (Applify):** Jeder Suchlauf schreibt pro gesehener Stelle eine Zeile in `raw.job_sightings` (Lauf, Zeitpunkt, Quelle, externe ID, `job_id`, Hash über Titel + Text + Roh-JSON). Ändert sich der Hash, kommt zusätzlich eine Zeile in `raw.job_versions` mit dem vollständigen Inhalt. Bestandsstellen vor der Umstellung bekommen einmalig eine Version; ihre Historie beginnt mit `jobs.first_seen_at`.

**Merkmale (Python-Asset `job_features`):**

| Merkmal | Regel | LLM-Fallback |
|---|---|---|
| Rollenfamilie | Schlüsselwörter im Titel laut `roles.yaml` (Backend, Frontend, Fullstack, Data, DevOps/Cloud, Embedded, Mobile, SAP, QA, IT-Admin, Sonstige) | ja, bei unklarem Titel |
| Seniorität | Titel (Junior/Senior/Lead) hat Vorrang, sonst Jahre: < 2 Junior, 2–4 Mid, ≥ 5 Senior (konfigurierbar) | nein (folgt aus Titel/Jahren) |
| Berufsjahre | Muster wie „3+ Jahre“, „mindestens 2 Jahre“, „3–5 years“ | ja |
| Gehalt | strukturierte Quellfelder, Muster wie „55.000–65.000 €“, „4.500 € brutto/Monat“; Monat/Stunde → Jahr | ja |
| Skills | Taxonomie (wie Matching) | ja: zusätzliche **Skill-Kandidaten** außerhalb der Taxonomie |
| Sprachen, Abschluss | Muster (wie Matching), Abschluss-Begriffe | ja |

- LLM nur für Volltext-Stellen mit Lücken, max. **50 pro Pipeline-Lauf**, älteste zuerst; Ergebnis per Pydantic-Schema (D5), Cache je Text-Hash + Prompt-Version.
- Gehalt nur in **EUR** in Statistiken; andere Währungen werden erfasst, aber ausgeschlossen. Plausibilität 15.000–300.000 €/Jahr.
- `extractor_version` steigt bei Regel- oder Taxonomie-Änderungen → Regeln laufen für alle Stellen neu (schnell), LLM-Ergebnisse kommen aus dem Cache.

**Transform (dbt):**
- `staging`: bereinigte Sichten auf `raw`, `features`, App-Tabellen (`jobs`, `job_sources`, Profil) und Seeds (Skill-Taxonomie, Rollenfamilien).
- `intermediate`: Laufzeit je Stelle (first/last seen, aktiv), Region (Bundesland aus Koordinaten), Umfang (in Profil-Orten / Deutschland / Ausland).
- `marts`: `fct_job_postings` (Grain: zusammengeführte Stelle), `bridge_job_skills`, Dimensionen; Aggregate `agg_skills_weekly`, `agg_skill_pairs`, `agg_experience`, `agg_salary`, `agg_profile_gap`.
- Tests: Schlüssel eindeutig/nicht leer, Beziehungen, Wertebereiche; Dagster-Asset-Checks für Abdeckung (Anteil bestimmter Rollen/Seniorität).

**Orchestrierung (Dagster):** Sensor auf `search_runs` (Status `done`) → `job_features` → `dbt build` → Checks. Manuell auslösbar in der Dagster-UI.

**Dashboard „Markt“:** Applify-API liest nur `marts`. Jede Gehalts- und Erfahrungszahl zeigt n und den Anteil ohne Angabe. Skill-Kandidaten lassen sich per Klick in `skills.yaml` übernehmen (wirkt dann auch aufs Matching).

---

## 6. Fahrplan (≈ 120 h)

Jeder Meilenstein endet mit etwas Lauffähigem. Die LLM-Schicht wandert wegen der CV-Extraktion in M1 nach vorn.

| # | Meilenstein | Inhalt | Aufwand | Ergebnis / Abnahme |
|---|---|---|---|---|
| **M0** | Fundament | Git, `docker-compose` (app + db, Bind-Mounts), FastAPI-Gerüst, Alembic, SvelteKit-SPA mit Layout & Routing, OpenAPI→TS-Typen, ruff/pytest/vitest, Ollama installieren + `qwen3:14b` auf der GPU testen | 7 h | `docker compose up` → leere SPA, Healthcheck grün (inkl. Ollama erreichbar), DB überlebt Neustart |
| **M1** | Profil, Dokumente, LLM-Schicht | `LLMProvider` + Ollama inkl. `generate_structured`, Upload/Verwaltung, PDF-Text, `skills.yaml` (Start: ~150 Web-/Dev-Skills), CV-Extraktion + Validierung, Profil-Formular inkl. Skill-Gewichtung, Orte/Radius, Remote, Sprachen, Diff bei erneutem Auslesen | 16 h | Eigener CV hochgeladen → Profil ≥ 90 % korrekt vorbefüllt, Rest editierbar |
| **M2** | Quelle BA + Pipeline | Spike BA-API (inkl. Detail-Endpunkt) **und** Kurz-Check aller MVP-Quellen aus §5.1 (Adzuna, Arbeitnow, service.bund.de-RSS, je 2–3 echte Firmen pro ATS, GitHub-/Wikidata-Abfrage), `JobSource`-Plugin-Interface, BA-Client, Suchbegriff-Ableitung, Normalisierung, GeoNames-Import, Dedup, `search_runs` mit Fortschritt | 12 h | Suchlauf-Button liefert BA-Stellen in der DB, ohne Duplikate |
| **M3** | Matching & Tagesliste | Harte Filter, Score, Breakdown, Dashboard, Detailseite, „neu/gesehen“, Volltext einfügen + Neubewertung | 12 h | **Erstes Erfolgskriterium prüfbar**: Top 10 manuell bewerten |
| **M4** | Weitere Quellen & Abdeckung | Adzuna, Arbeitnow, service.bund.de; Tabellen `companies`/`user_companies`/`source_settings`; Discovery aus Treffern, GitHub, Wikidata; Erkennung Karriereseite + ATS; Adapter Personio/Greenhouse/Lever/Recruitee/SmartRecruiters/Workday mit Fixtures; JSON-LD + Sitemap; Vorfilter Ort/Remote; Firmen-Ansicht; Quellen an/aus + Statistik je Quelle; Abdeckungs-Check (Tabelle, Abgleich, Ansicht) | 20 h | ≥ 50 Firmen mit erkanntem ATS/JSON-LD auf der Watchlist, deren Stellen erscheinen **mit Volltext** gerankt in der Liste; **Abdeckungsmessung durchgeführt**, Zielwert ≥ 70 % |
| **M5** | Marktanalyse (ELT + Dashboard) | Raw-Schicht im Suchlauf (Sichtungen, Versionen); `analytics/`-Projekt mit Dagster + dbt; Regel-Extraktion (Rolle, Seniorität, Jahre, Gehalt, Sprachen, Abschluss) mit `roles.yaml`; LLM-Fallback mit Budget + Cache, Skill-Kandidaten; dbt-Modelle staging/intermediate/marts mit Tests; Sensor + Asset-Checks; Metabase optional mit Nur-Lese-Rolle; API + Seite „Markt“ | 34 h | Nach einem Suchlauf läuft die Pipeline automatisch, dbt-Tests grün; Dashboard zeigt Skills, Erfahrung und Gehalt mit sichtbarer Abdeckung; für ≥ 80 % der Volltext-Stellen sind Rollenfamilie und Seniorität bestimmt |
| **M6** | Anschreiben & Paket | Anschreiben-Prompt, Stichpunkt-Prüfung, Editor mit Revisionen, PDF-Template, Paket/ZIP, Kopierhilfe, Bewerbungsliste mit Status | 13 h | Zusage → editierbares Anschreiben → Paket mit 3+ PDFs |
| **M7** | Puffer & Feinschliff | Fehlerfälle (Ollama nicht erreichbar, Quelle/Feed nicht erreichbar), Tuning der Score-Gewichte am echten Datenbestand, README | 6 h | Eine Woche Eigennutzung ohne Blocker |

**Gesamt: ~120 h.** Wenn es eng wird, zuerst kürzen: Workday-Adapter und Wikidata-Discovery (M4), Metabase und Skill-Kombinationen (M5), Revisionshistorie (M6), CV-Diff (M1), Fuzzy-Dedup (nur Fingerprint).

---

## 7. Risiken

| Risiko | Wahrscheinlichkeit | Auswirkung | Gegenmaßnahme |
|---|---|---|---|
| Discovery findet zu wenige Karriereseiten / ATS | mittel | Watchlist bleibt klein, wenig Mehrwert ggü. BA | Mehrere Discovery-Quellen, manuelles Hinzufügen per URL, Erkennungsquote sichtbar, Abdeckungsmessung zeigt Lücken; Stufe 2: OpenStreetMap, später Websuche-API |
| Abdeckung bleibt unter 70 % | mittel | Relevante Stellen fehlen | Verpasste Stellen nach Grund auswerten (§5.7), gezielt Quellen aus Stufe 2 nachziehen; reine Portal-Anzeigen bleiben eine Lücke bis zur Browser-Erweiterung |
| Workday-Endpunkt ist undokumentiert und ändert sich | mittel | Konzern-Stellen fehlen | Fehlertoleranter Adapter, Fixtures, Fallback JSON-LD; Konzerne sind meist auch bei der BA |
| Rate-Limits (GitHub-Suche, Adzuna, Wikidata) | mittel | Discovery/Lauf unvollständig | Ergebnisse cachen, Discovery wöchentlich statt pro Lauf, optionaler GitHub-Token, Warteschlange für neue Firmen |
| Viele Quellen → viele Duplikate und Rauschen | hoch | Unübersichtliche Liste | Dedup (§5.2) mit Quellenliste pro Stelle, Vorfilter Ort/Remote vor dem Speichern, Ranking + harte Filter |
| ATS-Anbieter ändern oder sperren öffentliche Feeds | gering | Ein Adapter fällt aus | Adapter isoliert, Fixtures-Tests, `last_error` pro Firma, JSON-LD als Fallback |
| Karriereseiten ohne Feed und ohne JSON-LD | mittel | Firma nicht abrufbar | Status `unknown` sichtbar; LLM-Fallback als Ausblick |
| Seiten blockieren automatisierte Abrufe | gering | Einzelne Firmen fehlen | Etikette (N6), niedrige Frequenz, kein Umgehen von Sperren |
| BA-API ist inoffiziell dokumentiert, Endpunkte ändern sich | mittel | Quelle fällt aus | Spike zuerst (M2), Client isoliert hinter Interface |
| Kurzinfo-Stellen (BA ohne Detail, Aggregator-Snippets) zu dünn für gutes Ranking | mittel | Schlechtere Top 10 | Volltext aus Karriereseite derselben Firma per Dedup übernehmen; Badge + manuelles Einfügen |
| LLM halluziniert Skills/Stationen im CV | mittel | Falsches Profil | Evidenz-Pflicht pro Skill, Berufsjahre per Code, Nutzer bestätigt Vorschlag |
| `qwen3:14b` schreibt mittelmäßiges Deutsch | mittel | Viel Nacharbeit am Anschreiben | Gutes Beispielanschreiben, Stichpunkte, Editor; Provider austauschbar |
| ROCm/Ollama-Probleme mit der AMD-GPU | gering | Langsame Generierung | Früh in M0 testen; Fallback kleineres Modell (`qwen3:8b`) |
| Wenige Stellen nennen ein Gehalt (Bestand: ~9 %) | hoch | Gehaltsstatistik dünn und verzerrt | Text-Extraktion per Regel + LLM, n und Abdeckung immer anzeigen, Gehalt nur in EUR |
| LLM-Extraktion belegt die GPU lange | mittel | PC während der Pipeline träge | Budget pro Lauf, Cache je Text-Hash, Regeln zuerst |
| Analyse-Pipeline und App-Schema driften auseinander | mittel | dbt-Modelle brechen nach Migrationen | Staging-Modelle als einzige Stelle, die App-Tabellen liest; `dbt build` in den Tests |

---

## 8. Ausblick nach dem MVP

1. **Zeitplan & Hosting**: Scheduler (APScheduler oder Cron im Worker), Benachrichtigung über neue Top-Treffer
2. **Browser-Erweiterung** „An Applify senden“ für Volltexte aus eingeloggten Portal-Sitzungen
3. **Ablehnen mit Grund** → Gewichte/Ausschlüsse automatisch vorschlagen
4. **Cloud-LLM** (Claude API) als wählbarer Provider pro Nutzer
5. **Versand per Mail** (eigener Scope `gmail.send` oder SMTP), weiterhin nur nach Freigabe
6. **Mehrnutzer**: Login (OIDC), Mandantentrennung, Verschlüsselung der Dokumente, DSGVO (Auftragsverarbeitung bei Cloud-LLM, Löschkonzept, Auskunft); geteilte Firmen-Datenbank über alle Nutzer
7. **Quellen der Stufe 2** (§5.1), Reihenfolge nach Abdeckungsmessung; danach **Websuche-API** für die Firmen-Discovery
8. **Sonstiges**: OCR für gescannte Zeugnisse; Embedding-basiertes Matching

---

## 9. Offene Punkte (in der Umsetzung klären)
- ~~Verfügbarkeit/Format des BA-Detail-Endpunkts~~ → geklärt im Spike M2 (§5.1)
- ~~service.bund.de-RSS~~ → in M4 erreichbar (§5.1)
- Adzuna-API-Key und ggf. GitHub-Token beantragen
- Kontaktadresse für den User-Agent (N6): per `APPLIFY_HTTP_CONTACT` konfigurierbar, Standard leer
- Layout/Design des Anschreiben-PDFs (eigene Vorlage vorhanden?)
- Feintuning der Score-Gewichte nach den ersten echten Läufen
- Chart-Bibliothek für das Markt-Dashboard (Kandidaten: LayerChart, ECharts)
