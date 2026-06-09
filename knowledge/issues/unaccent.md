# Issues — `contrib/unaccent`

Text-search dictionary template that removes accents. 1 source file / ~502 LOC.

**Parent docs:** `knowledge/files/contrib/unaccent/unaccent.c.md`.

**Source:** 4 entries surfaced 2026-06-09 by A14-3.

## Headlines

1. Trie grows unboundedly with rules file; no `MaxAllocSize` cap on node count.
2. Duplicate-rule WARNINGs unaggregated — log-spam attack on bad rules file.
3. Untranslatable lines silently skipped on encoding change.
4. Parser loop assumes `pg_mblen_cstr > 0` — `ptrlen=0` could infinite-loop.

**Path traversal in unaccent/dict_xsyn is properly blocked** by `ts_utils.c:49` (basename allowlist `[a-z0-9_]+`).

## Entries — `unaccent.c`

- [ISSUE-resource: trie grows unboundedly with rules file; no `MaxAllocSize` cap on node count (maybe)] — `:56-89,96-302`
- [ISSUE-resource: duplicate-rule WARNINGs unaggregated, log-spam attack on bad rules file (nit)] — `:71-74`
- [ISSUE-correctness: untranslatable lines silently skipped on encoding change (nit)] — `:278-294`
- [ISSUE-correctness: parser loop assumes `pg_mblen_cstr > 0`; `ptrlen=0` could infinite-loop (nit)] — `:157-159`

## Cross-sweep references

- A14 dict_xsyn, dict_int — same dictionary-template family.
- A5 jsonapi recursive parser — parser-loop family.
