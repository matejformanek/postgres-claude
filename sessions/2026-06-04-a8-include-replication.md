# 2026-06-04 — A8 include/replication sweep (foreground sweep #8)

**Type:** interactive (worktree `ft_corpus_a8_include_replication`).
**Outcome:** 22 new per-file docs across `src/include/replication/` —
closing the gap exposed by the replication subsystem spine doc.
**98 issues consolidated into `knowledge/issues/include-replication.md`**.

**THE headline:** the **output-plugin `dlopen` primitive is
CONFIRMED** as a Phase D companion to A6's `check_loadable_libraries`
RCE. `pg_create_logical_replication_slot('name', 'arbitrary_so')`
gates only on `has_rolreplication`; the plugin's `_PG_init` runs via
`dlopen` side effect BEFORE the missing-symbol check rejects
non-output-plugin libraries. This is the **FIFTH "load arbitrary code
from untrusted name" primitive** in the corpus.

## Why this sweep

Phase A foreground sweep #8 per `progress/coverage-gaps.md`. The
src/include/replication subdir was at 4.5% (1/22) — a surprising gap
because the .c bodies under src/backend/replication/ were over 100%
covered. The trust posture of replication is encoded in these
headers; closing the gap completes the cross-corpus replication
picture and was the right place to verify A6's pg_upgrade
`output_plugin name carried verbatim` finding has a server-side
companion.

## What landed

### New files (24 total)

| Path | Count | Role |
|---|---|---|
| `knowledge/files/src/include/replication/*.md` | 22 | All previously-missing replication headers |
| `knowledge/issues/include-replication.md` | 1 | 98-entry register grouped by Phase D pattern |
| `sessions/2026-06-04-a8-include-replication.md` | 1 | This log |

### Modified files

| Path | Change |
|---|---|
| `progress/files-examined.md` | +22 rows (source slug `include-replication-a8`) |
| `progress/coverage.md` | 1 385 → 1 407 docs; src/include 51.1% → 53.7%; total 54.0% → **54.9%** |
| `progress/coverage-gaps.md` | A8 marked done; replication subdir 4.5% → 104.5%; #9 (`src/pl/plpgsql/`) unchanged |
| `progress/STATE.md` | Last-activity bumped; Phase A work queue 1-8 done, 9-11 queued |

## How it was done — 3 parallel agents

| Batch | Theme | Files | Issues | Wall time |
|---|---|---:|---:|---:|
| B1 | logical replication core (logical, logicalctl, logicallauncher, logicalproto, logicalrelation, logicalworker, message, worker_internal) | 8 | 37 | ~6 min |
| B2 | slots + snapshots + sync + output_plugin (slot, slotsync, snapbuild + internal, syncrep, origin, output_plugin, pgoutput) | 8 | 38 | ~6 min |
| B3 | WAL receive/send + decode + conflict + reorderbuffer (walreceiver, walsender + private, decode, conflict, reorderbuffer) | 6 | 23 | ~6 min |
| **Total** | | **22** | **98** | ~6 min wall (parallel max) |

**Zero misdirection.** Eight successive sweeps with the explicit
"RELATIVE paths" instruction = zero relocation incidents.

## What the sweep surfaced

### Headline 1: Output-plugin dlopen primitive (THE A6 echo)

`output_plugin.h` documents only the symbol contract
`_PG_output_plugin_init` and the callback table. The header is silent
on validation. The backend implementation in `logical.c:726-744` does
exactly two checks:

1. `load_external_function(plugin, "_PG_output_plugin_init", false, NULL)`
   returns non-NULL — else `elog(ERROR, "output plugins have to declare
   the _PG_output_plugin_init symbol")`. **By that point `dlopen` has
   already succeeded and any `_PG_init` side-effects have run.**
2. After `plugin_init(callbacks)`, core verifies `begin_cb`,
   `change_cb`, `commit_cb` are non-NULL.

What gates `pg_create_logical_replication_slot('name', 'arbitrary_so')`
from `dlopen`'ing an arbitrary `.so`: **only**
`has_rolreplication(GetUserId())` at slot creation
(`slot.c:1688-1696`). The REPLICATION role attribute bundles
"trigger dlopen of any matching .so in `dynamic_library_path`".

Plus: the slot is **persisted to disk BEFORE plugin load is
attempted**, so a bad plugin name lives in `pg_replication_slots`
retaining WAL until manually dropped.

**Closure:** whitelist plugin names against installed extensions;
reject paths with `/` or `..`; validate plugin existence BEFORE
persisting the slot.

### Headline 2: pg_logical_emit_message is EXECUTE PUBLIC

