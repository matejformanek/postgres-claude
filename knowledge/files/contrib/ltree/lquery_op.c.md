# lquery_op.c

## One-line summary

The lquery (path-query language) matcher: a recursive backtracking engine in `checkCond` that walks an lquery's levels against an ltree's levels, with per-level repetition counts (`{N,M}`), label variants (`a|b|c`), and four match modifiers — `*` (prefix), `@` (case-insensitive), `%` (word-wise via `_`-separator sublexemes), `!` (negation). **This is the Phase D headline file for ltree** — the recursive backtracker is the canonical CPU-DoS surface (regex-class catastrophic backtracking), but it does call `check_stack_depth()` and `CHECK_FOR_INTERRUPTS()` on every recursion.

## Public API / entry points

- `Datum ltq_regex(PG_FUNCTION_ARGS)` (line 263, `PG_FUNCTION_INFO_V1`) — `ltree ~ lquery` operator (strategy 12/13). Calls `checkCond`.
- `Datum ltq_rregex(PG_FUNCTION_ARGS)` (line 278) — commutator; swaps args and re-dispatches via `DirectFunctionCall2`.
- `Datum lt_q_regex(PG_FUNCTION_ARGS)` (line 287) — `ltree ? lquery[]`; iterates an `lquery[]` array, OR-combining `ltq_regex`. Validates one-dim + no-NULLs (lines 295-302).
- `Datum lt_q_rregex(PG_FUNCTION_ARGS)` (line 322) — commutator.

Exported helpers (used by `ltxtquery_op.c` and `ltree_gist.c`):

- `bool ltree_label_match(const char *pred, size_t pred_len, const char *label, size_t label_len, bool prefix, bool ci)` (line 80) — predicate-vs-label string match with optional prefix + case-folding.
- `bool compare_subnode(ltree_level *t, char *qn, int len, bool prefix, bool ci)` (line 43) — `%` sublexeme match: split `qn` and `t->name` on `_` and check every query lexeme matches some target lexeme.

Internal:

- `static char *getlexeme(char *start, char *end, int *len)` (line 24) — split-on-`_` iterator.
- `static bool checkLevel(lquery_level *curq, ltree_level *curt)` (line 149) — one-level OR'd-variant check + `LQL_NOT` handling.
- `static bool checkCond(lquery_level *curq, int qlen, ltree_level *curt, int tlen)` (line 183) — the recursive backtracker.

## Key invariants

- INV-LQUERY-DEFAULT-COUNT: when `(curq->flag & LQL_COUNT) == 0 && curq->numvar != 0`, the level matches exactly 1 ltree level — pre-v13 on-disk compatibility hack, enforced at line 205-208. `[verified-by-code + cross-ref ltree.h:80-86]`
- INV-STAR-MATCHES-NONE: `numvar == 0` is the `*` wildcard; matches `low..high` ltree levels (line 158). With `*{0,N}` it can match zero levels.
- INV-NOT-INVERTS-MATCH: `LQL_NOT` (`!foo`) returns `false` on match, `true` on no-match (line 155: `success = (curq->flag & LQL_NOT) ? false : true;`). For `*` levels (`numvar == 0`), `LQL_NOT` is never set by the parser. `[verified-by-code]`
- INV-PREFIX-FAST-PATH: `ltree_label_match` line 93-95 — if pred_len == label_len OR (prefix && pred_len < label_len), strncmp; case-folding skipped entirely. The slow path runs `pg_strfold` on both sides only if the fast path missed AND `ci == true`. `[verified-by-code]`
- INV-PG_LOCALE-CACHED: `ltree_label_match` caches `pg_database_locale()` in a static at line 84 — first call resolves locale, all subsequent calls reuse. **This means the locale used for case folding is captured at first use of the backend's lifetime; a `SET lc_collate` later in the session does not change it.** `[verified-by-code]`
- INV-CHECK-STACK-AND-INTERRUPTS: `checkCond` calls `check_stack_depth()` AND `CHECK_FOR_INTERRUPTS()` on every entry (lines 188, 191). The recursive backtracker can be cancelled by Ctrl-C / statement timeout / pg_cancel_backend. `[verified-by-code]`

## Notable internals

