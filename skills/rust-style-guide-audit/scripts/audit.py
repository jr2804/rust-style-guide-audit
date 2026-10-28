#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Deterministic heuristic audit of Rust code against the Google Rust Style Guide.

Every finding carries a rule ID that matches references/rules-catalog.md.
This script does the mechanical half of the audit: pattern-shaped violations.
The semantic half (API design, trait choice, module boundaries, naming intent)
is listed by --list-manual and must be judged by reading the code.

Exit code is 1 when a finding at or above --fail-on severity exists.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------
# Rule registry
# --------------------------------------------------------------------------

# severity: error | warning | note
# scope:    any | library | application | chrome | fuchsia
RULES: dict[str, dict[str, str]] = {}


def rule(rid: str, title: str, section: str, severity: str, scope: str, manual: bool = False) -> None:
    RULES[rid] = {
        "id": rid,
        "title": title,
        "section": section,
        "severity": severity,
        "scope": scope,
        "manual": "yes" if manual else "no",
    }


# Code organization
rule("ORG-01", "Prefer small, single-purpose crates", "Prefer small crates", "note", "chrome", manual=True)
rule("ORG-02", "Flat file layout inside one crate", "Use flat file layout", "note", "chrome")
rule(
    "ORG-03",
    "Name leaf modules after their primary item",
    "Name source files and leaf modules",
    "note",
    "any",
    manual=True,
)
rule("ORG-04", "No API implementation in non-leaf modules", "Don't implement APIs in non-leaf modules", "note", "any")

# Imports
rule("IMP-01", "No glob imports", "Don't use glob imports", "warning", "any")
rule(
    "IMP-02", "One module per `use` statement", "A use statement should import items from one module", "warning", "any"
)
rule(
    "IMP-03", "Qualify top-level function calls with the module", "Qualify calls to top-level functions", "note", "any"
)
rule("IMP-04", "Import type names and use them unqualified", "Type names should be imported", "note", "any")
rule(
    "IMP-05",
    "Import a trait inside the function that uses it",
    "Prefer locally-scoped trait imports",
    "note",
    "any",
    manual=True,
)
rule(
    "IMP-06",
    "Chrome code imports through `chromium::import!`",
    "Use the appropriate import mechanism",
    "note",
    "chrome",
    manual=True,
)

# Formatting
rule("FMT-01", "Rustfmt-clean, max 100 columns", "Use the appropriate formatting tool", "note", "any")
rule(
    "FMT-02",
    "`#[rustfmt::skip]` only for alignment or generated code",
    "Opting out of automatic formatting",
    "note",
    "any",
)

# Ownership
rule("OWN-01", "Avoid `Rc`/`Arc`", "Avoid Rc and Arc", "warning", "any")
rule("OWN-02", "Prefer borrows over deep copies", "Prefer borrows over deep copies", "note", "any")

# Function inputs and outputs
rule(
    "API-01",
    "Accept flexible references (`&T`, `&[T]`, `&str`, `Option<&T>`)",
    "Accept flexible references",
    "error",
    "any",
)
rule("API-02", "Prefer iterators over `Vec<T>` in return types", "Iterators vs owned collections", "note", "library")
rule(
    "API-03",
    "Prefer `impl IntoIterator` for iteration-only parameters",
    "Iterators vs slices in function parameters",
    "note",
    "library",
    manual=True,
)
rule("API-04", "`impl Into<T>` only where call-site ergonomics matter", "Accepting Into", "note", "application")
rule("API-05", "Prefer `enum` over `bool` in APIs", "Prefer enum over bool in APIs", "warning", "any")
rule(
    "API-06",
    "Pick the right failure mechanism (`Option`/`Result`/`panic!`)",
    "Reporting errors",
    "note",
    "any",
    manual=True,
)

# Types
rule("TYP-01", "Prefer newtypes over type aliases when semantics differ", "Newtypes versus type aliases", "note", "any")
rule("TYP-02", "Named fields over multi-field tuple structs", "Prefer named fields over tuples", "warning", "any")

# Traits
rule("TRT-01", "Add trait impls when they become necessary", "Add trait implementations", "note", "any", manual=True)
rule(
    "TRT-02",
    "Implement std traits instead of custom methods",
    "Implement known standard library traits",
    "warning",
    "any",
)
rule("TRT-03", "Prefer `#[derive]` over manual impls", "Use derive if possible", "note", "any")
rule("TRT-04", "Prefer generics over `dyn Trait` in parameters", "Generics versus dyn Trait", "note", "library")
rule(
    "TRT-05",
    "Define traits only for generics, `impl`/`dyn`, or extension",
    "When to define a trait",
    "note",
    "any",
    manual=True,
)
rule("TRT-06", "Extension traits use the `Ext` suffix", "Extension traits", "note", "any")
rule("TRT-07", "Pair important `From` impls with a constructor", "Pair important From impls", "note", "library")
rule("TRT-08", "Options structs implement `Default`", "Options structs should implement Default", "warning", "any")
rule(
    "TRT-09",
    "Implement `Copy`/`Clone`/`Default`/`PartialEq`/`Hash` where the guide expects them",
    "Specific guidance for important traits",
    "note",
    "any",
    manual=True,
)

# Concurrency
rule("CON-01", "Never reach inside a poisoned mutex", "Handling poison", "warning", "any")
rule("CON-02", "No `async`/`.await`", "Don't use async", "note", "chrome")
rule("CON-03", "No `std::thread` spawning", "Don't start new threads", "note", "chrome")
rule("CON-04", "Use `fuchsia_sync::Mutex`", "Use fuchsia_sync::Mutex", "note", "fuchsia")

# Macros
rule("MAC-01", "Prefer functions, types, traits over macros", "Macros", "note", "any")

# Naming
rule("NAM-01", "Follow std method naming (`as_`/`to_`/`into_`, no `get_`)", "Naming methods", "warning", "any")
rule("NAM-02", "Descriptive lifetime names for type lifetimes", "Naming lifetimes", "note", "any", manual=True)
rule("NAM-03", "Indicative generic parameter names", "Naming generic parameters", "note", "any", manual=True)
rule(
    "NAM-04",
    "Initialization functions are `new`/`new_with_foo`/`try_new`",
    "Naming initialization functions",
    "warning",
    "any",
)
rule("NAM-05", "Avoid project-local abbreviations", "Avoid abbreviations", "note", "any")
rule(
    "NAM-06", "`set_foo()` returns `()`; `replace_foo()` returns the old value", "Getters and setters", "warning", "any"
)

# Documentation
rule("DOC-01", "Document public APIs", "When and how to write documentation", "warning", "library")
rule("DOC-02", "Use `///` and `//!`, not block doc comments", "How to format documentation comments", "note", "any")
rule("DOC-03", "Document panic cases", "When and how to write documentation", "note", "any")

# Other features
rule("SAF-01", "`unsafe` needs a `SAFETY:` comment and justification", "Unsafe code", "error", "any")
rule("SAF-02", "No unstable features", "No unstable features", "error", "any")
rule("SAF-03", "Implement `len()` and `is_empty()` together", "Implement expected API sets together", "warning", "any")
rule("SAF-04", "`const fn` only when it will stay `const`", "Use const functions responsibly", "note", "library")
rule("SAF-05", "`#[non_exhaustive]` on public enums", "Apply non_exhaustive to enums", "note", "library")
rule(
    "SAF-06",
    "`#[non_exhaustive]` on public structs with public fields",
    "Apply non_exhaustive to structs",
    "note",
    "library",
)
rule("SAF-07", "`#[must_use]` where ignoring the return value is a bug", "must_use on functions", "note", "library")
rule("SAF-08", "No code running before `main()`", "Do not run code before main", "error", "any")
rule(
    "SAF-09",
    "Don't touch `#[doc(hidden)]` items you don't own",
    "Do not access doc(hidden) items",
    "warning",
    "any",
    manual=True,
)
rule(
    "SAF-10",
    "Operator overloads keep their mathematical meaning",
    "Avoid overloading for non-mathematical purposes",
    "note",
    "any",
    manual=True,
)
rule(
    "SAF-11",
    "`#[must_use]` on error and lazy-computation types, not only functions",
    "must_use on types",
    "note",
    "library",
)

