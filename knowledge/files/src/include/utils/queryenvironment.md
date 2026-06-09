# `src/include/utils/queryenvironment.h`

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Provides *Ephemeral Named Relations* (ENRs) — named tuple sources
visible to a query but NOT present in `pg_class`. Currently used for
AFTER-trigger transition tables (`OLD TABLE` / `NEW TABLE`)
[from-comment: lines 4-5, 47-49].

## Public API

[verified-by-code: lines 20-72]

- `EphemeralNameRelationType` enum — currently only
  `ENR_NAMED_TUPLESTORE`.
- `EphemeralNamedRelationMetadataData {name, reliddesc | tupdesc,
  enrtype, enrtuples}` — exactly ONE of `reliddesc` (OID of catalog
  rel whose tupdesc to use) or `tupdesc` (independent descriptor) is
  set [from-comment: lines 30-31].
- `EphemeralNamedRelationData {md, reldata}` — metadata plus opaque
  pointer to execution-time data (typically a tuplestore).
- `QueryEnvironment` — opaque type [from-comment: line 62].
- API: `create_queryEnv`, `register_ENR`, `unregister_ENR`,
  `get_ENR`, `get_visible_ENR_metadata`, `ENRMetadataGetTupDesc`.

## Invariants

- **INV-ONE-OF** [from-comment: lines 30-31] Exactly one of
  `reliddesc` or `tupdesc` is meaningful per metadata. Setting both
  is undefined.
- **INV-EXCLUSIVE-CTX** [inferred] An ENR is registered into a
  single `QueryEnvironment` and looked up by name; no cross-session
  visibility.

## Trust boundary (Phase D)

- ENRs let the parser resolve a *bare relation name* to something
  that has no `pg_class.oid`. They participate in name resolution
  (`get_visible_ENR_metadata`) but **bypass schema-level ACL checks**
  — there is no `aclcheck_okay` along this path. Mitigation: ENRs
  are only registered by the AFTER-trigger code, never directly by
  user SQL.
- SPI exposes ENR registration via `SPI_register_relation` /
  `SPI_register_trigger_data` (see `executor/spi.h`) — same trust
  posture: the caller is C code that already passed ACL.
- A custom extension calling `register_ENR` from a hook could
  inject a tuplestore as a fake relation visible by name to subsequent
  parser passes — useful for legitimate extensions (e.g. RLS-like
  filtering) but a footgun if naïvely accepted from untrusted input.

## Cross-refs

- `commands/trigger.c` — main user of ENRs (transition tables).
- `executor/spi.h` — `SPI_register_relation`,
  `SPI_register_trigger_data`.
- `parser/parse_relation.c` — name resolution consults
  `get_visible_ENR_metadata`.

## Issues

- [ISSUE-DOC: header gives no list of which subsystems may safely
  register an ENR; only "transition tables" is named (low)] —
  lines 47-49.
- [ISSUE-DESIGN: `EphemeralNameRelationType` has a single
  enumerator; the abstraction is more general than the
  implementation, inviting drift if a new type is added without
  re-auditing name-resolution sites (low)] — line 22.