- `getlexeme` (line 24) is a sub-tokenizer for `%` (sublexeme) mode: treats `_` as a separator, returning each non-`_` run. Used both on the predicate (`qn`) and the target (`t->name`) — every query lexeme must appear as some target lexeme. So `foo%` matches `foo_bar` (one query lexeme `foo` matches first target lexeme), and also `bar_foo` and `foo_baz_quux`.
- `ltree_label_match` (line 80) has a careful comment at lines 99-103 explaining why case-folding is needed even when `pred_len > label_len` (case-folding can change byte length, e.g. German ß → SS doubles the length).
- `pg_strfold` is called with the input buffer first; if the output length exceeds the buffer (signalled by `len > fpred_len` at line 109), the buffer is `repalloc`'d and the fold retried. The slow path therefore does up to two `palloc` + two `pg_strfold` calls per predicate-label comparison.
- `checkCond` (line 183) is **textbook regex-style backtracking**: for each level it tries `matchcnt = low..high` consumption choices, recursing into the remaining pattern at each choice point. With `*{a,b}` levels at K positions in the query and an N-level ltree, the worst case is `O(b^K · N)` — exponential in the number of variable-bounded levels.
- The recursion at line 234 (`checkCond(nextq, qlen, curt, tlen)`) is the "try matching the rest of the query here" path. The for-loop at line 228 advances the match count of THIS query item; when `matchcnt >= low` it recursively verifies the tail; otherwise it tries to match one more. The loop bound `matchcnt < high` (line 228) is essential — without it an unbounded `*` would never terminate.
- `high > tlen → high = tlen` clamp at line 214 is the key bound that keeps `high` reasonable when the ltree is short.
- `nextq = LQL_NEXT(curq)` at line 225 is computed before the inner loop — `curq` is reused as the current level pointer for each `LEVEL_NEXT(curt)` advance at line 243. The tail-recursion-style loop-around at line 252 (`curq = nextq`) avoids one frame when `matchcnt == high`.

## Trust boundary / Phase D surface — the headline file

- **Catastrophic backtracking class**: `checkCond` is structurally identical to a regex matcher with bounded quantifiers. A pathological query against a long ltree can take exponential time. Example: lquery `*{0,5}.*{0,5}.*{0,5}.*{0,5}.x` against an ltree `a.a.a.a.a.a.a.a.a.a.a.a.a.a.a.a.a.a.a.a` — each `*{0,5}` level forks 6 ways at each starting position, total ~6^4 × 20 = 26000 recursive calls. With more levels and wider `{N,M}` ranges the count balloons fast. **The 65535-level cap on both ltree and lquery means an upper bound exists but it is astronomical.** Mitigation: `check_stack_depth()` (line 188) bounds recursion depth to ~`max_stack_depth` frames (default 2 MB → ~50K frames at ~40-bytes-per-frame); `CHECK_FOR_INTERRUPTS()` (line 191) lets statement_timeout/cancel work.
- **Quadratic baseline even without backtracking**: a query of N `*{a,b}` levels against an M-level ltree does `N×M` work in the no-mismatch case (each level position is tried against each tree position). For 65535 × 65535 this is ~4 billion operations.
- **`lt_q_regex` array iteration (line 287)**: an `lquery[]` array of K queries against one ltree runs `checkCond` K times. K is bounded by `MaxAllocSize / sizeof(min-lquery) ≈ 64M / 16 ≈ 4M entries` — but each per-element call may itself be expensive.
- **Soft-fail on bad array**: `lt_q_regex` validates one-dim + no-NULLs with hard `ereport(ERROR)` at lines 295-302. No soft-error path. `[verified-by-code]`
- **`ltree_label_match` slow path allocates per-call**: lines 107-126 palloc + maybe repalloc + pfree per comparison. With a 65535-level ltree and a long backtracking query, this is potentially millions of palloc/pfree pairs. Each is bounded; cumulative cost is the concern. The fast-path strncmp (line 93) avoids this when case-insensitive flag is off OR the binary match succeeds.
- **Static `pg_locale_t locale` (line 84)**: cached at first use, **never invalidated**. Cross-backend correctness if `lc_collate` is changed mid-session via `SET`: case folding will still use the first-resolved locale. Functionally a minor footgun; not a security issue.
- **No signature/index use here** — this file is the leaf-level recheck. Strategies 12/13 go through `ltree_consistent` (`ltree_gist.c:617`) which calls `ltq_regex` ONLY for leaf entries; non-leaf entries go through `gist_qe + gist_between`. So `checkCond`'s exponential cost applies only to actual ltree values, not to GiST inner nodes — bounding total work by `(rows-returned × backtracking-cost)`. With a permissive signature filter (small siglen), MANY rows may flow into the leaf check.
- **`compare_subnode` quadratic**: `compare_subnode` is O(Q × T) where Q is the number of `_`-separated lexemes in the predicate and T is the number in the target label (lines 53-70). Bounded by `LTREE_LABEL_MAX_CHARS = 1000` each, so worst case ~1 million `ltree_label_match` calls PER label-vs-predicate compare — and each of those may itself palloc. Realistically a label with 500 `_`s on each side is degenerate but legal.
- **`pg_database_locale` at line 105**: identical static-cache pattern. Locale resolved at first call.

## Cross-references

