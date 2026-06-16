# `src/include/c.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~1525
- **Source:** `source/src/include/c.h`

The master frontend/backend compatibility header — included by **every** .c
file in PostgreSQL via either `postgres.h` (backend) or `postgres_fe.h`
(frontend). Pulls in `pg_config.h`, `pg_config_manual.h`, `pg_config_os.h`,
the std headers (`stdint.h`, `stddef.h`, `stdarg.h`, `stdbool.h`, …), and
finishes by including `port.h` for /port compatibility shims. The
declarations here are explicitly **not** for client API consumers — see
`postgres_ext.h` for that surface. [verified-by-code]

The file is organised in nine numbered sections (TOC at top): (0) std
headers; (1) compiler characteristics / attribute macros; (2) `bool`/
`true`/`false`; (3) standard system types (`int8`..`uint64`, `int128`,
`Datum`-precursor `Oid`/`TransactionId`/etc, `varlena`, `NameData`); (4)
`*IsValid` macros; (5) `lengthof` + alignment; (6) `Assert` /
`StaticAssert`; (7) `Max`/`Min`/`MemSet`; (8) `PGAlignedBlock`,
`SQL_STR_DOUBLE`, gettext; (9) system-specific hacks (`PG_BINARY`,
`PGDLLIMPORT`/`PGDLLEXPORT`, `sigjmp_buf`). [from-comment]

## API / declarations

### Section 1 — compiler attribute macros (`c.h:104-585`)

All wrappers around `__attribute__((…))`/C23 attributes with portability
fallbacks. The complete inventory: [verified-by-code]
- `pg_attribute_unused()` — `c.h:144`. C23 `[[maybe_unused]]` else GCC
  `unused`.
- `pg_fallthrough` — `c.h:157`. Marks intentional switch fall-through.
- `pg_nodiscard` — `c.h:169`. Warn if return value ignored.
- `pg_noreturn` — `c.h:187`. C11 `_Noreturn` / C23 `[[noreturn]]`. Note
  the comment at `c.h:177-186` explaining why PG avoids the standard
  spelling `noreturn`.
- `pg_attribute_no_sanitize_address()`, `pg_attribute_no_sanitize_alignment()`
  — `c.h:198,213`. Used sparingly.
- `pg_attribute_nonnull(...)`, `pg_attribute_target(...)`,
  `pg_attribute_format_arg`, `pg_attribute_printf`,
  `pg_attribute_aligned`, `pg_attribute_packed`,
  `pg_attribute_always_inline`, `pg_attribute_cold`,
  `pg_attribute_hot`, `pg_noinline` — `c.h:223-353`.
- `PG_USED_FOR_ASSERTS_ONLY` — `c.h:247`. Suppresses
  `unused-variable` warnings in non-cassert builds.
- `pg_unreachable()` — `c.h:362`. `__builtin_unreachable()` in release;
  `abort()` under cassert (intentional, for debuggability).
- `pg_integer_constant_p(x)` — `c.h:380,391`. Wraps
  `__builtin_constant_p` with MSVC `_Generic` fallback.
- `pg_assume(expr)` — `c.h:413,415,421,423`. Under cassert it's
  `Assert(expr)`; in release it's `__builtin_unreachable` /
  `__assume`. The comment at `c.h:409-410` notes `expr` may not be
  evaluated, so it must be side-effect-free.
- `likely(x)` / `unlikely(x)` — `c.h:434-438`. `__builtin_expect`.

### Section 2 — bool / `stdbool.h`

`bool` is C99 `_Bool`. The hard requirement: `sizeof(bool) == 1` —
`c.h:598` says "PostgreSQL currently cannot deal with bool of size
other than 1; there are static assertions around the code to prevent
that." [verified-by-code]

### Section 3 — standard system types (`c.h:610-833`)

- `Pointer` (obsolescent, prefer `void *`).
- `int8`..`uint64` — historical names for `<stdint.h>` types.
- `int128`/`uint128` — only when `PG_INT128_TYPE` is set AND alignment
  fits. `HAVE_INT128` is the cap.
- `Size` (= `size_t`), `Index` (`unsigned int`), `Offset` (`signed int`).
- `float4`/`float8` — catalog-visible names.
- `regproc` / `RegProcedure`, `TransactionId` = `uint32`,
  `LocalTransactionId`, `SubTransactionId`, `MultiXactId`,
  `MultiXactOffset` = `uint64`, `CommandId` = `uint32`. `Oid8`
  introduced as `uint64` at `c.h:756`.
- `varlena` struct (`c.h:775-779`) — `vl_len_[4]` + flexible
  `vl_dat[]`. Hard rule at `c.h:777`: "Do not touch this field
  directly!" — touched by `varatt.h` macros only.
