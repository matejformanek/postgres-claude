# hashvalidate.c

- **Source path:** `source/src/backend/access/hash/hashvalidate.c` (350 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

`amvalidate` slot. Cross-checks `pg_amop`/`pg_amproc` entries for a hash opclass. [from-comment, hashvalidate.c:1-12]

## Required procs

- procnum 1 `hash` — 32-bit hash of the value. **Mandatory.**
- procnum 2 `hash_extended` — 64-bit hash with a seed. **Mandatory.** Used by hash joins/aggregates needing extended hashing.
- procnum 3 `options` — reloption parser. Optional.

## Required operator

- Strategy 1 (`=`) only. Hash indexes support equality and nothing else.

The validator walks opfamily procs/amops, checks signatures, and warns on missing strategies or wrong arg types.

Tags: [from-comment].

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
