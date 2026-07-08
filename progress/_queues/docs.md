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

# 2026-06-20: below 6 [in-progress:cloud/pg-docs-miner/2026-06-19] markers were stale —
# all 6 docs shipped in PR #356 (merge 54962de, "6 docs — logical-decoding §49 family +
# trigger §39.1 + geqo §61.1", docs-distilled →133) but the merger never flipped the markers
# (same recurring class as 06-16→#330 and 06-18→#347). Verified all 6 outputs present under
# knowledge/docs-distilled/. Flipped to [done:54962de] this run.
[done:54962de] trigger-definition https://www.postgresql.org/docs/current/trigger-definition.html
[done:54962de] logicaldecoding-walsender https://www.postgresql.org/docs/current/logicaldecoding-walsender.html
[done:54962de] logicaldecoding-sql https://www.postgresql.org/docs/current/logicaldecoding-sql.html
[done:54962de] logicaldecoding-writer https://www.postgresql.org/docs/current/logicaldecoding-writer.html
[done:54962de] logicaldecoding-example https://www.postgresql.org/docs/current/logicaldecoding-example.html
[done:54962de] geqo-intro https://www.postgresql.org/docs/current/geqo-intro.html

## Refill 2026-06-20 (both queues drained at run start — wiki side exhausted per wiki-index.md EXHAUSTED note; the 6 [in-progress:cloud/pg-docs-miner/2026-06-19] markers above were stale-from-#356 and flipped to [done:54962de] this run. Re-walked §16 planner-control + §28 monitoring + §31 logical-replication + §38 Extending-SQL + §70 planner-stats ToCs for the densest internals/developer-prose LEAF chapters with ZERO docs-distilled coverage. The standout gap was the planner SUPPORT-function interface §38.11 xfunc-optimization — the SupportRequestSimplify/Selectivity/Cost/Rows/IndexCondition protocol behind every smart builtin, completely uncovered despite deep executor/planner corpus. Also: planner-stats-security §70.2 (the leakproof / statistics-leakage rules a security reviewer needs), explicit-joins §16.5 (join_collapse_limit / from_collapse_limit planner control — the join-reordering knobs), dynamic-trace §28.5 (the backend's static DTrace probe points — a genuine internals instrumentation surface), and logical-replication-architecture §31.10 (the launcher / apply-worker / tablesync-worker process model behind built-in pub/sub, distinct from the already-covered §49 low-level logical-decoding plugin API). HEAD-probed catalog-pg-control / xfunc-tablefunc / xindex-opfamily — ALL 404 (reference-only or folded), do not re-queue. spi-examples is a worked-example page (skip-class, like other -examples leaves), not distilled.)

[done:1c89485] xfunc-optimization https://www.postgresql.org/docs/current/xfunc-optimization.html
[done:1c89485] planner-stats-security https://www.postgresql.org/docs/current/planner-stats-security.html
[done:1c89485] explicit-joins https://www.postgresql.org/docs/current/explicit-joins.html
[done:1c89485] dynamic-trace https://www.postgresql.org/docs/current/dynamic-trace.html
[done:1c89485] logical-replication-architecture https://www.postgresql.org/docs/current/logical-replication-architecture.html

## Refill 2026-06-21 (both queues drained at run start — wiki side exhausted per wiki-index.md EXHAUSTED note. Re-walked the full internals.html ToC (§54-§68) for the dense internals-prose LEAF chapters that survived prior sweeps without a docs-distilled/<slug>.md, plus the Extending-SQL §38.1 conceptual root. Standout finds this run: the GEQO implementation pair geqo-pg-intro §61.3 (the TSP/Genitor encoding + edge-recombination machinery — the ACTUAL PG implementation, where only the geqo.html parent + §61.1 intro were covered before) and geqo-intro2 §61.2 (the GA-vocabulary chapter §61.3 reuses); the BKI lexical layer bki-format §68.2 (the tokenizer rules, distinct from the already-covered bki-commands §68.3 + bki-structure §68.4); the NLS translator workflow nls-translator §57.1 (gettext PO/POT/MO + the %n$ positional-arg rule that constrains errmsg() authoring — only nls.md parent + nls-programmer §57.2 were covered); the catalog-system orientation pair catalogs-overview §54.1 (the shared-vs-per-database split — verified the 11-catalog shared list against IsSharedRelation() in catalog.c @ f25a07b2d94c) + views-overview §53.1 (the system-view taxonomy + the hacker-relevant pg_backend_memory_contexts/pg_shmem_allocations/pg_aios/pg_wait_events runtime-introspection views); and the extensibility thesis extend-how §38.1 (PG-is-catalog-driven — the conceptual root of all of Part V). indextypes §64 was probed and is ToC-only (chapter intro, no distillable prose — skip-class, like planner-stats-details); the per-AM intro/implementation/extensibility leaves and per-catalog/per-view reference pages remain excluded (reference, not internals prose). Markers left [in-progress:cloud/pg-docs-miner/2026-06-21] for the merger to flip to the squash SHA.)

[done:db0bf1b] geqo-pg-intro https://www.postgresql.org/docs/current/geqo-pg-intro.html
[done:db0bf1b] geqo-intro2 https://www.postgresql.org/docs/current/geqo-intro2.html
[done:db0bf1b] bki-format https://www.postgresql.org/docs/current/bki-format.html
[done:db0bf1b] nls-translator https://www.postgresql.org/docs/current/nls-translator.html
[done:db0bf1b] catalogs-overview https://www.postgresql.org/docs/current/catalogs-overview.html
[done:db0bf1b] views-overview https://www.postgresql.org/docs/current/views-overview.html
[done:db0bf1b] extend-how https://www.postgresql.org/docs/current/extend-how.html
[skipped:toc-only-no-prose] indextypes https://www.postgresql.org/docs/current/indextypes.html  # 2026-06-21: chapter intro / ToC only — six AM names + section links, zero distillable prose (the per-AM detail lives in btree/gist/spgist/gin/brin/hash-index, all already distilled). Same skip-class as planner-stats-details. Do not re-queue.

