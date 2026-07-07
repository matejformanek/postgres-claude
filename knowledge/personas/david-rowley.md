# Persona: David Rowley

- **Last verified:** 2026-06-12
- **Source pin:** e18b0cb7344
- **Method:** `git log` mining of `source/` (read-only clone). Cross-cut against
  `knowledge/personas/committer-map.md`, `contributor-map.md`,
  `domain-ownership.md`. No external network calls.

## Role + email(s)

- **Primary identity:** `David Rowley <drowley@postgresql.org>` (committer).
- **Author-trailer identity** (in his own commit bodies): `David Rowley
  <dgrowleyml@gmail.com>`. Match both addresses when grepping.
- **Lifetime commits as committer:** 576.

## Activity profile (last 24mo)

Window: 2024-06-11 .. 2026-06-11.

| Metric | Value |
|---|---:|
| Commits as committer (24mo) | 187 |
| Commits as committer (12mo) | 86 |
| `Reviewed-by:` trailers crediting him (24mo, tree-wide) | 68 |
| `Reported-by:` trailers (24mo) | 19 |
| `Author:` / `Co-authored-by:` trailers crediting him (24mo) | 90 |
| `Discussion:` URL on his commits (24mo) | 183 of 187 (essentially 100%) |
| Backpatch references (24mo) | 38 (~20%) |

Reads as: lower review-credit count than Fujii/Daniel — he is more of a
self-driven feature/perf author than a patch shepherd. 77 of 187 commits
credit him as `Author:` himself (vs Fujii's 98 or Daniel's 76). Reported-by
share (19) is also among the highest in this bucket — he files perf-regression
reports on others' patches.

## Domain ownership

Path footprint, 24mo:

```
115 src/test/regress         ← #1 by file-touches — heavy regression-test work
 94 doc/src/sgml
 80 src/backend/executor     ← real domain
 72 src/backend/utils
 68 src/backend/access
 47 src/backend/commands
 46 src/backend/optimizer    ← real domain
 25 src/include/access
 19 src/include/nodes
 16 src/backend/replication
```

Note executor + optimizer are #3 and #7 — but `src/test/regress` is #1 because
he insists on a regression test for every behavior change.

Subject prefix histogram is nearly empty:

```
 17 Doc        (the only consistent prefix he uses)
  1 Widen lossy and exact page counters for Bitmap Heap Scan
  1 Use the GetPGProcByNumber() macro when possible
  1 Use strchr instead of strstr for single-char lookups
  ... [each subject unique]
```

[verified-by-code] **He does not use the `area:` prefix style.** Subjects are
full imperative sentences. The only repeating prefix is `Doc` (capitalised).
This contrasts sharply with Andres's lowercase `area:` style.

**His owned-area cluster:**

- **Executor performance.** `c456e391138` "Optimize tuple deformation" (1568
  LOC) — adds `TTS_FLAG_OBEYS_NOT_NULL_CONSTRAINTS`, precalculates
  `attcacheoff`, SWAR-trick NULL bitmap processing. `adf97c1` "Speed up Hash
  Join by making ExprStates support hashing" — JIT-compilable hash-key
  evaluation. This is his signature: low-level micro-optimization with
  benchmark numbers in the commit body.
- **Planner micro-opts.** `42473b3b312` "Have the planner replace COUNT(ANY)
  with COUNT(*), when possible" — adds `SupportRequestSimplifyAggref` to
  prosupport functions. `94219a73f79` fixes a hashed-IN bug for non-strict
  operators.
- **Bitmap Heap Scan / TID Range Scan parallelism.** `0ca3b16973a` "Add
  parallelism support for TID Range Scans" (504 LOC).
- **"Use X instead of Y, where possible" cleanup commits.** A recurring pattern
  in his subject lines: "Use stack-allocated StringInfoDatas, where possible",
  "Use bms_add_members() instead of bms_union() when possible", "Use
  TupleDescAttr macro consistently", "Tidyup truncate_useless_pathkeys()
  function". Distinctive recurring sweep style.
- **Documentation polish.** `49d43faa835` "Doc: use uppercase keywords in
  SQLs" (518 LOC sweep) — bulk doc consistency commits.

## Style + patterns

- **Imperative-mood title, no prefix.** "Optimize tuple deformation", "Fix
  incorrect logic for hashed IN / NOT IN with non-strict operators". This is
  the most "traditional PG" subject style of the bucket-B set.
  `[verified-by-code]`.
