---
name: coding-style
description: PostgreSQL C coding-style rulebook — apply whenever editing, adding, or reviewing C code under source/src/**/*.{c,h}. Covers tabs/braces/line-length, include ordering (postgres.h first!), C99 subset (no //, no VLA, no mid-block decls), naming, ereport vs elog and the error-message style guide, palloc vs malloc, Assert hygiene, PG_TRY rules, and what pgindent will rewrite if you don't.
---

# PostgreSQL coding-style — operational rules

When you touch any `.c` or `.h` under `source/src/`, the file must end up
looking like the surrounding code. Follow this checklist; full reasoning
and citations live in `knowledge/conventions/coding-style.md`.

## Hard rules (must not violate)

### 1. Indentation: hard tabs, width 4
- Literal `\t`, not spaces. One tab per nesting level.
- Verify your editor: `.editorconfig` covers it; if you write a file
  with spaces, pgindent will produce a noisy diff.

### 2. `#include "postgres.h"` is line 1 of every backend `.c` file
Order (each group separated by a blank line):
1. `#include "postgres.h"` (backend) **or** `"postgres_fe.h"` (frontend)
   **or** `"c.h"` (shared) — **before any system header**
2. `<system headers>` (`<stdio.h>`, `<unistd.h>`, …)
3. `"project headers"` grouped, alphabetical-ish

Headers under `src/include/` must compile standalone (`make
headerscheck`) and as C++ (`make cpluspluscheck`).

### 3. C99 subset only — these are banned even though C99 has them
- No `//` line comments (use `/* … */`)
- No variable-length arrays
- No declarations interleaved with statements (declare locals at the top
  of the block before any statement)
- No universal character names (`\uXXXX`)
- Newer features (`_Static_assert`, GCC builtins) require a fallback.

### 4. No raw `malloc` / `free` / `strdup` in the backend
Use `palloc` / `pfree` / `repalloc` / `pstrdup` / `psprintf`. Allocations
live in `CurrentMemoryContext`. Frontend/common code uses `pg_malloc`
etc. from `src/common`.

### 5. Errors via `ereport`, not `fprintf(stderr, …)`
```c
ereport(ERROR,
        errcode(ERRCODE_DIVISION_BY_ZERO),
        errmsg("division by zero"));
```
Use `elog(level, …)` **only** for internal / "cannot happen" / debug
messages (no SQLSTATE, no translation). `ereport(ERROR, …)` does **not
return** — never write code after it.

### 6. Assertions never have side effects
`Assert(cond)` compiles away in non-cassert builds. Move any side effect
out of the macro. Prefer `StaticAssertDecl`/`StaticAssertStmt` for
compile-time checks.

### 7. File header block is mandatory and copyrights are exact
Every `.c` and most `.h` start with this format-preserving block. Both
copyright lines, verbatim:

```c
/*-------------------------------------------------------------------------
 *
 * filename.c
 *      one-line description
 *
 * Portions Copyright (c) 1996-<year>, PostgreSQL Global Development Group
 * Portions Copyright (c) 1994, Regents of the University of California
 *
 *
 * IDENTIFICATION
 *      src/path/to/filename.c
 *
 *-------------------------------------------------------------------------
 */
```

The leading `/*-------` makes pgindent leave it alone.

## Formatting checklist (pgindent will fix these — do them anyway)

| Rule | Detail |
|---|---|
| Brace style | BSD/Allman — opening brace on its own line at same indent |
| Function definition | Return type alone on a line; `name(args)` on the next; `{` in column 1 |
| Pointer star | Binds to the variable: `char *p`. Function return type: `Foo *` with one space |
| Single-statement `if` | No braces; body on next line indented +1 |
| `else` | On its own line after the closing `}` |
| Line length | Target ~80 cols; pgindent uses `-l79`. Don't fracture translatable strings just to fit |
| Trailing whitespace | Stripped everywhere except a few data files (see `.editorconfig`) |
| Final newline | Required (except a few data files) |

## Comment style

Standard multi-line block:
```c
/*
 * comment text begins here
 * and continues here
 */
```

Format-preserving block (pgindent won't reflow):
```c
/*---------
 * keep these line breaks
 *---------
 */
```

Function header comments sit directly above the function, start with the
function name, then describe what it does and any non-obvious
preconditions. They are anchored in column 1 and not reflowed.

## Naming

| Thing | Convention | Examples |
|---|---|---|
| Types / typedefs | `PascalCase`, no `_t` suffix | `HeapTuple`, `MemoryContext` |
| Functions (verbs on a subsystem) | `lower_snake_case` | `heap_fetch_next_buffer`, `log_heap_update` |
| Functions ("MethodOnType") | `PascalCase` | `MultiXactIdGetUpdateXid` |
| Locals & struct fields | `lower_snake_case`, often with a 2-3 char subsystem prefix (`rs_…`) | `scan->rs_cbuf` |
| Globals | mixed; match surrounding module | `error_context_stack`, `Log_line_prefix` |
| Macros & constants | `ALL_CAPS_SNAKE` for action macros, `PascalCase` for values of Pascal-typed constants | `CHECK_FOR_INTERRUPTS()`, `InvalidBlockNumber` |
| SQLSTATE codes | `ERRCODE_*` | `ERRCODE_DIVISION_BY_ZERO` |

**Two operational rules:**
1. If you add a new typedef, also add it to
   `source/src/tools/pgindent/typedefs.list` — otherwise pgindent
   mis-spaces uses of the new type.
2. Don't give a function the same name as a typedef. pgindent will
   mangle both.

## Error message style (when wrapping in `errmsg`/`errdetail`/`errhint`)

| Slot | First letter | Terminal punctuation | Sentence shape |
|---|---|---|---|
| `errmsg` (primary) | lower-case | none | fragment, one line |
| `errdetail`, `errhint` | Capital | `.` | complete sentences |
| `errcontext` | lower-case | none | fragment |

- Active voice. Past tense ("could not …") for recoverable; present
  tense ("cannot …") for permanent.
- No contractions. Use "cannot", never "can't".
- Avoid "unable", "illegal", "bad", "unknown" → prefer "cannot/could
  not", "invalid", "unrecognized".
- Quote user-supplied identifiers, file names, GUC names with `"%s"`.
- `%m` expands to `strerror(errno)`.
- State the *reason*. `could not open file "%s": %m` — not `open()
  failed`.
- Wrap user-visible literal strings in `_("…")` so `xgettext` extracts
  them. `errmsg` already does this internally; `errmsg_internal` does
  not.

## `PG_TRY` / `PG_CATCH` rules

```c
PG_TRY();
{
    /* code that might ereport(ERROR) */
}
PG_CATCH();
{
    /* release resources held across the TRY */
    PG_RE_THROW();
}
PG_END_TRY();
```

- Don't use `PG_TRY` for ordinary control flow.
- Always `PG_RE_THROW()` from `CATCH` unless you have a specific reason
  to swallow (e.g. a PL exception handler).
- Don't `return`/`goto`/`break`/`continue` out of the `TRY` block.
- Any resource (lock, buffer, file, palloc'd memory you can't let
  context cleanup handle) acquired inside the `TRY` must be released in
  the `CATCH` before re-throwing.

## Before you commit

```bash
src/tools/pgindent/pgindent .   # pretty-print
# inspect git diff; restore mangled files with git checkout
make -s clean && make -s all    # warnings = bugs
make check-world                # full regression
make -s headerscheck            # if you touched a public header
make -s cpluspluscheck          # ditto
```

If pgindent insists on changes outside your patch:
1. Did you add a typedef? Put it in
   `src/tools/pgindent/typedefs.list`.
2. Did you name a function the same as a typedef? Rename one.
3. Mismatched braces inside an `#if`? Restructure.

Other committing-checklist items relevant to style:
- `*printf` calls: check trailing newlines.
- Catalog change? Bump `CATALOG_VERSION_NO`.
- WAL/control change? Bump `PG_CONTROL_VERSION` etc.
- Regression-test names: `regress_*` pattern.
- `EXPLAIN` in tests: use `COSTS OFF` so output is portable.

## When in doubt: imitate the neighbours

> "Make the new code look like the existing code around it."
> — PG docs, Source Formatting

If two patterns exist in the tree (snake_case vs PascalCase for
functions, parenthesized vs un-parenthesized `ereport` aux calls, etc.),
match the file you are editing. Consistency *within* a file matters more
than picking the globally "right" answer.

## See also

- Long-form rationale and citations: `knowledge/conventions/coding-style.md`
- Error-handling deep-dive: `.claude/skills/error-handling/SKILL.md` (when written)
- Memory contexts: `.claude/skills/memory-contexts/SKILL.md` (when written)
- Patch submission flow: `.claude/skills/patch-submission/SKILL.md` (when written)
- Build & run: `.claude/skills/build-and-run/SKILL.md`
