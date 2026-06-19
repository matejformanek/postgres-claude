# pg_similarity — ideology / divergence notes

Extension: **eulerto/pg_similarity** (`master`, default version `1.0`).
A library of ~17 string-similarity algorithms (cosine, jaccard, levenshtein,
jaro-winkler, …) exposed as SQL functions **and** as GUC-thresholded boolean
operators (`a ~## b`, `a ~== b`), with partial GIN index support.

> Citation note: source read via `raw.githubusercontent.com`; the Git Trees API
> (`api.github.com/.../git/trees/master?recursive=1`) returned HTTP 200 here and
> was used to discover real paths. The manifest hint `pg_similarity.h` is
> actually **`similarity.h`** and the main C file is **`similarity.c`**
> (per-algorithm logic lives in `cosine.c`, `levenshtein.c`, … plus
> `similarity_gin.c`). See Sources footer. Line numbers match the fetched files.

---

## Domain & purpose

pg_similarity turns approximate-string-matching into first-class SQL. It ships a
function per algorithm — `cosine(text,text) → float8`, `lev(text,text)`,
`jaro(text,text)`, etc. — and, layered on top, a **custom operator per
algorithm** that returns boolean "is this pair a match?" by comparing the
function's score against a per-algorithm threshold. The pitch in the README is
that you replace `=`/`<>` with similarity operators like `~~~` (q-gram) or `~!~`
(smith-waterman-gotoh): "instead of the traditional operators (= and <>) you can
use ~~~ and ~!~" `[from-README]` (README.md:6). Three components are named
explicitly: **Functions**, **Operators**, and **Session Variables** — the last
being GUCs that "can be defined at run time" `[from-README]` (README.md:8-12).
That third component is where the design diverges hardest from core PG.

---

## How it hooks into PG

Plain loadable-C-extension model — no bgworker, no hook chaining, no
shared-preload requirement for correctness:

- **Control file** `pg_similarity.control`: `default_version = '1.0'`,
  `module_pathname = '$libdir/pg_similarity'`, `relocatable = true`,
  `comment = 'support similarity queries'`. `[verified-by-code]`
  (pg_similarity.control:1-5). Note there is no `superuser` line and no
  `trusted` line — installs as superuser-only by default.
- **Module magic**: bare `PG_MODULE_MAGIC;` (the old single-line macro).
  `[verified-by-code]` (similarity.c:14).
- **`_PG_init`** exists solely to register GUCs and finish with
  `EmitWarningsOnPlaceholders("pg_similarity")` — it chains *no* planner /
  executor / ProcessUtility hooks. `[verified-by-code]` (similarity.c:133-730).
  The `pg_similarity.conf.sample` comments suggest loading via
  `shared_preload_libraries` *or* `local_preload_libraries` (the `$libdir/plugins`
  trick), but loading is also implicit on first call to any function in the
  `.so`. `[from-comment]` (pg_similarity.conf.sample:4-10).
- **SQL-callable C functions** via `PG_FUNCTION_INFO_V1`: two per algorithm — a
  scoring function (`cosine`) and an operator-backing predicate (`cosine_op`) —
  declared `extern Datum PGDLLEXPORT …(PG_FUNCTION_ARGS)` in the header.
  `[verified-by-code]` (similarity.h:175-216). See [[fmgr]].
- **Operators**: each algorithm gets a punctuation operator created with
  `CREATE OPERATOR`, e.g. `~##` (cosine), `~??` (jaccard), `~==` (levenshtein),
  `~@@` (jaro-winkler), `~~~` (q-gram). Each is `LEFTARG = text, RIGHTARG = text`,
  `PROCEDURE = <algo>_op`, **`COMMUTATOR` = itself**, and
  `RESTRICT = contsel, JOIN = contjoinsel`. `[verified-by-code]`
  (pg_similarity--1.0.sql:13-334).
- **GUCs**: registered in `_PG_init` via `DefineCustomEnumVariable` (tokenizer),
  `DefineCustomRealVariable` (threshold, range 0.0–1.0, default 0.7), and
  `DefineCustomBoolVariable` (is_normalized, default true), all `PGC_USERSET`.
  `[verified-by-code]` (similarity.c:151-727). See [[guc-variables]].
- **GIN opclass** (partial): `gin_similarity_ops FOR TYPE text USING gin`, wiring
  three C support routines plus `bttextcmp` as the comparison function.
  `[verified-by-code]` (pg_similarity--1.0.sql:355-378; similarity_gin.c).

---

## Where it diverges from core idioms

The headline: **pg_similarity registers a whole family of operators whose truth
value is a function of session GUCs, then mislabels the volatility of the code
that reads those GUCs.** Core PG treats operators as pure, deterministic,
catalog-fixed predicates; here the same `a ~## b` flips between true and false
depending on a `SET` issued earlier in the session.

