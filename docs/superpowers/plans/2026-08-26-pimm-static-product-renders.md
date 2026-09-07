# PIMM Static Product Renders Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce six new governed, photoreal static renders for the unified PIMM 30G/50G product page and promote verified WebP derivatives into the Shopify theme.

**Architecture:** Add a contract-first static-shot registry beside the existing front-hero authoring module. Every shot links the approved `PIMM_PUBLISHED` master collection, reuses the pinned studio lighting/HDRI baseline, owns only scene-local camera/light/world/catcher state, and passes immutable proof approval before final rendering. Storefront derivatives are created only from approved native finals.

**Tech Stack:** Blender 5.2, Cycles, AgX, OpenImageDenoise, Python 3, `unittest`, existing PIMM scene/proof/final publication modules, OpenImageIO/ffmpeg only where already licensed and locked.

**Spec:** `docs/superpowers/specs/2026-08-26-pimm-unified-product-configurator-design.md`

## Global Constraints

- Canonical root: `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders`.
- Never mutate authoritative STEP sources, product meshes, approved materials, decals, displays or master files.
- One shot per `.blend`; scenes link `PIMM_PUBLISHED` and own only shot-specific state.
- Reuse pinned `studio_kontrast_04_4k.exr`, SHA-256 `9A982ADE8702402A895F3297BF3CB652CB6F9C8C9CCCA961D2C7603107094A06`, strength `0.5`, rotation `0`.
- Use AgX Medium High Contrast, exposure `0`, gamma `1`, 36mm sensor, 5500K lights and the existing lower-bounce rig.
- Complete-machine shots use 85mm at f/11; detail groups use 135mm at f/8–f/11.
- Proof changes require a new generation and owner approval; final renders require the exact approved proof state.
- No animation, AI enhancement, generative repainting, cloud rendering or upscaling.
- No production deployment or Shopify publication.

---

### Task 1: Define the six-shot registry and contract payloads

**Files:**
- Create: `scripts/blender/pimm_production/blender_static_product_scene.py`
- Create: `scripts/blender/pimm_production/tests/test_static_product_scene.py`
- Modify: `scripts/blender/pimm_production/tests/__init__.py`

**Interfaces:**
- Consumes: `MachineConfig`, `CameraPose`, `studio_light_specs()`, `studio_environment_specs()`, `studio_world_environment_spec()` and `scaled_camera_distance()` from `blender_static_hero_scene.py`; `SceneContract` from `scene_contract.py`.
- Produces: `ShotConfig`, `SHOT_CONFIGS`, `contract_payload(config)`, `prepare_contract(config)` and CLI `--shot-id <id> --prepare-contract`.

- [ ] **Step 1: Write the failing registry tests**

```python
EXPECTED = {
    "pimm-30g--overview--three-quarter": ("30G", "overview", "three-quarter", 85.0),
    "pimm-30g--engineering--controls": ("30G", "engineering", "controls", 135.0),
    "pimm-30g--tooling--front-detail": ("30G", "tooling", "front-detail", 135.0),
    "pimm-50g--overview--three-quarter": ("50G", "overview", "three-quarter", 85.0),
    "pimm-50g--engineering--controls": ("50G", "engineering", "controls", 135.0),
    "pimm-50g--tooling--front-detail": ("50G", "tooling", "front-detail", 135.0),
}

def test_registry_has_exact_static_shots(self):
    module = self._module()
    self.assertEqual(set(module.SHOT_CONFIGS), set(EXPECTED))
    for shot_id, (machine, purpose, view, lens) in EXPECTED.items():
        config = module.SHOT_CONFIGS[shot_id]
        self.assertEqual((config.machine, config.purpose, config.view), (machine, purpose, view))
        self.assertEqual(config.focal_length_mm, lens)
        self.assertEqual((config.output_width, config.output_height), (2400, 1800))
        self.assertIsNone(config.animation_contract)
```

