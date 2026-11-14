# Frontend linter: oxlint with TypeScript 7

**Date:** 2026-11-14 · **Decided by:** Taha Fayed · **Task:** TESS-14 (T-008)

## Question

The agreed stack names ESLint for the frontend. The current Vite template (Vite 8) ships TypeScript 7, the new native
compiler, and oxlint instead of ESLint. ESLint reads TypeScript through `typescript-eslint`, which only supports
TypeScript below 6.1. Which linter, and which TypeScript version?

## What the linter must do here

Catch mistakes the typecheck can't: above all React's hooks rules (a hook called inside an `if`), plus unused code and
fast-refresh mistakes. Type errors are caught separately by `tsc` (`npm run typecheck`).

## Options considered

| Option | Verdict |
|---|---|
| **oxlint + TypeScript 7** | **Chosen.** The template's own default: 1 dev dependency, a 7-line config, the current TypeScript. Covers the hooks rules. Younger tool; fewer type-aware rules. |
| ESLint + typescript-eslint + TypeScript 6.0 | Runner-up. Matches the stack word for word, mature type-aware rules, huge ecosystem. Costs 6 dev dependencies, a ~20-line config, and pinning TypeScript one major version back. |
| Biome (linter and formatter) | Not now. Works with any TypeScript and adds formatting, but neither the template nor the stack uses it, and no E1 task needs a formatter. |
| ESLint forced onto TypeScript 7 | Rejected. npm reports the combination as unsupported and "potentially broken". |
| No linter, typecheck only | Rejected. Fails TESS-14's "lint and typecheck pass" and loses the hooks rules. |

## Decision

oxlint with TypeScript 7. `npm run lint` runs oxlint and `npm run typecheck` runs `tsc -b`; TESS-11's `frontend` CI job
runs both, plus the build.

**Side effect:** the typed-client generator (openapi-typescript) also needs TypeScript's old JavaScript API, so
`npm run generate:api` runs it through `npx` with its own pinned TypeScript 5.9.3. It only produces a `.d.ts` type
file, which TypeScript 7 reads normally.

## Proposed entry for the project document

- **Section 25 (Decision Log), D-xx:** Use oxlint (with TypeScript 7) instead of ESLint for the frontend. Reason: it is
  the Vite template's default, needs one dependency and a 7-line config, and keeps the current TypeScript; ESLint's
  TypeScript support stops at TypeScript 6.0. Revisit if the team needs mature type-aware lint rules.
- **Tech-stack section:** replace "ESLint" with "oxlint".