### 1. Operators whose result depends on a GUC — `~op` is not deterministic

Every `*_op` function compares the algorithm's score against a *session-mutable*
threshold GUC. The cosine operator is the cleanest example:

```c
Datum cosine_op(PG_FUNCTION_ARGS)
{
    ...
    res = DatumGetFloat8(DirectFunctionCall2(cosine, ...));
    ...
    PG_RETURN_BOOL(res >= pgs_cosine_threshold);
}
```
`[verified-by-code]` (cosine.c:123-143). `pgs_cosine_threshold` is the GUC
`pg_similarity.cosine_threshold` `[verified-by-code]` (similarity.c:205-218,
cosine.c:24). The README demonstrates the consequence directly: the *same*
`WHERE a ~== b` returns 2 rows at `levenshtein_threshold = 0.7` and 3 rows after
`SET pg_similarity.levenshtein_threshold TO 0.5` `[from-README]`
(README.md:357-372). This is a deliberate inversion of PG's operator contract:
an operator's meaning normally lives in the catalog and is stable for the life of
the database; here it lives in a `PGC_USERSET` GUC and is stable only for the life
of a `SET`. The design *names* this — "Session Variables … can be defined at run
time" `[from-README]` (README.md:12) — so it is a feature, not an oversight, but
it is squarely a divergence.

### 2. Volatility mislabeling — `IMMUTABLE` functions that read GUCs

This is the load-bearing hazard, and it mirrors the volatility discussion in
[[pgsql-http]] §4 but lands on the *wrong* side. The scoring functions are
declared `IMMUTABLE STRICT`:

```sql
CREATE FUNCTION cosine (text, text) RETURNS float8
AS 'MODULE_PATHNAME', 'cosine'
LANGUAGE C IMMUTABLE STRICT;
```
`[verified-by-code]` (pg_similarity--1.0.sql:23-25; same pattern for every
algorithm, lines 5-321). But `cosine()` reads two GUCs — `pgs_cosine_tokenizer`
(which tokenizer to use) and `pgs_cosine_is_normalized` — at runtime:

```c
switch (pgs_cosine_tokenizer) { case PGS_UNIT_WORD: ... }
...
elog(DEBUG1, "is normalized: %d", pgs_cosine_is_normalized);
```
`[verified-by-code]` (cosine.c:52-71, 109). A function that changes its output
when a session GUC changes is, by PG's definition, at most **STABLE**, never
`IMMUTABLE` — `IMMUTABLE` promises the same output for the same arguments
*forever*, which licenses the planner to constant-fold and cache. `SET
pg_similarity.cosine_tokenizer TO camelcase` (README.md:300) silently changes
what an "immutable" `cosine('a','b')` returns. The practical bite: an expression
index on `cosine(col, 'x')` could be built under one tokenizer and queried under
another, returning wrong answers, and the planner may constant-fold a
`cosine(const, const)` at plan time using whatever the GUC was *then*.
`[inferred]` from PG volatility semantics + the GUC reads above.

The `*_op` predicates are more honestly labeled **`STABLE STRICT`**
`[verified-by-code]` (pg_similarity--1.0.sql:27-29) — correct, since they read
the threshold GUC and are stable only within a statement. So the extension
*knows* the operator layer is GUC-dependent (it marked it STABLE) yet marks the
underlying scoring layer IMMUTABLE even though that layer also reads GUCs. The
inconsistency is the tell.

### 3. The operator is its own COMMUTATOR — a symmetry claim the algorithms break

Every operator declares `COMMUTATOR = <itself>` (e.g. `~##` commutes with `~##`)
`[verified-by-code]` (pg_similarity--1.0.sql:13-334). That asserts `a OP b ⇔ b OP
a`, which lets the planner freely flip operand order. It holds for symmetric
measures (cosine, jaccard), but several backing algorithms are **not symmetric**:
Monge-Elkan in particular is a directional measure, and the cost tables here are
asymmetric (`megapcost`/`nwcost` are not symmetric in their two args)
`[verified-by-code]` (similarity.c:44-125). Declaring a non-symmetric operator
self-commutating is a correctness footgun: the planner may reorder operands and
get a different score. `[inferred]` from the self-COMMUTATOR clause + asymmetric
cost functions.

### 4. GIN opclass that always rechecks and ignores its own GUCs

There is a real `gin_similarity_ops` opclass, but it is a coarse pre-filter, not
a true index of the similarity predicate. `gin_token_consistent` unconditionally
sets `*recheck = true` and returns `true`:

