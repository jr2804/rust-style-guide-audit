#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""CalVer stamping and the importable ZIP for this skill.

There is no CI here: the release artefact is produced locally from the commit being
shipped, so the version and the archive always describe exactly one tree.

Version scheme — CalVer `<year>.<month>.<release>` derived from the *commit's own* date,
never from "now":

    git log -1 --format=%cd --date=format:%Y.%m   →  2026.10   ⇒  release 1  ⇒  2026.10.1

The third component is the release counter for that month, taken from the `v<version>` tags
that already exist — not the day of the month. The first release in a month is `.1`, the next
is `.2`, and a new month starts again at `.1`. Because the year and month come from the
commit, re-running a release for an already tagged commit yields the same version instead of
a bump. `2026.10.1` is a valid PEP 440 version.

Commands:
    version   print the CalVer version of HEAD
    stamp     write it into pyproject.toml and VERSION (no git action)
    package   build dist/<name>-<version>.zip
    check     fail unless pyproject.toml already carries HEAD's version (pre-push guard)
    release   stamp + package + commit + tag + push, then attach the ZIP to a GitHub release

Every command accepts --version to override the derived value.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import zipfile
from pathlib import Path

SKILL_NAME = "rust-style-guide-audit"
# <repo>/skills/rust-style-guide-audit/scripts/release.py — the skill folder is what the ZIP
# wraps, the repository root is where git, pyproject.toml and dist/ live.
SKILL_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[3]