## Refill 2026-06-22 (both queues drained at run start — wiki side exhausted per wiki-index.md EXHAUSTED note. The Part VII internals leaves are now near-saturated, so this run mined two coherent DEVELOPER-prose families with ZERO docs-distilled coverage. (1) §33 Regression Tests — the entire chapter family (run/evaluation/variant/tap/coverage) was uncovered despite the repo's `testing` skill + R13 phase-end-check ladder being a direct downstream of it; regress-evaluation §33.2 (the spurious-failure taxonomy: locale/timezone/float8/row-order/random) and regress-variant §33.3 (resultmap format + numbered best-match `testname_N.out` selection) are the two non-obvious ones. (2) §10 Type Conversion — the parser's four overload/coercion resolution algorithms (func §10.3 / oper §10.2 / value-storage §10.4 / union-case §10.5 + overview §10.1), the exact numbered tie-break ladders behind `parse_func.c`/`parse_oper.c`/`parse_coerce.c`, uncovered despite deep parser/fmgr corpus. Source paths cited were HEAD-verified at anchor 031904048aa2 via raw.githubusercontent.com: resultmap, parallel_schedule, perl/PostgreSQL/Test/Cluster.pm + Utils.pm, expected/char_1.out — all 200. regress-tap §33.4 module-API detail (PostgreSQL::Test::Cluster/Utils) is code-verified not docs-quoted, flagged as such in the doc. Markers left [in-progress:cloud/pg-docs-miner/2026-06-22] for the merger to flip to the squash SHA.)

[done:2605b54] regress-run https://www.postgresql.org/docs/current/regress-run.html
[done:2605b54] regress-evaluation https://www.postgresql.org/docs/current/regress-evaluation.html
[done:2605b54] regress-variant https://www.postgresql.org/docs/current/regress-variant.html
[done:2605b54] regress-tap https://www.postgresql.org/docs/current/regress-tap.html
[done:2605b54] regress-coverage https://www.postgresql.org/docs/current/regress-coverage.html
[done:2605b54] typeconv-overview https://www.postgresql.org/docs/current/typeconv-overview.html
[done:2605b54] typeconv-func https://www.postgresql.org/docs/current/typeconv-func.html
[done:2605b54] typeconv-oper https://www.postgresql.org/docs/current/typeconv-oper.html
[done:2605b54] typeconv-query https://www.postgresql.org/docs/current/typeconv-query.html
[done:2605b54] typeconv-union-case https://www.postgresql.org/docs/current/typeconv-union-case.html

## Refill 2026-06-23 (both queues drained at run start — wiki side exhausted per wiki-index.md EXHAUSTED note. The Part VII internals leaves are saturated, so this run mined the SEED-EXTENSION cluster the routine had never touched: the **backend-introspection contrib modules** (Appendix F). These are official-docs chapters, dense, and the single most directly-useful family for the `debugging` / `wal-and-xlog` / `storage-buffer` / `locking` skills — yet had ZERO docs-distilled coverage. HEAD-probed 21 candidate slugs; the 8 introspection modules + progress-reporting returned 200, while the per-AM `*-extensibility` slugs (gist/spgist/brin/gin) re-confirmed 404 (single-page-folded, matching every prior run — do not re-queue). Picked: pageinspect (raw page + t_infomask decode + per-AM page formats), pg_walinspect (SQL pg_waldump — rmgr/FPI/block-ref decode), amcheck (B-tree/GIN/heap invariant verification — the AccessShareLock-vs-ShareLock production-safety boundary), pg_buffercache (lock-free BufferDescriptor scan + PG18 NUMA view + eviction-for-testing), pgstattuple (full-scan vs VM/FSM-approx bloat), pg_visibility (VM-bit lies → IOS/wraparound danger + pg_check_frozen/visible), pg_freespacemap (FSM 1/256·BLCKSZ quantization gotcha), pgrowlocks (xmax/multixact → row-lock-mode decode), and progress-reporting §27.4 (the CIC/VACUUM phase state machines + st_progress_param PgBackendStatus mechanism). All claims source-cite into existing storage/index docs-distilled siblings + subsystems/storage-buffer.md + subsystems/storage-lmgr.md. progress-reporting's backend-C mechanism names (pgstat_progress_update_param etc.) are doc-referenced only — the doc flags the exact C signatures as [unverified] pending a source check. Markers left [done:98177f7] for the merger to flip to the squash SHA.)

[done:98177f7] pageinspect https://www.postgresql.org/docs/current/pageinspect.html
[done:98177f7] pgwalinspect https://www.postgresql.org/docs/current/pgwalinspect.html
[done:98177f7] amcheck https://www.postgresql.org/docs/current/amcheck.html
[done:98177f7] pgbuffercache https://www.postgresql.org/docs/current/pgbuffercache.html
[done:98177f7] pgstattuple https://www.postgresql.org/docs/current/pgstattuple.html
[done:98177f7] pgvisibility https://www.postgresql.org/docs/current/pgvisibility.html
[done:98177f7] pgfreespacemap https://www.postgresql.org/docs/current/pgfreespacemap.html
[done:98177f7] pgrowlocks https://www.postgresql.org/docs/current/pgrowlocks.html
[done:98177f7] progress-reporting https://www.postgresql.org/docs/current/progress-reporting.html
[skipped:404-no-such-docs-slug] gist-extensibility https://www.postgresql.org/docs/current/gist-extensibility.html  # re-confirmed 404 this run; single-page-folded, do not re-queue
[skipped:404-no-such-docs-slug] spgist-extensibility https://www.postgresql.org/docs/current/spgist-extensibility.html  # re-confirmed 404
[skipped:404-no-such-docs-slug] brin-extensibility https://www.postgresql.org/docs/current/brin-extensibility.html  # 404
[skipped:404-no-such-docs-slug] gin-extensibility https://www.postgresql.org/docs/current/gin-extensibility.html  # re-confirmed 404

