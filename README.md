# rust-style-guide-audit

An audit CLI and agent skill that checks Rust code against the
**[Google Rust Style Guide](https://google.github.io/styleguide/rustguide.html)** and turns
every finding into a reviewable refactor proposal.

It is built for the case a linter cannot cover: roughly half of the guide is about API
*design* — parameter types, trait choice, naming, ownership, error mechanisms — which no
compiler and no clippy lint will tell you about. This tool encodes those rules explicitly,
separates the ones a script can decide from the ones that need judgement, and walks an agent
(or a human) from finding to verified fix.

```text
# Rust Style Guide Audit

- Code kind: library, codebase: any
- Files scanned: 132
- Findings: 492 (error 2, warning 147, note 343)

## Findings by rule
| Rule   | Title                                                   | Severity | Count |
|--------|---------------------------------------------------------|----------|-------|
| SAF-06 | `#[non_exhaustive]` on public structs with public fields | note     | 84    |
| DOC-01 | Document public APIs                                     | warning  | 69    |
| NAM-05 | Avoid project-local abbreviations                        | note     | 56    |
| ...

### ERROR - ICN-02 Pattern matching over check-then-unwrap
`crates/core/src/alignment/prealignment_fast.rs:743` - check-then-unwrap
```

## Credits

The rule set is a faithful encoding of the **Google Rust Style Guide**:
<https://google.github.io/styleguide/rustguide.html>. That document is the authority — the
catalog here paraphrases it, quotes its section headings verbatim so a finding can be traced
back, and adds a fix for each rule. Where this repository and the guide disagree, the guide
wins; open an issue.

The guide's text is Google's, published under
[CC BY 3.0](https://creativecommons.org/licenses/by/3.0/). This repository's code and its own
prose are MIT (see [LICENSE](LICENSE)). Nothing here is endorsed by or affiliated with
Google.

## What it does

- **66 rules** across code organization, imports, formatting, ownership, function
  I/O, types, traits, concurrency, macros, naming, documentation, safety, implementation
  concerns and tests.
- **51 mechanical rules** are checked by a dependency-free Python script. Every one carries a
  stable ID (`API-01`, `ICN-03`, …), a severity, and a scope so `library` code can be held to
  API rules that `application` code is not.
- **15 judgement rules** are printed as a checklist with the report, because no regex decides
  whether a trait exists for a reason or whether a type should be `Copy`.
- **False positives are treated as bugs.** Detectors are shaped so they fire on the construct
  the guide names, not on a nearby shape; the regression suite pins each detector to an exact
  fixture line and pins the *non*-firing cases too.
- **The report is the deliverable.** Findings are grouped by rule with a summary table, then
  listed with `path:line`, the offending source line, and the fix.

## Install

### As an agent skill

```bash
bun x skills add jr2804/rust-style-guide-audit -a universal -y
```

That installs into `~/.agents/skills/rust-style-guide-audit`, where Claude Code, pi, Cursor and
other agents pick it up. Invoke it as `/skill:rust-style-guide-audit <paths>`, or just ask for a
Rust style review — the skill description carries the trigger words.

### As a one-off script

`scripts/audit.py` declares its own PEP 723 metadata and imports only the standard library, so
`uv` can run it straight from a checkout with no environment. The skill lives in
`skills/rust-style-guide-audit/`, which is the layout skill discovery expects:

```bash
uv run skills/rust-style-guide-audit/scripts/audit.py path/to/crate
```

### With mise

```bash
git clone https://github.com/jr2804/rust-style-guide-audit
cd rust-style-guide-audit
mise install      # uv, ruff, ty, rumdl, skills, ripgrep, ...
mise run sync     # dev virtualenv for the tests
```

## Usage

```bash
uv run skills/rust-style-guide-audit/scripts/audit.py <paths...> [options]
```

| Option | Meaning |
|---|---|
| `--kind library\|application` | `library` (default) makes API rules binding; `application` makes them advisory. |
| `--codebase any\|chrome\|fuchsia` | `chrome` enables the Chrome-only rules, `fuchsia` the Fuchsia ones. |
| `--format md\|json` | Markdown report (default) or a machine-readable payload. |
| `--out PATH` | Write the report to a file instead of stdout. |
| `--fail-on error\|warning\|note\|never` | Exit status gate; default `error`. |
| `--max-per-rule N` | Cap findings per rule (default 25) so one systemic rule cannot bury the rest. |
| `--disable IDS`, `--only IDS` | Comma-separated rule IDs. |
| `--exclude DIRS` | Directory names to skip. |
| `--root PATH` | Root for the relative paths in the report. |
| `--width N` | Report wrap width (default 100). |
| `--list-rules`, `--list-manual` | Print the catalog, or only the judgement rules. |

The script never edits source and never runs cargo. Its only side effect is the exit code.

### Report shapes

Markdown is for humans: a summary table, then one section per severity with the snippet and
the fix.

JSON is for tooling:

```json
{
  "roots": ["crates"],
  "kind": "library",
  "codebase": "any",
  "files_scanned": 132,
  "counts": { "error": 2, "warning": 147, "note": 343 },
  "findings": [
    {
      "rule": "ICN-02",
      "title": "Pattern matching over check-then-unwrap",
      "severity": "error",
      "path": "crates/core/src/x.rs",
      "line": 743,
      "message": "check-then-unwrap",
      "snippet": "let n = next.unwrap();",
      "fix": "Bind both values in the arm pattern ..."
    }
  ]
}
```

### Suppressing a finding

```rust
// style-guide-audit: ignore API-05 — flag name `set_visible` is unambiguous at call sites
// style-guide-audit: file-ignore NAM-05 — DSP vocabulary, defined in docs/glossary.md
```

Always give a reason. A suppression is also how you record a **false positive** — that is the
signal the detector needs tightening.

## The workflow the skill follows

1. **Scope** — library or application? Chrome/Fuchsia or standalone? Is there an existing
   `rustfmt.toml`/clippy config that already gates formatting?
2. **Scan** — run the script, markdown for reading, JSON for grouping.
3. **Verify each finding** — open `path:line`, read the whole item, and decide *real*,
   *intentional* (suppress with a reason), or *script bug*. A finding you cannot justify by
   quoting a guide section is not a finding.
4. **Answer the manual checklist** — the 15 judgement rules, each with a verdict and a pointer.
5. **Draft proposals** — current snippet, guide reason, proposed snippet, call-site impact
   count, risk, verification command.
6. **Sequence and gate** — formatting → signatures → renames → error handling → types and
   traits → ownership → suppressions. Never mix a rename with a logic change. Gate with
   `cargo fmt --all --check`, `cargo clippy --workspace --all-targets -- -D warnings`,
   `cargo test --workspace`, plus a behaviour gate when the change is numeric or public.
7. **Report** — Summary → Blocking → Should fix → Consider → Suppressions recommended →
   Mechanical pass available → Not mechanically checkable.

## Layout

```text
skills/rust-style-guide-audit/          the skill folder — what the ZIP wraps
  SKILL.md                      the agent skill: invocation, workflow, report shape
  references/rules-catalog.md   all 66 rules: guide section, severity, scope, rationale, fix
  references/refactoring-playbook.md   how to turn a finding into a reviewable refactor
  scripts/audit.py              the checker (stdlib only, PEP 723)
  scripts/self_test.py          regression groups: firing, false positives, suppressions, scope
  scripts/fixtures/violations.rs  one construct per rule, pinned to exact line numbers
  scripts/release.py            CalVer stamp, importable ZIP, tag and GitHub release
  AGENTS.md                     the working contract for that folder
tests/test_audit.py             the same groups as pytest cases, plus catalog/script drift
tests/test_release.py           version derivation and archive layout
.config/mise/                   tool pins, tasks, and the skill-install CSVs
.config/rumdl.toml, ruff.toml, ty.toml   linter configs
.githooks/pre-push              refuses a push that is not stamped for its commit
AGENTS.md                       the working contract for this repository
```

## Development

```bash
mise run check       # lint + markdown lint + typecheck + pytest + self test
mise run fmt         # ruff (imports, format) + rumdl
mise run audit crates
mise run add-skills  # installs the skills listed in .config/mise/data/skills.csv
```

Tooling: [ruff](https://docs.astral.sh/ruff/) and [ty](https://docs.astral.sh/ty/) for Python,
[rumdl](https://github.com/rvben/rumdl) for Markdown, [mise](https://mise.jdx.dev/) to pin them
and run the tasks.

## Versioning and releases

There is no CI. One command does the whole release, locally, from the commit that is being
shipped:

```bash
mise run hooks     # once: core.hooksPath=.githooks
mise run release   # check → stamp → ZIP → commit → tag → push → GitHub release
```

**Versions are CalVer `year.month.release`**, taken from the commit's own date — never from the
clock and never from the day of the month. The first release in October 2026 is `2026.10.1`,
the next is `2026.10.2`, and November starts again at `2026.11.1`; the counter is read from the
`v<version>` tags that already exist. Because the year and month come from the commit, re-running
a release is a no-op instead of a bump.

`2026.10.1` is a valid PEP 440 version, so `pyproject.toml` and `VERSION` can hold the same
string the tag and the ZIP name do.

**The artefact is `dist/rust-style-guide-audit-<version>.zip`** — one top-level
`rust-style-guide-audit/` directory holding `SKILL.md`, `references/`, `scripts/` and the
licence files, which is the layout an importer expects. `mise run release` attaches it to the
GitHub release for the tag, so it can be downloaded and imported without cloning — take the
asset from the [releases page](https://github.com/jr2804/rust-style-guide-audit/releases), or

```bash
version=$(uv run skills/rust-style-guide-audit/scripts/release.py version)
curl -L -o skill.zip \
  "https://github.com/jr2804/rust-style-guide-audit/releases/download/v$version/rust-style-guide-audit-$version.zip"
unzip skill.zip -d ~/.agents/skills/
```

The dev surface (`tests/`, `.config/`, `AGENTS.md`) is deliberately not in the archive.

`mise run release-dry` stops after tagging; `mise run package` only rebuilds the ZIP;
`.githooks/pre-push` runs `scripts/release.py check` and refuses a push whose `pyproject.toml`
version does not match its commit, so an unstamped tree cannot reach `main`.

### Changing a detector

1. Add the construct to `skills/rust-style-guide-audit/scripts/fixtures/violations.rs`.
2. Add the expected line to `EXPECT_VIOLATIONS` in `skills/rust-style-guide-audit/scripts/self_test.py`.
3. If the rule must *not* fire on a neighbouring construct, add it to `MUST_NOT_FIRE_AT`.
4. Change `skills/rust-style-guide-audit/scripts/audit.py`.
5. `mise run check` — all five regression groups plus pytest must pass.

The check-then-unwrap trap is instructive: `if x.is_none() { … }` followed by `x.unwrap()`
elsewhere is a finding, while `x.unwrap()` inside a match guard is a different rule
(`ICN-03`), because `if let` cannot fix a guard. Getting that distinction wrong produced four
false errors before it was split.

### Known limits

The audit is text-pattern based. It does not expand macros, resolve types, or build a module
graph, so expect false negatives in macro-heavy code and false positives on generics. The
known gaps are listed in Appendix B of `skills/rust-style-guide-audit/references/rules-catalog.md`. Clippy is treated as a
complement, not a competitor: run both.

## License

MIT for the code and this repository's prose — see [LICENSE](LICENSE). The audited guide is
Google's, CC BY 3.0; [NOTICE](NOTICE) records what is quoted and from where.
