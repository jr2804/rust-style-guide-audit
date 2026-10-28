# Rust Style Guide — Rule Catalog

Every rule ID the audit script emits, with the guide section it comes from, what
the guide actually says, and how to fix a violation. Rule IDs are stable: they
appear in audit output, in suppressions, and in review comments.

## Conventions

### Scopes

- **any** — applies to all Rust.
- **library** — binding for reusable library code; in application code these are advisory.
- **application** — Chrome/application-only guidance.
- **chrome** / **fuchsia** — only when `--codebase chrome|fuchsia` is passed.

### Severities

- **error** — the guide states a hard prohibition or the pattern is a correctness defect.
- **warning** — the guide says "prefer" / "avoid" and deviation needs a stated reason.
- **note** — style and judgement; report it, let the reviewer decide.

---

## Code organization

| ID | Severity | Scope | Rule |
|---|---|---|---|
| ORG-01 | note | chrome | Prefer small crates. Each crate should expose one abstraction. |
| ORG-02 | note | chrome | Use a flat module layout: one file per module, no `src/foo/` subdirectories for a single crate. |
| ORG-03 | note | any | Name a leaf module file after its primary item (`foo.rs` → `Foo`, `foo()`). |
| ORG-04 | note | any | Don't implement APIs in non-leaf modules (`lib.rs`, `mod.rs`, `main.rs`). They hold `mod` declarations and re-exports only. |

**ORG-01** — Small crates cut compile times, keep the dependency graph honest and stop
one crate from growing several abstraction layers. Split when a crate contains two
unrelated abstractions or when its public surface needs its own stability contract.
Counter-argument the guide accepts: too many tiny crates slows builds because each
crate is compiled separately.

**ORG-04** — Rust's privacy is per-module, not per-file: `Foo` can read private fields of
other items in the same module. Putting an implementation in `lib.rs` therefore widens
what can reach inside `Foo`. Move it to a leaf module and re-export.

---

## Imports

| ID | Severity | Scope | Rule |
|---|---|---|---|
| IMP-01 | warning | any | No glob imports (`use foo::*;`), except `use super::*;`/`use crate::*;` inside `#[cfg(test)]` test modules. |
| IMP-02 | warning | any | A `use` statement imports from one module only. Split `use foo::{a, bar::b};`. |
| IMP-03 | note | any | Qualify top-level function calls with their module: `use foo;` then `foo::bar()`. |
| IMP-04 | note | any | Import type names (`use std::collections::HashMap;`) and use them unqualified. |
| IMP-05 | note | any | Import a trait inside the function that uses it, unless the file uses its methods throughout. |
| IMP-06 | note | chrome | Import through `chromium::import!()`. |

**IMP-01** — Glob imports make it impossible to tell where a name came from and break
silently when the source module gains an item. The guide's one exception is test
modules, where `use super::*;` avoids repeating the parent module's item list.

**IMP-02** — When names are introduced from more than one module, grep for the item
stops finding callers if the module path is buried inside a brace group.

**IMP-03** — `foo::bar()` at the call site makes origin obvious and survives renames
inside `foo`. Import the module, not the function. Exceptions: associated functions
(`Foo::bar()`), trait methods, and items imported into the **current** module from an
**ancestor** module or the prelude, which may be used unqualified.

This is a call-site rule, so the audit only reports a `use mod::name;` when the file
actually calls `name(…)` unqualified. A `pub use` re-export exports the name instead of
calling it, and a name that the file also uses as a path qualifier (`mem::swap`) was
imported as a module — neither is a finding.

**IMP-04** — Types read as part of the signature line (`fn f(m: HashMap<..>)`) and must
be importable. Functions read as statements and should carry their module.

**IMP-05** — A trait import only needs to be in scope where its methods are called, so a
function-local `use std::str::FromStr;` keeps the module-level import block from carrying
traits that the reader of another function does not need. The guide's own limit: if the
trait's methods are used extensively throughout the file, the module-level import is
fine. Judgement call — on the manual checklist.

**IMP-06** — Chrome builds remap crate names through `chromium::import!`, which keeps the
crate name independent of the source path and lets Chromium swap the underlying
implementation per build target. A plain `use serde::…` in Chrome code bypasses that
remapping. Not applicable outside Chrome.

---

## Formatting

