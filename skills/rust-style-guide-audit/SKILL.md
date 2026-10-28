---
name: rust-style-guide-audit
description: >-
  Audit Rust code against the Google Rust Style Guide (google.github.io/styleguide/rustguide.html)
  and propose concrete refactors. Use when asked to check Rust code against the Google Rust style
  guide, run a Rust style/lint/antipattern audit, find violations of Google's Rust conventions,
  review a Rust crate for style-guide compliance, propose refactors toward Google-style Rust, or
  review Rust API design (parameter types, traits, naming, constructor names, error handling,
  ownership) against a published style guide. Trigger words: rust style guide, google rust style,
  rustguide, rust antipatterns, rust style audit, rust API design review, rust refactor toward
  style guide.
license: MIT
---

# Rust Style Guide Audit

Audit Rust source against the Google Rust Style Guide and turn findings into
reviewable refactors. Mechanically checkable rules come from
`scripts/audit.py`; judgement-based rules come from reading the code.

Guide under audit: <https://google.github.io/styleguide/rustguide.html>

## Invocation

Two entry points, same workflow:

| Invocation | Arguments | Behaviour |
|---|---|---|
| `/skill:rust-style-guide-audit <paths>` | paths, optional flags | Run steps 1–7 over the given paths. Defaults: `--kind library --codebase any`. |
| Automatic selection | — | Infer paths from the request; ask only if the target crate is ambiguous. |

Treat everything after the command as the scope. Recognise `library`/`application` and
`chrome`/`fuchsia` when the user names them and pass the matching flags. If the user
supplies only a crate name or a directory, resolve it with `rg --files -g 'Cargo.toml'`
before scanning.

The default deliverable is the step 7 report, printed — not a file. Write a file only
when the user asks for one. Change no source unless the user asks for the refactor; the
script never writes to source either.

**Script paths are relative to this skill's directory, not to the audited crate.** Run
`audit.py` and `self_test.py` from the skill directory, or give their absolute paths — a
project usually has its own unrelated `scripts/` folder, and `uv run scripts/audit.py`
resolved against the project root would pick that one up instead:

```bash
cd ~/.agents/skills/rust-style-guide-audit && uv run scripts/audit.py /path/to/crate
uv run ~/.agents/skills/rust-style-guide-audit/scripts/audit.py /path/to/crate
```

## Workflow

Run these steps in order. Do not skip step 2 — audit findings are claims, not facts.

### 1. Scope the audit

Establish three facts before scanning; the answers change which rules are binding:

| Question | Effect |
|---|---|
| Is this **library** or **application** code? | `--kind library` makes API rules (`API-01..06`, `DOC-01`, `TYP-01`, `TRT-07`) binding. `--kind application` treats them as advisory. |
| Is it a **Chrome/Fuchsia** codebase or standalone? | `--codebase chrome` enables `CON-02`/`CON-03`, plus the Chrome-only `ORG-01`/`ORG-02`. `--codebase fuchsia` enables `CON-04`. |
| Is there an existing `rustfmt.toml` / clippy config? | If yes, `FMT-01` measures against the configured width, and clippy findings are already the project's own gate. |

```bash
rg --files -g 'Cargo.toml' -g 'rustfmt.toml' -g '.clippy.toml' -g 'clippy.toml'
```

### 2. Scan

```bash
uv run scripts/audit.py <paths> --kind library --codebase any
uv run scripts/audit.py <paths> --format json --out tmp/style-audit.json
```

Useful flags: `--fail-on error|warning|note|never` (CI gate, default `error`),
`--max-per-rule` (default 25), `--disable RULE-ID`, `--only RULE-ID`, `--exclude dir`
(plus `--list-rules` and `--list-manual` to print the catalog and the manual checklist).

The script exits `1` when a finding at or above `--fail-on` exists — that is its only
side effect; it never edits code.

Read the JSON form when you need to group or count programmatically. Read the markdown
form when the report goes to a human.

### 3. Verify each finding

For every finding you intend to act on:

