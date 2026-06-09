# Issues — `src/include/lib`

Per-subsystem issue register for the **generic in-tree data-structures** — binary heap, bloom, dshash, hyperloglog, ilist, integerset, knapsack, pairingheap, qunique, radixtree, rbtree, simplehash, sort_template, stringinfo. 15 headers / ~11 entries surfaced 2026-06-09 by A15-4.

**Parent docs:** `knowledge/files/src/include/lib/*` (15 docs total — full directory coverage).

## Headlines

1. **`stringinfo.h` is the central injection sink for the A13/A14/A7 cluster** — `appendStringInfo(s, "%s", untrusted)` is the canonical PG SQL/shell injection footgun (A13 tablefunc.connectby_text + A14 basebackup_to_shell + A7 to_char). Header carries NO warning. **Phase-D candidate:** API-level quoting helpers (`appendStringInfoQuotedIdentifier`, `appendStringInfoShellQuoted`).
2. **`radixtree.h` lacks lock-held Asserts** in `RT_SET`/`RT_DELETE` (only magic+root asserts protect); header TODOs the high-concurrency-mixed-rw weakness (lines 83-87).
3. **`bloomfilter.h` is the in-tree generic Bloom** while contrib `bloom`-AM + `hstore_gin` + `ltree_gist` + `intarray_gist` + `pg_trgm_gist` each ship their own ad-hoc multi-hash — **5 implementations, no shared abstraction**. Default seed=0 in all internal callers; attacker who knows the seed crafts collisions to defeat amcheck-style verification.
4. **`dshash.h` silent corruption on mismatched parameters** between attaching backends; no magic-cookie check in shared header — function-pointer skew across cross-version reloads is the real production hazard.
5. **`hyperloglog.h` used by ANALYZE** — stats-import path (A11 postgres_fdw cluster) feeds hashes influencing `n_distinct` and downstream planner choices. Planner-oracle vector.

## Entries

- [ISSUE-api-shape: 5 separate Bloom implementations in-tree; no unified abstraction (nit, design)] — `bloomfilter.h:16-25`
- [ISSUE-defense-in-depth: default seed=0 in all internal callers of `bloom_create` (nit)] — `bloomfilter.h:18-19`
- [ISSUE-correctness: silent corruption on mismatched `dshash_parameters` between attaching backends; no magic-cookie check (nit)] — `dshash.h:44-62`
- [ISSUE-security: hyperloglog used by ANALYZE; A11 postgres_fdw stats-import path feeds attacker-controlled hashes (nit)] — `hyperloglog.h:62-64`
- [ISSUE-api-shape: integerset is deletion-candidate, superseded by radixtree-backed tidstore in PG17 (nit, tech debt)] — `integerset.h:14-22`
- [ISSUE-concurrency: radixtree `RT_SET`/`RT_DELETE` do not Assert per-tree rwlock held in `RT_SHMEM` mode (nit)] — `radixtree.h:1707-1712,2617-2624`
- [ISSUE-documentation: radixtree header TODO notes current rwlock sub-optimal for high concurrency mixed read-write; OLC/ROWEX 2016 open future work (nit)] — `radixtree.h:83-87`
- [ISSUE-api-shape: simplehash silent corruption if `SH_ELEMENT_TYPE` missing the status field — fails only at link time (nit)] — `simplehash.h:54-55`
- [ISSUE-defense-in-depth: simplehash hash quality caller-managed; no header-level safe patterns for user-input keys; collision-DoS surface (nit, A11/A13/A14 cluster echo)] — `simplehash.h:33-66`
- [ISSUE-security: stringinfo header docs do not warn callers about `appendStringInfo(s, "%s", untrusted)` injection footgun (likely, A7/A13/A14 cluster headline)] — `stringinfo.h:193-199`
- [ISSUE-api-shape: no built-in SQL/shell quoting helpers in StringInfo API; callers reach for `quote_identifier` or ad-hoc escaping (nit, Phase D candidate)] — `stringinfo.h:193-256`

## Cross-sweep references

- A11/A13/A14 signature-collision cluster (bloomfilter.h is the in-tree generic version).
- A13 tablefunc + A14 basebackup_to_shell + A7 to_char + A14 cube cubeparse = **text-injection cluster** with stringinfo.h as host.
- A11 postgres_fdw stats-import → hyperloglog.h trust angle.
- A14 amcheck signature-collision angle on attacker data.
