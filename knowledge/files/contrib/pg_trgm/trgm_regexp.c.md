# source/contrib/pg_trgm/trgm_regexp.c

**Source pin:** master @ 4b0bf07. 2357 LOC. Largest single file in
the contrib trees touched by A14.

## Role

Compile a user regex into a trigram NFA: extract a set of trigrams
which any matching string MUST contain, plus a packed graph
representation so the index machinery (GIN consistent /
GiST consistent) can evaluate the trigram conjunction/disjunction.

The conversion is deliberately lossy in the safe direction:
matches-of-trigram-graph is a SUPERSET of matches-of-regex, so the
result must still be recheck'd against the heap row.

## Public API

- `createTrgmNFA(text *text_re, Oid collation, TrgmPackedGraph
  **graph, MemoryContext rcontext)` — entry point. Returns TRGM
  array allocated in rcontext (or NULL if too complex), with packed
  graph in *graph [source/contrib/pg_trgm/trgm_regexp.c:524].
- `trigramsMatchGraph(TrgmPackedGraph *graph, bool *check)` —
  evaluate the packed graph given index-derived bool array; returns
  true if the regex CAN match [trgm_regexp.c:628].

## Algorithm — four stages

1. **Stage 1:** compile regex into NFA via `pg_regcomp` with
   `REG_ADVANCED | REG_NOSUB [| REG_ICASE]`
   [trgm_regexp.c:546-552]. Extract colors via the regexport API.
2. **Stage 2:** breadth-first build of an expanded graph where arcs
   are labeled with COLOR trigrams. Each state carries a 2-color
   "prefix" identifying the last two characters read
   [trgm_regexp.c:897-955].
3. **Stage 3:** select which color trigrams to expand into simple
   trigrams. Penalty-weighted greedy removal — eliminate
   high-penalty color trigrams (those with whitespace, those
   expanding to many simple trigrams) by merging the states they
   connect [trgm_regexp.c:1459-1770].
4. **Stage 4:** expand surviving color trigrams into all
   characters × characters × characters combinations, pack the
   graph [trgm_regexp.c:1778-1841].

## Resource bounds — THE KEY DEFENSE

```c
#define MAX_EXPANDED_STATES 128
#define MAX_EXPANDED_ARCS   1024
#define MAX_TRGM_COUNT      256
#define WISH_TRGM_PENALTY   16
#define COLOR_COUNT_LIMIT   256
```
[verified-by-code source/contrib/pg_trgm/trgm_regexp.c:221-225]

- `COLOR_COUNT_LIMIT` checked at color extraction: colors with more
  than 256 characters are marked unexpandable
  [trgm_regexp.c:785-790].
- `MAX_EXPANDED_STATES` / `MAX_EXPANDED_ARCS` checked **once per
  outer-queue iteration** at `transformGraph`
  [trgm_regexp.c:951-953]. If exceeded, `overflowed=true` and all
  subsequent states are marked FINAL (= NFA accepts anywhere),
  producing a lossy-but-safe trigram set.
- `MAX_TRGM_COUNT` checked AFTER stage-3 reduction
  [trgm_regexp.c:1747-1749]. If still > 256, the regex is rejected
  (returns NULL → full index scan).
- `WISH_TRGM_PENALTY = 16` — soft target, not enforced.

## Invariants

- INV: stage-1 regex compilation can `ereport(ERROR)` on bad regex
  [trgm_regexp.c:745-752] — but the regex engine itself has its
  own complexity/timeout policy; trgm_regexp.c does NOT add one.
- INV: stage 2's breadth-first traversal terminates because every
  iteration either adds a state to the hashtable (bounded by
  MAX_EXPANDED_STATES check) or doesn't add a new one
  [trgm_regexp.c:937-954].
- INV: state merging in stage 3 uses tentative-flag rollback
  to safely test "can we merge?" before committing
  [trgm_regexp.c:1631-1706].
- INV: `mergeStates` cannot merge a state that becomes both INIT
  and FIN (asserted at trgm_regexp.c:1736-1737).
- INV: `trigramsMatchGraph` is a monotonic boolean function of
  check[] (more trues → still matches) — used by GIN
  triconsistent to safely promote GIN_MAYBE.
- INV: all temporary work allocated in a per-call AllocSetContext
  (`tmpcontext` at trgm_regexp.c:538-540) and deleted at function
  end — so partial work from an interrupted call is reclaimed.

## Notable internals

- `getColorInfo` calls `convertPgWchar` per character — in
  IGNORECASE mode, uppercase chars are dropped on the assumption
  the regex engine already paired them with lowercase
  [trgm_regexp.c:861-872]. Comment XXX at 854-859 admits this
  depends on str_tolower agreeing with the regex engine's case
  folding — collation drift risk.
- `processState` dispatches via `addKey` (computes reachable
  enter-keys) and `addArcs` (creates labeled arcs).
- `validArcLabel` enforces specific prefix shapes — e.g., rejects
  nonblank-blank-anything because such trigrams don't correspond
  to what `make_trigrams` would produce.
- Stage 3 sort+dedup of color trigrams via `qsort(...,
  colorTrgmInfoCmp)` then a second sort by penalty
  [trgm_regexp.c:1505-1567].
- Stage 4 expansion is a triple nested loop:
  `for (i1) for (i2) for (i3)` over each color's wordChars.
  Bounded because the cube-root of `MAX_TRGM_COUNT` (256) is ~6.3,
  so each color contributes ≤ ~256 char-combinations per arc.

## Trust-boundary / Phase-D surface — the major target

The header comment says: *"Otherwise regex processing could be too
slow and memory-consuming."* All five constants exist explicitly to
bound adversary input. So we need to check that **EVERY loop that
could be driven by attacker-controlled regex is bounded by one of
these constants** AND **that the bound check is reached promptly**.

