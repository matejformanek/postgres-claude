---
source_url: https://www.postgresql.org/docs/current/protocol-logical-replication.html
fetched_at: 2026-06-10T20:50:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Logical Streaming Replication Protocol (protocol ch. 54.5)

The wire framing that logical decoding output (via `pgoutput`) rides over the
physical streaming-replication channel. Central to the A8 output-plugin thread and
the D data-leak project: this is exactly the surface where row data leaves the
server in decoded form.

## Non-obvious claims

- **Logical replication reuses the physical streaming primitives**, started with
  `START_REPLICATION SLOT slot_name LOGICAL`. The built-in output plugin is
  `pgoutput`. [from-docs]
- **Four protocol versions, each gating a feature** (set via `proto_version`):
  - v1 — base.
  - v2 (server 14+) — streaming of large *in-progress* transactions.
  - v3 (server 15+) — two-phase commit streaming.
  - v4 (server 16+) — *parallel* apply of large in-progress streams. [from-docs]
- **Key START_REPLICATION options:** `proto_version` (required),
  `publication_names` (required, comma list), `binary` (faster/less robust),
  `messages` (surface `pg_logical_emit_message`), `streaming`
  (`off`/`on`(v2+)/`parallel`(v4+)), `two_phase` (v3+), `origin`
  (`none`/`any` — origin filtering for cascades). [from-docs]
- **Transaction envelopes differ by kind:**
  - regular → `Begin` … `Commit`;
  - two-phase → `Begin Prepare` … `Prepare`;
  - large in-progress → `Stream Start` … `Stream Stop`, finalized by
    `Stream Commit` **or** `Stream Abort`. [from-docs]
- **`Origin` message is optional and must precede all DML** in a transaction
  (cascaded-replication scenario); handling it is explicitly the *downstream's*
  responsibility "if needed". [from-docs]
- **🔑 Schema is pushed, not pulled.** A `Relation` message (describing columns by
  OID) precedes the first DML for a relation OID and is re-sent only when the
  definition changes. The client MUST cache this for *as many relations as needed*
  — an unbounded client-side schema cache is assumed. [from-docs]
- **Non-built-in types get a `Type` message *before* the `Relation` message.**
  Built-in type OIDs are assumed client-resolvable; for others the client must
  cache the `Type` message and consult it before any local catalog lookup.
  [from-docs]
- **DML messages:** `Insert`, `Update`, `Delete`, `Truncate`. Direction is
  backend→frontend except `START_REPLICATION` itself and replay-progress
  feedback, which are bidirectional. [from-docs]
- **No length header on top-level messages** — the underlying streaming protocol
  already frames length, so logical messages omit it. The leading message-type
  byte is "a signed byte with no associated encoding". [from-docs]

## Links into corpus

- Detailed byte layout: `knowledge/docs-distilled/protocol-logicalrep-message-formats`
  (not yet distilled — candidate for a future run) and
  `knowledge/docs-distilled/protocol-replication.md` (physical layer this rides on).
- Decoding entry points: `knowledge/docs-distilled/custom-rmgr.md` (`rm_decode`)
  and the `replication-overview` skill (walsender / output-plugin callbacks).
- Threat-adjacent: A8 output-plugin + D data-leak threads — `pgoutput` and the
  `binary`/`messages` options decide what bytes cross the wire.
- Code: `source/src/backend/replication/pgoutput/pgoutput.c`,
  `source/src/backend/replication/logical/proto.c` (logicalrep_write_* framing).
  [unverified — not line-pinned this run]
