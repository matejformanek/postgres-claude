# Hash bucket split — incremental redistribution with cleanup locks + deferred cleanup

When a hash index's `hashm_ntuples / (hashm_maxbucket + 1)` exceeds
the fillfactor, an insert triggers `_hash_expandtable` which splits
**one bucket** (the linear-hashing successor of `maxbucket`'s
lowmask predecessor) and creates a new bucket. The split:

1. Cleanup-locks the source bucket (and the to-be-allocated target).
2. Updates metapage masks (possibly starts a new doubling phase).
3. Iterates the source bucket's pages, computing each tuple's new
   bucket; tuples mapping to the new bucket get **copied** there;
   tuples staying in the source bucket are left in place but
   **dead tuples** are not removed yet — that's deferred to the
   next cleanup pass (`H_NEEDS_SPLIT_CLEANUP` flag).
4. Sets `LH_BUCKET_BEING_POPULATED` on target and
   `LH_BUCKET_BEING_SPLIT` on source until done.

The deferred-cleanup model is the **key concurrency win**: scans
that started before the split can keep reading from the source
bucket without interference. The split copies (doesn't move)
tuples to the target; the source still has them. Only a later
cleanup pass — once all old scans have drained — removes the
duplicates from the source.

This doc covers `_hash_expandtable`'s fill-factor + maxbucket
gates, the four-state bucket flag transitions, the cleanup-lock
acquisition (and the **retry-finish-pending-split** path), the
mask-update logic when crossing a doubling boundary, the
`_hash_splitbucket` redistribution loop, `_hash_finish_split` for
recovering interrupted splits, and the locking-order invariant
(low-numbered bucket first, metapage last).

Companion docs:
- [[hash-page-layout]] — the addressing scheme this grows.
- [[hash-overflow-pages]] — overflow-page handling during split.

## Anchors

- `source/src/backend/access/hash/README` — "Lock Definitions" + "Bucket Split" + "Concurrency" sections.
- `source/src/backend/access/hash/hashpage.c:613-966` — `_hash_expandtable`.
- `source/src/backend/access/hash/hashpage.c:1075-1357` — `_hash_splitbucket`.
- `source/src/backend/access/hash/hashpage.c:1360-1500` — `_hash_finish_split`.
- `source/src/backend/access/hash/hashpage.c:993-1039` — `_hash_alloc_buckets` (extend file for new splitpoint).
- `source/src/backend/access/hash/hash.c` — `hashbucketcleanup` (the deferred cleanup pass).
- `source/src/include/access/hash.h:58-60` — `LH_BUCKET_BEING_POPULATED`, `_BEING_SPLIT`, `_NEEDS_SPLIT_CLEANUP`.

## The four-state lifecycle of a split

A bucket has three transient flags during a split:

| Flag                              | Set on   | When                | Cleared at                          |
|-----------------------------------|----------|---------------------|--------------------------------------|
| `LH_BUCKET_BEING_SPLIT`           | source   | start of split      | end of split / `_hash_finish_split`  |
| `LH_BUCKET_BEING_POPULATED`       | target   | start of split      | end of split                         |
| `LH_BUCKET_NEEDS_SPLIT_CLEANUP`   | source   | end of split        | next `hashbucketcleanup` pass        |

The state diagram:

```
                                 [normal]
                                    │
                       split starts │
                                    ↓
        ┌─ source: LH_BUCKET_BEING_SPLIT
        │  target: LH_BUCKET_BEING_POPULATED
        │
        │           split finishes (tuples copied to target)
        │                          │
        │                          ↓
        ├─ source: LH_BUCKET_NEEDS_SPLIT_CLEANUP
        │  target: [normal]
        │
        │           hashbucketcleanup pass (eventually)
        │                          │
        │                          ↓
        └─ source: [normal]        target: [normal]
```

[from-comment] (`hash.h:58-60`, `README` "Bucket Split").

## The cleanup-lock invariant

> A cleanup lock on a primary bucket page represents the right to
> perform an arbitrary reorganization of the entire bucket. Therefore,
> scans retain a pin on the primary bucket page for the bucket they
> are currently scanning. Splitting a bucket requires a cleanup
> lock on both the old and new primary bucket pages.

[from-comment] (`README` "Lock Definitions").

A cleanup lock is **exclusive lock + sole pin holder**. Since scans
keep a pin on the bucket page while they're walking it, the split
must wait for all scans to release before it can re-organize the
bucket. This is what makes the split safe: while it runs, no scan
is iterating the source bucket.

`_hash_getbuf_with_condlock_cleanup` (the *conditional* variant)
gives up if it can't get the cleanup lock immediately — splits
back off rather than blocking inserts. [from-comment]
(`hashpage.c:681-687`).

## `_hash_expandtable` — the entry point

```c
/* hashpage.c:613-966 (skeleton) */
void _hash_expandtable(Relation rel, Buffer metabuf)
{
restart_expand:
    LockBuffer(metabuf, BUFFER_LOCK_EXCLUSIVE);
    metap = HashPageGetMeta(BufferGetPage(metabuf));

    /* Gate 1: still need to split? (concurrent split may have finished) */
    if (metap->hashm_ntuples <= ffactor * (maxbucket + 1))
        goto fail;

    /* Gate 2: maxbucket overflow guard */
    if (metap->hashm_maxbucket >= 0x7FFFFFFE)
        goto fail;

    /* Gate 3: identify source bucket via lowmask */
    new_bucket = metap->hashm_maxbucket + 1;
    old_bucket = new_bucket & metap->hashm_lowmask;
    start_oblkno = BUCKET_TO_BLKNO(metap, old_bucket);

    /* Gate 4: cleanup-lock the source */
    buf_oblkno = _hash_getbuf_with_condlock_cleanup(rel, start_oblkno, LH_BUCKET_PAGE);
    if (!buf_oblkno) goto fail;

    oopaque = HashPageGetOpaque(BufferGetPage(buf_oblkno));

    /* Recovery path 1: source has BEING_SPLIT → finish that split first */
    if (H_BUCKET_BEING_SPLIT(oopaque)) {
        /* Snapshot mask info */
        maxbucket = metap->hashm_maxbucket;
        highmask  = metap->hashm_highmask;
        lowmask   = metap->hashm_lowmask;

        LockBuffer(metabuf, BUFFER_LOCK_UNLOCK);
        LockBuffer(buf_oblkno, BUFFER_LOCK_UNLOCK);

        _hash_finish_split(rel, metabuf, buf_oblkno, old_bucket, maxbucket, highmask, lowmask);
        _hash_dropbuf(rel, buf_oblkno);
        goto restart_expand;                                 /* retry */
    }

    /* Recovery path 2: source has NEEDS_SPLIT_CLEANUP → clean now */
    if (H_NEEDS_SPLIT_CLEANUP(oopaque)) {
        maxbucket = ...; highmask = ...; lowmask = ...;
        LockBuffer(metabuf, BUFFER_LOCK_UNLOCK);
        hashbucketcleanup(rel, old_bucket, buf_oblkno, ..., true /*split_cleanup*/);
        _hash_dropbuf(rel, buf_oblkno);
        goto restart_expand;
    }

    /* Step 1: extend the file if we're crossing a splitpoint phase */
    start_nblkno = BUCKET_TO_BLKNO(metap, new_bucket);
    spare_ndx = _hash_spareindex(new_bucket + 1);
    if (spare_ndx > metap->hashm_ovflpoint) {
        buckets_to_add = _hash_get_totalbuckets(spare_ndx) - new_bucket;
        if (!_hash_alloc_buckets(rel, start_nblkno, buckets_to_add))
            goto fail;                              /* BlockNumber overflow */
    }

    /* Step 2: allocate + cleanup-lock the new bucket's primary page */
    buf_nblkno = _hash_getnewbuf(rel, start_nblkno, MAIN_FORKNUM);
    if (!IsBufferCleanupOK(buf_nblkno)) goto fail;   /* extremely rare */

    /* Step 3: mutate the metapage under a critical section */
    START_CRIT_SECTION();
    metap->hashm_maxbucket = new_bucket;

    /* If crossing a doubling boundary, update the mask pair */
    if (new_bucket > metap->hashm_highmask) {
        metap->hashm_lowmask  = metap->hashm_highmask;
        metap->hashm_highmask = new_bucket | metap->hashm_lowmask;
        metap_update_masks = true;
    }

    /* If new splitpoint phase, carry hashm_spares[] forward */
    if (spare_ndx > metap->hashm_ovflpoint) {
        metap->hashm_spares[spare_ndx] = metap->hashm_spares[metap->hashm_ovflpoint];
        metap->hashm_ovflpoint = spare_ndx;
        metap_update_splitpoint = true;
    }
    MarkBufferDirty(metabuf);

    /* Snapshot for _hash_splitbucket */
    maxbucket = metap->hashm_maxbucket;
    highmask  = metap->hashm_highmask;
    lowmask   = metap->hashm_lowmask;

    /* Step 4: mark source + target pages */
    oopaque->hasho_flag |= LH_BUCKET_BEING_SPLIT;
    oopaque->hasho_prevblkno = maxbucket;            /* stale-cache marker */
    MarkBufferDirty(buf_oblkno);

    nopaque = HashPageGetOpaque(BufferGetPage(buf_nblkno));
    nopaque->hasho_prevblkno = maxbucket;
    nopaque->hasho_nextblkno = InvalidBlockNumber;
    nopaque->hasho_bucket = new_bucket;
    nopaque->hasho_flag = LH_BUCKET_PAGE | LH_BUCKET_BEING_POPULATED;
    nopaque->hasho_page_id = HASHO_PAGE_ID;
    MarkBufferDirty(buf_nblkno);

    /* Step 5: WAL */
    if (RelationNeedsWAL(rel)) {
        XLogRegisterBuffer(0, buf_oblkno, REGBUF_STANDARD);
        XLogRegisterBuffer(1, buf_nblkno, REGBUF_WILL_INIT);
        XLogRegisterBuffer(2, metabuf, REGBUF_STANDARD);
        if (metap_update_masks) ...;
        if (metap_update_splitpoint) ...;
        recptr = XLogInsert(RM_HASH_ID, XLOG_HASH_SPLIT_ALLOCATE_PAGE);
    }
    END_CRIT_SECTION();

    /* Step 6: drop metapage lock, keep pin */
    LockBuffer(metabuf, BUFFER_LOCK_UNLOCK);

    /* Step 7: redistribute tuples */
    _hash_splitbucket(rel, metabuf, old_bucket, new_bucket,
                      buf_oblkno, buf_nblkno, NULL,
                      maxbucket, highmask, lowmask);

    _hash_dropbuf(rel, buf_oblkno);
    _hash_dropbuf(rel, buf_nblkno);
}
```

[verified-by-code] (`hashpage.c:613-966`).

### Why finish-then-restart for `BEING_SPLIT`

> We want to finish the split from a bucket as there is no apparent
> benefit by not doing so and it will make the code complicated to
> finish the split that involves multiple buckets considering the
> case where new split also fails.

[from-comment] (`hashpage.c:700-706`).

If we land on a bucket mid-split (because the previous splitter
crashed or got interrupted), we **finish that split first** before
starting a new one. The new split happens on `restart_expand`'s
next iteration.

### Why finish-then-restart for `NEEDS_SPLIT_CLEANUP`

> Clean the tuples remained from the previous split. … we are
> always sure that the garbage tuples belong to most recently split
> bucket. On the contrary, if we allow cleanup of bucket after meta
> page is updated to indicate the new split and before the actual
> split, the cleanup operation won't be able to decide whether the
> tuple has been moved to the newly created bucket and ended up
> deleting such tuples.

[from-comment] (`hashpage.c:734-745`).

The cleanup-then-split ordering is correctness-critical: the
cleanup phase needs to assume "all duplicate-from-split tuples are
in *this* particular other bucket"; if we started another split
first, that assumption would break.

## Mask update on doubling boundary

When `new_bucket > hashm_highmask`, we've crossed a power-of-2
boundary and need to start a new doubling phase:

```c
metap->hashm_lowmask  = metap->hashm_highmask;
metap->hashm_highmask = new_bucket | metap->hashm_lowmask;
```

E.g. with 7 buckets (`highmask = 7`, `lowmask = 3`), adding the
8th bucket (`new_bucket = 7`, comparing `7 > 7` is false — no
crossover). Adding the 9th (`new_bucket = 8`, `8 > 7` true):
`lowmask = 7`, `highmask = 8 | 7 = 15`. Now the index spans 8-15
buckets logically (even though physically only 9 exist) and
lookups use `lowmask` for buckets ≥ maxbucket+1 to stay in the
old range. [verified-by-code] (`hashpage.c:838-844`).

## `_hash_splitbucket` — the redistribution loop

```c
/* hashpage.c:1075-1357 (skeleton) */
static void _hash_splitbucket(Relation rel, Buffer metabuf,
                              Bucket obucket, Bucket nbucket,
                              Buffer obuf, Buffer nbuf, HTAB *htab,
                              uint32 maxbucket, uint32 highmask, uint32 lowmask)
{
    /* Walk all pages of source bucket (primary + overflow chain) */
    obucket_page = obuf;
    for each page in obucket's chain:
        for each tuple on page:
            hashkey = _hash_get_indextuple_hashkey(tuple);
            target = _hash_hashkey2bucket(hashkey, maxbucket, highmask, lowmask);

            if (target == nbucket) {
                /* Belongs in new bucket — COPY it there */
                if (!htab || !found in htab) {
                    if (no space in nbuf) {
                        /* Need to add overflow page to new bucket */
                        nbuf_new = _hash_addovflpage(rel, metabuf, nbuf, ...);
                        nbuf = nbuf_new;
                    }
                    PageAddItem(nbuf, tuple, ...);
                }
                /* Tuple stays in source bucket too (will be cleaned up later) */
            } else {
                /* Stays in old bucket */
            }

    /* Mark source bucket as needing cleanup, target as normal */
    oopaque->hasho_flag &= ~LH_BUCKET_BEING_SPLIT;
    oopaque->hasho_flag |= LH_BUCKET_NEEDS_SPLIT_CLEANUP;
    nopaque->hasho_flag &= ~LH_BUCKET_BEING_POPULATED;

    /* WAL */
}
```

[verified-by-code] (`hashpage.c:1075+`).

**Key property**: tuples are **copied**, not moved. The source
bucket keeps every tuple until the next cleanup pass. A scan that
started before the split sees the source bucket unchanged.

The `htab` parameter is used by `_hash_finish_split` when
recovering a partially-completed split — it carries the set of
tuples already copied to the target so we don't double-copy.

The cleanup pass (`hashbucketcleanup`) later removes the
duplicates from the source bucket by re-hashing each tuple and
removing those that now belong in the new bucket. Since the cleanup
pass also requires a cleanup lock on the source bucket, it can
**only run when no scans are active**, which by induction means
all scans that could have started before the split have finished.

## `_hash_finish_split` — recovery for interrupted splits

If a split was interrupted (e.g. by a crash or by a backend that
gave up), the source bucket is stuck with `LH_BUCKET_BEING_SPLIT`
set. The next split (or insert that detects this) calls
`_hash_finish_split`:

```c
/* hashpage.c:1360-1500 (skeleton) */
void _hash_finish_split(Relation rel, Buffer metabuf, Buffer obuf,
                        Bucket obucket, uint32 maxbucket,
                        uint32 highmask, uint32 lowmask)
{
    /* Build a hashtable of tuples ALREADY in the new bucket */
    nbucket = obucket | (lowmask + 1);                  /* compute target */
    htab = _hash_scan_existing_tuples(rel, nbucket);

    /* Re-run _hash_splitbucket with htab — skips tuples already copied */
    _hash_splitbucket(rel, metabuf, obucket, nbucket,
                      obuf, nbuf, htab, maxbucket, highmask, lowmask);
}
```

The hashtable lookup makes the operation idempotent — duplicate
copies are avoided. After this completes, source has
`NEEDS_SPLIT_CLEANUP` and target has normal flags.

## The deferred cleanup — `hashbucketcleanup`

Called from VACUUM and from `_hash_expandtable` when it encounters
`LH_BUCKET_NEEDS_SPLIT_CLEANUP`. Walks every tuple in the source
bucket, re-hashes it with current `maxbucket`/masks, and **deletes**
any tuple that now hashes to a different bucket (those were copies
left behind by the split). Then clears the
`LH_BUCKET_NEEDS_SPLIT_CLEANUP` flag.

VACUUM does this for every bucket as part of its normal cleanup
pass. So in practice, splits leave source buckets needing cleanup
that gets done at next VACUUM, with `_hash_expandtable` opportunistically
cleaning when it needs to split that bucket again.

## The "scan retains pin on primary bucket page" invariant

> Therefore, scans retain a pin on the primary bucket page for the
> bucket they are currently scanning.

[from-comment] (`README`).

The pin prevents anyone from cleanup-locking the bucket, which
prevents splits and cleanups from running during the scan. The scan
can release the pin and move to overflow pages, but if it ever
needs to come back to the primary bucket page, it must re-pin and
re-check that the page hasn't been split since.

Scans that span a split (i.e. were started just before the split
finished) need to consult **both** the source bucket and the new
target bucket, because tuples may live in either. The
`HashScanOpaqueData.hashso_split_bucket_buf` is the pin on the
target bucket carried across pages. [verified-by-code]
(`hash.h:163-180`).

## Lock order

> To avoid deadlocks, we must be consistent about the lock order
> in which we lock the buckets for operations that requires locks
> on two different buckets. We choose to always lock the
> lower-numbered bucket first. The metapage is only ever locked
> after all bucket locks have been taken.

[from-comment] (`README`).

In a split: the source is lower-numbered (`old_bucket < new_bucket`
always, because `new_bucket = maxbucket + 1`). So source-first
satisfies the rule. The metapage is locked last.

For scans across a split: scan locks source first, then target —
again, lower-numbered first.

## Invariants and races

1. **Cleanup lock required for split** on both source and target
   primary bucket pages. Scans retain a pin which prevents cleanup
   lock acquisition. [from-comment] (`README`).
2. **`_hash_getbuf_with_condlock_cleanup`** is non-blocking — if a
   cleanup lock can't be acquired immediately, the split silently
   backs off and the insert proceeds without splitting. The next
   insert that hits the fillfactor will retry.
3. **Tuples are copied, not moved** during split. The source
   retains everything; cleanup later removes the now-duplicates.
4. **`LH_BUCKET_BEING_SPLIT` and `LH_BUCKET_BEING_POPULATED`** are
   the source/target flags during a split. Scans must consult
   both when encountering either.
5. **Mask update precedes redistribution**: the metapage is
   updated BEFORE `_hash_splitbucket` runs. So a concurrent
   inserter that sees the new mask will route correctly.
6. **`hasho_prevblkno` on bucket pages stores `maxbucket-at-split`**,
   not a previous page. Cache invalidation check.
7. **Crash mid-split** is recovered by `_hash_finish_split` on
   next access. The `htab` parameter makes it idempotent.
8. **Lock order**: source (lower-numbered) first, then target,
   then metapage. [from-comment] (`README`).
9. **`maxbucket` can reach `0x7FFFFFFE`** before the AM refuses to
   split further. ~2 billion buckets, well past anything practical.
   [verified-by-code] (`hashpage.c:671`).
10. **`_hash_alloc_buckets` zeros the last page of the new
    splitpoint phase** and lets the FS leave intermediate pages
    as holes. The metapage's `spares[]` view may temporarily lag
    the file EOF after a crash. [from-comment]
    (`hashpage.c:993-989`).

## Useful greps

```bash
# Split entry + helpers:
grep -nE "_hash_expandtable|_hash_splitbucket|_hash_finish_split|_hash_alloc_buckets" \
       source/src/backend/access/hash/hashpage.c

# Cleanup-lock primitives:
grep -rn "_hash_getbuf_with_condlock_cleanup\|IsBufferCleanupOK\|LockBufferForCleanup" \
       source/src/backend/access/hash/

# Split-state flag predicates:
grep -rn "H_BUCKET_BEING_SPLIT\|H_BUCKET_BEING_POPULATED\|H_NEEDS_SPLIT_CLEANUP" source/src/

# Where scans handle split-in-progress:
grep -n "hashso_split_bucket_buf\|hashso_buc_split\|hashso_buc_populated" source/src/backend/access/hash/

# Cleanup invocation from vacuum:
grep -n "hashbucketcleanup" source/src/backend/access/hash/hash.c
```

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/hash/hash.c`](../files/src/backend/access/hash/hash.c.md) | — | hashbucketcleanup (the deferred cleanup pass) |
| [`src/backend/access/hash/hashpage.c`](../files/src/backend/access/hash/hashpage.c.md) | 613 | _hash_expandtable |
| [`src/backend/access/hash/hashpage.c`](../files/src/backend/access/hash/hashpage.c.md) | 993 | _hash_alloc_buckets (extend file for new splitpoint) |
| [`src/backend/access/hash/hashpage.c`](../files/src/backend/access/hash/hashpage.c.md) | 1075 | _hash_splitbucket |
| [`src/backend/access/hash/hashpage.c`](../files/src/backend/access/hash/hashpage.c.md) | 1360 | _hash_finish_split |
| [`src/include/access/hash.h`](../files/src/include/access/hash.h.md) | 58 | LH_BUCKET_BEING_POPULATED, _BEING_SPLIT, _NEEDS_SPLIT_CLEANUP |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-operator-class`](../scenarios/add-new-operator-class.md)

<!-- /scenarios:auto -->
## Cross-references

- [[hash-page-layout]] — the addressing this mutates.
- [[hash-overflow-pages]] — overflow allocation during split.
- `source/src/backend/access/hash/README` — design + lock definitions.
