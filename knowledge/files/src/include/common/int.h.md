# src/include/common/int.h

## Purpose
The PostgreSQL overflow-checked-integer arithmetic primitives. All inline,
no external linkage. Every integer-overflow defense in the backend depends
on these — they are **security-critical infrastructure**.

API surface:
- `pg_add_{s,u}{16,32,64}_overflow(a, b, *result) → bool`
- `pg_sub_{s,u}{16,32,64}_overflow(a, b, *result) → bool`
- `pg_mul_{s,u}{16,32,64}_overflow(a, b, *result) → bool`
- `pg_neg_{s,u}{16,32,64}_overflow(a, *result) → bool`
- `pg_add_size_overflow`, `pg_sub_size_overflow`, `pg_mul_size_overflow`
  (size_t variants for allocation sizing)
- `pg_abs_s{16,32,64}(a) → unsigned` — absolute value returning unsigned
  so the operation **cannot overflow** even on INT_MIN.
- `pg_cmp_{s,u}{16,32,64}` and `pg_cmp_size` — qsort comparator helpers
  that avoid the classic `a-b` underflow.

## Role in PG
Used across the entire backend wherever PG must accept user-controlled
integers and reject overflow rather than wrap. Notable callers:
- `numeric.c`, `int8.c`, `int.c` — SQL `+/-/*` operators on int2/int4/int8
- `timestamp.c` — interval arithmetic
- `array.c` — element-count math
- `palloc` size accounting (`pg_mul_size_overflow` etc.)
- `pg_dump` / `pg_basebackup` size computations
- `tuptoaster.c` — toast pointer size math
- protocol-message length checks

The convention is: every caller writes
```c
if (pg_add_s64_overflow(a, b, &result))
    ereport(ERROR, errcode(ERRCODE_NUMERIC_VALUE_OUT_OF_RANGE), ...);
```
**Skipping these checks is a class of CVE** — see CVE-2017-7484 ancestors
and the `pg_mul_s32_overflow` introduction patches.

## Key implementation strata
Each routine has up to three implementations selected at compile time:
1. **`HAVE__BUILTIN_OP_OVERFLOW`** (GCC/Clang) — `__builtin_add_overflow`
   et al. Generates branch-on-CPU-overflow-flag. Optimal.
2. **`HAVE_INT128`** (GCC/Clang on 64-bit) — widen to int128, range-check,
   narrow. Used for the 64-bit cases when builtins are absent.
3. **Pure-C portable** — widen by one width, range-check, narrow; or for
   int64 multiply, the divide-trick that avoids 128-bit math.

`int.h:69-81` (`pg_add_s16_overflow`) shows the canonical structure.
`int.h:293-333` (`pg_mul_s64_overflow`) is the trickiest fallback —
explicit sqrt-range short-circuit + four sign-case division checks.

## State / globals
None — all inline static.

## Phase D notes
- **`__builtin_*_overflow` correctness.** GCC/Clang have had bugs in
  these intrinsics historically (e.g. early Clang on 32-bit ARM had
  `__builtin_mul_overflow` issues). PG implicitly trusts the compiler.
  Mitigation: `src/test/regress/sql/int*.sql` exercise the operators
  with edge cases (INT*_MIN ⋅ -1, MAX+1, etc.). [verified-by-code]
- **The `0x5EED` sentinel** (`int.h:76, 94, 111, ...`) — when overflow
  is reported, `*result` is set to 0x5EED ("SEED") so static analyzers
  don't flag uninitialized-use false positives. **Callers must check
  the return value, not the result.** Documented in the comment block
  at int.h:25-29 ("*The content of *result is implementation defined
  in case of overflow*"). [from-comment]
- **Pure-C fallback paths for u64 multiply** (`int.h:563-572`) use
  `a != 0 && b != res / a` — correct for unsigned, but exercises the
  divider only when both inputs are non-zero. The `a != 0` guard is
  load-bearing; a missing guard would mean division by zero for
  `pg_mul_u64_overflow(0, x, &r)`. [verified-by-code]
- **`pg_abs_s64(PG_INT64_MIN)`** (`int.h:354-357`) — explicit special
  case returning `(uint64)PG_INT64_MAX + 1`. The library `i64abs(INT64_MIN)`
  is undefined behavior; PG handles it explicitly. **This is a CRITICAL
  invariant**: any caller using `abs((int64)x)` instead of `pg_abs_s64`
  hits UB on INT64_MIN. Grep for `i64abs(` and `llabs(` in the tree to
  audit.
- **`pg_cmp_s16`/`pg_cmp_u16`** (`int.h:701, 707`) — uses `(int32)a -
  (int32)b` which is safe because the inputs widen. For 32/64-bit
  versions the diff-trick **would** overflow, so the code switches to
  `(a > b) - (a < b)`. **Reviewers must not regress 32/64-bit comparators
  to the subtraction form** — it's a classic qsort-transitivity bug.
- **`pg_neg_size_overflow` deliberately omitted** (`int.h:660-669`) —
  comment explains the SSIZE_MIN/MAX portability concern. Means callers
  needing signed-negate of size_t must inline the check.
- **Static analyzers and `__builtin_*_overflow`.** Some static analyzers
  (Coverity, clang-tidy) understand these builtins and can flag
  unchecked-overflow paths. The PG codebase passes a clean Coverity
  scan — these primitives are part of why.

## Cross-refs
- A7 corpus finding: `knowledge/subsystems/utils.md` — `numeric.c`
  and `formatting.c` integer-overflow surface; this header is the
  primitive layer those callers must use.
- A5 corpus finding: `knowledge/subsystems/common.md` —
  arithmetic-safety idiom across `src/common/`.
- `source/src/include/c.h` — `i64abs` / `PG_INT64_MIN` macros
  these helpers depend on.

## Potential issues
- [ISSUE-correctness: pg_abs_s64(PG_INT64_MIN) special case is correct,
  but any backend code path that does `(uint64) -x` or `abs(x)` directly
  on user input bypasses this guard. A grep audit of arithmetic on
  signed user-controlled values would be worthwhile for Phase D. (high)]
- [ISSUE-undocumented-invariant: the 0x5EED sentinel convention is not
  asserted anywhere — a misused result-after-overflow is silent. (low —
  callers conventionally check the bool first)]
- [ISSUE-dead-code: fallback paths (neither HAVE__BUILTIN_OP_OVERFLOW
  nor HAVE_INT128) are likely unexercised by CI. Old AIX/HP-UX-only
  paths now. (low)]
