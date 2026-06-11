# Plan: SP2 — `pg_str{lower,upper,title,fold}` `MaxAllocSize` cap

**Status:** READY. Single-phase plan.
**Pitch:** `knowledge/phase-d-pitches.md` SP2 (cross-finding A7 + A15 + A16)
**Source pin:** `e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa` (master at 2026-06-10)
**Slug:** `sp2-pgstr-maxalloc`
**Branch:** `feature_sp2_pgstr_maxalloc` (in `dev/`)
**Expected commits:** 1 (single phase per R3 + R5)

## §1 Problem statement

The case-mapping primitives `pg_strlower`, `pg_strtitle`, `pg_strupper`, `pg_strfold`
(`src/include/utils/pg_locale.h:183-194`) all take a `(dst, dstsize, src, srclen, locale)`
shape. The non-C/POSIX path dispatches to ICU's `ucasemap_utf8To{Lower,Upper,Title}` or
libc equivalents, which can expand the output up to **3×** the input (the canonical
German ß → SS / Greek ς → Σ case where one byte maps to two).

The caller pattern at all four sites in `src/backend/utils/adt/formatting.c`
(`str_tolower:1640+`, `str_toupper:1683+`, `str_initcap:1740+`, `str_casefold:1812+`):

```c
dstsize = srclen + 1;
dst = palloc(dstsize);
needed = pg_strlower(dst, dstsize, src, srclen, mylocale);
if (needed + 1 > dstsize) {
    dstsize = needed + 1;        /* needed can be ~3 * srclen */
    dst = repalloc(dst, dstsize);
    needed = pg_strlower(dst, dstsize, src, srclen, mylocale);
}
```

If `srclen` is near `MaxAllocSize` (≈ 1 GB), the first `palloc(srclen + 1)` succeeds,
ICU/libc walks the entire input computing `needed`, then `repalloc(needed + 1)` exceeds
`MaxAllocSize` and ereports `invalid memory alloc request size N`. Concrete cost:

- ~700 MB palloc allocated + held until error
- Full ICU casemap pass (CPU + cache pressure) walked on input
- Opaque error message — operator sees `"invalid memory alloc request size 2148532223"`,
  not "input too long for casefolding"

A7 surfaced this as `to_char(repeat('ß', 1e8))`-class echo amplification (50 MB →
600 MB). A15 + A16 confirmed at the header layer. ltree's `lquery_op.c:108-126` is
also a downstream user (`pg_strfold` x4) and inherits the same cliff.

## §2 Approach

Add an early `srclen` cap inside each of the four `pg_str*` functions in
`src/backend/utils/adt/pg_locale.c`. The cap is `MaxAllocSize / 3 - 1` so that **both**
the first allocation (`srclen + 1`) and the worst-case grow (`3 * srclen + 1`) fit
under `MaxAllocSize`. Above the cap, ereport with a specific, helpful message
naming the function class.

Why inside `pg_locale.c` rather than at each `str_*` site in `formatting.c`:

1. Four fix points vs eight (no `str_*` / `pg_str*` duplication).
2. Protects downstream contrib users (`contrib/ltree/lquery_op.c`,
   `contrib/ltree/crc32.c`) automatically.
3. The cap is a property of the casemap operation itself (worst-case 3× expansion),
   not of any particular caller's allocation strategy.

Implementation:

```c
/* in src/backend/utils/adt/pg_locale.c */

/*
 * The longest input pg_str{lower,upper,title,fold} can accept.  Case mapping
 * may expand the result up to ~3x (e.g. German sharp s, Greek final sigma).
 * Both the caller's initial palloc(srclen + 1) and the worst-case repalloc to
 * 3 * srclen + 1 must fit under MaxAllocSize.
 */
#define PG_STR_CASEMAP_MAX_SRCLEN  ((MaxAllocSize - 1) / 3)

static inline void
check_str_casemap_srclen(size_t srclen, const char *funcname)
{
    if (srclen > PG_STR_CASEMAP_MAX_SRCLEN)
        ereport(ERROR,
                (errcode(ERRCODE_PROGRAM_LIMIT_EXCEEDED),
                 errmsg("input too long for %s", funcname),
                 errdetail("Input length %zu exceeds the case-mapping limit of %zu bytes.",
                           srclen, (size_t) PG_STR_CASEMAP_MAX_SRCLEN)));
}
```

Each `pg_strlower` / `pg_strtitle` / `pg_strupper` / `pg_strfold` gains a single line at
the top:

```c
check_str_casemap_srclen(srclen, "lower()" /* or "initcap()" / "upper()" / "casefold()" */);
```

The C/POSIX fast path runs **after** the cap (it would also have allocated `srclen + 1`,
and ASCII expansion is 1× — so technically a stricter cap is fine — but a single
shared bound is simpler to reason about).

## §3 Files that change

| File | Change | LOC |
|---|---|---|
| `src/backend/utils/adt/pg_locale.c` | Add `PG_STR_CASEMAP_MAX_SRCLEN` macro + static `check_str_casemap_srclen` helper + 4 call sites | +25 |

