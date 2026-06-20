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

[done:009b82d] sasl-authentication https://www.postgresql.org/docs/current/sasl-authentication.html
[done:009b82d] generic-wal https://www.postgresql.org/docs/current/generic-wal.html
[done:009b82d] custom-rmgr https://www.postgresql.org/docs/current/custom-rmgr.html
[done:009b82d] protocol-logical-replication https://www.postgresql.org/docs/current/protocol-logical-replication.html
[done:009b82d] backup-manifest-format https://www.postgresql.org/docs/current/backup-manifest-format.html  # parent ToC-only; field detail salvaged from backup-manifest-files.html leaf
[done:009b82d] query-path https://www.postgresql.org/docs/current/query-path.html
[done:009b82d] planner-optimizer https://www.postgresql.org/docs/current/planner-optimizer.html
[done:009b82d] row-estimation-examples https://www.postgresql.org/docs/current/row-estimation-examples.html

## Refill 2026-06-11 (both queues drained at run start — wiki side exhausted per wiki-index.md EXHAUSTED note; re-walked internals.html + "Extending SQL" + protocol + coding-conventions ToCs for dense internals-prose LEAF chapters not yet under docs-distilled/; storage §66 leaf chapters (page-layout/fsm/file-layout/init) + overview §52 leaves (executor/parser-stage/connect-estab) prioritized; 3 candidates 404'd this run: gin-implementation, gist-implementation, gin-extensibility — current docs tree has no such slugs)

[done:752b452] storage-page-layout https://www.postgresql.org/docs/current/storage-page-layout.html
[done:752b452] storage-fsm https://www.postgresql.org/docs/current/storage-fsm.html
[done:752b452] storage-file-layout https://www.postgresql.org/docs/current/storage-file-layout.html
[done:752b452] storage-init https://www.postgresql.org/docs/current/storage-init.html
[done:752b452] executor https://www.postgresql.org/docs/current/executor.html
[done:752b452] parser-stage https://www.postgresql.org/docs/current/parser-stage.html
[done:752b452] connect-estab https://www.postgresql.org/docs/current/connect-estab.html
[done:752b452] bki-structure https://www.postgresql.org/docs/current/bki-structure.html
[done:752b452] protocol-overview https://www.postgresql.org/docs/current/protocol-overview.html
[done:752b452] protocol-error-fields https://www.postgresql.org/docs/current/protocol-error-fields.html
[done:752b452] error-style-guide https://www.postgresql.org/docs/current/error-style-guide.html
[done:752b452] xoper-optimization https://www.postgresql.org/docs/current/xoper-optimization.html
[done:752b452] nls-programmer https://www.postgresql.org/docs/current/nls-programmer.html
[skipped:404-no-such-docs-slug] gin-implementation https://www.postgresql.org/docs/current/gin-implementation.html
[skipped:404-no-such-docs-slug] gist-implementation https://www.postgresql.org/docs/current/gist-implementation.html
[skipped:404-no-such-docs-slug] gin-extensibility https://www.postgresql.org/docs/current/gin-extensibility.html

## Refill 2026-06-12 (both queues drained at run start — wiki side exhausted per wiki-index.md EXHAUSTED note; re-walked indexam.html §63 + wal.html §30 ToCs for the remaining dense internals-prose LEAF subsections not yet under docs-distilled/. The §63 indexam subsections (functions/scanning/locking/unique/cost) and the §30 WAL subsections (intro/reliability/async-commit/configuration) are the meatiest remaining internals chapters. Confirmed this run that the per-AM "extensibility"/"implementation" leaf slugs (gist-extensibility, spgist-extensibility, hash-implementation) are folded into their single-page parents in the current docs tree — all 404, matching prior gin/gist-implementation 404s; do not re-queue.)

[done:3d79680] index-functions https://www.postgresql.org/docs/current/index-functions.html
[done:3d79680] index-scanning https://www.postgresql.org/docs/current/index-scanning.html
[done:3d79680] index-locking https://www.postgresql.org/docs/current/index-locking.html
[done:3d79680] index-unique-checks https://www.postgresql.org/docs/current/index-unique-checks.html
[done:3d79680] index-cost-estimation https://www.postgresql.org/docs/current/index-cost-estimation.html
[done:3d79680] wal-intro https://www.postgresql.org/docs/current/wal-intro.html
[done:3d79680] wal-reliability https://www.postgresql.org/docs/current/wal-reliability.html
[done:3d79680] wal-async-commit https://www.postgresql.org/docs/current/wal-async-commit.html
[done:3d79680] wal-configuration https://www.postgresql.org/docs/current/wal-configuration.html
[skipped:404-no-such-docs-slug] gist-extensibility https://www.postgresql.org/docs/current/gist-extensibility.html
[skipped:404-no-such-docs-slug] spgist-extensibility https://www.postgresql.org/docs/current/spgist-extensibility.html
[skipped:404-no-such-docs-slug] hash-implementation https://www.postgresql.org/docs/current/hash-implementation.html

