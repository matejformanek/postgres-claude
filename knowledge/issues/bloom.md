# Issues — `contrib/bloom`

Bloom-signature index AM. 7 source files / ~1759 LOC.

**Parent docs:** `knowledge/files/contrib/bloom/*` (7 docs: blcost, blinsert, bloom.h, blscan, blutils, blvacuum, blvalidate).

**Source:** 2 entries surfaced 2026-06-09 by A14-2.

## Headlines

1. **Bloom is the 4th GiST/signature-AM in the A13/A14 "signature-collision" cluster** — joins hstore CRC32, ltree CRC32, intarray mod-hash, pg_trgm mod-hash. `signValue` uses a deterministic Park-Miller LCG (NOT `pg_prng_*`) for ON-DISK STABILITY. Attacker-craftable collisions only inflate false-positive rate (heap recheck closes the leak gap, but DoS amplification stands).
2. **Relation extension under exclusive metapage lock serializes inserters** — author-flagged "XXX" comment.

## Entries

- [ISSUE-defense-in-depth: `signValue` is deterministic — attacker can craft colliding signatures; heap recheck prevents data leak (nit)] — `source/contrib/bloom/blutils.c:266-293`
- [ISSUE-concurrency: relation extension under exclusive metapage lock serializes inserters (maybe)] — `source/contrib/bloom/blinsert.c:312-315` — author-flagged "XXX" comment.

## Cross-sweep references

- A13 hstore (CRC32) + A13 ltree (CRC32) + A13 intarray (mod-hash) + A14 pg_trgm (mod-hash) + A14 bloom = **5-module signature-collision cluster**. Pattern: deterministic signature with attacker-controllable inputs → false-positive amplification → leaf scan + recheck → DoS.