- **Quantitative justification in body.** `adf97c1` body cites "up to a 20%
  performance increase ... without JIT compilation and up to a 26% performance
  increase when JIT is enabled". Almost every perf commit has measured
  numbers — the unwritten rule is "no benchmark, no commit".
  `[verified-by-code]`.
- **"This commit only addresses X, but lays infrastructure for Y."** `adf97c1`
  closes with this exact phrasing. He flags scope boundaries explicitly,
  pointing at the follow-up direction without expanding the current patch.
  `[verified-by-code]`.
- **Test placement is part of the design.** `374a6394c6a` ("Move planner
  row-estimation tests to new planner_est.sql") opens with the test-file
  motivation: "there wasn't an ideal home for such tests ... More such tests
  are possibly on the way, so let's create a better home". He thinks about
  where tests should live as a first-class design decision.
  `[verified-by-code]`.
- **Concrete failure modes named in fix commits.** `94219a73f79` body: "could
  have resulted in an accidental true return if the hash table contained zero
  valued Datum, or could result in a crash for non-byval types ... All built-in
  types have strict equality functions, so this could affect custom /
  user-defined types." — describes the user-visible blast radius precisely.
- **CompactAttribute / TupleDesc invariants.** Several of his recent commits
  reshape `TupleDesc`/`CompactAttribute` (`Use CompactAttribute more often,
  when possible`, `c456e391138`). Treat tuple-layout invariants as his
  domain currently.
- **Self-author + low cross-review credit.** 77 of his 187 commits are
  self-authored. The reviewer pool reviewing his work is smaller — Tom Lane
  (14), Michael Paquier (8), Andres Freund (4) — than for Fujii or Daniel.
  His work is often reviewed by 1-2 named reviewers + himself.


## Scenarios I'd review
<!-- persona-scenarios:auto -->

*Derived from Domain-ownership paths overlapping each scenario's §Files section. If this persona claims a directory and a scenario mentions any file under it, they're a likely reviewer.*
*Refresh via `scripts/build-persona-scenario-matrix.py`.*

| Scenario | Via path(s) |
|---|---|
| [`add-new-aggregate-function`](../scenarios/add-new-aggregate-function.md) | `src/test/regress` |
| [`add-new-buffer-strategy`](../scenarios/add-new-buffer-strategy.md) | `src/test/regress` |
| [`add-new-builtin-function`](../scenarios/add-new-builtin-function.md) | `src/test/regress` |
| [`add-new-cast`](../scenarios/add-new-cast.md) | `src/test/regress` |
| [`add-new-cost-model-knob`](../scenarios/add-new-cost-model-knob.md) | `src/test/regress` |
| [`add-new-data-type`](../scenarios/add-new-data-type.md) | `src/test/regress` |
| [`add-new-expression-eval-step`](../scenarios/add-new-expression-eval-step.md) | `src/test/regress` |
| [`add-new-guc`](../scenarios/add-new-guc.md) | `src/test/regress` |
| [`add-new-index-am`](../scenarios/add-new-index-am.md) | `src/test/regress` |
| [`add-new-operator-class`](../scenarios/add-new-operator-class.md) | `src/test/regress` |
| [`add-new-pg-stat-view`](../scenarios/add-new-pg-stat-view.md) | `src/test/regress` |
| [`add-new-sql-keyword`](../scenarios/add-new-sql-keyword.md) | `src/test/regress` |
| [`add-new-system-catalog-column`](../scenarios/add-new-system-catalog-column.md) | `src/test/regress` |
| [`add-new-system-view`](../scenarios/add-new-system-view.md) | `src/test/regress` |
| [`add-new-table-am`](../scenarios/add-new-table-am.md) | `src/test/regress` |
| [`integrate-with-plpgsql`](../scenarios/integrate-with-plpgsql.md) | `src/test/regress` |
| [`remove-from-catalog`](../scenarios/remove-from-catalog.md) | `src/test/regress` |

<!-- /persona-scenarios:auto -->


## Subsystems I know
<!-- persona-subsystems:auto -->

*Derived from Domain-ownership paths overlapping each subsystem's `## Files owned` block.*
*Refresh via `scripts/build-persona-scenario-matrix.py`.*

_(none)_

<!-- /persona-subsystems:auto -->

## Common reviewer / collaborator partners

Reviewers of his commits (24mo):

```
 22 David Rowley           — self
 14 Tom Lane               — primary design reviewer
 10 Chao Li
  8 Michael Paquier
  5 Álvaro Herrera
  4 Andres Freund          — perf / executor overlap
  4 Ashutosh Bapat
  4 Junwang Zhao
  4 Zsolt Parragi
```

Co-authors on his commits:

```
 77 David Rowley           — self
  5 Ilia Evdokimov         — planner regression-test work
  5 Chao Li
  3 David Geier
```

Pairings cluster:

1. **Tom Lane is the executor/optimizer reviewer of record.** When a
   Rowley patch lands, expect Tom Lane in the trailer block more often than
   not.
2. **Ilia Evdokimov is the recurring planner-test contributor.**
   `374a6394c6a` was authored by him with Rowley as reviewer/committer.
3. **No tight inner circle.** Compared to Andres (AIO group), Daniel (OAuth
   group) or Fujii (NTT group), Rowley's work shows less of a fixed
   collaborator cluster. This matches a "I review patches in the area I touch
   that week" pattern rather than a feature-team pattern.

## What to expect on a patch he would review

- **Benchmark numbers required.** If your patch touches executor or
  tuple-deformation, expect "what's the perf impact?" with a request for
  pgbench / TPCH numbers. The bar is set by his own commits (20-26% wins
  reported with full reproduction context).
- **Test file in the right place.** If you add a test, he will tell you it
  belongs in a different file. `374a6394c6a` (move planner row-est tests to a
  new file) is the canonical example.
- **CompactAttribute / TupleDesc invariants.** If your patch touches `TupleDesc`
  fields, the `attcacheoff` precalculation in `TupleDescFinalize()` is recent
  invariant territory. Read `c456e391138` body before posting such a patch.
- **Scope-creep avoidance flagged in the body.** He will ask the commit body
  to say "This commit only does X; Y is left for later" rather than silently
  fitting Y into the current diff.
- **Style cleanups he runs as standalone commits.** Don't bundle a "Use bms_X"
  cleanup with a feature change — he separates these into their own commits
  and will ask the same of patches he reviews. `[verified-by-code]` — see his
  many "Use X, where possible" commit subjects.

## Landmark commits (last 12mo)

1. **`c456e391138` Optimize tuple deformation** (1568 LOC, 2026-03). Major
   restructure: `TupleDescFinalize()` becomes mandatory before TupleDesc use;
   `TTS_FLAG_OBEYS_NOT_NULL_CONSTRAINTS` introduced; SWAR NULL-bitmap trick
   added. Body cites both speedup rationale and the "round tts_isnull array
   size up to next 8 bytes" memory-context-checking interaction. Representative
   of his deep perf rework style.
2. **`adf97c1562` Speed up Hash Join by making ExprStates support hashing**
   (2024-08, ~1300 LOC). Adds expression-state hashing for multi-key joins,
   JIT-compilable. Benchmark-driven body. (Outside the strict 12mo window —
   listed here because committer-map cites it as his landmark, and it sets the
   pattern for `c456e391138`.)
3. **`0ca3b16973a` Add parallelism support for TID Range Scans** (504 LOC).
   Extends TID Range Scan to participate in parallel plans.
4. **`42473b3b312` Have the planner replace COUNT(ANY) with COUNT(*), when
   possible** (360 LOC, 2025-11). Adds new `SupportRequestSimplifyAggref`
   prosupport callback type. Body explicitly suggests future work ("It may be
   possible to add prosupport functions for other aggregates ... ORDER BY
   could be dropped for some calls, e.g. ... MAX(c ORDER BY c)").
5. **`94219a73f79` Fix incorrect logic for hashed IN / NOT IN with non-strict
   operators** (437 LOC, 2026-04, backpatched through 14). Bug fix with
   precise failure-mode characterization. Represents his bug-fix style.

## Notes / hedges

- **"Where possible" / "When possible" sweep commits are his signature.**
  At least 8 subject lines in 24mo end with one of these phrases. This is a
  distinctive search pattern. `[verified-by-code]`.
- **`Doc` (capitalised) prefix vs `doc` (lowercase) prefix.** He uses `Doc:`
  capitalised. Fujii and Daniel use lowercase `doc:`. Small but distinctive.
  `[verified-by-code]`.
- **Lower review-throughput, higher author-share.** 68 review credits vs Daniel's
  156 — Rowley does less mailing-list shepherd duty. Per patch review request,
  Tom Lane is the most reliable second pair of eyes.
- **Backpatch share (~20%) is moderate.** Bug fixes get backpatched (e.g.
  `94219a73f79` to 14); perf work does not. `[verified-by-code]`.
- **Two email identities.** `drowley@postgresql.org` for the commit bit;
  `dgrowleyml@gmail.com` for the author/reviewer trailer. The 22 self-review
  credits are via the gmail address.
