# PIMM Blender Production Workspace

This workspace is a free-tools-only, reproducible production system for PIMM 30G and 50G machines. The source-controlled Shopify repository owns its canonical governance documents, validators, and Blender Python scripts. Do not edit the installed root documents here; update their canonical counterparts and run the documented installer.

## Authoritative inputs and units

- `masters/PIMM-30G-MASTER.blend` and `masters/PIMM-50G-MASTER.blend` are the authoritative machine masters.
- `masters/PIMM-MATERIAL-LIBRARY.blend` owns shared physical finishes.
- Immutable STEP sources and import manifests are the geometry authority.
- Each master contains independently selectable STEP solids with documented `0.01` object scale, Metric/Millimeters, and `scene.unit_settings.scale_length=0.001`.

Use linked render scenes under `scenes/`; they link an approved master’s `PIMM_PUBLISHED` collection and never embed private product copies or localize linked product materials. Manual material approval is a publication and render-scene gate, not a task for automation.

## Layout

```text
blender-product-renders/
├── AGENTS.md
├── README.md
├── sources/{cad,references,artwork}/
├── masters/
├── scenes/{30g,50g,shared-templates}/
├── renders/{proofs,approved,final}/
├── manifests/{sources,scenes,approvals,releases}/
├── scripts/
├── tools/
└── docs/
```

The pending-delete archive is a sibling workspace, not an active consumer path: `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders-archive\pending-delete`.

## Canonical documentation commands

Run these commands from the Shopify repository after changing canonical docs:

```powershell
python scripts/blender/pimm_production/workspace_docs.py --check
python scripts/blender/pimm_production/workspace_docs.py --install
python scripts/blender/pimm_production/workspace_docs.py --check
```

`--check` is read-only and fails on a missing or drifted external file. `--install` uses temporary files and atomic replacement, writing only this root’s `AGENTS.md`, `README.md`, and the approved Markdown files below `docs/`; it prints matching source and destination SHA-256 values.

## Operating sequence

1. Read `AGENTS.md`, inspect the current file/session, and identify objects by stable ID and STEP provenance before a modification.
2. Validate source/master/material identity, units, scale, linked geometry and materials, controller values, animation endpoint contract, output path, and the free-tool lock before a proof.
3. Generate low-cost composition and material/lighting proofs, including white, checker, and dark composites and a labelled owner-review contact sheet.
4. Record the owner decision with proof/source/master/material/scene/script hashes and render settings. A changed scene or setting invalidates approval.
5. Render native finals only from the exact approved proof state; validate output, alpha, dimensions, controller values, endpoints, hashes, and release manifest.

Do not use the obsolete OBJ/metres workflow or its `0.001` object scale.
