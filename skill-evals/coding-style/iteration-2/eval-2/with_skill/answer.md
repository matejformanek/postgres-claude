# Eval 2 — with skill

## What you forgot

You didn't add `FooScanState` to `src/tools/pgindent/typedefs.list`.

pgindent uses that list to know which identifiers are types. Without the
entry it can't tell that `FooScanState *p` is a pointer-to-type (which
should be formatted as `FooScanState *p` with the star bound to `p`) vs.
a multiplication-like expression, so it produces spurious reformatting
of every line in the tree that mentions `FooScanState`. That's why
"unrelated" files churn.

Fix: add `FooScanState` to `src/tools/pgindent/typedefs.list` (keep the
list sorted), re-run pgindent, and the churn disappears.

## The other typedef gotcha that bites you

**Don't give a function the same name as a typedef.** If you have a
typedef `FooScanState` and also a function `FooScanState(...)`, pgindent
will mangle both — it'll try to format every call as `FooScanState (...)`
(type cast spacing) and the result is ugly diffs everywhere. Rename one
of the two.

## Bonus from the same family of pgindent escape valves

While we're on pgindent surprises: if pgindent insists on reformatting
code inside an `#if` / `#else` / `#endif` block because the brace
nesting is mismatched between branches, the fix is to restructure the
preprocessor block so each branch is brace-balanced on its own.
pgindent only sees one branch at a time and gets confused otherwise.

## Operational hygiene

Run `src/tools/pgindent/pgindent .` locally before committing — it'll
surface this in your own diff instead of as a surprise on the
buildfarm or in a reviewer's comments. (Note: the upstream
typedefs.list is regenerated periodically from buildfarm output, so
even types you forgot will eventually appear there — but you want your
patch clean *before* that, not after.)
