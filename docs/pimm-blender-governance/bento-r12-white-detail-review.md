# White tile detail correction — proof review

The white configuration tile now has a neutral 1px border, retaining its 14px
radius. Only this tile changes; there is no image filter, extra shadow or overlay.

The owner reported the r11 machine looked overexposed. A separate immutable
configuration-only proof was rendered from the approved r11 scene:

- Generation: `bento-20260903-r12-white-detail`.
- Root: `M:/30_Products/00_Pneumatic Injection Molding Machine/blender-product-renders`.
- Proof: `renders/proofs/bento-20260903-r12-white-detail/configuration.png`.
- Contract: `scenes/contracts/pimm-30g--bento-20260903-r12-white-detail--configuration.json`.
- Scene SHA-256: `F2454DD18CC1CAA2D17AD41A914C2A8E09ABA13697330A199B8A94BB050B5062`.
- Proof SHA-256: `DFC188976ED7CFCA10FE6792F16122FB0FCB6DBFF8E0FD7F87907E4A5737C3FD`.
- Exposure: +1.1 to +0.3; HDRI fill: 0.65 to 0.45; camera reflection wall: 0.65 to 0.35.
- White ground and ground wash, key lighting, camera, product geometry and
  published materials remain unchanged. All four foot levels were checked.
- Saved final-intent scene: 2400 × 1200, 128 samples. Review output: 25%, 64 samples.

The saved scene was reopened and checked before rendering. Python compilation,
proof render and source hash rechecks passed. This new lighting revision is
pending exact proof approval; it has not been promoted to a native final or theme
asset. The existing r10 orbit is already approved and does not need another
approval. Do not confuse those separate states.

Border validation: `npm run verify` passed 128 component/asset tests and 15 route
tests, with one opt-in route test skipped and three existing dependency warnings.
Six live English/Thai checks at 390, 768 and 1440px confirmed the border, radius,
equal portrait heights, loaded current images and no horizontal overflow.

`export_bento_motion_release.py` prepares the complete approved orbit addition
without replacing the white r11 stills. It checks all native frames through the
existing validator, exact poster parity, video receipt/source hashes, immutable
targets and the original per-still approval. It must run only after the 192-frame
render and Blender video encoding finish. Liquid video wiring and live playback
QA remain pending. No production deployment is authorized.
