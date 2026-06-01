# `src/backend/regex/regc_nfa.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~3880; `#include`d into `regcomp.c`
- **Source:** `source/src/backend/regex/regc_nfa.c`

NFA construction and optimization primitives — the biggest source file
in the regex subsystem. Provides `newnfa`/`freenfa`, `newstate`,
`newarc`, `cparc`, plus the heavy-lifting optimization passes called
from `regcomp.c`:

- `pullback` / `pushfwd` — move "constraint" arcs (BOS/EOS/lookaround)
  out of the way so DFA construction can see plain character arcs.
- `fixempties` — remove epsilon arcs.
- `compact` — lower the working `nfa`/`state`/`arc` graph to a
  cache-friendly `cnfa` (contiguous arrays) for the DFA executor.
- `cleanup` / `markreachable` / `cleantraverse` — dead-state pruning.

The NFA is the source of truth; the DFA in `regexec.c` is derived from
the CNFA on demand. [from-README]
