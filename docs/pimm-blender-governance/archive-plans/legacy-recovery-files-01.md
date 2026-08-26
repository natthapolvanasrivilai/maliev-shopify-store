# PIMM archive proposal: legacy-recovery-files-01

- Status: plan-only no-op; no move is authorized or required.
- Task 7 publication: `bc320a119a214ec5907288ac78412e06`.
- Exact `pending-archive` records: 0.
- Proposed items / bytes: 0 / 0.
- Highest-risk items: none.
- Proposed destination: `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders-archive\pending-delete\2026-08-17-legacy-recovery-files-01`.
- External plan: `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders-governance\manifests\archive-plans\legacy-recovery-files-01.json`.
- External plan SHA-256: `80484BBE3E420987407306E908BB9E0AF7E42B785396855E2C72D74224DE608E`.
- Authorization: no exact owner approval JSON exists. The empty plan is ineligible for apply.
- Blocker: the independently approved inventory contains no exact `pending-archive` record; records were not reclassified to create candidates.

The plan binds inventory `14267B1A04A0D11D97B7A92FE281224CF45BF1A2149EEBD6E884FFC017538BEE`, consumer graph `3C326AE7763290572A676457864C4DBB8342930EB7053C955854A420AB8BEF27`, and render-generation inventory `DDEF189FD0C77170DFC80CC5EEB794E1C1FF26A356AE3AD7460B918071F291DA`. No archive root, approval, or archive manifest was created, and no asset was moved or deleted.

The plan lives in a sibling governance root, not inside the governed active render root. This authority separation keeps Task 7's exact active-root freshness check current while retaining the brief's `manifests/archive-plans/<batch-id>.json` layout under the dedicated governance boundary.