# Implementation concerns
rule("ICN-01", "Don't overuse type inference", "Don't overuse type inference", "note", "any")
rule(
    "ICN-02",
    "Pattern matching over check-then-unwrap",
    "Prefer pattern matching over check-then-unwrap",
    "error",
    "any",
)
rule("ICN-03", "Prefer `expect` over `unwrap`", "Prefer expect over unwrap", "warning", "any")
rule("ICN-04", "Give assertions context strings", "Use context strings to clarify assertions", "note", "any")
rule("ICN-05", "Avoid `Iterator::for_each`", "Don't use iterator combinator chains", "note", "any")
rule("ICN-06", "Don't build combinator chains in a `for` header", "Don't use iterator combinator chains", "note", "any")
rule("ICN-07", "No `panic::catch_unwind`", "Don't call panic::catch_unwind", "error", "any")
rule("ICN-08", "`format!`/`write!` over `+` concatenation", "Prefer format!/write!", "note", "any")
rule(
    "ICN-09",
    "List `non_exhaustive` variants instead of a bare `_` arm",
    "Do not omit patterns on non_exhaustive enums",
    "note",
    "any",
    manual=True,
)

# Tests
rule(
    "TST-01",
    "Use the codebase's test framework",
    "Use the right per-codebase test framework",
    "note",
    "any",
    manual=True,
)

SEVERITY_ORDER = {"error": 3, "warning": 2, "note": 1}

# --------------------------------------------------------------------------
# Source model
# --------------------------------------------------------------------------


@dataclass
class Finding:
    rule: str
    path: str
    line: int
    message: str
    snippet: str = ""
    fix: str = ""

    def as_dict(self) -> dict:
        d = {
            "rule": self.rule,
            "title": RULES.get(self.rule, {}).get("title", ""),
            "severity": RULES.get(self.rule, {}).get("severity", "note"),
            "path": self.path,
            "line": self.line,
            "message": self.message,
            "snippet": self.snippet,
            "fix": self.fix,
        }
        return d


def strip_source(text: str) -> list[str]:
    """Blank out comments and literal bodies, preserving line count and columns."""
    return _strip(text, collapse_literals=False)


def strip_source_collapsed(text: str) -> list[str]:
    """Like `strip_source`, but literal bodies collapse to nothing.

    Used for the line-width check: rustfmt cannot reflow a string literal, so a long
    line whose length comes from literal text is not a formatting violation.
    """
    return _strip(text, collapse_literals=True)


def _strip(text: str, *, collapse_literals: bool) -> list[str]:
    out: list[str] = []
    i, n = 0, len(text)
    state = "normal"
    depth = 0
    hashes = 0
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if state == "normal":
            if ch == "/" and nxt == "/":
                state = "line"
                out.append("  ")
                i += 2
                continue
            if ch == "/" and nxt == "*":
                state = "block"
                depth = 1
                out.append("  ")
                i += 2
                continue
            if ch == '"':
                state = "string"
                out.append(" ")
                i += 1
                continue
            if ch == "'":
                if nxt == "\\":
                    state = "char"
                    out.append(" ")
                    i += 1
                    continue
                if i + 2 < n and text[i + 2] == "'" and nxt not in ("", "\n"):
                    state = "char"
                    out.append(" ")
                    i += 1
                    continue
                out.append(ch)
                i += 1
                continue
            if ch == "r" and nxt in ('"', "#") and (i == 0 or not (text[i - 1].isalnum() or text[i - 1] == "_")):
                j = i + 1
                h = 0
                while j < n and text[j] == "#":
                    h += 1
                    j += 1
                if j < n and text[j] == '"':
                    state = "raw"
                    hashes = h
                    out.append(" ")
                    i = j + 1
                    continue
            out.append(ch)
            i += 1
            continue
        if state == "line":
            if ch == "\n":
                state = "normal"
                out.append("\n")
            else:
                out.append(" ")
            i += 1
            continue
        if state == "block":
            if ch == "/" and nxt == "*":
                depth += 1
                out.append("  ")
                i += 2
                continue
            if ch == "*" and nxt == "/":
                depth -= 1
                out.append("  ")
                i += 2
                if depth == 0:
                    state = "normal"
                continue
            out.append("\n" if ch == "\n" else " ")
            i += 1
            continue
        if state == "string":
            if ch == "\\":
                # A backslash-newline continuation inside a literal consumes a newline;
                # keep its line so the stripped copy stays line-aligned with the source.
                if nxt == "\n":
                    out.append("\n")
                elif not collapse_literals:
                    out.append("  ")
                i += 2
                continue
            if ch == '"':
                state = "normal"
                out.append(" ")
                i += 1
                continue
            if ch == "\n":
                out.append("\n")
            elif not collapse_literals:
                out.append(" ")
            i += 1
            continue
        if state == "raw":
            if ch == '"':
                j = i + 1
                seen = 0
                while j < n and text[j] == "#" and seen < hashes:
                    seen += 1
                    j += 1
                if seen == hashes:
                    state = "normal"
                    out.append(" " + " " * hashes)
                    i = j
                    continue
            if ch == "\n":
                out.append("\n")
            elif not collapse_literals:
                out.append(" ")
            i += 1
            continue
        if state == "char":
            if ch == "\\":
                if nxt == "\n":
                    out.append("\n")
                elif not collapse_literals:
                    out.append("  ")
                i += 2
                continue
            if ch == "'":
                state = "normal"
                out.append(" ")
                i += 1
                continue
            if not collapse_literals:
                out.append(" ")
            i += 1
            continue
    return "".join(out).split("\n")


FN_RE = re.compile(
    r"^(?P<indent>\s*)"
    r"(?P<vis>pub(?:\s*\([^)]*\))?\s+)?"
    r"(?:(?:const|async|unsafe|extern)\s+)*"
    r"fn\s+(?P<name>\w+)"
)
STRUCT_RE = re.compile(r"^\s*(pub(?:\s*\([^)]*\))?\s+)?struct\s+(?P<name>\w+)")
ENUM_RE = re.compile(r"^\s*(pub(?:\s*\([^)]*\))?\s+)?enum\s+(?P<name>\w+)")
IMPL_RE = re.compile(r"^\s*impl(?:<[^>]*>)?\s+(?P<name>[\w:<>]+)")
TRAIT_RE = re.compile(r"^\s*(pub(?:\s*\([^)]*\))?\s+)?trait\s+(?P<name>\w+)")
# A module path followed by a capitalised name: `std::collections::HashMap`, `regex::Regex`.
TYPE_PATH_RE = re.compile(r"(?<![\w:])((?:(?:[a-z_]\w*)::)+)([A-Z]\w*)\b")