| ID | Severity | Scope | Rule |
|---|---|---|---|
| FMT-01 | note | any | Code is rustfmt-formatted, max width **100** columns. |
| FMT-02 | note | any | `#[rustfmt::skip]` only for manual alignment or generated code. |

**FMT-01** — Use the guide's `rustfmt.toml`:

```toml
max_width = 100
use_small_heuristics = "Max"
# To match the 2018/2021 edition
edition = "2021"
# Comments and strings should always be formatted
format_code_in_doc_comments = true
format_strings = true
```

`use_small_heuristics = "Max"` is load-bearing: it keeps short `struct` literals,
calls and `match` arms on one line and is what makes the visual difference versus
default rustfmt noticeable. Verify with `cargo fmt --check`.

**FMT-02** — Legal uses: aligning consecutive assignment or `match` arms, and
machine-generated code. Everything else should be reformatted instead of skipped.

---

## Ownership

| ID | Severity | Scope | Rule |
|---|---|---|---|
| OWN-01 | warning | any | Avoid `Rc` and `Arc` except when the ownership graph is genuinely unworkable. |
| OWN-02 | note | any | Prefer borrows over deep copies. Investigate repeated `.clone()`. |

**OWN-01** — Shared ownership makes the lifetime of an object depend on runtime
reference counts, so leaks and cycles become possible and the borrow checker can no
longer prove single ownership. Before reaching for `Rc`/`Arc`, try: passing a reference
through the call chain, splitting the object so each owner owns its own part, or an
index/arena. Chrome additionally disallows them inside `rust_g` via a lint.

**OWN-02** — `.clone()` that silences a borrow error is usually a design smell: either
the call graph needs restructuring or a narrower borrow suffices. The script reports
functions with many `.clone()` calls as candidates, not as violations.

---

## Function inputs and outputs

| ID | Severity | Scope | Rule |
|---|---|---|---|
| API-01 | error | any | Accept flexible references: `&T`, `&[T]`, `&str`, `&Path`, `Option<&T>`. |
| API-02 | note | library | Return `impl Iterator<Item = _>` instead of `Vec<T>` where callers don't need indexing. |
| API-03 | note | library | Take `impl IntoIterator<Item = _>` when the function only iterates its argument. |
| API-04 | note | application | `impl Into<T>` only where call-site ergonomics justify it. |
| API-05 | warning | any | Prefer an `enum` over a `bool` parameter. |
| API-06 | note | any | Choose the failure mechanism deliberately: `Option`, `Result`, or `panic!`. |

**API-01** — The specific substitutions:

| Don't | Do |
|---|---|
| `&Vec<T>`, `&[T; N]`, `&Box<[T]>` | `&[T]` |
| `&String` | `&str` |
| `&Box<T>` | `&T` |
| `&Option<T>` | `Option<&T>` |
| `&PathBuf` | `&Path` |

`&Option<T>` is the one case where the reference must be *transformed*, not just
reborrowed: callers write `opt.as_ref()`. Taking `&Option<T>` also forbids `None`
at the call site.

**API-02 / API-03** — Iterators let callers stop early and avoid an intermediate
`Vec`. If callers genuinely need indexing, length or `Clone`, return the collection.
In a parameter, `impl IntoIterator<Item = T>` accepts `Vec<T>`, `&[T]`, arrays and
ranges alike, so a new caller does not force a signature change.

**API-04** — `impl Into<T>` hides an allocation or conversion at the call site and
can hurt type inference. In application code, take the concrete type. In library code it
is acceptable on builder-style setters where the ergonomic gain is visible.

**API-05** — `foo(data, true)` is unreadable at the call site. Use
`enum Truncate { Yes, No }`. If the flag is obvious from the name
(`set_visible(bool)`), keep the `bool` and say so in review.

**API-06** — Decision table:

| Situation | Mechanism |
|---|---|
| Failure is expected and callers routinely ignore it | `Option<T>` |
| Failure is recoverable and callers need detail | `Result<T, E>` with a real error type |
| Failure means the caller violated an invariant | `panic!` / `assert!` |

Never encode failure in a sentinel value (`-1`, `""`, `f64::NAN` used as "missing").

---

## Types

| ID | Severity | Scope | Rule |
|---|---|---|---|
| TYP-01 | note | any | Use a newtype, not a type alias, when the type has distinct semantics. |
| TYP-02 | warning | any | Prefer named fields over multi-field tuple structs. |