## Refill 2026-06-28 (both queues drained at run start — wiki side exhausted per wiki-index.md EXHAUSTED note; Part VII internals leaves are saturated. Re-walked Appendix F (contrib modules) for the SECOND coherent contrib family: the **reference-implementation / hook-example modules** — the canonical "how to do X" example code for the extension/AM/FDW/hook skills, distinct from the 06-23 backend-INTROSPECTION family. Each picked module maps to an existing skill or subsystem doc: bloom→access-method-apis (the canonical custom index AM), postgres_fdw→fdw-* (the FDW reference impl), auto_explain→executor-and-planner + bgworker-and-extensions hooks (ExecutorStart/Run/Finish/End hook example), pg_prewarm→storage-buffer + bgworker (autoprewarm bgworker), pg_stat_statements→testing + R13 contrib gate (query jumbling/normalization — the contrib R13 specifically requires for catalog/executor phases), test_decoding→logicaldecoding-* (the output-plugin example), passwordcheck→bgworker-and-extensions (check_password_hook example), basic_archive→archive-module-callbacks (the archive_library example). All 8 HEAD-probed 200 this run; the user-facing function/opclass contrib refs (dblink/pg_trgm/btree_gin — also 200) were excluded as reference, not internals/example prose. Markers left [in-progress:cloud/pg-docs-miner/2026-06-28] for the merger to flip to the squash SHA.)

[done:29d3204] bloom https://www.postgresql.org/docs/current/bloom.html
[done:29d3204] postgres-fdw https://www.postgresql.org/docs/current/postgres-fdw.html
[done:29d3204] auto-explain https://www.postgresql.org/docs/current/auto-explain.html
[done:29d3204] pgprewarm https://www.postgresql.org/docs/current/pgprewarm.html
[done:29d3204] pgstatstatements https://www.postgresql.org/docs/current/pgstatstatements.html
[done:29d3204] test-decoding https://www.postgresql.org/docs/current/test-decoding.html
[done:29d3204] passwordcheck https://www.postgresql.org/docs/current/passwordcheck.html
[done:29d3204] basic-archive https://www.postgresql.org/docs/current/basic-archive.html
[done:29d3204] auth-delay https://www.postgresql.org/docs/current/auth-delay.html
[done:29d3204] pgsurgery https://www.postgresql.org/docs/current/pgsurgery.html

## Refill 2026-06-29 (both queues drained at run start — wiki side exhausted per wiki-index.md EXHAUSTED note; Part VII internals leaves saturated (174 docs-distilled). After two contrib families (06-23 backend-introspection, 06-28 reference-impl/hook-example), this run mines the THIRD coherent uncovered family: the **WAL / control-file / recovery developer tools** (Part VI Reference, server applications). Each maps to an existing skill or subsystem doc — the densest internals-relevant developer-tool prose left in the tree: pgwaldump→wal-and-xlog (WAL record decode CLI; rmgr/block-ref/FPI filters, the SQL-less twin of pg_walinspect.md), pg_controldata §app-pgcontroldata→wal-and-xlog+debugging (the pg_control struct dump — checkpoint LSN/REDO/TLI/wal_level/state/data-checksum-version), pg_resetwal §app-pgresetwal→wal-and-xlog (control-file surgery: -f forced reset, the "last resort" guarantees + OID/MXID/epoch override switches), pg_checksums §app-pgchecksums→storage-buffer (offline enable/verify/disable of data checksums; cluster-must-be-down invariant), pg_rewind §app-pgrewind→replication-overview (timeline-divergence resync via WAL-replay of changed blocks since the divergence checkpoint; the full_page_writes + wal_log_hints precondition), pg_test_fsync §pgtestfsync→wal-and-xlog (wal_sync_method micro-benchmark — open_datasync vs fdatasync vs fsync vs open_sync, the source behind the GUC default pick), pg_test_timing §pgtesttiming→debugging+monitoring (clock-source overhead histogram — the EXPLAIN ANALYZE / track_io_timing tax), pg_verifybackup §app-pgverifybackup→pairs with backup-manifest-format.md (manifest checksum + WAL-range verification — the read side of the §65 format). HEAD-probed this run: pgwaldump/pgtestfsync/pgtesttiming resolve WITHOUT the app- prefix (200); app-pgwaldump/pgresetwal(bare)/pgcontroldata(bare)/pgchecksums(bare) all 404 — slug prefix is inconsistent across these tools, recorded here so future runs don't re-probe. The budget floor (≥70% of 50k output) was still short after the 8 offline-tools docs, so the **streaming-client sub-family** (app-pgbasebackup / app-pgreceivewal / app-pgrecvlogical, all 200) was pulled into the SAME run to complete the WAL/replication developer-tool family and fill the budget: pg_basebackup→replication-overview (BASE_BACKUP over walsender; -X stream two-connection self-consistency, manifest options that feed pg_verifybackup, incremental/pg_combinebackup), pg_receivewal→wal-and-xlog (raw-WAL-to-disk archiver; the --synchronous-or-block-forever footgun + .partial convention), pg_recvlogical→replication-overview (logical-slot CLI; database-bound, output-plugin-at-create, consume-only vs the SQL peek). 11 docs total this run (docs-distilled 174→185). Markers left [in-progress:cloud/pg-docs-miner/2026-06-29] for the merger to flip to the squash SHA.)

[done:758a8039] pgwaldump https://www.postgresql.org/docs/current/pgwaldump.html
[done:758a8039] app-pgcontroldata https://www.postgresql.org/docs/current/app-pgcontroldata.html
[done:758a8039] app-pgresetwal https://www.postgresql.org/docs/current/app-pgresetwal.html
[done:758a8039] app-pgchecksums https://www.postgresql.org/docs/current/app-pgchecksums.html
[done:758a8039] app-pgrewind https://www.postgresql.org/docs/current/app-pgrewind.html
[done:758a8039] pgtestfsync https://www.postgresql.org/docs/current/pgtestfsync.html
[done:758a8039] pgtesttiming https://www.postgresql.org/docs/current/pgtesttiming.html
[done:758a8039] app-pgverifybackup https://www.postgresql.org/docs/current/app-pgverifybackup.html
[done:758a8039] app-pgbasebackup https://www.postgresql.org/docs/current/app-pgbasebackup.html
[done:758a8039] app-pgreceivewal https://www.postgresql.org/docs/current/app-pgreceivewal.html
[done:758a8039] app-pgrecvlogical https://www.postgresql.org/docs/current/app-pgrecvlogical.html

