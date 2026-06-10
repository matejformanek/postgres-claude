# `access/stratnum.h` — index AM strategy-number constants

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/access/stratnum.h`)

## Role
Small integer codes that name operators within an operator family. Every
index AM exports a fixed (or extensible) set of strategy numbers; an opclass
maps each strategy to a real SQL operator. Strategies are the "language" the
planner uses to ask "does this index support `<=`?".

## Public API
- `StrategyNumber` typedef = `uint16` (`stratnum.h:22`).
- `InvalidStrategy = 0` (`stratnum.h:24`).
- B-tree (`stratnum.h:29`-`35`): `BTLessStrategyNumber = 1`,
  `BTLessEqualStrategyNumber = 2`, `BTEqualStrategyNumber = 3`,
  `BTGreaterEqualStrategyNumber = 4`, `BTGreaterStrategyNumber = 5`,
  `BTMaxStrategyNumber = 5`.
- Hash (`stratnum.h:41`-`43`): `HTEqualStrategyNumber = 1`,
  `HTMaxStrategyNumber = 1`.
- R-Tree / GiST / SP-GiST / BRIN (`stratnum.h:51`-`82`):
  `RTLeftStrategyNumber = 1` (`<<`) through
  `RTOldAboveStrategyNumber = 30` (`|>>` old spelling),
  `RTMaxStrategyNumber = 30`.

## Invariants
- B-tree strategy numbers encode the **order** of operators on the number
  line: 1=<, 2=<=, 3==, 4=>=, 5=>. This ordering is exploited by btree
  page-traversal code (e.g., to decide whether to keep walking right).
  `[verified-by-code]` (`stratnum.h:29`-`33`; usage in `_bt_first` etc.).
- Hash supports **only** equality. `[from-comment]` (`stratnum.h:38`-`39`).
- R-Tree strategies started at the original 8 (overlap, contained, etc.)
  and have grown by accretion — gaps (13/14 marked "old spelling") and
  non-sequential semantics make this set heterogeneous. `[from-comment]`
  (`stratnum.h:46`-`50`, `:63`-`64`, `:79`-`80`).
- `StrategyNumber` is `uint16` ⇒ space for up to 65535 strategies, but
  `amvalidate.h`'s 64-bit bitmask cap (see that file) effectively limits
  practical opfamily designs to ≤64 strategies per type pair.
  `[verified-by-code]` (`stratnum.h:22`).
- The 5-element btree set is referenced via `BTMaxStrategyNumber` rather
  than 5 directly; new AMs should follow that pattern.
  `[from-comment]` `stratnum.h:35`.

## Notable internals
- The "compare type" abstraction (`cmptype.h`) was added so non-btree AMs
  could speak in generalized terms ("less than") and AM-specific code
  translates to strategy numbers via `amtranslatestrategy` /
  `amtranslatecmptype` (see `amapi.h:107`-`110`). This decouples planner
  expressions from AM strategy encoding.
- R-Tree strategies 13/14/29/30 are legacy aliases for old operator spellings
  — kept for backward compat with extensions.

## Trust-boundary / Phase D surface

This header is purely constants — no runtime behavior. The Phase D risk
is **semantic** rather than memory-safe:

**[ISSUE-correctness: strategy assignment is semantic — type-specific
comparator can disagree with the strategy label (informational)]** —
An opclass mapping `BTLessStrategyNumber` to an operator whose semantics
aren't actually "less than" produces wrong index scan results. This is
the root cause of A13/A14 corpus findings on collation-pin and NaN
clusters: the comparator's `<` doesn't match SQL's `<` everywhere.
`stratnum.h:29`-`33`. amvalidate cannot catch this; only behavioral
testing does.

**[ISSUE-api-shape: R-Tree strategy block is heterogeneous and grown
by accretion (informational)]** — 30 values in three semantic clusters
(geometric, range, network/inet, text-prefix) make this a brittle
namespace. A new AM adopting "RT" strategies must check each value's
documented operator. `stratnum.h:51`-`82`.

## Cross-refs
- `knowledge/files/src/include/access/amapi.h` —
  `amtranslate_strategy_function` and `amtranslate_cmptype_function`.
- `knowledge/files/src/include/access/amvalidate.h` — checks pg_amop
  strategy numbers fit the AM's declared range.
- `access/cmptype.h` (not in this slice) — `CompareType` abstraction.
- A13/A14 corpus findings: collation pin, NaN cluster — strategy
  semantics mismatch.

## Issues
1. **[ISSUE-correctness: strategy semantics are convention-only, not enforced (informational)]**
   — `stratnum.h:29`-`33`.
2. **[ISSUE-api-shape: RT strategy block is heterogeneous, accretive (informational)]**
   — `stratnum.h:51`-`82`.
