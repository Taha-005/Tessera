# Database: SQLite with SQLAlchemy and Alembic

**Date:** 2026-11-14 · **Decided by:** Taha Fayed · **Task:** TESS-13 (T-007)

## Question

Which database and migration setup should Tessera use? The agreed stack named PostgreSQL, run locally in Docker, with Alembic.

## What the database must support (from the Jira tasks)

- T-017: tables for the domain entities, created by a migration that applies cleanly.
- T-018: schedule versions that cannot be modified and an audit log whose rows cannot be updated or deleted, proven by tests.
- T-019: a transactional import, where a failure halfway leaves no partial write.
- T-021: the instructor pseudonym mapping is stored in the database.
- A few department staff as users, one term of data, three developers on Windows and macOS, and a demo on Nov 24.

## Options considered

| Option | Verdict |
|---|---|
| **SQLite + SQLAlchemy + Alembic** | **Chosen.** Nothing to install, no database service in CI, the demo runs on any laptop. Meets T-017 (migrations), T-018 (triggers reject updates and deletes), T-019 (transactions). Writes are serialized, which is fine for a few users. |
| PostgreSQL (Docker) + SQLAlchemy + Alembic | Runner-up. Most robust; database permissions could also enforce T-018. Costs Docker on every machine, a database password and a CI service container. Choose it if Tessera must run as a real multi-user service. |
| SQLite without Alembic | Rejected. T-017 needs a migration, and every schema change would mean deleting the database, including the audit log. |
| Hosted PostgreSQL (Neon, Supabase) | Rejected. Accounts for every developer, internet needed for the demo, and department data on a third party's servers (conflicts with D-13). |
| PostgreSQL installed natively | Rejected. Docker's complexity plus separate installs and version drift across Windows and macOS. |
| Plain files (JSON/CSV) | Rejected. No transactions (fails T-019), no referential checks, immutability and audit would be hand-built. |

## Decision

SQLite, accessed only through SQLAlchemy, with Alembic migrations. Three SQLite settings live in `backend/tessera/data/db.py`
and `backend/migrations/env.py`: foreign keys are switched on for every connection, connections may be shared across
FastAPI's threads, and migrations use Alembic's batch mode (SQLite can't change most table definitions in place).

Moving to PostgreSQL later is mostly a different `DATABASE_URL` plus re-running the migrations; any SQL triggers would need rewriting.

## Proposed entry for the project document

- **Section 25 (Decision Log), D-xx:** Use SQLite (via SQLAlchemy, with Alembic migrations) instead of PostgreSQL for development, CI and the demo. Reason: no setup for three developers, no CI database service, and every database requirement of T-017, T-018 and T-019 is still met. Revisit if Tessera must run as a multi-user service.
- **Tech-stack section:** replace "PostgreSQL" with "SQLite".