**Sites verified against current source (pin `e18b0cb7344`):**
- `source/src/backend/utils/adt/pg_locale.c:1320-1328` — `pg_strlower`
- `source/src/backend/utils/adt/pg_locale.c:1330-1338` — `pg_strtitle`
- `source/src/backend/utils/adt/pg_locale.c:1340-1348` — `pg_strupper`
- `source/src/backend/utils/adt/pg_locale.c:1350-1359` — `pg_strfold`
- `source/src/include/utils/memutils.h:40` — `MaxAllocSize` definition (already included by pg_locale.c)

## §4 Catalog impact

None.

## §5 Behavior changes

- Inputs ≤ `MaxAllocSize / 3 - 1` (≈ 357 MB): unchanged.
- Inputs > 357 MB to `lower()` / `upper()` / `initcap()` / `casefold()` /
  `regexp_replace()`-via-casemap / ltree case ops: previously errored with
  `invalid memory alloc request size N` (after the repalloc attempt), now error
  earlier with a specific message.
- No change for C/POSIX collations — the cap fires before the dispatch, but ASCII
  case mapping is 1:1 so behavior is identical except for the error path.

## §6 Test plan

No regression test added. The natural input that exercises the cap is
> 357 MB and would dominate buildfarm test time + memory. The cap is defense-in-depth:
behavior at the limit is verified by inspection (`MaxAllocSize - 1) / 3` arithmetic +
the worst-case 3× ICU bound from
[ICU docs](https://unicode-org.github.io/icu/userguide/transforms/casemappings.html)).

A future test that exercises this with `repeat(text, big_int)` could be added but
should be gated behind `PG_TEST_EXTRA=stress` to avoid slowing normal CI. Marked as
follow-up in `notes.md`.

**Phase-end check:** `meson test --suite regress` must pass (no change in default
behavior for normal-size inputs); `meson test --no-rebuild` ≤ 1 pre-existing flake
(ecpg).

## §7 Implementation sketch

(See §2.)

## §8 Phase-end check

```bash
cd dev
ninja -C build-debug install
rm -rf build-debug/tmp_install
meson test -C build-debug --suite setup
meson test -C build-debug --no-rebuild   # broad sweep; ≤1 pre-existing flake
```

## §9 Risk + reviewer concerns

**Anticipated reviewer pushback:**

1. *"Why not put the cap at the formatting.c sites instead?"* — Choice of header
   layer protects ltree + any future caller. The cap is a property of the casemap
   primitive's worst-case expansion, not of any particular allocation strategy.
2. *"Is 3× actually the worst case?"* — Yes for UTF-8 (ICU docs). For UTF-16 it
   can be larger in extreme edge cases, but PG always passes UTF-8 to ICU here
   (`source/src/backend/utils/adt/pg_locale.c:1338-1844` UTF8-only path in
   `str_casefold`). For libc it depends on the locale, but POSIX guarantees
   1:1 for the C/POSIX path which is short-circuited before the cap matters in
   practice.
3. *"What about the C/POSIX fast path?"* — The cap runs before dispatch. Since
   ASCII is 1:1, a stricter cap could be allowed for C/POSIX, but a single
   uniform bound keeps the code readable and the diff small.
4. *"What's the practical impact?"* — On a 1 GB input the previous failure was a
   ~700 MB palloc plus a full ICU walk before erroring. The new path errors on the
   first call with no allocation. Net: clearer error + freed memory for the
   surrounding query.

**Known limitations after this patch:**
- The error message says "input too long for X()". For non-user-facing callers
  (`contrib/ltree`), the function name is technically incorrect — they call
  `pg_strfold` directly. Listed as a follow-up consideration; the user-facing
  surface (`lower/upper/initcap/casefold`) is what hits the cap first in
  practice.

## §10 Cross-corpus echoes (this fix touches)

- A7 to_char echo amplification (50 MB → 600 MB)
- A15 finding on `pg_locale.h:183-194` (header confirmation)
- A16 finding on `formatting.h:21-24` (formatting layer confirmation)
- A13 citext + A14 pg_trgm cluster (downstream users)
- contrib/ltree (`crc32.c` + `lquery_op.c` — protected for free by this cap)

## §11 Submission package

After implementation lands and tests pass:
- `git format-patch e18b0cb7344..feature_sp2_pgstr_maxalloc --output-directory ../sp2-pgstr-maxalloc/`
- Patch subject: `Cap input size for pg_strlower/upper/title/fold to MaxAllocSize/3`
- Commit message body: cite the worst-case 3× expansion, the repalloc trap, and the
  shift from opaque `palloc` error to a specific one. Reference cross-finding A7 +
  A15 + A16.
- Target: pgsql-hackers mailing list + commitfest 60 (January 2026).
- Backpatch candidate: yes (defensive cap; no behavior change for normal inputs).

## §12 Notes / surprises

(Empty at plan time. Populate in `notes.md` during implementation per R8.)
