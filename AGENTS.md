# AGENTS.md

Working contract for `rust-style-guide-audit` — an audit CLI and agent skill that checks
Rust code against the [Google Rust Style Guide](https://google.github.io/styleguide/rustguide.html)
and turns findings into reviewable refactors.

## Purpose

Ship two artefacts from one rule set:

1. `SKILL.md` — an agent skill (Agent Skills spec) that runs a 7-step audit workflow.
2. `scripts/audit.py` — a dependency-free checker implementing the mechanical rules.

The rule set is the product. The guide is the authority; this repository encodes it, adds a
fix per rule, and separates what a script can decide from what needs judgement.

## Ownership

| Surface | Owner |
|---|---|
| `SKILL.md`, `references/rules-catalog.md` | The rule set — one row per rule ID, all 66 |
| `references/refactoring-playbook.md` | How a finding becomes a proposal |
| `scripts/audit.py` | Mechanical detectors (51 rules) |
| `scripts/self_test.py`, `scripts/fixtures/violations.rs` | Detector regression pins |
| `tests/` | pytest surface over the same groups plus catalog/script drift |
| `.config/mise/` | Tool pins, tasks, skill-install CSVs |

## Local contracts

- **Rule IDs are stable.** `API-01`, `ICN-03`, … appear in audit output, suppressions, in
  `EXPECT_VIOLATIONS`, and in the catalog table. Renaming one is a breaking change: add a new
  ID and retire the old one in the same commit, with the catalog row moved.
- **Catalog and script must not drift.** Every `rule(...)` call in `scripts/audit.py` needs a
  catalog row, and vice versa. `tests/test_audit.py::test_every_rule_is_documented` enforces it.
- **A false positive is a bug.** A detector fires on the construct the guide names, not on a
  nearby shape. When one is found, tighten it, add the non-firing case to `MUST_NOT_FIRE_AT`,
  and record the gap in Appendix B of the catalog if it cannot be closed.
- **The script never writes.** No source edits, no cargo invocation, no network. Its only
  side effect is the exit code (`--fail-on`, default `error`).
- **Stdlib only in shipped scripts.** `scripts/*.py` carry PEP 723 headers with
  `dependencies = []` so `uv run scripts/audit.py` works in any checkout.
- **Severity and scope are load-bearing.** `error` = hard prohibition or correctness defect;
  `warning` = the guide says "prefer"/"avoid"; `note` = style and judgement. `library` scope
  rules are binding only under `--kind library`; `chrome`/`fuchsia` only under
  `--codebase chrome|fuchsia`.
- **Judgement rules stay manual.** The 15 rules in `--list-manual` must never be turned into
  regexes to look thorough; they are printed as a checklist with every report.

## Work guidance

- Changing a detector: fixture line → `EXPECT_VIOLATIONS` → (if needed) `MUST_NOT_FIRE_AT` →
  detector → `mise run check`.
- Prefer a narrow detector with a documented gap over a broad one that fires on neighbours.
  The check-then-unwrap vs match-guard split (`ICN-02` / `ICN-03`) exists because the broad
  version produced four false errors.
- Keep `SKILL.md` under ~300 lines: it is loaded into an agent's context on every invocation.
  Detail belongs in `references/`.
- Cite the guide's section heading verbatim in the catalog row — that is how a finding is
  traced back, and it is the only defence against encoding an opinion as a rule.
- Do not add a tool without a mise pin, a task, and a line in the README's development section.
- Commits are conventional (`feat(detector):`, `fix(catalog):`, `docs(readme):`).

## Verification

`mise run check` is the gate: ruff, rumdl, ty, pytest (9 cases) and `scripts/self_test.py`
(5 regression groups). `mise run fmt` writes; never commit with `check` red.

Skill frontmatter: `uvx --from skills-ref agentskills validate .` from this directory.

## Child DOX index

None yet. Add a child AGENTS.md when a subdirectory acquires its own durable contract (for
example `scripts/` if the detector architecture grows beyond one module).