`pg_proc.dat:11731-11740` ships no `proacl`, and `system_functions.sql`
has no REVOKE. Any logged-in role on the publisher can inject
arbitrary `prefix + bytes` into the WAL stream that every subscriber
and every external CDC consumer reads.

Bytes are ignored by core apply but surfaced to wal2json/custom
plugins. The "unique prefix" rule documented in `message.c:25-27` is
a **social contract only** — a malicious caller can impersonate
another extension's control-plane prefix.

**Closure:** `REVOKE EXECUTE ON FUNCTION pg_logical_emit_message FROM PUBLIC`.

### Headline 3: Subscriber-trusts-publisher name resolution

`logicalrelation.h:21,32` + the `logicalrep_rel_open` implementation
in `relation.c`: subscriber resolves target table by publisher-
supplied `nspname.relname`, NOT by OID. The publisher's OID
(`remoteid`, `logicalproto.h:107`) is just an opaque cache key.

Apply worker runs as the subscription owner (`worker_internal.h:58`).
A malicious or compromised publisher can name-collide with **any
local table the subscription owner has INSERT/UPDATE/DELETE on**,
even tables never advertised in the publication.

This mirrors A6's pg_upgrade trust-the-old-catalog finding on the
subscriber side. **NAME-based not OID-based** is now the corpus-wide
upstream-controls-downstream pattern.

### Headline 4: max_slot_wal_keep_size = -1 default

`xlog.c:142` ships `max_slot_wal_keep_size_mb = -1`. Confirmed in
`postgresql.conf.sample:362`. Retention check
`if (max_slot_wal_keep_size_mb >= 0 && !IsBinaryUpgrade)` — negative
value disables the cap entirely.

One abandoned persistent slot → unbounded WAL retention →
eventual `pg_wal` disk-full PANIC. No per-role slot-count quota
either: a single REPLICATION-attribute role can claim all
`max_replication_slots` shmem entries.

The only protective bound is `RS_INVAL_IDLE_TIMEOUT` (PG17+) gated
by `idle_replication_slot_timeout_secs` — also defaults to 0
(disabled).

### Headline 5: primary_conninfo plaintext window in WalRcv

`WalRcv->conninfo[MAXCONNINFO]` (`walreceiver.h:124`). Startup process
writes the RAW conninfo via `RequestXLogStreaming`
(`walreceiverfuncs.c:311`). Walreceiver copies it into a stack buffer,
runs `memset(walrcv->conninfo, 0, MAXCONNINFO)` at `walreceiver.c:278`,
then repopulates with the libpq-obfuscated form.

**Vulnerable window:** milliseconds between `RequestXLogStreaming` and
walreceiver's post-connect `memset`. A postmaster shared-memory dump
during that window leaks the password.

The `ready_to_display` flag gates `pg_stat_wal_receiver` correctly
(`walreceiver.c:1489`). The scrub on shutdown is also correct
(`walreceiver.c:825`). The gap is purely the brief plaintext window.

**Closure:** pre-scrub before shared memory write, or document the
window explicitly with an upper bound.

### Headline 6: Reorderbuffer disk-bomb

`reorderbuffer.h` declares `logical_decoding_work_mem` (memory cap)
at line 27. Once that limit is reached, the biggest xact (by
`total_size`, tracked in `txn_heap` pairing heap at line 675) is
spilled to disk.

**No per-transaction size cap. No per-slot disk-space quota.** Spill
statistics (`spillTxns`/`spillCount`/`spillBytes`, lines 684-686) are
observability-only. Bounded externally by disk space and (indirectly)
`max_slot_wal_keep_size` for WAL retention.

A single huge publisher transaction WILL spill its full size to
`pg_replslot/<slot>/`. A 100 GB transaction spills ~100 GB.

**Closure:** add `max_slot_spill_size` GUC.

### Headline 7: REPLICATION-role reads all databases' WAL

A walsender connection with `replication=true` (physical) reads WAL
containing data from ALL databases regardless of per-DB CONNECT
privileges. Documented design choice but worth flagging for
multi-tenant clusters.

`pg_replication_origin` is a shared catalog visible from every
database — subscription origin names + LSNs leak cross-DB. Logical
slot `catalog_xmin` holds back vacuum on shared catalogs cluster-wide
regardless of which database the slot is bound to.

### What's working well (record)

- **Wire-protocol strictly validated**: `apply_dispatch`
  (`worker.c:3797`) reads the message-type byte via `pq_getmsgbyte`
  and runs a `switch`; `default:` arm raises
  `ereport(ERROR, ERRCODE_PROTOCOL_VIOLATION, "invalid logical
  replication message type \"??? (%d)\"")`. Unknown bytes kill the
  apply worker.