**TYP-01** — An alias (`type FrameId = usize;`) is a rename: the compiler will not stop
you mixing it with the underlying type, and it cannot carry its own impls. Use a
newtype (`struct FrameId(usize);`) when the type has its own invariants, units, or API.

**TYP-02** — `.0`, `.1`, `.2` at a call site says nothing. A tuple struct with one field
is a legitimate newtype; with two or more, name them.

---

## Traits

| ID | Severity | Scope | Rule |
|---|---|---|---|
| TRT-01 | note | any | Add trait implementations as soon as callers need them (`Debug`, `Clone`, `Default`, `From`, `PartialEq`). |
| TRT-02 | warning | any | Implement the std trait (`FromStr`, `Display`, `FromIterator`, `Default`) instead of an ad-hoc method. |
| TRT-03 | note | any | Prefer `#[derive]` over hand-written impls that only forward. |
| TRT-04 | note | library | Prefer `impl Trait`/generics over `dyn Trait` in parameters; `dyn` where code size matters. |
| TRT-05 | note | any | Define a trait only when it serves generics, `impl`/`dyn`, or extension of a foreign type. |
| TRT-06 | note | any | Name extension traits with the `Ext` suffix. |
| TRT-07 | note | library | Pair a meaningful `From` impl with `new`/`try_new`/`from_foo`. |
| TRT-08 | warning | any | Options structs implement `Default`. |
| TRT-09 | note | any | Implement `Copy`/`Clone`/`Default`/`PartialEq`/`Hash`/`Ord` where the guide expects them. |

**TRT-02** — Mapping table: "parse from a string" → `FromStr`; "render for humans" →
`Display`; "render for debugging" → `Debug`; "build from an iterator" →
`FromIterator`; "convert losslessly from `T`" → `From<T>`.

**TRT-04** — `impl Trait` in argument position is monomorphised: faster, no vtable, but
code size grows per instantiation. `dyn Trait` costs one indirect call and keeps the
binary small. Library APIs default to generics.

**TRT-05** — If the only impl of your trait is in the same module and nobody writes
`T: YourTrait`, the trait is a namespacing device; use a module instead.

**TRT-06** — `impl FooExt for str { fn capitalize(&self) … }` makes the origin of the
method obvious at every call site and avoids name collisions.

**TRT-07** — `From` cannot fail and cannot carry context, so callers need an infallible
constructor too. Convention: `Foo::new()`, `Foo::try_new()` for fallible, `Foo::from_bar()`
where several `From` impls would be ambiguous.

**TRT-08** — Options structs are meant to be spread with `..Default::default()`; without
`Default` every caller repeats every field.

**TRT-09** — The guide's per-trait expectations, condensed:

| Trait | Implement when |
|---|---|
| `Copy` | the type is likely to stay `Copy` — pass by value without moves |
| `Clone` | almost always, unless the type owns an external resource |
| `Default` | there is a sane default state, in particular when there is a `new()` |
| `PartialEq` | callers should be able to write `==`; prefer it over `Eq` |
| `Eq` | only when reflexivity genuinely holds |
| `PartialOrd`/`Ord` | callers should compare with `<`/`>`; `Ord` needs total ordering |
| `Hash` + `Eq` | the type is likely to be a map key or cache entry |
| public-field types | the traits every subfield implements |
| error types | `Copy` where possible |

Judgement calls about which traits a type should carry — on the manual checklist.

---

## Concurrency

| ID | Severity | Scope | Rule |
|---|---|---|---|
| CON-01 | warning | any | Never recover from a poisoned mutex. |
| CON-02 | note | chrome | No `async` / `.await`. |
| CON-03 | note | chrome | Don't spawn threads with `std::thread`. |
| CON-04 | note | fuchsia | Use `fuchsia_sync::Mutex`. |

**CON-01** — A poisoned mutex means another thread panicked while holding the lock; the
protected data may be half-updated. Patterns that hide this — `lock().unwrap_or_else(|e|
e.into_inner())`, `PoisonError::into_inner`, `lock().ok()?` with a fabricated value —
turn a loud failure into silent corruption, and the unwrap variant turns it into a
second panic. Propagate the poison or `expect()` with a message.

**CON-02 / CON-03** — Chrome's Rust is synchronous and sequence-driven; async and
thread spawning are blocked by lints in `//build/rust`.

