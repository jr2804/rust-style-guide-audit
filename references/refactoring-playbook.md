# Refactoring Playbook

The audit produces findings. This playbook turns them into proposals a reviewer will
accept: each finding becomes a concrete before/after, ordered by risk, with the
verification that proves the refactor was behaviour-preserving.

Two rules govern everything here:

1. **A finding is a claim about code, not about intent.** Read the surrounding code
   before proposing a change. A `&String` parameter that exists to call
   `push_str` needs a different fix than one that only reads.
2. **Refactors that change behaviour are not refactors.** If the fix touches floating
   point, iteration order, allocation timing, or error paths, it must be proven
   equivalent before it is proposed as safe. When it cannot be proven, say which
   behaviour may change and let the reviewer decide.

---

## Step 1 — Triage the findings

Bucket every finding into one of four classes before writing any proposal.

| Class | Meaning | Action |
|---|---|---|
| **Mechanical** | Text-level rewrite, provably identical behaviour | Batch into one pass; no per-item discussion |
| **Signature** | Changes a public API or the type of a parameter/return | Propose as a versioned change; note downstream call sites |
| **Design** | The finding points at a deeper problem (clone storm, bool flag, trait misuse) | Propose a design change with alternatives |
| **Contested** | You disagree with the rule in this context | Record a suppression with the reason; do not silently ignore |

Mechanical findings first: they make the review diff smaller and give the reviewer a
clean signal before anything contentious arrives.

Order within a pass: `error` → `warning` → `note`. The guide's own priorities put
correctness (`SAF-01`, `ICN-02`, `ICN-07`) before ergonomics (`API-05`, `NAM-01`) before
cosmetics (`FMT-01`, `DOC-02`).

---

## Step 2 — Verify the finding is real

Before writing a proposal, for each finding:

1. Open the file at the reported line and read the whole item (function, impl, struct).
2. Check whether the pattern is intentional: a `bool` that mirrors a CLI flag, a
   `.clone()` needed across an `await` boundary (if async is permitted), an alias that
   exists for readability in a long generic signature.
3. If the finding is a false positive, record the suppression with the reason rather
   than letting the audit fail silently on the next run.
4. If the finding is real, capture the before-state: the exact snippet, plus (for
   anything behaviour-adjacent) the test command that covers it.

A finding that cannot be reproduced by reading the code is a **script bug**: note the
rule ID and the construct that fooled it, so the checker can be tightened.

---

## Step 3 — Draft the proposal

One finding per proposal entry, with this shape (the outer fence below is four backticks so
the inner `rust` fences survive):

````markdown
### API-01 · `crates/foo/src/parse.rs:88` — `&String` parameter

**Current**
```rust
pub fn parse_line(input: &String) -> Result<Line, ParseError> { … }
```

**Why it violates the guide**
The guide requires `&str`; `&String` forces callers holding a literal, a `&str` slice,
or a `Cow<str>` to allocate before calling.

**Proposed**
```rust
pub fn parse_line(input: &str) -> Result<Line, ParseError> { … }
```

**Impact** — 4 call sites, all pass `&String` already: `src/a.rs:12`, `src/b.rs:40`,
`tests/parse.rs:7`, `benches/parse.rs:3`. No signature change ripples further.

**Risk** — none: `&String` derefs to `&str` at every call site.

**Verify** — `cargo test -p foo`; `cargo clippy -p foo -- -D warnings`.
````

Include the **Impact** line whenever the change touches a signature. Count real call
sites (`rg 'parse_line\(' --type rust`), not files. A proposal that says "update
callers" without a count is not reviewable.

---

## Step 4 — Before/after patterns

### API-01 — flexible references

```rust
// before
fn checksum(data: &Vec<u8>) -> u32
fn load(path: &PathBuf) -> io::Result<Config>
fn apply(cfg: &Option<Config>)
fn greet(name: &String)

// after
fn checksum(data: &[u8]) -> u32
fn load(path: &Path) -> io::Result<Config>
fn apply(cfg: Option<&Config>)
fn greet(name: &str)
```

Call sites only ever need `&x` where they had `&x`, plus `opt.as_ref()` at the `Option`
call sites. Both are mechanical. **Exception**: if the function stores the reference
behind a lifetime with a `T: '_` bound or returns a type naming the parameter's
element type, converting an owned parameter to a slice may force a lifetime annotation
on the return type — check before claiming "no ripple".

### API-03 — `impl IntoIterator` for iteration-only parameters

```rust
// before
fn sum_all(values: &[i64]) -> i64 {
    values.iter().sum()
}
// caller with a Vec<i64> must write &vec; with an iterator it cannot call at all

// after
fn sum_all(values: impl IntoIterator<Item = i64>) -> i64 {
    values.into_iter().sum()
}
// accepts Vec, &[i64] (with .iter().copied()), arrays, ranges
```

