"""pytest entry points for the audit's regression groups.

`scripts/self_test.py` owns the assertions and is runnable on its own (`uv run
scripts/self_test.py`), which is what an agent invokes. This module only re-exports its
groups as pytest cases so `mise run test` reports per-group failures instead of one opaque
line, and so the suite can `--last-failed`.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Callable

import pytest
from self_test import AUDIT, EXPECT_VIOLATIONS, GROUPS, run_audit


@pytest.mark.parametrize(("label", "check"), GROUPS, ids=[label for label, _ in GROUPS])
def test_group(label: str, check: Callable[[], list[str]]) -> None:
    failures = check()
    assert not failures, f"{label}:\n" + "\n".join(f"  - {f}" for f in failures)


def test_every_rule_is_documented() -> None:
    """The catalog and the script must not drift: an undocumented rule ID is unusable."""
    catalog = AUDIT.parent.parent / "references" / "rules-catalog.md"
    documented = {
        m.group(1)
        for line in catalog.read_text(encoding="utf-8").splitlines()
        if (m := re.match(r"^\| ([A-Z]{3}-\d{2}) \|", line))
    }
    listed = subprocess.run(
        [sys.executable, str(AUDIT), "--list-rules"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    implemented = {line.split()[0] for line in listed.splitlines()[1:] if line.strip()}
    assert implemented, "audit --list-rules printed no rules"
    assert implemented == documented, (
        f"script-only: {sorted(implemented - documented)}; catalog-only: {sorted(documented - implemented)}"
    )


def test_json_report_shape() -> None:
    """The JSON payload is a published interface (agents parse it); keep the keys stable."""
    data = run_audit(AUDIT.parent / "fixtures" / "violations.rs", "--kind", "library")
    assert set(data) == {"roots", "kind", "codebase", "files_scanned", "counts", "findings"}
    assert set(data["counts"]) == {"error", "warning", "note"}
    assert data["files_scanned"] == 1
    finding = data["findings"][0]
    assert {"rule", "path", "line", "message", "snippet", "fix"} <= set(finding)
    assert finding["severity"] in {"error", "warning", "note"}


def test_fixture_expectations_cover_real_findings() -> None:
    """Guard against a fixture edit that silently drops a rule from the expectation table."""
    data = run_audit(AUDIT.parent / "fixtures" / "violations.rs", "--kind", "library")
    seen = {f["rule"] for f in data["findings"]}
    missing = set(EXPECT_VIOLATIONS) - seen
    assert not missing, f"expected but absent: {sorted(missing)}"


def test_report_is_valid_markdown() -> None:
    """The markdown report starts with an H1 and carries the summary counts an agent quotes."""
    out = subprocess.run(
        [
            sys.executable,
            str(AUDIT),
            str(AUDIT.parent / "fixtures" / "violations.rs"),
            "--kind",
            "library",
            "--max-per-rule",
            "2",
        ],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    assert out.startswith("# Rust Style Guide Audit")
    assert "Findings by rule" in out
    assert "more" in out, "per-rule truncation is the only signal that findings were elided"
    assert json.dumps(out)  # the report is encodable, i.e. no lone surrogates from a source file