## Refill 2026-06-30 (both queues drained at run start — wiki side exhausted per wiki-index.md EXHAUSTED note; Part VII internals leaves saturated (185 docs-distilled). After three contrib/dev-tool families (06-23 introspection, 06-28 reference-impl/hook-example, 06-29 WAL/control-file/recovery tools), this run completes the **§29/§31 Logical Replication chapter** — the user-facing/operator + semantics leaves that pair with the already-distilled §x.10 architecture leaf (logical-replication-architecture.md, 06-20). Direct response to the harvester's strongest standing gaps: replication-overview is the heaviest skill (×8 per #425) and gap:logical-replication has recurred ×9/×4 across multiple nights (#393/#399). Each leaf maps to replication-overview + the §49 logicaldecoding-*.md family + protocol-logical-replication.md. HEAD-probed this run: all 8 leaf slugs 200 (logical-replication / -publication / -subscription / -conflicts / -row-filter / -col-lists / -restrictions / -failover); vacuum-for-* subsection slugs all 404 (folded into routine-vacuuming.html as anchors, recorded so future runs don't re-probe). Chapter renumbered 31→29 in current docs — same chapter; cite by slug not number. Markers left [in-progress:cloud/pg-docs-miner/2026-06-30] for the merger to flip to the squash SHA.)

[done:2fdbc90] logical-replication https://www.postgresql.org/docs/current/logical-replication.html
[done:2fdbc90] logical-replication-publication https://www.postgresql.org/docs/current/logical-replication-publication.html
[done:2fdbc90] logical-replication-subscription https://www.postgresql.org/docs/current/logical-replication-subscription.html
[done:2fdbc90] logical-replication-conflicts https://www.postgresql.org/docs/current/logical-replication-conflicts.html
[done:2fdbc90] logical-replication-row-filter https://www.postgresql.org/docs/current/logical-replication-row-filter.html
[done:2fdbc90] logical-replication-col-lists https://www.postgresql.org/docs/current/logical-replication-col-lists.html
[done:2fdbc90] logical-replication-restrictions https://www.postgresql.org/docs/current/logical-replication-restrictions.html
[done:2fdbc90] logical-replication-failover https://www.postgresql.org/docs/current/logical-replication-failover.html

## Refill 2026-07-01 (both queues drained at run start — wiki side exhausted per wiki-index.md EXHAUSTED note; Part VII internals leaves saturated (193 docs-distilled). After the §29 logical-replication chapter (06-30), this run mines the **Server Configuration (runtime-config-*) GUC-reference family + the §25 routine-maintenance internals** — the half-covered §20 series (only runtime-config-wal + runtime-config-replication were distilled before) completed toward the harvester's strongest standing corpus gaps: gap:vacuum-autovacuum ×7 + the vacuum-horizon candidate-subsystem cluster, gap:pgstat ×9 (heaviest recurring), and the executor-and-planner skill surface. Each chapter maps to an existing skill/subsystem: runtime-config-query→executor-and-planner/optimizer.md, runtime-config-resource→memory-contexts/storage-buffer.md, runtime-config-statistics→pgstat gap/monitoring-stats.md, runtime-config-vacuum + routine-vacuuming→vacuum gap/access-heap+access-transam, runtime-config-locks→locking/storage-lmgr.md, runtime-config-error-handling→error-handling/wal-reliability, routine-reindex→access-method-apis. HEAD-probed this run: runtime-config-autovacuum.html 301-REDIRECTS → runtime-config-vacuum.html (autovacuum GUCs merged into the vacuum config page in current docs — recorded so future runs use the new slug); all other slugs 200. Non-obvious harvest this run: freeze-age knobs are silently clamped to 50%/95% of autovacuum_freeze_max_age (a user value can be ignored); work_mem is per-node not per-query; max_locks_per_transaction is a shared-pool size not a per-xact cap; data_sync_retry=off PANICs on fsync failure by design (fsyncgate); io_method is the new PG18 async-I/O front door. Markers left [in-progress:cloud/pg-docs-miner/2026-07-01] for the merger to flip to the squash SHA. docs-distilled 193→201.)

[done:bd648ec] runtime-config-query https://www.postgresql.org/docs/current/runtime-config-query.html
[done:bd648ec] runtime-config-resource https://www.postgresql.org/docs/current/runtime-config-resource.html
[done:bd648ec] runtime-config-statistics https://www.postgresql.org/docs/current/runtime-config-statistics.html
[done:bd648ec] runtime-config-vacuum https://www.postgresql.org/docs/current/runtime-config-vacuum.html
[done:bd648ec] runtime-config-locks https://www.postgresql.org/docs/current/runtime-config-locks.html
[done:bd648ec] runtime-config-error-handling https://www.postgresql.org/docs/current/runtime-config-error-handling.html
[done:bd648ec] routine-vacuuming https://www.postgresql.org/docs/current/routine-vacuuming.html
[done:bd648ec] routine-reindex https://www.postgresql.org/docs/current/routine-reindex.html
[redirect:301→runtime-config-vacuum] runtime-config-autovacuum https://www.postgresql.org/docs/current/runtime-config-autovacuum.html  # autovacuum GUCs merged into runtime-config-vacuum.html in current docs; do not re-queue the old slug