**CON-04** — `fuchsia_sync::Mutex` is const-constructible and behaves like the rest of
Fuchsia's mutexes; mixing in `std::sync::Mutex` breaks that contract.

---

## Macros

| ID | Severity | Scope | Rule |
|---|---|---|---|
| MAC-01 | note | any | Prefer functions, types and traits over `macro_rules!`/proc macros. |

**MAC-01** — Macros hide control flow from `rustfmt`, `rust-analyzer` and
clippy, cannot be type-checked until expansion, and produce poor error spans. Reach for
one only when nothing else works: variadic APIs, deriving trait impls, or DSLs the
guide considers justified.

---

## Naming

| ID | Severity | Scope | Rule |
|---|---|---|---|
| NAM-01 | warning | any | Follow std method naming: `as_`/`to_`/`into_` prefixes, `foo()`/`foo_mut()` getters, no `get_`. |
| NAM-02 | note | any | Descriptive lifetime names once there is more than one or two. |
| NAM-03 | note | any | Generic parameters should hint at their most important bound. |
| NAM-04 | warning | any | Initialization functions are `new`/`new_with_foo`/`try_new`. |
| NAM-05 | note | any | Avoid project-local abbreviations. |
| NAM-06 | warning | any | `set_foo()` returns `()`; `replace_foo()` returns the old value. |

**NAM-01** — Conversion prefixes:

- `as_foo()` — cheap, borrowed/view conversion with no side effects (`as_str`, `as_bytes`).
- `to_foo()` — an owned result with a possible allocation/copy (`to_string`, `to_vec`).
- `into_foo()` — consumes `self` (`into_inner`, `into_vec`).
- `foo()` / `foo_mut()` — getters returning `&T` / `&mut T`.

`get_` is a C/Java habit that adds nothing; `len`/`is_empty` and `iter` already
follow the std shape. Chrome applies this as a lint in `rust_g`.

**NAM-02** — `'a`, `'b` are fine for local one-off lifetimes. Once a struct has
several, name them for the data they tie to (`'src`, `'buf`, `'input`).

**NAM-03** — `T`, `U` are only readable when the bound is obvious from the signature.
Prefer `K`/`V`, `R` (reader), `W` (writer) in std style; a single-parameter generic can be
`T` with the bound documented.

**NAM-04** — `initialize()`, `create_foo() -> Self`, `Foo::make()` all mean "construct"
and force readers to learn each spelling. Chrome's `rust_g` has a
`clippy::new_without_default`-style guideline: `new` for infallible, `new_with_foo` for
variants, `try_new` for fallible.

**NAM-05** — Abbreviations are only readable to the author. Keep well-known acronyms
(`url`, `id`, `fft`) and DSP/domain abbreviations the project already defines.

**NAM-06** — The guide's accessor set is a contract, not a naming preference: a reader
who sees `set_foo` assumes the old value is gone, and a reader who sees `replace_foo`
assumes it is returned. Swapping the two silently changes what the call site can rely
on. `take_foo()` is the third shape — it clears the value and returns the old one.

---

## Documentation

| ID | Severity | Scope | Rule |
|---|---|---|---|
| DOC-01 | warning | library | Every public item has a doc comment. |
| DOC-02 | note | any | Use `///` (item) and `//!` (module) doc comments, not `/** */`. |
| DOC-03 | note | any | Document panic conditions with a `# Panics` section. |

**DOC-01** — Public library APIs need docs describing *what for* and *what invariants*,
not a restatement of the signature. Application code documents the same way where a
reader will need it, but the script only enforces it for `--kind library`.

**DOC-02** — `///` and `//!` are what `rustdoc` and editors expect for folding,
auto-insertion, and markdown rendering.

**DOC-03** — Any public function that can panic documents the conditions under a
`# Panics` section. Panicking on programmer error (index out of bounds, `unwrap` of a
documented invariant) is fine; leaving it undocumented is not.

---

## Other features

| ID | Severity | Scope | Rule |
|---|---|---|---|
| SAF-01 | error | any | `unsafe` requires a `// SAFETY:` comment justifying the invariant. |
| SAF-02 | error | any | No unstable features (`#![feature(..)]`). |
| SAF-03 | warning | any | Implement `len()` and `is_empty()` together. |
| SAF-04 | note | library | `const fn` only where you can keep it `const`. |
| SAF-05 | note | library | Public enums are `#[non_exhaustive]`. |
| SAF-06 | note | library | Public structs with public fields are `#[non_exhaustive]`. |
| SAF-07 | note | library | `#[must_use]` where dropping the value is a bug. |
| SAF-08 | error | any | No code runs before `main()`. |
| SAF-09 | warning | any | Don't touch `#[doc(hidden)]` items you don't own. |
| SAF-10 | note | any | Operator overloads keep their mathematical meaning. |
| SAF-11 | note | library | `#[must_use]` on error and lazy-computation types. |

