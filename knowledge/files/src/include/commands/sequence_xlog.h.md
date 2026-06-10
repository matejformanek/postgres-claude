# src/include/commands/sequence_xlog.h

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Lines:** 45 [verified-by-code]

## Role

WAL record definitions for sequence updates (`RM_SEQ_ID`). Carries the
post-nextval state of a sequence tuple onto WAL so standbys can
materialize the same `currval` and so post-crash recovery preserves the
"sequences never go backwards" guarantee.

## Public API

- `XLOG_SEQ_LOG` = `0x00` — the only record kind (`:21`).
- `SEQ_MAGIC` = `0x1717` — special-area magic on every sequence page
  (`:26`).
- `sequence_magic` — single-`uint32` struct embedded in the page's
  special area (`:28-31`).
- `xl_seq_rec` — `RelFileLocator locator` followed by raw sequence
  tuple bytes (`:34-38`).
- Redo trio + tuple mask: `seq_redo`, `seq_desc`, `seq_identify`,
  `seq_mask` (`:40-43`).

## Invariants

- INV-SEQ-MAGIC: every page in a sequence relation has the
  `sequence_magic` at offset `PageGetSpecialPointer(page)`; mismatch
  on read indicates either page corruption OR the file is not actually
  a sequence (smgr-level mistake). The magic `0x1717` is fixed since
  PG7-ish; never changed.
- INV-SEQ-XLOG-FLUSH: nextval batches updates — every Nth call (where
  N = sequence's `cache_value`) emits one `XLOG_SEQ_LOG` covering the
  high-water mark of issued values. Crash recovery may "lose" the
  intra-cache numbers — sequences are NOT guaranteed gapless.
- `xl_seq_rec.locator` identifies which sequence; the trailing tuple
  bytes are a full HeapTuple (xmin/xmax/etc.) so redo can reinstate it.

## Notable internals

- `seq_mask` is the page-image masking function used by `wal_consistency
  _checking` — masks out fields that change without WAL logging
  (e.g. hint bits).
- `seq_identify` returns a string for `pg_waldump` output; standard
  pattern.

## Trust boundary / Phase D surface

- **A8 replication echo.** Standby replays `seq_redo` and bumps its
  sequence to the master's high-water — failover guarantees no
  duplicate IDs. A hostile WAL stream injecting a forged sequence
  record with `last_value=0` could **rewind** a sequence on a
  standby, leading to duplicate-key inserts after failover. Defense:
  WAL stream authenticity (TLS + replication privilege).
- The `RelFileLocator` is trusted — redo opens that relfilenode and
  overwrites its first page. A WAL stream pointing at a non-sequence
  relfilenode would corrupt that relation.

## Cross-references

- `commands/sequence.h` — front-end nextval / setval API.
- `access/rmgrlist.h` — `RM_SEQ_ID` rmgr table entry (A17 sibling).
- `backend/commands/sequence.c` — `seq_redo` implementation,
  `nextval_internal` WAL emission.
- `access/xlogreader.h`, `lib/stringinfo.h` — included.

## Issues / drift

- `[ISSUE-TRUST: A8 — forged sequence WAL record could rewind sequence on standby; mitigated only by stream-level auth (medium)] — source/src/include/commands/sequence_xlog.h:34-43`
- `[ISSUE-DOC: SEQ_MAGIC 0x1717 not explained anywhere visible — historical pun on year/joke; harmless but mysterious (low)] — source/src/include/commands/sequence_xlog.h:26`
