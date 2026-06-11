# pgsql-hackers cover email — SP2 pg_str* MaxAllocSize cap

**To:** pgsql-hackers@lists.postgresql.org
**Subject:** [PATCH] Cap input size for pg_strlower/upper/title/fold to MaxAllocSize/3
**Attach:** `0001-Cap-input-size-for-pg_strlower-upper-title-fold-to-M.patch`

---

Hi hackers,

The four case-mapping primitives pg_strlower / pg_strtitle /
pg_strupper / pg_strfold (declared in src/include/utils/pg_locale.h
and defined in src/backend/utils/adt/pg_locale.c) dispatch to ICU's
ucasemap_utf8To* or to libc.  Both can expand the result up to 3x the
input length (German sharp s -> SS, Greek final sigma).

Callers in formatting.c (str_tolower, str_toupper, str_initcap,
str_casefold) use the documented two-call pattern: first try with
`dstsize = srclen + 1`, and if `needed > dstsize - 1`, repalloc to
`needed + 1` and call again.  When `srclen` approaches MaxAllocSize
(about 1 GB), the first palloc succeeds, ICU/libc walks the entire
input computing `needed`, and the subsequent repalloc to `~3 * srclen`
trips MaxAllocSize with the opaque message:

    ERROR:  invalid memory alloc request size 2148532223

Allocated state at that point: ~700 MB live palloc plus the full ICU
walk's CPU and cache cost.  The same pattern is present in
contrib/ltree (lquery_op.c, crc32.c) via pg_strfold.

The attached patch adds a single early cap inside each of the four
pg_str* entry points.  The cap is `(MaxAllocSize - 1) / 3` -- ~357
MB -- so that both the initial `palloc(srclen + 1)` and the worst-case
`repalloc(3 * srclen + 1)` remain under MaxAllocSize.  Above the cap,
ereport with ERRCODE_PROGRAM_LIMIT_EXCEEDED and a specific message
naming the SQL-visible function:

    ERROR:  input string is too long for lower()
    DETAIL: Input length 400000000 exceeds the case-mapping limit of
            357913940 bytes.

Build + `meson test --suite regress` green on master @ e18b0cb7344
(245/245 subtests; no behavior change for normal-size inputs).

**Discussion points for reviewers:**

1. **Why a header-layer cap (pg_locale.c), not at the formatting.c
   sites?**  The cap is a property of the casemap primitive's
   worst-case expansion, not of any specific caller's allocation
   strategy.  Putting it in `pg_str*` also covers ltree (`crc32.c`,
   `lquery_op.c`) for free -- one fix point, four primitives, all
   downstream callers protected.

2. **Conservative for the C/POSIX path.**  The cap fires before the
   `locale->ctype == NULL` dispatch, but ASCII case mapping is 1:1
   so a stricter bound could be admitted there.  Decided against
   splitting: one uniform limit keeps the code readable, and an
   operator who hits 357 MB on the C path probably doesn't want a
   ~1 GB output either.

3. **No regression test.**  Exercising the cap requires > 357 MB
   input, which would dominate buildfarm time + memory.  The 3x
   expansion is the documented ICU contract.  A `PG_TEST_EXTRA=stress`
   gated test could be added if hackers want one -- I'm happy to
   follow up.

4. **Backpatch.**  This is defensive code with no behavior change for
   normal-size inputs.  The case-mapping primitives have been stable
   since v16 (the four pg_str* names) and inherit identical
   expansion behavior on older branches.  I'd suggest backpatching to
   v16/v17/v18 if hackers agree.

Surfaced during a code-corpus sweep (postgres-claude/A7+A15+A16
cross-finding, 2026-06).

Thanks,
Matej

---

## After sending

1. Wait for the message to hit the archive: https://www.postgresql.org/list/pgsql-hackers/
2. Capture the archive message-id.
3. Open a CF entry at https://commitfest.postgresql.org/ targeting CF #60:
   - Topic: Server Features  (or Security, hackers' call)
   - Patch: archive URL
   - Reviewers: open
4. Add the CF link back to `postgres-claude/planning/sp2-pgstr-maxalloc/notes.md`.