## Refill 2026-07-02 (both queues drained at run start — wiki side exhausted per wiki-index.md EXHAUSTED note; Part VII internals leaves saturated (201 docs-distilled). This run COMPLETES the §20 Server-Configuration GUC-reference family that 07-01 (#440/bd648ec: query/resource/statistics/vacuum/locks/error-handling) began. The remaining §20 leaves are the highest-value uncovered GUC pages for the gucs-config + debugging skills: runtime-config-developer §20.17 is THE hacker page (wal_consistency_checking, ignore_checksum_failure/zero_damaged_pages/ignore_invalid_pages corruption-recovery trio, backtrace_functions, debug_discard_caches = CLOBBER_CACHE_ALWAYS, the debug_*_parse_plan_trees node-test gates a parser-and-nodes change must survive, trace_locks/LOCK_DEBUG, pre/post_auth_delay debugger windows, send_abort_for_crash cores) — completely uncovered before this run; runtime-config-custom §20.16 (the placeholder/two-part-name mechanism behind DefineCustom*Variable — maps to gucs-config); runtime-config-preset §20.15 (block_size/wal_block_size/segment_size geometry + debug_assertions = the fast cassert-build check + NAMEDATALEN/INDEX_MAX_KEYS constants); runtime-config-client §20.12 (search_path invisible-entry rules, the 5-timeout family scoping, session_replication_role=replica trigger/FK/apply master switch, the preload-library load-timing trio); runtime-config-connection §20.3 (max_connections↔shmem↔standby-must-match coupling, the 3-tier connection reserve, unix-socket .lock-file/abstract-namespace details, scram_iterations doesn't-touch-existing-passwords); runtime-config-logging §20.8 (the log_min_messages-vs-client_min_messages LOG-rank inversion, log_line_prefix %-escapes %v/%P/%Q, log_error_verbosity=VERBOSE gives file:func:line, log_statement skips syntax errors). Plus errcodes-appendix (Appendix A — the full SQLSTATE class/condition taxonomy generated from src/backend/utils/errcodes.txt; the single most useful error-handling-skill reference, previously uncovered despite error-message-reporting.md + error-style-guide.md being distilled). HEAD/fetch note: runtime-config-autovacuum 301-redirects into runtime-config-vacuum (recorded 07-01, not re-probed). docs-distilled 201→208. Markers left [in-progress:cloud/pg-docs-miner/2026-07-02] for the merger to flip to the squash SHA.)

[done:bf0de030] runtime-config-developer https://www.postgresql.org/docs/current/runtime-config-developer.html
[done:bf0de030] runtime-config-custom https://www.postgresql.org/docs/current/runtime-config-custom.html
[done:bf0de030] runtime-config-preset https://www.postgresql.org/docs/current/runtime-config-preset.html
[done:bf0de030] runtime-config-client https://www.postgresql.org/docs/current/runtime-config-client.html
[done:bf0de030] runtime-config-connection https://www.postgresql.org/docs/current/runtime-config-connection.html
[done:bf0de030] runtime-config-logging https://www.postgresql.org/docs/current/runtime-config-logging.html
[done:bf0de030] errcodes-appendix https://www.postgresql.org/docs/current/errcodes-appendix.html

## Refill 2026-07-03 (both queues drained at run start — wiki side exhausted per wiki-index.md EXHAUSTED note; Part VII internals leaves + §20 GUC family + §29 logical-replication saturated (208 docs-distilled). This run mines the coherent uncovered PHYSICAL-HA / PITR / STANDBY family — the physical twin of the already-complete §29 logical-replication chapter, and a direct hit on the harvester's heaviest standing skill (replication-overview ×8 per #452/#425) + gap:logical-replication. We had the whole LOGICAL side (§29 + §49 logicaldecoding-*) but ZERO coverage of the physical side: continuous-archiving/PITR (§25.3), the "cp the data dir" pitfall (§25.2 backup-file), the HA taxonomy (§26.1), warm-standby/streaming-replication (§26.2), failover+STONITH (§26.3), hot-standby recovery-conflicts (§26.4), and the recovery.conf→postgresql.conf signal-file migration (Appendix O recovery-config). Current-docs chapter numbers: Backup&Restore=§25, High-Availability=§26 (renumbered down from §26/§27 — cite by slug not number, same class as the §31→§29 logical-replication renumber). HEAD/fetch notes this run: standby-settings.html 404 (standby GUCs folded into runtime-config-replication.html — already distilled; do not re-queue); recovery GUCs (restore_command/recovery_target_*/archive_cleanup_command/recovery_end_command) live ON runtime-config-wal.html — already distilled, cross-referenced from continuous-archiving.md rather than re-distilled; backup-dump.html §25.1 EXCLUDED as user-facing pg_dump/pg_dumpall/pg_restore operator prose (no backend internals), same skip-class as other user-facing reference pages. All 7 shipped map to replication-overview + wal-and-xlog skills + subsystems/replication.md + subsystems/access-transam.md. docs-distilled 208→215. Markers left [in-progress:cloud/pg-docs-miner/2026-07-03] for the merger to flip to the squash SHA.)

[done:6c597fa] backup-file https://www.postgresql.org/docs/current/backup-file.html
[done:6c597fa] continuous-archiving https://www.postgresql.org/docs/current/continuous-archiving.html
[done:6c597fa] different-replication-solutions https://www.postgresql.org/docs/current/different-replication-solutions.html
[done:6c597fa] warm-standby https://www.postgresql.org/docs/current/warm-standby.html
[done:6c597fa] warm-standby-failover https://www.postgresql.org/docs/current/warm-standby-failover.html
[done:6c597fa] hot-standby https://www.postgresql.org/docs/current/hot-standby.html
[done:6c597fa] recovery-config https://www.postgresql.org/docs/current/recovery-config.html
[skipped:404-no-such-docs-slug] standby-settings https://www.postgresql.org/docs/current/standby-settings.html  # 2026-07-03: standby-server GUCs folded into runtime-config-replication.html (already distilled); do not re-queue
[skipped:user-facing-operator-prose] backup-dump https://www.postgresql.org/docs/current/backup-dump.html  # 2026-07-03: §25.1 SQL Dump — pg_dump/pg_dumpall/pg_restore usage, no backend internals; excluded like other user-facing reference pages

