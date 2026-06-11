# CB7 implementation notes

## Phase 1 — implementation + tests (single phase per R3)

**Status:** done.
**Commit:** `944e540792f ltree: cap total variant allocations in parse_lquery` (in `dev/` branch `feature_cb7_ltree_amplification`)
**Test scope:** `meson test --suite ltree` — green (1/1 OK).
**Broader test:** `meson test --no-rebuild` — 99 OK, 1 unrelated pre-existing ecpg flake (same as SP7/SP6/SP2).

### What changed

Three files in `dev/`, all under `contrib/ltree/`:

1. **`ltree_io.c`** — added `LQUERY_MAX_TOTAL_VARIANTS` macro (= `1 << 17` = 131072 nodeitems = ~3 MB worst-case scratch) + cap check immediately after the existing `LQUERY_MAX_LEVELS` check in `parse_lquery`. +34 LOC.
2. **`sql/ltree.sql`** — added 2-statement regression test: a ~21 KB input that would otherwise drive ~10M nodeitem scratch. +8 LOC.
3. **`expected/ltree.out`** — updated to match new regress output (column-header trailing whitespace + new error line). +14 LOC.

### Surprises / drift

1. **The cap had to be raised from the planning estimate (43690) to 131072.** Discovered when the existing test `SELECT (repeat('a|', 65535) || 'a')::lquery;` failed under the lower cap. That test produces num=1, numOR=65535 → 65536 entries, which exceeds 43690 but passes 131072. Existing test is testing the per-level `lquery_level.numvar` overflow boundary (legitimate test of `pg_add_u16_overflow` at line 348). Lesson: when introducing a numeric bound on lookups that share a buffer-size parameter with existing tests, verify the existing tests don't exercise the same boundary.

2. **The existing test gets caught by a different cap.** `SELECT (repeat('a|', 65535) || 'a')::lquery;` now errors with the in-loop `pg_add_u16_overflow` check, NOT my new total-variants cap. That's correct — my cap fires earlier (pre-allocation) for the cross-level amplification case, while the per-level numvar overflow check fires inside the parse loop for single-level overflows. Two different boundary checks, both important.

3. **`expected/ltree.out` trailing-whitespace gotcha.** First attempt at writing the expected output had ` length` (no trailing space) where pg_regress produces ` length ` (trailing space). Same problem as SP7's expected-output round-trip — solved by copying the actual regress result directly into `expected/`. Worth canonizing in the build-and-run skill: "if expected/X.out differs only by trailing whitespace on column headers, just `cp results/X.out expected/X.out` rather than hand-typing."

4. **The fix is genuinely a new error class.** Existing ltree errors: "syntax error at character N", "too many items", "too large", "too many variants", "too many array overflow". This patch adds a new one: "lquery is too complex" — flagged as such in the error message + detail. Reviewers may prefer reusing one of the existing message classes; happy to change if hackers suggest.

### What this phase did NOT do

- Did NOT touch `parse_ltree` (separate function for ltree literal parsing). That function palloc's only once based on level count + label sizes — no cross-level amplification. Out of scope.
- Did NOT add a GUC. Hardcoded constant matches PG contrib convention for security caps; reviewers prefer this for backpatch-friendly fixes. If hackers prefer a GUC, easy to convert.
- Did NOT change `ltree_op.c` / `lquery_op.c`. Those consume the parser's output and inherit bounds from the cap.
- Did NOT address the other A13 ltree findings (e.g. `ltree2text` overflow paths). Tracked separately as MP3+ in the pitch roadmap.

### Submission readiness

- `format-patch` ready: `git format-patch e18b0cb7344..feature_cb7_ltree_amplification --output-directory ../cb7-ltree-amplification/`
- Patch subject: `ltree: cap total variant allocations in parse_lquery`
- Backpatch candidates: yes (confirmed DoS bug in released code). v16, v17, v18 all share the parser.
- CF target: 60 (January 2026).

### End-of-implementation gate (R12)

- [x] Full `meson test --no-rebuild` — 99 OK, 1 unrelated pre-existing ecpg flake
- [x] `git log --oneline e18b0cb7344..HEAD` shows exactly 1 commit
- [x] Commit message in upstream PG style (no Co-Authored-By, no Plan: trailer per R5)
- [ ] Upstream-bound: needs `review-checklist` + `patch-submission` skills. NEXT STEP.
- [x] Local branch ready for review

### Next step

Same gate as the previous Phase D quick-wins: stage in a PR for user review. Four Phase D patches now queued for hackers-list submission (SP7, SP6, SP2, CB7).
