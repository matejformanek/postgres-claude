# controldata.c

## Purpose

Extracts the OLD and NEW cluster's `pg_control` state by parsing the
text output of `pg_controldata` and `pg_resetwal -n`. Provides
`get_control_data()` (line 39), `check_control_data()` (line 699), and
`disable_old_cluster()` (line 764). Unlike A5's controldata_utils.c
which reads the binary `global/pg_control` directly, pg_upgrade goes
through the version-appropriate text-emitting binaries — because the
on-disk layout differs across major versions.

## Role in pg_upgrade

Called once per cluster from `pg_upgrade.c::setup`. Populates
`cluster->controldata` (a `ControlData` struct of ~27 fields). Then
`check_control_data(&old.ctrl, &new.ctrl)` enforces compatibility
constraints. `disable_old_cluster()` is called late: renames
`<old_pgdata>/global/pg_control` → `pg_control.old` to prevent
accidental restart of the OLD cluster after link/swap mode upgrade.

## Approach

[from-comment, line 30-37] "The approach taken here is to invoke
pg_resetwal with -n option and then pipe its output." pg_controldata
covers the `--check` mode (server can be running). pg_resetwal is
needed to also get xid data for the actual upgrade.

So:
- `--check` + `live_check`: skip the first `pg_controldata` call;
  only run `pg_controldata` (not pg_resetwal).
- Real run on old cluster: pg_controldata for cluster-state, then
  pg_resetwal -n for the full field set.
- New cluster: same as real-run.

## Wire/parse surface

Lines 137-176: pg_controldata output. Parsed by `strstr` then `strchr
(p, ':')`. The cluster state must be one of `"shut down"` (good),
`"shut down in recovery"` (fatal, use rsync) or otherwise fatal.

Lines 213-527: pg_resetwal -n output. ~24 distinct `strstr` matches
populating `cluster->controldata.{ctrl_ver, cat_ver, chkpnt_*, align,
blocksz, ...}`. Each match path is uniform: find substring, find ':',
advance past, `str2uint(p)`. Exceptions:
- `Latest checkpoint's NextXID:` (line 273): delimiter is `/` (pre-9.6)
  or `:` (9.6+); handled by `strchr` fallback.
- `First log segment after reset:` (line 358): scanned with
  `strpbrk(p, "0123456789ABCDEF")` then validated as 24-hex.
- `Float8 argument passing:` (line 375): boolean from `strstr(p, "by
  value") != NULL`.
- `Date/time type storage:` (line 486): boolean from `strstr(p,
  "64-bit integers")`.
- `Default char data signedness:` (line 508): must be exactly
  `"signed"` or `"unsigned"`, with whitespace-skipping.

## Locale-handling

Lines 89-121: saves LC_*, LANG, LANGUAGE, LC_ALL, LC_MESSAGES env
vars, unsets them, force-sets `LC_MESSAGES=C` so pg_controldata
emits English label strings (which the parse logic depends on). On
Windows, `LANG=en` is forced. Restored at lines 538-559.

## Validation

Lines 602-689: explicit field-by-field "did we get this?" check,
catalog-version-conditional for fields added later (oldestmulti,
large_object, default_char_signedness).

`check_control_data` (line 699) enforces hard-equality on:
- align, blocksz, largesz, walsz, walseg, ident, index, toast,
  large_object (post-9.5).
- date_is_int (storage type) — must match.
- data_checksum_version — both must be off, or both on with same
  version; in-progress states are fatal.

## State / globals

None. Writes through `cluster->controldata`. Saves and restores
process env vars temporarily.

## Phase D notes

[from-code] **No CRC check.** The pg_controldata utility itself
verifies pg_control's CRC; pg_upgrade trusts the utility's parse
output. So same trust boundary as A5 controldata_utils — there is no
torn-write window here because the file is read by a separate process
that does CRC, and only the text is consumed by pg_upgrade. Differs
from A5 in that the binary read isn't done in-process.

