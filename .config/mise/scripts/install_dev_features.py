#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Install the dev-feature tools, MCP servers and skills listed in data/*.csv.

The CSVs in ``.config/mise/data/`` are the single source of truth — add a row and
re-run the task instead of editing shell commands:

``skills.csv``        enabled,category,repo,skill
``dev-features.csv``  enabled,category,tool,tool_value,mcp_command,mcp_name,skill_repo,skill

A missing file is not an error: this repository pins its own tools in
``.config/mise/config.toml`` and therefore ships only ``skills.csv``, while the
``dev-features.csv`` path stays supported so the copier-uv-plus layout transfers.

Every row carries a leading ``enabled`` flag so a feature can be switched off without
deleting it. Rows without that column (hand-written CSVs) count as enabled.

Commands:
    install_dev_features.py add-dev-features   tools + MCP servers + skills from both CSVs
    install_dev_features.py add-skills         skills only
    install_dev_features.py list               show what would run, change nothing

Run through mise: ``mise run add-skills``.
"""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"

SkillRow = dict[str, str]


def rows(name: str) -> list[SkillRow]:
    """Read one CSV, returning an empty list when the file is absent."""
    path = DATA / name
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def enabled(row: SkillRow) -> bool:
    """A row runs only when its ``enabled`` cell is truthy; a missing cell means yes."""
    flag = row.get("enabled")
    if flag is None:
        return True
    return flag.strip().lower() not in {"0", "false", "no", ""}


def run(cmd: list[str], *, dry_run: bool) -> None:
    print(f"$ {' '.join(cmd)}")
    if not dry_run:
        subprocess.run(cmd, check=False)


def skill_command(repo: str, skill: str) -> list[str]:
    """Build the `skills add` invocation. Order matters: repo first, then `-s <name>`."""
    cmd = ["bun", "x", "skills", "add", repo]
    if skill:
        cmd += ["-s", skill]
    return [*cmd, "-a", "universal", "-y"]


def add_skills(*, dry_run: bool) -> None:
    """Install every enabled skill from dev-features.csv and skills.csv."""
    for row in rows("dev-features.csv"):
        if enabled(row) and (repo := row.get("skill_repo")):
            run(skill_command(repo, row.get("skill", "")), dry_run=dry_run)
    for row in rows("skills.csv"):
        if enabled(row) and (repo := row.get("repo")):
            run(skill_command(repo, row.get("skill", "")), dry_run=dry_run)


def add_dev_features(*, dry_run: bool) -> None:
    """Pin every enabled tool into the project and register its MCP server, then add skills."""
    for row in rows("dev-features.csv"):
        if not enabled(row):
            continue
        if tool := row.get("tool"):
            # `mise use` (not `mise install`) so the pin lands in [tools] and its shim
            # resolves; a bare `install` leaves "No version is set for shim".
            run(["mise", "use", f"{tool}@latest"], dry_run=dry_run)
        if (command := row.get("mcp_command")) and (name := row.get("mcp_name")):
            run(
                ["bun", "x", "add-mcp", command, "-y", "-a", "universal", "-n", name],
                dry_run=dry_run,
            )
    add_skills(dry_run=dry_run)


def list_features(*, dry_run: bool) -> None:
    """Print the commands in order without running them."""
    del dry_run  # listing never executes anything
    add_dev_features(dry_run=True)


COMMANDS = {
    "add-dev-features": add_dev_features,
    "add-skills": add_skills,
    "list": list_features,
}


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command not in COMMANDS:
        print(__doc__, file=sys.stderr)
        return 1
    COMMANDS[command](dry_run=command == "list")
    return 0


if __name__ == "__main__":
    sys.exit(main())
