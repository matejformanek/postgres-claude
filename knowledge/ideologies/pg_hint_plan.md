# pg_hint_plan — reintroduces the planner hints core PG has always refused, by hooking the optimizer and (historically) vendoring its internals

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `ossc-db/pg_hint_plan` @ branch `master` (extension version `2.0.0`,
> per `pg_hint_plan.control`). All `file:line` cites point into that repo (NOT
> `source/`); a few cites point into the `PG16` branch where the *historical*
> vendored-core architecture still lives — those are marked `(@PG16)`. Cites
> verified against files fetched 2026-06-12 (see Sources footer). The main
> `pg_hint_plan.c` is ~3000+ lines and was **skimmed via targeted queries**, not
> line-by-line audited. Read alongside `[[knowledge/architecture/planner]]`,
> `[[knowledge/subsystems/optimizer]]`, and the "tune the planner from outside"
> cluster `[[knowledge/ideologies/hypopg]]` / `[[knowledge/ideologies/pg_qualstats]]`.

## Domain & purpose

pg_hint_plan "lets users control the PostgreSQL planner with hints embedded in
SQL comments" — e.g. `/*+ SeqScan(a) HashJoin(a b) */` — overriding the
cost-based optimizer's choices `[from-README]` (`README.md` opening; the README
is thin and defers to `docs/`). The hint vocabulary (`docs/hint_list.md`,
`[from-README]`) spans four families: **scan-method** hints
(`SeqScan`/`IndexScan`/`IndexOnlyScan`/`BitmapScan`/`TidScan` and their `No…`
negations, plus `…Regexp` index-name matchers and `DisableIndex`); **join-method**
hints (`NestLoop`/`HashJoin`/`MergeJoin` + `No…`); **join-order** hints
(`Leading(...)`, optionally with parenthesised join pairs to also fix
inner/outer direction); and **behaviour/GUC** hints (`Set(guc value)`,
`Rows(... correction)`, `Parallel(table n soft|hard)`, `Memoize`/`NoMemoize`).
The reason to document it: it is the corpus's canonical example of an extension
whose **entire purpose contradicts a standing core-PostgreSQL design position**
(PG has historically refused query hints), and whose implementation strategy has
swung from *copying the planner's source into the extension* (PG16 branch and
earlier) to *driving upstreamed hooks* (master / 2.0.0).

## How it hooks into PG

`_PG_init` saves the previous value of, then overwrites, a long chain of hooks
(`pg_hint_plan.c:1076-1095`, `[verified-by-code]`):

- `post_parse_analyze_hook` → `pg_hint_plan_post_parse_analyze` — the capture
  point for the raw query text (see below).
- `planner_hook` → `pg_hint_plan_planner` — the driver: builds hint state, sets
  GUCs, calls `standard_planner`, restores state.
- `join_search_hook` → `pg_hint_plan_join_search` — forces join order.
- `set_rel_pathlist_hook` → `pg_hint_plan_set_rel_pathlist` — per-rel
  enforcement.
- `fmgr_hook` / `needs_fmgr_hook` — used to track entry into PL/pgSQL functions
  for the recursion bookkeeping.
- `ExecutorEnd_hook` → `pg_hint_ExecutorEnd` — resets the "hint already
  retrieved" latch (`pg_hint_plan.c:1593-1600`, `[verified-by-code]`).
- **Three hooks that exist only in recent core**: `build_simple_rel_hook`,
  `joinrel_setup_hook`, `join_path_setup_hook` →
  `pg_hint_plan_build_simple_rel_hook`, `pg_hint_plan_joinrel_setup`,
  `pg_hint_plan_join_path_setup` (`pg_hint_plan.c:1090-1095`,
  `[verified-by-code]`). These are the mechanism that replaced the vendored
  planner copies — see divergence #2.