- [ ] **Step 2: Run the focused test and confirm the module is absent**

Run: `python -m unittest scripts.blender.pimm_production.tests.test_static_product_scene -v`

Expected: FAIL because `blender_static_product_scene` does not exist.

- [ ] **Step 3: Add the immutable shot model and exact registry**

```python
@dataclass(frozen=True)
class ShotConfig:
    scene_id: str
    machine: str
    purpose: str
    view: str
    focal_length_mm: float
    aperture_fstop: float
    output_width: int = 2400
    output_height: int = 1800
    animation_contract: None = None

SHOT_CONFIGS = {
    shot.scene_id: shot
    for shot in (
        ShotConfig("pimm-30g--overview--three-quarter", "30G", "overview", "three-quarter", 85.0, 11.0),
        ShotConfig("pimm-30g--engineering--controls", "30G", "engineering", "controls", 135.0, 8.0),
        ShotConfig("pimm-30g--tooling--front-detail", "30G", "tooling", "front-detail", 135.0, 11.0),
        ShotConfig("pimm-50g--overview--three-quarter", "50G", "overview", "three-quarter", 85.0, 11.0),
        ShotConfig("pimm-50g--engineering--controls", "50G", "engineering", "controls", 135.0, 8.0),
        ShotConfig("pimm-50g--tooling--front-detail", "50G", "tooling", "front-detail", 135.0, 11.0),
    )
}
```

Build contract paths as `scenes/contracts/<scene_id>.json`, scene paths as `scenes/stills/<scene_id>.blend`, and master paths as `masters/PIMM-<machine>-MASTER.blend`. `contract_payload()` must set `complete_product: true`, `master_collection: PIMM_PUBLISHED`, `alpha: true`, exact live hashes, 2400 x 1800 output and `animation_contract: null`.

- [ ] **Step 4: Add fail-closed contract tests**

Test that an unknown shot ID, existing contract path, non-85/135 lens, animation payload, wrong output dimensions and a destination outside `scenes/contracts` are rejected before any write.

- [ ] **Step 5: Run the focused tests**

Run: `python -m unittest scripts.blender.pimm_production.tests.test_static_product_scene -v`

Expected: PASS.

- [ ] **Step 6: Commit the registry slice**

```powershell
git add -- scripts/blender/pimm_production/blender_static_product_scene.py scripts/blender/pimm_production/tests/test_static_product_scene.py scripts/blender/pimm_production/tests/__init__.py
git commit -m "Define governed PIMM static product shots"
```

### Task 2: Implement deterministic camera targets and scene authoring

**Files:**
- Modify: `scripts/blender/pimm_production/blender_static_product_scene.py`
- Modify: `scripts/blender/pimm_production/tests/test_static_product_scene.py`

**Interfaces:**
- Consumes: exact `ShotConfig` entries from Task 1 and stable product IDs discovered from the open linked master.
- Produces: `inspect_target_candidates(bpy, machine)`, `load_target_manifest(path)`, `resolve_target_bounds(bpy, config, target_manifest)`, `camera_pose(bounds_min, bounds_max, config)`, `author_scene(bpy, config, target_manifest)` and CLI modes `--inspect-targets` / `--author-scene --target-manifest "M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\manifests\PIMM-static-shot-targets-v1.json"`.

- [ ] **Step 1: Write failing pure camera tests**

```python
def test_three_quarter_camera_is_level_and_uses_realistic_orbit(self):
    module = self._module()
    pose = module.orbit_camera_pose((-200, -200, 0), (220, 160, 900), 2400, -24.0, 0.0)
    self.assertLess(pose.location[1], pose.target[1])
    self.assertNotEqual(pose.location[0], pose.target[0])
    self.assertAlmostEqual(pose.location[2], pose.target[2])

def test_detail_target_requires_one_nonempty_stable_id_group(self):
    module = self._module()
    with self.assertRaisesRegex(ValueError, "stable target"):
        module.bounds_for_objects([])
```