## Refill 2026-06-13 (both queues drained at run start — wiki side exhausted per wiki-index.md EXHAUSTED note; re-walked the internals ToC for the two biggest UNcovered internals chapters: Logical Decoding §49 and SPI §47, plus the leaf C-ABI chapters for event triggers §40.4, archive modules §51.3, and replication origins §50. The logical-decoding family (concepts/output-plugin/streaming/synchronous) was a glaring gap — zero coverage despite being a top-tier internals subsystem. All 8 fetched clean, no 404s this run.)

[done:becf948] logicaldecoding-explanation https://www.postgresql.org/docs/current/logicaldecoding-explanation.html
[done:becf948] logicaldecoding-output-plugin https://www.postgresql.org/docs/current/logicaldecoding-output-plugin.html
[done:becf948] logicaldecoding-streaming https://www.postgresql.org/docs/current/logicaldecoding-streaming.html
[done:becf948] logicaldecoding-synchronous https://www.postgresql.org/docs/current/logicaldecoding-synchronous.html
[done:becf948] spi https://www.postgresql.org/docs/current/spi.html
[done:becf948] event-trigger-interface https://www.postgresql.org/docs/current/event-trigger-interface.html
[done:becf948] archive-module-callbacks https://www.postgresql.org/docs/current/archive-module-callbacks.html
[done:becf948] replication-origins https://www.postgresql.org/docs/current/replication-origins.html

## Refill 2026-06-14 (both queues drained at run start — wiki side exhausted per wiki-index.md EXHAUSTED note; re-walked internals.html ToC §51-§70. Biggest UNcovered chapter is Transaction Processing §67 — all four leaf sections (transaction-id/xact-locking/subxacts/two-phase) had ZERO coverage despite being a top-tier internals topic with deep corpus backing (transam/lmgr file docs + snapshot/proc data-structures). Also picked the densest remaining leaves: ereport internals §55.2, logical-rep wire formats §54.9, the two BKI catalog-declaration chapters §68.1/§68.2, the rule-system overview §51.4, and miscellaneous coding conventions §55.4. Catalog/view per-object reference pages (§52/§53) excluded as reference, not internals prose.)

[done:7367f67] transaction-id https://www.postgresql.org/docs/current/transaction-id.html
[done:7367f67] xact-locking https://www.postgresql.org/docs/current/xact-locking.html
[done:7367f67] subxacts https://www.postgresql.org/docs/current/subxacts.html
[done:7367f67] two-phase https://www.postgresql.org/docs/current/two-phase.html
[done:7367f67] error-message-reporting https://www.postgresql.org/docs/current/error-message-reporting.html
[done:7367f67] protocol-logicalrep-message-formats https://www.postgresql.org/docs/current/protocol-logicalrep-message-formats.html
[done:7367f67] system-catalog-declarations https://www.postgresql.org/docs/current/system-catalog-declarations.html
[done:7367f67] system-catalog-initial-data https://www.postgresql.org/docs/current/system-catalog-initial-data.html
[done:7367f67] rule-system https://www.postgresql.org/docs/current/rule-system.html
[done:7367f67] source-conventions https://www.postgresql.org/docs/current/source-conventions.html

## Refill 2026-06-15 (both queues drained at run start — wiki side exhausted per wiki-index.md EXHAUSTED note; re-walked internals.html ToC §51-§70. Pattern this run: the PARENT chapters (fdwhandler §58, custom-scan §60, indexam §63) are already under docs-distilled/, but their callback/struct-heavy LEAF subsections — where the actual interface structs and callback signatures live — had ZERO coverage. Picked the densest of those plus the wire-protocol §54.6 "Message Data Types" page that pg-user-question-harvester repeatedly flagged as a recurring corpus gap. Catalog/view per-object reference pages (§52/§53) and pure-prose intro leaves (geqo-intro/biblio) excluded.)

[done:d2fd1fc] index-api https://www.postgresql.org/docs/current/index-api.html
[done:d2fd1fc] fdw-callbacks https://www.postgresql.org/docs/current/fdw-callbacks.html
[done:d2fd1fc] fdw-planning https://www.postgresql.org/docs/current/fdw-planning.html
[done:d2fd1fc] custom-scan-plan https://www.postgresql.org/docs/current/custom-scan-plan.html
[done:d2fd1fc] custom-scan-execution https://www.postgresql.org/docs/current/custom-scan-execution.html
[done:d2fd1fc] tablesample-support-functions https://www.postgresql.org/docs/current/tablesample-support-functions.html
[done:d2fd1fc] protocol-message-types https://www.postgresql.org/docs/current/protocol-message-types.html
[done:d2fd1fc] multivariate-statistics-examples https://www.postgresql.org/docs/current/multivariate-statistics-examples.html