- `bytea`, `text`, `BpChar`, `VarChar` — all typedef'd to `varlena`.
- `int2vector` / `oidvector` — historical layouts kept for pg_proc
  primary key (`c.h:803-823`).
- `NameData { char data[NAMEDATALEN]; }`, `Name`, `NameStr(name)`
  macro.

### Section 5 — alignment

The TYPEALIGN family at `c.h:889-921`:
```c
#define TYPEALIGN(ALIGNVAL,LEN)  \
    (((uintptr_t) (LEN) + ((ALIGNVAL) - 1)) & ~((uintptr_t) ((ALIGNVAL) - 1)))
```
Plus `SHORTALIGN`, `INTALIGN`, `INT64ALIGN`, `DOUBLEALIGN`, `MAXALIGN`,
`BUFFERALIGN`, `CACHELINEALIGN`, and the `_DOWN` variants. Hard caveat
at `c.h:881`: TYPEALIGN does **not** work if `ALIGNVAL` is not a power
of 2. `TYPEALIGN64` exists for the case where `LEN` exceeds
`uintptr_t` (32-bit platforms aligning a 64-bit value). [verified-by-code]

### Section 6 — Assert / StaticAssert (`c.h:929-1074`)

Trinity:
- `Assert(condition)` — backend-only when `USE_ASSERT_CHECKING`; calls
  `ExceptionalCondition(cond, file, line)` which is `pg_noreturn`.
  Frontend cassert uses standard `assert(3)`. Non-cassert: `((void)
  true)`.
- `AssertMacro(condition)` — usable in expression context (the comma
  operator trick at `c.h:969-971`).
- `StaticAssertDecl` / `StaticAssertStmt` / `StaticAssertExpr` —
  wrappers around `static_assert`. The MSVC < 19.33 fallback at
  `c.h:1040-1041` uses the negative-bit-field-width klugde.
- `StaticAssertVariableIsOfType[Macro]` — compile-time type check via
  `__builtin_types_compatible_p`; sizeof-fallback otherwise.

`ExceptionalCondition` is **always** compiled into the backend even
when cassert is off, so that extensions built with cassert can link
against a non-cassert backend (`c.h:982-990`). [verified-by-code]

### Section 7 — widely useful macros

- `Max` / `Min` — naive `((x)>(y)?(x):(y))`, multi-eval hazard.
- `MemSet(start, val, len)` — `c.h:1107`. Faster than libc memset for
  small size_t-aligned zero fills. Internal `if` collapses at compile
  time when `MEMSET_LOOP_LIMIT == 0`. `MemSetAligned` is the
  pre-aligned variant.
- `FLOAT[48]_FITS_IN_INT[16,32,64](num)` — range-check macros, with
  the load-bearing comment at `c.h:1164-1170`: must `rint()` first;
  NaN handling not portable.

### Section 8 — random stuff

- `INVERT_COMPARE_RESULT(var)` — flip qsort comparison without
  overflowing on `INT_MIN`.
- `PGAlignedBlock` (`c.h:1205`) — `MAXIMUM_ALIGNOF`-aligned `BLCKSZ`
  buffer. Use instead of `char buf[BLCKSZ]`.
- `PGIOAlignedBlock` (`c.h:1226`), `PGAlignedXLogBlock` (`c.h:1232`) —
  `PG_IO_ALIGN_SIZE`-aligned (4 KB). Disabled on g++ < 9 due to
  GCC bug 89357.
- `HIGHBIT`, `IS_HIGHBIT_SET`, `SQL_STR_DOUBLE`, `ESCAPE_STRING_SYNTAX`,
  `STATUS_OK/ERROR/EOF`.
- gettext machinery: `_(x) = gettext(x)`, `gettext_noop(x)`,
  `PG_TEXTDOMAIN(domain)` mangles in SO version + PG major.
- `unconstify(type, expr)` / `unvolatize(type, expr)` (`c.h:1328`) —
  with a `StaticAssertVariableIsOfTypeMacro` guard so it only strips
  const/volatile, not type.

### Section 9 — platform hacks

- `PG_BINARY` family — non-empty (`O_BINARY`/`"rb"`) on Win32/Cygwin.
- `strtoi64` / `strtou64` — choose `strtol`/`strtoll` based on
  `SIZEOF_LONG`.
- `PGDLLIMPORT` / `PGDLLEXPORT` — empty by default; on Windows
  expands to `__declspec(dllimport)`/`(dllexport)`. `PGDLLEXPORT` also
  uses `__attribute__((visibility("default")))` when
  `HAVE_VISIBILITY_ATTRIBUTE`.
- `pg_signal_info { uint32_t pid; uint32_t uid; }`, `SIGNAL_ARGS`
  macro = `int postgres_signal_arg, const pg_signal_info *pg_siginfo`.
