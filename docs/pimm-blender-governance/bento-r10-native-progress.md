# Approved r10 native release preparation

The owner's exact r10 proof approval is recorded in `bento-r10-approval.json`.
It authorizes local preview integration with automatic playback and no pause
button, with a static reduced-motion alternative. No production deployment is
authorized. The original review manifest and scenes remain immutable.

## Native pipeline

- `blender_bento_r10_final.py` reopens each approved scene at its authored 100%
  dimensions and 128 samples. It checks exact contract, source approval, scene,
  proof, master, material library and tool-lock hashes. Per-frame receipts allow
  safe resumption, rejecting mismatched or unreceipted files.
- Native output: `renders/final/bento-20260903-r10-native/<shot>/` under the
  governed external asset root. All four stills are complete. The 192-frame,
  24 fps camera-only orbit remains in progress at this handoff.
- `encode_bento_r10_video.py` uses the already locked Blender 5.2 build and its
  bundled FFmpeg libraries, not a separate executable. Two native test frames
  successfully encoded at 2400 × 1200, 24 fps. This fixture is not a release.
- `export_bento_r10_assets.py` accepts only completed native receipts and a
  matching video receipt. Lossless stills retain exact native pixels; controls
  uses the orbit's first frame for poster parity. H264 video retains native
  dimensions and cadence without interpolation, upscaling or retouching.

## Storefront readiness

The automatic MP4 component and policy tests are prepared but deliberately not
wired into Liquid while the native animation is incomplete. Existing r06
images remain visible. Reduced motion, data saving, offscreen state, hidden
tabs, errors and autoplay rejection retain the accessible static image.
There are no pause/replay buttons. No new user-facing strings are needed.

The owner subsequently requested a white studio for configuration; its separate
r11 proof needs approval. Do not silently promote the superseded gray
configuration final. Final release integration must combine the exact approved
shots in a provenance-bound release manifest, update the four static URLs and
controls MP4 URL, and then validate actual playback, reduced motion, responsive
layout and video/still parity in the local browser before declaring completion.

No final asset promotion or storefront animation completion is claimed here.
