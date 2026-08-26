# PIMM Rendering and Approval

## Gate 0: preflight

Verify STEP/master/material identity, scene dependencies, linked geometry and materials, units and scale, controller values, animation endpoints, output path, generation ID, and absence of paid/cloud dependencies. Any failure blocks rendering.

## Gates 1–3: proofs and owner decision

Composition proof uses 12.5–25% contracted resolution, 16–32 Cycles samples, denoising, and white/checker/dark composites. Material and lighting proof normally uses 25% resolution, 32–64 samples, masks, targeted crops, quantitative tests, and a labelled contact sheet. The owner may approve, reject, or annotate individual shots. Record proof/contact-sheet, STEP, master, material-library, scene, script, and settings hashes plus decision, notes, owner, and timestamp.

Changing geometry, material, camera, lighting, world, compositor, animation, output size, or render settings invalidates approval.

## Gates 4–5: finals and release

Only an approved exact proof state may render native resolution. Use Cycles adaptive sampling (normally 128–256 maximum samples), float EXR master, and the required transparent PNG, WebP, or video deliverables. AI upscaling, cloud enhancement, generative texture replacement, and product repainting are prohibited.

Release QA verifies original-resolution visual inspection, white/checker/dark composites, physical controller value, dimensions, alpha mode, shadow containment, edge continuity, static/poster/animation endpoint parity, provenance hashes, and consumer filename/format. Consumers resolve only one immutable approved release manifest; proof, rejected, temporary, archived, and mixed-generation outputs are invalid. Output directories are immutable after approval.

## Task 9 read-only governance report

Observed 2026-08-17 in Asia/Bangkok. This is a read-only handoff snapshot, not a render, approval, publication, archive application, or storefront promotion.

| Gate | Read-only status |
|---|---|
| Documentation parity | Canonical and installed `AGENTS.md` bytes match at SHA-256 `99679D4627F13AD2ADD3B74BDCEFB0924E67CD98F4861E0C07D21B0FA1F8F30A`; canonical and installed `README.md` bytes match at `2D54B0DF1D1142927A6A3C8C4C2B0C480F19B9EC94216749F207A5A8A5A39EDE`. |
| Tool policy | `pimm-free-tools-lock/v1` contains only the pinned local Blender, BlenderMCP, Python, and Pillow records. Runtime policy rejects network-bearing, paid, cloud, generative, and upscaling additions. |
| Machine semantics | 30G remains physical `300/300`; 50G remains physical `350/350`. Both animation contracts are `blocked_pending_owner_motion_map` with no allowed controls, so animation is unavailable until an owner-approved motion map is published. |
| Master/material publication | Fresh read-only working audits of the real masters each account for 554 solids, preserve source/master identity, report zero integrity or disconnected-geometry errors, and find 10 unassigned solids. Both are `publishable=false`; the production linked template is absent and the real workflow remains `blocked_manual_material_approval`. |
| Scene safety | Fixture-native validation rejects private or stripped scene-local product meshes, localized product materials, overrides, incomplete published collections, and non-native scene resolution. No production linked scene exists while material publication is blocked. |
| Proofs | Proof contracts permit only isolated `renders/proofs/<generation-id>` output at 12.5–25% resolution, bounded Cycles samples, denoising, and required evidence. The recorded Task 5 results are temporary fixture-only validations; their fixture generation IDs are absent from the production proof tree. |
| Finals/releases | Native finals require a current immutable owner approval for the exact proof state. Task 6 proves that gate and atomic immutable release publication with temporary native fixtures only. The production approval and release directories contain no records, and the Task 7 render inventory contains zero releases. |
| Consumers | Task 7 publication `bc320a119a214ec5907288ac78412e06` records 87 ambiguous and 400 unresolved legacy references; these remain migration/review blockers, not approved release consumers. Release validation rejects proof, rejected, temporary, archive, mutable, mixed-generation, and unmanifested paths. |
| Inventory | The current Task 7 inventory accounts exactly once for 5,434 discovered active-root items totaling 23,278,163,353 bytes. Record paths equal the complete unique discovered-path set, and inventory, render inventory, and consumer graph share the publication ID above. A fresh read-only `verify_published_outputs(ASSET_ROOT)` re-hashed and identity-checked the complete external tree and returned `PUBLISHED_AUTHORITY bc320a119a214ec5907288ac78412e06 5434 5434`. |
| Archive | The immutable zero-item plan is outside the active inventory root at sibling governance path `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders-governance\manifests\archive-plans\legacy-recovery-files-01.json`, SHA-256 `80484BBE3E420987407306E908BB9E0AF7E42B785396855E2C72D74224DE608E`. It covers 0 items and 0 bytes. No exact-plan approval exists, its pending-delete destination does not exist, and no move was applied. Fixture tests prove hash-preserving restore and reject any permanent-delete action. No permanent deletion occurred. |
| Blender session evidence | A BlenderMCP connector was unavailable in this execution context, so no BlenderMCP evidence is claimed. Blender 5.2.0 LTS ran the checked-in background CLI preflight with `dirty=false`, then fresh working audits for both real masters; these read-only substitutes did not save, render, mutate an interactive selection, or terminate an interactive Blender process. |

Validation on the settled Task 9 slice: focused governance Node tests passed 15/15; master-assets Python passed 66/66; production-governance Python passed 234/234; Python compilation and `git diff --check` passed; and Theme Check inspected 256 files with zero errors and three dependency-template warnings. The combined Node run passed 21/23. Its two known external handoff failures are unchanged: the master-assets contract still expects the superseded STEP hash `024BC2D5FD847D3EE1F65E83D7C3CB42459E5626177008509CF877B4DA3E8A1A`, and its generated-artifact assertion still expects 491 master objects while the current manifests and read-only Blender audits account for 554. Task 9 does not weaken or rewrite those earlier contracts.

The next production action is manual owner material assignment, followed by working and publish audits. Proof generation, native finals, releases, archive application, and storefront migration remain blocked until their exact upstream approvals exist.
