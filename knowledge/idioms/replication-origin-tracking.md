# Replication origin tracking — replorigin progress + loop prevention

A **replication origin** is a named source for incoming
WAL changes — a way for a subscriber's apply worker to record
"these changes came from publisher X" and to track its applied
progress (`replorigin_session_origin_lsn`). The mechanism
serves two purposes: durable progress tracking (so an apply
worker can resume from the right LSN after a crash) and **loop
prevention** in bi-directional logical replication (output
plugin's `filter_by_origin_cb` can skip changes that originated
from the same node).

Anchors:
- `source/src/backend/replication/logical/origin.c:928` —
  replorigin_advance [verified-by-code]
- `source/src/backend/replication/logical/origin.c:1329-1332` —
  session-local advance commentary [verified-by-code]
- `source/src/backend/replication/logical/origin.c:1603` —
  replorigin_advance use in WAL replay [verified-by-code]
- `knowledge/idioms/output-plugin-callbacks.md` — companion
  (filter_by_origin_cb)
- `knowledge/idioms/logical-decoding-snapshot.md` — companion
- `.claude/skills/replication-overview/SKILL.md` — companion

## The origin concept

An origin is a **named identity** registered in
`pg_replication_origin`:
- `roident` — small integer id (uint16; ≤ 65k origins).
- `roname` — string name (e.g., 'pg_16385' for a SUBSCRIPTION).

The apply worker associates itself with an origin via
`replorigin_session_setup(origin)`. Subsequent transactions
applied by this worker are tagged with `origin_id`, recorded in
the commit WAL record.

## Two state surfaces

1. **Shmem origin state** — one slot per active origin, fast
   lookup, progress tracking.
2. **On-disk origin state** — checkpointed to
   `pg_logical/replorigin_checkpoint`, durable.

The shmem state is the operational copy; the on-disk state
exists for crash recovery.

## replorigin_advance — the progress update

[verified-by-code `origin.c:928`]

```c
void
replorigin_advance(RepOriginId node,
                   XLogRecPtr remote_commit,
                   XLogRecPtr local_lsn,
                   bool go_backward,
                   bool wal_log);
```

Advances the recorded progress for `node`:
- `remote_commit` — the upstream LSN this xact came from.
- `local_lsn` — the local LSN where the xact's commit is
  written.

After this call, "we've applied upstream LSN ≤ remote_commit;
locally that's at local_lsn".

If the apply worker crashes, it can resume by reading
`replorigin_session_origin_lsn`, requesting the publisher to
start streaming from there.

## Session-local advance (cheaper)

[verified-by-code `origin.c:1329-1332`]

> Do the same work replorigin_advance() does, just on the
> session's own slot.
>
> This is noticeably cheaper than using replorigin_advance().

When the apply worker has bound an origin to its session via
`replorigin_session_setup`, it can call
`replorigin_session_advance` for its OWN origin — bypassing
the global lookup. The per-xact apply path uses this for hot-
path efficiency.

## The commit-WAL record tagging

[from-code `xact.c` + `origin.c`]

When the apply worker commits a replicated transaction, the
commit WAL record carries an `origin_id` field. Downstream
decoders see this field via:
- `ReorderBufferChange.origin_id`
- `commit_cb`'s txn->origin_id.

This is what enables `filter_by_origin_cb`:

```c
static bool
my_filter_origin(LogicalDecodingContext *ctx, RepOriginId origin_id)
{
    /* skip changes that came from us */
    return (origin_id == my_subscription_origin);
}
```

The decoder calls `filter_by_origin_cb` early in transaction
processing; if it returns true, the entire txn is discarded.

## Loop prevention in bidirectional logical-rep

```
[node A] --pub--> [node B] --pub--> [node A]
```

Without loop prevention: A publishes to B; B applies and re-
publishes back to A; A applies (creating a duplicate row); ...

With origin tracking:
1. A's apply worker tags its replicated xacts with origin
   "from_B".
