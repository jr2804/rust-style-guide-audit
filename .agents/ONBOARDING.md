# AGENTS.md — ONBOARDING

Read this when starting a new session. After first read, only revisit when
project structure or tooling changes significantly.

## Project

An audit CLI and agent skill that checks Rust code against the
[Google Rust Style Guide](https://google.github.io/styleguide/rustguide.html) and turns
every finding into a reviewable refactor proposal. Full docs at `README.md`.

## Quick start

```bash
mise install          # pins uv, bun, ruff, ty, rumdl, skills-ref, ripgrep, tree-cli
mise run sync         # dev virtualenv for the tests (ruff/ty/pytest)
mise run check        # the gate: lint, lint-md, typecheck, pytest, self test
mise run fmt          # writes: ruff --fix, ruff format, rumdl fmt
mise run audit PATH   # run the checker, e.g. `mise run audit crates/`
```

## Entry points (read these first)

| File | Why |
|------|-----|
| `AGENTS.md` | Root rail — rules + `.agents/` index + child DOX index |
| `.agents/POLICIES.md` | Boundaries, priorities, verification, DOX authoring |
| `.agents/FILES.md` | Source of truth for rule IDs, fixtures, versions, task config |
| `skills/rust-style-guide-audit/AGENTS.md` | Child contract for the shipped skill folder: detectors, fixtures, release tooling |

## Where things live

| Surface | What it holds |
|---------|---------------|
| `skills/rust-style-guide-audit/SKILL.md` | The agent skill: invocation, 7-step workflow, report shape (≤ ~300 lines) |
| `skills/rust-style-guide-audit/references/rules-catalog.md` | All 66 rules: guide section, severity, scope, rationale, fix |
| `skills/rust-style-guide-audit/references/refactoring-playbook.md` | How a finding becomes a reviewable proposal |
| `skills/rust-style-guide-audit/scripts/audit.py` | Mechanical detectors (51 rules), stdlib only, never writes |
| `skills/rust-style-guide-audit/scripts/fixtures/violations.rs` | One construct per detectable rule, pinned to exact lines |
| `skills/rust-style-guide-audit/scripts/self_test.py` | 5 regression groups: firing, false positives, suppressions, scope |
| `skills/rust-style-guide-audit/scripts/release.py` | CalVer stamp, importable ZIP, tag and GitHub release |
| `tests/` | pytest surface over the same groups plus catalog/script drift |
| `.config/mise/` | Tool pins, task definitions, skill-install CSVs |

## Where to dig deeper

- `.agents/TOOLS.md` — tools, skills, CLIs and the project's mise tasks
- `.agents/HISTORY.md` — past decisions and the alternatives that lost
- `.agents/MAINTENANCE.md` — how to keep the `.agents/` files current
- `skills/rust-style-guide-audit/AGENTS.md` — detector architecture and the regression-pin workflow

## Available tools

Development tools, MCP servers, skills, and CLIs are inventoried in the
state file `.agents/TOOLS.md` — read it before assuming a tool, update it
when tooling changes. If tooling grows large, detail moves to
`.agents/tools/<name>.md` (each listed in TOOLS.md).
