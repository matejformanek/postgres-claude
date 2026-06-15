---
path: src/interfaces/ecpg/test/preproc/strings.h
anchor_sha: e18b0cb7344
loc: 18
depth: read
---

# src/interfaces/ecpg/test/preproc/strings.h

## Purpose

**Fixture header declaring eight `char *` host variables** (`s1`..`s8`)
for the ecpg preprocessor's string-handling tests. A `.pgc` test source
includes this header and then uses `:s1`..`:s8` as host-variable bindings
in `EXEC SQL` statements. The test verifies that ecpg correctly recognizes
externally-declared C string variables as valid host variables — the same
include-boundary concern as `struct.h`, but for scalar `char *` rather
than struct types. `[verified-by-code]` (`strings.h:1-18`)

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `char *s1, *s2, *s3, *s4, *s5, *s6, *s7, *s8;` | `strings.h:11-18` | tentative definitions; reserve storage in the including translation unit |
| `extern char *s1, ..., *s8;` | `strings.h:2-9` | matching prior `extern` declarations to silence `-Wmissing-variable-declarations` |

## Internal landmarks

- **Double declaration is intentional.** Lines 2-9 are an `extern`
  declaration; lines 11-18 are the actual tentative definitions. Without
  the prior `extern`, compiling the including `.c` with
  `-Wmissing-variable-declarations` (a default in some PG builds) emits
  a warning for each `sN`. The leading comment makes this explicit:
  *"redundant declaration to silence -Wmissing-variable-declarations"*.
  `[from-comment]` (`strings.h:1`)
- **Definitions, not declarations.** Because the file is `#include`d by
  exactly one `.pgc` source in the test suite, the tentative definitions
  on lines 11-18 reserve storage there — not in every TU that ever
  includes the header. Including this from two `.pgc` files would
  produce duplicate-symbol link errors.

## Invariants & gotchas

- **Single-include header.** No `#ifndef` guard. Including it from two
  TUs in the same link will fail at link time (multiple definition of
  `s1` etc.).
- **No initializer.** All eight pointers start as the zero-initialized
  static value (NULL). Tests must assign before dereferencing — typical
  pattern is `EXEC SQL FETCH … INTO :s1, :s2, …` which ecpg expands into
  `malloc`+copy.
- **Eight is arbitrary.** The number matches what the consumer `.pgc`
  needs at the anchor; expanding the suite means appending `s9, s10, …`
  in both the `extern` block and the definition block in lockstep.

## Cross-refs

- `knowledge/files/src/interfaces/ecpg/preproc/` — the preprocessor under
  test, which must recognize `s1`..`s8` as host variables when they
  appear after `:` in an `EXEC SQL` statement.
- `knowledge/files/src/interfaces/ecpg/test/pg_regress_ecpg.c.md` — the
  driver that compiles the consumer `.pgc` and diffs the result.
- `knowledge/files/src/interfaces/ecpg/test/preproc/struct.h.md` —
  sibling fixture for struct-type host variables.