**The scanner / how it gets the comment.** The hint text lives in a leading
block comment whose magic prefix is `/*+`, assembled from
`BLOCK_COMMENT_START "/*"` and `HINT_COMMENT_KEYWORD "+"` into `HINT_START`
(`pg_hint_plan.c:89-91`, `[verified-by-code]`). The gotcha the design must solve
is that by the time the planner runs, the parser has already discarded comments —
so pg_hint_plan grabs the comment from the **raw source text** much earlier.
`pg_hint_plan_post_parse_analyze` receives the `ParseState` and reads
`pstate->p_sourcetext`, passing it to `get_current_hint_string(query, sourcetext)`
(`pg_hint_plan.c:2273-2306`, esp. the `…p_sourcetext` call ~`:2299`,
`[verified-by-code]`). `get_current_hint_string`
(`pg_hint_plan.c:2202-2268`) chooses between two sources: the **hint table**
(`get_hints_from_table`, queried via SPI, ~`:2239`) and the **leading comment**
(`get_hints_from_comment` → `query_scan_*` from the vendored scanner
`query_scan.h`, `pg_hint_plan.c:2076-2110`, `:59`, `[verified-by-code]`). So the
real "where does the comment come from" answer is `p_sourcetext` captured at
post-parse-analyze, not `debug_query_string` (though older code paths used the
latter). Cross-ref `[[knowledge/idioms/parser-pipeline]]`,
`.claude/skills/parser-and-nodes/SKILL.md`.

## Where it diverges from core idioms

### 1. Hints override cost-based planning — the philosophical heresy

Core PostgreSQL has a long-standing, deliberate refusal to support planner
hints; the cost model is meant to be the single source of plan choice. pg_hint_plan
is the most prominent extension that reintroduces them, letting a `/*+ … */`
comment veto the optimizer. This is the headline divergence: not a missing
feature being added, but a **rejected design being re-enabled out-of-tree**
`[inferred]` (the README states the override purpose `[from-README]`; the
"core refuses hints" stance is well-established PG project lore, tagged
`[unverified]` as to any single citable source). Everything below is mechanism in
service of this one stance.

### 2. It (historically) VENDORS core planner functions — exact-PG-version coupling

This is the sharpest *implementation* divergence, and it has two eras:

- **Old era (PG16 branch and earlier, the long-dominant design).** The Makefile
  compiled the main object *with two copied planner files as dependencies*:
  `pg_hint_plan.o: core.c make_join_rel.c` (`Makefile:34 @PG16`,
  `[verified-by-code]`), which `pg_hint_plan.c` pulled in by `#include`. Both
  files announce their provenance in the header: `make_join_rel.c` is "Routines
  copied from PostgreSQL core distribution with some modifications" from
  `src/backend/optimizer/path/joinrels.c`, reproducing `make_join_rel()` and
  `populate_joinrel_with_paths()` (`make_join_rel.c:1-17 @PG16`,
  `[verified-by-code]`). `core.c` copies a much larger set from
  `optimizer/path/allpaths.c` and `joinrels.c` — `standard_join_search`,
  `set_plain_rel_pathlist`, `create_plain_partial_paths`, `join_search_one_level`,
  `make_rels_by_clause_joins`, `make_rels_by_clauseless_joins`, `join_is_legal`,
  `has_join_restriction`, `try_partitionwise_join`, and more
  (`core.c` header `@PG16`, `[verified-by-code]`). Because these are *byte-copies
  of `static` core functions*, the extension is pinned to one PG major version:
  every release ships a **separate per-major branch** (`PG16`, etc.) whose `core.c`
  matches that major's planner internals `[inferred from branch layout]`. When
  core refactors `joinrels.c`, the vendored copy silently diverges until a human
  re-copies it — the exact "confident copy that drifts" failure mode the corpus
  is wary of.

