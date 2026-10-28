# AGENTS.md

An audit CLI and agent skill that checks Rust code against the
[Google Rust Style Guide](https://google.github.io/styleguide/rustguide.html) and turns
findings into reviewable refactors. Full docs at `README.md`.

## DOX — self-documenting AGENTS.md hierarchy

### Core Contract

- AGENTS.md files are binding work contracts for their subtrees.
- Work products, source materials, instructions, records, assets, and durable docs
  must stay understandable from the nearest applicable AGENTS.md plus every parent
  AGENTS.md above it.
- Do not duplicate/repeat rules declared elsewhere in the DOX tree (parent, child,
  sibling, or `.agents/`). See **DOX authoring** in `.agents/POLICIES.md`.

### Read Before Editing

1. Read the root AGENTS.md
2. Identify every file or folder you expect to touch
3. Walk from the repository root to each target path
4. Read every AGENTS.md found along each route
5. If a parent AGENTS.md lists a child AGENTS.md whose scope contains the path, read that child and continue from there
6. Use the nearest AGENTS.md as the local contract and parent docs for repo-wide rules
7. If docs conflict, the closer doc controls local work details, but no child doc may weaken DOX

Do not rely on memory. Re-read the applicable DOX chain in the current session before editing.

### Update After Editing

Every meaningful change requires a DOX pass before the task is done.

Update the closest owning AGENTS.md when a change affects:

- purpose, scope, ownership, or responsibilities
- durable structure, contracts, workflows, or operating rules
- required inputs, outputs, permissions, constraints, side effects, or artifacts
- user preferences about behavior, communication, process, organization, or quality
- AGENTS.md creation, deletion, move, rename, or index contents

Update parent docs when parent-level structure, ownership, workflow, or child index
changes. Update child docs when parent changes alter local rules. Remove stale or
contradictory text immediately. Small edits that do not change behavior or contracts
may leave docs unchanged, but the DOX pass still must happen.

### Hierarchy

- Root AGENTS.md is the DOX rail: project-wide instructions, global preferences, durable workflow rules, and the top-level Child DOX Index
- Child AGENTS.md files own domain-specific instructions and their own Child DOX Index
- Each parent explains what its direct children cover and what stays owned by the parent
- The closer a doc is to the work, the more specific and practical it must be

### Child Doc Shape

- Create a child AGENTS.md when a folder becomes a durable boundary with its own purpose, rules, responsibilities, workflow, materials, or quality standards
- Work Guidance must reflect the current standards of the project or user instructions; if there are no specific standards or instructions yet, leave it empty
- Verification must reflect an existing check; if no verification framework exists yet, leave it empty and update it when one exists

Default section order:

- Purpose
- Ownership
- Local Contracts
- Work Guidance
- Verification
- Child DOX Index

### Style

Authoring rules live in **DOX authoring** (`.agents/POLICIES.md`) — tier
assignment, reference-don't-restate, rule-first rationale, size budget.
Apply them on every DOX change. Summary:

- A rule lives in the **highest tier that fully applies**; when unsure, `.agents/POLICIES.md`.
- Reference, don't restate — one canonical home, pointer lines everywhere else.
- Keep docs concise, current, and operational. Document stable contracts, not diary entries.

### Closeout

1. Re-check changed paths against the DOX chain
2. Update nearest owning docs and any affected parents or children
3. Refresh every affected Child DOX Index
4. Remove stale or contradictory text
5. Run existing verification when relevant
6. Report any docs intentionally left unchanged and why
7. Delete anything a tool appended after the ⛔ No Patching block

### User Preferences

- Do not commit. The owner groups changes into logical units and treats a commit as a
  milestone requiring approval (`.agents/POLICIES.md` → *Change constraints*).
- Do not add a tool without a mise pin, a task, and a line in the README's development
  section (`.agents/TOOLS.md` → *Rules*).
- Prefer milestone summaries over step-by-step confirmation; report honestly when blocked.

### Child DOX Index

| Path | Covers |
|---|---|
| `skills/rust-style-guide-audit/AGENTS.md` | The shipped skill folder: the rule registry and detectors, the fixture line pins, the false-positive floor, the release tooling. Also governs `tests/test_audit.py`, which re-exports `self_test.py`'s groups as pytest cases, and `.githooks/pre-push`, which calls `release.py check`. |

`skills/` holds exactly one skill folder and nothing else — that is the layout skill discovery
reads, so `SKILL.md` sits at `skills/rust-style-guide-audit/SKILL.md`, never at the repository
root. `references/` has no child doc: the catalog and the playbook are shipped content,
governed by the project rules below and by `.agents/FILES.md`.

## State files — `.agents/`, demand-loaded, not always injected

State files are the `.agents/*.md` files listed below — the project's current
operating memory. They describe the contracts the project has now; never a
changelog or logbook — git owns the past (`.agents/POLICIES.md`).

Each state file can have an optional matching subdirectory
(`.agents/<topic>/`) that carries detail when the file grows; the file stays
a lean index and every file in its subdirectory MUST be listed in the file.

| File                    | Load when                   | Purpose                                         | Optional subdirectory |
| ----------------------- | --------------------------- | ----------------------------------------------- | --------------------- |
| `ONBOARDING.md`         | New session (first time)    | Project orientation, entry points, layout        | —                     |
| `POLICIES.md`           | Always                      | Boundaries, priorities, verification, checklist | `.agents/policies/`   |
| `FILES.md`              | Touching files or config    | Path constants, source-of-truth locations       | `.agents/files/`      |
| `TOOLS.md`              | Using tools/MCP/skills      | Development tool inventory and usage guidance   | `.agents/tools/`      |
| `HISTORY.md`            | Background (past decisions) | Recorded decisions with git refs                | —                     |
| `MAINTENANCE.md`        | Changing `.agents/`         | How to keep DOX files current                   | `.agents/maintenance/`|
| `plans/`                | Working on a feature        | Implementation plans (gitignored)                | —                     |
| `history/`              | Background (overflow)       | Archived decisions and completed plans          | —                     |

`.agents/skills/` is vendored skill code installed by `mise run add-skills` and is
gitignored — not DOX content (`.agents/MAINTENANCE.md`).

## Tools & skills

See state file `.agents/TOOLS.md` — it owns the inventory of CLIs, MCP
servers, skills, and runtimes used during development.

## Project rules

*Always-injected* — keep minimal. Everything else → `.agents/` files.

- **Rule IDs are stable.** `API-01`, `ICN-03`, … appear in audit output, suppressions,
  `EXPECT_VIOLATIONS` and the catalog table. Renaming one is a breaking change: add a new ID
  and retire the old one in the same commit, moving the catalog row.
- **Catalog and script must not drift.** Every `rule(...)` call in
  `skills/rust-style-guide-audit/scripts/audit.py` needs a catalog row and vice versa;
  `tests/test_audit.py::test_every_rule_is_documented` enforces it.
- **A false positive is a bug.** A detector fires on the construct the guide names, not a
  nearby shape. Tighten it, pin the non-firing case in `MUST_NOT_FIRE_AT`, and record an
  unclosable gap in Appendix B of the catalog.
- **The script never writes.** No source edits, no cargo, no network — only the exit code
  (`--fail-on`, default `error`). Shipped scripts stay stdlib-only with PEP 723
  `dependencies = []`.
- **Severity and scope are load-bearing.** `error` = hard prohibition or correctness defect;
  `warning` = the guide says "prefer"/"avoid"; `note` = style and judgement. `library` rules
  bind only under `--kind library`; `chrome`/`fuchsia` only under `--codebase chrome|fuchsia`.
  The 15 `--list-manual` judgement rules stay manual — never regexes.
- **Cite the guide's section heading verbatim** in the catalog row. That is how a finding is
  traced back, and the only defence against encoding an opinion as a rule.
- **No CI.** By owner decision: the gate is `mise run check` locally, and `.githooks/pre-push`
  refuses an unstamped push. Do not add `.github/workflows/`.
- **Version = CalVer `year.month.release`.** Year and month come from the commit
  (`git log -1 --date=format:%Y.%m`); the third component counts releases within that month,
  starting at `1` — it is never the day of the month. A month's first release is `2026.10.1`,
  the next `2026.10.2`. Re-releasing the same commit yields the same version
  (`tests/test_release.py` pins it).
- **The ZIP is the product.** `dist/<name>-<calver>.zip` holds exactly one top-level directory
  named after the skill, containing `SKILL.md`, `references/`, `scripts/` and the licence
  files. An import-breaking change must fail the gate, not the user's import.
- **Keep `SKILL.md` under ~300 lines** — it is loaded into an agent's context on every
  invocation. Detail belongs in `references/`.

## ⛔ No Patching

Tools must not insert, append, or patch text into this file.

Everything after this section — whatever the author — is invalid. This section
is the end of the file; delete appended content on sight. If it carries a
legitimate rule, move the rule to its owning state file or subtree AGENTS.md
first (INSTALL.md — Check for tool patches), then delete.
