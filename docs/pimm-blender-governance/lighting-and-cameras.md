# PIMM Lighting and Cameras

The standard product presentation is a clean white studio with physically meaningful reflections: broad area lights, studio-card gradients, reflection cards that shape polished cylinders without washing broad aluminum faces, calibrated world contribution, and AgX highlight rolloff. Use an effectively infinite physical Cycles shadow catcher with transparent RGBA output and a soft, complete, light ground shadow.

Camera contracts preserve full-product and intended feature framing. White, checker, and dark composites must show no catcher boundary, cropped shadow tail, dark contact bar, or lost silhouette. Image-space painted shadows, radial fake masks, clipped finite catcher planes, and arbitrary exposure compensation are prohibited. Render scenes own their cameras, lights, cards, catchers, compositor nodes, passes, outputs, and paths; they never own product geometry or local copies of linked product materials.
