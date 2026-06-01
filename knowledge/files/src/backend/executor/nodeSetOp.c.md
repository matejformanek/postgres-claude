# nodeSetOp.c

- **Source:** `source/src/backend/executor/nodeSetOp.c` (≈700 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Implements INTERSECT, INTERSECT ALL, EXCEPT, EXCEPT ALL — multiset
operations on sorted or hashed input. NOT used for UNION/UNION ALL (those
are cheaper via Append + Sort/HashAgg).

[from-comment file head, paraphrased]

## Two strategies

### SETOP_SORTED

Input arrives sorted with a flag column (resjunk integer 0/1) marking
which input branch each row came from. Walk groups of equal rows, count
how many from each branch, then emit per ALL/non-ALL and INTERSECT/EXCEPT
semantics:

- INTERSECT — emit `min(count0, count1)` copies (1 copy for non-ALL).
- EXCEPT    — emit `max(count0 - count1, 0)` copies (1 if any for non-ALL).

### SETOP_HASHED

Drain outer (the LEFT side of the set op) building a TupleHashTable that
counts copies. Then drain inner (RIGHT), decrementing copies. After both
sides done, walk the hash table emitting per the count semantics.

[from-comment] `:8-26`

## No qual / no project

SetOp just copies the first-arriving tuple of each group to output. The
flag column is stripped via JunkFilter in the enclosing plan.

## Tags

- [verified-by-code] both strategies.
- [from-comment] file-level semantics explanation.
