#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Regression test for scripts/audit.py.

Two fixtures:
  fixtures/violations.rs  — one construct per detectable rule; every rule listed in
                            EXPECT_VIOLATIONS must be reported at the expected line.
  (inline)               — clean code that must produce zero findings, so a too-greedy
                            regex is caught as well as a missing one.

Run: uv run scripts/self_test.py
Exit 0 when all assertions pass.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUDIT = HERE / "audit.py"
FIXTURE = HERE / "fixtures" / "violations.rs"

# rule -> line numbers in fixtures/violations.rs that must be reported
EXPECT_VIOLATIONS: dict[str, set[int]] = {
    "IMP-01": {4},
    "IMP-02": {7},
    "TYP-02": {9},
    "TYP-01": {11},
    "SAF-05": {13},
    "SAF-06": {18},
    "TRT-08": {18},
    "NAM-01": {38, 78},
    "API-01": {38, 46, 131},
    "NAM-04": {42},
    "ICN-03": {49},
    "ICN-01": {49},
    "ICN-02": {59},
    "ICN-04": {61},
    "ICN-05": {63},
    "ICN-06": {66},
    "ICN-08": {69},
    "SAF-03": {74},
    "API-05": {83},
    "SAF-01": {88},
    "OWN-01": {92, 93},
    "CON-01": {98},
    "TRT-07": {104},
    "DOC-02": {110},
    "TRT-03": {125},
    "IMP-04": {138},
    "IMP-03": {153},
    "SAF-11": {143},
    "NAM-06": {147},
}

# Rule -> lines the rule must NOT report, even though it fires elsewhere in the file. These
# guard the exclusions of the rule itself (a `pub use` re-export, a module used as a path
# qualifier), which a whole-rule FORBIDDEN entry cannot express.
MUST_NOT_FIRE_AT: dict[str, set[int]] = {
    "IMP-03": {160, 167},
}

# Rules that must NOT fire on the fixture, because doing so would be a false positive.
FORBIDDEN: set[str] = {
    "MAC-01",  # no macro definitions in the fixture
    "ICN-07",  # no catch_unwind
    "CON-02",  # async is chrome-only and not enabled
    "CON-03",  # thread spawn is chrome-only
    "CON-04",  # fuchsia-only
    "SAF-02",  # no feature gates
    "SAF-08",  # no ctor
    "TRT-04",
    "TRT-06",
    "FMT-02",
    "ORG-04",
    "ORG-02",
    "ICN-09",
    "SAF-10",
}

CLEAN_FIXTURE = """
//! A module that follows the guide, to catch over-eager detectors.

use std::collections::HashMap;

/// A counter.
#[derive(Debug, Default, Clone)]
pub struct Counter {
    counts: HashMap<String, u64>,
}

impl Counter {
    /// Creates an empty counter.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Returns the count for `key`, or zero.
    #[must_use]
    pub fn count(&self, key: &str) -> u64 {
        self.counts.get(key).copied().unwrap_or(0)
    }

    /// Records one occurrence of `key`.
    pub fn bump(&mut self, key: &str) {
        *self.counts.entry(key.to_owned()).or_insert(0) += 1;
    }

    /// Returns `true` when no key has been recorded.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.counts.is_empty()
    }

    /// Returns the number of distinct keys.
    #[must_use]
    pub fn len(&self) -> usize {
        self.counts.len()
    }
}

/// Sums `values`.
///
/// # Panics
///
/// Panics when the sum overflows `i64`.
#[must_use]
pub fn checked_sum(values: &[i64]) -> i64 {
    values.iter().try_fold(0i64, |acc, v| acc.checked_add(*v)).expect("sum overflows i64")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn counts_occurrences() {
        let mut counter = Counter::new();
        counter.bump("a");
        counter.bump("a");
        assert_eq!(
            counter.count("a"),
            2,
            "two increments must produce a count of two"
        );
    }
}
"""

# Findings the clean fixture is allowed to have, because the rule genuinely applies
# to it or the checker cannot know better. Keep this list short and justified.
CLEAN_ALLOWED: dict[str, str] = {}


def run_audit(path: Path, *extra: str) -> dict:
    import json

    proc = subprocess.run(
        [sys.executable, str(AUDIT), str(path), "--format", "json", "--max-per-rule", "500", *extra],
        capture_output=True,
        text=True,
        check=False,
    )
    if not proc.stdout.strip():
        raise SystemExit(f"audit produced no output (rc={proc.returncode}): {proc.stderr}")
    return json.loads(proc.stdout)


def check_violation_fixture() -> list[str]:
    failures: list[str] = []
    data = run_audit(FIXTURE, "--kind", "library")
    seen: dict[str, set[int]] = {}
    for f in data["findings"]:
        seen.setdefault(f["rule"], set()).add(f["line"])

    for rid, expected in EXPECT_VIOLATIONS.items():
        got = seen.get(rid, set())
        missing = expected - got
        if missing:
            failures.append(f"{rid}: expected at line(s) {sorted(missing)}, got {sorted(got) or 'none'}")

    for rid, forbidden_lines in MUST_NOT_FIRE_AT.items():
        hit = forbidden_lines & seen.get(rid, set())
        if hit:
            failures.append(f"{rid}: fired at line(s) {sorted(hit)}, which the rule must exclude")

    for rid in FORBIDDEN:
        if rid in seen:
            lines = sorted(seen[rid])
            failures.append(f"{rid}: false positive at line(s) {lines}")

    # Test-module code must not be flagged: everything from the `#[cfg(test)]` module
    # onwards is off-limits, which is what `is_test` gates in the detector. The boundary
    # comes from the fixture itself so adding lines above it cannot invalidate the check.
    test_start = next(
        i + 1
        for i, line in enumerate(FIXTURE.read_text(encoding="utf-8").splitlines())
        if line.strip().startswith("#[cfg(test)]")
    )
    for f in data["findings"]:
        if f["line"] >= test_start:
            failures.append(f"{f['rule']}: flagged test code at line {f['line']}")

    return failures