- **New era (master / 2.0.0).** The vendored copies are **gone**: the Makefile
  compiles only `pg_hint_plan.o` and `query_scan.o` (`Makefile:8-11`,
  `[verified-by-code]`), and `pg_hint_plan.c` contains **no `#include` of any
  `.c` file** (`[verified-by-code]`, confirmed by scanning all includes). The
  copied `core.c`/`make_join_rel.c` no longer exist at the repo root (both 404 on
  `master`). The work they did is now done by the three upstreamed hooks
  (`build_simple_rel_hook`, `joinrel_setup_hook`, `join_path_setup_hook`) plus the
  `pgs_mask` field on `RelOptInfo`/`JoinPathExtraData` — i.e. the extension
  lobbied the needed hook points into core rather than re-copying core. This is a
  notable maturity arc and the cleanest contrast in the copy-core-internals
  cluster `[[knowledge/ideologies/pg_squeeze]]` / `[[knowledge/ideologies/pg_ivm]]`
  (which still vendor) `[inferred]`.

### 3. Forcing scan/join methods — a hack on the cost model, in two flavours

- **Old flavour (PG16): toggle the `enable_*` GUCs per query.** A `SET_CONFIG_OPTION`
  macro wraps `set_config_option_noerror` and is fired for `enable_seqscan`,
  `enable_indexscan`, `enable_nestloop`, `enable_mergejoin`, `enable_hashjoin`,
  etc., flipping them off to suppress unwanted path types during this planning
  pass (`pg_hint_plan.c @PG16`, around the `set_scan_config_options` /
  `set_join_config_options` helpers, `[verified-by-code]` via the Makefile-era
  source; exact lines `[unverified]` — the PG16 file was not deep-read). This is
  a literal abuse of the user-facing planner GUCs as an internal toggle, restored
  via `AtEOXact_GUC`.

- **New flavour (master): a `pgs_mask` bitmask consulted by core.** Instead of
  GUC flipping, 2.0.0 sets a bitmask on the rel/join: `setup_scan_method_enforcement`
  clears `PGS_SCAN_ANY` and ORs in `PGS_SEQSCAN`/`PGS_INDEXSCAN`/… from an
  `ENABLE_*` mask (`pg_hint_plan.c:1915` region, `[verified-by-code]`);
  `set_join_config_options` does the same with `PGS_NESTLOOP_*`/`PGS_HASHJOIN`/…
  on `extra->pgs_mask` (`:1945` region, `[verified-by-code]`);
  `setup_parallel_plan_enforcement` ORs `PGS_GATHER` and clears
  `PGS_CONSIDER_NONPARTIAL` for forced parallelism (`:1860` region). The mask is
  read by core through the new hooks to skip generating disabled path types.
  `Set` hints still go through real GUCs: `setup_guc_enforcement` →
  `set_config_option_noerror` (`:2638-2653`), and `set_config_int32_option`
  bumps `max_parallel_workers_per_gather` when a `Parallel` hint needs more
  workers (`:2148-2151`), all rolled back via `AtEOXact_GUC(true, save_nestlevel)`
  (`:2164-2165`, `[verified-by-code]`). So even the modern design still leans on
  the GUC machinery for the `Set`/`Rows`/parallel knobs — it just stopped abusing
  `enable_*`. Cross-ref `[[knowledge/idioms/guc-variables]]`,
  `.claude/skills/gucs-bgworker-parallel/SKILL.md`.

Index hints work by **mutating `RelOptInfo->indexlist`**: `restrict_indexes`
empties it (`list_free_deep` → `rel->indexlist = NIL`) for `SeqScan`/`TidScan`,
or `foreach_delete_current`s out the non-matching indexes for a named-index hint
(`pg_hint_plan.c:3117-3234`, called from `setup_hint_enforcement` ~`:3285`,
`[verified-by-code]`). Note this is done in the rel-pathlist phase, not a
`get_relation_info_hook` handler in this version. Cross-ref
`.claude/skills/executor-and-planner/SKILL.md`,
`[[knowledge/architecture/query-lifecycle]]`.

### 4. Join-order forcing via `join_search_hook` (and the GEQO problem)