Only when the body truly only iterates. If it needs `len()`, indexing, or two passes,
keep the slice.

### API-05 — bool parameter to enum

```rust
// before
fn render(&self, out: &mut String, compact: bool) { … }
// call site reads: render(&mut s, true)   ← what is `true`?

// after
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Layout { Compact, Pretty }
fn render(&self, out: &mut String, layout: Layout) { … }
// render(&mut s, Layout::Compact)
```

If the enum has more than two variants in future, this change already accommodates
them. If the flag is genuinely a one-off and its name says it
(`set_enabled(bool)`), suppress with a comment.

### OWN-01 — `Rc`/`Arc` removal

Sequence to try, cheapest first:

1. **Pass a reference** through the call chain (`&T` instead of `Arc<T>`), adjusting
   lifetimes.
2. **Move the value** into the single owner and let other users borrow it for the
   duration of the call.
3. **Split the type**: the shared part becomes `Copy` data or an index into an arena;
   the mutable part stays uniquely owned.
4. **Arena/slab**: `Vec<T>` plus `struct Handle(usize)` removes the reference count
   entirely and often makes the API faster.
5. **Keep `Arc`** when the ownership graph is genuinely a DAG with multiple long-lived
   owners (plugin registries, caches, thread pools). Record why in a comment — that is
   the guide's stated exception.

An `Arc` on a hot path is also a performance finding: every clone is an atomic
increment. Mention it if the clone count is more than a handful per call.

### NAM-01 — std method naming

```rust
// before                          // after
fn get_value(&self) -> &T          fn value(&self) -> &T
fn get_value_mut(&mut self)        fn value_mut(&mut self) -> &mut T
fn to_bytes(&self) -> &[u8]        fn as_bytes(&self) -> &[u8]
fn as_string(&self) -> String      fn to_string_impl(&self) -> String   // or impl Display
fn from_u32(v: u32) -> Self        fn from_u32(v: u32) -> Self          // fine: infallible ctor
fn initialize() -> Self            fn new() -> Self
fn create_foo(a: A) -> Self        fn new_with_foo(a: A) -> Self
```

Renaming a public method is a breaking change: bump the version, or keep the old name as
a deprecated forwarding method for one release.

### NAM-05 — abbreviations

Rename project-local abbreviations, keep standard ones:

| Abbrev | Rename | Keep when |
|---|---|---|
| `cfg` | `config` | it is the `#[cfg]` attribute, or the field is a public API you cannot break |
| `buf` | `buffer` | it is a local of a few lines where the standard name reads as noise |
| `cnt` | `count` | — |
| `idx` | `index` | — |
| `mgr` | `manager` | — |
| `prm` | `param` | never |
| `snd`/`rcv` | `sender`/`receiver` | — |

Chrome's guide says keep well-known acronyms (`url`, `id`, `fft`). Extend the audit's
`ABBREVIATIONS_OK` set for domain vocabulary instead of suppressing each finding.

### TRT-03 — manual impl to derive

```rust
// before
impl Default for Options { fn default() -> Self { Self { retries: 3, ..Self::zeroed() } } }
impl Debug for Pair { fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result { write!(f, "{:?}/{:?}", self.0, self.1) } }

// after
#[derive(Debug)]
struct Pair(A, B);

#[derive(Debug)]
struct Options { retries: u32, … }
impl Default for Options { … }   // keep: a non-derivable default is legitimate
```

Only derive when the derive produces the same output. `Debug` derives print field
names; a hand-written `Debug` that prints a computed value is intentional — keep it.

### ICN-02 / ICN-03 — check-then-unwrap to pattern matching

```rust
// before
if map.contains_key(&k) {
    let v = map.get(&k).unwrap();
}
let v = parsed.unwrap();

// after
if let Some(v) = map.get(&k) { … }
let Some(v) = parsed else { return Err(Error::Missing(k)) };
// or, where the invariant is documented:
let v = parsed.expect("parser always sets `v` when `k` is present");
```

In tests, `unwrap()` is fine — assertions on a panic message are less readable than an
unwrapped `Ok`. The audit skips `#[cfg(test)]` blocks.

### ICN-06 — combinator chain in a `for` header

```rust
// before
for line in text.lines().map(str::trim).filter(|l| !l.is_empty()).flat_map(|l| l.split(',')) {
    handle(line);
}

// after
let tokens = text
    .lines()
    .map(str::trim)
    .filter(|line| !line.is_empty())
    .flat_map(|line| line.split(','));
for token in tokens {
    handle(token);
}
```

The named binding also documents the pipeline, and a profiler breakpoint can see it.

### SAF-01 — unsafe justification