### 1. Loops bounded by the constants — verified

- `transformGraph` outer loop: bounded by `MAX_EXPANDED_STATES`
  + `MAX_EXPANDED_ARCS` (line 951-953). Check is per-state, NOT
  per-arc — between two state-boundary checks, `addArcs` can add
  up to `arcsCount` (regex out-arcs of a single NFA state) arcs.
  Worst-case lateness: O(per-state-arcs) excess.
- Stage 3 outer loop iterates over `colorTrgmsCount` ≤ arcsCount ≤
  MAX_EXPANDED_ARCS = 1024.
- Stage 4 expansion: bounded by `totalTrgmCount` ≤ MAX_TRGM_COUNT
  = 256 (checked at line 1747-1749).

### 2. ZERO `CHECK_FOR_INTERRUPTS()` calls

[verified-by-code: `grep -n CHECK_FOR_INTERRUPTS trgm_regexp.c` returns
NOTHING]. The entire algorithm relies on the static MAX_* constants
to bound work. **No way to cancel a query stuck inside
`createTrgmNFA`** except postmaster SIGTERM.

This is probably ok because the bounds are small enough that even
worst-case work is < 1ms on modern hardware. But:

- The **REGEX COMPILE itself** (`pg_regcomp` at line 737) has no
  bound visible from this file. The regex engine has its own
  complexity guard (`REG_EXPECT` plus a backtrack-counter), but
  that lives in `src/backend/regex/`. **If an attacker passes a
  catastrophic-backtracker regex via `~`, `~*`, etc., the time is
  spent in `pg_regcomp` BEFORE we even reach the bounded
  algorithm.** Echo of A13 ltree `checkCond`.
- Stage 3's nested tentative-merge logic (lines 1604-1706) has
  TWO nested `foreach` over `trgmInfo->arcs` with inner
  `while (source->parent)` walks — bounded by graph size which
  is bounded by MAX_EXPANDED_ARCS, but no CFI.

### 3. State merging is parent-pointer linked-list

`while (source->parent) source = source->parent;` at
`trgm_regexp.c:1619-1622`. If state merging creates a long parent
chain, each lookup walks it. Bounded by total states (≤ 128) so
trivially bounded — but worth noting.

### 4. fn_extra cache in gtrgm_consistent uses `memcmp` (NOT this file)

Acknowledged regex-graph leak across rescans
(see `trgm_gist.c` notes) is the only known resource leak.

### 5. Collation / case-folding assumption

The XXX comment at trgm_regexp.c:854-859 is candid:

> this code is dependent on the assumption that str_tolower()
> works the same as the regex engine's internal case folding
> machinery. ... we're probably screwed if there's any
> incompatibility anyway.

If `str_tolower` and the regex engine disagree on the case-fold of
a non-ASCII character, the extracted trigrams won't match the
indexed trigrams (which were extracted via `str_tolower`), and the
regex query will return **false negatives** — rows that match the
regex won't be found. This is a correctness bug latent in
multi-locale databases, NOT a security bug.

### 6. printSourceNFA / printTrgmNFA writes /tmp/*.gv

Only when compiled with `-DTRGM_REGEXP_DEBUG`
[trgm_regexp.c:206-209]. Not a prod issue, but a TOCTOU hazard in
that build mode (writes to /tmp without `mkstemp`). Documented as
"for exploring and debugging".

## Cross-refs

- `source/backend/regex/*.c` — the actual regex engine; its
  catastrophic-backtracker policy lives there
- `source/backend/regex/regexport.h` — the API used here
- `source/contrib/pg_trgm/trgm_gin.c` — calls `createTrgmNFA` from
  the GIN extract-query path
- `source/contrib/pg_trgm/trgm_gist.c` — calls `createTrgmNFA`
  from `gtrgm_consistent`
- A13 ltree `_ltree_op.c` `checkCond` — sibling regex-style
  matcher with similar catastrophic-backtracker concern

## Issues

- [ISSUE-Phase-D: no CHECK_FOR_INTERRUPTS in createTrgmNFA pipeline (med)] —
  source/contrib/pg_trgm/trgm_regexp.c (entire file: zero CFI) —
  relies entirely on static MAX_* constants to bound work; under
  worst-case combinatorics of stage-3 tentative merges, the
  function could spin for tens of milliseconds with no cancel
  point. Defense-in-depth would add one CFI per outer loop.
- [ISSUE-Phase-D: pg_regcomp complexity not bounded here (low)] —
  source/contrib/pg_trgm/trgm_regexp.c:737-741 — adversary regex
  with catastrophic backtracking is spent in `pg_regcomp` before
  reaching the bounded NFA-to-trigram conversion. Belongs to
  backend/regex, but trgm_regexp doesn't add a timeout either.
  Echo of A13 ltree checkCond regex backtracker concern.
- [ISSUE-Correctness: case-fold assumption shaky for non-ASCII (low)] —
  source/contrib/pg_trgm/trgm_regexp.c:854-859 (XXX comment) — if
  str_tolower and regex case-fold disagree, regex queries can
  return false negatives.
- [ISSUE-Phase-D: MAX_EXPANDED_ARCS=1024, MAX_TRGM_COUNT=256 are
  static module-level constants, not GUCs (low)] —
  source/contrib/pg_trgm/trgm_regexp.c:221-225 — DBA cannot tune
  these for hostile vs trusted workloads. A hardening build could
  expose them as GUCs.
- [ISSUE-Resource: regex graph leak across rescans (low, already
  filed under trgm_gist.c)] — relevant here because this file
  creates the graphs.