## Refill 2026-07-04 (both queues drained at run start — wiki side exhausted per wiki-index.md EXHAUSTED note; Part VII internals leaves + §20 GUC family + §29 logical-replication + §25/§26 physical-HA all saturated (215 docs-distilled). This run mines the biggest remaining coherent uncovered chapter: §21 CLIENT AUTHENTICATION — an entire backend subsystem (src/backend/libpq/{hba,auth,crypt,auth-scram}.c) with ZERO docs-distilled coverage despite the corpus already carrying knowledge/files/src/backend/libpq/{hba,auth,crypt,auth-scram,auth-sasl}.c.md + subsystems/libpq-backend.md + docs-distilled/sasl-authentication.md. Picked the 7 INTERNALS-dense auth leaves and deliberately EXCLUDED the third-party-service-config methods (ldap/radius/pam/bsd/oauth — external-service wiring, low backend-internals value) and the GSSAPI/SSPI method leaves (encryption-layer, partly covered by protocol-replication + be-secure-gssapi corpus). The load-bearing page is auth-pg-hba-conf (§21.1) — the first-match-wins lookup algorithm, VERIFIED against check_hba() foreach + `port->hba = hba; return;` at hba.c:2347/:2430 @ a5422fe3bd7e (no fall-through on auth failure). auth-password (§21.5) verified against get_password_type()/encrypt_password() at crypt.c:153/:180 (the stored-verifier-type drives the exchange, hence md5→SCRAM auto-upgrade). To round the run out to the budget floor beyond the 7-page auth cluster, added: monitoring-locks §28.3 (pg_locks — held-vs-waited, dual heavyweight+SIReadLock coverage, virtualxid/transactionid twin rows, fastpath; maps to locking skill + storage-lmgr), monitoring-ps §28.1 (process-title/update_process_title/cluster_name; ps_status.c), server-shutdown §19.5 (SIGTERM/SIGINT/SIGQUIT → Smart/Fast/Immediate, VERIFIED against pmdie() at postmaster.c:2080/:2084/:2088; the never-SIGKILL-the-postmaster IPC-cleanup rule), kernel-resources §19.4 (hybrid SysV-guard+mmap shmem, num_os_semaphores formula, huge_pages, the OOM-killer PG_OOM_ADJUST_FILE/VALUE protection, systemd RemoveIPC parallel-query corruption), and preventing-server-spoofing §19.6 (server-down impostor threat; unix_socket_directories write-protection, requirepeer, sslmode=verify-full, SCRAM channel_binding=require). HEAD-probe notes this run: auth-gssapi/auth-sspi 404 (method detail folded into gss/sspi single pages — do not re-queue); postgres-shutdown-signals/secure-tcpip/row-estimation 404 (folded/renamed). Chapter renumbering: Client Authentication is §21 in current docs but the page bodies still say "Section 20.x" (docs lag — cite by slug, note both numbers). docs-distilled 215→227. Markers left [in-progress:cloud/pg-docs-miner/2026-07-04] for the merger to flip to the squash SHA.)

[done:b0253c3] auth-pg-hba-conf https://www.postgresql.org/docs/current/auth-pg-hba-conf.html
[done:b0253c3] auth-username-maps https://www.postgresql.org/docs/current/auth-username-maps.html
[done:b0253c3] auth-password https://www.postgresql.org/docs/current/auth-password.html
[done:b0253c3] auth-cert https://www.postgresql.org/docs/current/auth-cert.html
[done:b0253c3] auth-peer https://www.postgresql.org/docs/current/auth-peer.html
[done:b0253c3] auth-ident https://www.postgresql.org/docs/current/auth-ident.html
[done:b0253c3] auth-trust https://www.postgresql.org/docs/current/auth-trust.html
[done:b0253c3] monitoring-locks https://www.postgresql.org/docs/current/monitoring-locks.html
[done:b0253c3] monitoring-ps https://www.postgresql.org/docs/current/monitoring-ps.html
[done:b0253c3] server-shutdown https://www.postgresql.org/docs/current/server-shutdown.html
[done:b0253c3] kernel-resources https://www.postgresql.org/docs/current/kernel-resources.html
[done:b0253c3] preventing-server-spoofing https://www.postgresql.org/docs/current/preventing-server-spoofing.html
[skipped:third-party-service-config] auth-ldap https://www.postgresql.org/docs/current/auth-ldap.html  # 2026-07-04: LDAP server wiring — external-service config, low backend-internals value; excluded like other operator-config pages
[skipped:third-party-service-config] auth-radius https://www.postgresql.org/docs/current/auth-radius.html  # 2026-07-04: RADIUS server wiring
[skipped:third-party-service-config] auth-pam https://www.postgresql.org/docs/current/auth-pam.html  # 2026-07-04: PAM service wiring
[skipped:third-party-service-config] auth-bsd https://www.postgresql.org/docs/current/auth-bsd.html  # 2026-07-04: BSD Auth service wiring
[skipped:404-no-such-docs-slug] auth-gssapi https://www.postgresql.org/docs/current/auth-gssapi.html  # 2026-07-04: 404 — GSSAPI method detail folded into gss single page; do not re-queue
[skipped:404-no-such-docs-slug] auth-sspi https://www.postgresql.org/docs/current/auth-sspi.html  # 2026-07-04: 404 — SSPI method detail folded into sspi single page

## Refill 2026-07-05 (both queues drained at run start — wiki side exhausted per wiki-index.md EXHAUSTED note; Part VII internals leaves + §20 GUC family + §29 logical-replication + §25/§26 physical-HA + §21 auth all saturated (227 docs-distilled). This run opens a genuinely uncovered TOP-LEVEL chapter: §43 PL/pgSQL — ZERO docs-distilled coverage despite the corpus already carrying docs-distilled/plhandler.md + spi*.md + trigger-interface.md and the fmgr-and-spi/plhandler skills, and despite PL/pgSQL being the REFERENCE PL handler + the PARAM-reuse infrastructure the sesvars work leans on (CLAUDE.md R15: the manual reference impl reused existing PARAM infra). Mined the 8 INTERNALS-dense leaves and deliberately EXCLUDED the pure-tutorial leaves (control-structures §43.6 loops/IF, declarations §43.3 %TYPE tutorial, errors-and-messages §43.9 RAISE tutorial — maps to error-handling but user-facing, development-tips §43.12, porting §43.11-Oracle). The load-bearing page is plpgsql-implementation §43.11 (variable substitution = PARAM nodes NOT text + SPI_prepare per-statement plan caching + generic/custom plan choice) — the exact mechanism behind the sesvars PARAM reuse. Chapter renumbered to §43 in the current ToC but ALL page bodies still read "41.x" (docs lag, same class as §31→§29 logical-replication + §21 auth "20.x" body-lag; cite by slug, noted both numbers in each doc). 3 load-bearing claims CODE-VERIFIED @e0ff7fd9aa2e via raw.githubusercontent.com (pl_exec.c 200): (1) non-atomic SPI txn context — estate.atomic=atomic pl_exec.c:511 + options.allow_nonatomic=true pl_exec.c:2270; (2) PARAM substitution — setup_param_list pl_exec.c:6351 + plpgsql_param_fetch pl_exec.c:6399; (3) refcursor=portal-name-string — curname=TextDatumGetCString(curvar->value) pl_exec.c:2922 → SPI_cursor_open_with_paramlist(curname,...) pl_exec.c:2987. All 13 §43 leaf slugs HEAD-probed 200 (none folded/404). docs-distilled 227→235. Markers left [done:005abe5] for the merger to flip to the squash SHA.)