# What an importer needs: SKILL.md, everything it links to, and the attribution files.
# The skill files live in this folder; the licence and README stay at the repository root and
# are copied into the archive's single top-level directory.
ROOT_FILES = ("SKILL.md", "references", "scripts")
LICENCE_FILES = ("LICENSE", "NOTICE", "README.md")
EXCLUDED_DIRS = {"__pycache__", ".ruff_cache", ".pytest_cache", ".ty_cache", ".venv", "tmp", "dist"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
# AGENTS.md is the development contract for this repository; it is not skill content.
EXCLUDED_NAMES = {".DS_Store", "Thumbs.db", "AGENTS.md"}


def git(*args: str) -> str:
    """Run a git command in the repository and return its stripped stdout."""
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def commit_month(commit: str = "HEAD") -> str:
    """The commit's own year and month as `YYYY.MM` — the CalVer prefix."""
    month = git("log", "-1", "--format=%cd", "--date=format:%Y.%m", commit)
    if not re.fullmatch(r"\d{4}\.\d{2}", month):
        raise SystemExit(f"unexpected commit month: {month!r}")
    return month


def release_tags() -> dict[str, str]:
    """Map every `v<calver>` tag to the commit it points at.

    Annotated tags point at a tag object, so the dereferenced `*objectname` is the commit and
    must be preferred; `objectname` alone would compare a tag SHA against a commit SHA and
    never match.
    """
    out = git(
        "for-each-ref",
        "refs/tags",
        "--format=%(refname:short) %(objectname) %(*objectname)",
    )
    tags: dict[str, str] = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and re.match(r"v[0-9]", parts[0]):
            tags[parts[0]] = parts[2] if len(parts) > 2 else parts[1]
    return tags


def tag_version_for(commit: str, month: str, tags: dict[str, str]) -> str | None:
    """The `<month>.<release>` version already tagged on `commit`, if any."""
    for tag, sha in tags.items():
        if sha == commit and re.fullmatch(rf"v{re.escape(month)}\.\d+", tag):
            return tag[1:]
    return None


def next_version(month: str, tags: dict[str, str]) -> str:
    """The first free `<month>.<release>` version not yet tagged."""
    release = 1
    while f"v{month}.{release}" in tags:
        release += 1
    return f"{month}.{release}"


def resolve_version(month: str, commit: str, tags: dict[str, str]) -> str:
    """Return the release version for `commit`, reusing the tag it already carries.

    Pure, so the tests drive every branch: a tag on this commit wins (a re-run is a no-op),
    otherwise the next free release counter for that month is chosen.
    """
    return tag_version_for(commit, month, tags) or next_version(month, tags)


def head_version() -> str:
    """The CalVer version for HEAD: the tag it already carries, else the next free one."""
    tags = release_tags()
    commit = git("rev-parse", "HEAD")
    month = commit_month(commit)
    return tag_version_for(commit, month, tags) or next_version(month, tags)


def pyproject_text(version: str, text: str) -> str:
    """`text` with its `version = "…"` line replaced."""
    new_text, count = re.subn(
        r'^version = "[^"]+"',
        f'version = "{version}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if count != 1:
        raise SystemExit('pyproject.toml has no `version = "…"` line')
    return new_text


def recorded_version() -> str | None:
    """The version currently in pyproject.toml, if any."""
    match = re.search(r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.MULTILINE)
    return match.group(1) if match else None


def stamp(version: str) -> None:
    """Write the version into pyproject.toml and VERSION, and refresh the lock's copy."""
    path = ROOT / "pyproject.toml"
    path.write_text(pyproject_text(version, path.read_text(encoding="utf-8")), encoding="utf-8")
    (ROOT / "VERSION").write_text(f"{version}\n", encoding="utf-8")
    # uv.lock records the project's own version; re-locking keeps the stamp from showing up as
    # a dirty file on the next `uv sync`.
    if subprocess.run(["uv", "lock", "--quiet"], cwd=ROOT, check=False).returncode != 0:
        print("note: `uv lock` failed; uv.lock may still name the previous version", file=sys.stderr)


def excluded(relative: Path) -> bool:
    """True when a repository-relative path is build noise, not shippable content."""
    return (
        bool(EXCLUDED_DIRS & set(relative.parts))
        or relative.name in EXCLUDED_NAMES
        or relative.suffix in EXCLUDED_SUFFIXES
    )


def shipped_files() -> list[tuple[Path, Path]]:
    """Every file that belongs in the ZIP as `(source, path inside the archive)`, stably ordered."""
    missing = [name for name in ROOT_FILES if not (SKILL_ROOT / name).exists()]
    if missing:
        raise SystemExit(f"missing skill files: {', '.join(missing)}")
    files: list[tuple[Path, Path]] = []
    for name in (*LICENCE_FILES, *ROOT_FILES):
        base = SKILL_ROOT if name in ROOT_FILES else ROOT
        path = base / name
        if path.is_file() and not excluded(Path(name)):
            files.append((path, Path(name)))
        elif path.is_dir():
            files.extend(
                (p, p.relative_to(base))
                for p in sorted(path.rglob("*"))
                if p.is_file() and not excluded(p.relative_to(base))
            )
    return files


def build_zip(version: str, out_dir: Path) -> Path:
    """Write `<out_dir>/<name>-<version>.zip` with one `<name>/` directory at its root.

    The single top-level directory is what an importer expects: unzipping drops one skill
    folder whose root holds SKILL.md, which is the layout `skills add` and the Claude
    Desktop importer consume.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    archive = out_dir / f"{SKILL_NAME}-{version}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for source, relative in shipped_files():
            zf.write(source, Path(SKILL_NAME) / relative)
    return archive


def cmd_version(_: argparse.Namespace) -> int:
    print(head_version())
    return 0


def cmd_stamp(args: argparse.Namespace) -> int:
    version = args.version or head_version()
    stamp(version)
    print(f"stamped {version}")
    return 0


def cmd_package(args: argparse.Namespace) -> int:
    version = args.version or head_version()
    archive = build_zip(version, ROOT / "dist")
    print(f"{archive.relative_to(ROOT)} ({len(zipfile.ZipFile(archive).namelist())} files)")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Guard the invariant that a pushed tree is stamped for the commit it ships.

    The reference is the tag on HEAD, not a recomputed month: the release commit is tagged in
    the same run that stamps it, so a tag on HEAD is exactly the proof that this tree was
    released. Recomputing instead would chase its own tail — stamping creates a commit, which
    moves HEAD, which shifts the counter.
    """
    commit = git("rev-parse", "HEAD")
    released = args.version or tag_version_for(commit, commit_month(commit), release_tags())
    if not released:
        print("HEAD is not released: no v<calver> tag on this commit.", file=sys.stderr)
        print("Run `mise run release`, which stamps, packages, commits and tags in one step.", file=sys.stderr)
        return 1
    actual = recorded_version()
    if actual != released:
        print(f"pyproject.toml says {actual!r}, HEAD is tagged {released}. Run `mise run release`.", file=sys.stderr)
        return 1
    if not (ROOT / "dist" / f"{SKILL_NAME}-{released}.zip").is_file():
        print(f"note: dist/{SKILL_NAME}-{released}.zip is not built — `mise run release`.", file=sys.stderr)
    return 0


def cmd_release(args: argparse.Namespace) -> int:
    version = args.version or head_version()
    stamp(version)
    archive = build_zip(version, ROOT / "dist")
    print(f"{version} → {archive.relative_to(ROOT)}")

    # Explicit paths only: a release must never sweep unrelated work into its commit.
    git("add", "pyproject.toml", "VERSION", "uv.lock")
    if git("diff", "--cached", "--name-only"):
        git("commit", "-m", f"chore(release): {version}")
    tag = f"v{version}"
    if tag not in release_tags():
        git("tag", "-a", tag, "-m", f"{SKILL_NAME} {version}")

    if args.no_push:
        print(f"tagged {tag}; push skipped (--no-push)")
        return 0
    git("push", "--follow-tags")
    print(f"pushed {tag}")
    if args.no_github_release:
        return 0
    if subprocess.run(["gh", "release", "view", tag], cwd=ROOT, capture_output=True, check=False).returncode == 0:
        print(f"GitHub release {tag} already exists; attaching the archive")
        return subprocess.run(
            ["gh", "release", "upload", tag, str(archive), "--clobber"],
            cwd=ROOT,
            check=False,
        ).returncode
    notes = (
        f"Importable skill archive: `{archive.name}` (unzip it, then put the folder in your agent's skills directory)."
    )
    return subprocess.run(
        [
            "gh",
            "release",
            "create",
            tag,
            str(archive),
            "--title",
            f"{SKILL_NAME} {version}",
            "--notes",
            notes,
        ],
        cwd=ROOT,
        check=False,
    ).returncode


def main() -> int:
    # A cp1252 console cannot encode the arrows and em dashes used in the progress output; the
    # release must not die on a print statement after it has already stamped the tree.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description="CalVer versioning and the importable ZIP for this skill.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--version", help="override the CalVer version derived from HEAD")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("version", help="print the CalVer version of HEAD")
    commands.add_parser("stamp", parents=[common], help="write the version into pyproject.toml and VERSION")
    commands.add_parser("package", parents=[common], help="build dist/<name>-<version>.zip")
    commands.add_parser("check", parents=[common], help="fail unless the tree is stamped for HEAD")
    release = commands.add_parser("release", parents=[common], help="stamp, package, commit, tag, push, publish")
    release.add_argument("--no-push", action="store_true", help="stop after tagging")
    release.add_argument("--no-github-release", action="store_true", help="do not attach the ZIP to a GitHub release")
    args = parser.parse_args()
    handler = {
        "version": cmd_version,
        "stamp": cmd_stamp,
        "package": cmd_package,
        "check": cmd_check,
        "release": cmd_release,
    }[args.command]
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
