# AGENTS.md — FILES

Single source of truth for paths, config keys, and naming conventions.
Kept compact — agents hallucinate less when they know where definitions live.

## Pattern

- One file owns each class of definition (paths, config defaults, enums).
- Import from that file. Never hard-code values in other modules.
- Variables that address files get `_file` suffix; directories get `_dir`.

## Project-specific sources of truth

| What | Where | Key names |
|------|-------|-----------|
| Shipped skill folder | `skills/rust-style-guide-audit/` | `SKILL.md`, `references/`, `scripts/` — the only thing the release ZIP wraps |
| Rule registry (the 51 mechanical + 15 manual rules) | `skills/rust-style-guide-audit/scripts/audit.py` → *Rule registry* | `RULES`, `rule(rid, title, section, severity, scope, manual=False)` |
| Rule documentation (all 66 rows) | `skills/rust-style-guide-audit/references/rules-catalog.md` | `\| ID \| Title \| Guide section \| …` table rows |
| Detector entry points | `skills/rust-style-guide-audit/scripts/audit.py` | `check_imports`, `check_api`, `check_traits`, `check_unsafe_and_attrs`, `check_impl_concerns`, `check_structure`, `run` |
| Fixture line pins | `skills/rust-style-guide-audit/scripts/self_test.py` | `EXPECT_VIOLATIONS`, `MUST_NOT_FIRE_AT`, `FORBIDDEN`, `GROUPS` |
| Fixture source (one construct per rule) | `skills/rust-style-guide-audit/scripts/fixtures/violations.rs` | line numbers are load-bearing |
| Version | `pyproject.toml` → `[project] version`, `VERSION` | CalVer `<commit year>.<commit month>.<release>`, e.g. `2026.10.1`, written by `release.py stamp` |
| Release archive layout | `skills/rust-style-guide-audit/scripts/release.py` | `SKILL_NAME`, `SKILL_ROOT`, `ROOT`, `ROOT_FILES`, `LICENCE_FILES`, `EXCLUDED_DIRS` |
| Skill metadata / trigger words | `skills/rust-style-guide-audit/SKILL.md` frontmatter | `name`, `description` |
| Tool pins | `.config/mise/config.toml` | `[tools]` |
| Tasks | `.config/mise/conf.d/*.toml` | `[tasks.<name>]` |
| Skill install list | `.config/mise/data/skills.csv` | `enabled,category,repo,skill` |
| Python lint rules | `ruff.toml` | `[lint] select`, `line-length = 120` |
| Type-check surface | `ty.toml` | `[src] include` |
| Markdown lint | `.config/rumdl.toml` | `exclude = [… ".agents"]`, `disable = ["MD013"]` |
| Test config | `pyproject.toml` → `[tool.pytest.ini_options]` | `testpaths`, `cache_dir = "tmp/pytest-cache"` |

## Naming conventions

- Rule IDs: `<AREA>-<NN>` where AREA is `ORG IMP FMT OWN API TYP TRT CON MAC NAM DOC SAF ICN`.
  IDs are stable — never renumber; retire and add.
- Suppression comments: `// style-guide-audit: ignore <ID> — <reason>` (or `file-ignore`).
- Conventional commits: `feat(detector):`, `fix(catalog):`, `docs(readme):`.

## Subdirectory

If this file grows past its size budget, split detail into
`.agents/files/<name>.md` — every file there MUST be listed above.