`Leading(...)` is enforced through `pg_hint_plan_join_search`
(`join_search_hook`). The handler builds the join tree in the hinted order rather
than letting `standard_join_search` enumerate freely; the `JoinMethodHint` carries
the relation set and an enforce mask (`JoinMethodHint` struct
`pg_hint_plan.c:497-505`, `JoinMethodHintParse` `:2352-2395`,
`[verified-by-code]`). Because core has *two* join searchers — the DP
`standard_join_search` and the genetic `geqo` for many-way joins — a join-order
hook must contend with GEQO; pg_hint_plan's join searcher takes over enumeration
so the hinted `Leading` order wins regardless of which core searcher would have
run (`pg_hint_plan_join_search` body `[inferred]`; exact GEQO interaction
`[unverified]` — the function body was not fully read). Cross-ref
`.claude/skills/executor-and-planner/SKILL.md`.

### 5. Hint state lives in global/static state with a stack — re-entrancy hazard

Hints are not threaded through planner arguments; they sit in **file-scope
globals**: `current_hint_state` (the active context), `HintStateStack` (a `List`
used as a push/pop stack), `current_hint_retrieved` (a "already parsed this
statement" latch), and the recursion counters `plpgsql_recurse_level`,
`recurse_level`, `hint_inhibit_level` (`pg_hint_plan.c:938-978`,
`[verified-by-code]`). `push_hint`/`pop_hint` (`:2712-2734`) maintain the stack
and point `current_hint_state` at its head, with `pop_hint` calling
`HintStateDelete`. This is the classic hook-chain state-passing pattern and its
classic hazard: **nested queries** (a hinted statement that runs PL/pgSQL which
itself issues queries) must not let the outer hint leak in. The planner handler
explicitly detects `plpgsql_recurse_level > 0`, stashes and clears
`current_hint_str`/`current_hint_retrieved`, re-derives the hint for the inner
query, and restores the outer string if the inner had none
(`pg_hint_plan.c:2345-2371`, `[verified-by-code]`). The whole apply/restore is
wrapped in `PG_TRY`/`PG_CATCH` so an error during planning still pops the hint
and rolls back GUCs (`:2410-2437`, `[verified-by-code]`), and
`pg_hint_ExecutorEnd` resets `current_hint_retrieved` at top level
(`:1593-1600`). Cross-ref `[[knowledge/idioms/error-handling]]`,
`[[knowledge/idioms/memory-contexts]]`, `.claude/skills/error-handling/SKILL.md`.

### 6. Interaction with `pg_stat_statements` — normalization strips the hint

`pg_stat_statements` normalizes a statement's text for grouping, and the
extension's place in the hook order relative to it matters: if pg_hint_plan does
not capture the hint before the comment is stripped/normalized, the hint is lost
and the statement is grouped without it. The master Makefile's commented-out
`# pg_stat_statements.c` dependency line (`Makefile:34 @PG16`,
`[verified-by-code]` for the comment's existence) is a fossil of the era when the
extension shipped a *patched copy of pg_stat_statements* to preserve hints. The
current design instead captures from `p_sourcetext` at
`post_parse_analyze_hook` (see "How it hooks") so the raw comment is read before
any normalization `[inferred]`. The general caution — hint comments and query
normalization are at odds — is real but the exact present-day handling was
`[unverified]` (no explicit normalization-stripping code found in the skimmed
master `pg_hint_plan.c`).

## Notable design decisions (cited)

- **Two hint sources, table beats comment.** `get_current_hint_string` consults a
  `hint_plan.hints` **table** (keyed by `query_id` + `application_name`, queried
  via SPI: `"SELECT hints FROM hint_plan.hints WHERE query_id = $1 AND
  (application_name = $2 OR application_name = '') ORDER BY application_name
  DESC"`, `pg_hint_plan.c:1667-1689`, `[verified-by-code]`) so hints can be
  injected without touching application SQL — useful when you can't edit the query
  text. Cross-ref `[[knowledge/idioms/spi]]`, `.claude/skills/fmgr-and-spi/SKILL.md`.
- **Non-default schema, non-relocatable.** `pg_hint_plan.control` sets
  `schema = hint_plan`, `relocatable = false`, `default_version = '2.0.0'`
  (`pg_hint_plan.control:1-5`, `[verified-by-code]`) — the hint table lives in a
  fixed schema the SPI query hard-codes.
- **Long upgrade chain.** The Makefile carries migration scripts from
  `1.3.0` through `1.9.0--2.0.0` (`Makefile:18-58`, `[verified-by-code]`), a sign
  of a mature, long-lived extension with users on many versions.
- **`set_config_option_noerror` wrapper.** All GUC pokes go through a
  non-throwing wrapper (`:2592-2622`) so a bad `Set(...)` hint degrades rather
  than aborting the query `[verified-by-code]`.

## Links into corpus

- `[[knowledge/architecture/planner]]` — the cost-based path/join enumeration
  this extension overrides; `Leading`/scan/join hints intervene at exactly the
  add_path / join-search points described there.
- `[[knowledge/subsystems/optimizer]]` — `RelOptInfo->indexlist`,
  `JoinPathExtraData`, `standard_join_search`/geqo: the structures pg_hint_plan
  mutates or whose enumeration it replaces.
- `[[knowledge/idioms/guc-variables]]` — `Set` hints and the historical
  `enable_*` toggling both ride the GUC machinery (`AtEOXact_GUC`, nest levels).
- `[[knowledge/ideologies/hypopg]]`, `[[knowledge/ideologies/pg_qualstats]]` — the
  "tune the planner from outside" cluster (hypopg = what-if indexes,
  pg_qualstats = which predicates lack stats/indexes, pg_hint_plan = force the
  plan); overlapping author/community lineage.
- `[[knowledge/ideologies/pg_squeeze]]`, `[[knowledge/ideologies/pg_ivm]]` — the
  copy-core-internals cluster; pg_hint_plan is the one that *escaped* vendoring by
  upstreaming hooks, a useful contrast (note: `pg_ivm.md` is a forward reference,
  not yet written).
- `.claude/skills/executor-and-planner/SKILL.md` — path/join enumeration, add_path
  cost dominance, the hooks pg_hint_plan installs.
- `.claude/skills/gucs-bgworker-parallel/SKILL.md` — custom GUC + the
  `max_parallel_workers_per_gather` poke for `Parallel` hints.

## Anthropology takeaway

pg_hint_plan is the corpus's purest study in **building against the grain of a
core design decision**. PostgreSQL deliberately has no hints; this extension
re-supplies them, and the *cost* of swimming upstream is visible in its
architecture. For years that cost was **vendoring** — byte-copying `static`
planner functions into `core.c`/`make_join_rel.c`, which buys access to internals
the hook API doesn't expose but pins the extension to one PG major and risks
silent drift every time core refactors `joinrels.c`/`allpaths.c`. The master/2.0.0
rewrite is the redemption arc: the copies are deleted in favour of three hook
points (`build_simple_rel_hook`, `joinrel_setup_hook`, `join_path_setup_hook`)
plus a `pgs_mask` field that core reads — i.e. the project converted "copy the
planner" into "ask core for the seams," which is exactly the maturation a meta
corpus wants to flag for *other* copy-core extensions
(`[[knowledge/ideologies/pg_squeeze]]`, `[[knowledge/ideologies/pg_ivm]]`). Two
secondary lessons worth a `knowledge/issues` note: (a) **global hint state across
a recursive hook chain** is a re-entrancy minefield — the `plpgsql_recurse_level`
/ `HintStateStack` / `PG_TRY` dance exists solely to stop an outer query's hint
from leaking into PL/pgSQL-issued inner queries, and is easy to get subtly wrong;
(b) **hint-in-comment vs query normalization** (pg_stat_statements) is a standing
tension — the hint must be captured from raw `p_sourcetext` at post-parse-analyze
before any comment stripping, and the fossil `# pg_stat_statements.c` Makefile
line records that this once required shipping a patched copy of another extension.
The whole story is a cautionary, then exemplary, case of how far out-of-tree code
must reach to override a planner that was designed to not be overridden.

## Sources

Fetched 2026-06-12. Note: the GitHub *API* tree endpoint and the GitHub MCP
tooling were both blocked in this environment (HTTP 403 / "repo not configured"),
so the manifest was reconstructed from `Makefile` + targeted `raw.githubusercontent.com`
fetches rather than a full tree listing. The huge `pg_hint_plan.c` was
**skimmed via targeted queries, not line-by-line audited** — line numbers for it
are best-effort from those queries and should be re-verified before being used as
load-bearing patch cites.

- `https://api.github.com/repos/ossc-db/pg_hint_plan/git/trees/master?recursive=1`
  @ 2026-06-12 → HTTP 403 (API blocked; manifest reconstructed from Makefile).
- `https://raw.githubusercontent.com/ossc-db/pg_hint_plan/master/pg_hint_plan.control`
  @ 2026-06-12 → HTTP 200 (~150 bytes; read fully).
- `https://raw.githubusercontent.com/ossc-db/pg_hint_plan/master/README.md`
  @ 2026-06-12 → HTTP 200 (thin; defers to `docs/`).
- `https://raw.githubusercontent.com/ossc-db/pg_hint_plan/master/docs/hint_list.md`
  @ 2026-06-12 → HTTP 200 (full hint vocabulary; `[from-README]`-class).
- `https://raw.githubusercontent.com/ossc-db/pg_hint_plan/master/pg_hint_plan.c`
  @ 2026-06-12 → HTTP 200 (~3000+ lines; **skimmed** via 2 targeted query passes
  — hooks, scanner, `pgs_mask`, globals/re-entrancy, hint table, ExecutorEnd).
- `https://raw.githubusercontent.com/ossc-db/pg_hint_plan/master/Makefile`
  @ 2026-06-12 → HTTP 200 (OBJS = `pg_hint_plan.o query_scan.o`; the
  `# pg_stat_statements.c` fossil; upgrade-script chain).
- `https://raw.githubusercontent.com/ossc-db/pg_hint_plan/master/core.c`
  @ 2026-06-12 → **HTTP 404** (removed on master — the key finding for divergence
  #2; substituted with the PG16-branch copy below).
- `https://raw.githubusercontent.com/ossc-db/pg_hint_plan/master/make_join_rel.c`
  @ 2026-06-12 → **HTTP 404** (removed on master; substituted with PG16 below).
- `https://raw.githubusercontent.com/ossc-db/pg_hint_plan/PG16/Makefile`
  @ 2026-06-12 → HTTP 200 (HINTPLANVER 1.6.3; `pg_hint_plan.o: core.c make_join_rel.c`).
- `https://raw.githubusercontent.com/ossc-db/pg_hint_plan/PG16/make_join_rel.c`
  @ 2026-06-12 → HTTP 200 (header read — "Routines copied from PostgreSQL core",
  `joinrels.c`, `make_join_rel()`/`populate_joinrel_with_paths()`).
- `https://raw.githubusercontent.com/ossc-db/pg_hint_plan/PG16/core.c`
  @ 2026-06-12 → HTTP 200 (header read — copied `standard_join_search`,
  `set_plain_rel_pathlist`, `join_search_one_level`, etc. from `allpaths.c`/`joinrels.c`).
- `https://raw.githubusercontent.com/ossc-db/pg_hint_plan/PG16/pg_hint_plan.c`
  @ 2026-06-12 → HTTP 200 (skimmed for the historical `enable_*`-GUC toggling
  design; exact PG16 line numbers `[unverified]`).
- `.../master/SOURCES.txt` @ 2026-06-12 → HTTP 404 (does not exist; ignored).

All scan/join/order-mechanism, hook-chain, scanner, `pgs_mask`, global-state, and
hint-table claims are `[verified-by-code]` against the fetched master
`pg_hint_plan.c`/`Makefile`/`.control`, except: the "core refuses hints" stance
(`[unverified]` project lore), the GEQO interaction inside
`pg_hint_plan_join_search` (`[unverified]`, body not read), the per-major-branch
vendoring rationale (`[inferred]` from branch layout), and the present-day
pg_stat_statements handling (`[inferred]`/`[unverified]`). The vendored-core
header facts are `[verified-by-code]` against the **PG16** branch.