@dataclass
class SourceFile:
    path: str
    raw: list[str]
    code: list[str]
    narrow: list[str] = field(default_factory=list)
    suppressed: dict[int, set[str]] = field(default_factory=dict)
    file_suppressed: set[str] = field(default_factory=set)
    in_test: list[bool] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path, root: Path) -> SourceFile:
        text = path.read_text(encoding="utf-8", errors="replace")
        raw = text.split("\n")
        code = strip_source(text)
        narrow = strip_source_collapsed(text)
        if len(code) < len(raw):
            code += [""] * (len(raw) - len(code))
        if len(narrow) < len(raw):
            narrow += [""] * (len(raw) - len(narrow))
        rel = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
        f = cls(path=rel, raw=raw, code=code[: len(raw)], narrow=narrow[: len(raw)])
        f._parse_suppressions()
        f._mark_tests(rel)
        return f

    def _parse_suppressions(self) -> None:
        for idx, line in enumerate(self.raw):
            m = re.search(r"style-guide-audit:\s*(file-ignore|ignore)\s*([A-Z]{3}-\d{2}[,\s]*)*", line)
            if not m:
                continue
            ids = re.findall(r"[A-Z]{3}-\d{2}", line)
            if m.group(1) == "file-ignore":
                if ids:
                    self.file_suppressed.update(ids)
                else:
                    self.file_suppressed.add("*")
            else:
                self.suppressed.setdefault(idx + 1, set()).update(ids or ["*"])
                self.suppressed.setdefault(idx + 2, set()).update(ids or ["*"])

    def _mark_tests(self, rel: str) -> None:
        self.in_test = [False] * len(self.raw)
        if "/tests/" in rel.replace("\\", "/") or rel.startswith("tests/"):
            self.in_test = [True] * len(self.raw)
            return
        depth = 0
        active = False
        for idx, line in enumerate(self.code):
            if re.search(r"#\[cfg\(test\)\]", line):
                active = True
                depth = 0
            if active:
                depth += line.count("{") - line.count("}")
                self.in_test[idx] = True
                if depth <= 0 and "}" in line:
                    active = False

    def is_test(self, line_no: int) -> bool:
        i = line_no - 1
        return 0 <= i < len(self.in_test) and self.in_test[i]

    def module_path(self) -> str:
        """Best-effort `crate::a::b` path for this file, used by the IMP-03 ancestor rule."""
        parts = Path(self.path.replace("\\", "/")).parts
        if "src" not in parts:
            # Integration tests (`tests/foo.rs`) and benches live outside `src`; treat them as
            # their own leaf module so the ancestor check still applies to `crate::*` imports.
            stem = Path(parts[-1]).stem
            return f"crate::{stem}" if parts else ""
        idx = len(parts) - 1 - parts[::-1].index("src")
        tail = list(parts[idx + 1 : -1])
        stem = Path(parts[-1]).stem
        if stem not in ("lib", "main", "mod"):
            tail.append(stem)
        return "::".join(["crate", *tail]) if tail else "crate"

    def is_ancestor_module(self, path: str) -> bool:
        """True when `path` names this module or one of its ancestors (guide's IMP-03 exception)."""
        if path in ("super", "self", "crate"):
            return True
        if path.startswith("super::") or path == "super":
            return True
        current = self.module_path()
        if not current:
            return False
        return path == current or current.startswith(path + "::")

    def suppression_for(self, line_no: int, rid: str) -> bool:
        if "*" in self.file_suppressed or rid in self.file_suppressed:
            return True
        ids = self.suppressed.get(line_no, set())
        return "*" in ids or rid in ids


def fn_spans(sf: SourceFile) -> list[tuple[int, int, str]]:
    """(start_line, end_line, name) 1-based, inclusive, by brace matching."""
    spans: list[tuple[int, int, str]] = []
    lines = sf.code
    for idx, line in enumerate(lines):
        m = FN_RE.match(line)
        if not m:
            continue
        depth = 0
        started = False
        end = idx
        for j in range(idx, min(len(lines), idx + 4000)):
            depth += lines[j].count("{") - lines[j].count("}")
            if "{" in lines[j]:
                started = True
            if started and depth <= 0:
                end = j
                break
            end = j
        spans.append((idx + 1, end + 1, m.group("name")))
    return spans


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

ABBREVIATIONS_OK = {
    "buf",
    "idx",
    "len",
    "ptr",
    "cfg",
    "arg",
    "args",
    "num",
    "src",
    "dst",
    "tmp",
    "id",
    "url",
    "api",
    "cpu",
    "fft",
    "dsp",
    "pcm",
    "mos",
    "asl",
    "bgn",
    "snr",
    "swb",
    "nb",
    "fb",
    "db",
    "sd",
    "rms",
    "thr",
    "var",
    "std",
    "ms",
    "hz",
    "khz",
    "lsb",
    "vad",
    "sqrt",
    "str",
    "max",
    "min",
    "abs",
    "exp",
    "log",
    "sin",
    "cos",
    "tan",
    "vec",
    "iter",
    "ref",
    "mut",
    "impl",
    "dyn",
    "self",
}

# Project-local abbreviations worth spelling out. Kept as an explicit table instead of a
# consonant heuristic: `sqrt`, `str`, `ptr`, `std` and friends are all short consonant runs
# and a heuristic would flag them all.
ABBREVIATIONS_SPELL_OUT = {
    "cnt": "count",
    "mgr": "manager",
    "prm": "param",
    "prms": "params",
    "snd": "sender",
    "rcv": "receiver",
    "cfg": "config (only when it is not the `#[cfg]` attribute)",
    "coef": "coefficient",
    "elem": "element",
    "elems": "elements",
    "attr": "attribute",
    "attrs": "attributes",
    "usr": "user",
    "pkg": "package",
    "wnd": "window",
    "frm": "frame",
    "frms": "frames",
    "chnl": "channel",
    "chnls": "channels",
}
LINT_ALLOW_RE = re.compile(r"#\[allow\(")


def check_imports(sf: SourceFile, out: list[Finding]) -> None:
    imported: set[str] = set()
    qualified: dict[str, list[tuple[int, int]]] = {}
    source_text = "\n".join(sf.code)
    for line in sf.code:
        m = re.match(r"^\s*(?:pub(?:\([^)]*\))?\s+)?use\s+([^;]+);", line)
        if m:
            imported.update(re.findall(r"\b([A-Z]\w*)\b", m.group(1)))
    for idx, line in enumerate(sf.code):
        lineno = idx + 1
        if re.match(r"^\s*(pub(\([^)]*\))?\s+)?use\s+[^;]*::\*", line):
            allowed = re.match(r"^\s*(pub(\([^)]*\))?\s+)?use\s+(super|crate)::\*", line)
            if not allowed:
                out.append(
                    Finding(
                        "IMP-01",
                        sf.path,
                        lineno,
                        "glob import",
                        sf.raw[idx].strip(),
                        "List the imported items explicitly.",
                    )
                )
        m = re.match(r"^\s*(pub(\([^)]*\))?\s+)?use\s+([\w:]+)::\{([^}]*)\}", line)
        if m and "::" in m.group(4):
            out.append(
                Finding(
                    "IMP-02",
                    sf.path,
                    lineno,
                    "`use` group spans several modules",
                    sf.raw[idx].strip(),
                    "Split into one `use` per module.",
                )
            )
        # IMP-03: `use mod::func;` followed by unqualified `func()` calls. The regex alone
        # cannot tell a module import (`use std::mem;` then `mem::transmute(..)`) from a
        # function import, so the file's own usage decides: a name that is ever used as a
        # path qualifier was imported as a module, and a `pub use` re-export exports a name
        # instead of calling it. The guide's rule is about call sites only.
        m = re.match(r"^\s*(pub(\([^)]*\))?\s+)?use\s+([\w:]+)::([a-z_][\w]*)\s*;", line)
        if m and m.group(4) not in ("self", "super", "crate"):
            path, name = m.group(3), m.group(4)
            re_exported = m.group(1) is not None
            used_as_module = re.search(rf"\b{re.escape(name)}::", source_text) is not None
            calls_unqualified = re.search(rf"(?<![\w:.]){re.escape(name)}\s*\(", source_text) is not None
            if not re_exported and calls_unqualified and not used_as_module and not sf.is_ancestor_module(path):
                out.append(
                    Finding(
                        "IMP-03",
                        sf.path,
                        lineno,
                        f"function `{name}` imported unqualified",
                        sf.raw[idx].strip(),
                        f"`use {path};` then call `{path.split('::')[-1]}::{name}()`.",
                    )
                )  # IMP-04: a type reached through its module path instead of an import. Macros
        # (`!`), attributes and `use` lines are exempt, as are paths rooted at
        # `crate`/`self`/`super` and names already imported above. The guide accepts
        # leaving rare types qualified, so a path is only reported when the file uses it
        # more than once - that is where an import pays for itself and the reviewer agrees.
        if "!" in line or line.lstrip().startswith(("impl ", "#[", "use ")):
            continue
        for m in TYPE_PATH_RE.finditer(line):
            prefix, type_name = m.group(1), m.group(2)
            if prefix.split("::")[0] in ("crate", "self", "super") or type_name in imported:
                continue
            if type_name.isupper():
                continue  # `f64::INFINITY`, `std::f64::consts::PI`: a constant, not a type.
            qualified.setdefault(prefix + type_name, []).append((lineno, idx))
    for qualified_path, uses in qualified.items():
        if len(uses) < 2:
            continue
        lineno, idx = uses[0]
        type_name = re.split(r"::", qualified_path)[-1]
        out.append(
            Finding(
                "IMP-04",
                sf.path,
                lineno,
                f"`{qualified_path}` used {len(uses)} times through its module path",
                sf.raw[idx].strip(),
                f"Import `{type_name}` (`use {qualified_path};`) and use it unqualified.",
            )
        )