- `source/contrib/ltree/ltree.h:88-130` — `lquery_level`, `lquery_variant`, `LVAR_xxx` and `LQL_xxx` flags.
- `source/contrib/ltree/ltree_gist.c:617` — `ltree_consistent` strategies 12-17 dispatch here for leaf entries.
- `source/contrib/ltree/ltxtquery_op.c:71` — `checkcondition_str` reuses `ltree_label_match` and `compare_subnode`.
- `source/src/include/miscadmin.h` — `check_stack_depth`, `CHECK_FOR_INTERRUPTS`.
- `source/src/backend/utils/adt/formatting.c` — `pg_strfold`.
- `source/src/backend/utils/adt/pg_locale.c` — `pg_database_locale`.
- A5 jsonapi finding — recursive-descent parsers in PG use `check_stack_depth`; here `checkCond` does the same; OK.
- Regex catastrophic-backtracking literature — Friedl, "Mastering Regular Expressions" §6 — the algorithmic shape here is identical.

<!-- issues:auto:begin -->
- [Issue register — `ltree`](../../../issues/ltree.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-security: `checkCond` exhibits exponential backtracking on adversarial input. Concrete repro recipe: `lquery '*{0,9}.*{0,9}.*{0,9}.*{0,9}.*{0,9}.*{0,9}.x'` against `ltree 'a.a.a.a.a.a.a.a.a.a.a.a.a.a.a.a.a.a'` — 6 nested `*{0,9}` give ~10^6 × 18 explorations. With `*{0,LTREE_MAX_LEVELS}` the count is bounded only by `check_stack_depth` (depth, not breadth) and `statement_timeout`. **Per-call CPU DoS class.** Mitigation: `CHECK_FOR_INTERRUPTS()` allows cancel; `statement_timeout` bounds it. Defense-in-depth: a per-call "explorations done" counter would be more direct. Compare to `src/backend/regex/regexec.c` which has explicit step bounds. (likely — known regex problem; arguably "use statement_timeout")] — `source/contrib/ltree/lquery_op.c:228-244`.
- [ISSUE-security: `ltree_label_match` slow path (lines 107-141) allocates two buffers + maybe repalloc per comparison. With backtracking and a 1000-character label, a single GiST leaf recheck can execute ~10^5 palloc/pfree pairs. Memory-context churn, not leak, but unobservable to `statement_timeout` between CHECK_FOR_INTERRUPTS points. (nit — performance)] — `source/contrib/ltree/lquery_op.c:107-141`.
- [ISSUE-correctness: static `pg_locale_t locale = NULL` at line 84 caches per-process; never refreshed if `lc_collate` is changed mid-session. With same-database-locale convention this is fine, but a `SET LC_COLLATE` (which is per-session, not per-call) does NOT take effect for `@` case-insensitive lquery matches on this backend. (nit — known PG static-cache pattern)] — `source/contrib/ltree/lquery_op.c:84-105`.
- [ISSUE-cost: `compare_subnode` is O(Q × T) on the number of underscore-separated lexemes. With `_` as the separator, a label like `a_b_c_..._a` of 500 chars has 250 lexemes; predicate vs label gives ~62500 `ltree_label_match` calls, each potentially palloc'ing twice. (nit)] — `source/contrib/ltree/lquery_op.c:43-73`.
- [ISSUE-API-shape: `ltq_regex` always does `PG_FREE_IF_COPY` (lines 272-273), which is correct, but `lt_q_regex` uses `DirectFunctionCall2(ltq_regex, ...)` (line 306) — this means the inner `ltq_regex` runs `PG_FREE_IF_COPY` on its `fcinfo` args... which are the SAME pointers as the caller's `tree` and `query` (via `PointerGetDatum`). Looking carefully: `DirectFunctionCall2` builds a fresh `FunctionCallInfoBaseData`, but `PG_FREE_IF_COPY` checks `PG_GETARG_POINTER` against the original toasted datum from `flinfo`. In the `DirectFunctionCall2` path, `flinfo` is not initialized for argument detoasting, so `PG_FREE_IF_COPY` is effectively a no-op there. Net: no double-free, but the code is fragile. The outer `lt_q_regex` does `PG_FREE_IF_COPY(tree, 0)` at line 317. Confirmed correct, but the pattern is subtle. (nit — known PG-wide footgun)] — `source/contrib/ltree/lquery_op.c:306-317`.
- [ISSUE-correctness: line 22 `NEXTVAL(x)` uses `INTALIGN` (4-byte) but `lquery` is a `vl_len_` varlena type, and arrays of varlenas in `lquery[]` are stored using INTALIGN per the `pg_type.typalign='i'` declaration. Consistent with `_ltq_extract_regex` in `_ltree_op.c:35`. (verification — matches catalog convention)] — `source/contrib/ltree/lquery_op.c:22`.
- [ISSUE-doc: lines 200-208 — the LQL_COUNT compat hack is critical but explained mostly by the comment in `ltree.h:80-86`. This call site would benefit from a backref. (nit)] — `source/contrib/ltree/lquery_op.c:205-208`.