[ISSUE-trust-boundary: pg_resetwal -n output is parsed by string
match without strict format validation; a substring like "Latest
checkpoint's NextXID:" inside an error message would be picked up
(maybe-low)] — `controldata.c:273` and similar. Mitigation:
pg_resetwal is a sibling binary in the SAME bindir, version-locked
by check_bin_dir (exec.c:384). If the operator hasn't substituted a
malicious binary in the OLD cluster's bindir, the format is fixed.

[ISSUE-trust-boundary: the old cluster's bindir contains the
pg_controldata + pg_resetwal that pg_upgrade `popen`s; a malicious
OLD cluster's bindir = code execution (by design)] —
`controldata.c:130,197`. Operator must trust the bindir they pass to
pg_upgrade's `-b/-B`.

[ISSUE-correctness: `str2uint(p)` is `strtoul(p, NULL, 10)` —
silently returns 0 on garbage and 0 also on legitimate "0" values
(low)] — Many fields can't legitimately be 0 (block size, etc.) so
the `check_control_data` checks catch most mis-parses (line 702,
706 etc. all explicitly test `== 0`).

[from-code] **Char-signedness inference for pre-v18 clusters** (line
592-600) — uses the *build-time* `CHAR_MIN != 0` test on the
pg_upgrade binary itself. So if pg_upgrade was built on a platform
where char is signed, it ASSUMES the pre-v18 cluster's char was
also signed. This is documented as a known limitation; running
pg_upgrade compiled on a different signedness than the old cluster
was compiled on can be wrong.

[ISSUE-correctness: char-signedness assumption is the pg_upgrade
binary's build-time, not the old cluster's runtime (medium-by-
design)] — `controldata.c:592-599`. The Assert at line 594 confirms
the field wasn't read from old cluster (because old < v18); the
inference is platform-platform-equality based.

[from-code] **`disable_old_cluster`** (line 764): `pg_mv_file(...
/pg_control, .../pg_control.old)`. NOT a CRC verification — just a
rename. Means if the rename succeeds but a subsequent step fails,
the old cluster is intentionally bricked (re-runnable by reversing
the rename). Comment lines 781-787 document this for link mode;
also for swap mode at line 789.

[ISSUE-state-transition: `disable_old_cluster` makes the old cluster
unstartable without a recovery step; if pg_upgrade aborts after this
the operator must manually rename .old back (by-design, documented)]
— `controldata.c:773-777`.

[from-code] **Data-checksum compatibility** (line 745-759):
- `oldctrl->data_checksum_version > PG_DATA_CHECKSUM_VERSION` →
  "checksums are being enabled in the old cluster" (refers to the
  online enabling-in-progress state introduced in v18+).
- off↔on mismatch in either direction → fatal.
- version mismatch (rare; PG_DATA_CHECKSUM_VERSION has only ever
  been 1) → fatal.

[ISSUE-undocumented-invariant: `oldctrl->large_object != 0` test
(line 728) is a special "pre-9.5 doesn't have this field" check; if
a future version makes 0 a legitimate value, the test misfires
(low)] — `controldata.c:728`.

[from-code] **`float8_pass_by_value`** is NOT required to match
(comment line 736-738). Used elsewhere for ISN extension check.

[ISSUE-secret-scrub: PG_VERBOSE-mode logs every parsed line via
`pg_log(PG_VERBOSE, "%s", bufin)` (line 218) — pg_controldata output
contains LC_COLLATE/LC_CTYPE/LC_TIME values which could include
locale paths (low)] — `controldata.c:218`. Only with `-v` enabled.

[ISSUE-undocumented-invariant: the `else if` chain (lines 220-526)
is order-INDEPENDENT but the `else if` form means each line gets at
most ONE match; if a future pg_controldata changes a header to
contain another header's substring (e.g. "Latest checkpoint's
NextOID before:") the wrong field would be parsed (low)] —
`controldata.c:220`.

[from-code] **No partial-read tolerance.** `fgets` returning EOF
ends the parse; if pg_controldata crashes mid-output you get a
partial parse and the "lacks some required control information"
fatal at line 688 catches it. Defense-in-depth.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_upgrade`](../../../../issues/pg_upgrade.md)
<!-- issues:auto:end -->