```c
*recheck = true;
PG_RETURN_BOOL(true);
```
`[verified-by-code]` (similarity_gin.c:224-226). So GIN can only ever say "maybe;
re-run the operator on the heap tuple" — it never rules a tuple *in*. Worse, the
tokenizer used at index-build time is hard-wired at **compile time** via
`#define PGS_BY_ALNUM`, not read from the per-algorithm tokenizer GUC, with a
standing `TODO we want to index according to out GUCs` `[verified-by-code]`
(similarity_gin.c:25-33, 64-69). That means the index tokenization can silently
disagree with the query-time tokenizer GUC — another consequence of building an
index over a GUC-parameterized predicate (see [[gin-extract-and-consistent]] for
how core opclasses are expected to behave). Only a subset of operators are even
wired into the opclass; jaro/levenshtein/soundex/etc. are commented out
(pg_similarity--1.0.sql:363-373). `[verified-by-code]`.

### 5. fmgr re-entry instead of factoring shared logic; GUC save/restore

`cosine_op` does not call a shared C helper — it calls the SQL-visible `cosine`
through `DirectFunctionCall2`, and brackets the call with a manual
save/force/restore of the `is_normalized` GUC global:

```c
bool tmp = pgs_cosine_is_normalized;
pgs_cosine_is_normalized = true;
res = DatumGetFloat8(DirectFunctionCall2(cosine, ...));
pgs_cosine_is_normalized = tmp;
```
`[verified-by-code]` (cosine.c:131-140). Mutating a GUC's backing variable
directly (bypassing `set_config_option`) and relying on a straight-line restore
is fragile: any `ereport(ERROR)` inside `cosine` longjmps past the restore line,
leaving the global flipped for the rest of the session. Core PG would use
`PG_TRY`/`PG_FINALLY` or `NewGUCNestLevel`/`AtEOXact_GUC` for exactly this. See
[[error-handling]]. `[inferred]` from the longjmp-unsafe restore pattern.

### 6. Hard string-length cap via ereport, not detoasting

Inputs longer than `PGS_MAX_STR_LEN` (1024 bytes) are rejected with
`ereport(ERROR, ERRCODE_INVALID_PARAMETER_VALUE)` rather than processed
`[verified-by-code]` (similarity.h:24, cosine.c:42-46). The functions also
materialize each argument to a C string up front via
`DirectFunctionCall1(textout, …)` `[verified-by-code]` (cosine.c:37-40), so a
toasted/long value is fully detoasted then length-checked. This is a pragmatic
guard against the O(n·m) DP algorithms blowing up, but it means the operators
silently can't be applied to long text columns — a sharp edge for users treating
`~==` as a drop-in for `=`. `[inferred]`.

### Contrast with core fuzzystrmatch / pg_trgm

Core ships `fuzzystrmatch` (levenshtein, soundex) and `pg_trgm` (trigram
similarity) for the same domain. The instructive contrast: `pg_trgm` exposes
similarity as a **function** plus a `%` operator whose threshold is *also* a GUC
(`pg_trgm.similarity_threshold`) — so core itself accepts GUC-thresholded
operators. But `pg_trgm`'s `similarity()` is correctly labeled, and its GiST/GIN
opclasses do real lossy indexing of the trigram set rather than always-recheck.
pg_similarity's divergence is therefore not "GUC-thresholded operators exist"
(core does that) but "the IMMUTABLE label on GUC-reading scoring functions" and
"the always-recheck, compile-time-tokenized GIN opclass." `[inferred]` from
known pg_trgm design + the cites above. `[unverified]` for the exact pg_trgm
labels (not re-read here).

---

## Notable design decisions (with cites)

- **Two functions per algorithm**: a `float8` scorer (`IMMUTABLE STRICT`) and a
  `bool` operator-backer (`STABLE STRICT`) that thresholds the scorer.
  `[verified-by-code]` (pg_similarity--1.0.sql:23-38).
- **Per-algorithm GUC triple** — `<algo>_tokenizer` (enum),
  `<algo>_threshold` (real, 0.0–1.0, default 0.7), `<algo>_is_normalized`
  (bool, default true), all `PGC_USERSET`. `[verified-by-code]`
  (similarity.c:151-727).
- **Operators self-declared as COMMUTATOR** to let the planner flip operands —
  safe only for symmetric measures. `[verified-by-code]`
  (pg_similarity--1.0.sql:17, 35, …).
- **`RESTRICT = contsel, JOIN = contjoinsel`** — borrows the generic
  "containment selectivity" estimators, the same default used by range/contains
  operators, since no bespoke selectivity function is provided.
  `[verified-by-code]` (pg_similarity--1.0.sql:18-19, repeated per operator).
- **GIN opclass is a recheck-only prefilter** with compile-time tokenizer choice
  and a standing TODO to honor GUCs. `[verified-by-code]`
  (similarity_gin.c:25-33, 224-226).
