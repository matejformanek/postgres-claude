# pg_crdt — ideology / divergence-from-core notes

> Headline: a CRDT engine as a PG TYPE, kept live across a query via the
> expanded-datum trick (the deliberate fix for the deserialize-per-call tax).

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `supabase/pg_crdt` @ branch `master`. All `file:line` cites below point
> into **the pg_crdt tree, NOT PG `source/`** — this doc characterizes an external
> extension's divergence from core idioms. **Status: experimental** (the README's
> own title is "pg_crdt (experimental)", `README.md:3`). The on-disk artifacts use
> the name `automerge`, not `crdt`: the control file is `automerge.control`, the
> SQL type is `autodoc`, and the module is `automerge`. This is a **hand-written C
> / PGXS** extension (no Rust, no pgrx) that statically links the **automerge-c**
> library (`-lautomerge`, `Makefile`). Cites verified against files fetched
> 2026-06-15 (see Sources footer). Read alongside
> `[[knowledge/ideologies/pglite-fusion]]` — the comparable "embed a foreign
> engine as a datum" case, against which pg_crdt's expanded-datum design is the
> instructive contrast.

## Domain & purpose

pg_crdt "is an experimental extension adding support for conflict-free replicated
data types (CRDTs) in Postgres" (`README.md:3-5`) `[from-README]`. It registers
two new base types: `autodoc` — a serialized **Automerge CRDT document** — and
`autochange` — a single Automerge change op — plus a family of SQL functions that
mutate, merge, and apply changes to documents (`src/automerge/automerge--0.0.1.sql`)
`[verified-by-code]`. The canonical use is collaborative-app state: a column holds
an `autodoc`, peers each produce changes, and `merge(doc1, doc2)` or `apply(doc,
change)` reconciles them **conflict-free** rather than last-write-wins. The README
frames CRDTs as "the enabling technology for collaborative applications like Notion
and Figma" (`README.md:11`) `[from-README]`.

The reason to document it: it is the corpus's sharpest example of **a foreign CRDT
engine instantiated as a PG base type, but kept *live* across a query** — and the
README is unusually explicit that this design was chosen specifically to *fix* the
cost model that pglite-fusion exhibits. The "[original implementation] … used the
Automerge's Rust libary to implement a CRDT as a data type. This had a major
limitation: frequently updated CRDTs produce a lot of WAL and dead tuples. The new
implementation improves on this by taking advantage of an advanced in-memory
feature in Postgres called an 'expanded datum'" (`README.md:17-21`)
`[from-README]`. So where pglite-fusion deserialize-mutate-reserializes on *every*
call, pg_crdt keeps the deserialized engine handle alive in a `RW` expanded datum
and only flattens to bytes when the value is written back to the heap.

## How it hooks into PG

Plain PGXS + hand-written C. The `Makefile` declares `MODULE_big = automerge`,
globs every `src/automerge/**/*.c` into `OBJS`, and links the Automerge C library:
`SHLIB_LINK = -lc -lpq -lautomerge` (`Makefile`) `[verified-by-code]`. The
`.control` is minimal: `relocatable = false`, `superuser = false`, `schema =
automerge` (`automerge.control`) `[verified-by-code]` — note `superuser = false`,
unlike pglite-fusion's superuser/untrusted posture, because nothing here touches
the server filesystem.

- **The types** (`src/automerge/automerge--0.0.1.sql`) `[verified-by-code]`:
  - `autodoc` — `internallength = VARIABLE`, `storage = 'extended'`, with
    `autodoc_in` / `autodoc_out` I/O functions, all declared `IMMUTABLE STRICT`.
  - `autochange` — same shape, `autochange_in` / `autochange_out`.
- **The functions**, every one a `PG_FUNCTION_INFO_V1` C function:
  - reconcilers: `merge(autodoc, autodoc)` → `autodoc_merge`
    (`src/automerge/autodoc/autodoc_merge.c`), `apply(autodoc, autochange)` →
    `autodoc_apply_change` (`autodoc_apply_change.c`) `[verified-by-code]`.
  - mutators returning the doc: `put_str/int/double/bool/text/counter`,
    `inc_counter`, `splice_text`, `create_mark`, `set_actor_id` (all generated
    from `autodoc_put_template.h`) `[verified-by-code]`.
  - readers: `get_str/int/double/bool/text/counter`, `get_marks`,
    `get_changes` (SETOF autochange), `to_jsonb`.
  - constructors / casts: `from_jsonb`, and **implicit casts** both ways between
    `autodoc` and `jsonb` (`CREATE CAST (autodoc AS jsonb) … AS IMPLICIT`) plus a
    pure-SQL `autodoc_path_query` wrapping `jsonb_path_query`
    (`automerge--0.0.1.sql`) `[verified-by-code]`.
