# AGENTS.md — DOX authoring

Detail file for `.agents/POLICIES.md`. Read it on every DOX change: it owns tier
assignment, reference-don't-restate, the rule-first rationale, and the size budget.

## DOX authoring (keep AGENTS.md lean)

AGENTS.md and `.agents/` files share limited context. Bloat and duplication
are the failure mode.

### Where a rule lives

A rule goes in the **highest (most general) tier that fully applies**:

- Applies to **all code in the project** → `.agents/POLICIES.md` (default);
  if it must be seen before any edit is attempted, root `AGENTS.md`.
- Meaningful **only inside one subtree** → that subtree's `AGENTS.md`.
- Just helps navigation → the parent's Child DOX Index, nothing else.

### Reference, don't restate

A rule appears in **exactly one file**. Other files use a **pointer line**:
`<topic> — see <file>`. Never copy the rule, rationale, or example.

### Rule first, rationale second, never third

A DOX line is the rule. If a rationale is costly to rediscover, add one
short clause. No multi-paragraph explanations or code pairs — those belong
in a skill or `docs/`, linked once.

### Content rules

- **No tree views.** Generate on demand with `rg --files | tree-cli --fromfile`.
- **No history in AGENTS.md files.** Git log has routine history. Record only
  decisions costly to rediscover — in `.agents/HISTORY.md` (or
  `.agents/history/` for overflow archives). See `.agents/policies/plans-and-docs.md`
  for archiving completed plans.
- **Lean state files, optional subdirectories.** State files stay brief entry
  points (index-style, not sprawling documents). A state file that grows past
  its size budget (≤ **120 lines**) must be split into
  `.agents/<topic>/<name>.md` subdirectories — not stuffed longer. Every file
  in an optional subdirectory **MUST** be mentioned in the state file that
  owns it. See **State file subdirectories** below.
- **No TODO lists.** Use an issue tracker or beads.
- Prefer direct bullets with explicit names.
- Trim obvious statements, repeated rules, and detail that no longer applies.

## State file subdirectories

Each state file has a matching optional subdirectory for growth — the file
stays a lean index and the subdirectory carries the detail:

| State file | Optional subdirectory |
| ---------- | -------------------- |
| `FILES.md` | `.agents/files/` |
| `POLICIES.md` | `.agents/policies/` |
| `TOOLS.md` | `.agents/tools/` |
| `MAINTENANCE.md` | `.agents/maintenance/` |

- Only create a subdirectory when its state file approaches its size budget.
- Every file in a subdirectory MUST be listed in its state file (name + one
  line of what it covers). A subdirectory file missing from the index is
  dead content — move it or delete it.
- `ONBOARDING.md` and `HISTORY.md` have no subdirectories: entry points stay
  a single file, and history growth goes to `.agents/history/`.

## Size budget

- `.agents/` files: ≤ **120 lines** (always-injected context).
- Subtree `AGENTS.md`: ≤ **250 lines** (loaded cumulatively with parents).
- `SKILL.md`: ≤ ~300 lines — it is loaded into an agent's context on every
  invocation, so detail belongs in the sibling `references/`.

Exceeding the budget signals restating instead of pointing, or hoarding
rationale. Cut first; split the subtree only as a last resort.

When a state file exceeds its budget, split detail into its matching
subdirectory (`.agents/files/`, `.agents/policies/`, `.agents/tools/`,
`.agents/maintenance/`) — the file stays a lean index and every file in the
subdirectory MUST be listed in it.
