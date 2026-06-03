# HypoPG — hypothetical indexes by forging RelOptInfo entries inside the planner

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `HypoPG/hypopg` @ branch `REL1_STABLE`. All `file:line` cites below
> point into that repo (not `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. Cites verified against
> the files fetched on 2026-06-03 (see Sources footer).

## Domain & purpose

HypoPG lets a DBA ask "would PostgreSQL use this index if it existed?" without
paying to build it. You call `hypopg_create_index('CREATE INDEX ON hypo
(id)')`, then run `EXPLAIN` — the plan shows an `Index Scan using
<41072>hypo_btree_hypo_id` even though no index exists on disk
(`README.md:4-10`, `:84-89`) `[from-README]`. There is **zero** catalog
mutation and **zero** storage: the hypothetical index lives only in a
per-backend in-memory list and is materialized into the planner's view of the
world *only during `EXPLAIN`*. It is the cleanest worked example of the
question: *how much can you lie to the planner from a hook, and have it produce
a truthful "would-use" answer?*

## How it hooks into PG

HypoPG is **lazy-loaded** (no `shared_preload_libraries`) — its hooks are
installed in `_PG_init` on first SQL call, which is sufficient because the only
moment they need to be active is during an interactive `EXPLAIN` in the same
backend (`hypopg.control:1-5`). All state is backend-local and ephemeral; the
README even notes there are no upgrade scripts because "there's no data saved
in any of the objects" (`README.md:31-33`).

`_PG_init` chains **five** hooks (`hypopg.c:118-176`) `[verified-by-code]`:

| Hook | Purpose |
|---|---|
| `ProcessUtility_hook` (`hypo_utility_hook`) | The *trigger*: detect that the current statement is a simple `EXPLAIN` and set the global `isExplain` flag, so the planner hooks know to inject (`hypopg.c:121-122`, `:294-322`, `:456-465`). |
| `ExecutorEnd_hook` (`hypo_executorEnd_hook`) | Reset `isExplain = false` after the query so injection doesn't leak into real execution (`hypopg.c:124-125`, `:458-465`). |
| `get_relation_info_hook` **(PG < 19)** / `build_simple_rel_hook` **(PG ≥ 19)** | The *payload*: when `isExplain && hypo_is_enabled`, walk the backend's `hypoIndexes` list and inject matching hypothetical indexes into the `RelOptInfo` (`hypopg.c:127-133`, `:514-565`). |
| `explain_get_index_name_hook` | Make `EXPLAIN` print the fake index's synthesized name (`<oid>name`) instead of resolving the OID against `pg_class` (where it doesn't exist) (`hypopg.c:135-136`, `hypopg_index.h:133-135`). |

Two `PGC_USERSET` GUCs: `hypopg.enabled` and `hypopg.use_real_oids`
(`hypopg.c:153-173`). The control surface is ten SQL-callable C functions
(`hypopg_create_index`, `hypopg_drop_index`, `hypopg_relation_size`,
`hypopg_hide_index`, …) (`hypopg_index.h:122-131`) — the
UDF-as-control-surface pattern, since an extension cannot add `CREATE
HYPOTHETICAL INDEX` grammar. Cross-ref `[[knowledge/idioms/fmgr]]`.

## Where it diverges from core idioms

### 1. It builds a hand-rolled twin of `IndexOptInfo`, populated from `pg_am` at runtime

The core idiom is: `get_relation_info()` reads `pg_index`/`pg_class` and builds
an `IndexOptInfo` per real index. HypoPG instead defines `hypoIndex`
(`hypopg_index.h:45-110`) — explicitly commented "pretty much an
`IndexOptInfo`" — and fills it with the *same* fields the planner needs
(`indexkeys`, `opfamily`, `opclass`, `sortopfamily`, `amcostestimate`,
`amcanreturn`, `amsearcharray`, `amcanparallel`, …). Crucially it copies the
AM's capability flags and the `amcostestimate`/`amcanreturn` **function
pointers** straight off the access method (`hypopg_index.h:72-78`,
`:92-104`) so the planner costs the hypothetical index with the *real* cost
function of the chosen AM. This is a deliberate re-implementation of core's
relcache-to-IndexOptInfo path at "imaginary index" scope. Cross-ref
`[[knowledge/subsystems/optimizer]]`, `[[knowledge/architecture/planner]]`,
`[[knowledge/architecture/access-methods]]`.

### 2. Fake OIDs deliberately allocated below `FirstNormalObjectId` (16384)

Hypothetical indexes need OIDs the planner can key on, but those OIDs must not
collide with real catalog objects. By default HypoPG hands out OIDs from the
**bootstrap-reserved range `< 16384`** (`hypopg.c:164-167` — the
`use_real_oids` GUC toggles "Use real oids rather than the range < 16384",
`hypo_getNewOid`/`hypo_reset_fake_oids` at `hypopg.h:55-56`). Squatting in the
reserved-OID space is precisely the inverse of core's `FirstNormalObjectId`
contract (everything user-created is ≥ 16384); HypoPG uses the gap as a private
namespace that can never alias a real index. Cross-ref
`[[knowledge/idioms/catalog-conventions]]` — the OID-assignment policy this
intentionally side-steps.

### 3. Injection is gated on an `isExplain` flag toggled by ProcessUtility, not on planner context

There is no planner-level "is this EXPLAIN?" signal an extension can read, so
HypoPG manufactures one: `hypo_utility_hook` inspects the utility statement,
decides if it's a *simple* `EXPLAIN` (`hypo_is_simple_explain`), and sets the
global `isExplain` (`hypopg.c:294-322`). The planner hook then reads that flag
(`hypopg.c:529`). `ExecutorEnd_hook` clears it. This cross-hook flag handoff —
utility hook arms, planner hook fires, executor hook disarms — is an idiom
core never needs (core knows its own call context) and is the load-bearing
trick that keeps hypothetical indexes invisible to everything except
`EXPLAIN`. The README's promise that "concurrent connections doing `EXPLAIN`
won't be bothered by your hypothetical indexes" (`README.md:38-40`) follows
directly: the list is backend-local and the flag is per-statement.

### 4. It opens the heap relation from inside a planner hook, taking AccessShareLock

`hypo_get_relation_info_hook` does `table_open(relationObjectId,
AccessShareLock)` … `table_close(..., AccessShareLock)` around the injection
(`hypopg.c:534`, `:564`) to read `relkind` and reltuples-like stats for cost
estimation. Re-opening a relation the planner already has info for, from within
a `get_relation_info` hook, is unusual — core passes the planner everything it
needs — but HypoPG needs live relation stats to estimate the hypothetical
index's `pages`/`tuples` (computed lazily, not stored; `hypopg_index.h:52-54`).
It carefully restricts injection to `RELKIND_RELATION`/`RELKIND_MATVIEW`
(`hypopg.c:536-540`). Cross-ref `[[knowledge/idioms/locking-overview]]`,
`[[knowledge/subsystems/utils-cache]]` (relcache).

### 5. "Hidden indexes": the mirror feature — make a *real* index invisible to the planner

Beyond adding fake indexes, HypoPG can *remove* real ones from the planner's
consideration: `hypoHiddenIndexes` + `hypo_hideIndexes(rel)` strip existing
`IndexOptInfo`s out of the `RelOptInfo` during the same hook
(`hypopg_index.h:116`, `:143`, `hypopg.c:560`). This lets a DBA ask "what would
the planner do *without* index X?" — the symmetric question to "with
hypothetical index Y?". Both are pure planner-view manipulations with no
catalog effect.

### 6. Header is a museum of `PG_VERSION_NUM` compatibility shims (PG 9.2 → 19)

HypoPG supports PostgreSQL 9.2 and up (`README.md:21`) in one source tree, so
the headers backfill APIs that changed across a decade of majors: `table_open`
aliased to `heap_open` pre-12 (`hypopg.h:26-29`); a "hacky macro" reimplementing
1-arg vs 2-arg `lnext()` pre-13 (`hypopg.h:32-41`); `atooid` backport pre-10
(`hypopg.h:43-46`); the whole hook *choice* switches from `get_relation_info_hook`
to `build_simple_rel_hook` at PG 19 (`hypopg.c:127-133`) because core changed
where per-rel info is assembled. It even hardcodes bloom-index page constants
because "`bloom.h` is not exported" (`hypopg_index.h:30-35`). This pervasive
multi-version straddling has no core analogue — core deletes old code; an
out-of-tree extension cannot.

## Notable design decisions (cited)

- **All state in one `TopMemoryContext` child.** `HypoMemoryContext` is created
  under `TopMemoryContext` (`hypopg.c:142-151`) so hypothetical-index
  definitions survive across statements within a backend but die with the
  backend — exactly the lifetime a session-scoped "what-if" tool wants.
  Cross-ref `[[knowledge/idioms/memory-contexts]]`.
- **Parse the user's real `CREATE INDEX` text.** `hypopg_create_index` takes a
  literal `CREATE INDEX` statement string and runs it through the normal parser
  to extract columns/opclasses/predicate (`README.md:53-76`) — reusing core's
  grammar instead of inventing an index-spec format, at the cost of ignoring
  some clauses (e.g. the index name) (`README.md:60-62`).
- **`hypopg()` mimics `pg_index`.** The introspection function returns columns
  "in a similar way as the `pg_index` system catalog" (`README.md:78-80`,
  `HYPO_INDEX_NB_COLS = 12` at `hypopg_index.h:24`) so existing tooling reads it
  like a catalog.
- **`EmitWarningsOnPlaceholders("hypopg")`** (`hypopg.c:175`) — the older
  spelling of `MarkGUCPrefixReserved`, reserving the `hypopg.*` GUC namespace
  (another compat-era artifact).
- **Single-column-only, for now.** `ncolumns` is commented "only 1 for now"
  (`hypopg_index.h:60`) — a candid scope limit in the struct itself.

## Links into corpus

- `[[knowledge/architecture/planner]]` + `[[knowledge/subsystems/optimizer]]`
  — the `RelOptInfo`/`IndexOptInfo` machinery HypoPG forges entries into; this
  is the single most important cross-reference.
- `[[knowledge/architecture/access-methods]]` — HypoPG copies AM capability
  flags + `amcostestimate`/`amcanreturn` function pointers to cost a fake index
  with the real AM's costing.
- `[[knowledge/idioms/catalog-conventions]]` — the `FirstNormalObjectId` /
  OID-assignment policy HypoPG deliberately squats below.
- `[[knowledge/idioms/fmgr]]` — UDF-as-control-surface (ten SQL-callable C
  functions instead of new DDL grammar).
- `[[knowledge/idioms/memory-contexts]]` — the `TopMemoryContext`-child
  session-lifetime context.
- `[[knowledge/idioms/locking-overview]]` + `[[knowledge/subsystems/utils-cache]]`
  — `table_open(AccessShareLock)` + relcache access from inside the planner hook.
- `[[knowledge/subsystems/tcop]]` — `ProcessUtility_hook` is where the
  `isExplain` flag is armed; tcop owns the utility path.
- `.claude/skills/extension-development/SKILL.md` — the five-hook chaining
  pattern, GUC definition, lazy-load model HypoPG exemplifies.

## Sources

Fetched 2026-06-03 (branch `REL1_STABLE`):

- `https://raw.githubusercontent.com/HypoPG/hypopg/REL1_STABLE/README.md`
  @ 2026-06-03T23:06Z → HTTP 200 (192 lines).
- `https://raw.githubusercontent.com/HypoPG/hypopg/REL1_STABLE/include/hypopg.h`
  @ 2026-06-03T23:06Z → HTTP 200 (58 lines).
- `https://raw.githubusercontent.com/HypoPG/hypopg/REL1_STABLE/include/hypopg_index.h`
  @ 2026-06-03T23:06Z → HTTP 200 (145 lines).
- `https://raw.githubusercontent.com/HypoPG/hypopg/REL1_STABLE/hypopg.control`
  @ 2026-06-03T23:06Z → HTTP 200 (6 lines).
- `https://raw.githubusercontent.com/HypoPG/hypopg/REL1_STABLE/hypopg.c`
  @ 2026-06-03T23:06Z → HTTP 200 (584 lines).
- Tree listing
  `https://api.github.com/repos/HypoPG/hypopg/git/trees/REL1_STABLE?recursive=1`
  @ 2026-06-03T23:06Z → HTTP 200.

> Queue manifest named `hypopg.h,hypopg_index.h`; the real paths are under
> `include/`, fetched accordingly — no gap.

All cites are `[verified-by-code]` against the fetched `.c`/`.h` (struct
shapes, hook installs, the `isExplain` flag handoff, fake-OID range) except the
end-user workflow narrative, which is `[from-README]`. The index-injection
internals (`hypopg_index.c`, `hypo_injectHypotheticalIndex` body) were not in
the manifest; statements about *how* the `IndexOptInfo` is populated are
inferred from the `hypoIndex` struct + the hook call sites and tagged where
they exceed a declaration.
</content>