- **`walrcv_get_conninfo()`** correctly obfuscates passwords for
  `pg_stat_wal_receiver` display via the `ready_to_display` gate.
- **Subscription drop** properly resets `ready_to_display=false`
  (`walreceiver.c:825`) — no plaintext leak at shutdown.

### Cross-corpus pattern reinforcement

#### The FIVE "load arbitrary code" primitives

The corpus now documents 5 different ways an upstream-controlled
NAME (not hash, not signature, not registry) gates code execution:

| Primitive | Sweep | File:line | Gate |
|---|---|---|---|
| `check_loadable_libraries` | A6 pg_upgrade | check.c | None |
| `binary_upgrade_*` catalog functions | A7 utils | pg_upgrade_support.c | Single `IsBinaryUpgrade` bool |
| **`output_plugin` name** | **A8 (NEW)** | **logical.c:730** | **`has_rolreplication`** |
| pg_dump archive `te->defn` | A3 pg_dump | pg_backup_archiver.c | Trust the archive file |
| pg_rewind null-bytea/symlink primitives | A6 pg_rewind | file_ops.c | Source-side privilege |

**Single coordinated Phase D pitch** could close 3 of these by
introducing a shared `validate_loadable_module_name(name)` helper in
`src/include/common/`:
- Reject path-traversal (`/`, `..`)
- Whitelist against installed extensions (via `pg_extension` catalog)
- Refuse paths under `/tmp/` or world-writable directories
- Used by: `check_loadable_libraries`, `LoadOutputPlugin`, future
  `_PG_init`-loading sites.

#### Subscriber-side trust mirrors publisher-side: NAME, not OID

A8's `logicalrelation.h` finding (target table by `nspname.relname`)
is the **subscriber-side mirror** of A6's pg_upgrade
trust-the-old-catalog finding (relname/spclocation consumed
unchecked). Both let the upstream side dictate the downstream's
targets purely by name. **NAME-based not OID-based** is now the
corpus-wide pattern.

#### Eighth installment of the secret-scrub cluster

A2 libpq + A4 psql/streamutil/initdb + A5 common (SecretBuf site) +
A6 pg_upgrade + A8 walreceiver `primary_conninfo` window. The
walreceiver case is unique: the **scrub happens correctly** but the
window of vulnerability is documented in a header comment without a
bound.

## Overnight cloud cycle digest

9 routines fired cleanly under bumped budgets:

| Routine | Output |
|---|---|
| `pg-community-pulse` | hackers 5 · CF 59 ba… (back from SILENT) |
| `pg-file-backfiller` | 17 files in src/backend/utils/adt scalar types (**overlapped with A7**, resolved on rebase) |
| `pg-corpus-maintainer` | backlinks 30 · glossary +56 · issues +15 |
| `pg-upstream-watcher` | 12 commits, 5 buildfarm failures (back from SILENT) |
| `pg-user-question-harvester` | 22 questions for 2026-06-04 |
| `pg-quality-auditor` | fixed 2 stale cites in arch docs |
| `pg-docs-miner` | 3 wiki + 6 docs distilled (WAL, AMs, parallel, GIN/BRIN, bgworker) |
| `pg-extension-anthropologist` | 4 extensions (pgvector, hypopg, pgaudit, pg_partman) |
| `pg-evening-merger` | rewrote queue placeholders to merge SHAs |

**Cloud + A7 overlap resolution:** pg-file-backfiller and my A7 sweep
both wrote 17 of the same scalar-type files. Resolved by rebasing A7
on main and keeping A7 versions (deeper Phase D analysis +
cross-references), while merging cloud's files-examined rows
alongside A7's. Both rows are preserved in the registry, showing
that two sweeps independently visited the same file.

## What this commit explicitly does NOT do

- No subsystem doc update. `knowledge/subsystems/replication.md` is
  already comprehensive; the new `.h` docs cross-link to it from
  individual headers but don't restructure it.
- No upstream patches for any of the 98 issues. Corpus side done;
  Phase D work.
- No changes to `dev/` or other knowledge/ trees.

## Followup candidates surfaced

- **Phase D — output_plugin name validation** (single-function patch
  in `LoadOutputPlugin`).
- **Phase D — `pg_logical_emit_message` REVOKE FROM PUBLIC**
  (single-line patch).
- **Phase D — subscriber-side OID-based name resolution** (bigger
  refactor; closes the publisher→subscriber name-collision attack).
- **Phase D — `max_slot_wal_keep_size` sane default** (1 GiB?
  config-only change).
- **Phase D — Reorderbuffer per-slot disk quota GUC**.
- **Phase D — `primary_conninfo` window bound** (pre-scrub).
- **Phase D — Shared `validate_loadable_module_name` helper** —
  closes 3 corpus-wide "load arbitrary code" primitives.
