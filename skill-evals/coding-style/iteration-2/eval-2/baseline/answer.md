# Eval 2 — baseline (no skill)

## What you forgot

`src/tools/pgindent/typedefs.list`.

pgindent is essentially `indent(1)` driven by a list of known type names.
For each identifier in that list it knows "this is a type, so format
`Type *var` with the star attached to the variable, not to the type." For
identifiers it doesn't know, it treats them as ordinary names — which
means `FooScanState *p` looks to it like a binary expression and it adds
spaces in the wrong places. Once you add `FooScanState` to the list, the
unrelated churn goes away.

The list is in `src/tools/pgindent/typedefs.list`, one identifier per
line, sorted. The upstream copy is also periodically regenerated from
the buildfarm (which extracts typedef names from object files), so
contributions naturally get folded back — but you should still add new
types in your patch so reviewers don't see the spurious churn.

## Other typedef gotchas with pgindent

- **Don't name a function the same as a typedef.** pgindent's heuristic
  uses identifier names; if `FooScanState` is both a typedef and a
  function name, pgindent can't disambiguate and the formatting goes
  sideways. Pick distinct names.

- **Don't `typedef struct X X;` and then also forward-declare `struct X`
  inconsistently across headers** — pgindent doesn't care, but C
  compilers on some platforms historically did.

- **Run pgindent locally before committing.** `src/tools/pgindent/pgindent`
  with the current `typedefs.list` will surface exactly this kind of
  problem in your own diff instead of in a reviewer's.

- If pgindent rewrites code inside `#ifdef` blocks oddly, it's usually
  because the preprocessor branches have unbalanced braces — pgindent
  only sees the post-preprocessor form and gets confused. Restructure
  the block so each branch is brace-balanced.
