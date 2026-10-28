# AGENTS.md — HISTORY

State file. The one file that may reference the past — sparingly. Read when
relevant to the current task; long-term memory for decisions, not a log.
Routine history lives in git; only record what is costly to rediscover.

## Format

| Date | Decision | Rationale | Git ref |
| ---- | -------- | --------- | ------- |
| YYYY-MM-DD | [description] | [why] | [commit hash/tag] |

## Record

| Date | Decision | Rationale | Git ref |
| ---- | -------- | --------- | ------- |
| 2026-10-28 | The skill lives in its own repository, extracted from the prompt collection it was authored in | The rule set is a product with its own release cadence; keeping it inside a multi-skill repo made the ZIP layout and the version meaningless | `89a233b` |
| 2026-10-28 | MIT for the code and this repository's prose; the quoted guide stays Google's CC BY 3.0, recorded in `NOTICE` | The catalog paraphrases and quotes the guide; a single MIT claim over the quoted headings would be a false licence statement | `f4a984f` |
| 2026-10-28 | No hosted CI. The gate is `mise run check` locally plus `.githooks/pre-push` | Every GitHub Actions run needed the same three fixes (venv before `ty`/pytest, absolute path for the skill validator) and still could not build the artefact without a second pipeline; a local gate plus a pre-push hook is one mechanism, not two | `879c5c6`, `364cca0`, `a086448`, `2748dd7` |
| 2026-10-28 | Version is CalVer `year.month.release`, with year and month taken from the commit and the counter from existing tags | Makes the version a function of the commit, so re-running a release is a no-op instead of a bump — and an unstamped tree can be detected by comparing the two. The third component counts releases (`.1`, `.2`, …), it is not the day of the month | `2748dd7` |
| 2026-10-28 | The skill lives in `skills/rust-style-guide-audit/`, not at the repository root | Skill discovery reads `skills/<name>/SKILL.md`; a root-level `SKILL.md` is not discoverable by `bun x skills add` or the Desktop importer, and it forced the packager to guess where the skill ended | `830d8f4`, `v2026.10.1` |
| 2026-10-28 | The release artefact is an importable ZIP (`dist/<name>-<calver>.zip`), attached to the GitHub release | An importer unzips and drops one folder; requiring a clone to install the skill contradicted the `skills add` install path in the README | `2748dd7` |
| 2026-10-28 | `ICN-02` (check-then-unwrap) and `ICN-03` (match guard) are separate rules | The broad "no unwrap" detector produced four false errors: `if let` cannot fix an `unwrap` inside a match guard. `ICN-03` was already narrowed to `expect` over `unwrap`; the split is the reason both exist | pre-repo history, see `skills/rust-style-guide-audit/references/rules-catalog.md` |

## Do not record

- Routine commits, refactor logs, session activity, release notes.
- Anything obvious from git, the code, or current AGENTS.md/state files.

## Guidance

- Keep entries brief — enough to reconstruct the reasoning.
- Link to the relevant commits or tags.
- If this file grows large, move older entries to `.agents/history/` and keep
  a pointer here.
- Completed implementation plans are archived as single files at
  `.agents/history/<YYYY-MM-DD-plan-name>.md` and linked from the decision
  entry they belong to. The trigger to archive is **plan completion**, not
  file growth — see **Archive a plan** below.

## Archive a plan

When a plan's work is complete — the point to do this is when the
implementation lands, not at the planning stage:

1. Consolidate `.agents/plans/<YYYY-MM-DD>-<feature-name>/` into a single
   file `.agents/history/<YYYY-MM-DD-plan-name>.md` (use the plan directory's
   date prefix, e.g. `2026-07-14-api-migration.md`).
2. Delete the plan directory.
3. Add an entry to `.agents/HISTORY.md` referencing the archive and its
   commit.

If the date prefix on the plan directory is missing or wrong, use the date
work started — record it in the archive filename exactly as-is.
