# Approved final render execution

Started 2026-09-03 following the owner's instruction: "finish the renders already!"
This record describes running work, not a completed release or production deployment.

## Queue and boundaries

1. Existing frozen r22-native worker renders tooling: 192 frames, 1600 x 2000, 128 samples.
2. New r27 worker renders capacity: 192 frames, 800 x 1100, 48 samples, exactly the approved r24 benchmark settings. Persistent render data stays disabled to prevent the black-face flicker.
3. Frozen r22-native worker renders configuration: 840 frames, 2400 x 1200, 128 samples, seven pitch rows and 120 yaw views.
4. Delivery validates every PNG, float EXR, frame index, manifest and approval hash before encoding two MP4 loops and lossless WebP rotation frames. Delivery sizes are 800 x 1100, 800 x 1000 and 1200 x 600 respectively. No upscaling, repainting or geometry changes.

The native tooling/configuration settings retain their exact r22 approvals. Only capacity has an approved reduced-size/sampling benchmark; that approval is not silently broadened to other render settings. Browser derivatives may downsample the approved final pixels.

`finish-approved-bento-renders.ps1` waits for the identified tooling worker, then runs capacity and configuration sequentially. `finish-bento-delivery.ps1` waits for that queue and runs the fail-closed packager. All processes are local; the user's interactive Blender session is untouched. Both continuation helpers were launched hidden. They do not depend on another approval message or an open Codex tool session.

Initial process IDs (verify identity before acting; IDs can be reused): tooling 85028, render continuation 1664, delivery continuation 23944.

## Evidence and status

- First tooling frame rendered, PNG/EXR receipt saved, and PNG inspected visually.
- Early tooling frames took approximately 28–30 seconds each after scene setup. This is not an estimate for the unmeasured configuration sequence.
- Python compilation passed; 108 Bento tests passed, including seven new approval/completeness tests.
- PowerShell parser checks: zero errors in both continuation helpers.
- Real Blender H264 encode/decode smoke check: two completed native frames encoded at 800 x 1000, decoded dimensions and frame count verified.
- `npm run verify` passed: 157 component tests, 15 route tests, one opt-in live route test skipped; Theme Check zero errors, three existing CLI-template warnings.
- Full sequence completion, final rendered-video flicker inspection and final-review browser acceptance remain pending until the queue finishes. Do not describe them as passed.

Logs are ignored task artifacts under `.codex-tmp`: `bento-r23-tooling-final.log`, `bento-r27-capacity-final.log`, `bento-r23-configuration-final.log`, `bento-final-queue.log`, `bento-final-queue-error.log`, `bento-final-delivery.log`, `bento-final-delivery-error.log`.

Native roots are `renders/final/bento-20260903-r23-native-motion` and `renders/final/bento-20260903-r27-capacity-web-final` under the external Blender asset root. Existing r23 high-resolution capacity frame 1 is preserved but is not mixed into the r27 capacity sequence.

On success, the existing local review server can display `http://127.0.0.1:61284/bento-20260903-r28-final-motion-review/`. Its `index.html` is written only after all native frames, derivatives and videos validate. The review directory is an evidence presentation of final-render derivatives, not permission to reuse proof pixels. No Shopify template integration or production publication happens automatically.

Failed or unreceipted outputs are retained for inspection. A failed generation is not overwritten or silently treated as complete.