[done:005abe5] plpgsql-overview https://www.postgresql.org/docs/current/plpgsql-overview.html
[done:005abe5] plpgsql-structure https://www.postgresql.org/docs/current/plpgsql-structure.html
[done:005abe5] plpgsql-expressions https://www.postgresql.org/docs/current/plpgsql-expressions.html
[done:005abe5] plpgsql-statements https://www.postgresql.org/docs/current/plpgsql-statements.html
[done:005abe5] plpgsql-cursors https://www.postgresql.org/docs/current/plpgsql-cursors.html
[done:005abe5] plpgsql-transactions https://www.postgresql.org/docs/current/plpgsql-transactions.html
[done:005abe5] plpgsql-trigger https://www.postgresql.org/docs/current/plpgsql-trigger.html
[done:005abe5] plpgsql-implementation https://www.postgresql.org/docs/current/plpgsql-implementation.html
[skipped:user-facing-tutorial] plpgsql-control-structures https://www.postgresql.org/docs/current/plpgsql-control-structures.html  # 2026-07-05: §43.6 IF/LOOP/FOR tutorial — user-facing control-flow prose, no backend internals; excluded like other tutorial leaves
[skipped:user-facing-tutorial] plpgsql-declarations https://www.postgresql.org/docs/current/plpgsql-declarations.html  # 2026-07-05: §43.3 %TYPE/%ROWTYPE/ALIAS declaration tutorial — mostly user-facing; internals (record shape) covered from plpgsql-implementation.md
[skipped:user-facing-tutorial] plpgsql-errors-and-messages https://www.postgresql.org/docs/current/plpgsql-errors-and-messages.html  # 2026-07-05: §43.9 RAISE tutorial — maps to error-handling skill but user-facing; SQLSTATE taxonomy already in errcodes-appendix.md + error-message-reporting.md
[skipped:user-facing-tutorial] plpgsql-development-tips https://www.postgresql.org/docs/current/plpgsql-development-tips.html  # 2026-07-05: §43.12 dev tips — tutorial
[skipped:user-facing-tutorial] plpgsql-porting https://www.postgresql.org/docs/current/plpgsql-porting.html  # 2026-07-05: Oracle PL/SQL migration guide — user-facing, zero backend internals

## Refill 2026-07-06 (both queues drained at run start — wiki side exhausted per wiki-index.md EXHAUSTED note; Part VII internals leaves + §20 GUC family + §29 logical-replication + §25/§26 physical-HA + §21 auth + §43 plpgsql all saturated (235 docs-distilled). This run mines a coherent uncovered TEXT & LOCALE internals family, a direct hit on the recurring `encoding-conversion` harvester gap and the "nondeterministic LIKE" -hackers thread (community-pulse #474). Two chapters: (1) §24 Localization — the whole chapter (locale §24.1 / collation §24.2 / multibyte §24.3) had ZERO docs-distilled coverage despite deep pg_locale.c / mbutils.c / pg_collation catalog corpus. The load-bearing internals fact is the deterministic-vs-nondeterministic collation split (byte-equality vs collator-equality → pattern-matching + btree-dedup restrictions) and the LC_COLLATE/LC_CTYPE-are-frozen-at-db-creation invariant. (2) §12 Full-Text-Search EXTENSIBILITY leaves — parsers §12.5 (the 23-token-type default parser + custom START/GETTOKEN/END/LEXTYPES C API), dictionaries §12.6 (the lexize contract: array/{}/TSL_FILTER/NULL + the first-non-NULL-wins dictionary chain), indexes §12.9 (GIN exact-inverted vs GiST lossy-signature-with-heap-recheck) — the FTS parser/dict/index API trio was uncovered though tsvector/tsquery type internals sat in the corpus. Plus the timely contrib example dict_xsyn (extended synonym dictionary — its dxsyn_lexize was simplified upstream recently per upstream-watcher #477 dict_xsyn cluster). 4 load-bearing claims CODE-VERIFIED @a8c2547eaac7 via raw.githubusercontent.com: (1) SQL_ASCII no-conversion bypass — pg_do_encoding_conversion returns src untouched at mbutils.c:377-380, PG_SQL_ASCII=0 at pg_wchar.h:76; (2) collation provider dispatch — pg_newlocale_from_collation branches on collprovider at pg_locale.c:1189/:1062-1066; (3) collisdeterministic + collversion catalog columns at pg_collation.h:42/:49; (4) GiST tsvector SIGLEN_DEFAULT = 31*4 = 124 bytes at tsgistidx.c:35 (confirms docs' "124-byte default signature"); dict_xsyn matchorig/keeporig option struct + dxsyn_lexize at dict_xsyn.c:40-41/:48/:165. HEAD/fetch notes this run: charset.html is CHAPTER-TOC-ONLY (§24 root; the §24.1 body lives on the separate locale.html leaf — same ToC-only class as planner-stats-details; fetched locale.html instead); locale-providers/icu-locales 404 (folded into locale.html §24.1.4/§24.1.5 anchors, NOT separate pages — do not re-queue); textsearch-migration 404 (folded). Deliberately excluded: textsearch-intro/-tables/-controls/-limitations §12.1-12.4 (user-facing query-writing tutorial, no backend internals); the third-party dict contrib refs beyond dict_xsyn deferred to a future run if budget needs. docs-distilled 235→242. Markers left [done:cb61999] for the merger to flip to the squash SHA.)

