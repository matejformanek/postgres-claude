# `src/include/storage/proclist_types.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~54
- **Source:** `source/src/include/storage/proclist_types.h`

Three tiny POD structs that back the by-procno doubly-linked list
machinery in `proclist.h`. Split out into its own header so that
code which needs to *embed* a `proclist_node` in a struct (most
notably `PGPROC` itself) does not transitively pull in `proc.h` —
which would be a header cycle since `proclist.h` already needs
`proc.h` for `GetPGProcByNumber`. [from-comment]

## API / declarations

- `typedef struct proclist_node { ProcNumber next; ProcNumber prev; }`
  — embedded link field inside PGPROC. Each PGPROC may carry several
  of these for different lists (LWLock wait, CV wait, etc.). [verified-by-code]
- `typedef struct proclist_head { ProcNumber head; ProcNumber tail; }`
  — list header; `head == tail == INVALID_PROC_NUMBER` for empty. [verified-by-code]
- `typedef struct proclist_mutable_iter { ProcNumber cur; ProcNumber next; }`
  — iterator state allowing deletion of `cur` mid-walk. [verified-by-code]

## Notable invariants / details

- The "not in any list" state of a `proclist_node` is encoded as
  `next == prev == 0` — note this is **literal zero**, not
  `INVALID_PROC_NUMBER`. The head-comment explicitly forbids
  circularity so this encoding is unambiguous: a real list never
  links a node back to procno 0 in both directions because that
  would imply procno 0 is its own neighbour. [verified-by-code]
  [from-comment]
- `ProcNumber` is an `int` (see `procnumber.h`); the special values
  `INVALID_PROC_NUMBER` (-1) and `0` carry distinct meanings here. [from-comment]
- The split-header trick (types here, functions in `proclist.h`) is a
  recurring PG pattern for cycle-breaking — see also
  `dsa.h`/`dsa_internal.h`, `htab.h`/`hash.h`. [inferred]

## Potential issues

- Lines 20-27. The "not in any list ⇒ next == prev == 0" rule is
  documented in this header, but consumers that **manually** zero a
  freshly allocated PGPROC (or memset it) rely on this. If a future
  PGPROC refactor moved away from zero-init, every proclist_node
  field would need explicit initialization. There is no central
  assertion for this. [verified-by-code]
  [ISSUE-undocumented-invariant: rule "zero-init is sufficient for
  not-in-any-list state" depends on PGPROC remaining a `MemSet`-able
  POD allocation (nit)]
