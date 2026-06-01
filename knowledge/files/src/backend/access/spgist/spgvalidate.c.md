# spgvalidate.c

- **Source path:** `source/src/backend/access/spgist/spgvalidate.c` (383 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

`amvalidate` slot for SP-GiST. Cross-checks `pg_amop`/`pg_amproc` entries. [from-comment, spgvalidate.c:1-12]

## Required procs

```
1 config            mandatory  /* prefix type, label type, ... */
2 choose            mandatory  /* descend / AddNode / SplitTuple */
3 picksplit         mandatory  /* page-full repartition */
4 inner_consistent  mandatory  /* scan: which children match */
5 leaf_consistent   mandatory  /* scan: does this leaf match */
6 compress          optional   /* leaf storage compression */
7 options           optional   /* reloption parser */
```

The validator walks the opfamily's procs and ops, checks signatures, warns on missing strategies.

Tags: [from-comment].