## Refill 2026-06-16 (both queues drained at run start — wiki side exhausted per wiki-index.md EXHAUSTED note; re-walked the §58 FDW / §60 custom-scan / §68 BKI parent chapters for their callback/command LEAF subsections, which were already-distilled-as-parents but had ZERO leaf coverage. The §58 family was missing its handler-entry (§58.1), helper-functions (§58.4), and row-locking (§58.5) leaves; §60 was missing the custom-path stage (§60.1) under custom-scan-plan/-execution; §68 BKI was missing the command reference (§68.3) + example (§68.4) under bki/bki-structure. Also picked the long-neglected xfunc-internal (LANGUAGE internal). 2 candidates 404'd: protocol-versions, gist/spgist-extensibility re-confirmed gone.)

[done:14c3231] fdw-functions https://www.postgresql.org/docs/current/fdw-functions.html
[done:14c3231] fdw-helpers https://www.postgresql.org/docs/current/fdw-helpers.html
[done:14c3231] fdw-row-locking https://www.postgresql.org/docs/current/fdw-row-locking.html
[done:14c3231] custom-scan-path https://www.postgresql.org/docs/current/custom-scan-path.html
[done:14c3231] bki-commands https://www.postgresql.org/docs/current/bki-commands.html
[done:14c3231] bki-example https://www.postgresql.org/docs/current/bki-example.html
[done:14c3231] xfunc-internal https://www.postgresql.org/docs/current/xfunc-internal.html
[skipped:404-no-such-docs-slug] protocol-versions https://www.postgresql.org/docs/current/protocol-versions.html
# 2026-06-17: above 7 [in-progress:cloud/pg-docs-miner/2026-06-16] markers were stale —
# the docs all shipped in PR #330 (merge 14c3231, "7 docs leaf chapters") but the merger
# never flipped the markers. Verified outputs present under knowledge/docs-distilled/.
# Flipped to [done:14c3231] this run.

## Refill 2026-06-17 (both queues drained at run start — wiki side exhausted per wiki-index.md EXHAUSTED note. Re-walked Part V "Extending SQL" (§38) + §55 coding-conventions + §41 rule-system + §35 large-objects ToCs for dense internals-prose LEAF chapters not yet under docs-distilled/. Targeted the two biggest UNcovered clusters: the extension-packaging/build pair (extend-extensions §38.17 + extend-pgxs §38.18 — glaring gap given the extension-development skill) and the rule-system data-modification family (rules-update §41.4 / rules-privileges §41.5 / rules-status — only the SELECT-rule side rules-views was covered before). Plus the type-system + SQL-function + overloading Extending-SQL leaves and source-format §55.1 (the canonical pgindent rules behind the coding-style skill) and lo-implementation §35.5. 1 candidate 404'd: geqo-pg (folded into the single-page geqo parent in the current docs tree, matching prior gin/gist-extensibility 404s — do not re-queue). rules-status needed a re-fetch with a corrected prompt — first WebFetch returned a rules-vs-triggers framing that the page doesn't carry; it is "Rules and Command Status".)

[done:b990d12] extend-extensions https://www.postgresql.org/docs/current/extend-extensions.html
[done:b990d12] extend-pgxs https://www.postgresql.org/docs/current/extend-pgxs.html
[done:b990d12] extend-type-system https://www.postgresql.org/docs/current/extend-type-system.html
[done:b990d12] xfunc-sql https://www.postgresql.org/docs/current/xfunc-sql.html
[done:b990d12] xfunc-overload https://www.postgresql.org/docs/current/xfunc-overload.html
[done:b990d12] source-format https://www.postgresql.org/docs/current/source-format.html
[done:b990d12] lo-implementation https://www.postgresql.org/docs/current/lo-implementation.html
[done:b990d12] rules-update https://www.postgresql.org/docs/current/rules-update.html
[done:b990d12] rules-privileges https://www.postgresql.org/docs/current/rules-privileges.html
[done:b990d12] rules-status https://www.postgresql.org/docs/current/rules-status.html
[skipped:404-no-such-docs-slug] geqo-pg https://www.postgresql.org/docs/current/geqo-pg.html