- **`knowledge/idioms/upstream-controls-downstream-by-name.md`** —
  document the corpus-wide pattern from A3 + A6 + A7 + A8.
- **Foreground sweep #9** — `src/pl/plpgsql/` (16 files; privileged
  sandbox boundary).

## Repository state after this commit

- 22 new files in `knowledge/files/src/include/replication/`.
- 1 new file `knowledge/issues/include-replication.md` (98 entries).
- 1 session log.
- 4 progress files updated.

Total: ~28 files changed, ~2 500 lines added.

## Commit message for this work

```
ft(corpus): document 22 include/replication headers (A8 sweep) + 98 issues

Eighth foreground sweep of Phase A: cover every .h under
src/include/replication/ via 3 parallel general-purpose agents. Wall
time ~6 min; 22 per-file docs landed; 98 [ISSUE-*] tags consolidated
into knowledge/issues/include-replication.md grouped by Phase D
pattern.

Coverage bumps: 1 385 -> 1 407 docs (54.0% -> 54.9%); src/include
51.1% -> 53.7%; replication subdir 4.5% -> 104.5%.

THE PHASE D HEADLINE: output-plugin dlopen primitive CONFIRMED as the
A6 companion. pg_create_logical_replication_slot('name',
'arbitrary_so') gates only on has_rolreplication; the plugin's
_PG_init runs via dlopen side effect BEFORE the missing-symbol check
rejects non-output-plugin libraries. NO whitelist, NO validation, NO
registry. This is the FIFTH "load arbitrary code from untrusted name"
primitive in the corpus, joining:
- A6 pg_upgrade check_loadable_libraries (no gate)
- A7 utils pg_upgrade_support (IsBinaryUpgrade bool gate)
- A3 pg_dump archive te->defn (trust the file)
- A6 pg_rewind null-bytea / symlink primitives (source-side privilege)
- A8 output_plugin dlopen (has_rolreplication)

Single coordinated patch series could close 3 of these by introducing
a shared validate_loadable_module_name(name) helper in
src/include/common/ that rejects /, .., /tmp/, world-writable paths
and whitelists against pg_extension.

Six other headlines:

1. pg_logical_emit_message is EXECUTE PUBLIC by default
   (pg_proc.dat:11731, no proacl). Any logged-in role on the
   publisher injects arbitrary prefix+bytes into the WAL stream
   every subscriber + CDC consumer reads. "Unique prefix" rule is
   social contract only.

2. Subscriber resolves target table by publisher-supplied
   nspname.relname, NOT by OID (logicalrelation.h:21,32;
   logicalrep_rel_open). Malicious publisher name-collides with any
   local table subscription owner has DML on, even tables never
   advertised in publication. Mirror of A6 pg_upgrade trust-the-
   old-catalog finding on the subscriber side.

3. max_slot_wal_keep_size = -1 default (xlog.c:142,
   postgresql.conf.sample:362). One abandoned persistent slot ->
   unbounded WAL retention -> pg_wal disk-full PANIC.

4. primary_conninfo plaintext window in WalRcv->conninfo shared
   memory. Startup writes raw conninfo via RequestXLogStreaming
   (walreceiverfuncs.c:311); walreceiver scrubs at walreceiver.c:278.
   Window: milliseconds between RequestXLogStreaming and post-connect
   memset. Eighth installment of the cross-corpus secret-scrub
   cluster.

5. Reorderbuffer disk-bomb. logical_decoding_work_mem caps memory
   only. Spill files in pg_replslot/<slot>/xid-*.spill bounded only
   by available disk; no per-slot quota, no per-xact cap. 100 GB
   transaction spills 100 GB.

6. REPLICATION-role reads all databases' WAL bypassing per-DB CONNECT.
   Cross-DB info leak via pg_replication_origin shared catalog,
   logical slot catalog_xmin pins shared-catalog vacuum cluster-wide.

What's working: wire-protocol strictly validated (logicalproto.h
switch with default: ereport(ERROR, ERRCODE_PROTOCOL_VIOLATION));
walrcv_get_conninfo() correctly obfuscates passwords for
pg_stat_wal_receiver via ready_to_display gate; subscription drop
properly resets ready_to_display=false.

Cross-corpus reinforcement: NAME-based not OID-based is now the
corpus-wide upstream-controls-downstream pattern (A3 + A6 + A7 + A8).
A single knowledge/idioms/ doc could synthesize this.

All 3 agents wrote to correct worktree paths (zero misdirection;
8 successive sweeps with explicit RELATIVE-paths guidance = 0
relocation incidents).

Session: sessions/2026-06-04-a8-include-replication.md
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```