- [ ] **Step 2: Run the tests and confirm the new functions are absent**

Run: `python -m unittest scripts.blender.pimm_production.tests.test_static_product_scene -v`

Expected: FAIL on missing camera/target functions.

- [ ] **Step 3: Implement normalized camera geometry**

Use product bounds for overview framing. Use explicit stable-ID lists for controls and tooling, resolved from the linked master after read-only inspection and stored in `manifests/PIMM-static-shot-targets-v1.json`. Never select targets by mutable Blender display name alone.

```python
def orbit_camera_pose(bounds_min, bounds_max, distance, azimuth_degrees, elevation_degrees):
    center, _size = _center_and_size(bounds_min, bounds_max)
    azimuth = math.radians(azimuth_degrees)
    elevation = math.radians(elevation_degrees)
    horizontal = distance * math.cos(elevation)
    return CameraPose(
        location=(
            center[0] + horizontal * math.sin(azimuth),
            center[1] - horizontal * math.cos(azimuth),
            center[2] + distance * math.sin(elevation),
        ),
        target=center,
        pitch_degrees=elevation_degrees,
    )
```

Use `-24°` azimuth and `0°` elevation for overview. Detail target lists must be written into each generated scene's contract evidence and must contain the gauge/regulator/controller/actuator artwork group for engineering or nozzle/platen/fixture group for tooling.

- [ ] **Step 4: Implement authoring without master mutation**

`author_scene()` must:

1. Require the exact shared-template source and exact master/material hashes.
2. Link `PIMM_PUBLISHED` through the existing scene-template path.
3. Reuse the approved HDRI, key/fill/base-bounce/strip specs and physical catcher.
4. Set 85mm or 135mm, 36mm sensor, governed f-stop and focus distance.
5. Set Cycles, AgX, zero exposure, 100% 2400 x 1800 and transparent film.
6. Embed canonical scene-contract JSON and save only to the contracted new path.
7. Reopen the saved scene in a fresh Blender process and run `validate_open_render_scene()`.

- [ ] **Step 5: Add mutation and framing regression tests**

Test that authoring rejects a local product mesh, localized linked material, wrong HDRI hash, missing artwork target, crop outside the contracted frame, nonzero exposure and pre-existing destination.

- [ ] **Step 6: Run focused and boundary suites**

```powershell
python -m unittest scripts.blender.pimm_production.tests.test_static_product_scene scripts.blender.pimm_production.tests.test_static_hero_scene scripts.blender.pimm_production.tests.test_scene_contract -v
```

Expected: PASS.

- [ ] **Step 7: Commit deterministic authoring**

```powershell
git add -- scripts/blender/pimm_production/blender_static_product_scene.py scripts/blender/pimm_production/tests/test_static_product_scene.py
git commit -m "Author photoreal PIMM static product scenes"
```

### Task 3: Inspect stable targets and author the six external scenes

**Files:**
- Create externally: six `scenes/contracts/*.json` files named by `SHOT_CONFIGS`.
- Create externally: six `scenes/stills/*.blend` files named by `SHOT_CONFIGS`.
- Create externally: `manifests/PIMM-static-shot-targets-v1.json`.
- Preserve: all files under `masters/`, `sources/` and existing final releases.

**Interfaces:**
- Consumes: Task 2 CLI and the live published 30G/50G masters.
- Produces: six independently reopened, zero-error still scenes.

- [ ] **Step 1: Run read-only master and tool preflight**

