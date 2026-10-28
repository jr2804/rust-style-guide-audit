# AGENTS.md — POLICIES

Always applicable. Boundaries, priorities, verification, checklist.
Detail lives in the subdirectory files indexed below.

## Priorities

1. Correctness
2. Evidence
3. Safety
4. Minimal changes
5. Consistency
6. Performance

## Boundaries

- NEVER fabricate paths, commits, APIs, config keys, env vars, test results,
  or benchmark numbers. If you don't know, say so.
- NEVER guess at command names, flags, or paths. Read source or run `--help`.
- NEVER add secrets, API keys, or tokens to files. Use env vars.
- NEVER run destructive commands (`rm -rf`, `git reset --hard`,
  `git push --force`) without explicit confirmation.
- NEVER delete or move files without explicit instruction.
- NEVER create temp files in project root. Use `tmp/` (gitignored).

## Change constraints

- Minimal, surgical edits. Preserve existing style.
- No new dependencies without explicit instruction.
- No unrelated refactoring while fixing a bug.
- Do not commit. The owner groups changes into logical commits and treats a
  commit as a milestone requiring approval.

## Code quality

Universal defaults. Project-specific standards live in child AGENTS.md.

- **SRP** — one reason to change per module/function.
- **DRY** — check before adding. Extract on third occurrence (Rule of Three).
- **Redundant code** — remove dead branches, unreachable conditions, unused
  params/imports before finishing.
- **Duplication vs. abstraction** — prefer duplication over wrong premature
  abstraction.
- No new code-quality tooling by default — opt in per project.

## Completion checklist

- Change solves the stated problem
- Relevant validation ran (or gaps stated)
- No unintended side effects or secrets exposed

## Verification

The gate is `mise run check` — see `.agents/TOOLS.md` → *Project scripts &
tasks* for what it runs and root `AGENTS.md` → *Verification* for the
project-specific caveats (release stamping, skill frontmatter validation).

- Never commit or push with `check` red.
- A detector change is only valid once the fixture pin *and* the
  non-firing case both pass — see `skills/rust-style-guide-audit/AGENTS.md`.

## Response format

Concise and specific. No filler, intros, or restated requirements.
Answer direct questions directly.

For review/debugging/analysis: findings with references, conclusion,
approach. Mention caveats.

## Subdirectory — `.agents/policies/`

| File | Covers |
| ---- | ------ |
| `dox-authoring.md` | **DOX authoring** (tier assignment, reference-don't-restate, rule-first rationale, content rules), **Size budget**, **State file subdirectories** |
| `plans-and-docs.md` | **Implementation Plans**, **Documentation**, archiving a completed plan |

Anything below is a pointer; the files above own the text.
