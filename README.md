# Tessera

Agentic course scheduling for the AUB EECE department (EECE 503P, Fall 2026).
Team: Mohamad El Ajouz, Taha Fayed, Adam Hijazi.

> Status: setup in progress. Sections marked TODO are filled in by the Jira task named next to them.

## What it does

Tessera helps the department's scheduling staff build, check, repair and approve a clash-free term schedule.
A deterministic solver (CP-SAT) places every meeting and an independent validator re-checks every hard rule;
an LLM agent turns notes into typed constraints, explains conflicts and proposes relaxations;
humans approve every constraint, relaxation and publication. The LLM never places a meeting.

## Repository layout

| Path | Contents |
|---|---|
| `backend/` | Python package `tessera`: `api`, `agent`, `solver`, `validator`, `data`, `observability`; settings in `tessera/config.py` |
| `frontend/` | React + TypeScript interface (Vite, Tailwind, TanStack Query); typed API client in `src/api/` |
| `eval/` | Evaluation harness and runners (TODO: plan task T-110, not yet in Jira) |
| `spikes/` | Time-boxed technical experiments (SPIKE-1 to SPIKE-4) and their results |
| `data/` | Synthetic data only. Raw department data is never committed (see `data/README.md`) |
| `reports/` | Committed evaluation and metrics reports, each with its method and versions |
| `docs/` | Architecture, API, decisions (`docs/decisions/`) and workflow evidence (`docs/evidence/`) |

## Setup

TODO: full setup and reproduction guide: plan task T-137, not yet in Jira.

### Backend

You need [uv](https://docs.astral.sh/uv/). It installs Python 3.12 for you.

| Step | Windows (PowerShell) | macOS / Linux |
|---|---|---|
| Install uv (once) | `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Go to the backend | `cd backend` | `cd backend` |
| Install the locked dependencies | `uv sync` | `uv sync` |
| Create your settings file | `Copy-Item .env.example .env` | `cp .env.example .env` |

Then edit `backend/.env`: set `DATA_DIR` and `JWT_SECRET_KEY`. `DATABASE_URL` can stay as it is for development.
Generate the key with `uv run python -c "import secrets; print(secrets.token_urlsafe(32))"`.
The app refuses to start if a required setting is missing or empty, and the error names the setting.

The commands below are the same on every system, run from `backend/`:

| Task | Command |
|---|---|
| Create or update the database | `uv run alembic upgrade head` |
| Run the API (reloads on save) | `uv run uvicorn tessera.main:create_app --factory --reload` |
| Check it is up | open <http://127.0.0.1:8000/health>, which returns `{"status":"ok"}` |
| Run the tests | `uv run pytest` |
| Lint and format check | `uv run ruff check` and `uv run ruff format --check` |

### Database

The database is a single SQLite file, `backend/tessera.db` by default (see `DATABASE_URL`). It is git-ignored,
and there is no server to install. Why SQLite: [`docs/decisions/2026-11-14-database-sqlite.md`](docs/decisions/2026-11-14-database-sqlite.md).

- **Start fresh:** delete the `.db` file, then run `uv run alembic upgrade head`.
- **Change the tables:** edit the models in `tessera/`, then run `uv run alembic revision --autogenerate -m "what changed"`.
  Review the new file in `migrations/versions/`, then run `uv run alembic upgrade head`.
- **Real department data:** point `DATABASE_URL` at a file outside the repository, e.g. `sqlite:///C:/tessera-data/tessera.db`
  (Windows) or `sqlite:////home/you/tessera-data/tessera.db` (macOS / Linux, four slashes for an absolute path).

### Frontend

You need [Node.js](https://nodejs.org/) 22.12 or newer (it includes npm). The commands are the same on every system, run from `frontend/`:

| Task | Command |
|---|---|
| Install the locked dependencies | `npm ci` |
| Run the app (reloads on save) | `npm run dev`, then open <http://localhost:5173> |
| Lint | `npm run lint` |
| Typecheck | `npm run typecheck` |
| Production build | `npm run build` |
| Regenerate the typed API client | `npm run generate:api` (the backend must be running) |

The page calls the backend's `/health` and shows the result. For that to work:

- the backend must be running on <http://127.0.0.1:8000>. Use another address by setting `VITE_API_BASE_URL` in `frontend/.env.local`;
- the backend must allow the frontend's origin: `CORS_ALLOWED_ORIGINS=["http://localhost:5173"]` in `backend/.env`, as in `.env.example`.

**Typed API client.** `src/api/schema.d.ts` is generated from the backend's OpenAPI schema with
[openapi-typescript](https://openapi-ts.dev/), and `src/api/client.ts` calls the API through
[openapi-fetch](https://openapi-ts.dev/openapi-fetch/). A wrong path, parameter or response field is then a compile error.
Run `npm run generate:api` after every backend API change, and commit the regenerated file.
The generator runs through `npx` with its own TypeScript 5.9, because it needs TypeScript's older JavaScript API, which TypeScript 7 no longer has. The app itself uses TypeScript 7.

**Linter.** The frontend uses oxlint, not ESLint. Why: [`docs/decisions/2026-11-14-frontend-linter-oxlint.md`](docs/decisions/2026-11-14-frontend-linter-oxlint.md).

## Data policy

- Raw department files live only in the team's shared drive. They are never committed, because git history is permanent.
- The code reads the data location from configuration (environment variable), never from a path inside this repository.
- Synthetic data in `data/synthetic/` is labeled synthetic and records its seed and parameters.
- No student-identifying data is stored or sent to an LLM. Instructor names are pseudonymized before any LLM call.

## License

TODO: the repository is public; the team chooses a license before the first external share.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the Jira–GitHub workflow, naming conventions and the definition of done.
