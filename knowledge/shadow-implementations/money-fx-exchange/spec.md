---
slug: money-fx-exchange
thread-url: https://www.postgresql.org/message-id/flat/ea43df01-019b-4365-a47e-f2577d22c0f9%40app.fastmail.com
first-message-url: https://www.postgresql.org/message-id/ea43df01-019b-4365-a47e-f2577d22c0f9%40app.fastmail.com
author: Joel Jacobson <joel@compiler.org>
captured-at: 2026-06-12
captured-anchor: e18b0cb7344
posted-at: 2026-04-01T07:00:15
shadow-run-status: SPEC EXTRACTED; PATCH BODY NOT FETCHED (archive 503)
---

# Spec extracted from pgsql-hackers thread

## What this does (verbatim claim from COVER)

Adds foreign-exchange (FX) rate support to PostgreSQL's `money` type.
The `money` type has been heavily criticized for its limitations (was
debated at Nordic PGDay 2026). Rather than deprecating it, the patch
proposes adding currency exchange rate conversion to the value path.

**Claimed design (from COVER):**

- New GUC `money_source_currency` (`'USD'` etc.) — declares the
  source currency for stored monetary values.
- The output formatter (`money_out` / `cash_out` / equivalent) detects
  whether the `lc_monetary` locale's currency differs from
  `money_source_currency`, and if so, looks up an exchange rate
  to perform conversion at output time.
- Exchange-rate lookup is per-session-cached. First lookup hits
  `https://api.frankfurter.app/` via libcurl; subsequent lookups
  in the same session re-use the cached rate.
- Cache should be extensible to a shared persistent disk-backed
  cache surviving reconnects + restarts.
- The frankfurter URL is hardcoded for the PoC; "should be made
  configurable via new GUC", "Configuration should support multiple
  API URLs for redundancy."

**Example session from COVER:**

```sql
SET money_source_currency = 'USD';
SET lc_monetary = 'sv_SE.UTF-8';
SELECT 100::money AS usd;
-- usd
-- ---------
-- 949,67 kr    (~38ms first time, <1ms cached)
```

## Touched subsystems (per our `domain-ownership.md` lookup)

- `src/backend/utils/adt/cash.c` — the `money` type I/O functions
- `src/backend/utils/misc/guc_tables.c` — new GUC registration
- `src/include/utils/cash.h` (if exists) or `pg_proc.dat` for any
  new C functions
- (NEW external dependency surface) `libcurl` — already linked since
  the PG 18 OAuth work, per `daniel-gustafsson.md` Phase B persona

Owners (per `domain-ownership.md`): the `utils-adt` cluster — no
single owner; Tom Lane reviews everything in this area, Peter
Eisentraut + Dean Rasheed for the type-system shape, Daniel
Gustafsson for the libcurl side (he landed the OAuth libcurl).

## Predicted reviewer set (per Phase C calibration patterns)

| Rank | Reviewer | Why |
|---|---|---|
| 1 | Tom Lane | Universal reviewer for `utils/adt/`; type-I/O-function contract reviewer. **He will reject this design — see plan.** |
| 2 | Peter Eisentraut | Type-system + style |
| 3 | Dean Rasheed | Type / numeric reviewer |
| 4 | Daniel Gustafsson | libcurl knowledge |
| 5 | Andreas Karlsson | Per archive reply, said "thanks, add to commitfest" — pragmatic engagement |
| 6 | Noah Misch | Will flag the security-implications of network calls in type I/O |

## Author's stated claims (verbatim)

- Files affected: not explicitly enumerated; cover names `money_out`,
  the GUC, and the cache. Diff stat in the patch body (`0001-Add-fx-
  exchange-support-to-money-type.patch`, 15.3 KB) not fetched.
- Behavior delta: output formatter triggers network fetch when source
  currency ≠ locale currency.
- Test plan: not stated. Per-session cache implied to be tested via the
  before/after time measurements.
- Backpatch: not stated.

## Open questions raised in thread before this shadow run

Andreas Karlsson's reply (2026-04-01T14:40:42):

> "Thanks for the patch! It is very late in the release cycle for 19
>  but you could add it to the next commitfest. Always nice to see
>  some interest in the money type, I have some own ideas for it for
>  PostgreSQL 20."

No technical pushback in the thread. The patch posting was on
**2026-04-01 (April Fools' Day)** — context that future PG-archive
miners should account for. Karlsson's reply is professionally
deadpan and does not engage with the design.

## Phase 0 gates that apply (per `review-checklist` Phase 0)

| Gate | Triggers? | Note |
|---|---|---|
| 1 `security@` embargo | ✗ | Not a vulnerability fix; a feature proposal. |
| 2 Test-omission | partial | COVER doesn't mention regression tests; the planner will flag this in plan §3. |
| 3 Install-script immutability | ✗ | No `--*.sql` changes |

## Methodology note

Step 4 of the shadow-implementation methodology (Ground truth fetch)
**failed for this run** — the `.patch` attachment URL returned 503
from the postgres-archive Varnish cache after one retry. Comparison
proceeds at the design level only, using the COVER's stated
design as the ground truth. This is logged as Phase E methodology
finding #1.
