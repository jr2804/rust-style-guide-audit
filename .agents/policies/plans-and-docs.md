# AGENTS.md — Plans and documentation

Detail file for `.agents/POLICIES.md`. It owns where plans live, the archive trigger, and the
rules for durable vs. mutable documentation.

## Implementation Plans

- Plans, refactoring plans, and design docs go in
  `.agents/plans/<YYYY-MM-DD>-<feature-name>/` — NOT under version control
  (gitignored).
- Name descriptively with phase-number prefixes so file order matches
  implementation order, e.g. `01-sub-feature.md`, `02-next-sub-feature.md`.
- NEVER commit plans to git. They are mutable working artifacts.
- The archive trigger is **plan completion**: archive the moment the work
  lands — don't wait for the next maintenance pass. Archive naming and
  procedure: see `.agents/HISTORY.md` → *Archive a plan*.
- Shipped docs (user-facing guides, API references) go in `docs/` and
  ARE committed. This repository keeps them in `README.md` and inside the
  skill folder (`skills/rust-style-guide-audit/SKILL.md` and its
  `references/`) instead — those ship in the release ZIP.

## Documentation

- When `.agents/HISTORY.md` grows too large, archive older entries to
  `.agents/history/`. Reference them from `.agents/HISTORY.md`.
- Completed plans (`.agents/plans/<YYYY-MM-DD>-<feature-name>/`) are durable
  once implemented: consolidate them into
  `.agents/history/<YYYY-MM-DD-plan-name>.md`, remove the plan directory, and
  reference the archive from `.agents/HISTORY.md`. The trigger is **plan
  completion** — archive when the work lands, not at a later maintenance pass.
- `.agents/history/` IS version-controlled (durable decision records).
- AGENTS.md and state files describe the project's current contracts — never
  append session notes, iteration logs, or changelogs; delete stale text
  instead. `.agents/HISTORY.md` is the only permitted exception and holds
  high-level decisions only.