- **1024-byte input cap** enforced by `ereport(ERROR)` to bound the DP cost.
  `[verified-by-code]` (similarity.h:24; cosine.c:42-46).
- **Liberal `elog(DEBUG1/DEBUG3)` instrumentation** left in the hot path of every
  scorer (token-list dumps), gated only by log level. `[verified-by-code]`
  (cosine.c:73-113).
- **`#if PG_VERSION_NUM >= 90100` shims** throughout `_PG_init` and the GIN
  routines — the code still carries pre-9.1 `DefineCustom*` arity compatibility.
  `[verified-by-code]` (similarity.c:159-161; similarity_gin.c:123-128).

---

## Links into corpus

- [[fmgr]] — `PG_FUNCTION_INFO_V1`, `DirectFunctionCall1/2`, `PG_GETARG_TEXT_P`,
  the operator-backer calling the scorer via fmgr re-entry.
- [[guc-variables]] — `DefineCustomEnumVariable` / `RealVariable` / `BoolVariable`,
  `PGC_USERSET`, `EmitWarningsOnPlaceholders`; the per-algorithm threshold/
  tokenizer/normalized triple.
- [[error-handling]] — `ereport(ERROR, ERRCODE_INVALID_PARAMETER_VALUE)` length
  guard; the longjmp-unsafe GUC save/restore in `cosine_op`.
- [[memory-contexts]] — token lists `palloc`'d and `destroyTokenList`'d per call;
  `PG_FREE_IF_COPY` in the GIN extractors.
- [[catalog-conventions]] — `CREATE OPERATOR` / `CREATE OPERATOR CLASS` catalog
  wiring, strategy numbers, COMMUTATOR/RESTRICT/JOIN clauses.
- Sibling ideologies: [[pgsql-http]] (the volatility-labeling discussion this doc
  cross-references — there the labels are correct; here IMMUTABLE is misapplied),
  [[zhparser]] / [[pgroonga]] (other text/tokenizer extensions),
  [[orafce]] (another broad SQL-function library).

> Corpus gap: there is no `idioms/sql-function-volatility.md` and no
> `idioms/gin-extract-and-consistent.md` yet. The volatility-vs-GUC analysis (§2)
> and the GIN opclass analysis (§4) are anchored to the install SQL +
> `similarity_gin.c` and to PG's volatility/GIN semantics; both would be the
> proper wikilink targets once written. `[inferred]`. The wikilinks
> `[[gin-extract-and-consistent]]` above is a forward reference to that gap.

---

## Sources

- `https://api.github.com/repos/eulerto/pg_similarity/git/trees/master?recursive=1`
  — HTTP 200 — fetched 2026-06-19. Used to discover real paths; confirmed the
  header is `similarity.h` (not `pg_similarity.h`) and the main C file is
  `similarity.c`.
- `https://raw.githubusercontent.com/eulerto/pg_similarity/master/README.md`
  — HTTP 200 — fetched 2026-06-19.
- `https://raw.githubusercontent.com/eulerto/pg_similarity/master/similarity.h`
  — HTTP 200 — fetched 2026-06-19.
- `https://raw.githubusercontent.com/eulerto/pg_similarity/master/similarity.c`
  — HTTP 200 — fetched 2026-06-19 (the `_PG_init` GUC registry).
- `https://raw.githubusercontent.com/eulerto/pg_similarity/master/pg_similarity.control`
  — HTTP 200 — fetched 2026-06-19 (confirmed default_version 1.0, relocatable).
- `https://raw.githubusercontent.com/eulerto/pg_similarity/master/pg_similarity--1.0.sql`
  — HTTP 200 — fetched 2026-06-19 (function/operator/opclass definitions).
- `https://raw.githubusercontent.com/eulerto/pg_similarity/master/similarity_gin.c`
  — HTTP 200 — fetched 2026-06-19 (GIN support routines).
- `https://raw.githubusercontent.com/eulerto/pg_similarity/master/cosine.c`
  — HTTP 200 — fetched 2026-06-19 (representative scorer + `*_op`).
- `https://raw.githubusercontent.com/eulerto/pg_similarity/master/pg_similarity.conf.sample`
  — HTTP 200 — fetched 2026-06-19 (load instructions + GUC defaults).
- `https://raw.githubusercontent.com/eulerto/pg_similarity/master/levenshtein.c`
  — HTTP 200 — fetched 2026-06-19 — **skimmed, not cited** (confirms the
  IMMUTABLE-scorer / STABLE-op pattern holds beyond cosine).

> Manifest-path corrections: prompt said `pg_similarity.h` → real file is
> `similarity.h`; prompt said `pg_similarity.c` → real file is `similarity.c`.
> The control file is `pg_similarity.control` (not `.control.in`) and the install
> SQL is `pg_similarity--1.0.sql`, both as hinted.