def check_clean_fixture() -> list[str]:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        clean = Path(td) / "clean.rs"
        clean.write_text(CLEAN_FIXTURE, encoding="utf-8")
        data = run_audit(clean, "--kind", "library")
        for f in data["findings"]:
            if f["rule"] in CLEAN_ALLOWED:
                continue
            failures.append(f"{f['rule']} false positive on clean code at line {f['line']}: {f['snippet']}")
    return failures


def check_suppressions() -> list[str]:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        base = "pub fn f(a: &String, b: &String) -> u8 { 0 }\n"
        plain = Path(td) / "plain.rs"
        plain.write_text(base, encoding="utf-8")
        if not run_audit(plain, "--kind", "library")["findings"]:
            failures.append("baseline: `&String` parameter was not detected at all")

        inline = Path(td) / "inline.rs"
        inline.write_text("// style-guide-audit: ignore API-01 — fixture\n" + base, encoding="utf-8")
        rules = {f["rule"] for f in run_audit(inline, "--kind", "library")["findings"]}
        if "API-01" in rules:
            failures.append("inline suppression did not suppress API-01")

        file_wide = Path(td) / "file.rs"
        file_wide.write_text("// style-guide-audit: file-ignore API-01\n" + base, encoding="utf-8")
        rules = {f["rule"] for f in run_audit(file_wide, "--kind", "library")["findings"]}
        if "API-01" in rules:
            failures.append("file-ignore did not suppress API-01")

        disabled = {f["rule"] for f in run_audit(plain, "--kind", "library", "--disable", "API-01")["findings"]}
        if "API-01" in disabled:
            failures.append("--disable API-01 did not suppress the finding")

        only = {f["rule"] for f in run_audit(plain, "--kind", "library", "--only", "ICN-03")["findings"]}
        if "API-01" in only:
            failures.append("--only ICN-03 still reported API-01")
    return failures


def check_scope_gating() -> list[str]:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        asyncfile = Path(td) / "async.rs"
        asyncfile.write_text(
            "pub async fn work() -> u8 { 1 }\n\npub fn call() {\n    let _ = work().await;\n}\n", encoding="utf-8"
        )
        any_scope = {f["rule"] for f in run_audit(asyncfile, "--kind", "library")["findings"]}
        if "CON-02" in any_scope:
            failures.append("CON-02 fired without --codebase chrome")
        chrome = {f["rule"] for f in run_audit(asyncfile, "--kind", "library", "--codebase", "chrome")["findings"]}
        if "CON-02" not in chrome:
            failures.append("CON-02 did not fire with --codebase chrome")

        # library-only doc rule must stay silent for application code
        undocumented = Path(td) / "app.rs"
        undocumented.write_text("pub fn run() -> u8 { 0 }\n", encoding="utf-8")
        lib = {f["rule"] for f in run_audit(undocumented, "--kind", "library")["findings"]}
        app = {f["rule"] for f in run_audit(undocumented, "--kind", "application")["findings"]}
        if "DOC-01" not in lib:
            failures.append("DOC-01 missing for --kind library")
        if "DOC-01" in app:
            failures.append("DOC-01 fired for --kind application")
    return failures


def check_exit_codes() -> list[str]:
    failures: list[str] = []
    plain = FIXTURE
    cases = [
        ("--fail-on error", 1),
        ("--fail-on never", 0),
    ]
    for extra, expected in cases:
        proc = subprocess.run(
            [sys.executable, str(AUDIT), str(plain), "--kind", "library", *extra.split()],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != expected:
            failures.append(f"{extra}: exit {proc.returncode}, expected {expected}")
    # A warning-only file with --fail-on error must exit 0.
    with tempfile.TemporaryDirectory() as td:
        warn_only = Path(td) / "warn.rs"
        warn_only.write_text("pub fn f(a: bool) -> u8 { 0 }\n", encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(AUDIT), str(warn_only), "--kind", "library", "--fail-on", "error"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            failures.append(f"warning-only file with --fail-on error exited {proc.returncode}")
    return failures


# The check groups, in the order they run. tests/test_audit.py parametrises over this list,
# so a new group is a pytest case without touching the test file.
GROUPS: list[tuple[str, Callable[[], list[str]]]] = [
    ("violations fixture", check_violation_fixture),
    ("clean fixture (false positives)", check_clean_fixture),
    ("suppressions", check_suppressions),
    ("scope gating", check_scope_gating),
    ("exit codes", check_exit_codes),
]


def main() -> int:
    total = 0
    for label, fn in GROUPS:
        failures = fn()
        total += len(failures)
        status = "PASS" if not failures else f"FAIL ({len(failures)})"
        print(f"[{status}] {label}")
        for f in failures:
            print(f"    - {f}")
    print(f"\n{'all checks passed' if total == 0 else f'{total} failure(s)'}")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