## Refill 2026-06-18 (both queues drained at run start — wiki side exhausted per wiki-index.md EXHAUSTED note. Re-walked §47 SPI + §40 event-triggers + §38 Extending-SQL + §15 parallel-query + §55.x protocol-changes ToCs for dense internals-prose LEAF chapters NOT folded into an already-distilled parent. The pattern this run: parent chapters spi/event-trigger-interface/parallel-query/xoper-optimization were covered, but their meatiest interface-rule LEAVES had ZERO coverage — the three SPI footgun leaves (memory §47.3 / visibility §47.5 / transaction §47.4), the event-trigger firing matrix §40.1 (only the §40.4 C-ABI was covered), the CREATE OPERATOR base mechanism §38.14 (only §38.15 optimizer hints covered), the PL SQL-registration side §40.1/40.1-install (only the §57 C handler covered), and the §15.3 parallel-plan node taxonomy (parallel-query.md also_fetched §15.1/§15.4 but NOT §15.3). HEAD-probed ~50 per-AM leaf slugs (gin/gist/spgist/brin -intro/-implementation/-extensibility, row-estimation) — ALL 404, single-page-folded in the current tree, matching prior runs; do not re-queue. Three parent pages render ToC-only via WebFetch (spi-transaction §47.4, xplang §40, protocol-changes partial) — enriched from leaf/function pages (spi-spi-commit, xplang-install) where the prose actually lives, same workaround as the planner-stats-details extraction class. mvcc-intro/mvcc-caveats deliberately SKIPPED: mvcc.md already mined the full §13.1-13.7 index. parallel-safety SKIPPED: already folded into parallel-query.md's also_fetched.)

# 2026-06-19: below 8 [in-progress:cloud/pg-docs-miner/2026-06-18] markers were stale —
# all 8 docs shipped in PR #347 (squash 0c7419e, "8 internals-leaf chapters", docs-distilled →127)
# but the merger never flipped the markers (same class as the 06-16→#330 stale-marker case above).
# Verified all 8 outputs present under knowledge/docs-distilled/. Flipped to [done:0c7419e] this run.
[done:0c7419e] spi-memory https://www.postgresql.org/docs/current/spi-memory.html
[done:0c7419e] spi-visibility https://www.postgresql.org/docs/current/spi-visibility.html
[done:0c7419e] spi-transaction https://www.postgresql.org/docs/current/spi-transaction.html
[done:0c7419e] event-trigger-definition https://www.postgresql.org/docs/current/event-trigger-definition.html
[done:0c7419e] xoper https://www.postgresql.org/docs/current/xoper.html
[done:0c7419e] xplang https://www.postgresql.org/docs/current/xplang.html
[done:0c7419e] protocol-changes https://www.postgresql.org/docs/current/protocol-changes.html
[done:0c7419e] parallel-plans https://www.postgresql.org/docs/current/parallel-plans.html

## Refill 2026-06-19 (both queues drained at run start — wiki side exhausted per wiki-index.md EXHAUSTED note; the 8 [in-progress:cloud/pg-docs-miner/2026-06-18] markers above were stale-from-#347 and flipped to [done:0c7419e] this run. Re-walked §49 Logical Decoding + §39 Triggers + §61 GEQO ToCs for dense internals-prose LEAF chapters not yet under docs-distilled/. The logical-decoding family was the biggest remaining coherent gap: the explanation/output-plugin/streaming/synchronous leaves were covered (PR #347-era), but the 4 INTERFACE leaves — streaming-replication-protocol §49.3 (walsender), SQL interface §49.4 (sql), output writers §49.6 (writer), and the worked example §49.1 — had ZERO coverage. Also picked trigger-definition §39.1 (the trigger firing-semantics overview — a glaring gap given trigger-interface §39.4 + trigger-datachanges were the only trigger leaves covered) and geqo-intro §61.1 (the GEQO genetic-algorithm overview behind the already-distilled geqo parent). HEAD-probed btree-behavior/-implementation/-support-funcs/-intro + xindex-opfamily + logicaldecoding-capabilities + trigger-arguments — ALL 404, single-page-folded in the current tree, matching prior per-AM leaf 404s; do not re-queue.)

[in-progress:cloud/pg-docs-miner/2026-06-19] trigger-definition https://www.postgresql.org/docs/current/trigger-definition.html
[in-progress:cloud/pg-docs-miner/2026-06-19] logicaldecoding-walsender https://www.postgresql.org/docs/current/logicaldecoding-walsender.html
[in-progress:cloud/pg-docs-miner/2026-06-19] logicaldecoding-sql https://www.postgresql.org/docs/current/logicaldecoding-sql.html
[in-progress:cloud/pg-docs-miner/2026-06-19] logicaldecoding-writer https://www.postgresql.org/docs/current/logicaldecoding-writer.html
[in-progress:cloud/pg-docs-miner/2026-06-19] logicaldecoding-example https://www.postgresql.org/docs/current/logicaldecoding-example.html
[in-progress:cloud/pg-docs-miner/2026-06-19] geqo-intro https://www.postgresql.org/docs/current/geqo-intro.html