[done:cb61999] locale https://www.postgresql.org/docs/current/locale.html
[done:cb61999] collation https://www.postgresql.org/docs/current/collation.html
[done:cb61999] multibyte https://www.postgresql.org/docs/current/multibyte.html
[done:cb61999] textsearch-dictionaries https://www.postgresql.org/docs/current/textsearch-dictionaries.html
[done:cb61999] textsearch-parsers https://www.postgresql.org/docs/current/textsearch-parsers.html
[done:cb61999] textsearch-indexes https://www.postgresql.org/docs/current/textsearch-indexes.html
[done:cb61999] dict-xsyn https://www.postgresql.org/docs/current/dict-xsyn.html
[skipped:chapter-toc-only] charset https://www.postgresql.org/docs/current/charset.html  # 2026-07-06: §24 Localization chapter ToC only (17KB HTML → 2KB text, links to §24.1/2/3 leaves); §24.1 body is on locale.html (fetched). Same skip-class as planner-stats-details/indextypes. Do not re-queue.
[skipped:404-folded] locale-providers https://www.postgresql.org/docs/current/locale-providers.html  # 2026-07-06: 404 — §24.1.4 Locale Providers is an anchor within locale.html, not a page
[skipped:404-folded] icu-locales https://www.postgresql.org/docs/current/icu-locales.html  # 2026-07-06: 404 — §24.1.5 ICU Locales folded into locale.html
[skipped:404-folded] textsearch-migration https://www.postgresql.org/docs/current/textsearch-migration.html  # 2026-07-06: 404 — no such slug in current tree

## Refill 2026-07-07 (both queues drained at run start — wiki side exhausted per wiki-index.md EXHAUSTED note; Part VII internals leaves + §20 GUC family + §29 logical-replication + §25/§26 physical-HA + §21 auth + §43 PL/pgSQL + §24/§12 text-locale all saturated (242 docs-distilled). §43 PL/pgSQL was fully mined (07-05), but the OTHER procedural-language handlers — §45 PL/Perl, §46 PL/Python, §44 PL/Tcl — had ZERO docs-distilled coverage despite plhandler.md + spi*.md + the fmgr-and-spi/plhandler skills. This run mines the "non-plpgsql PL internals" family: each PL's trusted-interpreter sandbox mechanism, its SPI-wrapper command surface, its datum↔language value mapping, and explicit subtransaction control. Deliberately EXCLUDED the pure-tutorial leaves (plperl-funcs/-triggers, plpython-funcs, pltcl-functions/-trigger — user-facing "how to write a function" prose) and the thin data leaves that fold into siblings (plperl-data + pltcl-data both return only the "args arrive as text" one-liner via WebFetch — captured inline in the builtins/overview docs instead). Chapters renumbered §41→§45/§46 and §42→§44 in the current ToC but page bodies still lag (cite by slug). 5 load-bearing claims CODE-VERIFIED @9d1188f29865 via raw.githubusercontent.com: (1) the internal-subxact triple is SHARED across all PLs — plpy_subxactobject.c:122/:181/:185 (BeginInternalSubTransaction/RollbackAndRelease/Release) == pltcl.c:2366/:2376/:2393; (2) PL/Tcl trusted sandbox = Tcl safe SLAVE interp via Tcl_CreateSlave(...,pltrusted?1:0) pltcl.c:503, per-role keyed by user_id :506; (3) PL/Tcl SPI commands wired by Tcl_CreateObjCommand in pltcl_init_interp pltcl.c:529/:531/:533/:535 (spi_exec/spi_prepare/spi_execp/subtransaction); (4) PL/Perl trusted sandbox = Perl OPCODE MASK (not Safe.pm) — PLPERL_SET_OPMASK(plperl_opmask) plperl.c:483 + PL_ppaddr[OP_REQUIRE]=pp_require_safe :499-500 + plperl_opmask[MAXO] :241 + #include plperl_opmask.h :50; plperl.on_init is PGC_SIGHUP plperl.c:418; (5) PL/Python is UNTRUSTED-ONLY — plpython3u.control has superuser=true (there is no trusted plpython). pltcl.start_proc/pltclu.start_proc DefineCustomStringVariable pltcl.c:471/:478. docs-distilled 242→250. Markers left [in-progress:cloud/pg-docs-miner/2026-07-07] for the merger to flip to the squash SHA.)

[in-progress:cloud/pg-docs-miner/2026-07-07] plperl-under-the-hood https://www.postgresql.org/docs/current/plperl-under-the-hood.html
[in-progress:cloud/pg-docs-miner/2026-07-07] plperl-builtins https://www.postgresql.org/docs/current/plperl-builtins.html
[in-progress:cloud/pg-docs-miner/2026-07-07] plpython-data https://www.postgresql.org/docs/current/plpython-data.html
[in-progress:cloud/pg-docs-miner/2026-07-07] plpython-database https://www.postgresql.org/docs/current/plpython-database.html
[in-progress:cloud/pg-docs-miner/2026-07-07] plpython-subtransaction https://www.postgresql.org/docs/current/plpython-subtransaction.html
[in-progress:cloud/pg-docs-miner/2026-07-07] pltcl-overview https://www.postgresql.org/docs/current/pltcl-overview.html
[in-progress:cloud/pg-docs-miner/2026-07-07] pltcl-dbaccess https://www.postgresql.org/docs/current/pltcl-dbaccess.html
[in-progress:cloud/pg-docs-miner/2026-07-07] pltcl-global https://www.postgresql.org/docs/current/pltcl-global.html
[skipped:thin-folds-into-siblings] plperl-data https://www.postgresql.org/docs/current/plperl-data.html  # 2026-07-07: WebFetch returns only "arguments arrive as text form" one-liner; the SV/AV/HV↔Datum detail lives on plperl-funcs/-builtins — captured inline in plperl-builtins.md. Do not re-queue standalone.
[skipped:thin-folds-into-siblings] pltcl-data https://www.postgresql.org/docs/current/pltcl-data.html  # 2026-07-07: same — only "values pass as text" one-liner; NULL/composite handling captured in pltcl-dbaccess.md (-nulls/argisnull) + pltcl-overview.md. Do not re-queue standalone.
