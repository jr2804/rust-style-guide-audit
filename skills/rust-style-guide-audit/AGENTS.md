# AGENTS.md — skills/rust-style-guide-audit

## Purpose

The shipped skill folder. `SKILL.md` plus the `references/` it links to plus the `scripts/` it
tells an agent to run are the whole product; the release ZIP wraps this directory and nothing
else. Everything here ships except this file — `SKILL.md`, `references/`, `scripts/` (including
`scripts/fixtures/`, because `scripts/self_test.py` imports its line pins) and the repository
root's `LICENSE`, `NOTICE` and `README.md`, which the packager copies in.

Standard library only, PEP 723 headers with `dependencies = []`, so
`uv run skills/rust-style-guide-audit/scripts/audit.py` works in any checkout.

The folder name is the skill name: the Agent Skills validator compares the frontmatter `name`
with the directory's basename, so renaming either one alone breaks `mise run validate-skill`.
The layout `skills/<skill-name>/` is what `bun x skills add` and the Claude Desktop importer
discover; it is why `SKILL.md` is not at the repository root.

## Ownership

| Path | Owns |
|---|---|
| `SKILL.md` | The 7-step audit workflow, invocation, report shape, suppression syntax — ≤ ~300 lines, because it is loaded into an agent's context on every invocation |
| `references/rules-catalog.md` | One row per rule ID (all 66): verbatim guide section, severity, scope, rationale, fix, plus Appendix A (suppressions) and B (known gaps) |
| `references/refactoring-playbook.md` | How a finding becomes a reviewable proposal and the report skeleton |
| `scripts/audit.py` | The 51 mechanical detectors, the rule registry, the markdown/JSON renderer, the CLI |
| `scripts/self_test.py` | The line pins (`EXPECT_VIOLATIONS`, `MUST_NOT_FIRE_AT`, `FORBIDDEN`, `CLEAN_ALLOWED`) and the 5 regression groups |
| `scripts/fixtures/violations.rs` | One construct per detectable rule; its line numbers are load-bearing |
| `scripts/release.py` | CalVer derivation, `pyproject.toml`/`VERSION` stamping, the importable ZIP, tag and GitHub release |

Outside this folder but governed here: `tests/test_audit.py` re-exports the regression groups
as pytest cases and asserts catalog↔script drift; `tests/test_release.py` drives the release
tooling; `.githooks/pre-push` calls `scripts/release.py check`.

## Local contracts

- **Registry first.** A new detector starts with a `rule(...)` call in `scripts/audit.py` →
  *Rule registry*. Rule IDs are stable and every ID needs a row in
  `references/rules-catalog.md`; `tests/test_audit.py::test_every_rule_is_documented` fails on
  either-side drift.
- **`scripts/audit.py` never writes.** No source edits, no cargo, no network. Its only side
  effect is the exit code, gated by `--fail-on` (default `error`).
- **Line pins are the contract.** `EXPECT_VIOLATIONS` maps a rule to exact fixture lines;
  `MUST_NOT_FIRE_AT` pins the exceptions a whole-rule `FORBIDDEN` entry cannot express. Adding
  a construct means adding its line to the pin, not just the detector.
- **`FORBIDDEN` is the false-positive floor.** `check_clean_fixture` runs `CLEAN_FIXTURE`
  through the audit and requires zero findings outside `CLEAN_ALLOWED`; anything in
  `CLEAN_ALLOWED` needs a one-line justification.
- **Narrow over broad.** A detector fires on the construct the guide names, not on a nearby
  shape. A gap that cannot be closed goes to Appendix B of the catalog, not to a looser regex.
- **Test code is off-limits.** `SourceFile.is_test` marks `tests/`, `#[cfg(test)]` modules and
  everything after them; `check_violation_fixture` asserts nothing is flagged from the fixture's
  `#[cfg(test)]` line onward.
- **The renderer is a published interface.** `Finding.as_dict()` keys and the JSON top-level
  shape (`roots`, `kind`, `codebase`, `files_scanned`, `counts`, `findings`) are asserted in
  `tests/test_audit.py`; change them only with the consumers (agents parsing the report).
- **`scripts/release.py` ships, so it stays standalone.** Its own path is how it finds the two
  roots: `SKILL_ROOT` is this directory (what the ZIP wraps) and `ROOT` is the repository
  (where git, `pyproject.toml` and `dist/` live). CalVer's year and month come from the
  commit (`git log -1 --format=%cd --date=format:%Y.%m`), the third component is the release
  counter read from existing `v<year>.<month>.<n>` tags — never the clock, never the day of the
  month. `tests/test_release.py` drives every branch and inspects the real ZIP.
- **`__pycache__` is build residue**, gitignored. Never import from it, never pin anything to it.

## Work guidance

1. Fixture line in `scripts/fixtures/violations.rs` (keep the file ordered; adding a line shifts
   every pin below it — update the whole table in one pass).
2. `EXPECT_VIOLATIONS` entry.
3. `MUST_NOT_FIRE_AT` entry when the rule has an exception the fixture must pin.
4. The detector in `scripts/audit.py`, registered in `CHECK_ORDER` when it is a new check
   function.
5. Catalog row, cited with the guide's section heading verbatim.
6. `mise run check`.

- Check functions take `(sf, out)`; the four that need options take `(sf, out, kind)` or
  `(sf, out, codebase)` or `(sf, out, width)` and are dispatched by name in `run()` — a new
  function with a different signature needs its dispatch branch there.
- Detectors read `sf.code` (comments and literal bodies blanked, columns preserved) or
  `sf.narrow` (literals collapsed, for width checks). Reading `sf.raw` is only correct when the
  comment text itself is the subject (`DOC-01`, `SAF-01`).
- Suppressions are parsed in `SourceFile._parse_suppressions` and honoured in `suppression_for`;
  a new detector gets suppression handling for free by emitting through `out`.
- Keep `SKILL.md` under ~300 lines. Anything longer belongs in `references/`, linked from the
  step that needs it.

## Verification

`mise run check` covers this folder: `ruff`, `rumdl`, `ty`, `pytest` and
`scripts/self_test.py` (5 groups: violation fixture, clean fixture, suppressions, scope gating,
exit codes). `uv run skills/rust-style-guide-audit/scripts/self_test.py` alone is the fast loop
while shaping a detector. `mise run validate-skill` checks the `SKILL.md` frontmatter against
the Agent Skills specification.

## Child DOX index

| Path | Covers |
|---|---|
| `scripts/fixtures/` | No own contract — `violations.rs` is governed by this file's line pins. |