```powershell
$preflight = (Resolve-Path -LiteralPath 'scripts\blender\pimm_production\blender_session_preflight.py').Path
& 'D:\Blender 5.2\blender.exe' -b 'M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\masters\PIMM-30G-MASTER.blend' --python-exit-code 1 -P $preflight
& 'D:\Blender 5.2\blender.exe' -b 'M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\masters\PIMM-50G-MASTER.blend' --python-exit-code 1 -P $preflight
& 'D:\Blender 5.2\blender.exe' -b 'M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\masters\PIMM-30G-MASTER.blend' --python-exit-code 1 -P scripts\blender\master_assets\pimm_master_audit.py -- --mode publish
& 'D:\Blender 5.2\blender.exe' -b 'M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\masters\PIMM-50G-MASTER.blend' --python-exit-code 1 -P scripts\blender\master_assets\pimm_master_audit.py -- --mode publish
```

Expected: both masters publishable, two governed artwork items per machine, zero audit errors, pinned Blender/HDRI/tool hashes unchanged.

- [ ] **Step 2: Resolve and record exact stable target IDs**

Run the new read-only `--inspect-targets` command for each machine. Require exactly one validated engineering group and one tooling group. Confirm engineering evidence includes gauge/regulator/controller/actuator artwork and tooling evidence includes nozzle/platen/fixture geometry. Write only the selected `pimm_stable_id` values, machine identities and the current master hashes to `manifests/PIMM-static-shot-targets-v1.json`. If uniqueness fails, stop; do not choose by visual guess.

- [ ] **Step 3: Prepare all six contracts**

```powershell
$shots = @(
  'pimm-30g--overview--three-quarter','pimm-30g--engineering--controls','pimm-30g--tooling--front-detail',
  'pimm-50g--overview--three-quarter','pimm-50g--engineering--controls','pimm-50g--tooling--front-detail'
)
foreach ($shot in $shots) {
  python scripts\blender\pimm_production\blender_static_product_scene.py --shot-id $shot --prepare-contract
  if ($LASTEXITCODE -ne 0) { throw "Contract preparation failed: $shot" }
}
```

- [ ] **Step 4: Author and reopen all six scenes**

Run each contracted shared template in Blender with `--author-scene`, then run `blender_scene_validator.py` in a fresh background process against each saved `.blend`.

Expected: six unique scene paths, no private machine meshes, no material overrides, correct 85/135mm lens, correct output dimensions and zero validation errors.

- [ ] **Step 5: Verify protected fingerprints**

Hash masters, material library and authored artwork before and after. Expected: byte-identical protected inputs.

No repository commit applies to this off-repository scene-authoring task. Record paths, hashes, stable target IDs and validation output in the execution report.

### Task 4: Render immutable proofs and obtain shot approval

**Files:**
- Create externally: six proof generations under `renders/proofs/<proof-id>/`.
- Create externally: six labelled contact sheets and 100% artwork/material crops.

**Interfaces:**
- Consumes: six validated scene contracts from Task 3.
- Produces: owner decisions bound to exact proof IDs; no final output yet.

- [ ] **Step 1: Create composition proof contracts**

Use 25% resolution, 32 Cycles samples, denoising, transparent RGBA and required white/checker/dark composites. Bind exact scene, master, material-library, script, Blender, HDRI and render-setting hashes.

- [ ] **Step 2: Render the six composition proofs**

Invoke `blender_proof_render.py` once per shot with a unique generation ID. Expected: `status: pass`, `fingerprints_unchanged: true`, no pending artifacts and no output outside the generation root.

- [ ] **Step 3: Create material/lighting crops**

For overview shots include full-machine and lower-base crops. For engineering include gauge, regulator label, AirTAC decal and controller segments. For tooling include nozzle, platen, fixture grid, contact feet and underside shadow.

- [ ] **Step 4: Inspect quantitative and visual gates**

Reject any shot with clipped stainless highlights, featureless white faces, crushed black parts, dark base plate, floating feet, catcher boundary, clipped shadow tail, unreadable artwork or a component group outside acceptable focus.

- [ ] **Step 5: Stop for owner approval**

Present a contact sheet keyed by exact proof ID and shot ID. Do not run Task 5 until every required shot is approved. Any requested camera/light/world/material/output change creates a new proof generation.

No repository commit applies to immutable proof artifacts.

