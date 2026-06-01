# spgtextproc.c

- **Source path:** `source/src/backend/access/spgist/spgtextproc.c` (702 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Built-in **radix tree (compressed trie)** opclass over `text`: `text_ops`. Inner-tuple prefix = the common byte prefix; node label = next byte; leaf value = remaining suffix. Reconstruction: concatenate path prefixes + node labels + leaf suffix. [from-comment, spgtextproc.c:1-30]

## Special node labels

- **`-1`** — "no more bytes after the prefix-so-far". I.e. a string that ends exactly at this point still needs an index entry; that's the child reached by label -1.
- **`-2`** — "split of an all-the-same tuple". When an existing inner tuple had identical labels for all children (degenerate case), and a `SplitTuple` is needed, a -2-labeled child is created that doesn't correspond to any real byte. [from-comment, spgtextproc.c:18-30]
- **`0`** — legacy label, used for both -1 and -2 before they were distinguished. Still readable but new entries never use 0. [from-comment, spgtextproc.c:23-30]

## SPGIST_MAX_PREFIX_LENGTH

Bounds the inner-tuple prefix to keep tuples on-page. Long common prefixes get broken up into multiple inner-tuple levels.

## Procs

- `spg_text_config` — prefix = bytea (the common prefix), label = int2 (byte 0-255 or -1/-2).
- `spg_text_choose` — match prefix; descend by next byte. May return `AddNode` (new label) or `SplitTuple` (prefix mismatch).
- `spg_text_picksplit` — when bulk-splitting leaves, find longest common prefix + cluster by next byte.
- `spg_text_inner_consistent`, `spg_text_leaf_consistent` — strategy-specific (`=`, `<`, `<=`, `>=`, `>`, prefix-match).

Tags: [from-comment]; [verified-by-code].

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
