# `src/include/access/sequence.h`

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**24 lines.**

## Role

Two-function wrapper around `relation_open`/`relation_close` specialized
for sequence relations. Provides a single chokepoint that asserts (or
will assert) "this relid is actually a sequence" so callers don't accidentally
open a regular table thinking it's a sequence.
[verified-by-code] `source/src/include/access/sequence.h:1-13`

## Public API

Two externs:
- `sequence_open(relationId, lockmode)` → `Relation`.
- `sequence_close(relation, lockmode)`.

That's the entire surface (lines 20-21).

## Invariants

- The caller is responsible for picking the right `lockmode` —
  `RowExclusiveLock` for `nextval`/`setval`, `AccessShareLock` for
  metadata-only reads. [inferred from caller patterns]
- `sequence_open` is expected to error if the relid is not a sequence
  (`RELKIND_SEQUENCE`). [inferred — actual check is in `sequence.c`,
  not the header]

## Notable internals

This header is intentionally minimal — it's the public access-method
interface. The actual sequence storage, fetching, and the
`nextval/currval/setval/lastval` SQL-level functions live in
`commands/sequence.c` (note: that file, not `access/sequence.c`).
The split: `access/sequence.h` is the open/close surface; the
operational sequence behavior is in `commands/`.

## Trust-boundary / Phase D surface

**A11 finding context (sequences)**: the canonical "trust the next-val"
surface. Sequence values flow into IDs, primary keys, surrogate keys,
and (notoriously) into client-visible identifiers that are sometimes
assumed unguessable. They are NOT cryptographically random.

A Phase-D leak vector: a low-privilege user with `USAGE` on a sequence
in another schema can `SELECT nextval(...)` to **probe how busy other
tenants are** — sequences are shared, monotonic, and observable. The
classic side-channel: call `nextval` once per minute and watch the
delta to infer write traffic on tables you can't read.

`sequence_open` is also the point where ownership/usage checks should
fire; the current header relies on `RangeVarGetRelidExtended` and
ACL checks at the SQL layer, NOT here. A direct caller of
`sequence_open(some_oid, ...)` from C bypasses those checks.

**A12 cross-link:** `pg_surgery` does not touch sequences (it only
modifies heap tuple visibility) — but a forensic counterpart for
sequences (manually setting `is_called`/`last_value`) would need
`sequence_open` and is worth noting as a not-yet-implemented surface.

## Cross-refs

- `commands/sequence.h` (and `commands/sequence.c`) — `nextval`,
  `currval`, `setval` SQL surface.
- `catalog/pg_sequence.h` — `pg_sequence` catalog.
- `utils/relcache.h` — `Relation` type.
- `storage/lockdefs.h` — `LOCKMODE`.

## Issues

- **ISSUE-doc**: header is too thin to convey the chokepoint role.
  No assertion documented; new contributors may inline
  `relation_open` and miss the implied RELKIND check.
- **ISSUE-leak**: no comment about the cross-tenant side-channel
  risk of public `nextval()`. Documentation should flag this.