- `sigjmp_buf` / `sigsetjmp` / `siglongjmp` — passthrough to standard
  on Unix; on MinGW-64 uses `__builtin_setjmp/longjmp` because of
  longstanding setjmp bugs (`c.h:1483-1494`).
- `char16_t` / `char32_t` — fallback typedefs when `<uchar.h>` missing
  (notably macOS, `c.h:1514-1521`).

## Notable invariants / details

- `c.h` MUST come before any system header per its TOC comment
  (`c.h:53-56`) because it defines `_FILE_OFFSET_BITS` etc. that
  affect later headers. [from-comment]
- The file MUST NOT contain `extern` declarations unless `#ifdef`'d
  per-side, because it's included by both frontend and backend
  (`c.h:41-43`). Violations break the libpq build. [from-comment]
  [ISSUE-style: `ExceptionalCondition` extern at `c.h:988` is gated
  by `!FRONTEND` per the contract; new extern declarations routinely
  miss this gate (nit)]
- `Datum` is **NOT** declared here. The comment at `postgres.h:35-39`
  explains why: types that "never escape the backend" go in
  `postgres.h`. So a frontend module that wants to inspect
  backend-formatted binary still uses `c.h`-level types like
  `varlena`. [from-comment]
- `FLOAT8PASSBYVAL` is hard-coded `true` (`c.h:720`) — a vestigial
  symbol left for extension ABI; PG no longer supports
  pass-by-reference float8. [verified-by-code]
- `varlena.vl_len_` is the only header field that source code is
  *forbidden* to touch directly; all access is via varatt.h
  macros (`c.h:769-772`). [from-comment]
- `MAXIMUM_ALIGNOF` intentionally excludes wider-than-8 types (e.g.
  `int128`) per the comment at `c.h:884-886`. This is why `int128`
  needs the explicit `pg_attribute_aligned(MAXIMUM_ALIGNOF)`. [from-comment]
- `Min`/`Max` have a known multi-evaluation hazard — the file does
  not flag this in a `WARNING:` comment, only via grep-tribal-knowledge.
  [ISSUE-undocumented-invariant: `Min`/`Max` multi-eval not flagged at definition site (nit)]
- `MemSet` macro path makes a Size-typed runtime constant — easy to
  accidentally pass a smaller integer. [ISSUE-undocumented-invariant:
  `MemSet`'s `Size _len = (len)` truncates if caller passes wider
  int (nit)]
- `pg_noreturn` is placed before return type per C23 (`c.h:182-186`).
  Old PG code may have it post-return-type, which produces a different
  diagnostic. [from-comment]
- `pg_unreachable()` deliberately is `abort()` (not `__builtin_unreachable`)
  when cassert is on, to ease debugging — but this means cassert builds
  have *different code-gen* than release, a subtle test-coverage gap.
  [ISSUE-correctness: `pg_unreachable` codegen differs between cassert
  and release; a flow that hits `abort()` in cassert may UB silently
  in release (likely)]
- `int128` typedef is silently absent on 32-bit / older compilers
  (`c.h:646-663`). `HAVE_INT128` gates use, but readers of `int128`
  arithmetic code often miss the `#ifdef HAVE_INT128` discipline.
  [ISSUE-doc-drift: `HAVE_INT128` gate not mentioned beside `int128`
  typedef (nit)]
- `PGDLLEXPORT` semantics differ across platforms; the comment at
  `c.h:1439-1452` is the only documentation for the
  visibility-attribute path. Extensions that forget this on a
  non-Windows build with `-fvisibility=hidden` silently fail to
  export. [ISSUE-doc-drift: `PGDLLEXPORT` visibility-attribute
  requirement not loud enough (nit)]
- `MinGW-64`'s `setjmp` workaround at `c.h:1483-1494` is a known
  long-standing toolchain bug — has been there for many releases.
  [ISSUE-stale-todo: MinGW-64 setjmp workaround could be removed
  once buildfarm drops mingw-w64-x86_64 (nit)]

## Potential issues

See above inline ISSUEs. Headlines:
- `c.h:982-990` — `ExceptionalCondition` always-compiled-but-frontend-gated
  is the cassert↔non-cassert ABI bridge; a future cleanup
  that removes the `!FRONTEND` guard would break this contract.
- `c.h:1340-1365` — `USE_SSE2`/`USE_NEON` dispatch is purely
  compile-time; cross-compile from x86_64 to aarch64 forces the
  explicit `#undef USE_AVX2_WITH_RUNTIME_CHECK` cleanup at `c.h:1350-1352`.
  Future SIMD additions must remember this pattern.
- `c.h:602` — `#include <stdbool.h>` is unconditional. Used to be
  guarded by `HAVE_STDBOOL_H`; the guard was removed when PG raised
  the C standard to C99 then C11. No issue today.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-misc`](../../../issues/include-misc.md)
<!-- issues:auto:end -->
