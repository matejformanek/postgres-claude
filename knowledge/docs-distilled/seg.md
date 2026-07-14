---
source_url: https://www.postgresql.org/docs/current/seg.html
fetched_at: 2026-07-14T20:53:00Z
anchor_sha: 1863452a4bfe
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "F.35 seg — a datatype for line segments or floating point intervals"
maps_to_skill: [access-method-apis, type-cache]
---

# Docs distilled — seg (float interval with confidence limits + R-tree GiST)

A 1-D interval type that carries laboratory-style *measurement uncertainty*.
Its `gist_seg_ops` is a classic **R-tree-over-GiST** boolean opclass (the 1-D
analog of `cube`), useful as the minimal template for an interval type with
positional operators.

## Non-obvious claims

- **Stored as a pair of 32-bit `float`s (not `double`).** So values beyond
  **7 significant digits truncate** — a deliberately lower precision than
  `cube`'s 64-bit `double` (~16 digits). Leading zeros don't count against the
  7; trailing zeros are preserved as real precision. [from-docs]
- **Uncertainty markers `<`, `>`, `~` are stored but semantically inert.**
  `~5.0`, `<5.0`, `>5.0` retain the marker as a comment on output, **but every
  built-in operator ignores them** — they do not widen or shift the interval
  for comparison. [from-docs]
- **`gist_seg_ops` is R-tree-over-GiST**, supporting the full positional
  operator set: `<<` (strictly left, `b<c`), `>>` (strictly right, `a>d`),
  `&<` (does not extend right, `b<=d`), `&>` (does not extend left, `a>=c`),
  `=`, `&&` (overlap), `@>` (contains), `<@` (contained-by). [from-docs]
- **Scalar comparison is lexicographic on the endpoint pair**: `<`,`>`,`<=`,`>=`
  compare lower bounds `(a)` vs `(c)` first, then upper bounds `(b)` vs `(d)`.
  [from-docs]
- **Known precision wart** (documented in Notes): the `(+-)` → range conversion
  is not exact about significant digits and can add a spurious digit when the
  interval spans a power of ten (`'10(+-)1'::seg` prints `9.0 .. 11` instead of
  `9 .. 11`). Worth knowing before trusting `seg`'s round-trip text. [from-docs]
- **Functions**: `seg_lower`, `seg_upper`, `seg_center`. [from-docs]

## Links into corpus

- `access-method-apis` skill — `gist_seg_ops` is the **minimal R-tree GiST
  opclass** template (consistent/union/penalty/picksplit over a 1-D interval);
  step up to `[[docs-distilled/cube.md]]` for the N-D + KNN version, or
  `[[docs-distilled/btree-gist.md]]` for the scalar-emulation route.
- `[[docs-distilled/gist.md]]` — the GiST support-function contract these
  opclasses fill.
- Contrast with the built-in `range` types (`int4range`/`numrange`): `seg`
  predates them and shows the hand-rolled interval-type approach.
