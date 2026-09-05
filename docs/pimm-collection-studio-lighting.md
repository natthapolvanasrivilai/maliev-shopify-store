# Collection studio-lighting interaction

Release: `maliev-pimm-collection-lighting-20260902-r01`.

Hovering or keyboard-focusing a machine dims the other machine's physical studio.
There is no CSS brightness filter, translucent dark layer, exposure animation,
shadow compositing, or generated/interpolated intermediate frame. The active
machine retains its existing 24fps turntable. Cards do not lift or acquire borders.

## Render contract

- Two authoritative, hash-checked masters; no master files are saved or modified.
- Twelve native Cycles frames per model, 1440 × 1920, 128 samples, 24fps.
- A 0.5-second eased power ramp affects softboxes, reflection emitters, the HDRI,
  emissive cyclorama, and camera background. Machine display emissions stay on.
- Camera, geometry, material colors, and exposure remain fixed. The bright endpoint
  uses the existing motion camera scale of 1.24 and exposure of −0.15.
- The upward transition reverses those exact twelve frames. H.264 all-intra encoding
  permits corresponding-frame seeks when the pointer changes direction quickly.
- Reduced motion uses the native dim endpoint as a lossless WebP. Touch taps do
  not create sticky hover lighting. Labels remain separate, accessible HTML.
- Failed video playback restores the bright poster, never a CSS dimming substitute.

The renderer is `scripts/blender/pimm_production/blender_collection_card_render.py`
with `--lighting --samples 128 --scale 1.24` and the existing model/master arguments.
Use `--proof` only for half-resolution endpoint previews. The finalizer rejects
proofs, incorrect source hashes, missing frames, modified emitter ramps, and
non-native resolution before encoding:

```powershell
py -3 scripts/blender/pimm_production/finalize_collection_lighting.py --render-dir .codex-tmp/pimm-lighting-native-r01
```

The asset manifest records each native frame's hash and emitter multipliers, plus
the encoded clips' dimensions, frame counts, duration, and hashes. Existing bright
rotation assets remain unchanged. The lighting snippet is used only by the PIMM
collection section; routing, model specifications, and pricing contracts are unchanged.

## Validation

```powershell
npm run verify
py -3 -m unittest discover -s scripts/blender/pimm_production/tests -p 'test_collection*.py'
node --test --test-name-pattern="native studio lighting" scripts/tests/pimm-collection-responsive-browser.test.mjs
```

Set `PIMM_COLLECTION_PREVIEW_URL` privately for browser validation; never commit
its preview key. The focused browser test exercises English/Thai desktop, native
lighting/restoration, keyboard focus, reduced motion, and mobile touch. The full
browser matrix additionally exercises commerce/navigation boundaries.

This is local/development-theme work only, not a production release.

### Verified on 2026-09-02

- `npm run verify`: 87 asset/interaction/contract tests passed; 15 router tests
  passed and its opt-in live-route test was skipped. Theme Check: zero errors,
  three existing warnings in Shopify CLI dependency templates. There is no
  separate compiled application build target for this Liquid theme.
- Collection Python suite: 17 tests passed. Both source master hashes were
  checked again after rendering and remain unchanged.
- Focused real-browser lighting acceptance: passed English/Thai, keyboard,
  reduced motion, touch, and screenshot-pixel checks for both dimmed cards.
- High-DPI viewport check: all twelve English/Thai cases passed at 2× pixel
  density, from 390×844 through 1920×1080, with native-resolution images,
  retained rotation, no horizontal overflow, and one-screen desktop layout.
- Full browser acceptance reached commerce/navigation but remains blocked by
  the existing upstream Shopify preview `/cart.js` HTTP 401 and its non-JSON
  token error. That unrelated authentication error was not suppressed or changed.
  Re-run the full browser suite after the preview cart authentication is restored.
