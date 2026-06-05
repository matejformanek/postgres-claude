# pg_repack — online CLUSTER/VACUUM FULL by copying core's catalog-swap into an extension

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `reorg/pg_repack` @ branch `master`. All `file:line` cites below point
> into that repo (not `source/`), since this doc characterizes an *external*
> extension's divergence from core idioms. Cites verified against the files
> fetched on 2026-06-05 (see Sources footer).

## Domain & purpose

pg_repack removes bloat from tables and indexes — and optionally restores the
physical row order of a clustered index — **online**, without the
`ACCESS EXCLUSIVE` lock that core's `CLUSTER` and `VACUUM FULL` hold for their
entire run (`doc/pg_repack.rst:8-13`) `[from-README]`. It is the worked answer
to: *how do you rewrite a whole heap into a fresh, compact, correctly-ordered
file while concurrent INSERT/UPDATE/DELETE keep running, then cut over
atomically?* The answer pg_repack settled on is a **trigger-based
change-capture log + a full copy + a catalog-level relfilenode swap** — i.e. it
re-implements, in an extension, the cut-over half of what core's `CLUSTER` does
internally, plus a hand-rolled mini-logical-replication to bridge the online
window. It is a fork of the older `pg_reorg` (`doc/pg_repack.rst:15-16`).

It ships as two halves: a client program (`bin/pg_repack.c`, a libpq driver that
orchestrates over multiple connections) and a **backend C extension**
(`lib/repack.c`) that exposes ten `PG_FUNCTION_INFO_V1` SQL-callable functions
the client calls in sequence (`lib/repack.c:85-105`). This note is about the
backend half — that is where the idiom divergence lives.

## How it hooks into PG

pg_repack installs **no hooks, no bgworker, no AM**. It hooks into PG purely as
a set of SQL-callable C functions in a `repack` schema, driven by an external
client. The modern magic block is version-gated:
`PG_MODULE_MAGIC_EXT(.name="pg_repack", .version=...)` on PG ≥ 18, plain
`PG_MODULE_MAGIC` before (`lib/repack.c:76-83`) `[verified-by-code]`.

The cut-over algorithm the client drives (`doc/pg_repack.rst:447-461`)
`[from-README]`:

1. `CREATE` a log table `repack.log_<oid>` to record changes.
2. Add an `AFTER` row trigger (`repack_trigger`) to the original table that
   writes every INSERT/UPDATE/DELETE into that log.
3. `CREATE TABLE repack.table_<oid>` holding a copy of all rows (ordered, if
   clustering).
4. Build indexes on the copy.
5. Replay the accrued log onto the copy (`repack_apply`).
6. **Swap** heap, indexes, and TOAST in the system catalogs (`repack_swap`).
7. Drop the original (`repack_drop`).

Only steps 1–2 and 6–7 hold `ACCESS EXCLUSIVE`, and only briefly; the long copy
runs under `SHARE UPDATE EXCLUSIVE`, so DML proceeds (`doc/pg_repack.rst:457-461`).

## Where it diverges from core idioms

### 1. It copies a *static* core function — `swap_relation_files` from `cluster.c` — into the extension

The single most idiom-divergent choice. `swap_heap_or_index_files`
(`lib/repack.c:1230-1418`) is, by its own comment, *"a copy of
swap_relation_files in cluster.c, but it also swaps relfrozenxid"*
(`lib/repack.c:1226-1229`) `[from-comment]`. Core never exported that function,
so pg_repack vendored it: it opens `pg_class` with `RowExclusiveLock`, fetches
two writable `Form_pg_class` tuples with `SearchSysCacheCopy1`, and **byte-swaps
the physical-storage fields directly** — `relfilenode`, `reltablespace`,
`reltoastrelid` (`lib/repack.c:1263-1273`), then `relfrozenxid`/`relminmxid` for
heaps (`lib/repack.c:1278-1290`) and the `relpages`/`reltuples`/`relallvisible`
size stats (`lib/repack.c:1292-1309`), writing both back with
`CatalogTupleUpdateWithInfo` (`lib/repack.c:1325-1326`). Reaching into
`Form_pg_class` and overwriting `relfilenode` from an extension is exactly the
kind of catalog surgery core keeps behind static functions; pg_repack does it in
userspace because that is the only way to make the new file *become* the table
without a fresh OID. Cross-ref `[[knowledge/subsystems/access-heap]]` (CLUSTER /
swap_relation_files), `[[knowledge/idioms/catalog-conventions]]`.

