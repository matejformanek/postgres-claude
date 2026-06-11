# pgsql-hackers cover email — CB7 ltree parse_lquery amplification cap

**To:** pgsql-hackers@lists.postgresql.org
**Subject:** [PATCH] ltree: cap total variant allocations in parse_lquery
**Attach:** `0001-ltree-cap-total-variant-allocations-in-parse_lquery.patch`

---

Hi hackers,

contrib/ltree's parse_lquery() has a cross-level allocation
amplification: at every level it allocates an array sized for the
GLOBAL number of '|' characters in the input, not the per-level
variant count.

    palloc0_array(nodeitem, numOR + 1);   /* ltree_io.c:322 and :329 */

The cumulative scratch is `num * (numOR + 1) * sizeof(nodeitem)` bytes.
With LQUERY_MAX_LEVELS = PG_UINT16_MAX and sizeof(nodeitem) = 24 bytes,
a hostile input of the shape

    a|b|c.a|b|c.a|b|c. ...

at roughly 256 KB can drive that product to N * (N+1) * 24 bytes -
about 100 GB scratch.  Each individual palloc stays well under
MaxAllocSize so the existing per-call cap does not fire; the bug is
the unbounded growth of the cross-level product.

The attached patch adds a hardcoded cap on the total variant slots
allocated across all levels:

    #define LQUERY_MAX_TOTAL_VARIANTS  (1 << 17)   /* 131072 */

    if ((uint64) num * (uint64) (numOR + 1) > LQUERY_MAX_TOTAL_VARIANTS)
        ereturn(...);

131072 is far more than any legitimate lquery needs (typical: tens of
levels x tens of variants), leaves room for the existing single-level
overflow test at 65535 variants in one level, and bounds the
worst-case scratch to a few MB.  Above the cap, ereport
ERRCODE_PROGRAM_LIMIT_EXCEEDED with a specific detail message naming
the totals.

A regression test covers the cap with a ~21 KB input that would
otherwise drive ~10M nodeitems of scratch allocation, well into the
attack territory but small enough not to dominate the regression run.

Build + `meson test --suite ltree` green on master @ e18b0cb7344.

**Discussion points for reviewers:**

1. **Why hardcoded constant and not a GUC?**  Backpatch friendliness:
   adding a GUC complicates back-branch maintenance.  The cap is a
   structural property of the parser, not an operator-tunable knob.
   The precedent is LQUERY_MAX_LEVELS = PG_UINT16_MAX, also a
   hardcoded ltree cap.  Happy to convert to a GUC if hackers prefer.

2. **Why total variants x levels and not input length?**  Input-length
   caps either accept the pathological short inputs that trigger this
   (256 KB is well under any reasonable input-length GUC default) OR
   they break legitimate large queries that have few levels and few
   variants per level.  The product directly bounds the allocation
   amount we care about.

3. **Cap choice = 131072.**  Two competing pressures: high enough to
   not break the existing 65535-variant-in-one-level overflow test
   (`SELECT (repeat('a|', 65535) || 'a')::lquery;`), low enough that
   worst-case scratch is a few MB rather than tens of GB.  131072
   (= 2^17, ~3 MB) hits both.

4. **New error message class.**  The patch adds "lquery is too
   complex" alongside existing "syntax error", "too many items",
   "too large", "too many variants".  Open to renaming if reviewers
   prefer to reuse "too many variants" or "too large".

5. **Backpatch.**  This is a confirmed DoS bug in already-released
   code.  v16, v17, v18 all share the parser.  I'd suggest backpatching
   to all three.

Surfaced during a code-corpus sweep (postgres-claude/A13, 2026-06-09).

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
4. Add the CF link back to `postgres-claude/planning/cb7-ltree-amplification/notes.md`.
