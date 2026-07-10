# pg_dirtyread — forensic "undelete" by deliberately defeating MVCC visibility

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `df7cb/pg_dirtyread` @ branch `master`. All `file:line` cites below
> point into that repo (not `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. Cites verified against the
> blobs fetched on 2026-07-10 (see Sources footer). Line numbers are for the
> `master` blobs as fetched.

pg_dirtyread is a set-returning function that reads **dead but not-yet-vacuumed
rows** back out of a heap — an "undelete" for a table that was accidentally
`DELETE`d or `UPDATE`d before `VACUUM` reclaimed the tuples (`README.md:4-5`)
`[from-README]`. **Headline divergence:** every sanctioned PostgreSQL access
path filters heap tuples through an MVCC `Snapshot`
(`HeapTupleSatisfiesVisibility`), so a committed-deleted row is *invisible* by
construction. pg_dirtyread opens the relation and runs a raw sequential heap
scan under **`SnapshotAny`** (`pg_dirtyread.c:115-119`) `[verified-by-code]`,
which accepts *every* line-pointer-live tuple regardless of `xmin`/`xmax`
commit state. It is not a new storage engine or a hook — it is a single C
function whose entire reason to exist is to *turn off* the visibility check that
the rest of the system treats as inviolable.

## Domain & purpose

The extension "provides the ability to read dead but unvacuumed rows from a
relation" (`README.md:4-5`) `[from-README]`. Concretely: you `DELETE`d (or
`UPDATE`d) rows, autovacuum has not yet run, and you want them back. Because a
deleted heap tuple physically survives until `VACUUM`/HOT-prune reclaims it, the
bytes are still on the page — only the visibility rules hide them. pg_dirtyread
surfaces them, and additionally lets you name **system columns**
(`xmin`, `xmax`, `cmin`, `cmax`, `ctid`, `tableoid`) plus a synthetic `dead`
boolean, so you can see exactly which transaction inserted or deleted each
version and decide what to re-insert (`README.md:87-111`) `[from-README]`. The
README is blunt about the window: dropped-column content and dead rows survive
"as long as the table has not been rewritten (e.g. via `VACUUM FULL` or
`CLUSTER`)" (`README.md:69-70`) `[from-README]`. It is a forensic tool, the
recovery counterpart to `[[pg-safeupdate]]` (which *prevents* the unqualified
`DELETE` that pg_dirtyread cleans up after).

## How it hooks into PG

There is no `_PG_init`, no hook, no bgworker, no shmem. The whole surface is one
`LANGUAGE C` SRF declared `pg_dirtyread(regclass) RETURNS SETOF record`
(`pg_dirtyread--2.sql:1-4`) `[verified-by-code]`, `relocatable = true` with the
control comment "Read dead but unvacuumed rows from table"
(`pg_dirtyread.control:1-5`) `[verified-by-code]`. The function returns
`RECORD`, so the caller must attach a column-alias list —
`SELECT * FROM pg_dirtyread('foo') AS t(bar bigint, baz text)` — and columns are
matched to the heap **by name**, letting you omit, reorder, or add columns
(`README.md:40-43`) `[from-README]`.

First-call setup (`pg_dirtyread.c:82-135`) `[verified-by-code]`:

- **Superuser gate.** `if (!superuser()) ereport(ERROR … "must be superuser to
  use pg_dirtyread")` (`pg_dirtyread.c:88-91`) — the only access control, since
  the function bypasses row-level visibility entirely.
- **Open + describe.** `table_open(relid, AccessShareLock)` (pre-12
  `heap_open`) (`pg_dirtyread.c:100-105`); the on-disk descriptor is
  `RelationGetDescr` (`:106`); the *output* descriptor comes from
  `get_call_result_type(...)` + `BlessTupleDesc` (`:107-112`).
- **Build the conversion map** between the heap descriptor and the caller's
  alias via `dirtyread_convert_tuples_by_name` (`pg_dirtyread.c:113-114`) — the
  vendored tuple converter (see §diverges).
- **Raw scan under `SnapshotAny`.** `heap_beginscan(rel, SnapshotAny, 0, NULL,
  …, SO_TYPE_SEQSCAN)` (`pg_dirtyread.c:115-119`) — this is the load-bearing
  line. No index is used; it is a full seqscan of every page.
- **A visibility horizon for the `dead` column only.** On PG ≥ 14
  `GlobalVisTestFor(rel)`; earlier, `GetOldestXmin(rel, 0)` guarded by
  `!RecoveryInProgress()` (`pg_dirtyread.c:121-133`). This horizon is *not* used
  to filter the scan — only to compute the synthetic `dead` flag per row.

Per-call (`pg_dirtyread.c:138-160`): `heap_getnext(scan, ForwardScanDirection)`;
each raw `HeapTuple` is run through `dirtyread_do_convert_tuple(tuplein, map,
oldest_xmin)` and returned via `SRF_RETURN_NEXT` (`:141-149`); at end of scan it
`heap_endscan` + `table_close` (`:151-159`).

## Where it diverges from core idioms

### 1. It scans under `SnapshotAny` — the deliberate MVCC bypass

Core's contract is that a heap tuple is returned to a query only if it satisfies
the query's snapshot: `heap_getnext` normally carries an MVCC snapshot and each
tuple is tested by `HeapTupleSatisfiesVisibility` before it reaches the caller.
pg_dirtyread passes **`SnapshotAny`** (`pg_dirtyread.c:115`), the "see
everything the line pointer still points at" pseudo-snapshot, so
committed-deleted (`xmax` set + committed), aborted-insert, and
not-yet-visible tuples are *all* returned. The README's worked example shows
exactly this: rows with a non-zero `xmax` and `dead = t` are returned alongside
live ones (`README.md:98-111`) `[from-README]`. This is the single idiom
inversion the whole extension is built around — it does not add a filter, it
removes the one filter every other read path assumes.
Cross-ref `[[knowledge/idioms/heap-tuple-visibility-mvcc.md]]`,
`[[knowledge/idioms/snapshot-acquisition.md]]`.

### 2. It reaches below the tuple descriptor to resurrect `DROP COLUMN`-ed data

`ALTER TABLE … DROP COLUMN` does not rewrite the heap; it marks the attribute
`attisdropped` in `pg_attribute` and forgets its type. The bytes stay in every
existing tuple. pg_dirtyread lets you name such a column as `dropped_N` (N =
1-based attnum) in the alias and recovers it (`README.md:66-85`)
`[from-README]`. The converter finds the dropped input attribute, runs the only
sanity checks still possible — `attlen`, `attbyval`, `attalign`, `atttypmod`
must match the type you assert — and then **writes the asserted type OID back
into the (in-memory) input descriptor**: `inatt->atttypid = atttypid`
(`dirtyread_tupconvert.c:246-292`, esp. `:284`) `[verified-by-code]`. Core has
no supported path to read a dropped column's value; this one reconstructs a
usable attribute out of the physical layout the descriptor still carries.

### 3. A vendored fork of core's `tupconvert.c` that teaches it about system columns

The tuple converter is a **copy of PostgreSQL 11's `tupconvert.c`**, forked
specifically to "add … support for system columns like xmin/xmax/oid. PostgreSQL
14 refactored it a lot, but the PG 11 version still works, so we stick with it"
(`dirtyread_tupconvert.c:1-6`) `[from-comment]`. This is the recurring
extension-author tax the corpus sees in `[[pg_squeeze]]` and pg_repack (copy a
`static`/awkward-to-extend core routine and let it drift): here the fork adds a
`system_columns[]` table mapping `ctid`/`xmin`/`cmin`/`xmax`/`cmax`/`tableoid`
(and pre-12 `oid`) to their negative `*AttributeNumber` constants
(`dirtyread_tupconvert.c:172-189`) `[verified-by-code]`. At map-build time an
alias name is resolved first against real columns, then against `dropped_N`,
then against this system-column table (`:295-317`). At convert time a negative
attrMap entry is fetched with `heap_getsysattr(tuple, j, indesc, &isnull)`
(`dirtyread_tupconvert.c:373-374`) `[verified-by-code]` — the same accessor core
uses, but exposed to arbitrary SQL callers.

### 4. A synthetic `dead` column computed from the visibility horizon

The fork invents a fake attribute `dead boolean` mapped to
`DeadFakeAttributeNumber`, `#define`d to `FirstLowInvalidHeapAttributeNumber`
(`dirtyread_tupconvert.h:36`, `dirtyread_tupconvert.c:187`) `[verified-by-code]`
— i.e. it squats one slot *below* the lowest real system-attribute number so it
can't collide. When that column is requested, convert time calls
`HeapTupleIsSurelyDead(tuple, oldest_xmin)` and returns the boolean
(`dirtyread_tupconvert.c:364-372`) `[verified-by-code]`, where `oldest_xmin` is
the `GlobalVisState *` / `TransactionId` computed at scan start (the
`OldestXminType` macro straddles the PG 14 API change,
`dirtyread_tupconvert.h:20-24`). Because that horizon needs `GetOldestXmin`,
which "is not available during recovery", requesting `dead` on a standby is a
hard error: `"Cannot use \"dead\" column during recovery"`
(`dirtyread_tupconvert.c:309-314`, `README.md:93-94`) `[verified-by-code]`
`[from-README]`.

### 5. Documented safety caveats it cannot enforce

The divergence carries caveats core never has to state, because core never hands
you a dead tuple: the rows are only recoverable **before VACUUM / HOT-prune /
table rewrite** (`README.md:69-70`) `[from-README]`; there is **no index use**
(always a full seqscan, `pg_dirtyread.c:115-119`) `[verified-by-code]`; and
TOAST-ed values are only recoverable while the corresponding TOAST chunks
likewise survive unvacuumed — the seqscan reads the main heap, and detoasting a
recovered pointer still goes through the normal TOAST path, so a vacuumed TOAST
table defeats recovery of long values `[inferred]`. Cross-ref
`[[knowledge/idioms/toast-storage-strategies.md]]`,
`[[knowledge/idioms/vacuum-two-pass-heap.md]]`.

## Notable design decisions (cited)

- **Name-based column matching with a per-column type check.** The map builder
  matches alias columns to heap columns by name and errors on any type/typmod
  mismatch (`dirtyread_tupconvert.c:224-244`) `[verified-by-code]`, so you can
  project a subset or reorder, but you must state each column's real type.
- **Three-tier name resolution order:** real column → `dropped_N` →
  `system_columns[]`, then a hard "does not exist" error
  (`dirtyread_tupconvert.c:224-325`) `[verified-by-code]`.
- **`dropped_N` type resurrection is validation-only, not coercion.** It refuses
  the request unless `attlen`/`attbyval`/`attalign`/`atttypmod` all match the
  asserted type, because PostgreSQL "deletes the type information of the original
  column" (`README.md:71-74`, `dirtyread_tupconvert.c:265-291`)
  `[from-README]` `[verified-by-code]`.
- **Fast path when descriptors are physically identical.** If the map is
  one-to-one it returns `NULL` and the SRF falls back to
  `heap_copy_tuple_as_datum` with no per-row transposition
  (`dirtyread_tupconvert.c:98-146`, `pg_dirtyread.c:148-149`)
  `[verified-by-code]`.
- **Broad version straddle, 9.2 → current, via inline `#if PG_VERSION_NUM`.**
  `table_open`/`heap_open`, `TableScanDesc`/`HeapScanDesc`,
  `GlobalVisTestFor`/`GetOldestXmin`, and the PG 13 `AttrMap` struct change are
  all handled with inline ifdefs rather than a compat shim
  (`pg_dirtyread.c:39-44,62-66,101-133`, `dirtyread_tupconvert.c:152-159`)
  `[verified-by-code]`.
- **The output descriptor is `BlessTupleDesc`'d** so the anonymous `RECORD`
  result is usable as a composite (`pg_dirtyread.c:112`) `[verified-by-code]`.
- **Superuser-only, no finer grant.** Because the function defeats visibility
  and exposes raw system columns, the sole guard is `superuser()`
  (`pg_dirtyread.c:88-91`) `[verified-by-code]`.

## Links into corpus

- `[[knowledge/idioms/heap-tuple-visibility-mvcc.md]]` — the exact rule
  pg_dirtyread inverts; `SnapshotAny` vs `HeapTupleSatisfiesVisibility`.
- `[[knowledge/idioms/snapshot-acquisition.md]]` /
  `[[knowledge/idioms/snapshot-static-and-current.md]]` — `SnapshotAny` as a
  non-MVCC pseudo-snapshot; the scan takes no registered snapshot.
- `[[knowledge/idioms/heaptuple-update-chain.md]]` — the `xmin`/`xmax`/`ctid`
  columns pg_dirtyread surfaces are exactly the update-chain fields.
- `[[knowledge/idioms/vacuum-two-pass-heap.md]]` — defines the window
  pg_dirtyread lives inside: recovery is only possible until VACUUM reclaims the
  dead tuples.
- `[[knowledge/subsystems/access-heap.md]]` — `heap_beginscan`/`heap_getnext`/
  `heap_getsysattr`/`HeapTupleIsSurelyDead` are all this subsystem's API.
- `[[knowledge/ideologies/pg-safeupdate.md]]` — the prevention/recovery pair:
  pg-safeupdate blocks the unqualified DELETE; pg_dirtyread undoes it afterward.
- `[[knowledge/ideologies/pg_squeeze.md]]` — same "vendor-and-drift a core
  routine" pattern (`tupconvert.c` here, `swap_relation_files` there).
- `.claude/skills/snapshot-management/SKILL.md` — `SnapshotAny` semantics.
- `.claude/skills/toast-storage/SKILL.md` — the TOAST-recovery caveat (§5).
- `.claude/skills/fmgr-and-spi/SKILL.md` — the SRF ValuePerCall skeleton
  (`SRF_IS_FIRSTCALL`/`SRF_RETURN_NEXT`/`SRF_RETURN_DONE`).

## Anthropology takeaway

pg_dirtyread is the corpus's cleanest example of an extension whose entire value
is *removing* a core invariant rather than adding a mechanism. It ships no hook,
no worker, no catalog of its own — just one SRF that swaps the MVCC snapshot for
`SnapshotAny` and a forked `tupconvert.c` that re-teaches tuple conversion about
system and dropped columns. Two reusable patterns for the corpus: (a)
`SnapshotAny` heap scans as a *forensic read primitive* (shared with
`pageinspect`/`pg_visibility`-style tooling) is worth an idiom note; (b) the
`FirstLowInvalidHeapAttributeNumber - 1` "fake system column" trick
(`dirtyread_tupconvert.h:36`) is a neat, citable way to smuggle a computed
column into a name-matched tuple converter.

## Sources

All fetched 2026-07-10, branch `master`, via
`https://raw.githubusercontent.com/df7cb/pg_dirtyread/master/<path>`:

- `README.md` — 200 (156 lines).
- `pg_dirtyread.c` — 200 (164 lines; SRF entry point, SnapshotAny scan, deep-read).
- `dirtyread_tupconvert.c` — 200 (386 lines; forked converter, system/dropped
  columns, `dead` flag — deep-read).
- `dirtyread_tupconvert.h` — 200 (38 lines; `DeadFakeAttributeNumber`,
  `OldestXminType` macros).
- `pg_dirtyread.control` — 200 (5 lines).
- `pg_dirtyread--2.sql` — 200 (4 lines; `pg_dirtyread(regclass) RETURNS SETOF record`).
- `pg_dirtyread--1.0.sql` — 200 (4 lines; identical body, older signature — not
  separately cited).

No 404 gaps. GitHub API is blocked this run, so no tree listing was fetched; the
manifest paths were fetched directly and all resolved. All cites are
`[verified-by-code]` against the fetched `.c`/`.h`/`.control`/`.sql` except the
purpose/caveat narrative and the dropped-column/`dead`-on-standby prose, tagged
`[from-README]`, and the fork rationale, tagged `[from-comment]`. The TOAST
caveat (§5) is `[inferred]` from the seqscan-only design plus the normal
detoast path.