def check_formatting(sf: SourceFile, out: list[Finding], width: int) -> None:
    for idx, line in enumerate(sf.code):
        raw = sf.raw[idx] if idx < len(sf.raw) else ""
        if "#[rustfmt::skip]" in line:
            out.append(
                Finding(
                    "FMT-02",
                    sf.path,
                    idx + 1,
                    "rustfmt opt-out",
                    raw.strip(),
                    "Only for manual alignment or generated code; delete otherwise.",
                )
            )
        # Measure the shape rustfmt can change: code, not comment or literal text.
        narrow = sf.narrow[idx] if idx < len(sf.narrow) else line
        if len(narrow.rstrip()) > width and not LINT_ALLOW_RE.search(raw):
            out.append(
                Finding(
                    "FMT-01",
                    sf.path,
                    idx + 1,
                    f"code exceeds {width} columns",
                    raw.strip()[:140],
                    "Reformat with rustfmt (max_width = 100).",
                )
            )


def check_ownership(sf: SourceFile, out: list[Finding]) -> None:
    spans = fn_spans(sf)
    for idx, line in enumerate(sf.code):
        if re.search(r"\b(Rc|Arc)<", line) and not sf.is_test(idx + 1):
            out.append(
                Finding(
                    "OWN-01",
                    sf.path,
                    idx + 1,
                    "shared-ownership pointer",
                    sf.raw[idx].strip(),
                    "Use unique ownership or borrows unless the ownership graph is unworkable.",
                )
            )
    for start, end, name in spans:
        body = "\n".join(sf.code[start - 1 : end])
        clones = body.count(".clone()")
        if clones >= 6:
            out.append(
                Finding(
                    "OWN-02",
                    sf.path,
                    start,
                    f"`{name}` calls `.clone()` {clones} times",
                    sf.raw[start - 1].strip(),
                    "Check whether these are genuine deep copies or borrow-checker workarounds.",
                )
            )


def check_api(sf: SourceFile, out: list[Finding], kind: str) -> None:
    for idx, line in enumerate(sf.code):
        lineno = idx + 1
        if not FN_RE.match(line):
            continue
        externally_visible = (
            bool(re.match(r"^\s*pub\s", line)) and "pub(crate)" not in line and "pub(super)" not in line
        )
        signature_end = idx
        while signature_end < len(sf.code) and "{" not in sf.code[signature_end] and signature_end - idx < 12:
            signature_end += 1
        sig = " ".join(sf.code[idx : signature_end + 1])
        for m in re.finditer(r"&(Vec|String|Box|Option|PathBuf|Cow)(?:<|\b)", sig):
            what = m.group(1)
            good = {
                "Vec": "&[T]",
                "String": "&str",
                "Box": "&T",
                "Option": "Option<&T>",
                "PathBuf": "&Path",
                "Cow": "&str",
            }[what]
            pos = "return type" if "->" in sig and sig.index("->") < m.start() else "parameter"
            out.append(
                Finding("API-01", sf.path, lineno, f"`&{what}` in {pos}", sf.raw[idx].strip(), f"Use `{good}` instead.")
            )
        if kind == "library" and externally_visible and re.search(r"->\s*(Vec|String)<", sig):
            out.append(
                Finding(
                    "API-02",
                    sf.path,
                    lineno,
                    "owned collection returned from public library API",
                    sf.raw[idx].strip(),
                    "Return `impl Iterator<Item = _>` when callers do not need indexing.",
                )
            )
        if kind == "application" and "impl Into<" in sig:
            out.append(
                Finding(
                    "API-04",
                    sf.path,
                    lineno,
                    "`impl Into<T>` parameter in application code",
                    sf.raw[idx].strip(),
                    "Application code should take the concrete type.",
                )
            )
        seen_flags: set[str] = set()
        for m in re.finditer(r"(\w+)\s*:\s*bool\b", sig):
            flag = m.group(1)
            if flag in seen_flags:
                continue
            seen_flags.add(flag)
        if seen_flags:
            names = ", ".join(f"`{f}`" for f in sorted(seen_flags))
            out.append(
                Finding(
                    "API-05",
                    sf.path,
                    lineno,
                    f"bool parameter(s): {names}",
                    sf.raw[idx].strip(),
                    "Use a two-variant enum, or add an inline comment naming each flag.",
                )
            )
        if re.search(r"Result<[^>]*(String|&str)\s*>", sig):
            out.append(
                Finding(
                    "API-06",
                    sf.path,
                    lineno,
                    "stringly-typed error",
                    sf.raw[idx].strip(),
                    "Define an error enum implementing `std::error::Error`.",
                )
            )


def check_types(sf: SourceFile, out: list[Finding]) -> None:
    for idx, line in enumerate(sf.code):
        lineno = idx + 1
        if re.match(r"^\s*(pub(\([^)]*\))?\s+)?type\s+\w+\s*=", line):
            out.append(
                Finding(
                    "TYP-01",
                    sf.path,
                    lineno,
                    "type alias",
                    sf.raw[idx].strip(),
                    "Use a newtype if the type has distinct semantics or needs its own API.",
                )
            )
        m = re.match(r"^\s*(pub(\([^)]*\))?\s+)?struct\s+\w+\s*[(<]", line)
        if m and line.rstrip().endswith(";"):
            fields = line.split("(")[1].split(")")[0] if "(" in line else ""
            if fields.count(",") >= 1 and "," in fields:
                out.append(
                    Finding(
                        "TYP-02", sf.path, lineno, "multi-field tuple struct", sf.raw[idx].strip(), "Name the fields."
                    )
                )


def check_traits(sf: SourceFile, out: list[Finding], kind: str) -> None:
    text = "\n".join(sf.code)
    for idx, line in enumerate(sf.code):
        lineno = idx + 1
        if re.search(r"\bfn\s+(from_str|to_string|from_iter|default|from)\s*\(", line):
            out.append(
                Finding(
                    "TRT-02",
                    sf.path,
                    lineno,
                    "custom method duplicating a std trait",
                    sf.raw[idx].strip(),
                    "Implement the std trait (`FromStr`, `Display`, ...).",
                )
            )
        m = re.search(r"\bimpl\s+(Default|Clone|Debug|PartialEq|Eq|Hash|PartialOrd|Ord|Copy)\s+for\b", line)
        if m:
            out.append(
                Finding(
                    "TRT-03",
                    sf.path,
                    lineno,
                    f"manual `impl {m.group(1)}`",
                    sf.raw[idx].strip(),
                    f"Derive it: `#[derive({m.group(1)})]`.",
                )
            )
        if kind == "library" and "dyn " in line and re.search(r"(:|->)\s*[&(]?\s*(Box<)?dyn\s+\w+", line):
            out.append(
                Finding(
                    "TRT-04",
                    sf.path,
                    lineno,
                    "`dyn Trait` in a library signature",
                    sf.raw[idx].strip(),
                    "Prefer `impl Trait` or a generic parameter unless code size matters.",
                )
            )
        if re.search(r"\bimpl\s+From<", line):
            window = "\n".join(sf.code[idx : idx + 40])
            if not re.search(r"fn\s+(new|try_new|from_\w+)\s*\(", window):
                out.append(
                    Finding(
                        "TRT-07",
                        sf.path,
                        lineno,
                        "`From` impl without a paired constructor",
                        sf.raw[idx].strip(),
                        "Add `::new()`, `::try_new()` or `::from_foo()`.",
                    )
                )
        options_match = re.match(r"^(\s*)(pub(\([^)]*\))?\s+)?struct\s+(\w*(Options|Config|Params|Settings))\b", line)
        if options_match:
            name = options_match.group(4)
            if (
                f"impl Default for {name}" not in text
                and "#[derive(Default" not in text
                and f"Default for {name}" not in text
            ):
                out.append(
                    Finding(
                        "TRT-08",
                        sf.path,
                        lineno,
                        f"options struct `{name}` lacks `Default`",
                        sf.raw[idx].strip(),
                        f"Add `#[derive(Default)]` or `impl Default for {name}`.",
                    )
                )
        tr = TRAIT_RE.match(line)
        if tr:
            name = tr.group("name")
            if name.endswith("Ext"):
                continue
            window = "\n".join(sf.code[idx : idx + 200])
            foreign_impl = re.search(rf"impl\s+{re.escape(name)}\s+for\s+(\w+)", window)
            if foreign_impl and not re.search(r"fn\s+\w+\([^)]*\)\s*(->\s*[^{]*)?;?\s*$", line):
                impl_of_self = re.search(rf":\s*{re.escape(name)}\b|impl\s+{re.escape(name)}\s+for\b", window)
                if not impl_of_self:
                    out.append(
                        Finding(
                            "TRT-06",
                            sf.path,
                            lineno,
                            f"trait `{name}` looks like an extension trait",
                            sf.raw[idx].strip(),
                            f"Rename to `{name}Ext` if it only adds methods to a foreign type.",
                        )
                    )


