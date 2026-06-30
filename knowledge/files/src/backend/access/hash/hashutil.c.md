# hashutil.c

- **Source path:** `source/src/backend/access/hash/hashutil.c` (632 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Misc utilities: `_hash_checkqual` (does this index tuple match the scan condition), `_hash_datum2hashkey`, bucket-bit math, page-init helpers, `_hash_get_indextuple_hashkey`, and reloption parsing. [from-comment, hashutil.c:1-13]

## Notable macros / functions

- `CALC_NEW_BUCKET(old, lowmask) = old | (lowmask + 1)` — given the old bucket and the lowmask after a split, compute the new bucket number that a tuple may have migrated to. [verified-by-code, line 25]
- `_hash_get_indextuple_hashkey` — extract the 4-byte hash code from an index tuple (located right after the tuple header; not in t_tid).
- `_hash_datum2hashkey` / `_hash_datum2hashkey_type` — invoke the opclass `hash` proc.
- `_hash_hashkey2bucket` — mask hashkey by `(maxbucket, highmask, lowmask)` to compute target bucket: `bucket = hashkey & highmask; if bucket > maxbucket then bucket &= lowmask`.
- `_hash_finish_split` — restart logic for crashed splits: scan new bucket (build hash table of TIDs), conditional cleanup-lock both, run split-completion. [from-README, README:292-300]

Tags: [from-comment, hashutil.c:1-13]; [verified-by-code for `CALC_NEW_BUCKET`].

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [idioms/hash-page-layout.md](../../../../../idioms/hash-page-layout.md)