### Task 5: Render approved finals and promote storefront derivatives

**Files:**
- Create externally: six native final releases under `renders/final/<release-id>/<shot-id>/`.
- Create: `assets/pimm-machine-30g-overview-three-quarter.webp`
- Create: `assets/pimm-machine-30g-engineering-controls.webp`
- Create: `assets/pimm-machine-30g-tooling-front-detail.webp`
- Create: `assets/pimm-machine-50g-overview-three-quarter.webp`
- Create: `assets/pimm-machine-50g-engineering-controls.webp`
- Create: `assets/pimm-machine-50g-tooling-front-detail.webp`
- Create or replace from approved existing finals: `assets/pimm-machine-{30g,50g}-hero-front.webp`
- Create: `scripts/tests/pimm-unified-render-assets.test.mjs`

**Interfaces:**
- Consumes: exact approved proof IDs from Task 4.
- Produces: eight named theme WebPs with manifest-bound source hashes and dimensions.

- [ ] **Step 1: Write the failing asset contract**

```javascript
const assets = [
  'pimm-machine-30g-hero-front.webp',
  'pimm-machine-30g-overview-three-quarter.webp',
  'pimm-machine-30g-engineering-controls.webp',
  'pimm-machine-30g-tooling-front-detail.webp',
  'pimm-machine-50g-hero-front.webp',
  'pimm-machine-50g-overview-three-quarter.webp',
  'pimm-machine-50g-engineering-controls.webp',
  'pimm-machine-50g-tooling-front-detail.webp',
];

test('unified PIMM assets are nonempty WebP files', async () => {
  for (const asset of assets) assert.ok((await stat(new URL(`../../assets/${asset}`, import.meta.url))).size > 20_000);
});
```

- [ ] **Step 2: Confirm the asset test fails before promotion**

Run: `node --test scripts/tests/pimm-unified-render-assets.test.mjs`

Expected: FAIL on missing files.

- [ ] **Step 3: Authorize and render native finals**

Use `blender_final_render.py` with each exact approval and final contract. Use 128–256 adaptive samples. Expected: release manifests validate dimensions, RGBA, component masks, hashes and unchanged live state.

- [ ] **Step 4: Produce WebP derivatives from native finals**

Use locally locked OpenImageIO or ffmpeg at quality 88–92 with alpha preserved. Do not enlarge any source. Generate mobile-specific derivatives only if crop validation proves the native composition cannot survive responsive presentation.

- [ ] **Step 5: Run asset and image metadata checks**

Run: `node --test scripts/tests/pimm-unified-render-assets.test.mjs`

Expected: PASS for all eight names, WebP headers, nonzero alpha bounds and contracted dimensions.

- [ ] **Step 6: Run the affected Blender regression suite**

```powershell
python -m unittest scripts.blender.pimm_production.tests.test_static_product_scene scripts.blender.pimm_production.tests.test_static_hero_scene scripts.blender.pimm_production.tests.test_published_artwork scripts.blender.pimm_production.tests.test_artwork_verification_render scripts.blender.pimm_production.tests.test_scene_contract scripts.blender.master_assets.tests.test_pimm_master_audit scripts.blender.pimm_production.tests.test_proof_contract -v
```

Expected: PASS.

- [ ] **Step 7: Commit only promoted storefront assets and their contract**

```powershell
git add -- assets/pimm-machine-30g-hero-front.webp assets/pimm-machine-30g-overview-three-quarter.webp assets/pimm-machine-30g-engineering-controls.webp assets/pimm-machine-30g-tooling-front-detail.webp assets/pimm-machine-50g-hero-front.webp assets/pimm-machine-50g-overview-three-quarter.webp assets/pimm-machine-50g-engineering-controls.webp assets/pimm-machine-50g-tooling-front-detail.webp scripts/tests/pimm-unified-render-assets.test.mjs
git commit -m "Add photoreal PIMM configurator renders"
```
