"""Tests for the CalVer/ZIP release tooling in `scripts/release.py`.

The version derivation is pure and is driven here through every branch. The archive test
inspects the real ZIP, because the importable layout (one top-level directory holding
SKILL.md) is the whole point of the artefact.
"""

from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

import pytest
import release

DATE = "2026.10"
COMMIT = "a" * 40
OTHER = "b" * 40


@pytest.mark.parametrize(
    ("tags", "expected"),
    [
        ({}, f"{DATE}.1"),
        ({f"v{DATE}.1": OTHER}, f"{DATE}.2"),
        ({f"v{DATE}.1": OTHER, f"v{DATE}.2": COMMIT}, f"{DATE}.2"),
        ({f"v{DATE}.1": OTHER, f"v{DATE}.2": OTHER, f"v{DATE}.4": OTHER}, f"{DATE}.3"),
        # A tag from another month must not influence this month's counter.
        ({"v2026.01.1": OTHER, f"v{DATE}.1": OTHER}, f"{DATE}.2"),
        # A tag on a foreign commit does not hand its version to this one.
        ({f"v{DATE}.2": COMMIT, f"v{DATE}.3": OTHER}, f"{DATE}.2"),
    ],
)
def test_resolve_version(tags: dict[str, str], expected: str) -> None:
    assert release.resolve_version(DATE, COMMIT, tags) == expected


def test_the_first_release_of_a_month_is_release_one() -> None:
    """CalVer here is `year.month.release` — the third component counts releases, not days."""
    assert release.resolve_version(DATE, COMMIT, {}) == f"{DATE}.1"
    assert release.next_version(DATE, {f"v{DATE}.1": OTHER}) == f"{DATE}.2"


def test_resolve_version_is_stable_for_the_same_commit() -> None:
    """Re-running a release for a commit that is already tagged must not bump."""
    tags = {f"v{DATE}.1": COMMIT}
    assert release.resolve_version(DATE, COMMIT, tags) == f"{DATE}.1"
    assert release.resolve_version(DATE, COMMIT, tags) == f"{DATE}.1"


def test_tag_version_requires_a_release_counter() -> None:
    """Only `<month>.<release>` tags count; a bare `v2026.10` is not a released version."""
    assert release.tag_version_for(COMMIT, DATE, {f"v{DATE}": COMMIT}) is None
    assert release.tag_version_for(COMMIT, DATE, {f"v{DATE}9": COMMIT}) is None


def test_pyproject_text_replaces_only_the_version_line() -> None:
    text = '[project]\nname = "x"\nversion = "0.1.0"\n\n[tool.other]\nversion = "9.9.9"\n'
    out = release.pyproject_text(DATE, text)
    assert f'version = "{DATE}"' in out
    assert 'version = "9.9.9"' in out, "the first non-matching version line must survive"
    assert 'name = "x"' in out


def test_pyproject_text_requires_a_version_line() -> None:
    with pytest.raises(SystemExit):
        release.pyproject_text(DATE, '[project]\nname = "x"\n')


def test_shipped_files_excludes_the_dev_surface() -> None:
    names = {inside.as_posix() for _, inside in release.shipped_files()}
    assert {"SKILL.md", "LICENSE", "NOTICE", "README.md", "scripts/audit.py", "scripts/release.py"} <= names
    assert "scripts/fixtures/violations.rs" in names
    assert not {n for n in names if n.startswith(("tests/", ".config/", "dist/", "tmp/", "skills/"))}
    assert not {n for n in names if "__pycache__" in n or n.endswith(".pyc")}
    assert "AGENTS.md" not in names, "the repository's working contract is not skill content"


def test_build_zip_has_one_top_level_directory(tmp_path: Path) -> None:
    """An importer unzips and drops the single folder it finds; anything else is broken."""
    archive = release.build_zip("2099.01.01", tmp_path)
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
        assert zf.testzip() is None
    assert archive.name == f"{release.SKILL_NAME}-2099.01.01.zip"
    assert {name.split("/")[0] for name in names} == {release.SKILL_NAME}
    assert f"{release.SKILL_NAME}/SKILL.md" in names
    assert not [name for name in names if name.endswith("/")], "directory entries are redundant"


def test_release_tags_resolve_annotated_tags_to_their_commit(tmp_path: Path) -> None:
    """`git tag -a` stores a tag object; the tag-to-commit map must dereference it.

    Without the dereference the stamp guard never finds HEAD's tag and every push is refused.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]

    def run(*args: str) -> str:
        return subprocess.run([*git, *args], capture_output=True, text=True, check=True).stdout.strip()

    run("init", "-q")
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    run("add", "a.txt")
    run("commit", "-q", "-m", "one")
    first = run("rev-parse", "HEAD")
    run("tag", "-a", f"v{DATE}", "-m", DATE)
    (repo / "a.txt").write_text("b\n", encoding="utf-8")
    run("commit", "-q", "-am", "two")

    tags = subprocess.run(
        [*git, "for-each-ref", "refs/tags", "--format=%(refname:short) %(objectname) %(*objectname)"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    assert len(tags) == 1
    parts = tags[0].split()
    assert len(parts) == 3, "an annotated tag reports both the tag object and the commit"
    assert parts[2] == first, "the dereferenced commit is the third field"
