# AGENTS.md — TOOLS

State file: inventory of tools used in development — CLIs, MCP servers,
skills, runtimes, and project scripts. Demand-loaded like all state files;
keep it current (see `.agents/MAINTENANCE.md`).

## Rules

- Use an existing tool before adding a new one. No new tools, MCP servers,
  skills, or dependencies without explicit instruction (`.agents/POLICIES.md`).
- Each tool appears exactly once, in its primary table.
- Tables describe current usage — delete rows when tools leave; this is not a
  historical log.
- A new tool needs three things before it counts as adopted: a mise pin in
  `.config/mise/config.toml`, a task in `.config/mise/conf.d/`, and a line in
  the README's development section.

## Subdirectory

If this file grows past its size budget, split detail into
`.agents/tools/<name>.md` — every file there MUST be listed above.

## CLI tools & runtimes

| Tool | When | Purpose |
| ---- | ---- | ------- |
| `mise` | Every entry point | Pins the toolchain and owns every task; `mise install` is the first command after a clone |
| `uv` | Running any Python file | Runs the PEP 723 scripts without an environment and owns the dev venv (`mise run sync`) |
| `bun` | Installing skills | `bun x skills add …`; also the configured npm package manager in mise |
| `ruff` | Python lint + format | `mise run lint` / `mise run fmt`; all rules in `ruff.toml` |
| `ty` | Type checking | `mise run typecheck`; `error-on-warning = true`, so a warning fails the gate |
| `rumdl` | Markdown lint + format | `mise run lint-md` / `mise run fmt-md`; config `.config/rumdl.toml` |
| `skills` (`npm:skills`) | Adding companion skills | Reads `.config/mise/data/skills.csv` |
| `skills-ref` (`uvx --from skills-ref`) | Validating the skill | `mise run validate-skill` — needs the absolute dir, not `.` |
| `ripgrep` (`rg`) | Searching | Preferred over `Select-String`/`grep` for source searches |
| `tree-cli` | Rendering a tree | `rg --files \| tree-cli --fromfile`; tree views are never committed |
| `gh` | Publishing a release | Only `skills/rust-style-guide-audit/scripts/release.py` calls it, to create/view the GitHub release |
| `git` | Version and refs | Year and month come from `git log -1 --date=format:%Y.%m`; existing tags drive the release counter |
| `pytest` | Test runner | `mise run test`; cache under `tmp/pytest-cache` |

## MCP servers

| Server | When | Purpose |
| ------ | ---- | ------- |
| — | — | None registered for this repository |

## Skills

Installed by `mise run add-skills` from `.config/mise/data/skills.csv` into
`.agents/skills/` (vendored, gitignored — see `.agents/MAINTENANCE.md`).

| Skill | When | Purpose |
| ----- | ---- | ------- |
| `skill-creator` | Authoring or optimizing a skill | Scaffolding, evals, description tuning |
| `skill-reviewer` | Reviewing this skill's `SKILL.md` | Agent Skills spec compliance and improvement patterns |
| `stop-slop` | Editing prose in `README.md`, `SKILL.md`, `references/` | Removes AI writing tells |

The skill this repository ships is `skills/rust-style-guide-audit/`; `mise run install-skill`
installs it into `~/.agents/skills` for use by other agents.

## Project scripts & tasks

| Command | Purpose |
| ------- | ------- |
| `mise run check` | The gate: `sync`, `lint`, `lint-md`, `typecheck`, `test`, `self-test` |
| `mise run fmt` | Writes: ruff import-sort + format, then rumdl fmt |
| `mise run sync` | Sync the dev virtualenv with `pyproject.toml` |
| `mise run audit PATH` | Run `skills/rust-style-guide-audit/scripts/audit.py` against a path |
| `mise run self-test` | Run `skills/rust-style-guide-audit/scripts/self_test.py` (5 regression groups) directly |
| `mise run test` | Run the pytest suite |
| `mise run add-skills` | Install the skills listed in `skills.csv` |
| `mise run add-dev-features` | Pin tools, register MCP servers, install skills (dry run: `list`) |
| `mise run list-skills` | List skills currently installed for agents |
| `mise run validate-skill` | Validate the skill folder's `SKILL.md` frontmatter against the spec |
| `mise run install-skill` | Install this skill into `~/.agents/skills` |
| `mise run hooks` | Once per clone: `git config core.hooksPath .githooks` |
| `mise run release` | `check` → stamp CalVer → ZIP → commit → tag → push → GitHub release |
| `mise run release-dry` | Same, stopping before the push |
| `mise run package` | Rebuild `dist/<name>-<calver>.zip` only |
| `mise run version` | Print the CalVer version of HEAD |
| `mise run upgrade-tools` | `mise install`, `mise up`, `mise prune` |
