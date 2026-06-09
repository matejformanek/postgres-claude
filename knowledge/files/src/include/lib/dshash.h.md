# `src/include/lib/dshash.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 138

## Role

Concurrent hash table backed by DSA (dynamic shared-memory area).
A `dshash_table_handle` is a `dsa_pointer` — shareable across
processes. Counterpart of dynahash for non-shmem and `HTAB`
(shmem fixed-size); dshash is the only resizable shared hash.
[verified-by-code] `source/src/include/lib/dshash.h:23-27`

Major consumers: `pg_stat_statements` shared registry,
typcache shared record-type cache, replication slot directory
parts, cumulative-stats subsystem in pgstats.

## Public API

- Create/attach: `dshash_create`, `dshash_attach`, `dshash_detach`,
  `dshash_destroy`, `dshash_get_hash_table_handle`
- Entry ops: `dshash_find` (with `exclusive` bool),
  `dshash_find_or_insert{,_extended}`, `dshash_delete_key`,
  `dshash_delete_entry`, `dshash_release_lock`
- Seq scan: `dshash_seq_init`/`_next`/`_term`/`_delete_current`
- `DSHASH_INSERT_NO_OOM` flag (`source/src/include/lib/dshash.h:96`)

## Invariants

- INV-1: `dshash_parameters` must specify identical {key_size,
  entry_size, compare, hash, copy} on every attach — these aren't
  validated and a mismatch silently corrupts. [verified-by-code]
  `source/src/include/lib/dshash.h:44-62`
- INV-2: function pointers in `dshash_parameters` must point at
  symbols valid in every attaching backend (typically static
  functions in the same .c file). Loadable-module pointer skew
  across backends is a known foot-gun.
- INV-3: returned entries are *locked* — caller MUST eventually
  call `dshash_release_lock` (or use seq-scan's term).
  [from-comment] dshash.c API contract.

## Notable internals

- Internally uses **partition locks** (split lwlocks per bucket
  range) so concurrent ops on different keys don't contend.
- Resize is online (under exclusive partition lock walk); during
  resize, lookups can be slow.

## Trust boundary (Phase D)

- DSA pointer leakage: `dshash_get_hash_table_handle` returns a
  raw `dsa_pointer`; if an extension exposes it as a SQL-visible
  value (bytea/text), backends with detach-then-attach could be
  pointed at arbitrary DSA chunks. No core caller does this.
- Function-pointer-skew across `dlopen()` is the real production
  hazard (cross-version contrib reload).

## Cross-refs

- `knowledge/files/src/include/utils/dsa.h.md` (if exists) — the
  underlying allocator
- `knowledge/files/src/include/lib/simplehash.h.md` —
  non-shmem templated peer

## Issues

- ISSUE-DESIGN: silent corruption on mismatched
  `dshash_parameters` between attachers. Could add a magic-cookie
  check in the shared header. (Low — process model normally
  guarantees consistency.)
