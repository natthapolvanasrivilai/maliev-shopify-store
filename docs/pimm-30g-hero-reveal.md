# 30G cinematic studio reveal

Local-preview hero enhancement only. The 50G page, machine specifications, prices,
and contact links retain their existing behavior.

## Native scene

`scripts/blender/pimm_production/blender_30g_hero_reveal.py` opens the governed 30G
master read-only and reuses the approved Cycles studio. No `.blend` save is called.
The temporary machine stage turns from -12 degrees to front over 48 native frames
at 24fps. Studio light powers rise from 30% to 100%; background emitters rise from
75% to 100%. Lighting reaches full power before the turn finishes.

- 1440 × 1920, 128 samples, fixed -0.15 exposure, no depth-of-field blur.
- Camera scale 1.08; the entire machine and soft ground contact remain in frame.
- No interpolated frames, CSS darkening, synthetic shadows, or edited shadow masks.
- The bright resting WebP is the exact final rendered frame.
- The initial WebP is the exact first rendered frame, used while eligible video loads.

The finalizer verifies native frame hashes, resolution, frame sequence, master
provenance and H.264 output metadata before creating a new release. It refuses to
overwrite an existing release. Native PNGs stay outside version control; the
release manifest records their hashes and the shipped derivatives.

## Browser behavior

`pimm-hero-reveal` progressively enhances a normal image. Video is loaded only when
the hero intersects the viewport, plays once, and rests on the final still after
decoding. The two-second intro has no playback or replay control.
Offscreen/hidden-page playback pauses and resumes only an unfinished intro.
Reduced-motion and data-saver visitors keep the bright still without loading video.
Playback rejection or a video error also restores the bright still.

The title settles by eight pixels once, without fading or gating visibility.
CTA links remain separate from the animation and usable throughout.

## Verification

- `npm run verify`
- `py -3 -m unittest scripts.tests.test_30g_hero_reveal`
- `py -3 scripts/tests/pimm-hero-reveal-browser.py` with local preview running

The browser check covers both locales, six viewport sizes, native video resolution,
one-time playback without replay, final still handoff, reduced motion and failed video.
It saves screenshots under the ignored `.codex-tmp/hero-reveal-browser` directory.