def check_concurrency(sf: SourceFile, out: list[Finding], codebase: str) -> None:
    for idx, line in enumerate(sf.code):
        lineno = idx + 1
        if re.search(r"PoisonError::into_inner|\.lock\(\)\s*\.unwrap\(\)|\.lock\(\)\s*\.expect\(", line):
            out.append(
                Finding(
                    "CON-01",
                    sf.path,
                    lineno,
                    "recovers from a poisoned mutex",
                    sf.raw[idx].strip(),
                    "Propagate the poison instead of reaching inside.",
                )
            )
        if codebase == "chrome":
            if re.search(r"\basync\s+fn\b|\.await\b", line):
                out.append(
                    Finding(
                        "CON-02",
                        sf.path,
                        lineno,
                        "`async`/`.await`",
                        sf.raw[idx].strip(),
                        "Chromium forbids async/await in Rust.",
                    )
                )
            if re.search(r"\bthread::spawn\b|\bstd::thread::spawn\b", line):
                out.append(
                    Finding(
                        "CON-03",
                        sf.path,
                        lineno,
                        "std thread spawn",
                        sf.raw[idx].strip(),
                        "Use sequences instead of threads.",
                    )
                )
        if codebase == "fuchsia" and re.search(r"std::sync::Mutex|parking_lot", line):
            out.append(
                Finding(
                    "CON-04", sf.path, lineno, "non-Fuchsia mutex", sf.raw[idx].strip(), "Use `fuchsia_sync::Mutex`."
                )
            )


def check_macros(sf: SourceFile, out: list[Finding]) -> None:
    for idx, line in enumerate(sf.code):
        if re.search(r"macro_rules!\s+\w+|#\[proc_macro", line):
            out.append(
                Finding(
                    "MAC-01",
                    sf.path,
                    idx + 1,
                    "macro definition",
                    sf.raw[idx].strip(),
                    "Prefer a function/type/trait; macros impair tooling and LSCs.",
                )
            )


def check_naming(sf: SourceFile, out: list[Finding]) -> None:
    spans = fn_spans(sf)
    for idx, line in enumerate(sf.code):
        m = FN_RE.match(line)
        if not m:
            continue
        name = m.group("name")
        if name.startswith("get_") and name != "get_or_insert":
            out.append(
                Finding(
                    "NAM-01",
                    sf.path,
                    idx + 1,
                    f"`get_`-prefixed getter `{name}`",
                    sf.raw[idx].strip(),
                    "Use `foo()` for `&T`, `foo_mut()` for `&mut T`.",
                )
            )
        if name in ("initialize", "init") or (name.startswith("create_") and "->" in line and "Self" in line):
            out.append(
                Finding(
                    "NAM-04",
                    sf.path,
                    idx + 1,
                    f"non-standard constructor `{name}`",
                    sf.raw[idx].strip(),
                    "Use `new()`, `new_with_foo()` or `try_new()`.",
                )
            )
        if name.startswith("as_") and "->" in line and not re.search(r"->\s*&", line):
            out.append(
                Finding(
                    "NAM-01",
                    sf.path,
                    idx + 1,
                    "`as_` prefix returns an owned value",
                    sf.raw[idx].strip(),
                    "Use `to_` for owned conversions.",
                )
            )
        # NAM-06: the guide pairs `set_foo()` (returns `()`) with `replace_foo()` (returns the
        # old value). A `set_` that returns something hides the old value under the wrong name.
        if name.startswith("set_") and re.search(r"->\s*(?!\(\s*\))\S", line):
            out.append(
                Finding(
                    "NAM-06",
                    sf.path,
                    idx + 1,
                    f"`{name}` is a setter that returns a value",
                    sf.raw[idx].strip(),
                    f"Rename to `replace_{name[len('set_') :]}` when the old value escapes.",
                )
            )
        if name.startswith("replace_") and ("->" not in line or re.search(r"->\s*\(\s*\)|->\s*$", line)):
            out.append(
                Finding(
                    "NAM-06",
                    sf.path,
                    idx + 1,
                    f"`{name}` returns nothing",
                    sf.raw[idx].strip(),
                    f"Rename to `set_{name[len('replace_') :]}`; `replace_` returns the old value.",
                )
            )
    for start, end, _name in spans:
        for idx in range(start - 1, end):
            line = sf.code[idx]
            for ident in re.findall(r"\b[a-z][a-z0-9_]{2,}\b", line):
                if "_" in ident or ident in ABBREVIATIONS_OK:
                    continue
                if ident in ABBREVIATIONS_SPELL_OUT:
                    out.append(
                        Finding(
                            "NAM-05",
                            sf.path,
                            idx + 1,
                            f"abbreviated identifier `{ident}`",
                            sf.raw[idx].strip(),
                            f"Spell it out (`{ABBREVIATIONS_SPELL_OUT[ident]}`).",
                        )
                    )
                    break


def check_docs(sf: SourceFile, out: list[Finding], kind: str) -> None:
    for idx, line in enumerate(sf.code):
        lineno = idx + 1
        if re.match(r"^\s*/\*[*!]", sf.raw[idx]):
            out.append(
                Finding("DOC-02", sf.path, lineno, "block doc comment", sf.raw[idx].strip(), "Use `///` or `//!`.")
            )
        if sf.is_test(lineno):
            continue
        # Only externally visible items are part of the documented API surface;
        # `pub(crate)`/`pub(super)` are internal.
        # `pub mod foo;` is a declaration: the docs live as `//!` in `foo.rs`.
        is_pub = bool(re.match(r"^\s*pub\s+(fn|struct|enum|trait|const|static|type)\b", line))
        if not is_pub or kind != "library":
            continue
        documented = False
        for back in range(1, 7):
            j = idx - back
            if j < 0:
                break
            prev = sf.raw[j].strip()
            if prev.startswith(("///", "//!", "#[doc")):
                documented = True
                break
            if prev and not prev.startswith("#["):
                break
        if not documented:
            out.append(
                Finding(
                    "DOC-01",
                    sf.path,
                    lineno,
                    "public item without a doc comment",
                    sf.raw[idx].strip(),
                    "Add `///` docs describing behaviour and invariants.",
                )
            )
        if re.match(r"^\s*pub\s+fn\b", line):
            spans = {s for s, _e, _n in fn_spans(sf)}
            end = lineno
            for j in range(idx, min(len(sf.code), idx + 200)):
                if j + 1 in spans and j > idx:
                    break  # nested fn: its panics are its own
                if re.search(r"\bpanic!|\bunreachable!|\bunwrap\(\)|\bexpect\(", sf.code[j]):
                    end = j + 1
                    break
            if end > lineno:
                doc_block = "\n".join(sf.raw[max(0, idx - 6) : idx])
                if "# Panics" not in doc_block:
                    out.append(
                        Finding(
                            "DOC-03",
                            sf.path,
                            lineno,
                            "panicking public function without `# Panics`",
                            sf.raw[idx].strip(),
                            "Document the panic conditions.",
                        )
                    )