- **`_PG_init`** exists but is a no-op log line: `void _PG_init(void) { LOGF(); }`
  (`src/automerge/automerge.c`) `[verified-by-code]`. No hooks, no GUCs, no
  bgworker. `PG_MODULE_MAGIC` is in `automerge.c`.

Cross-ref `[[knowledge/idioms/fmgr-and-spi]]` (the calling convention), and
`.claude/skills/extension-development/SKILL.md`.

## Where it diverges from core idioms

### 1. The Datum is a foreign CRDT engine's serialized state — but it stays *expanded* (live) across the query

`autodoc` has two representations. On disk / flattened it is
`autodoc_FlatAutodoc { int32 vl_len_; uint8_t uuid[UUID_LEN]; }` followed by the
Automerge-saved byte image (`src/automerge/autodoc/autodoc.h:18-22`)
`[verified-by-code]`. In memory it is `autodoc_Autodoc`, an
`ExpandedObjectHeader`-fronted struct that holds a **live `AMdoc *doc`** and an
`AMstack *stack` — i.e. an instantiated Automerge engine handle, not bytes
(`autodoc.h:29-36`) `[verified-by-code]`. This is the core mechanism pglite-fusion
*lacks*: pg_crdt registers `ExpandedObjectMethods` (`autodoc_get_flat_size`,
`autodoc_flatten_into`, `autodoc.c`) so the executor can carry a read-write
expanded datum (`EOHPGetRWDatum`, the `AUTODOC_RETURN` macro, `autodoc.h:46-47`)
through a chain of function calls without re-serializing between them. See the PG
"in-memory expanded datum" doc the README itself cites (storage-toast.html
in-memory section). `[verified-by-code]`

### 2. Deserialize happens once per datum-entry, not once per call — the explicit anti-pglite-fusion

`DatumGetAutodoc` branches on `VARATT_IS_EXTERNAL_EXPANDED`: if the datum is
*already* expanded it returns the live handle with no work; only a flat (on-disk /
TOASTed) datum triggers `new_expanded_autodoc`, which `AMload`s the bytes back into
an `AMdoc` (`autodoc.c`, `DatumGetAutodoc` + `new_expanded_autodoc`)
`[verified-by-code]`. Mutators then operate on `doc->doc` in place and return the
**same** expanded datum via `AUTODOC_RETURN(doc)` (e.g.
`autodoc_put_template.h`, `autodoc_merge.c`, `autodoc_apply_change.c`)
`[verified-by-code]`. So a SQL expression like `put_str(put_int(doc, …), …)`
deserializes once and mutates a single live engine — O(1) deserializes for a chain,
versus pglite-fusion's O(N) full-image reserializes. Flattening back to bytes
(`AMsave`, `autodoc_get_flat_size`/`autodoc_flatten_into`, `autodoc.c`) happens
only when PG needs to store the value to the heap. This is the headline divergence,
and it is divergence *toward* a more PG-native cost model than the comparable
foreign-engine-as-type extension. `[verified-by-code]`

### 3. Conflict-free merge semantics replace MVCC last-write-wins at the value level

