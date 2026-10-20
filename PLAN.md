# Applify – Projektplan

> Persönlicher Bewerbungsassistent: findet täglich passende Stellen, bewertet sie gegen das eigene Profil und erzeugt auf Zusage ein fertiges Bewerbungspaket.

Stand: 20.10.2026 (Gmail-Quelle verworfen; Quellen erweitert: Karriereseiten, Aggregatoren, öffentlicher Dienst, Firmen-Discovery; Abdeckungsmessung) · Status: Planung abgeschlossen, MVP-Umsetzung ausstehend

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
- F2 Nach dem Lebenslauf-Upload liest das **lokale LLM** den Lebenslauf aus und liefert einen strukturierten Profilvorschlag (Kontaktdaten, Wunschrollen, Skills, Sprachen, Stationen, Berufsjahre). Code prüft und normalisiert das Ergebnis (siehe §5.4). Der Vorschlag wird vor dem Speichern angezeigt; alle Felder bleiben editierbar und erweiterbar.
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

### 2.2 Ansichten (SPA)
1. **Dashboard / Tagesliste** – gerankte Stellen, Filter „nur neue“, Suchlauf starten, Fortschritt
2. **Stellendetail** – Volltext/Kurzinfo, Score-Aufschlüsselung, Quellen-Links, Volltext einfügen, Zusagen
3. **Profil** – Formular inkl. Skill-Gewichtung, Orte/Radius, Remote, Gehalt, Sprachen, Ausschlüsse
4. **Dokumente** – Upload/Verwaltung Lebenslauf, Zeugnisse, Beispielanschreiben
5. **Bewerbungen** – Liste mit Status; Editor für Anschreiben; Paket-Download; Kopierhilfe
6. **Firmen** – Watchlist mit Status (Kandidat / beobachtet / ignoriert), erkanntem ATS, letztem Abruf und Fehlern; Karriere-URL hinzufügen
7. **Abdeckung** – Stichprobe eintragen, Quote gesamt und je Quelle, verpasste Stellen mit vermutetem Grund
8. **Einstellungen** – Quellen an/aus, API-Keys (Adzuna, optional GitHub-Token), LLM-Modell, Suchparameter, Abruf-Limits

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
| D11 | **Geodaten offline**: GeoNames-Datensatz DE (Orte + PLZ) einmalig importiert, Distanz per Haversine | Keine externen Geocoding-Aufrufe, keine Rate-Limits, schnell. | Nominatim/Google Geocoding |
| D12 | **Skill-Taxonomie als YAML** im Repo (kanonischer Name, Synonyme, Kategorie) | Gemeinsame Sprache für CV-Extraktion und Matching: LLM-Ausgabe wird darauf normalisiert („JS“ → „JavaScript“, „Vue.js“ → „Vue“), Stellentexte ebenso. Unbekannte Skills bleiben als Freitext erhalten. | ESCO komplett (zu groß für MVP, aber später als Quelle nutzbar) |
| D13 | **PDF-Erzeugung: HTML-Template + WeasyPrint** im Container | Anschreiben-Layout mit Jinja2/CSS gestaltbar; WeasyPrint läuft unter Linux problemlos. | LaTeX, reportlab |
| D14 | **PDF-Textextraktion: `pdfplumber`** (Fallback `pypdf`), Text geht dann ans LLM | Gute Ergebnisse bei Text-PDFs, auch mit Spalten-Layout; OCR bewusst ausgelassen. | Tesseract im MVP; PDF direkt an ein Vision-Modell |
| D15 | **Karriereseiten über ATS-Feeds statt HTML-Scraping**: ein Adapter pro ATS (Personio XML, Greenhouse/Lever/Recruitee/SmartRecruiters/Workday JSON), generischer Fallback über `schema.org/JobPosting` (JSON-LD) mit Stellen-URLs aus `sitemap.xml`. Gespeicherte Feed-/Seiten-Antworten als Test-Fixtures. | Feeds sind stabile, strukturierte Schnittstellen mit Volltext; JSON-LD pflegen viele Firmen ohnehin für Google for Jobs. Wenige Adapter decken sehr viele Firmen ab. | Gmail-Empfehlungsmails (Auswahl durch Portal-Algorithmus, nur Kurzinfo, fragile Parser, OAuth-Token läuft alle 7 Tage ab); freier Web-Crawler; HTML-Scraper pro Firma |
| D16 | **Firmen-Discovery über eine Watchlist** statt freiem Crawlen: Firmen aus allen Stellen-Treffern, GitHub-Organisationen und Wikidata werden Kandidaten, Karriereseite und ATS werden einmalig erkannt, danach wird direkt der Feed abgefragt | Das schwierige Problem ist, *welche* Firmen man ansieht, nicht das Auslesen. Stellenquellen liefern die Liste gratis mit; GitHub-Orgs sind fast immer Tech-Firmen (passt zum Profil); Wikidata ergänzt größere Unternehmen. Alle drei mit offizieller API. | Websuche-API im MVP (Key, Kosten, Anbieterlage unklar → Ausblick); LLM-Agent mit Websuche (langsam, nicht reproduzierbar, widerspricht D1); Common Crawl (zu groß, nicht tagesaktuell) |
| D17 | **Viele Quellen als Plugins, in Stufen eingeführt** (§5.1): MVP = BA, 2 Aggregatoren, service.bund.de, 6 ATS-Adapter, JSON-LD + Sitemap, Discovery über Treffer/GitHub/Wikidata | Maximale Abdeckung bei begrenztem Budget; jede weitere Quelle ist ein kleines Plugin. Welche Quelle als nächste kommt, entscheidet die Abdeckungsmessung (§5.7), nicht das Bauchgefühl. | Alle Quellen auf einmal (sprengt das Budget); nur eine Quelle (zu große Lücken) |
| D18 | **Python-Tooling: `uv`, `ruff`, `pytest`, `mypy`**; Frontend: `pnpm`, `vitest`, `eslint`/`prettier` | Schnell, modern, wenig Konfiguration. | – |

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
- REST: `GET https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs`, Header `X-API-Key: jobboerse-jobsuche` (öffentlicher Schlüssel, Doku: bund.dev / github.com/bundesAPI/jobsuche-api).
- Parameter: `was` (Suchbegriff), `wo` (Ort), `umkreis` (km), `angebotsart=1` (Arbeit), `veroeffentlichtseit` (Tage), `page`, `size`.
- Pro Lauf: Kreuzprodukt aus abgeleiteten Suchbegriffen × Orten, Ergebnis über `refnr` dedupliziert.
- Detail-/Volltext-Abruf: **im Spike (M2) verifizieren** – der Detail-Endpunkt hat sich in der Vergangenheit geändert. Fallback: Kurzinfo + Link.

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
| Skills | 45 | Treffer der Pflicht-Skills (voll), gern-Skills (halb), avoid-Skills (Abzug) im Stellentext, über Synonyme |
| Rolle/Titel | 20 | Ähnlichkeit Titel ↔ Wunschrollen (Token-Overlap + Synonyme) |
| Seniorität | 15 | Junior/Mid passt zu 2,5 J.; „Senior/Lead/Principal“ oder „5+ Jahre“ → Abzug |
| Ort/Remote | 10 | Distanz innerhalb Radius, Bonus für passende Remote-Option |
| Gehalt | 10 | Über Mindestgehalt → voll, knapp darunter → teilweise |

