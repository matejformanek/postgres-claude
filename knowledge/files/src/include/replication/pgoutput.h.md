# src/include/replication/pgoutput.h

## Purpose

Declares `PGOutputData`, the private plugin-context struct used by
`pgoutput` — the built-in logical replication output plugin that ships
with the server and is the default plugin used by every
`CREATE SUBSCRIPTION`. Source pin
`4b0bf0788b066a4ca1d4f959566678e44ec93422`.

## Role in PG

`pgoutput` lives in `src/backend/replication/pgoutput/pgoutput.c`,
exports `_PG_output_plugin_init`, and implements the
`OutputPluginCallbacks` contract from `output_plugin.h`. It is what
turns decoded ReorderBuffer changes into the binary logical-replication
wire format consumed by the apply worker on the subscriber side
(messages defined in `protocol/logicalproto.h`). The header itself is
tiny — only `PGOutputData` is exposed — because `pgoutput`'s API
surface to other modules is just "exists as a registered plugin".

## Key types/struct fields

- `PGOutputData` (lines 18-37):
  - `context` (MemoryContext) — transient per-message allocations.
    [verified-by-code]
  - `cachectx` (MemoryContext) — RelationSyncEntry hashtable lives
    here; survives across messages within a streaming session.
    [verified-by-code]
  - `pubctx` (MemoryContext) — publication metadata (resolved
    publication objects, row filters). [verified-by-code]
  - `in_streaming` (bool) — true inside a `stream_start_cb` /
    `stream_stop_cb` window; gates which callbacks are used.
    [verified-by-code]
  - `protocol_version` (uint32) — version the subscriber negotiated
    via the `proto_version` start_replication option. Older
    subscribers get a more restricted message set. [verified-by-code]
  - `publication_names` (List *) — raw `text` list of publication
    names supplied in the start_replication options.
    [verified-by-code]
  - `publications` (List *) — resolved `Publication *` objects.
    [verified-by-code]
  - `binary` (bool) — subscriber requested binary tuple format
    (`binary=true` SUBSCRIPTION option). [verified-by-code]
  - `streaming` (char) — `'f'` off, `'o'` on, `'p'` parallel (PG14+
    streaming-in-progress xacts, PG16+ parallel apply).
    [verified-by-code]
  - `messages` (bool) — subscriber wants `pg_logical_emit_message()`
    payloads forwarded. [verified-by-code]
  - `two_phase` (bool) — two-phase commit decoding negotiated.
    [verified-by-code]
  - `publish_no_origin` (bool) — drop changes whose origin is set
    (used to break replication loops between bidirectional pubs).
    [verified-by-code]

## Phase D notes

`PGOutputData` is the live state of an in-flight subscription's
decoding session on the publisher side. Every field is supplied by the
subscriber at start time via START_REPLICATION options, so the
subscriber gets to set its own filtering and protocol-version
preferences. The publisher does not authenticate that the subscriber's
chosen `publication_names` are publications the subscribing role should
be able to read; instead the publication-membership check happens at
publication-resolution time inside pgoutput (publications are catalog
objects and have no per-role ACL beyond catalog SELECT — they were
intentionally designed as cluster-wide publishing definitions).

Row filters and column filters live on the publication
(`pg_publication_rel.prqual`, `pg_publication_rel.prattrs`) and are
evaluated by pgoutput per-row. A row filter expression is a stored
expression node evaluated as the publisher's slot-owner role; a
malicious publication owner who can edit a filter can exfiltrate other
columns or pin the publisher into an expensive predicate evaluated for
every replicated row.

`publish_no_origin` is the loop-breaker for bidirectional logical
replication: if a tuple's WAL was already tagged with a non-zero
`ReplOriginId`, pgoutput drops it. Relies on the subscriber correctly
setting its own origin via `replorigin_session_setup` before applying
incoming WAL — a misconfigured subscriber that doesn't set an origin
will create an apply loop.

## Potential issues

- [ISSUE-info-disclosure: publication objects have no per-role ACL;
  any role that can SELECT `pg_publication` sees all publication
  names and resolved tables — a subscriber that knows a publication
  name can `START_REPLICATION ... ("publication_names" 'p1, p2')`
  subject only to REPLICATION role attribute, not per-publication
  permission (sev=likely)]
- [ISSUE-trust-boundary: row filter expressions on publications run
  in the walsender backend with the slot owner's identity; a
  malicious publication owner's filter expression is evaluated for
  every replicated row (sev=maybe)]
- [ISSUE-state-transition: `publish_no_origin` relies on the
  subscriber correctly invoking `replorigin_session_setup`; a
  subscriber that omits this creates an unbounded apply loop
  (sev=maybe)]
- [ISSUE-wire-protocol: `protocol_version` and `streaming` are
  subscriber-supplied uint32 / char — pgoutput must validate them
  against supported ranges; header doesn't document the valid set
  (sev=unlikely)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-replication`](../../../../issues/include-replication.md)
<!-- issues:auto:end -->
