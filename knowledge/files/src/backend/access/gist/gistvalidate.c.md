# gistvalidate.c

- **Source path:** `source/src/backend/access/gist/gistvalidate.c` (353 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

`amvalidate` slot for GiST: cross-checks `pg_amop`/`pg_amproc` entries for a GiST opclass against the required-proc list. [from-comment, gistvalidate.c:1-12]

## Required procs

```
1 consistent     mandatory
2 union          mandatory
3 compress       optional (default: identity)
4 decompress     optional (default: identity)
5 penalty        mandatory
6 picksplit      mandatory
7 same           mandatory
8 distance       optional (must exist for KNN-orderable strategies)
9 fetch          optional (enables index-only scans)
10 options       optional (reloption parser)
11 sortsupport   optional (enables sorted-build path)
```

Validator walks the opfamily's procs and amops, checks each against the opclass's `opcintype`/`opckeytype`. Returns true if valid; ereports WARNINGs otherwise.

Tags: [from-comment, gistvalidate.c:1-12].

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
