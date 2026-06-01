# PostgreSQL C coding style & conventions

Long-form reference for how PG backend C code is supposed to look. Every
concrete claim carries a confidence tag; unverified items are listed at the
bottom.

Verified against source at the tree currently mounted at `source/` (PG 19
devel; copyright headers say `1996-2026`, per `source/src/backend/access/heap/heapam.c:6`).

---

## 1. Formatting — whitespace, indentation, line length

### 1.1 Tabs and indentation
- **Use hard tabs for indentation; one tab per nesting level.**
  [from-docs](https://www.postgresql.org/docs/current/source-format.html)
  ("Each level of code is indented one tab stop … tab stops every four
  columns.")
- **Tab width = 4 columns** (for display only — the file actually contains a
  literal `\t`). [from-readme] `source/.editorconfig` lines for `*.[chly]`
  set `indent_style = tab`, `tab_width = 4`. [from-readme]
  `source/.dir-locals.el` `(c-basic-offset . 4) (indent-tabs-mode . t)
  (tab-width . 4)`.
- **Do not expand tabs to spaces.** [from-readme] `pgindent` invokes
  `pg_bsd_indent` with `-ts4 -i4`, the BSD-indent flags that preserve tabs
  (`source/src/tools/pgindent/pgindent:42`).
- View files with `less -x4` / `more -x4` to render tabs correctly.
  [from-docs](https://www.postgresql.org/docs/current/source-format.html)

### 1.2 Line length
- **Target ~80 columns**, but it is a guideline, not a hard wrap. Don't
  fracture a long translatable error string just to fit.
  [from-docs](https://www.postgresql.org/docs/current/source-format.html)
- `pg_bsd_indent` is invoked with `-l79`
  (`source/src/tools/pgindent/pgindent:42`), so pgindent will reflow lines
  ≥80 cols where it can. [verified-by-code]
- Emacs `fill-column` is set to **78** for C/SGML/nxml in
  `source/.dir-locals.el` — used for *comment* fill, not enforced on code.
  [from-readme]

### 1.3 Brace style: BSD / Allman
- Opening brace on its own line at the same indent as the keyword.
  [from-docs](https://www.postgresql.org/docs/current/source-format.html)
  ("curly braces for control blocks … go on their own lines.")
- Function definitions: return type alone on one line, name + `(` on the
  next, opening `{` in column 1. [verified-by-code]
  `source/src/backend/access/heap/heapam.c:754-757`:

  ```c
  static pg_noinline BlockNumber
  heapgettup_initial_block(HeapScanDesc scan, ScanDirection dir)
  {
      Assert(!scan->rs_inited);
  ```

- A *single-statement* `if`/`else` body is written without braces, on its
  own line at +1 indent. [verified-by-code]
  `source/src/backend/access/heap/heapam.c:743-744`:
  `if (BufferIsValid(scan->rs_cbuf)) scan->rs_cblock = …;` — split across
  two lines, no braces.
- `else` lives on its own line after the closing `}` of the `if`
  block. [verified-by-code] `heapam.c:764-769`.

### 1.4 Pointer & function-pointer formatting
- Pointer star binds to the variable: `char *Log_line_prefix = NULL;`
  [verified-by-code] `source/src/backend/utils/error/elog.c:115`.
- In function *return types*, a single space precedes `*`. pgindent
  enforces this with the regex `s!^([A-Za-z_]\S*)[ \t]+\*$!$1 *!gm`
  (`source/src/tools/pgindent/pgindent:294`). [verified-by-code]
- For function pointers stored in plain variables, **explicitly
  dereference** when calling: `(*emit_log_hook)(edata);`. For function
  pointers inside structs, drop the punctuation:
  `paramInfo->paramFetch(paramInfo, paramId);`.
  [from-docs](https://www.postgresql.org/docs/current/source-conventions.html)

### 1.5 What pgindent normalizes (so don't fight it)
[from-readme] `source/src/tools/pgindent/README`,
[verified-by-code] `source/src/tools/pgindent/pgindent`.

`pg_bsd_indent` flags (line 42): `-bad -bap -bbb -bc -bl -cli1 -cp33 -cdb
-nce -d0 -di12 -nfc1 -i4 -l79 -lp -lpl -nip -npro -sac -tpg -ts4`. Notable
effects:

| What pgindent does | Where |
|---|---|
| Converts `// …` to `/* … */` | pgindent:248 |
| Forces tab between run-together `*/`-`/*` comments | pgindent:286 |
| Reflows multi-line `/* … */` comments unless they start with `/*---` or `/*===` | pgindent:289, 312, 330 |
| Splits text on the first line of a multi-line comment onto its own line | pgindent:314 |
| Aligns return-type `*` with a single space | pgindent:294 |
| Doesn't touch `extern "C" { … }` braces | pgindent:259-261 |
| Doesn't touch `CATALOG(...)` declarations | pgindent:264, 274 |
| Skips files derived from `.y` / `.l` | pgindent:470-475 |

**Practical rules:**
1. Add new typedef names to `source/src/tools/pgindent/typedefs.list` or
   pgindent will mis-space them. [from-readme]
   `source/src/tools/pgindent/README:46-48`.
2. Don't name a function the same as a typedef — pgindent will mangle both.
   [from-readme] `README:122-124`.
3. To protect a hand-formatted comment block from reflow, open it
   `/*-------` (any number of `-`). [from-docs+from-readme]

### 1.6 Comment style
- **No C++ `//` comments.** Use `/* … */`. C99's `//` is explicitly
  banned by project convention (and pgindent rewrites them anyway).
  [from-docs](https://www.postgresql.org/docs/current/source-conventions.html),
  [verified-by-code] pgindent:248.
- **Standard multi-line block** — leading `*` on every continuation line,
  one space before `*`:

  ```c
  /*
   * comment text begins here
   * and continues here
   */
  ```
  [from-docs](https://www.postgresql.org/docs/current/source-format.html)

- **Format-preserving block** — opens `/*---` (or `/*===`), closes
  `*---*/` (or `*===*/`). pgindent will not reflow. [from-readme]
  `README:112-118`.
- **File header block** is itself a format-preserving comment. Pattern
  verified in `source/src/backend/access/heap/heapam.c:1-31`:

  ```c
  /*-------------------------------------------------------------------------
   *
   * heapam.c
   *      heap access method code
   *
   * Portions Copyright (c) 1996-2026, PostgreSQL Global Development Group
   * Portions Copyright (c) 1994, Regents of the University of California
   *
   *
   * IDENTIFICATION
   *      src/backend/access/heap/heapam.c
   *
   *
   * INTERFACE ROUTINES
   *      …
   *
   * NOTES
   *      …
   *
   *-------------------------------------------------------------------------
   */
  ```
  [verified-by-code]

  Both copyright lines are mandatory: PG global dev group + 1994 Regents
  of UC. The IDENTIFICATION block lists the path relative to source root.
- **Function header comment** sits directly above the function, starts
  with the function name, then describes what it does and any
  non-obvious preconditions/postconditions. [verified-by-code]
  `source/src/backend/access/heap/heapam.c:703-708`,
  `:747-753`.
- Comments anchored in column 1 (file/function headers) are not reflowed
  by pgindent. [from-readme] wiki Developer FAQ.

---

## 2. File structure

### 2.1 `#include` order — postgres.h FIRST
**The single most important include rule.** A `.c` file must include
`postgres.h` (backend), `postgres_fe.h` (frontend), or `c.h` (shared
infrastructure) as the **very first** include, before *any* system header.
[from-wiki](https://wiki.postgresql.org/wiki/Committing_checklist)
("`.c` files should include `postgres.h`, `postgres_fe.h`, or `c.h` first,
then system headers, then other Postgres headers.")

[verified-by-code] `source/src/backend/access/heap/heapam.c:32-57`:

```c
#include "postgres.h"

#include "access/heapam.h"
…
```

[verified-by-code] `source/src/backend/utils/error/elog.c:55-91` — same
pattern, but with system headers between `postgres.h` and the project
headers:

```c
#include "postgres.h"

#include <fcntl.h>
#include <time.h>
…
#include "access/xact.h"
…
```

Layout convention: blank line after `postgres.h`, then system headers
(if any) in alphabetical-ish order, then a blank line, then project
`"…"` headers grouped and sorted. [verified-by-code] same files.

### 2.2 Header self-containment
Every public header in `src/include/**` must compile **stand-alone** —
i.e. you can `#include` it after `postgres.h` and nothing else and it
must work. Enforced by `make headerscheck` / `meson compile -C build
headerscheck`. [from-readme]
`source/src/tools/pginclude/README:45-71`.

Headers must also compile as C++ (`make cpluspluscheck`) so extension
authors who use C++ can include them. [from-readme]
`source/src/tools/pginclude/README:74-101`.

`include-what-you-use` (IWYU) is the recommended cleanup tool, with
project-specific `IWYU pragma` comments scattered through the tree.
[from-readme] `source/src/tools/pginclude/README:7-43`.

### 2.3 Static function prototypes at the top
Forward declarations of all `static` functions in the file appear in a
block after the includes, before any function definition. [verified-by-code]
`source/src/backend/access/heap/heapam.c:60-113`.

---

## 3. C standard & portability

### 3.1 C99 baseline, with caveats
- **PostgreSQL targets C99.**
  [from-docs](https://www.postgresql.org/docs/current/source-conventions.html)
  > "Code in PostgreSQL should only rely on language features available
  > in the C99 standard."
- **Banned C99 features (still!):** variable-length arrays, intermingled
  declarations and code (i.e. you must declare locals at the top of a
  block before any statement), `//` comments, universal character names
  (`\uXXXX`). Reasons: portability and historical practice.
  [from-docs](https://www.postgresql.org/docs/current/source-conventions.html)
- Post-C99 features (e.g. `_Static_assert`, GCC `__builtin_constant_p`)
  are allowed **only with a fallback** for compilers that lack them.
  [from-docs](https://www.postgresql.org/docs/current/source-conventions.html)

### 3.2 Macros vs `static inline`
- Both are allowed. Prefer `static inline` when a macro would have
  multiple-evaluation hazards.
  [from-docs](https://www.postgresql.org/docs/current/source-conventions.html)
- An inline function in a header that references backend-only symbols
  must be guarded with `#ifndef FRONTEND` so the same header is usable
  from frontend code.
  [from-docs](https://www.postgresql.org/docs/current/source-conventions.html)

### 3.3 Signal handlers
Inside a signal handler you may only call async-signal-safe POSIX
functions, and only touch `volatile sig_atomic_t` variables — unless
explicit arrangements (e.g. `SetLatch`) say otherwise.
[from-docs](https://www.postgresql.org/docs/current/source-conventions.html)

---

## 4. Naming

The wiki page `Coding_Conventions` is currently a 404 [unverified]. Names
below are read out of the source.

### 4.1 Function names
- Backend C functions are predominantly **lower_snake_case** when they
  represent verbs/operations: `heap_fetch_next_buffer`,
  `heap_prepare_insert`, `log_heap_update`, `heapgettup_initial_block`.
  [verified-by-code] `source/src/backend/access/heap/heapam.c:60-113`,
  `:709`, `:754`.
- **PascalCase / CamelCase** is also widely used, especially for older
  modules and for functions named after types they operate on:
  `HeapDetermineColumnsInfo`, `MultiXactIdGetUpdateXid`,
  `GetMultiXactIdHintBits`, `ExtractReplicaIdentity`.
  [verified-by-code] `heapam.c:73, 97, 99, 112`.
- **Rule of thumb** (from reading): follow the convention already used by
  the surrounding subsystem and by similar functions on the same type.
  Heap "verbs" → snake_case; "MethodOnType" → PascalCase. [inferred]

### 4.2 Variable names
- Locals and struct fields: lower_snake_case. `scan->rs_cbuf`,
  `old_infomask2`, `error_context_stack`. [verified-by-code]
  `heapam.c:743`, `elog.c:100`.
- Struct field prefix idiom: short tag tied to the struct
  (`rs_` for `HeapScanDesc`-relative state). [verified-by-code]
  `heapam.c:712-744`.
- Globals: usually PascalCase or snake_case depending on age, e.g.
  `Log_error_verbosity`, `Log_line_prefix`, `error_context_stack`,
  `PG_exception_stack`. [verified-by-code] `elog.c:100-118`.

### 4.3 Types and typedefs
- Types are PascalCase with no `_t` suffix: `HeapTuple`, `Relation`,
  `Buffer`, `TransactionId`, `MemoryContext`, `ErrorContextCallback`.
  [verified-by-code] `heapam.c` declarations, `elog.c:100`.
- Every new typedef must be added to
  `source/src/tools/pgindent/typedefs.list` or pgindent will get the
  spacing wrong. [from-readme] pgindent/README:46-48.

### 4.4 Macros and constants
- ALL_CAPS, snake_case: `CHECK_FOR_INTERRUPTS()`, `BUFFER_LOCK_UNLOCK`,
  `InvalidBlockNumber` (constant but Pascal-cased because it's a value
  of a PascalCase type), `ERRCODE_DIVISION_BY_ZERO`, `SIGNAL_ARGS`.
  [verified-by-code] `heapam.c:700, 726, 762`.
- Error-code macros: `ERRCODE_*` (uppercase, underscored). [from-docs]

### 4.5 Reserved name prefixes
- `pg_*` — anything user-visible (functions, tables, types) is the
  project's namespace; don't repurpose it for private helpers. [inferred
  from] [from-wiki](https://wiki.postgresql.org/wiki/Committing_checklist).
- `pg_noinline`, `pg_attribute_*`, `pg_likely`, `pg_unlikely` — portable
  compiler-attribute wrappers (verified by use:
  `source/src/backend/access/heap/heapam.c:84, 754`). [verified-by-code]
- `Px*` / `PG_*` in public headers are project namespaces for macros
  (e.g. `PG_TRY`, `PG_CATCH`, `PG_FUNCTION_ARGS`). [inferred]

---

## 5. Error reporting

### 5.1 `ereport` vs `elog`
[from-docs](https://www.postgresql.org/docs/current/error-message-reporting.html)

- **`ereport(level, …)`** — user-visible errors. The message **must** be
  wrapped for translation (via `errmsg`, which calls `gettext` under the
  hood), and should carry a SQLSTATE via `errcode(…)`.
- **`elog(level, fmt, …)`** — "cannot happen" / internal / debug. The
  message is *not* translated; `errcode` defaults. Use only for things
  end users should never see in normal operation.

Canonical form (PG 12+ allows omitting the inner parentheses around the
aux calls):

```c
ereport(ERROR,
        errcode(ERRCODE_DIVISION_BY_ZERO),
        errmsg("division by zero"));
```

Older style (still common in the tree, still valid):

```c
ereport(ERROR,
        (errcode(ERRCODE_DIVISION_BY_ZERO),
         errmsg("division by zero")));
```

### 5.2 Severity levels
[from-docs](https://www.postgresql.org/docs/current/error-message-reporting.html)

| Level | Behaviour |
|---|---|
| `DEBUG1`–`DEBUG5` | dev/diagnostic; gated by `client_min_messages`/`log_min_messages` |
| `LOG` | server log only by default |
| `INFO` / `NOTICE` / `WARNING` | flow continues |
| `ERROR` | longjmps out of the current query (PG_TRY/PG_CATCH catches) |
| `FATAL` | terminates the session |
| `PANIC` | terminates the whole cluster (restarts postmaster) |

`ERROR` and above **never return** — code after `ereport(ERROR, …)` is
unreachable.

### 5.3 Auxiliary calls inside `ereport`
- `errcode(ERRCODE_*)` — five-character SQLSTATE. Required for anything
  user-facing.
- `errmsg("…", …)` — primary message; passed through `gettext`. `%m`
  expands to `strerror(errno)`. [from-docs]
- `errmsg_internal("…", …)` — same as `errmsg` but skips translation;
  for "cannot happen" cases that still want SQLSTATE / structure.
- `errdetail("…")`, `errhint("…")`, `errcontext("…")` — optional;
  detail/hint are complete sentences (see §6).

### 5.4 `_(…)` gettext wrapping
Inside `elog.c`, the `_` macro is redefined to call `err_gettext`
locally:

```c
/* In this module, access gettext() via err_gettext() */
#undef _
#define _(x) err_gettext(x)
```
[verified-by-code] `source/src/backend/utils/error/elog.c:94-97`.

Elsewhere, string literals destined for translation are wrapped `_("…")`
so `xgettext` extracts them.

---

## 6. Error message style guide
[from-docs](https://www.postgresql.org/docs/current/error-style-guide.html)

| Slot | Capitalization | Punctuation | Sentence shape |
|---|---|---|---|
| Primary `errmsg` | lower-case first letter | no terminal period, no `!` | usually a fragment, one line |
| `errdetail` / `errhint` | Capital | period at end | complete sentences |
| `errcontext` | lower-case | no period | fragment |

Other rules to keep in mind:
- **Active voice**, not passive.
- **Past tense** ("could not …") for recoverable failures; **present
  tense** ("cannot …") for permanent impossibilities.
- No contractions ("cannot", never "can't").
- Avoid: "unable", "illegal", "bad", "unknown" → prefer "cannot/could not",
  "invalid", "unrecognized".
- Quote user-supplied identifiers, file names, GUC names with **double
  quotes**: `"%s"`. Don't quote output of `format_type_be()` etc.
- Always state the *reason* for the failure when you can.
- No function-name leakage: write `could not open file "%s": %m`, not
  `open() failed: %m`.
- No client-side line wrapping; `\n` only for paragraph breaks.

---

## 7. Memory management

- **Use `palloc` / `pfree` / `repalloc`**, not `malloc` / `free` /
  `realloc`, anywhere in the backend.
  [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ) ("palloc()
  and pfree() are used in place of malloc() and free() because we find it
  easier to automatically free all memory allocated when a query
  completes.")
- All allocations live in a `MemoryContext`. The current allocation
  target is `CurrentMemoryContext`; switch with `MemoryContextSwitchTo`.
  See `idioms/memory-contexts.md` (when written).
- Frontend / common code uses `pg_malloc` / `pg_free` wrappers from
  `src/common`. [inferred]
- For strings, prefer `pstrdup` over `strdup`; `psprintf` over manual
  `malloc + snprintf`. [inferred from PG-wide pattern]

---

## 8. Assertions & defensive code

- `Assert(cond)` — compiled in only when `USE_ASSERT_CHECKING` is
  defined (i.e. `--enable-cassert` builds, or meson `-Dcassert=true`).
  [verified-by-code] usage:
  `source/src/backend/access/heap/heapam.c:712, 757-758`; conditional
  block guarded explicitly: `heapam.c:67-72`:

  ```c
  #ifdef USE_ASSERT_CHECKING
  static void check_lock_if_inplace_updateable_rel(…);
  static void check_inplace_rel_lock(HeapTuple oldtup);
  #endif
  ```
- **Asserts must be side-effect free.** Anything that has to run in
  production goes outside the Assert. [inferred from] common PG review
  feedback; the macro vanishes in non-assert builds.
- `StaticAssertDecl(cond, "msg")` / `StaticAssertStmt(cond, "msg")` —
  compile-time, prefer when applicable. [from-docs]
  `source-conventions.html` mentions `_Static_assert` is used with a
  fallback.
- For dev builds, the wiki recommends configuring with
  `--enable-cassert --enable-debug CFLAGS="-ggdb -Og -g3
  -fno-omit-frame-pointer"`.
  [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ)

---

## 9. `PG_TRY` / `PG_CATCH`

[from-comment] `source/src/backend/utils/error/elog.c:12-43` (the long
"notes about recursion" comment) — the error subsystem is built around
`sigsetjmp`/`siglongjmp` with `PG_exception_stack` as the current jump
target. `ereport(ERROR)` longjmps out.

Usage pattern (verified from many call sites; the canonical shape):

```c
PG_TRY();
{
    /* code that might ereport(ERROR) */
}
PG_CATCH();
{
    /* cleanup; if you don't re-throw, the error is swallowed */
    PG_RE_THROW();
}
PG_END_TRY();
```

Rules of thumb [inferred from idiom, to verify]:
- Don't use `PG_TRY` for ordinary control flow — it is expensive and
  hides bugs.
- Always `PG_RE_THROW()` from the `CATCH` block unless you have an
  explicit, well-justified reason to swallow the error.
- Resources held across the `TRY` (locks, buffers, files) must be
  released in the `CATCH` block — they will not be unwound for you.
- Don't `return` / `goto` out of a `PG_TRY` block.

See `idioms/error-handling.md` (when written) for the detailed treatment.

---

## 10. Other portability / hygiene rules

### 10.1 `printf` family
- The committing checklist requires validating `*printf` calls for
  trailing newlines.
  [from-wiki](https://wiki.postgresql.org/wiki/Committing_checklist)
- For server-side messages prefer `ereport`/`elog` over `fprintf(stderr,
  …)`. [inferred]

### 10.2 Frontend vs backend
- `FRONTEND` macro distinguishes client-side code; some helpers
  (e.g. `MemoryContextSwitchTo`) are backend-only.
  [from-docs](https://www.postgresql.org/docs/current/source-conventions.html)
- Include `postgres_fe.h` (frontend) or `c.h` (very common
  infrastructure) instead of `postgres.h` for non-backend `.c` files.
  [from-wiki](https://wiki.postgresql.org/wiki/Committing_checklist)

### 10.3 `extern "C"` in headers
Public headers must compile under a C++ compiler (`cpluspluscheck`).
Most headers wrap declarations in `extern "C" { … }` under
`#ifdef __cplusplus`. pgindent has special handling so it doesn't
re-indent the body
(`source/src/tools/pgindent/pgindent:255-261`). [verified-by-code]

### 10.4 Catalog-data files
`CATALOG(...)` macro lines in `src/include/catalog/pg_*.h` are
parsed by genbki; pgindent protects them from reformatting
(`pgindent:264`). The bootstrap data lives in `pg_*.dat` files and is
reformatted by `make reformat-dat-files`.
[from-readme] `source/src/tools/pgindent/README:86-91`.

### 10.5 Catalog version bumps
Any catalog-affecting change must bump `CATALOG_VERSION_NO`. WAL/protocol
changes bump `PG_CONTROL_VERSION` etc.
[from-wiki](https://wiki.postgresql.org/wiki/Committing_checklist)

### 10.6 Static analysis & warnings
- `-Wall` clean is mandatory; new warnings block commits in practice.
  [inferred from] committing-checklist tone.
- `IWYU` (`include-what-you-use`) v0.23+ is the recommended include
  cleanup tool. [from-readme] `pginclude/README:24-29`.
- `headerscheck` (regular + `--cplusplus`) gate header changes.
  [from-readme] `pginclude/README`.
- The committing checklist also mentions `pgperlcritic` for Perl code,
  and spelling checks. [from-wiki]

---

## 11. Workflow: pgindent before commit

[from-readme] `source/src/tools/pgindent/README:30-64`.

Before a normal commit:

```bash
src/tools/pgindent/pgindent .
# inspect diff; restore any file pgindent mangled with git checkout
git status            # ensure no .BAK / .LOG leftovers
make -s clean && make -s all
make check-world
```

If pgindent insists on touching code outside your patch:
1. New typedef? add it to `src/tools/pgindent/typedefs.list`.
2. Function named the same as a typedef? rename one of them.
3. `#if` block with unbalanced braces seen as a whole? rearrange.

Per release cycle the typedef list is regenerated from the buildfarm:

```bash
wget -O src/tools/pgindent/typedefs.list \
  https://buildfarm.postgresql.org/cgi-bin/typedefs.pl
```

The bulk reformat commit gets added to `.git-blame-ignore-revs`.
[from-readme] `README:96-101`.

---

## 12. Quick reference: things that trip up generic C programmers

1. **`postgres.h` is always include #1.** Not `<stdio.h>`, not even
   `<string.h>`. It defines things (like `bool`) those system headers
   could shadow. [from-wiki]
2. **No `//` comments. No VLA. No `int x; x = 1; int y;` mid-block.**
   C99-the-subset, not C99-the-whole-thing.
   [from-docs](https://www.postgresql.org/docs/current/source-conventions.html)
3. **No `malloc`. No `strdup`. No `free`.** Use `palloc` / `pstrdup` /
   `pfree` and live inside the right MemoryContext.
   [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ)
4. **Tabs are real characters in the file.** Tab = 4 columns visually,
   but it's `\t`, not 4 spaces. Editor config matters.
5. **`ereport(ERROR, …)` does not return.** Stop reasoning past it. Free
   nothing after; the memory context machinery handles cleanup at
   transaction-abort time.
6. **`Assert` disappears in release builds.** Never put a side-effect
   inside.
7. **Headers must compile alone AND as C++.** That's why so many of
   them include other headers up top — they're paying the cost of
   self-containedness.
8. **pgindent will rewrite your code on commit.** Match the surrounding
   style; if pgindent insists on a change you didn't expect, the typedef
   list is the usual culprit.
9. **Don't return / goto out of `PG_TRY`.** The longjmp accounting
   breaks.
10. **Two copyright lines or none.** "Portions Copyright (c) 1996-<year>,
    PostgreSQL Global Development Group" AND "Portions Copyright (c)
    1994, Regents of the University of California" — both, verbatim,
    in every file header. [verified-by-code] `heapam.c:6-7`,
    `elog.c:46-47`.

---

## Source map

| Source | Role |
|---|---|
| `source/.editorconfig` | tab-vs-spaces, tab-width per file glob |
| `source/.dir-locals.el` | Emacs `bsd` style, fill-column 78 |
| `source/src/tools/pgindent/README` | how/when to run pgindent |
| `source/src/tools/pgindent/pgindent` | the script; line 42 = pg_bsd_indent flags |
| `source/src/tools/pgindent/typedefs.list` | typedef names pgindent must know about |
| `source/src/tools/pgindent/exclude_file_patterns` | files pgindent skips |
| `source/src/tools/pginclude/README` | headerscheck, cpluspluscheck, IWYU |
| `source/src/backend/access/heap/heapam.c:1-115` | reference for file header + include order + forward decls |
| `source/src/backend/utils/error/elog.c:1-120` | reference for ereport infrastructure; the `_()` gettext wiring |

External:
- https://www.postgresql.org/docs/current/source-format.html — Formatting
- https://www.postgresql.org/docs/current/source-conventions.html — C99 baseline, banned features, signal handlers
- https://www.postgresql.org/docs/current/error-message-reporting.html — ereport, elog
- https://www.postgresql.org/docs/current/error-style-guide.html — message style
- https://wiki.postgresql.org/wiki/Developer_FAQ — palloc rationale, BSD style summary
- https://wiki.postgresql.org/wiki/Committing_checklist — pgindent, headerscheck, version bumps, line-length check, printf newline check

---

## Open questions / unverified items

1. The wiki page at `https://wiki.postgresql.org/wiki/Coding_Conventions`
   returns 404 as of fetch. The canonical material has migrated to
   `https://www.postgresql.org/docs/current/source-format.html` and
   `source-conventions.html`. Confirm there is no separate wiki content
   we are missing.
2. `[unverified]` Exact rule for choosing snake_case vs PascalCase for
   new backend functions. The trees mix both freely; the only rule I can
   defend is "match surrounding code". A definitive write-up may exist on
   pgsql-hackers but I have not located it.
3. `[unverified]` Whether `PG_TRY` is allowed to swallow errors
   (not re-throw) outside of `proc_exit` cleanup paths. The pattern
   exists in the tree (e.g. PL/pgSQL exception blocks), but the
   committing-checklist policy on "when may you swallow" is not written
   down where I looked.
4. `[unverified]` Strict line-length rule: docs say "~80, soft", pgindent
   says `-l79`, `.dir-locals.el` says `fill-column 78` (comments). Which
   number do reviewers actually enforce? Probably 78 for hand-wrapped
   comments, 80 for code, with reviewer discretion above that — but this
   is inference.
5. `[unverified]` Are `pg_attribute_noreturn`, `pg_attribute_printf` etc.
   *required* for functions with those properties, or merely
   *recommended*? The codebase uses them consistently for new code, but
   I did not find a formal mandate.

---

## Tag tally

- `[from-docs]`: 18
- `[from-wiki]`: 8
- `[from-readme]`: 12
- `[from-comment]`: 1
- `[verified-by-code]`: 17
- `[inferred]`: 9
- `[unverified]`: 5 (listed above)
