# utils/datum.h — typbyval/typlen-driven Datum ops

Source: `source/src/include/utils/datum.h` (76 lines)
Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Generic operations on a Datum given just `typByVal` and `typLen` — copy, transfer, equality, hash, parallel-worker serialize/restore. The "anonymous Datum" API.

## Public API

- `datumGetSize(value, typByVal, typLen)` (`datum.h:24`).
- `datumCopy(value, typByVal, typLen)` (`datum.h:31`) — palloc's copy if pass-by-ref.
- `datumTransfer(value, typByVal, typLen)` (`datum.h:38`) — differs from datumCopy in handling RW expanded objects (keeps RW pointer instead of flattening).
- `datumIsEqual(v1, v2, typByVal, typLen)` (`datum.h:46-47`) — logical equality (subject to caveats).
- `datum_image_eq(v1, v2, typByVal, typLen)` (`datum.h:55-56`) — byte-image equality.
- `datum_image_hash(value, typByVal, typLen)` (`datum.h:64`) — hash of byte image.
- `datumEstimateSpace` / `datumSerialize` / `datumRestore` (`datum.h:70-74`) — parallel-worker transport.

## Invariants

- **INV-datumIsEqual-not-strict** [from-comment, `datum.h:42-44`]: "XXX : See comments in the code for restrictions!" — `datumIsEqual` does NOT call the type's equality operator. For pass-by-ref types it compares bytes (potentially missing semantic equality where two distinct representations compare equal — e.g. numeric "1.0" vs "1.00"). Callers needing real equality must use the type's btree opclass.
- **INV-image-eq-vs-logical-eq** [verified-by-code, `datum.h:50-56`]: `datum_image_eq` is explicitly byte-image. Different from logical equality.
- **INV-image-hash-matches-image-eq** [implied, `datum.h:58-64`]: `datum_image_hash` is the partner — if two datums byte-image-equal, they hash equal.
- **INV-datumTransfer-RW-aware** [from-comment, `datum.h:34-36`]: keeps an RW expanded datum's RW pointer intact (datumCopy would flatten it).

## Trust-boundary / Phase-D surface

- **`datumIsEqual` for security-sensitive comparisons is wrong** — its docs warn but callers comparing user data with `datumIsEqual` get byte-image semantics, not "user thinks these are equal" semantics. Easy to use mistakenly.
- **`datumSerialize`/`datumRestore` for parallel workers** trust the source's typbyval/typlen agreement. If sender/receiver disagree on those (different fmgr revisions?), bytes are misinterpreted. This is largely controlled by passing them out-of-band but worth noting.

## Cross-refs

- `source/src/backend/utils/adt/datum.c` — implementation.
- `knowledge/files/src/include/utils/expandeddatum.md` — RW pointer semantics.

## Issues

- `[ISSUE-DOC: datumIsEqual is not equality (high)]` — XXX comment at `datum.h:42-44` is non-specific. A loud warning that semantic equality requires the btree opclass would prevent misuse.