def check_unsafe_and_attrs(sf: SourceFile, out: list[Finding]) -> None:
    text = "\n".join(sf.code)
    forbidden_unsafe = "#![forbid(unsafe_code)]" in text or "#![deny(unsafe_code)]" in text
    for idx, line in enumerate(sf.code):
        lineno = idx + 1
        if re.search(r"\bunsafe\s*(fn|\{|\"|impl|trait)", line) and not forbidden_unsafe:
            window = "\n".join(sf.raw[max(0, idx - 4) : idx + 1])
            if "SAFETY:" not in window:
                out.append(
                    Finding(
                        "SAF-01",
                        sf.path,
                        lineno,
                        "`unsafe` without a `SAFETY:` comment",
                        sf.raw[idx].strip(),
                        "Add `// SAFETY: ...` explaining why the invariants hold.",
                    )
                )
        if "#![feature(" in line:
            out.append(
                Finding("SAF-02", sf.path, lineno, "unstable feature gate", sf.raw[idx].strip(), "Stable Rust only.")
            )
        if re.search(r"\bctor::|#\[ctor", line):
            out.append(
                Finding(
                    "SAF-08",
                    sf.path,
                    lineno,
                    "code runs before `main()`",
                    sf.raw[idx].strip(),
                    "Move initialisation into `main`.",
                )
            )
        if re.match(r"^\s*pub\s+const\s+fn\b", line):
            out.append(
                Finding(
                    "SAF-04",
                    sf.path,
                    lineno,
                    "public `const fn`",
                    sf.raw[idx].strip(),
                    "Only mark `const` if you can keep it `const`; reverting is a breaking change.",
                )
            )
    # len/is_empty pairing
    if re.search(r"\bfn\s+len\s*\(", text) and not re.search(r"\bfn\s+is_empty\s*\(", text):
        for idx, line in enumerate(sf.code):
            if re.search(r"\bfn\s+len\s*\(", line):
                out.append(
                    Finding(
                        "SAF-03",
                        sf.path,
                        idx + 1,
                        "`len()` without `is_empty()`",
                        sf.raw[idx].strip(),
                        "Implement `is_empty()` alongside `len()`.",
                    )
                )
                break
    # must_use on ignored-by-default results
    for idx, line in enumerate(sf.code):
        if not re.search(r"\bfn\s+\w+", line) or not re.search(r"->\s*Result<", line):
            continue
        if not re.search(r"^\s*pub\b", line):
            continue
        window = "\n".join(sf.code[max(0, idx - 3) : idx])
        if "must_use" not in window:
            out.append(
                Finding(
                    "SAF-07",
                    sf.path,
                    idx + 1,
                    "`Result`-returning public function without `#[must_use]`",
                    sf.raw[idx].strip(),
                    "Add `#[must_use]` so an ignored failure is visible.",
                )
            )
    # SAF-11: `#[must_use]` belongs on the type when the type is the thing that must not be
    # dropped - error types and lazy computations, the two cases the guide names.
    for idx, line in enumerate(sf.code):
        m = STRUCT_RE.match(line) or ENUM_RE.match(line)
        if not m or not re.match(r"^\s*pub\s", line):
            continue
        type_name = m.group("name")
        if not type_name.endswith(("Error", "Err")):
            continue
        window = "\n".join(sf.code[max(0, idx - 3) : idx + 1])
        if "must_use" not in window:
            out.append(
                Finding(
                    "SAF-11",
                    sf.path,
                    idx + 1,
                    f"error type `{type_name}` without `#[must_use]`",
                    sf.raw[idx].strip(),
                    "Add `#[must_use]` so an ignored error value is reported.",
                )
            )
    # non_exhaustive
    for idx, line in enumerate(sf.code):
        m = ENUM_RE.match(line)
        if m and "pub" in line:
            window = "\n".join(sf.code[max(0, idx - 3) : idx + 1])
            if "non_exhaustive" not in window:
                out.append(
                    Finding(
                        "SAF-05",
                        sf.path,
                        idx + 1,
                        "public enum without `#[non_exhaustive]`",
                        sf.raw[idx].strip(),
                        "Add `#[non_exhaustive]` unless the variant set will never grow.",
                    )
                )
        m = STRUCT_RE.match(line)
        if m and "pub" in line:
            end = idx + 1
            for j in range(idx + 1, min(len(sf.code), idx + 60)):
                if sf.code[j].strip().startswith("}"):
                    end = j
                    break
            body = "\n".join(sf.code[idx:end])
            window = "\n".join(sf.code[max(0, idx - 3) : idx + 1])
            if (
                re.search(r"^\s*pub\s+\w+:", body, re.MULTILINE)
                and "non_exhaustive" not in window
                and "pub(crate)" not in line
            ):
                out.append(
                    Finding(
                        "SAF-06",
                        sf.path,
                        idx + 1,
                        "public struct with public fields without `#[non_exhaustive]`",
                        sf.raw[idx].strip(),
                        "Add `#[non_exhaustive]`, or document that the field set is frozen.",
                    )
                )


def _statement_prefix(body: list[str], offset: int) -> str:
    """Return the statement containing `body[offset]`, joined across lines.

    Walks backwards until the previous statement ends (`;`) or a `let …: Type` annotation
    is reached, so a conversion inside a wrapped `let`/`match` block is read together with
    the annotation that fixes its target type.
    """
    annotation = r"\blet\s+(\w+|\()\s*[^=]*:\s*[\w&]"
    start = offset
    while start > 0 and offset - start < 14:
        prev = body[start - 1]
        if re.search(annotation, prev):
            start -= 1
            break
        if ";" in prev:
            break
        start -= 1
    return "\n".join(body[start : offset + 1])


def _bound_by_annotation(body: list[str], offset: int) -> bool:
    """True when the value at `offset` is inside a `let …: Type = { … }` block.

    In `let x: T = { match e { A => A::Foo.into() } }` the conversion's target type is the
    `let` annotation several lines up; the block form defeats a same-line check.
    """
    for back in range(1, 9):
        if offset - back < 0:
            return False
        line = body[offset - back]
        if ";" in line:
            return False
        if re.search(r"\blet\s+(\w+|\()\s*[^=]*:\s*[\w&]", line):
            return True
    return False


