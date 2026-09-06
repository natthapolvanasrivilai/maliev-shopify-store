# PIMM operating-motion review

These are local native-CAD proofs, not released storefront clips. Do not publish
them or start high-resolution rendering until the motion review is complete.

Seven 12-second shots: pneumatic overview, pressure adjustment, temperature
startup, supplied mold loading, pellet loading, injection, full-machine orbit.
The pressure knob and locking nut lift, turn clockwise as viewed from above,
then reseat. The gauge sweeps from zero toward 0.7 MPa. The connected five-body
plunger assembly travels 145 mm, holds, and retracts. Temperature time is
compressed; independent 215/220 C set values are illustration values, not a
resin-processing recommendation. Both displays blink twice at completion.

The mold is the supplied `4040 - Slot 10 - Single Cavity Mold.step`. Its six
meshes retain their native dimensions. The source sprue axis is X=6, Y=0 mm:
rotate the glTF assembly -90 degrees about X and offset X by -6 mm, placing its
bottom on the 42.5 mm-high base plate. No vise, stops, or invented spacer is used.
Source and tessellation hashes are in `fixtures/4040-single-cavity.json`.

For quick motion review, use the component renderer with `--operations
--profile motion-proof --samples 8 --frame-step 3`. This renders 96 images per
shot with Eevee at 640x360, sampling the 24 fps timeline at 8 fps. Use a fresh
output directory after changing animation or framing; existing frames are
resumed, not overwritten. `--proof` produces six poses instead of a moving clip.
Use Blender's `--python-exit-code 1` so validation errors fail the command.

`node scripts/package-pimm-motion-proof.mjs <render-directory>` validates the
frame count and produces seven rough MP4s plus a combined review. Proof lighting
and sampling do not represent the final Cycles render. The storefront continues
to use its existing videos until new media pass review, packaging, and browser
validation. High-resolution preparation scripts are separate and must not run
as part of this proof workflow.
