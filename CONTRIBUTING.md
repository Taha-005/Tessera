# Contributing to Tessera

## Workflow

1. Every change starts from a Jira task. Move it to **In Progress** when you start.
2. Create a branch from `main` named after the task (see below).
3. Open a pull request early; move the task to **In Review** when it is ready.
4. Another team member reviews and approves. CI must be green.
5. Merge with **Squash and merge**, keeping the PR title (with its TESS key) as the squash commit title; move the task to **Done** only when its definition of done is met.

`main` is protected: no direct pushes, one approving review required, CI required once it exists (TESS-11).

## Naming conventions (Jira–GitHub linking)

Jira project key: `TESS`. The Jira issue key must appear in every branch name, commit message and PR title,
so the GitHub for Jira app links them to the task.

| What | Format | Example |
|---|---|---|
| Branch | `<type>/TESS-<n>-<short-slug>` | `feat/TESS-21-canonical-schema` |
| Commit | `TESS-<n> <type>: <imperative summary>` | `TESS-21 feat: add section and meeting models` |
| PR title | `TESS-<n> <Task summary>` | `TESS-21 Canonical term-data schema and file format` |

Types: `feat` (new behavior), `fix` (bug fix), `test` (tests only), `docs`, `spike` (time-boxed experiment),
`chore` (setup, tooling, dependencies), `refactor` (no behavior change).

One task per branch and per PR where possible. If a PR touches two tasks, put both keys in the title.

## Definition of done

A task is done when everything in its "Done when" line in Jira is true, and:

- tests cover the new behavior, including at least one failure or edge case;
- CI is green;
- a teammate reviewed and approved the PR;
- any decision it produced is written up in `docs/decisions/` and proposed for the project document;
- no raw department data, secrets or real credentials are in the diff.

## AI-assisted development (course guardrail G9)

AI coding tools are allowed. The author of a PR is responsible for understanding, testing and securing every line in it,
and must be able to explain it in review and in the demo Q&A. Generated code that is unused, unexplained or untested is not merged.

## Data and secrets

- Never commit raw department files, even temporarily; anything committed stays in git history.
- Secrets live in `.env` locally and in GitHub Actions secrets in CI. `.env.example` holds placeholders only.
- Synthetic data is labeled synthetic and records its seed and parameters.

## Evidence

Every number that appears in the report, slides or demo must come from a committed report in `reports/`
with its method and versions stated. Screenshots of workflow evidence go in `docs/evidence/`.
