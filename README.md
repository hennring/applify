# Applify

A personal job application assistant that runs entirely on your own machine. Applify
searches German job sources daily, ranks every posting against your profile with an
explainable score, and (from milestone M6 on) drafts a tailored cover letter with a local
LLM.

No personal data leaves your machine: requests to job sources carry only search terms and
places, your CV is read by a local model via [Ollama](https://ollama.com), and nothing is
ever sent or applied for automatically.

## Features

- **Profile from your CV** – upload a PDF; a local LLM fills in roles, skills, languages,
  experience and education. Everything stays editable; re-reading a CV shows changes as a
  diff.
- **Job search across sources** – Bundesagentur für Arbeit, Arbeitnow, Adzuna (free API
  key), service.bund.de, plus the careers pages of companies on your watchlist (Personio,
  Greenhouse, Lever, Recruitee, SmartRecruiters, Workday, JSON-LD). Fully remote jobs are
  searched Germany-wide.
- **Company discovery** – companies are collected from postings, GitHub organizations and
  Wikidata near your places; their careers page and ATS are detected automatically.
- **Deduplication** – the same job from several sources or under several reference
  numbers is merged into one entry.
- **Explainable ranking** – a score of 0–100 from skills, role, seniority, location and
  salary, with hits (✓), misses (✗) and unknowns (?) per component. Hard filters hide jobs
  outside your radius, below your minimum salary or matching your exclusions.
- **Daily list** – new jobs are marked, the detail opens beside the list, and short
  postings can be completed by pasting the full text.
- **Coverage check** – enter jobs you found elsewhere to measure what Applify misses and
  why.
- **Market analysis** – an ELT pipeline (Dagster + dbt) turns every search run into a
  dashboard with tabs: demanded skills and the gaps in your profile, typical tech stacks,
  experience, seniority, salaries and benefits per role family; which skills would bring
  you the most additional good matches; the largest employers and staffing agencies (with
  a filter to hide them); a map of the states; how long postings stay online and which
  skills rise or fall; and what each source contributes – always with how many postings
  actually state a value.

See [PLAN.md](PLAN.md) (German) for requirements, design decisions and the roadmap.

## Tech stack

| Part | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, managed with [uv](https://docs.astral.sh/uv/) |
| Database | PostgreSQL 16 with `pg_trgm` (Docker) |
| Frontend | SvelteKit (SPA) with Svelte 5, TypeScript, typed API client generated from OpenAPI |
| LLM | Ollama with `qwen3:14b` (configurable) |

## Requirements

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (for PostgreSQL, or the
  whole app)
- [Ollama](https://ollama.com/download) running natively, with the model pulled:
  `ollama pull qwen3:14b` (about 9 GB; a GPU with ≥ 12 GB VRAM is recommended)
- For development additionally: [uv](https://docs.astral.sh/uv/getting-started/installation/),
  Node.js 24 and pnpm (`corepack enable`)

## Quick start (Docker)

Runs database and app in containers; Ollama stays on the host.

```sh
cp .env.example .env          # optional: change the database password
docker compose up -d --build
```

Open <http://localhost:8000>. Data is kept in `./data/` (database and uploaded documents)
and survives restarts.

## Development setup

```sh
# Backend
cd backend
uv sync                              # creates .venv with all dependencies
uv run python -m applify.dev_setup   # starts the database container and migrates
uv run uvicorn applify.main:app --reload --port 8000

# Frontend (second terminal)
cd frontend
pnpm install
pnpm dev                             # http://localhost:5173, proxies /api to :8000
```

In IntelliJ / PyCharm the shared run configurations in `.run/` do the same: **Dev (all)**
starts database, migrations, backend and frontend. Select `backend/.venv` as the Python
interpreter first.

## Usage

1. **Check the status** – the start page (*Tagesliste*) shows whether database and Ollama are reachable.
2. **Create your profile** – under *Dokumente* upload your CV; the profile is filled in
   automatically. Review it under *Profil*: desired roles, skills (must / nice / avoid),
   places with radius, remote preference, minimum salary, exclusions. Save.
3. **Configure sources** (*Einstellungen*, optional)
   - Enter a contact address (mail or URL). It is sent in the User-Agent so operators can
     reach you, and Wikidata requires it.
   - Add an Adzuna app ID and key ([free](https://developer.adzuna.com)) and a GitHub token
     for more company discovery.
   - Switch off sources you do not want.
4. **Start a search run** – on the start page. A run takes a few minutes; progress and
   per-source statistics are shown, and the list fills while it runs.
5. **Work through the list** – sort by score or date, open a job to see the full text and
   the score breakdown. Opening marks it as seen. For short postings, paste the full text
   to get an accurate rating.
6. **Grow the watchlist** (*Firmen*) – add companies by their careers page URL, follow or
   ignore discovered ones. Followed companies with a detected feed are read on every run.
7. **Measure coverage** (*Abdeckung*, optional) – enter jobs you found on other portals
   and check which ones Applify found, and if not, why.

## Market analysis pipeline

The analytics project in `analytics/` is a separate uv project:

```
search run ──▶ raw.job_sightings / raw.job_versions      (append-only, written by the app)
Dagster    ──▶ features.job_features                     (rules, then the local LLM for gaps)
           ──▶ features.job_regions, skill_stacks         (state per job, frequent skill sets)
           ──▶ dbt build: staging → intermediate → marts  (with tests)
marts      ──▶ page "Markt" in Applify · Metabase (optional, read-only)
```

```sh
cd analytics
uv sync
DAGSTER_HOME=../data/dagster uv run dagster dev -m applify_analytics.definitions -p 3000
```

Open <http://localhost:3000> and run the job `market_pipeline` once; afterwards a sensor
starts it after every finished search run. In IntelliJ use the run configuration
**Analytics (Dagster)**. The LLM step needs the model in Ollama (`ollama pull qwen3:14b`)
and handles at most 50 postings per run (`llm_budget`). Run status sensors record each
pipeline run in `features.pipeline_runs`; the dashboard shows whether the analysis is
current, running, failed or still waiting for a newer search run.

The outlines of the German states (`analytics/resources/states.json` and the map paths in
`frontend/src/lib/viz/germanyStates.ts`) are generated from Natural Earth (public domain):
`uv run python -m applify_analytics.build_states`.

Optional BI tool: `docker compose --profile analytics up -d metabase`, then open
<http://localhost:3001> and connect to host `db`, database `applify`, user
`applify_reader` (password `APPLIFY_READER_PASSWORD`, default `applify_reader`). This role
can read the `marts` schema only.

## Configuration

Settings are read from environment variables (or `backend/.env`) with the prefix
`APPLIFY_`:

| Variable | Default | Purpose |
|---|---|---|
| `APPLIFY_DATABASE_URL` | `postgresql+psycopg://applify:applify@127.0.0.1:5432/applify` | Database connection |
| `APPLIFY_OLLAMA_URL` | `http://127.0.0.1:11434` | Ollama API |
| `APPLIFY_OLLAMA_MODEL` | `qwen3:14b` | Model for CV extraction and cover letters |
| `APPLIFY_HTTP_CONTACT` | – | Contact for the User-Agent; the value under *Einstellungen* takes precedence |
| `APPLIFY_HTTP_INTERVAL` | `1.0` | Seconds between two requests to the same host |
| `APPLIFY_HTTP_IPV4_ONLY` | `true` | Avoids long connect timeouts on networks without IPv6 |

API keys entered under *Einstellungen* are stored in the local database in plain text and
are never sent back to the browser.

## Development

```sh
# Backend: tests (need the database container), lint, types
cd backend
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy applify tests

# Frontend
cd frontend
pnpm lint
pnpm check
pnpm test

# After changing API models: regenerate the TypeScript types
pnpm gen:api

# Analytics: tests, lint, types, dbt models and tests
cd analytics
uv run pytest
uv run ruff check . && uv run mypy applify_analytics tests
uv run dbt build --project-dir dbt --profiles-dir dbt

# New database migration
cd backend
uv run alembic revision --autogenerate -m "describe the change"
```

## Fair use of job sources

Applify only uses public APIs and feeds, and the careers pages of individual companies.
It respects `robots.txt`, sends a User-Agent with a contact address, waits at least one
second between requests to the same host, and uses conditional requests (ETag) for feeds.
Job portals such as StepStone, Indeed or LinkedIn are not scraped.

## Status

Milestones M0–M4 (profile, CV extraction, job sources, matching, company discovery)
M5 (market analysis with an ELT pipeline and dashboard) and M5.1 (more tabs: profile fit,
employers, regions, dynamics, data quality) are implemented. Open: M6 (cover
letter and application package) and M7 (polish).
