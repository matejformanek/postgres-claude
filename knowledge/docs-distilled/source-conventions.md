---
source_url: https://www.postgresql.org/docs/current/source-conventions.html
fetched_at: 2026-06-14T19:59:00Z
anchor_sha: e18b0cb7344
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Miscellaneous Coding Conventions (§55.4)

The portability/idiom rules that the `coding-style` skill enforces mechanically.
This page is the *why*; the skill is the *how* (tabs, brace style, include
order). Worth reading for the C99-subset and signal-handler rules that aren't
obvious from pgindent alone.

## C99 baseline, with four banned C99 features

- Core code must compile under a **conforming C99** compiler, but **four C99
  features are prohibited** for portability/historical reasons: **variable-length
  arrays**, **intermingled declarations and code** (declare at block top),
  **`//` comments**, and **universal character names**. [from-docs]
  [cross: skill `coding-style`]
- Newer-standard / compiler-specific features are allowed **only with a fallback**:
  e.g. **`_Static_assert()`** (C11) and **`__builtin_constant_p`** (GCC) each ship
  a C99-compatible replacement. No hard dependency on a post-C99 feature. [from-docs]

## static inline preferred over function-like macros

- Prefer a **`static inline` function** when a macro would have
  **multiple-evaluation hazards** (the classic `#define Max(x,y) ((x)>(y)?(x):(y))`
  double-evaluation) or would be very long. **Macros only when type polymorphism
  is needed** (passing expressions of various types). [from-docs]
- **Frontend/backend split:** an inline function that references backend-only
  symbols must be wrapped in **`#ifndef FRONTEND`** — some compilers emit
  references to symbols used in an inline function even when the function is never
  called, which would break frontend links. (Example: `MemoryContextSwitchTo`.) [from-docs]
  [cross: knowledge/idioms — see skill `memory-contexts`]

## Signal handlers: async-signal-safe only, set-flag-and-latch

- A signal handler may call **only async-signal-safe functions** (POSIX sense) and
  touch **only `volatile sig_atomic_t`** variables — with the PG-specific
  exception that **`SetLatch()` is deemed signal-safe**. The canonical pattern is
  set a flag + wake the main loop: [from-docs]
  ```c
  static void handle_sighup(SIGNAL_ARGS) { got_SIGHUP = true; SetLatch(MyLatch); }
  ```
  [cross: skill `bgworker-and-extensions`]

## Calling function pointers

- **Bare pointer variable: dereference explicitly** — `(*emit_log_hook)(edata)`.
  **Struct member: omit the extra punctuation** —
  `paramInfo->paramFetch(paramInfo, paramId)`. A small house-style consistency
  point that shows up in hook-calling code. [from-docs]

## Links into corpus
- Skill: **`coding-style`** — the mechanical enforcement (tabs@4, BSD braces, postgres.h-first, ~78-col, pgindent).
- Skill: **`error-handling`** — pairs with the `#ifndef FRONTEND` rule for backend-only ereport.
- Skill: **`bgworker-and-extensions`** — the SetLatch signal-handler idiom in context.
- [[knowledge/docs-distilled/source-format.md]] — (sibling §55.1, if distilled) the formatting rules.
- [[knowledge/docs-distilled/error-style-guide.md]] — §55.3 message-wording companion.

## Gaps / follow-ups
- This section does NOT cover the int32/uint typedefs, bool/true/false, do/while(0)
  macro wrapping, Assert() policy, or palloc-over-malloc — those are spread across
  §55.1 (Formatting) and the `coding-style` / `memory-contexts` skills, not here.