- Open `path:line` and read the whole item — function, impl, struct — not just the line.
- Decide: **real**, **intentional** (suppress with a reason), or **script bug** (note the
  rule ID and construct that fooled the checker).
- Drop findings that are artefacts of the heuristic. The known gaps are listed in
  `references/rules-catalog.md` Appendix B.

A finding you cannot justify by quoting the guide section is not a finding.

The script has its own regression check; run it after editing `scripts/audit.py`:

```bash
uv run scripts/self_test.py
```

It asserts that `scripts/fixtures/violations.rs` still produces the expected rule IDs and
that the clean fixture stays silent — a detector change that silently stops firing is
the failure mode worth guarding.

### 4. Answer the manual checklist

```bash
uv run scripts/audit.py <paths> --list-manual
```

These need judgement and are printed at the end of every report. Answer each with a verdict
and a `path:line` pointer, or "not applicable" and why:

- crate granularity (`ORG-01`), leaf-module naming (`ORG-03`)
- trait impl completeness (`TRT-01`), which traits a type should carry (`TRT-09`), trait
  necessity (`TRT-05`)
- failure-mechanism choice (`API-06`), parameter ergonomics (`API-03`), trait-import
  placement (`IMP-05`), Chrome import mechanism (`IMP-06`)
- lifetime/generic naming (`NAM-02`, `NAM-03`)
- `non_exhaustive` match arms (`ICN-09`), operator overloads (`SAF-10`), foreign
  `#[doc(hidden)]` items (`SAF-09`)
- test framework (`TST-01`)

### 5. Draft proposals

Follow `references/refactoring-playbook.md`. Minimum per proposal: current snippet,
guide reason, proposed snippet, call-site impact count, risk, verification command.
Cluster the mechanical work separately from the design work.

### 6. Sequence and gate

Order: formatting/imports → signature widening → renames → error handling → types and
traits → ownership redesign → suppressions. Never mix a rename with a logic change.

Gate before claiming done:

```bash
cargo fmt --all --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
```

Add a behaviour gate (bit-identical output comparison, benchmark delta, or
`cargo semver-checks`) whenever the change touches numeric results, performance, or a
public signature. State which gates ran and their results — "tests pass" alone is not a
report.

### 7. Report

Use the report skeleton in `references/refactoring-playbook.md` (Summary → Blocking →
Should fix → Consider → Suppressions recommended → Mechanical pass available → Not
mechanically checkable). Every entry carries `path:line` and a fix.

## Rule catalog

`references/rules-catalog.md` holds all 66 rules with the guide section, severity,
scope, rationale, and fix. Rule IDs are stable (`API-01`, `ICN-03`, …) and are the
vocabulary for findings, proposals, and suppressions.

Groups: code organization (`ORG`), imports (`IMP`), formatting (`FMT`), ownership
(`OWN`), function inputs/outputs (`API`), types (`TYP`), traits (`TRT`), concurrency
(`CON`), macros (`MAC`), naming (`NAM`), documentation (`DOC`), other features (`SAF`),
implementation concerns (`ICN`), tests (`TST`).

## Suppressing a finding

```rust
// style-guide-audit: ignore API-05 — flag name `set_visible` is unambiguous at call sites
// style-guide-audit: file-ignore NAM-05 — DSP domain vocabulary, defined in docs/glossary.md
```

Suppress with a reason, never silently. An unsuppressed false positive makes the next
run's signal worse.

## Scope limits

- The audit is text-pattern based: it does not expand macros, resolve types, or build a
  module graph. Expect false negatives in macro-heavy code and false positives on
  generics.
- The guide's Chrome-specific rules (`ORG-01`, `ORG-02`, `CON-02`, `CON-03`) are not
  applicable to ordinary crates; passing `--codebase chrome` on non-Chrome code
  produces noise.
- Clippy is treated as an extension of the guide. Run it alongside this audit rather
  than expecting the script to reproduce its lints.
- Rules the guide states as guidance for Chrome infrastructure (`rust_g` lints) are
  advisory everywhere else; say so when reporting them.