**SAF-01 / SAF-02** — Stable Rust only; no `ctor`/`#[ctor]` static initializers. Every
`unsafe` block is preceded by a `// SAFETY:` comment stating which invariant holds and
why.

**SAF-03** — `is_empty()` without `len()` (or vice versa) is a clippy lint
(`len_without_is_empty`) for a reason: callers expect both to exist and to agree.

**SAF-04** — Adding `const` to a public function is backwards-compatible, removing it is
breaking. Only mark `const` if you can keep it `const` under future refactors.

**SAF-05 / SAF-06** — `#[non_exhaustive]` lets a public enum gain a variant and a public
struct gain a field without breaking downstream code. Without it, any such change is
semver-major.

**SAF-07** — Return values whose only purpose is a side effect (a `Result` you must
check, a builder step) should be `#[must_use]`.

**SAF-09** — An item hidden from docs is hidden because it is unstable or internal; it may
change or disappear in a patch release.

**SAF-10** — `Add`/`Mul`/`Not`/… exist to let mathematics read as mathematics. Using them
as syntax sugar makes an expression look like arithmetic without being arithmetic, so
readers cannot reason about cost or associativity. Judgement call — on the manual
checklist.

**SAF-11** — `Result` is already `#[must_use]`, so a function returning it needs no
attribute; a *custom* error or lazy type does not carry it, and a dropped value is a
silently ignored failure or a computation that never ran.

---

## Implementation concerns

| ID | Severity | Scope | Rule |
|---|---|---|---|
| ICN-01 | note | any | Don't overuse type inference. |
| ICN-02 | error | any | Prefer pattern matching over check-then-unwrap. |
| ICN-03 | warning | any | Prefer `expect` over `unwrap`. |
| ICN-04 | note | any | Give assertions a context string. |
| ICN-05 | note | any | Avoid `Iterator::for_each`. |
| ICN-06 | note | any | Don't build combinator chains in a `for` header. |
| ICN-07 | error | any | No `panic::catch_unwind`. |
| ICN-08 | note | any | Prefer `format!`/`write!` over `+` string concatenation. |
| ICN-09 | note | any | List `non_exhaustive` variants instead of a bare `_` arm. |

**ICN-01** — Turbofish/annotation needed when the inferred type is not obvious from the
line: `collect::<Vec<_>>()`, `let x: u32 = s.parse()?`. If a reader has to jump to
another file to know the type, annotate it.
**ICN-02 / ICN-03** — `is_some()` followed by `unwrap()` is a race with yourself and a
panic waiting to happen:

```rust
// no
if opt.is_some() { use_it(opt.unwrap()); }
// yes
if let Some(v) = opt { use_it(v); }
// yes (early return)
let Some(v) = opt else { return; };
```

Where `Option` genuinely cannot be unwrapped by pattern, use
`expect("invariant explanation")` — a bare `unwrap()` reports only a line number.

**ICN-04** — `assert_eq!(a, b)` reports two values with no explanation.
`assert_eq!(a, b, "frame {i} must round-trip")` says which invariant broke.

**ICN-05** — `for_each` gives no `?`/`break`/`return` and reads worse than a loop.
Clippy's `needless_for_each` flags it.

**ICN-06** — A combinator chain inside `for x in a.iter().map(f).filter(g) {` hides the
iteration source and makes the loop body look unrelated. Bind it:
`let xs = a.iter().map(f).filter(g); for x in xs { … }`.

**ICN-07** — `catch_unwind` cannot recover a broken invariant, requires `UnwindSafe`
bounds, and interacts badly with panic=abort. Chrome blocks it. Make the code panic-free
instead.

**ICN-08** — `a + " " + &b` allocates a new `String` per `+`. `format!("{a} {b}")` allocates
once and reads better.

**ICN-09** — On a `#[non_exhaustive]` enum a bare `_` arm makes the next variant a silent
no-op: the compiler cannot warn you. List the variants you know and put the ignored ones
in the last arm together with `_`, so adding a variant forces a decision:
`Shape::Triangle | _ => {}`.