- **Neutralität (F13):** Unbekannte Komponente wird **aus der Gewichtung genommen**, die übrigen werden auf 100 renormiert. Die Begründung zeigt „? Gehalt unbekannt“.
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

---

## 6. Fahrplan (≈ 86 h)

Jeder Meilenstein endet mit etwas Lauffähigem. Die LLM-Schicht wandert wegen der CV-Extraktion in M1 nach vorn.

| # | Meilenstein | Inhalt | Aufwand | Ergebnis / Abnahme |
|---|---|---|---|---|
| **M0** | Fundament | Git, `docker-compose` (app + db, Bind-Mounts), FastAPI-Gerüst, Alembic, SvelteKit-SPA mit Layout & Routing, OpenAPI→TS-Typen, ruff/pytest/vitest, Ollama installieren + `qwen3:14b` auf der GPU testen | 7 h | `docker compose up` → leere SPA, Healthcheck grün (inkl. Ollama erreichbar), DB überlebt Neustart |
| **M1** | Profil, Dokumente, LLM-Schicht | `LLMProvider` + Ollama inkl. `generate_structured`, Upload/Verwaltung, PDF-Text, `skills.yaml` (Start: ~150 Web-/Dev-Skills), CV-Extraktion + Validierung, Profil-Formular inkl. Skill-Gewichtung, Orte/Radius, Remote, Sprachen, Diff bei erneutem Auslesen | 16 h | Eigener CV hochgeladen → Profil ≥ 90 % korrekt vorbefüllt, Rest editierbar |
| **M2** | Quelle BA + Pipeline | Spike BA-API (inkl. Detail-Endpunkt) **und** Kurz-Check aller MVP-Quellen aus §5.1 (Adzuna, Arbeitnow, service.bund.de-RSS, je 2–3 echte Firmen pro ATS, GitHub-/Wikidata-Abfrage), `JobSource`-Plugin-Interface, BA-Client, Suchbegriff-Ableitung, Normalisierung, GeoNames-Import, Dedup, `search_runs` mit Fortschritt | 12 h | Suchlauf-Button liefert BA-Stellen in der DB, ohne Duplikate |
| **M3** | Matching & Tagesliste | Harte Filter, Score, Breakdown, Dashboard, Detailseite, „neu/gesehen“, Volltext einfügen + Neubewertung | 12 h | **Erstes Erfolgskriterium prüfbar**: Top 10 manuell bewerten |
| **M4** | Weitere Quellen & Abdeckung | Adzuna, Arbeitnow, service.bund.de; Tabellen `companies`/`user_companies`/`source_settings`; Discovery aus Treffern, GitHub, Wikidata; Erkennung Karriereseite + ATS; Adapter Personio/Greenhouse/Lever/Recruitee/SmartRecruiters/Workday mit Fixtures; JSON-LD + Sitemap; Vorfilter Ort/Remote; Firmen-Ansicht; Quellen an/aus + Statistik je Quelle; Abdeckungs-Check (Tabelle, Abgleich, Ansicht) | 20 h | ≥ 50 Firmen mit erkanntem ATS/JSON-LD auf der Watchlist, deren Stellen erscheinen **mit Volltext** gerankt in der Liste; **Abdeckungsmessung durchgeführt**, Zielwert ≥ 70 % |
| **M5** | Anschreiben & Paket | Anschreiben-Prompt, Stichpunkt-Prüfung, Editor mit Revisionen, PDF-Template, Paket/ZIP, Kopierhilfe, Bewerbungsliste mit Status | 13 h | Zusage → editierbares Anschreiben → Paket mit 3+ PDFs |
| **M6** | Puffer & Feinschliff | Fehlerfälle (Ollama nicht erreichbar, Quelle/Feed nicht erreichbar), Tuning der Score-Gewichte am echten Datenbestand, README | 6 h | Eine Woche Eigennutzung ohne Blocker |

**Gesamt: ~86 h.** Wenn es eng wird, zuerst kürzen: Workday-Adapter und Wikidata-Discovery (M4), Revisionshistorie (M5), CV-Diff (M1), Fuzzy-Dedup (nur Fingerprint).

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
- Verfügbarkeit/Format des BA-Detail-Endpunkts (Spike M2)
- Ob alle MVP-Quellen (Adzuna, Arbeitnow, service.bund.de-RSS, ATS-Endpunkte, GitHub, Wikidata) wie in §5.1 antworten, inkl. Limits und Nutzungsbedingungen (Spike M2)
- Adzuna-API-Key und ggf. GitHub-Token beantragen
- Kontaktadresse für den User-Agent (N6)
- Layout/Design des Anschreiben-PDFs (eigene Vorlage vorhanden?)
- Feintuning der Score-Gewichte nach den ersten echten Läufen
