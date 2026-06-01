# `src/backend/regex/rege_dfa.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~1090; `#include`d into `regexec.c`
- **Source:** `source/src/backend/regex/rege_dfa.c`

The lazy DFA itself. Implements `longest`/`shortest`/`matchuntil`/
`lastcold`/`miss` plus state-set (`sset`) allocation/lookup. Each DFA
state corresponds to a set of active NFA states; `subset` does the
on-demand "next-state" computation: from the current sset and an input
color, follow all matching NFA arcs, mark all reachable NFA states,
and intern the resulting bitmap as a new sset (or reuse if cached).
The cache is a hash table sized by `re->nstates`; on full cache, the
oldest unused sset is recycled. [from-README]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