Core PG resolves concurrent writes by row-level MVCC: the last committed `UPDATE`
wins, earlier versions become dead tuples. pg_crdt pushes a *different* conflict
model down into a single column value: `autodoc_merge` calls `AMmerge(doc1->doc,
doc2->doc)` (`autodoc_merge.c`) and `autodoc_apply_change` calls `AMapplyChanges`
(`autodoc_apply_change.c`) `[verified-by-code]`, both of which reconcile divergent
edits deterministically and commutatively (Automerge's CRDT guarantee) rather than
discarding a loser. The doctest header shows the intent: `merge('{"foo":1}'::autodoc,
'{"bar":2}'::autodoc)` yields a doc with both keys (`autodoc_merge.c:18`)
`[from-comment]`. So MVCC still governs the *row*, but within the cell two
independently-evolved CRDT states merge without a "winner" — a semantic core's
heap AM has no notion of. `[inferred]`

### 4. The Automerge engine and its `AMstack` live outside PG MemoryContexts (partially)

`new_expanded_autodoc` creates an `AllocSetContextCreate` child context for the
expanded object and registers a `MemoryContextRegisterResetCallback` so that when
the context is reset/deleted, `autodoc_free_context_callback` runs `AMstackFree` +
`free(doc->stack)` (`autodoc.c`) `[verified-by-code]`. But note the engine's own
bookkeeping is **`calloc`'d, not `palloc`'d**: `doc->stack = calloc(1,
sizeof(AMstack))` (`autodoc.c`, mirrored in `autochange.c`) `[verified-by-code]`,
and the `AMdoc` plus everything the Automerge C library allocates internally lives
in libautomerge's own heap, invisible to `palloc`, `MemoryContextStats`, and
`pg_backend_memory_contexts`. The reset-callback bridge is the *correct* pattern to
avoid leaking the foreign engine on error/abort (better than pglite-fusion's bare
`std::mem::forget`), but the live CRDT state itself still inflates backend RSS in a
way PG's memory accounting can't see. Cross-ref `[[knowledge/idioms/memory-contexts]]`.

### 5. Type-I/O purity is bent: `autodoc_in` sniffs for JSON and dispatches to `jsonb_in`

A core type's input function parses exactly its own text format. `autodoc_in`
instead inspects the first byte: if `input[0] == '{'` it routes through
`DirectFunctionCall1(jsonb_in, …)` and builds the doc from JSON
(`_autodoc_from_jsonb`); otherwise it treats the input as a `bytea` literal and
`AMload`s it (`autodoc_in.c`) `[verified-by-code]`. So one type accepts two wire
formats (JSON object text *or* hex/escaped Automerge bytes) and the I/O function is
really a small dispatcher over two foreign decoders. `autodoc_out` always emits the
`bytea` form via `AMsave` + `getTypeOutputInfo(BYTEAOID, …)` (`autodoc_out.c`)
`[verified-by-code]` — i.e. round-tripping a JSON-entered doc out yields bytes, not
JSON. The implicit `autodoc ↔ jsonb` casts (§2 of the SQL file) are the intended
JSON path. `[verified-by-code]`

### 6. Error bridging goes through one shared abort callback, not per-call `ereport`

Every Automerge call is wrapped in `AMstackItem(&stack, AM…(), _abort_cb,
AMexpect(TAG))`. `_abort_cb` (`automerge.c`) is the single error funnel: it reads
`AMresultStatus`, and on `AM_STATUS_ERROR` / `AM_STATUS_INVALID_RESULT` (or a
wrong result tag) it `ereport(ERROR, …)`s with the Automerge error string pulled
via `AMresultError` + `pnstrdup` (`automerge.c`) `[verified-by-code]`. This is more
PG-idiomatic than pglite-fusion's panic-bridge — it *does* call `ereport` — but it
still selects no SQLSTATE (default `ERRCODE_INTERNAL_ERROR`), no `errdetail` /
`errhint`, and the message is whatever the foreign engine produced. Contrast core's
deliberate SQLSTATE/detail/hint discipline, `[[knowledge/idioms/fmgr-and-spi]]` and
the `error-handling` skill. Note also a latent bug smell: on the tag-mismatch path
it `free(data)` then `AMstackFree(stack)` *and* returns false after already having
`ereport(ERROR)`ed (which longjmps), so the post-ereport cleanup is dead code.
`[inferred]`

### 7. Volatility labels are optimistic: I/O is `IMMUTABLE`, but `put_*`/`merge` carry an actor-id identity

The I/O functions are declared `IMMUTABLE STRICT`
(`automerge--0.0.1.sql`) `[verified-by-code]`, and `merge`/`apply`/`put_*` are
declared only `STRICT` (default `VOLATILE`). The subtlety: an `autodoc` embeds a
per-document **actor id** (a UUID stored in the flat header, `autodoc.h:21`, set
from a random/derived actor on load, `autodoc.c` `AMsetActorId`)
`[verified-by-code]`, and `get_actor_id()` with no args mints a *new* actor id —
so document identity is not purely a function of its JSON content. Declaring the
content-producing path `IMMUTABLE` while the value carries hidden actor state is a
trust the planner can't verify. `[inferred]`

## Notable design decisions (cited)

- **Two expanded types share one machinery.** `autochange` is a near-clone of
  `autodoc`: same `ExpandedObjectHeader` + magic + `AMstack` shape
  (`autochange.h:24-32`, magic `319279584` vs autodoc's `319279583`,
  `autodoc.h:7` / `autochange.h:4`), same flatten/expand/reset-callback dance
  (`autochange.c`) `[verified-by-code]`. A change is just an Automerge change blob
  carried as its own type so `apply(doc, change)` and `get_changes(doc) → SETOF
  autochange` can move single ops through SQL.
- **`get_changes` is a set-returning function over the doc's op log**
  (`get_changes(autodoc) RETURNS SETOF autochange`, `automerge--0.0.1.sql`)
  `[verified-by-code]` — exposing the CRDT's internal change history as PG rows,
  the inverse of `apply`. The TODO list wants the aggregate counterpart
  (`select apply(doc, change) from changes`, `TODO.md`) `[from-README]`.
- **Heavy code-generation via token-paste macros.** `autodoc.h` defines `FN(x)`,
  `SUPPORT_FN`, and the `put_*` family is generated by including
  `autodoc_put_template.h` with `_SUFFIX` / `_PG_TYPE` / `_AM_PUT_MAP` defined per
  file (e.g. `autodoc_put_str.c` sets `_AM_PUT_MAP AMmapPutStr`)
  `[verified-by-code]`. One template, N typed `put_*` SQL functions.
- **`SupportRequestModifyInPlace` planner support.** `autodoc.h`'s `SUPPORT_FN`
  macro builds a planner support function that recognizes when an argument is an
  external `Param` matching the target paramid (`automerge.h`, `SupportRequestModifyInPlace`
  branch) `[verified-by-code]` — wiring the expanded-datum in-place-mutation
  optimization into the planner so a chained `put_*` can mutate the RW datum
  rather than copy it. This is the deepest core-integration point in the extension.
- **Counters and text-splice are real CRDT op types, not value overwrites.**
  `inc_counter(doc, key, val)` and `splice_text(doc, key, pos, del, val)`
  (`automerge--0.0.1.sql`) `[verified-by-code]` expose Automerge's RGA-text and
  PN-counter CRDTs — semantics with no PG-scalar analogue (an increment that
  commutes across replicas, a text edit positioned by index that survives
  concurrent edits).
- **No upgrade script.** `default_version = '0.0.1'` and the only SQL file is
  `automerge--0.0.1.sql` (`automerge.control`, `Makefile DATA` glob)
  `[verified-by-code]` — the Automerge save format is implicitly frozen at
  whatever libautomerge version is linked.

## Links into corpus

- `[[knowledge/ideologies/pglite-fusion]]` — the **direct contrast**. Both embed a
  foreign engine as a PG base type, but pglite-fusion deserialize-mutate-
  reserializes on *every* call (O(db size) per op, no persistent handle), whereas
  pg_crdt uses PG's expanded-datum to keep the live Automerge engine across a query
  and flatten only on store. pg_crdt's README names exactly this as the limitation
  it set out to fix. Read these two together.
- `[[knowledge/idioms/memory-contexts]]` — the expanded object lives in a child
  `AllocSet` context with a reset callback that frees the foreign engine; but the
  `AMstack` is `calloc`'d and the live `AMdoc` is in libautomerge's heap, outside
  `palloc` accounting.
- `[[knowledge/idioms/fmgr-and-spi]]` — every entry point is a hand-written
  `PG_FUNCTION_INFO_V1`; `merge`/`apply`/`get_changes` (SRF) map onto core fmgr +
  set-return mechanics; error reporting funnels through one `ereport`-ing callback.

## Anthropology takeaway

pg_crdt is the doc-set's cleanest case of **a foreign engine embedded as a PG type
that learned from the naive version's mistakes**. Its headline divergence is not
the embedding itself (pglite-fusion does that) but the *cost model fix*: by
registering `ExpandedObjectMethods` and returning read-write expanded datums, the
live Automerge `AMdoc` survives across a chain of SQL function calls — deserialized
once on entry, flattened once on store — explicitly to avoid the WAL/dead-tuple/
reserialize-per-call tax the original Rust-as-a-type implementation paid. The
second instructive divergence is semantic: it pushes a **conflict-free merge model
into a single column value**, so concurrent edits reconcile commutatively
(`AMmerge` / `AMapplyChanges`) instead of MVCC last-write-wins. The rough edges are
proportionate to "experimental": one un-SQLSTATE'd error funnel with dead post-
`ereport` cleanup, an `IMMUTABLE` I/O path over a value that carries hidden actor
identity, and a type input function that sniffs JSON-vs-bytes. It's a noticeably
more PG-native take on "datum as a foreign engine" than its closest cousin — the
expanded-datum integration (down to a `SupportRequestModifyInPlace` planner support
function) is the part worth stealing.

## Sources

Fetched 2026-06-15 (branch `master` — confirmed; `main` not tried, `master` 200'd):

- `https://raw.githubusercontent.com/supabase/pg_crdt/master/README.md`
  → HTTP 200 (1570 bytes; purpose, CRDT framing, the expanded-datum architecture
  rationale, read fully).
- `https://raw.githubusercontent.com/supabase/pg_crdt/master/TODO.md`
  → HTTP 200 (605 bytes; roadmap — aggregate apply, sync API, marks).
- `https://raw.githubusercontent.com/supabase/pg_crdt/master/Makefile`
  → HTTP 200 (471 bytes; PGXS, `MODULE_big = automerge`, `-lautomerge`, C11 -O0 -g3).
- `https://raw.githubusercontent.com/supabase/pg_crdt/master/automerge.control`
  → HTTP 200 (152 bytes; `superuser = false`, `relocatable = false`, schema=automerge).
- `https://raw.githubusercontent.com/supabase/pg_crdt/master/src/automerge/automerge.h`
  → HTTP 200 (1438 bytes; includes, `_abort_cb`, `SUPPORT_FN` macro, FN/STRINGIFY
  codegen helpers).
- `https://raw.githubusercontent.com/supabase/pg_crdt/master/src/automerge/automerge.c`
  → HTTP 200 (1940 bytes; `PG_MODULE_MAGIC`, `_abort_cb` error funnel, no-op `_PG_init`).
- `https://raw.githubusercontent.com/supabase/pg_crdt/master/src/automerge/autodoc/autodoc.h`
  → HTTP 200 (flat + expanded autodoc structs, EOH macros, magic).
- `https://raw.githubusercontent.com/supabase/pg_crdt/master/src/automerge/autodoc/autodoc.c`
  → HTTP 200 (expanded-object methods: flat-size/flatten/new_expanded/DatumGetAutodoc,
  reset callback, deep-read).
- `.../autodoc/autodoc_in.c`, `autodoc_out.c` → HTTP 200 (JSON-vs-bytes I/O dispatch).
- `.../autodoc/autodoc_merge.c`, `autodoc_apply_change.c` → HTTP 200 (AMmerge /
  AMapplyChanges — the CRDT reconcilers).
- `.../autodoc/autodoc_put_template.h`, `autodoc_put_str.c` → HTTP 200 (the codegen
  template; in-place mutate-and-return-RW-datum pattern).
- `.../autochange/autochange.h`, `autochange.c`, `autochange_in.c` → HTTP 200
  (the second expanded type, near-clone of autodoc).
- `https://raw.githubusercontent.com/supabase/pg_crdt/master/src/automerge/automerge--0.0.1.sql`
  → HTTP 200 (the full type/function/cast install schema, read fully).
- 404 noted: `src/automerge/automerge.control` (the control file is at repo root
  as `automerge.control`, not under `src/`).

All cites are `[verified-by-code]` against the fetched C / header / SQL files
except: the CRDT/collaborative-app framing and roadmap (`[from-README]`); the
`merge` example semantics (`[from-comment]`, doctest header); and the MVCC-vs-CRDT
contrast, actor-id volatility concern, foreign-heap memory observation, and the
dead-post-`ereport`-cleanup smell (`[inferred]`). Not examined (out of scope, names
self-describing): the ~40 `autodoc_get_*` / `autodoc_put_*` / `autodoc_create_mark_*`
/ traverse-template files, the `autochange_*` accessor files, the `sql/expected/`
regression fixtures, and the `docs/` / `docgen.py` documentation tooling.