def check_impl_concerns(sf: SourceFile, out: list[Finding]) -> None:
    spans = fn_spans(sf)
    for start, end, _name in spans:
        if sf.is_test(start):
            continue
        body = sf.code[start - 1 : end]
        for offset, line in enumerate(body):
            lineno = start + offset
            if ".unwrap()" in line:
                ctx = "\n".join(body[max(0, offset - 6) : offset + 1])
                in_match_arm = bool(
                    re.search(r"=>\s*\{?\s*$", line)
                    or re.search(r"=>", body[offset + 1] if offset + 1 < len(body) else "")
                )
                if in_match_arm:
                    # A match guard cannot bind with `if let`/`let else`; the fix is to move
                    # the optional into the arm pattern, so this is ICN-03, not ICN-02.
                    out.append(
                        Finding(
                            "ICN-03",
                            sf.path,
                            lineno,
                            "`.unwrap()` in a match guard",
                            sf.raw[lineno - 1].strip(),
                            "Bind in the arm pattern (`(Some(p), Some(n)) if ...`) instead of unwrapping in the guard.",
                        )
                    )
                elif re.search(r"is_some\(\)|is_ok\(\)|contains_key\(", ctx):
                    fix = (
                        "Bind both values in the arm pattern (`(Some(a), Some(b)) if ...`) "
                        "instead of unwrapping what the guard proved."
                        if "=>" in ctx
                        else "Use `if let Some(x) = opt { ... }` or `let ... else`."
                    )
                    out.append(Finding("ICN-02", sf.path, lineno, "check-then-unwrap", sf.raw[lineno - 1].strip(), fix))
                else:
                    out.append(
                        Finding(
                            "ICN-03",
                            sf.path,
                            lineno,
                            "`.unwrap()`",
                            sf.raw[lineno - 1].strip(),
                            'Use `expect("reason")`, `?`, or pattern matching.',
                        )
                    )
            if re.search(r"\.into\(\)|\.parse\(\)", line) and not re.search(r"::<|:\s*\w+(<|>)", line):
                # A conversion nested inside a call already has a type fixed by the callee's
                # signature (`Err(Var("…".into()))`); only a bare binding needs the note. Work
                # on the whole statement so multi-line calls and wrapped `let` statements count.
                statement = _statement_prefix(body, offset)
                m = re.search(r"\.(into|parse)\(\)", statement)
                prefix = statement[: m.start()] if m else ""
                nested_in_call = prefix.count("(") > prefix.count(")")
                annotated = (
                    re.search(r"let\s+(\w+|\()\s*[^=]*:\s*[\w&]", statement)
                    or re.search(r"^\s*[\w.]+\s*:\s*[\w&]+", statement)
                    or _bound_by_annotation(body, offset)
                )
                if not nested_in_call and not annotated:
                    out.append(
                        Finding(
                            "ICN-01",
                            sf.path,
                            lineno,
                            "inferred conversion type",
                            sf.raw[lineno - 1].strip(),
                            "Annotate the target type (`let x: T = ...`).",
                        )
                    )
            if re.search(r"\bassert(_eq|_ne)?!\(", line) and line.count(",") == 0:
                out.append(
                    Finding(
                        "ICN-04",
                        sf.path,
                        lineno,
                        "assertion without a context string",
                        sf.raw[lineno - 1].strip(),
                        "Add a message explaining why the assertion must hold.",
                    )
                )
            if ".for_each(" in line:
                out.append(
                    Finding(
                        "ICN-05",
                        sf.path,
                        lineno,
                        "`Iterator::for_each`",
                        sf.raw[lineno - 1].strip(),
                        "Use a `for` loop.",
                    )
                )
            if re.search(r"\.to_string\(\)\s*\+|\+\s*&\w+\.\w+\(", line):
                out.append(
                    Finding(
                        "ICN-08",
                        sf.path,
                        lineno,
                        "string concatenation with `+`",
                        sf.raw[lineno - 1].strip(),
                        "Use `format!`/`write!`.",
                    )
                )
            if "catch_unwind" in line:
                out.append(
                    Finding(
                        "ICN-07",
                        sf.path,
                        lineno,
                        "`panic::catch_unwind`",
                        sf.raw[lineno - 1].strip(),
                        "Not permitted; make the code panic-free.",
                    )
                )
    # combinator chain in a for header
    for idx, line in enumerate(sf.code):
        if re.match(r"^\s*for\s+\w+\s+in\s+.*\.(iter|into_iter)\(\)", line):
            chain = [line]
            j = idx
            while not sf.code[j].rstrip().endswith("{") and j - idx < 12:
                j += 1
                chain.append(sf.code[j])
            joined = " ".join(chain)
            if len([c for c in (".map(", ".filter(", ".filter_map(", ".flat_map(", ".fold(") if c in joined]) >= 2:
                out.append(
                    Finding(
                        "ICN-06",
                        sf.path,
                        idx + 1,
                        "combinator chain in a `for` header",
                        sf.raw[idx].strip(),
                        "Bind the chain to a named variable, then iterate it.",
                    )
                )


def check_structure(sf: SourceFile, out: list[Finding]) -> None:
    name = Path(sf.path).name
    if name in ("lib.rs", "main.rs", "mod.rs"):
        # A "non-leaf module" is one that owns submodules. A `lib.rs`/`main.rs` with no
        # `mod` declarations is itself a leaf, and implementing there is normal Rust.
        owns_submodules = any(re.match(r"\s*(pub(\([^)]*\))?\s+)?mod\s+\w+\s*;", line) for line in sf.code)
        if not owns_submodules:
            return
        # `fn main` is the entry point of a binary crate, not API implementation.
        items = [
            idx
            for idx, line in enumerate(sf.code)
            if re.match(r"^\s*(pub(\([^)]*\))?\s+)?(fn|struct|enum|impl|trait)\b", line)
            and not re.match(r"^\s*pub\s+fn\s+main\s*\(", line)
            and not re.match(r"^\s*fn\s+main\s*\(", line)
        ]
        if len(items) > 3:
            out.append(
                Finding(
                    "ORG-04",
                    sf.path,
                    items[0] + 1,
                    f"non-leaf module defines {len(items)} items",
                    sf.raw[items[0]].strip(),
                    "Move the implementation into a leaf module and re-export it.",
                )
            )


def check_module_layout(root: Path, out: list[Finding], exclude: set[str]) -> None:
    """ORG-02: chrome scope: no src/<subdir>/ module trees inside a single crate."""
    for src in root.rglob("src"):
        if not src.is_dir() or "target" in src.parts:
            continue
        for child in src.iterdir():
            if child.is_dir() and child.name not in exclude and child.name not in ("bin", "tests"):
                out.append(
                    Finding(
                        "ORG-02",
                        str(child.relative_to(root)),
                        1,
                        "subdirectory inside one crate's source tree",
                        child.name,
                        "Flatten into one directory, or split the crate.",
                    )
                )


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------

CHECK_ORDER = [
    "check_imports",
    "check_formatting",
    "check_ownership",
    "check_api",
    "check_types",
    "check_traits",
    "check_concurrency",
    "check_macros",
    "check_naming",
    "check_docs",
    "check_unsafe_and_attrs",
    "check_impl_concerns",
    "check_structure",
]

SKIP_DIRS = {".git", "target", "node_modules", ".venv", "venv", "build", "dist", ".cargo"}


def rule_applies(rid: str, kind: str, codebase: str) -> bool:
    """Scope gate: a rule fires only in the kind/codebase it was written for."""
    meta = RULES.get(rid)
    if meta is None:
        return True
    scope = meta["scope"]
    if scope == "any":
        return True
    if scope == "library":
        return kind == "library"
    if scope == "application":
        return kind == "application"
    return codebase == scope


def collect_files(paths: list[Path], root: Path, exclude: set[str]) -> list[SourceFile]:
    files: list[SourceFile] = []
    for p in paths:
        candidates = [p] if p.is_file() else sorted(p.rglob("*.rs"))
        for c in candidates:
            if any(part in SKIP_DIRS or part in exclude for part in c.parts):
                continue
            if c.suffix != ".rs":
                continue
            files.append(SourceFile.load(c, root))
    return files


def run(
    paths: list[Path],
    root: Path,
    kind: str,
    codebase: str,
    exclude: set[str],
    disable: set[str],
    only: set[str],
    width: int,
) -> list[Finding]:
    findings: list[Finding] = []
    files = collect_files(paths, root, exclude)
    for sf in files:
        raw: list[Finding] = []
        for name in CHECK_ORDER:
            fn = globals()[name]
            if name == "check_formatting":
                fn(sf, raw, width)
            elif name in ("check_api", "check_traits"):
                fn(sf, raw, kind)
            elif name == "check_concurrency":
                fn(sf, raw, codebase)
            elif name == "check_docs":
                fn(sf, raw, kind)
            else:
                fn(sf, raw)
        for f in raw:
            if f.rule in disable:
                continue
            if only and f.rule not in only:
                continue
            if not rule_applies(f.rule, kind, codebase):
                continue
            if sf.suppression_for(f.line, f.rule):
                continue
            findings.append(f)
    # Directory-level checks (need the tree, not a single file).
    if codebase == "chrome":
        layout: list[Finding] = []
        check_module_layout(root, layout, exclude)
        for f in layout:
            if f.rule in disable:
                continue
            if only and f.rule not in only:
                continue
            findings.append(f)
    # dedupe identical rule+path+line
    seen: set[tuple[str, str, int, str]] = set()
    unique: list[Finding] = []
    for f in findings:
        key = (f.rule, f.path, f.line, f.message)
        if key in seen:
            continue
        seen.add(key)
        unique.append(f)
    unique.sort(key=lambda f: (-SEVERITY_ORDER.get(RULES[f.rule]["severity"], 0), f.path, f.line))
    return unique


