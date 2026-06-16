# `src/include/regex/regcustom.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~101
- **Source:** `source/src/include/regex/regcustom.h`

PG-specific environmental overrides for the upstream Henry Spencer
regex engine. Bridges Spencer's `MALLOC`/`FREE`/`REALLOC`/`INTERRUPT`/
`FUNCPTR`/`assert` hooks to PG's palloc / CHECK_FOR_INTERRUPTS /
Assert. Pulled in by `regguts.h` before the rest of the engine, and
also (with a deliberate coding-conventions violation) includes
`postgres.h`. [verified-by-code] [from-comment]

## API / declarations

- Includes: `postgres.h` (deliberately violates "no postgres.h in
  headers" rule — comment explicitly waives it),
  `<ctype.h>`/`<limits.h>`/`<wctype.h>`, `mb/pg_wchar.h`,
  `miscadmin.h` (for `CHECK_FOR_INTERRUPTS`). [verified-by-code]
- Allocator macros — every regex allocation goes through PG with
  `MCXT_ALLOC_NO_OOM` so a malloc-style NULL return is propagated
  rather than throwing `ereport(ERROR)`:
  `MALLOC(n) = palloc_extended((n), MCXT_ALLOC_NO_OOM)`,
  `FREE(p) = pfree(VS(p))`,
  `REALLOC(p,n) = repalloc_extended(VS(p),(n), MCXT_ALLOC_NO_OOM)`,
  `MALLOC_ARRAY(type, n)`, `REALLOC_ARRAY(p, type, n)`.
  [verified-by-code]
- `INTERRUPT(re) = CHECK_FOR_INTERRUPTS()` — lets a long-running
  regex be cancelled via the standard signal path.
- `FUNCPTR(name, args) = (*name) args` — pointer-call macro flavor
  override.
- `assert(x)` → `Assert(x)`.

### Character type machinery

- `chr` = `pg_wchar`, `uchr` = `unsigned`.
- `CHR(c) = (unsigned char)(c)` — promotes char literal to chr.
- `DIGITVAL(c) = (c)-'0'`.
- `CHRBITS=32`, `CHR_MIN=0x00000000`, `CHR_MAX=0x7ffffffe` (with the
  constraints "`CHR_MAX-CHR_MIN+1` must fit in an int, and
  `CHR_MAX+1` must fit in a chr variable"). [from-comment]
- `CHR_IS_IN_RANGE(c)` — defined as `((c) <= CHR_MAX)` to avoid
  compiler warnings about the unsigned `>=0` check. May
  multi-evaluate `c` — caller's responsibility. [from-comment]
- `MAX_SIMPLE_CHR = 0x7FF` — cutoff between simple (flat array)
  and complicated (range-table) colormap logic, sized for Unicode.
  [from-comment]

### Character-class predicates

- `iscalnum`/`iscalpha`/`iscdigit`/`iscspace` route to
  `regc_wc_isalnum`/`isalpha`/`isdigit`/`isspace` (defined in
  `backend/regex/regc_locale.c`).

## Notable invariants / details

- `palloc_extended(MCXT_ALLOC_NO_OOM)` is critical: Spencer's
  internal code checks the return value for NULL and propagates
  `REG_ESPACE`. If MALLOC ever ereport'd on OOM, a longjmp out of
  the regex engine would leak the partially-built NFA.
  [inferred] [verified-by-code]
- "It's against Postgres coding conventions to include postgres.h
  in a header file, but we allow the violation here because the
  regexp library files specifically intend this file to supply
  application-dependent headers" — explicit waiver of the
  `postgres.h-in-header` rule. [from-comment]

## Potential issues

- `CHR_IS_IN_RANGE` may multi-evaluate its argument — the comment
  says "Callers should assume that the macro may multiply evaluate
  its argument, even though it does not today." Subtle trap if a
  later refactor adds an actual range comparison.
  [ISSUE-undocumented-invariant: multi-eval forewarning in macro
  (nit)]
- `CHR_MAX = 0x7ffffffe` is one below `INT32_MAX`; relying on
  `CHR_MAX+1` fitting in `chr` (= `pg_wchar` = `unsigned`) is fine,
  but if `pg_wchar` ever changed to a signed type this would break
  silently. [ISSUE-undocumented-invariant: pg_wchar must remain
  unsigned-int-wide (maybe)]
- `REALLOC_ARRAY` comment: "XXX this definition does not provide
  the desired overflow check" — long-standing TODO inherited from
  upstream. [ISSUE-stale-todo: REALLOC_ARRAY overflow check (likely)]
  Note: in `regcustom.h` PG overrides `REALLOC_ARRAY` to
  `repalloc_array_extended` which does include overflow detection,
  so the stale TODO actually lives in regguts.h's fallback path.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-regex`](../../../../issues/include-regex.md)
<!-- issues:auto:end -->
