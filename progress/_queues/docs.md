# Queue: pg-docs-miner — official-docs side

Format: `[status] <chapter-slug> <chapter-url>`
Refill rule: re-walk `https://www.postgresql.org/docs/current/index.html`
table of contents, exclude chapters whose slug already exists under
`knowledge/docs-distilled/`.

## Entries (internals-heavy chapters first)

[done:a49dd51] storage https://www.postgresql.org/docs/current/storage.html
[done:c34e6da] mvcc https://www.postgresql.org/docs/current/mvcc.html
[done:19c6e24] wal https://www.postgresql.org/docs/current/wal.html
[done:19c6e24] indexes-types https://www.postgresql.org/docs/current/indexes-types.html
[done:1aa5183] gist https://www.postgresql.org/docs/current/gist.html
[done:19c6e24] gin https://www.postgresql.org/docs/current/gin.html
[done:19c6e24] brin https://www.postgresql.org/docs/current/brin.html
[done:1aa5183] spgist https://www.postgresql.org/docs/current/spgist.html
[done:1aa5183] runtime-config-wal https://www.postgresql.org/docs/current/runtime-config-wal.html
[done:1aa5183] runtime-config-replication https://www.postgresql.org/docs/current/runtime-config-replication.html
[done:19c6e24] parallel-query https://www.postgresql.org/docs/current/parallel-query.html
[done:f53b7bf] planner-stats https://www.postgresql.org/docs/current/planner-stats.html
[done:f53b7bf] performance-tips https://www.postgresql.org/docs/current/performance-tips.html
[done:f53b7bf] xfunc-c https://www.postgresql.org/docs/current/xfunc-c.html
[done:19c6e24] bgworker https://www.postgresql.org/docs/current/bgworker.html

## Refill 2026-06-06 (re-walk of internals.html ToC — Part VII chapters without a docs-distilled/<slug>.md; per-catalog/per-view reference pages excluded as reference, not internals prose)

[done:a9c263b] overview https://www.postgresql.org/docs/current/overview.html
[done:a9c263b] tableam https://www.postgresql.org/docs/current/tableam.html
[done:a9c263b] indexam https://www.postgresql.org/docs/current/indexam.html
[done:a9c263b] bki https://www.postgresql.org/docs/current/bki.html
[done:a9c263b] transactions https://www.postgresql.org/docs/current/transactions.html
[done:a9c263b] protocol-flow https://www.postgresql.org/docs/current/protocol-flow.html
[done:b91492b] custom-scan https://www.postgresql.org/docs/current/custom-scan.html
[done:b91492b] geqo https://www.postgresql.org/docs/current/geqo.html
[done:b91492b] fdwhandler https://www.postgresql.org/docs/current/fdwhandler.html
[done:b91492b] tablesample-method https://www.postgresql.org/docs/current/tablesample-method.html
[done:b91492b] plhandler https://www.postgresql.org/docs/current/plhandler.html
[done:b91492b] source https://www.postgresql.org/docs/current/source.html
[done:b91492b] storage-toast https://www.postgresql.org/docs/current/storage-toast.html
[done:b91492b] storage-vm https://www.postgresql.org/docs/current/storage-vm.html
[done:b91492b] storage-hot https://www.postgresql.org/docs/current/storage-hot.html
[done:b91492b] wal-for-extensions https://www.postgresql.org/docs/current/wal-for-extensions.html
[done:8c2dd79] hash-index https://www.postgresql.org/docs/current/hash-index.html
[skipped:webfetch-toc-only-4x] planner-stats-details https://www.postgresql.org/docs/current/planner-stats-details.html  # 2026-06-09: retried twice more (/current/ and /docs/18/ slugs) — WebFetch markdown conversion strips the body of this multi-subsection page every time, returning only the ToC (4 failed attempts total across 06-08/06-09). Genuine extraction failure, not transient. Body lives in subsections (Functional Dependencies / Multivariate N-Distinct / MCV Lists); revisit only if WebFetch behavior changes or via a manual paste.

## Refill 2026-06-08 (re-walk of internals.html ToC + Part V "Extending SQL" index chapters — internals-prose chapters without a docs-distilled/<slug>.md; per-catalog/per-view reference pages excluded)

[done:8c2dd79] btree https://www.postgresql.org/docs/current/btree.html
[done:8c2dd79] xindex https://www.postgresql.org/docs/current/xindex.html
[done:8c2dd79] nls https://www.postgresql.org/docs/current/nls.html
[done:8c2dd79] monitoring-stats https://www.postgresql.org/docs/current/monitoring-stats.html

## Refill 2026-06-08 (second pass — both queues drained mid-run; re-walked "Extending SQL" (Part V) + WAL internals chapters to keep filling the output budget)

[done:8c2dd79] xtypes https://www.postgresql.org/docs/current/xtypes.html
[done:8c2dd79] xaggr https://www.postgresql.org/docs/current/xaggr.html
[done:8c2dd79] wal-internals https://www.postgresql.org/docs/current/wal-internals.html

## Refill 2026-06-09 (both queues drained at run start — wiki side fully exhausted per wiki-index.md; re-walked internals.html ToC for protocol + rule-system + trigger leaf chapters not yet under docs-distilled/, picking dense leaf-prose pages over ToC-style parent chapters to dodge the planner-stats-details extraction failure)

[done:cbdd5b0] protocol-message-formats https://www.postgresql.org/docs/current/protocol-message-formats.html
[done:cbdd5b0] protocol-replication https://www.postgresql.org/docs/current/protocol-replication.html
[done:cbdd5b0] xfunc-volatility https://www.postgresql.org/docs/current/xfunc-volatility.html
[done:cbdd5b0] querytree https://www.postgresql.org/docs/current/querytree.html
[done:cbdd5b0] trigger-interface https://www.postgresql.org/docs/current/trigger-interface.html
[done:cbdd5b0] rules-views https://www.postgresql.org/docs/current/rules-views.html
[done:cbdd5b0] trigger-datachanges https://www.postgresql.org/docs/current/trigger-datachanges.html

## Refill 2026-06-10 (both queues drained at run start — wiki side exhausted per wiki-index.md EXHAUSTED note; re-walked internals.html ToC for dense internals-prose LEAF chapters not yet under docs-distilled/, preferring leaf-prose over ToC parents to dodge the planner-stats-details extraction failure; catalog/view reference pages excluded)

[in-progress:cloud/pg-docs-miner/2026-06-10] sasl-authentication https://www.postgresql.org/docs/current/sasl-authentication.html
[in-progress:cloud/pg-docs-miner/2026-06-10] generic-wal https://www.postgresql.org/docs/current/generic-wal.html
[in-progress:cloud/pg-docs-miner/2026-06-10] custom-rmgr https://www.postgresql.org/docs/current/custom-rmgr.html
[in-progress:cloud/pg-docs-miner/2026-06-10] protocol-logical-replication https://www.postgresql.org/docs/current/protocol-logical-replication.html
[in-progress:cloud/pg-docs-miner/2026-06-10] backup-manifest-format https://www.postgresql.org/docs/current/backup-manifest-format.html  # parent ToC-only; field detail salvaged from backup-manifest-files.html leaf
[in-progress:cloud/pg-docs-miner/2026-06-10] query-path https://www.postgresql.org/docs/current/query-path.html
[in-progress:cloud/pg-docs-miner/2026-06-10] planner-optimizer https://www.postgresql.org/docs/current/planner-optimizer.html
[in-progress:cloud/pg-docs-miner/2026-06-10] row-estimation-examples https://www.postgresql.org/docs/current/row-estimation-examples.html