### 2. It carries core's relcache "kluge" comment verbatim — because it inherits the same hazard

Right after the swap it calls `RelationForgetRelation(r1)`/`(r2)`
(`lib/repack.c:1406-1407`) under a comment copied from core explaining that
`relcache.c` keeps a link to the `smgr` relation for the physical file, which
goes stale at the next `CommandCounterIncrement`, so the entries must be blown
away rather than carefully ordered (`lib/repack.c:1393-1405`) `[from-comment]`.
An extension reproducing core's *internal cache-coherence reasoning* is the
tell that it is operating one abstraction layer below where extensions usually
sit. Cross-ref `[[knowledge/subsystems/utils-cache]]` (relcache / smgr link),
`[[knowledge/subsystems/access-transam]]` (CommandCounterIncrement visibility).

### 3. Change-capture is a hand-rolled mini-logical-replication in SPI, not WAL/logical decoding

Rather than tap logical decoding, pg_repack captures concurrent writes with a
plain `AFTER` trigger whose C body (`repack_trigger`, `lib/repack.c:171-236`)
builds an `INSERT INTO repack.log_<relid>(pk, row) VALUES(...)` and executes it
through SPI (`lib/repack.c:223-231`). The replay side, `repack_apply`
(`lib/repack.c:252-373`), is a bespoke log-pump: it `peek`s up to
`DEFAULT_PEEK_COUNT` (1000) log rows via a prepared SPI plan
(`lib/repack.c:255-297`), demultiplexes each into INSERT/DELETE/UPDATE by which
of `pk`/`row` is NULL (`lib/repack.c:325-345`), lazily preparing one SPI plan per
op-kind, then bulk-`DELETE`s the consumed log rows with a `... IN (id,id,...)`
string it assembles by hand (`lib/repack.c:347-365`). This is a from-scratch
replication apply loop living inside a SQL-callable function. Cross-ref
`[[knowledge/idioms/spi]]`, `[[knowledge/subsystems/replication]]` (the logical
decoding it chose *not* to use).

### 4. It asserts core's locking invariants from the outside, and reasons about deadlocks in comments

Because pg_repack swaps catalog state itself, it cannot rely on a core command
to have taken the right locks — so it *checks*. Before swapping, `repack_swap`
calls `CheckRelationOidLockedByMe(oid, AccessExclusiveLock, true)` on both the
original and the copy and `elog(ERROR)`s if either lock is missing
(`lib/repack.c:919-936`) `[verified-by-code]` — version-gated against the
pre-17 `LockHeldByMe`/`LOCKTAG` form. And `repack_drop` carries a 19-line
comment deriving a concrete deadlock between the trigger's `log_<oid>` lock and
the target-table lock, concluding it must `LOCK TABLE ... IN ACCESS EXCLUSIVE
MODE` up front to serialize (`lib/repack.c:1096-1121`) `[from-comment]`.
Hand-proving a lock-ordering argument is normally a core-hacker activity.
Cross-ref `[[knowledge/subsystems/storage-lmgr]]`, `.claude/skills/locking/SKILL.md`.

### 5. Pervasive `PG_VERSION_NUM` `#if` ladders — the portability tax core never pays

Core targets exactly one version; pg_repack supports 9.5 → 19
(`doc/pg_repack.rst:43-46`) from one source tree, so almost every catalog touch
is wrapped: `RENAME_REL`/`RENAME_INDEX` macros bridge the
`RenameRelationInternal` signature change at 9.2/12 (`lib/repack.c:141-153`);
`must_be_owner` has three branches for `object_ownercheck` (16) vs
`pg_class_ownercheck` (11) vs the old `ACL_KIND_CLASS` form
(`lib/repack.c:120-135`); `table_open` vs `heap_open`, `CatalogTupleUpdateWithInfo`
vs `simple_heap_update` (`lib/repack.c:1242-1246, 1313-1328`). This
preprocessor-driven multi-version support is a defining external-extension idiom
and the opposite of core's single-target style.

## Notable design decisions (cited)

- **A PK or NOT-NULL UNIQUE index is mandatory** (`doc/pg_repack.rst:29-30`):
  the log replay keys every captured change on the primary key, encoded as a
  generated `repack.pk_<relid>` composite type (`lib/repack.c:223-228`). No PK ⇒
  no stable row identity to replay against.
