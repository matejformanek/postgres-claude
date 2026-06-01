# reloptions.c

- **Source path:** `source/src/backend/access/common/reloptions.c`
- **Lines:** 2282
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `reloptions.h`, `amapi.h` (per-AM `amoptions` callback), `commands/tablecmds.c`, every per-AM file that defines its own options (`nbtree.c`, `gist.c`, `brin.c`, …).

## Purpose

Core support for `pg_class.reloptions` and `pg_tablespace.spcoptions`: a typed-option registry (bool/ternary/int/real/enum/string) plus parsers/serializers. Each AM registers its specific options at startup; user-visible `WITH (...)` syntax is parsed against the union of the core option set and the AM-specific set. Also holds the canonical lock-level guidance for option changes. [from-comment, reloptions.c:39-90]

## Top-of-file comment

> "Core support for relation options (pg_class.reloptions)" — followed by a ~70-line how-to ("To add an option: (i) decide on a type … (vi) don't forget to document the option") and a definitive lock-level table for every existing option. **This is the authoritative source for which lock level a given reloption change requires.** [from-comment, reloptions.c:39-90]

## Top-of-file comment (lock levels)

> "The default choice for any new option should be `AccessExclusiveLock`. In some cases the lock level can be reduced from there, but the lock level chosen should always conflict with itself … `Fillfactor` can be set at `ShareUpdateExclusiveLock` because it applies only to subsequent changes made to data blocks … Autovacuum related parameters can be set at `ShareUpdateExclusiveLock` since they are only used by the AV procs and don't change anything currently executing." [from-comment, reloptions.c:58-90]

## Public surface (selection)

- **Registration helpers (called at module init):** `add_bool_reloption`, `add_ternary_reloption`, `add_int_reloption`, `add_real_reloption`, `add_enum_reloption`, `add_string_reloption`. Plus `add_local_*` variants for opclass-local options.
- **Parsing pipeline:** `transformRelOptions` (1266, merges old + new options into a Datum), `untransformRelOptions` (1450), `extractRelOptions` (1498, from a pg_class HeapTuple → the AM's options struct), `parseRelOptions` (1618), `parse_one_reloption` (1688), `parseRelOptionsInternal` (1546), `parseLocalRelOptions` (1660).
- **Output build:** `allocateReloptStruct` (1835), `fillRelOptions` (1875), `build_reloptions` (2053), `build_local_reloptions` (2090).
- **Per-relkind defaults:** `default_reloptions` (1975, heap/toast), `partitioned_table_reloptions` (2129), `view_reloptions` (2143), plus AM-specific definitions of `heap_reloptions`, `index_reloptions`, etc., declared in reloptions.h.

## Key invariants

- Each option has a registered `LOCKMODE lockmode` that an `ALTER TABLE … SET (...)` to that option must take. [from-comment, reloptions.c:58-90; verified-by-code]
- Option names live in a global namespace (within their kind: HEAP, INDEX, VIEW, TOAST, …). Duplicate registration triggers `elog(ERROR)`. [verified-by-code, reloptions.c:758-790]
- `transformRelOptions` is the only place that knows how to merge an existing options text-array with a `DefElem` list (handling `RESET`, `IGNORE_OIDS`, namespaces). [verified-by-code, reloptions.c:1266-1450]
- For options whose value affects query plans/results (anything user-visible at SELECT time), the lock level MUST be `AccessExclusiveLock`. Lower levels are reserved for things that only affect future writes (`fillfactor`), background work (`autovacuum_*`), or ANALYZE only (`n_distinct`). [from-comment, reloptions.c:67-90]

## Functions of note

1. **`transformRelOptions`** (1266) — Merges old and new options for `ALTER ... SET (...)` and `RESET (...)`. Handles namespace-qualified options (e.g. `toast.autovacuum_enabled`). Outputs a `Datum` containing a text[]. [verified-by-code]
2. **`extractRelOptions`** (1498) — Top-level entry called by relcache and DDL: load `pg_class.reloptions`, dispatch through the AM's `amoptions` callback (or `default_reloptions` / `view_reloptions` / `partitioned_table_reloptions`) to produce the parsed C struct (e.g. `StdRdOptions`, `BTOptions`). [verified-by-code]
3. **`parseRelOptions`** (1618) — Given the raw text-array and a `relopt_kind`, match each user option against the registered option list, store typed values into `relopt_value[]`. Throws on unknown options unless `validate=false`. [verified-by-code]
4. **`fillRelOptions`** (1875) — Walks the `relopt_value[]` and writes typed values into the AM's allocated struct at the right offsets (offsets are registered per option). Also handles string-option indirection (the struct stores an int offset; the string lives at `(char *)rdopts + offset`). [verified-by-code]
5. **`default_reloptions`** (1975) — Heap/toast options: `fillfactor`, `toast_tuple_target`, parallel-workers, all `autovacuum_*`, `user_catalog_table`, `vacuum_truncate`, `vacuum_index_cleanup`, `vacuum_max_eager_freeze_failure_rate`. Returns a `StdRdOptions *` or NULL. [verified-by-code]

## Cross-references

- Called from `relcache.c` (loading reloptions per relation), `tablecmds.c` (ALTER TABLE SET (...)), every AM handler routine (defining AM-specific opclass options).
- AMs supply their own `amoptions` (pointed to in `IndexAmRoutine` / `TableAmRoutine`) which calls `build_reloptions` with that AM's list.

## Open questions

- Whether the lock-level discipline is enforced beyond docstring (i.e. does anything cross-check that `ATExecSetRelOptions` actually takes the registered lock?). Spot-checks suggest yes but I didn't grep exhaustively. [unverified]

## Confidence tag tally
`[verified-by-code]=8 [from-comment]=5 [from-readme]=0 [inferred]=0 [unverified]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
