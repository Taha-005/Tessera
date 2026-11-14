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
| `backend/` | Python package: API, agent, solver, validator, data layer, observability (TODO: TESS-12) |
| `frontend/` | React + TypeScript interface (TODO: TESS-14) |
| `eval/` | Evaluation harness and runners (TODO: plan task T-110, not yet in Jira) |
| `spikes/` | Time-boxed technical experiments (SPIKE-1 to SPIKE-4) and their results |
| `data/` | Synthetic data only. Raw department data is never committed (see `data/README.md`) |
| `reports/` | Committed evaluation and metrics reports, each with its method and versions |
| `docs/` | Architecture, API, decisions (`docs/decisions/`) and workflow evidence (`docs/evidence/`) |

## Setup

TODO: TESS-12 (backend), TESS-13 (database), TESS-14 (frontend); full setup and reproduction guide: plan task T-137, not yet in Jira.

## Data policy

- Raw department files live only in the team's shared drive. They are never committed, because git history is permanent.
- The code reads the data location from configuration (environment variable), never from a path inside this repository.
- Synthetic data in `data/synthetic/` is labeled synthetic and records its seed and parameters.
- No student-identifying data is stored or sent to an LLM. Instructor names are pseudonymized before any LLM call.

## License

TODO: the repository is public; the team chooses a license before the first external share.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the Jira–GitHub workflow, naming conventions and the definition of done.