- **TOAST cut-over is a three-way rename dance.** When both old and new heaps
  have TOAST, `repack_swap` renames old→`pg_toast_pid<pid>`, new→`pg_toast_<oid>`,
  old→`pg_toast_<oid2>`, each followed by `CommandCounterIncrement`
  (`lib/repack.c:1012-1037`) — because TOAST relations are named by OID and two
  can't share a name mid-swap.
- **`repack_get_order_by` parses `pg_get_indexdef_string` textually**, with a
  candid `FIXME: this is very unreliable ... but I don't want to re-implement
  customized versions of pg_get_indexdef_string` (`lib/repack.c:698-701`). It
  string-walks the DDL to recover ORDER BY columns + opclass operators
  (`lib/repack.c:578-639, 684-775`) — choosing fragile text parsing over
  re-deriving from `pg_index`.
- **Owner check is manual, mirroring core's `aclcheck_error`** rather than
  relying on function `EXECUTE` privilege: `must_be_owner` calls
  `object_ownercheck` + `aclcheck_error(ACLCHECK_NOT_OWNER, ...)` directly
  (`lib/repack.c:120-135`), gating `repack_swap`/`repack_drop`/`repack_index_swap`.
- **`repack_get_table_and_inheritors`** uses core's `find_all_inheritors` and
  deliberately *keeps* the `AccessShareLock`s it takes (note in the header,
  `lib/repack.c:1465-1493`) so the client holds them across the operation.

## Links into corpus

- `[[knowledge/subsystems/access-heap]]` — `CLUSTER` / `swap_relation_files`,
  the static core routine pg_repack vendored.
- `[[knowledge/subsystems/utils-cache]]` — relcache ↔ smgr link and the
  `RelationForgetRelation` invalidation kluge it copied.
- `[[knowledge/subsystems/access-transam]]` — `relfrozenxid`/`relminmxid`
  consistency and `CommandCounterIncrement` visibility between swaps.
- `[[knowledge/subsystems/storage-lmgr]]` — the `AccessExclusiveLock` assertions
  and the hand-derived deadlock-avoidance lock order.
- `[[knowledge/idioms/spi]]` — the trigger-log capture and the `repack_apply`
  replay loop are all SPI prepared-plan execution.
- `[[knowledge/idioms/catalog-conventions]]` — direct `Form_pg_class` mutation
  + `CatalogTupleUpdateWithInfo` + dependency re-linking.
- `[[knowledge/subsystems/replication]]` — logical decoding, the alternative to
  the trigger-based change capture pg_repack built instead.
- `.claude/skills/locking/SKILL.md` — lock-ordering reasoning pg_repack reproduces.
- `.claude/skills/extension-development/SKILL.md` — SQL-callable-function-only
  module shape (no hooks/bgworker) and the `PG_VERSION_NUM` portability ladders.

## Sources

Fetched 2026-06-05 (branch `master`):

- `https://raw.githubusercontent.com/reorg/pg_repack/master/lib/repack.c`
  @ 2026-06-05 → HTTP 200 (1513 lines).
- `https://raw.githubusercontent.com/reorg/pg_repack/master/bin/pg_repack.c`
  @ 2026-06-05 → HTTP 200 (2496 lines; the libpq client orchestrator — fetched
  but only skimmed; this doc characterizes the backend `lib/repack.c`).
- `https://raw.githubusercontent.com/reorg/pg_repack/master/lib/pgut/pgut-spi.c`
  @ 2026-06-05 → HTTP 200 (111 lines; the `execute`/`execute_with_args` SPI
  wrappers `repack.c` calls).
- `https://raw.githubusercontent.com/reorg/pg_repack/master/doc/pg_repack.rst`
  @ 2026-06-05 → HTTP 200 (646 lines).
- `https://raw.githubusercontent.com/reorg/pg_repack/master/README.rst`
  @ 2026-06-05 → HTTP 200 (51 lines; points to `doc/`).
- Tree listing
  `https://api.github.com/repos/reorg/pg_repack/git/trees/master?recursive=1`
  @ 2026-06-05 → HTTP 200.

All `lib/repack.c` cites are `[verified-by-code]` against the fetched file (the
catalog-swap, the trigger-log capture, the lock assertions, the version
ladders). The 7-step algorithm, lock-window, and PK requirement are
`[from-README]`/`[from-comment]` per the `doc/pg_repack.rst` tags above. The
client-side multi-connection orchestration in `bin/pg_repack.c` was not traced
in depth.