```rust
// before
let value = unsafe { *ptr.add(offset) };

// after
// SAFETY: `offset < self.len` is guaranteed by the `assert!` above, and `ptr` comes
// from `self.data.as_ptr()` which is valid for `self.len` elements for `'a`.
let value = unsafe { *ptr.add(offset) };
```

The comment must name the invariant *and* the local evidence that it holds
(`assert!`, constructor check, type-level guarantee). "We know it's fine" is not a
justification, and neither is a comment that repeats what the code does.

### SAF-05 / SAF-06 — `#[non_exhaustive]`

```rust
// before
pub enum Status { Ok, Retry, Fatal }

// after
#[non_exhaustive]
pub enum Status { Ok, Retry, Fatal }
```

Consequence to state in the proposal: downstream `match` must gain a `_ =>` arm, so
adding the attribute is itself a breaking change. Add it to new APIs and to
pre-1.0 crates freely; for a stable crate, batch it with the next major bump.

### FMT-01 / FMT-02 — formatting

```toml
# rustfmt.toml at the workspace root
max_width = 100
use_small_heuristics = "Max"
format_code_in_doc_comments = true
format_strings = true
```

Then `cargo fmt --all` and remove each `#[rustfmt::skip]`. Where the skip was aligning
tables, keep it and add `// aligned for readability` so the next reader knows it is
deliberate.

### DOC-01 / DOC-03 — docs

```rust
/// Parses one line of the header block.
///
/// The line must match `<name>: <value>`; surrounding whitespace is trimmed.
///
/// # Errors
///
/// Returns [`ParseError::MissingColon`] when the line has no `:`.
///
/// # Panics
///
/// Panics if `line` is longer than 64 KiB — guarded by `MAX_LINE` at the call site.
pub fn parse_header(line: &str) -> Result<(String, String), ParseError> { … }
```

State behaviour and invariants; do not restate the signature. Sections the guide
expects: `# Errors`, `# Panics`, `# Safety` (for `unsafe fn`), `# Examples`
(compiled doctests).

---

## Step 5 — Sequence the work

Order proposals so that each step is independently mergeable and independently
revertible:

1. **Formatting and imports** — `cargo fmt`, glob-import removal. No semantic review
   needed. Do this first so later diffs are small.
2. **Signature widening** — `&Vec<T>` → `&[T]`, `&String` → `&str`, `&Option<T>` →
   `Option<&T>`. One commit per module; call sites are mechanical.
3. **Constructors and getters** — renames, with deprecated forwarding methods where
   the API is public.
4. **Error handling** — `unwrap` → `expect`/`?`/`let … else`. Each change must keep the
   panic message or error variant equivalent. Verify with the tests that cover the
   failure path, not only the happy path.
5. **Type and trait work** — newtypes, derives, `#[non_exhaustive]`, `Default`.
   Version-bump territory.
6. **Ownership redesign** — `Arc` removal, arena introduction. Land separately with
   benchmarks; this is the only step that can plausibly change performance.
7. **Suppressions** — for everything the reviewer rejects, so the next audit run is
   clean and the reason is recorded in the file.

Never mix a rename with a logic change in the same commit: `git blame` on the logic
becomes unreadable and a bisect cannot attribute a regression.

---

## Step 6 — Verification gate

A refactor is not done until these hold. Report the exact command and its result, not
"tests pass".

```bash
cargo fmt --all --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
uv run scripts/audit.py <paths> --codebase any --kind <library|application> --fail-on warning
```

Behaviour-sensitive changes add:

- **Numeric code**: compare outputs bit-for-bit against a recorded baseline
  (`sha256sum` of the output artifact, existing golden files, or the project's own
  comparison tool). A refactor that changes a float result is a behaviour change.
- **Performance-sensitive code**: run the benchmark before and after; state the delta.
- **Public API changes**: `cargo public-api diff` or `cargo semver-checks`; state whether
  the change is breaking.

If any gate is skipped, say which and why. A proposal that claims equivalence without
a gate is a guess.

---

## Step 7 — Write the report

Structure the deliverable so the reviewer can act top-down:

```markdown
# Rust Style Guide Audit — <paths>

## Summary
<N> findings across <M> files: <E> errors, <W> warnings, <N> notes.
Top three: <rule> (count), <rule> (count), <rule> (count).

## Blocking (errors)
…

## Should fix (warnings)
…

## Consider (notes, grouped by rule)
…

## Suppressions recommended
| Location | Rule | Reason |

## Mechanical pass available
The following findings are text-level and can be applied without review:
`cargo fmt --all`, glob-import removal at <n> sites.

## Not mechanically checkable
The manual checklist from the audit (`--list-manual`), answered.
```

Two things make a report usable: every finding carries `path:line` and a fix, and every
group is ordered by severity. A report that lists 200 findings without triage will be
ignored.