def render_markdown(
    findings: list[Finding], roots: list[str], kind: str, codebase: str, scanned: int, max_per_rule: int
) -> str:
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.rule] = counts.get(f.rule, 0) + 1
    sev_counts = dict.fromkeys(("error", "warning", "note"), 0)
    for f in findings:
        sev_counts[RULES[f.rule]["severity"]] += 1

    lines = [
        "# Rust Style Guide Audit",
        "",
        f"- Scope: `{', '.join(roots)}`",
        f"- Code kind: **{kind}**, codebase: **{codebase}**",
        f"- Files scanned: {scanned}",
        (
            f"- Findings: {len(findings)} "
            f"(error {sev_counts['error']}, warning {sev_counts['warning']}, note {sev_counts['note']})"
        ),
        "",
        "## Findings by rule",
        "",
        "| Rule | Title | Severity | Count |",
        "|---|---|---|---|",
    ]
    for rid in sorted(counts, key=lambda r: (-SEVERITY_ORDER[RULES[r]["severity"]], r)):
        lines.append(f"| {rid} | {RULES[rid]['title']} | {RULES[rid]['severity']} | {counts[rid]} |")

    lines += ["", "## Findings", ""]
    emitted: dict[str, int] = {}
    capped: dict[str, int] = {}
    for f in findings:
        if emitted.get(f.rule, 0) >= max_per_rule:
            capped[f.rule] = capped.get(f.rule, 0) + 1
            continue
        emitted[f.rule] = emitted.get(f.rule, 0) + 1
        sev = RULES[f.rule]["severity"]
        lines.append(f"### {sev.upper()} - {f.rule} {RULES[f.rule]['title']}")
        lines.append(f"`{f.path}:{f.line}` - {f.message}")
        if f.snippet:
            lines.append(f"```rust\n{f.snippet}\n```")
        if f.fix:
            lines.append(f"**Fix:** {f.fix}")
        lines.append("")
    if capped:
        lines.append(
            "_Truncated (raise `--max-per-rule` to see all):_ "
            + ", ".join(f"{r}: {n} more" for r, n in sorted(capped.items()))
        )
        lines.append("")

    manual = [r for r, m in RULES.items() if m["manual"] == "yes"]
    lines += [
        "## Manual review checklist (not mechanically checkable)",
        "",
        "| Rule | Question to answer by reading the code |",
        "|---|---|",
    ]
    questions = {
        "ORG-01": "Is this crate doing more than one abstraction? Would a smaller crate improve compile fan-out?",
        "ORG-03": "Does each leaf module file name match its primary item?",
        "API-03": (
            "Is an iteration-only parameter a concrete `&[T]`/`&Vec<T>` where "
            "`impl IntoIterator<Item = &T>` would widen what callers can pass?"
        ),
        "API-06": (
            "Does each failure path use `Option` for obvious failures, `Result` for "
            "recoverable ones with context, `panic!` only for violated invariants?"
        ),
        "ICN-09": "Does every `match` on a `#[non_exhaustive]` enum list the variants instead of a bare `_` arm?",
        "IMP-05": "Is each trait import scoped to the function that calls its methods, rather than module-wide?",
        "IMP-06": "In Chrome code, do imports go through `chromium::import!` instead of `use`?",
        "NAM-02": "Do type lifetimes have descriptive names beyond two local `'a`/`'b`?",
        "NAM-03": "Do generic parameters hint at their most important bound?",
        "SAF-09": "Does the code reach into `#[doc(hidden)]` items it does not own?",
        "SAF-10": (
            "Do `Add`/`Mul`/`BitAnd` impls hold their mathematical meaning rather than "
            "standing in for unrelated operations?"
        ),
        "TRT-01": "Are trait impls present where callers would expect them (`Debug`, `Clone`, `Default`, `From`)?",
        "TRT-05": "Is each trait used for generics, `impl`/`dyn`, or extension - or is it only organizing code?",
        "TRT-09": (
            "Does each type carry the `Copy`/`Clone`/`Default`/`PartialEq`/`Hash` impls the guide expects for its role?"
        ),
        "TST-01": "Do tests use the codebase's actual framework rather than a bespoke harness?",
    }
    for rid in manual:
        lines.append(f"| {rid} | {questions.get(rid, RULES[rid]['title'])} |")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Audit Rust code against the Google Rust Style Guide.")
    ap.add_argument("paths", nargs="*", default=["."], help="files or directories (default: .)")
    ap.add_argument("--root", default=".", help="root for relative paths in output")
    ap.add_argument(
        "--kind",
        choices=["library", "application"],
        default="library",
        help="library code: API rules are binding. application code: advisory (default: library)",
    )
    ap.add_argument(
        "--codebase",
        choices=["any", "chrome", "fuchsia"],
        default="any",
        help="enables codebase-specific rules (default: any)",
    )
    ap.add_argument("--format", choices=["md", "json"], default="md")
    ap.add_argument("--out", help="write the report here instead of stdout")
    ap.add_argument("--width", type=int, default=100, help="max line width (default 100)")
    ap.add_argument("--exclude", default="", help="comma-separated directory names to skip")
    ap.add_argument("--disable", default="", help="comma-separated rule IDs to disable")
    ap.add_argument("--only", default="", help="comma-separated rule IDs to run exclusively")
    ap.add_argument("--max-per-rule", type=int, default=25, help="cap findings per rule (default 25)")
    ap.add_argument("--fail-on", choices=["error", "warning", "note", "never"], default="error")
    ap.add_argument("--list-rules", action="store_true", help="print the rule catalog and exit")
    ap.add_argument("--list-manual", action="store_true", help="print rules needing human judgement and exit")
    args = ap.parse_args(argv)

    # Source snippets and paths are arbitrary UTF-8; a cp1252 console would otherwise
    # raise UnicodeEncodeError mid-report and lose the audit.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

    if args.list_rules:
        print(f"{'ID':8} {'Sev':8} {'Scope':12} {'Manual':7} Title")
        for rid in sorted(RULES):
            r = RULES[rid]
            print(f"{rid:8} {r['severity']:8} {r['scope']:12} {r['manual']:7} {r['title']}")
        return 0
    if args.list_manual:
        for rid in sorted(RULES):
            if RULES[rid]["manual"] == "yes":
                print(f"{rid}  {RULES[rid]['title']}")
        return 0

    root = Path(args.root).resolve()
    paths = [Path(p).resolve() for p in (args.paths or ["."])]
    exclude = {x.strip() for x in args.exclude.split(",") if x.strip()}
    disable = {x.strip() for x in args.disable.split(",") if x.strip()}
    only = {x.strip() for x in args.only.split(",") if x.strip()}

    files = collect_files(paths, root, exclude)
    findings = run(paths, root, args.kind, args.codebase, exclude, disable, only, args.width)

    if args.format == "json":
        payload = {
            "roots": [str(p) for p in paths],
            "kind": args.kind,
            "codebase": args.codebase,
            "files_scanned": len(files),
            "counts": {
                "error": sum(1 for f in findings if RULES[f.rule]["severity"] == "error"),
                "warning": sum(1 for f in findings if RULES[f.rule]["severity"] == "warning"),
                "note": sum(1 for f in findings if RULES[f.rule]["severity"] == "note"),
            },
            "findings": [f.as_dict() for f in findings],
        }
        text = json.dumps(payload, indent=2)
    else:
        text = render_markdown(
            findings, [str(p) for p in paths], args.kind, args.codebase, len(files), args.max_per_rule
        )

    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out} ({len(findings)} findings, {len(files)} files)")
    else:
        print(text)

    if args.fail_on == "never":
        return 0
    threshold = SEVERITY_ORDER[args.fail_on]
    return 1 if any(SEVERITY_ORDER[RULES[f.rule]["severity"]] >= threshold for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
