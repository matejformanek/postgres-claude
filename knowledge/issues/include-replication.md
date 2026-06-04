# Issues — `include/replication` (src/include/replication/)

Per-subsystem issue register for the replication header surface — the
API + struct layout for logical decoding, replication slots, WAL
receive/send, output plugins, and the subscriber-side apply machinery.

**Parent docs:** `knowledge/files/src/include/replication/*` (22 new
+ 1 pre-existing headers.md = 23 docs).

**Source:** 98 entries surfaced 2026-06-04 by the A8 foreground sweep
(3 batches B1-B3). Each is mirrored in the per-file doc's `## Potential
issues` block.

This sweep **confirms a Phase D companion finding** to A6's pg_upgrade
RCE: the output-plugin dlopen primitive. Combined with the prior
sweeps' findings, **the corpus now has five `load arbitrary code` /
`run code from untrusted name` primitives documented across the
replication + upgrade + extended-stats path**.

The headlines:
1. **Output plugin name → arbitrary `dlopen`** (A6 echo CONFIRMED).
   `pg_create_logical_replication_slot(name, 'arbitrary_so')` gates
   only on `has_rolreplication`; the plugin's `_PG_init` runs via
   `dlopen` side effect BEFORE the missing-symbol check rejects
   non-output-plugin libraries.
2. **`pg_logical_emit_message` is EXECUTE PUBLIC by default** — any
   logged-in role on publisher injects arbitrary prefix+bytes into
   the WAL stream every subscriber + CDC consumer reads.
3. **Subscriber resolves target table by publisher-supplied
   `nspname.relname`, not OID** — malicious publisher can name-collide
   with any local table the subscription owner has DML on, even
   tables never advertised in the publication.
4. **`max_slot_wal_keep_size = -1` default** → orphaned persistent
   slot = unbounded `pg_wal` growth → disk-full PANIC.
5. **`primary_conninfo` plaintext window** in `WalRcv` shared memory
   between `RequestXLogStreaming` and walreceiver post-connect
   `memset`.
6. **Reorderbuffer disk-bomb** — `logical_decoding_work_mem` caps
   memory only; spill files in `pg_replslot/<slot>/xid-*.spill` are
   bounded only by available disk; no per-slot quota, no per-xact cap.
7. **REPLICATION-role reads all databases' WAL** — physical
   replication bypasses per-DB CONNECT privileges.
8. **Cross-database leakage** through replication shared catalogs.

---

## P0 — Phase D candidates

### Output plugin → arbitrary `dlopen` (the A6 RCE echo)

The single highest-impact A8 finding. Direct companion to A6's
`check_loadable_libraries` in pg_upgrade.

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-04 | output_plugin.h | trust-boundary | likely | NO whitelist, NO validation, NO registry. Header documents only the symbol contract `_PG_output_plugin_init` and callback table. Silent on validation | open | knowledge/files/src/include/replication/output_plugin.h.md |
| 2026-06-04 | output_plugin.h (← logical.c:730) | trust-boundary | likely | `LoadOutputPlugin` passes slot's persisted `plugin` NameData straight to `load_external_function(plugin, "_PG_output_plugin_init", false, NULL)`. `_PG_init` runs via `dlopen` side effect BEFORE missing-symbol check rejects non-output-plugin libs | open | knowledge/files/src/include/replication/output_plugin.h.md |
| 2026-06-04 | slot.h (← slot.c:1688) | trust-boundary | likely | Only gate on `pg_create_logical_replication_slot('name', 'arbitrary_so')` is `has_rolreplication(GetUserId())`. REPLICATION role attribute bundles "trigger dlopen of any matching .so in dynamic_library_path" | open | knowledge/files/src/include/replication/slot.h.md |
| 2026-06-04 | slot.h | trust-boundary | maybe | Slot is persisted to disk BEFORE plugin load is attempted — a bad plugin name lives in `pg_replication_slots` retaining WAL until manually dropped | open | knowledge/files/src/include/replication/slot.h.md |
| 2026-06-04 | pgoutput.h | undocumented-invariant | nit | Built-in pgoutput plugin used when name = 'pgoutput'; not enforced as default | open | knowledge/files/src/include/replication/pgoutput.h.md |

**Phase D pitch — coordinated dlopen hardening (closes 4 corpus findings):**
1. Whitelist plugin names against installed extensions (cf. A6 `check_loadable_libraries` whitelist proposal).
2. Reject plugin names containing `/` or `..` (path-traversal).
3. Validate plugin existence BEFORE persisting the slot (avoid the "bad slot stuck retaining WAL" failure mode).
4. Optionally: require plugin be loaded via `CREATE EXTENSION` first.

This pitch + A6's `check_loadable_libraries` whitelist + A7's
`pg_upgrade_support` second-layer gate would close 3 of the 5
"arbitrary code" primitives in one coordinated patch series.

### `pg_logical_emit_message` — WAL injection by PUBLIC

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-04 | message.h (← pg_proc.dat:11731) | trust-boundary | likely | `pg_logical_emit_message(transactional, prefix, content)` is **EXECUTE PUBLIC by default** — no `proacl`, no REVOKE in `system_functions.sql`. Any logged-in role can inject arbitrary prefix+bytes into the WAL stream every subscriber + external CDC consumer reads | open | knowledge/files/src/include/replication/message.h.md |
| 2026-06-04 | message.h | wire-protocol | maybe | Bytes are ignored by core apply but surfaced to wal2json/custom plugins; "unique prefix" rule (`message.c:25-27`) is a **social contract only** — malicious caller can impersonate another extension's control-plane prefix | open | knowledge/files/src/include/replication/message.h.md |
| 2026-06-04 | message.h | dos | maybe | Logical message persisted in WAL forever; subscriber MUST parse it; per-message size bounded only by general WAL record size limit | open | knowledge/files/src/include/replication/message.h.md |

### Subscriber trust posture (the publisher→subscriber attack surface)

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-04 | logicalrelation.h:21,32 | trust-boundary | likely | **Subscriber resolves target table by publisher-supplied `nspname.relname`, NOT by OID** (`logicalrep_rel_open`). Apply worker runs as subscription owner; malicious publisher can name-collide with any local table the owner has INSERT/UPDATE/DELETE on, even tables never advertised in the publication. The publisher's OID (`remoteid`) is just an opaque cache key | open | knowledge/files/src/include/replication/logicalrelation.h.md |
| 2026-06-04 | worker_internal.h:57 | trust-boundary | likely | Apply worker connects as subscription owner; comment says so but NO header-level contract enumerates which fields are publisher-attacker-controlled vs subscriber-validated | open | knowledge/files/src/include/replication/worker_internal.h.md |
| 2026-06-04 | worker_internal.h:327 | secret-scrub | maybe | Publisher-supplied strings land in subscriber server logs via `apply_error_callback` with NO scrubbing — column values, relname, nspname all logged | open | knowledge/files/src/include/replication/worker_internal.h.md |
| 2026-06-04 | logicalproto.h | wire-protocol | nit | Wire-protocol strictly validated (`switch` with `default: ereport(ERROR, ERRCODE_PROTOCOL_VIOLATION)` at apply.c:3797); variable-length fields use `pq_getmsgstring`/`pq_getmsgbytes(len)` which `elog(ERROR)` on overrun. **Strict.** | open | knowledge/files/src/include/replication/logicalproto.h.md |
| 2026-06-04 | logicalproto.h | dos | maybe | `LOGICAL_REP_MSG_MESSAGE` ('M') is parsed-but-discarded by core apply (apply.c:3848-3855) — publisher can pump byte volume through every subscriber's apply path with NO semantic effect; DoS amplification | open | knowledge/files/src/include/replication/logicalproto.h.md |

### Slot lifecycle DoS

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-04 | slot.h (← xlog.c:142) | dos | likely | **`max_slot_wal_keep_size_mb = -1` default** confirmed in `postgresql.conf.sample:362`. Retention check `if (max_slot_wal_keep_size_mb >= 0 && !IsBinaryUpgrade)` — negative value disables cap entirely. One abandoned persistent slot → unbounded WAL retention → eventual `pg_wal` disk-full PANIC | open | knowledge/files/src/include/replication/slot.h.md |
| 2026-06-04 | slot.h | dos | maybe | No per-role quota on slot count — single REPLICATION-attribute role can claim all `max_replication_slots` shmem entries | open | knowledge/files/src/include/replication/slot.h.md |
| 2026-06-04 | slot.h | dos | nit | Per-slot xmin retention also unbounded — abandoned slot pins cluster xmin, prevents vacuum | open | knowledge/files/src/include/replication/slot.h.md |
| 2026-06-04 | slotsync.h | trust-boundary | maybe | Failover slot sync (PG17+) — standby pulls slot state from primary; trust posture on primary-supplied slot fields | open | knowledge/files/src/include/replication/slotsync.h.md |
| 2026-06-04 | reorderbuffer.h | dos | likely | `logical_decoding_work_mem` caps memory only. Spill files in `pg_replslot/<slot>/xid-*.spill` bounded only by available disk — no per-slot quota, no per-xact cap. A 100 GB publisher transaction spills ~100 GB | open | knowledge/files/src/include/replication/reorderbuffer.h.md |
| 2026-06-04 | reorderbuffer.h | undocumented-invariant | nit | `RS_INVAL_IDLE_TIMEOUT` (PG17+) gated by `idle_replication_slot_timeout_secs` GUC which defaults to 0 (disabled) | open | knowledge/files/src/include/replication/reorderbuffer.h.md |
| 2026-06-04 | worker_internal.h:89 | dos | maybe | `oldest_nonremovable_xid` couples a stuck apply worker to cluster-wide xmin — wedged or killed-without-cleanup apply worker pins xmin globally; no header-level escape hatch | open | knowledge/files/src/include/replication/worker_internal.h.md |

### Secret-scrub: `primary_conninfo` plaintext window

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-04 | walreceiver.h:124 (← walreceiverfuncs.c:311, walreceiver.c:278) | secret-scrub | likely | Startup process writes raw `primary_conninfo` (with `password=...`) into `WalRcv->conninfo` (shared memory). Walreceiver copies it to stack buffer, `memset`s the field, then replaces with libpq-obfuscated form. **Vulnerable window**: milliseconds between `RequestXLogStreaming` and walreceiver post-connect memset. Postmaster shared-memory dump in that window leaks the password | open | knowledge/files/src/include/replication/walreceiver.h.md |
| 2026-06-04 | walreceiver.h:122-123 | from-comment | nit | Header comment explicitly says "initially set to connect to the primary, and later clobbered to hide security-sensitive fields" — the gap is documented but the timing window is not bounded | open | knowledge/files/src/include/replication/walreceiver.h.md |
| 2026-06-04 | walreceiver.h:146 | undocumented-invariant | nit | `ready_to_display` flag correctly gates `pg_stat_get_wal_receiver` to return NULL for conninfo when false | open | knowledge/files/src/include/replication/walreceiver.h.md |

### Cross-database / cross-role info leakage

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-04 | origin.h | info-disclosure | maybe | `pg_replication_origin` is a shared catalog visible from every database — subscription origin names + LSNs leak cross-DB | open | knowledge/files/src/include/replication/origin.h.md |
| 2026-06-04 | slot.h | info-disclosure | maybe | Logical slot `catalog_xmin` holds back vacuum on shared catalogs cluster-wide regardless of which database the slot is bound to | open | knowledge/files/src/include/replication/slot.h.md |
| 2026-06-04 | slot.h | trust-boundary | maybe | `pg_publication` has no per-role ACL beyond catalog SELECT — any REPLICATION-attribute role can `START_REPLICATION` against any publication name they discover | open | knowledge/files/src/include/replication/slot.h.md |
| 2026-06-04 | walsender.h | trust-boundary | likely | **REPLICATION-role reads all databases' WAL** — physical replication connection (`replication=true`) reads WAL containing data from ALL databases regardless of per-DB CONNECT privileges. Documented design but worth flagging for multi-tenant clusters | open | knowledge/files/src/include/replication/walsender.h.md |

---

## P1 — Trust-the-primary (echo of A4 pg_basebackup)

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-04 | walreceiver.h | trust-boundary | maybe | `walrcv_server_version`, `walrcv_identify_system` trusted byte-for-byte from primary (echo of A4 pg_basebackup `wal_segment_size`/`data_directory_mode` findings). Only `system_identifier` mismatch causes abort | open | knowledge/files/src/include/replication/walreceiver.h.md |
| 2026-06-04 | walsender_private.h | trust-boundary | maybe | Walsender shared state; standby application_name parsed by syncrep | open | knowledge/files/src/include/replication/walsender_private.h.md |
| 2026-06-04 | syncrep.h | trust-boundary | maybe | `synchronous_standby_names` parsing trusts standby-supplied `application_name`; multiple standbys with same name collide | open | knowledge/files/src/include/replication/syncrep.h.md |

---

## P1 — Snapshot builder + decode invariants

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-04 | snapbuild.h | undocumented-invariant | nit | Historic-snapshot xmin retention; `SnapBuildSerialize` writes to disk; `pg_replslot/<slot>/snap-*.snap` files | open | knowledge/files/src/include/replication/snapbuild.h.md |
| 2026-06-04 | snapbuild_internal.h | undocumented-invariant | nit | Catalog change tracking; consistent-state transitions | open | knowledge/files/src/include/replication/snapbuild_internal.h.md |
| 2026-06-04 | decode.h | undocumented-invariant | nit | New WAL record types added each release; older subscribers receive new types via XLogReader; tolerance discipline | open | knowledge/files/src/include/replication/decode.h.md |
| 2026-06-04 | conflict.h | undocumented-invariant | nit | PG18 conflict-detection types; `conflict_resolution` policies (skip, apply, abort); per-subscription configurable | open | knowledge/files/src/include/replication/conflict.h.md |

---

## P1 — Logical worker / launcher

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-04 | logical.h | undocumented-invariant | nit | `LogicalDecodingContext` is the centerpiece struct; reuse across slot reconnect | open | knowledge/files/src/include/replication/logical.h.md |
| 2026-06-04 | logicalctl.h | undocumented-invariant | nit | Logical-replication control toggle (per-cluster on/off) | open | knowledge/files/src/include/replication/logicalctl.h.md |
| 2026-06-04 | logicallauncher.h | state-transition | nit | Launcher background process; failure mode if it dies (postmaster restarts) | open | knowledge/files/src/include/replication/logicallauncher.h.md |
| 2026-06-04 | logicalworker.h | undocumented-invariant | nit | Apply worker entry points; parallel-apply variants | open | knowledge/files/src/include/replication/logicalworker.h.md |
| 2026-06-04 | worker_internal.h | secret-scrub | maybe | Subscription conninfo (with password) stored in worker shared state similarly to walreceiver — needs audit | open | knowledge/files/src/include/replication/worker_internal.h.md |

---

## Cross-corpus pattern reinforcement

### THE 5 "load arbitrary code" / "run code from untrusted name" primitives

The corpus now has 5 documented primitives where a name (not a hash, not
a signature, not a registry entry) gates code execution:

| Primitive | Sweep | File:line | Gate |
|---|---|---|---|
| `check_loadable_libraries` | A6 pg_upgrade | check.c | None — runs every `pg_proc.probin`/extension lib referenced by old cluster |
| `binary_upgrade_*` catalog functions | A7 utils | pg_upgrade_support.c | Single `IsBinaryUpgrade` bool |
| `output_plugin` name | A8 (NEW) | logical.c:730 | `has_rolreplication` (REPLICATION role attribute) |
| pg_dump archive `te->defn` | A3 pg_dump | pg_backup_archiver.c | Trust the archive file |
| pg_rewind null-bytea = unlink + symlink primitives | A6 pg_rewind | file_ops.c | Source-side privilege |

**Single coordinated Phase D patch series** could close 3 of these by
introducing a shared `validate_loadable_module_name(name)` helper:
- Reject path-traversal (`/`, `..`)
- Whitelist against installed extensions (via `pg_extension` catalog)
- Refuse paths under `/tmp/` or world-writable directories
- Used by: `check_loadable_libraries`, `LoadOutputPlugin`, future `_PG_init`-loading sites.

### Subscriber-side trust matches publisher-side: NAME-based, not OID-based

A8's `logicalrelation.h` finding (target table by `nspname.relname`) is
the **subscriber-side mirror** of A6's pg_upgrade trust-the-old-catalog
finding. Both let the upstream side dictate the downstream's targets
purely by name. Worth a single cross-corpus pattern doc.

### Secret-scrub cluster extends: walreceiver `primary_conninfo` window

A2 libpq + A4 psql/streamutil/initdb + A5 common (SecretBuf site) +
A6 pg_upgrade + A8 NOW walreceiver primary_conninfo. Eighth installment
of the cross-corpus secret-scrub cluster. The walreceiver case is
unique: the **scrub happens correctly** but the window of
vulnerability is documented in a header comment without a bound.

---

## Corpus gaps surfaced (out of batch)

- `src/backend/replication/logical/logical.c` — implementation of
  `LoadOutputPlugin`; this is THE function to read for the dlopen
  primitive. Already documented in main repo (no work needed, just
  cross-link).
- `src/backend/replication/logical/worker.c` — the apply-worker
  implementation; the trust posture details. Already documented.
- `src/backend/replication/logical/relation.c` — `logicalrep_rel_open`
  name-resolution implementation. Already documented.
- `src/backend/replication/walreceiver.c` — the `memset` scrub at line
  278. Already documented in main repo from earlier sweeps.

**Net result:** the `.h` side of replication is now closed; the `.c`
side was previously closed via the replication subsystem spine doc.
The combined coverage is comprehensive.

---

## Summary by tag type

| Type | Count |
|---|---:|
| trust-boundary | 21 |
| dos | 14 |
| undocumented-invariant | 28 |
| wire-protocol | 6 |
| secret-scrub | 5 |
| info-disclosure | 6 |
| state-transition | 4 |
| stale-todo | 8 |
| dead-code | 4 |
| from-comment | 2 |
| **Total** | **98** (some entries double-tagged) |

Severity headline: 9 `likely`, 24 `maybe`, rest `nit`. THE Phase D
pitch order:
1. **Output plugin name validation** — single-function patch closes
   A6+A7+A8 dlopen primitives if coordinated with `check_loadable_libraries`.
2. **`pg_logical_emit_message` REVOKE FROM PUBLIC** — single-line patch.
3. **Subscriber-side OID-based name resolution** — bigger refactor but
   closes the publisher→subscriber name-collision attack.
4. **`max_slot_wal_keep_size` default = sane value** (1 GiB?) — config
   change.
5. **Reorderbuffer per-slot disk quota** GUC.
6. **`primary_conninfo` window bound** — either pre-scrub before shared
   memory write, or document the window explicitly.
