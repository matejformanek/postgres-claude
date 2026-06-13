# Issues — `ecpg` (embedded SQL preprocessor + runtime)

Per-subsystem issue register. See `knowledge/issues/README.md` for the
tag convention, severity scale, and workflow.

**Parent subsystem doc:** none yet (`knowledge/subsystems/ecpg.md` is a
future candidate). Covers `src/interfaces/ecpg/` — the runtime client
libraries (`ecpglib`, `pgtypeslib`, `compatlib`) and, later, the
`preproc` compiler.

> **Cross-cutting theme (seeded 2026-06-12, ecpglib + pgtypeslib +
> compatlib runtime sweep).** Two systemic patterns dominate this
> subsystem's register and explain most rows below:
>
> 1. **Client forks of backend code drift.** `pgtypeslib/dt_common.c`,
>    `interval.c`, `timestamp.c`, `datetime.c`, `numeric.c` and the
>    `dt.h` header are hand-copied from `src/backend/utils/adt/` +
>    `src/include/utils/datetime.h`. Upstream fixes (overflow hardening,
>    new tz abbreviations, rounding changes) do NOT auto-propagate.
>    Every `doc-drift` / `drift` row traces to this.
> 2. **Unbounded caller-supplied output buffers.** The pgtypes/Informix
>    `*_to_asc` / `fmt_asc` / `dttoasc` / `rfmtlong` formatters write
>    into a `char *` the embedded-SQL app supplies with no length
>    argument. Safe only if the caller sized for the worst case. This is
>    the Informix/ESQL-C ABI and cannot change, but it is the subsystem's
>    main memory-safety surface.

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-12 | ecpglib/execute.c:761 | overflow | maybe | ECPGt_bool input arrays allocate `arrsize+sizeof("{}")` (=arrsize+3) but write ~2*arrsize+2; heap overflow for bool[] host arrays of size >1 (numeric array cases use asize*20 and are safe) | open | knowledge/files/src/interfaces/ecpg/ecpglib/execute.c.md §Potential issues |
| 2026-06-12 | ecpglib/execute.c:1649 | leak | maybe | `ecpg_execute` returns false on result-check / register-prepared failure without `PQclear(stmt->results)`; `free_statement` never clears it → one PGresult leaks per failed statement | open | knowledge/files/src/interfaces/ecpg/ecpglib/execute.c.md §Potential issues |
| 2026-06-12 | ecpglib/execute.c:1888 | robustness | nit | PGRES_COPY_OUT data printf'd to stdout unconditionally, no return-value check; surprising for apps with closed/redirected stdout | open | knowledge/files/src/interfaces/ecpg/ecpglib/execute.c.md §Potential issues |
| 2026-06-12 | ecpglib/prepare.c:592 | lifetime | maybe | `AddStmtToCache` stores connection-name pointer by reference (not copied); `ecpg_freeStmtCacheEntry` derefs it later — dangles if caller passes transient storage | open | knowledge/files/src/interfaces/ecpg/ecpglib/prepare.c.md §Potential issues |
| 2026-06-12 | ecpglib/prepare.c:37 | concurrency | maybe | Global `stmtCacheEntries` / `nextStmtID` mutated without locking in `ecpg_auto_prepare`/`AddStmtToCache` — races across threads using auto-prepare | open | knowledge/files/src/interfaces/ecpg/ecpglib/prepare.c.md §Potential issues |
| 2026-06-12 | ecpglib/prepare.c:589 | leak | nit | Global statement-cache array + `ecpgQuery` strings never freed at process shutdown; only freed on eviction/reuse | open | knowledge/files/src/interfaces/ecpg/ecpglib/prepare.c.md §Potential issues |
| 2026-06-12 | ecpglib/misc.c:535 | threadsafety | maybe | Global `ivlist` linked list mutated by `ECPGset_var` / read by `ECPGget_var` with no mutex (unlike the per-thread sqlca); concurrent use can corrupt the list | open | knowledge/files/src/interfaces/ecpg/ecpglib/misc.c.md §Potential issues |
| 2026-06-12 | ecpglib/misc.c:231 | infoleak | nit | `ECPGdebug` trace writes SQL/transaction text + sqlca state to a caller-supplied FILE; opt-in, caller owns file permissions | open | knowledge/files/src/interfaces/ecpg/ecpglib/misc.c.md §Potential issues |
| 2026-06-12 | ecpglib/data.c:170 | overflow | nit | `ecpg_hex_decode` returns `(unsigned)-1` on odd-length/truncated hex, stored directly into `variable->len` at data.c:521 | open | knowledge/files/src/interfaces/ecpg/ecpglib/data.c.md §Potential issues |
| 2026-06-12 | ecpglib/data.c:387 | truncation | nit | `strtol` result cast to `(short)`/`(int)` with no range check; out-of-range values silently wrap | open | knowledge/files/src/interfaces/ecpg/ecpglib/data.c.md §Potential issues |
| 2026-06-12 | ecpglib/data.c:458 | locale | nit | `strtod` float parse is LC_NUMERIC-dependent; a comma-locale process mis-parses dot-formatted server floats | open | knowledge/files/src/interfaces/ecpg/ecpglib/data.c.md §Potential issues |
| 2026-06-12 | ecpglib/descriptor.c:706 | robustness | nit | `ECPGset_desc` ignores `set_int_item` return for indicator/length/precision/scale/type; a non-numeric host var raises internally yet the function still returns true (asymmetric with the GET side) | open | knowledge/files/src/interfaces/ecpg/ecpglib/descriptor.c.md §Potential issues |
| 2026-06-12 | ecpglib/sqlda.c:65 | overflow | nit | SQLDA size pass accumulates offsets in signed long with no overflow/saturation guard before `ecpg_alloc`; pathological column count/width could wrap and undersize the allocation | open | knowledge/files/src/interfaces/ecpg/ecpglib/sqlda.c.md §Potential issues |
| 2026-06-12 | ecpglib/sqlda.c:341 | robustness | nit | Numeric value parsed independently in size pass and fill pass; no assertion ties the two digit-buffer lengths, so a parse divergence would overflow the reserved tail | open | knowledge/files/src/interfaces/ecpg/ecpglib/sqlda.c.md §Potential issues |
| 2026-06-12 | ecpglib/typename.c:67 | dead-path | nit | `ecpg_type_name()` calls `abort()` on an unrecognized `ECPGttype` (hard client crash); only reachable if a new `ECPGt_*` code is added without a case here | open | knowledge/files/src/interfaces/ecpg/ecpglib/typename.c.md §Potential issues |
| 2026-06-12 | ecpglib/error.c:258 | infoleak | nit | `ecpg_raise_backend` copies server `PG_DIAG_MESSAGE_PRIMARY` verbatim into client-visible `sqlerrmc`; by-design, length-bounded, no memory bug | open | knowledge/files/src/interfaces/ecpg/ecpglib/error.c.md §Potential issues |
| 2026-06-12 | ecpglib/connect.c:130 | question | nit | `ecpg_finish` list-walk dereferences `con->next` with no explicit non-empty guard (safe only via the reachability invariant) | open | knowledge/files/src/interfaces/ecpg/ecpglib/connect.c.md §Potential issues |
| 2026-06-12 | ecpglib/connect.c:683 | undocumented-invariant | nit | autocommit + `PQsetNoticeReceiver` set after mutex unlock while connection already linked and name-discoverable; ordering contract unstated | open | knowledge/files/src/interfaces/ecpg/ecpglib/connect.c.md §Potential issues |
| 2026-06-12 | pgtypeslib/numeric.c:181 | overflow | maybe | Parsed exponent (±INT_MAX/2) inflates weight; `res_ndigits = rscale+weight+1` can int-overflow or request a huge `digitbuf_alloc` with no pre-alloc bound check | open | knowledge/files/src/interfaces/ecpg/pgtypeslib/numeric.c.md §Potential issues |
| 2026-06-12 | pgtypeslib/numeric.c:1334 | correctness | nit | `PGTYPESnumeric_from_long` negates `abs_long_val` for `LONG_MIN` (signed-overflow UB), mishandling that one input value | open | knowledge/files/src/interfaces/ecpg/pgtypeslib/numeric.c.md §Potential issues |
| 2026-06-12 | pgtypeslib/dt_common.c:756 | bounds | maybe | `EncodeDateTime`/`EncodeDateOnly` emit via chained `sprintf` into a caller `char *` with no size arg; safe only if the caller sizes for the BC+fsec+MAXTZLEN worst case | open | knowledge/files/src/interfaces/ecpg/pgtypeslib/dt_common.c.md §Potential issues |
| 2026-06-12 | pgtypeslib/dt_common.c:20 | undocumented-invariant | maybe | `datetktbl[]`/`deltatktbl[]` (~400 entries) have no build-time sortedness assertion; `datebsearch` assumes ASCII order, a mis-ordered insert fails silently | open | knowledge/files/src/interfaces/ecpg/pgtypeslib/dt_common.c.md §Potential issues |
| 2026-06-12 | pgtypeslib/dt_common.c:1115 | correctness | nit | Sub-second parse truncates the 7th fractional digit where backend `datetime.c` rounds — client/server can differ by 1us on the same literal (in-code XXX) | open | knowledge/files/src/interfaces/ecpg/pgtypeslib/dt_common.c.md §Potential issues |
| 2026-06-12 | pgtypeslib/dt_common.c:1 | doc-drift | nit | Whole file is a client fork of backend `datetime.c`; new tz abbreviations / reserved words / fixes upstream don't propagate unless manually mirrored | open | knowledge/files/src/interfaces/ecpg/pgtypeslib/dt_common.c.md §Potential issues |
| 2026-06-12 | pgtypeslib/datetime.c:168 | bounds | maybe | `PGTYPESdate_fmt_asc` takes no output-buffer size; `strcpy` + in-place token expansion can overflow the caller buffer | open | knowledge/files/src/interfaces/ecpg/pgtypeslib/datetime.c.md §Potential issues |
| 2026-06-12 | pgtypeslib/datetime.c:704 | correctness | nit | `PGTYPESdate_defmt_asc` misses leap-year check; Feb 29 in a non-leap year is silently normalized via `date2j` instead of erroring | open | knowledge/files/src/interfaces/ecpg/pgtypeslib/datetime.c.md §Potential issues |
| 2026-06-12 | pgtypeslib/datetime.c:681 | robustness | nit | `defmt_asc` does not validate year range before `date2j`; 2-digit year taken literally | open | knowledge/files/src/interfaces/ecpg/pgtypeslib/datetime.c.md §Potential issues |
| 2026-06-12 | pgtypeslib/timestamp.c:798 | overflow | nit | `PGTYPEStimestamp_sub` does unchecked int64 `(*ts1 - *ts2)`, can overflow without detection | open | knowledge/files/src/interfaces/ecpg/pgtypeslib/timestamp.c.md §Potential issues |
| 2026-06-12 | pgtypeslib/timestamp.c:894 | overflow | nit | `PGTYPEStimestamp_add_interval` does unguarded `*tin += span->time`, no overflow guard or post-add `IS_VALID_TIMESTAMP` recheck | open | knowledge/files/src/interfaces/ecpg/pgtypeslib/timestamp.c.md §Potential issues |
| 2026-06-12 | pgtypeslib/timestamp.c:547 | correctness | nit | `%s` epoch conversion divides by `1000000.0` (float), losing precision for large second counts | open | knowledge/files/src/interfaces/ecpg/pgtypeslib/timestamp.c.md §Potential issues |
| 2026-06-12 | pgtypeslib/interval.c:981 | overflow | nit | `tm2interval` int64 usec packing never range-checked; `tm` field `+=` accumulation in `DecodeInterval` unchecked; only month guarded | open | knowledge/files/src/interfaces/ecpg/pgtypeslib/interval.c.md §Potential issues |
| 2026-06-12 | pgtypeslib/interval.c:445 | robustness | nit | years-months `strtoint` checks `errno==ERANGE` without resetting `errno=0` first; a stale ERANGE is observable | open | knowledge/files/src/interfaces/ecpg/pgtypeslib/interval.c.md §Potential issues |
| 2026-06-12 | pgtypeslib/common.c:80 | robustness | nit | `pgtypes_fmt_replace` returns mixed `-1` / `ENOMEM` (positive) on failure paths; callers testing `== -1` miss the OOM case | open | knowledge/files/src/interfaces/ecpg/pgtypeslib/common.c.md §Potential issues |
| 2026-06-12 | pgtypeslib/dt.h:88 | doc-drift | nit | `dt.h` is a manual copy of backend `src/include/utils/datetime.h`; `DTK_*`/field-type renumbering upstream is not auto-propagated | open | knowledge/files/src/interfaces/ecpg/pgtypeslib/dt.h.md §Potential issues |
| 2026-06-12 | pgtypeslib/pgtypeslib_extern.h:24 | dead-path | nit | `PGTYPES_TYPE_UINT_LONG` + `un_fmt_comb.luint_val` declared but unreferenced by the `pgtypes_fmt_replace` switch | open | knowledge/files/src/interfaces/ecpg/pgtypeslib/pgtypeslib_extern.h.md §Potential issues |
| 2026-06-12 | compatlib/informix.c:660 | bounds | maybe | `dttoasc` unbounded `strcpy` AND no NULL-check on `PGTYPEStimestamp_to_asc` result (NULL-deref on OOM); sibling `intoasc` does check — a real asymmetry | open | knowledge/files/src/interfaces/ecpg/compatlib/informix.c.md §Potential issues |
| 2026-06-12 | compatlib/informix.c:787 | bounds | maybe | `rfmtlong` temp sized `fmt_len+1` and outbuf written via reverse-strcat with no caller-buffer bound; assumes 1 out char per fmt char | open | knowledge/files/src/interfaces/ecpg/compatlib/informix.c.md §Potential issues |
| 2026-06-12 | compatlib/informix.c:516 | bounds | nit | `rdatestr` `strcpy` of `PGTYPESdate_to_asc` into caller buffer with no len bound | open | knowledge/files/src/interfaces/ecpg/compatlib/informix.c.md §Potential issues |
| 2026-06-12 | compatlib/informix.c:682 | bounds | nit | `intoasc` unbounded `strcpy` into caller buffer (NULL is checked) | open | knowledge/files/src/interfaces/ecpg/compatlib/informix.c.md §Potential issues |
| 2026-06-12 | compatlib/informix.c:760 | robustness | nit | `getRightMostDot` narrows `size_t len` to `int` in its return; fragile for very long fmt strings | open | knowledge/files/src/interfaces/ecpg/compatlib/informix.c.md §Potential issues |
| 2026-06-12 | compatlib/informix.c:988 | dead-path | nit | `rgetmsg`/`rtypalign`/`rtypmsize`/`rtypwidth` are no-op stubs returning 0; struct-layout callers get wrong answers | open | knowledge/files/src/interfaces/ecpg/compatlib/informix.c.md §Potential issues |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|
| | | | | | |

## Notes

- **Severity calibration.** Most rows are `nit` — the unbounded-buffer
  formatters are the documented Informix/ESQL-C ABI, not bugs to fix;
  they sit here as a known memory-safety surface. The handful of `maybe`
  rows worth a real second read: `execute.c:761` (bool-array heap write
  on a plausible input shape), `execute.c:1649` (PGresult leak per failed
  statement), `numeric.c:181` (exponent-driven allocation sizing),
  `dt_common.c:20` (token-table sortedness with no build-time guard),
  `informix.c:660` (NULL-deref asymmetry vs the sibling routine), and
  `prepare.c:592`/`:37` (auto-prepare cache lifetime + threadsafety).
- **Before acting on any `overflow`/`bounds` row, diff against current
  master.** These files are forks of backend code; the backend may have
  already hardened the same arithmetic, in which case the finding becomes
  a `doc-drift` "fork has lagged" item rather than a live bug.
- None of these were promoted to a patch in this run — they're corpus
  notebook entries, surfaced during the 2026-06-12 ecpg runtime sweep.
