# `src/backend/replication/pgoutput/pgoutput.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~2500 (74.5K)
- **Source:** `source/src/backend/replication/pgoutput/pgoutput.c`
- **Depth:** read (top-of-file + structural)

## Purpose

The builtin output plugin used by native logical replication
(PUB/SUB). Loaded by name `pgoutput` whenever an apply worker connects.
Implements every callback in `OutputPluginCallbacks` and serializes
changes via the `logicalrep_write_*` family in `proto.c`. [from-comment]

## Key state: `PGOutputData` (`pgoutput.h:18-37`)

- `protocol_version` (client-negotiated; bounded by
  `LOGICALREP_PROTO_MAX_VERSION_NUM`).
- `publication_names` (list of pubnames from START_REPLICATION options).
- `publications` (resolved list, refreshed when relevant catalog cache
  invalidates).
- `binary`, `streaming`, `messages`, `two_phase`, `publish_no_origin`.
- 3 memory contexts: `context` (transient), `cachectx` (cache data),
  `pubctx` (publication structures).

## Row filtering / column lists

Pgoutput parses publication `pubactions`, per-relation row filters
(WHERE clauses compiled into ExprStates), and column lists into a
per-(rel, publication) cache. Changes are filtered before being emitted.
`pub_collist_cache` and `RowFilterCache` etc.

## Stream / 2PC support

All `stream_*` and `*_prepare(d)` callbacks are wired. Whether they take
effect depends on `protocol_version` and on client options requesting
streaming and/or two_phase.

## Plugin entry

`_PG_output_plugin_init` (looked up via `LoadOutputPlugin` in
`logical.c`) fills the `OutputPluginCallbacks` vtable.

## Coupling

- Heavy use of catalog accesses to `pg_publication` /
  `pg_publication_rel` / `pg_publication_namespace`.
- Calls into `proto.c` to format wire bytes.
- Honors origin filter (`publish_no_origin` blocks anything tagged with
  an origin id) via `filter_by_origin_cb`.
