# Developer_FAQ — distilled

Source: https://wiki.postgresql.org/wiki/Developer_FAQ
Crawled: 2026-06-01. Re-verify quotes before citing in code commentary.

Reorganized by topic. Items below are paraphrased unless quoted.

---

## Source tree layout

- `src/backend/` — backend (server) components [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
- `src/tools/` — developer utilities [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
- `src/tools/editors/` — emacs / vim config snippets to match PG style
  [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
- `src/test/regress/` — main regression test suite
  [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
- `src/test/isolation/` — concurrency / isolation tests
  [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
- `src/include/catalog/` — system catalog headers; OID assignment lives
  here [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
- `src/backend/parser/scan.l` (flex lexer) and `gram.y` (bison grammar)
  [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).

## Coding style (FAQ-level)

> "BSD style, with each level of code indented one tab stop, where each
> tab stop is four columns."
> [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ)

- Run `pgindent` at least once per dev cycle
  [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
- Block comments starting with `/*------` are **exempt** from pgindent
  reformatting [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
- Pager: `less -x4` or `more -x4` to view tabs correctly
  [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
- Authoritative source-style doc is the official PG docs, not the wiki:
  https://www.postgresql.org/docs/current/source.html [from-wiki](https://wiki.postgresql.org/wiki/Reviewing_a_Patch).

## Build & configure (autoconf path)

Recommended developer configure invocation:

```
./configure --enable-cassert --enable-debug \
  CFLAGS="-ggdb -Og -g3 -fno-omit-frame-pointer"
```

[from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ)

- `--enable-cassert` turns on assertions — catch bugs early
  [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
- `--enable-depend` for automatic header dep tracking
  [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
- Note: PG ≥ 16 default is **meson**; the FAQ still leans on autoconf
  examples [inferred] — cross-check with current source tree before
  citing in setup instructions.

## Debugging

- `SELECT pg_backend_pid()` in psql, then `gdb -p $PID`
  [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
- Set breakpoint at `errfinish` to trap any `elog`/`ereport`
  [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
- Dump memory contexts in gdb: `p MemoryContextStats(TopMemoryContext)`
  [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
- Suppress SIGUSR1 noise (used by PG for procsignal): in gdb,
  `handle SIGUSR1 noprint pass`
  [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
- For initdb debugging: breakpoint on `fork`, find child via `pstree -p`,
  attach a second gdb [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
- 0x7f bytes in a variable are CLOBBER_FREED_MEMORY sentinel — you're
  reading freed memory [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
- Tools mentioned: `perf` (Linux profiler), `rr` (record/replay, PG 13+),
  `valgrind` (set `#define USE_VALGRIND` in `pg_config_manual.h`),
  `gdbpg` (gdb macros for PG)
  [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).

## Memory management

- Use `palloc()` / `pfree()`, not `malloc`/`free`
  [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
- Memory contexts are hierarchical; cleanup is automatic at query end
  [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
- Don't mutate tuples in place; use `heap_modifytuple()` then
  `heap_update()` [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
- Always call `ReleaseSysCache()` after `SearchSysCache()`
  [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).

## System catalogs

- Preferred access: `SearchSysCache()` (cached, indexed)
  [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
- Fallback: `heap_open()` + `heap_beginscan()` + `heap_getnext()`
  [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
- Fixed-width columns: `GETSTRUCT()` cast → `Form_pg_class` etc.
- Variable-width columns: `heap_getattr()`
  [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).

## OID assignment (for new catalog entries)

- Hand-assigned OIDs are in range **1–9999** (globally unique across
  all catalogs) [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
- Use `src/include/catalog/unused_oids` script to find free IDs
  [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
- Prefer ranges starting in 8000–9999
  [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).

## Node / List

- `Node`/`List` are PG's generic container system, discriminated by
  `NodeTag` [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
- List macros: `lfirst()`, `lnext()`, `foreach()`, `lcons()`, `lappend()`
  [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
- In gdb: `call print(ptr)` or `call pprint(ptr)` to dump a node tree
  (output goes to the server log) [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).

## Error handling

- Use `ereport()` (full-featured) or `elog()` (simple, mostly
  DEBUG/INTERNAL) [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
- `CommandCounterIncrement()` makes the effects of preceding commands
  visible to subsequent commands within the same transaction
  [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).

## Parser

- `scan.l` (flex) → tokens; `gram.y` (bison) → parse tree
  [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
- > "Beware, though, that you'll have a rather steep learning curve
  > ahead of you if you've never used flex or bison before."
  > [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ)
- See `Fixing_shift/reduce_conflicts_in_Bison` for that classic problem.

## Patch flow (FAQ-level — see also Submitting_a_Patch)

1. **Propose** on pgsql-hackers before non-trivial work
   [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
2. **Test**: `make check` (regression), `make isolation`
   (concurrency) [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
3. **Submit** per Submitting_a_Patch; **track** in CommitFest
   [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
4. **No copyright assignment required**; contributions are under the
   PG license and contributor retains copyright
   [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).

## Testing

- Regression tests: `make check` (against a temporary install) or
  `make installcheck` (against an existing install)
  [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
- Isolation tests for concurrency
  [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
- Valgrind, perf, rr, core dumps, standalone backend all covered in the
  Debugging section [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).

---

## Open questions

- FAQ leans on autoconf wording; current default is meson (PG ≥ 16). The
  wiki has not been fully migrated. When following the FAQ's build
  recipes, translate to meson where appropriate (this repo's
  `.claude/skills/build-and-run/SKILL.md` is the in-repo source of truth).
- FAQ references **Backend_flowchart** as a link, but that wiki URL
  returned 404 in our crawl. The flowchart asset itself lives in the
  source tree / official site.
- "Coding_Conventions" wiki page is referenced from the FAQ but we did
  not successfully fetch it; treat
  https://www.postgresql.org/docs/current/source.html as the primary
  style document and the FAQ snippets above as the wiki-side summary.