---

## Tests

| ID | Severity | Scope | Rule |
|---|---|---|---|
| TST-01 | note | any | Use the codebase's test framework (Chrome: `rust_gtest_interop`). |

New test frameworks need an exception in `//build/rust`; use the one already
configured.

---

## Suppressing a finding

Findings are advisory input to review, so a false positive needs a recorded reason:

```rust
// style-guide-audit: ignore API-05 — the flag is named `set_visible`, unambiguous at call sites
fn set_visible(&mut self, visible: bool) { … }
```

`// style-guide-audit: ignore RULE-ID[, RULE-ID]` suppresses on the annotated line and the
next one. `// style-guide-audit: file-ignore RULE-ID` at the top of a file suppresses that
rule for the file; without IDs it suppresses the whole file. Prefer the narrowest scope
that works. Suppressions are visible in review, which is the point.

---

## Appendix A — Quick checklist

Before submitting Rust code for review, confirm:

- [ ] `cargo fmt --check` clean with `max_width = 100`, `use_small_heuristics = "Max"`.
- [ ] `cargo clippy -- -D warnings` clean (the guide calls clippy an extension of the style guide).
- [ ] No glob imports, one module per `use`.
- [ ] API params take `&[T]`/`&str`/`&Path`/`Option<&T>`, not the owned/boxed/`&`-of-`Option` variants.
- [ ] No `bool` parameter that needs a comment to read.
- [ ] Failure modes are deliberate: `Option` / `Result` / `panic!`.
- [ ] Constructors are `new`/`new_with_foo`/`try_new`; getters are `foo`/`foo_mut`.
- [ ] `set_foo` returns `()`; `replace_foo`/`take_foo` return the old value.
- [ ] `as_`/`to_`/`into_` prefixes match the conversion they actually perform.
- [ ] Every `unsafe` has a `// SAFETY:` justification.
- [ ] Public enums and public-field structs are `#[non_exhaustive]`; their `match` arms
      list the variants they handle rather than starting with `_`.
- [ ] `len()` and `is_empty()` both exist.
- [ ] Custom error/lazy types carry `#[must_use]`.
- [ ] No `unwrap()` outside tests.
- [ ] Public library items have doc comments; panicking ones have `# Panics`.

## Appendix B — Known gaps in the mechanical audit

`scripts/audit.py` matches text patterns on a comment/literal-stripped copy of each
file. It does not resolve macros, type information, or module graphs, so be aware:

- Multi-line `unsafe` blocks: only the `unsafe` keyword line is checked for a `SAFETY:`
  comment within four preceding lines.
- `API-01` misses generic wrappers such as `&std::borrow::Cow<'_, [u8]>`.
- `ORG-02` only inspects directories directly under a `src/` directory.
- `TRT-06` guesses extension traits from the presence of an out-of-module `impl Trait for
  Type`, so it can miss traits whose impl lives in another file.
- `NAM-05` flags only the abbreviations listed in its spell-out table
  (`ABBREVIATIONS_SPELL_OUT` in the script) and accepts the domain list in
  `ABBREVIATIONS_OK`; anything outside both passes. Add domain vocabulary to the
  allow-list rather than widening the pattern.
- `IMP-03` exempts `pub use` re-exports and imports the file uses as a path qualifier,
  and it exempts imports from the file's own module or an ancestor, matching the guide's
  exception; it cannot resolve a `use … as …` alias of a crate path, and a function that
  is only ever passed by name (`map(helper)`) is not counted as a call site.
- `IMP-03` also fires inside `#[cfg(test)]` modules and integration tests, because the
  guide's rule has no test exception; suppress those with `file-ignore` if the crate
  prefers unqualified test imports.
- `DOC-01` only checks `pub` items one line per declaration; `pub use` re-exports are
  skipped.
- `NAM-06` reads the return type from the declaration line, so a `set_` setter whose
  signature wraps before the `->` is missed.
- `SAF-11` recognises error types by the `Error`/`Err` suffix on the type name; a
  differently-named lazy type still needs a manual check.
- Test code is excluded from `OWN-01`, `ICN-02`, `ICN-03`.

Everything the guide states as a semantic requirement — trait necessity, API
ergonomics, module boundaries, test framework choice — is on the manual checklist the
report prints.