2. B publishes; its output plugin's `filter_by_origin_cb`
   skips "from_A" xacts.
3. No loop.

Each direction has its own origin; the filter prevents the
cycle.

## Origin progress in pg_stat_replication_origins

```sql
SELECT * FROM pg_show_replication_origin_status();
```

Returns:
- `external_id` — origin name.
- `remote_lsn` — last applied remote LSN.
- `local_lsn` — corresponding local LSN.

Monitoring tool for "how far has subscriber X applied?".

## Catalog: pg_replication_origin

Two columns:
- `roident` — uint16 id.
- `roname` — name.

Created by `pg_replication_origin_create('name')`; dropped by
`pg_replication_origin_drop('name')`.

The id is durable (used in WAL records); name is for human
display.

## Crash recovery flow

On crash + restart:
1. Recovery reads `pg_logical/replorigin_checkpoint` (set at
   last checkpoint).
2. Origin states reloaded into shmem.
3. As WAL is replayed, origin progress records advance the
   in-memory state.
4. Apply workers resume from the recovered progress.

This ensures replicated transactions aren't re-applied after a
crash.

## Common review-time concerns

- **Origin id is uint16** — max ~65k origins; rare to hit.
- **Loop prevention requires both sides** to use distinct
  origins.
- **Session-local advance is faster** — use when
  per-xact-hot.
- **`replorigin_session_setup` per worker** at startup;
  released at shutdown.
- **Checkpoint persists origin state** — recovery is
  crash-safe.
- **Adding a new replorigin user** requires registering at
  startup; don't proliferate.

## Invariants

- **[INV-1]** Origins identified by uint16 id; max ~65k.
- **[INV-2]** Apply worker sets up session origin once per
  startup.
- **[INV-3]** replorigin_advance is hot-path; session-local
  variant cheaper.
- **[INV-4]** filter_by_origin_cb consults txn->origin_id for
  loop prevention.
- **[INV-5]** Checkpoint persists state to
  pg_logical/replorigin_checkpoint.

## Useful greps

- The advance entries:
  `grep -n 'replorigin_advance\|replorigin_session_setup\|replorigin_session_advance' source/src/backend/replication/logical/origin.c | head -10`
- Filter use:
  `grep -RIn 'filter_by_origin_cb\|origin_id' source/src/backend/replication/logical | head -15`
- Catalog row:
  `grep -n 'pg_replication_origin' source/src/include/catalog/pg_replication_origin.h | head -5`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/replication/logical/origin.c`](../files/src/backend/replication/logical/origin.c.md) | 928 | replorigin_advance |
| [`src/backend/replication/logical/origin.c`](../files/src/backend/replication/logical/origin.c.md) | 1329 | session-local advance commentary |
| [`src/backend/replication/logical/origin.c`](../files/src/backend/replication/logical/origin.c.md) | 1603 | replorigin_advance use in WAL replay |
| [`src/backend/replication/logical/origin.c`](../files/src/backend/replication/logical/origin.c.md) | — | full module |
| [`src/include/catalog/pg_replication_origin.h`](../files/src/include/catalog/pg_replication_origin.h.md) | — | catalog row |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->

## Cross-references

- `knowledge/idioms/output-plugin-callbacks.md` —
  filter_by_origin_cb hook.
- `knowledge/idioms/logical-decoding-snapshot.md` —
  decoder context.
- `knowledge/idioms/replication-slot-advance.md` —
  separate slot state.
- `knowledge/idioms/walsender-state-machine.md` — walsender
  emits xacts with origin tagging.
- `knowledge/idioms/commit-transaction-sequence.md` — commit
  WAL records carry origin_id.
- `knowledge/idioms/checkpoint-coordination.md` — origin
  state checkpointed.
- `knowledge/subsystems/replication.md` — replication
  overview.
- `.claude/skills/replication-overview/SKILL.md` — companion.
- `source/src/backend/replication/logical/origin.c` — full
  module.
- `source/src/include/catalog/pg_replication_origin.h` —
  catalog row.
