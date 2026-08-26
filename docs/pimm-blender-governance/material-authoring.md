# PIMM Material Authoring

`PIMM-MATERIAL-LIBRARY.blend` owns shared physical finishes. Linked shared materials must not be made local in a machine master or render scene. Machine branding, serial labels, controller artwork, decals, and display materials remain local to their machine master. Manual material assignments are authoritative: automation may inspect, report, or suggest, never overwrite approved work.

Validate materials under both a neutral audit rig and approved studio rig. Treat these as distinct physical classes: CNC-milled aluminum, die-cast aluminum, satin extrusion, brushed stainless hairline, polished/nickel-plated shafts, satin/stainless fasteners, black oxide and heat-oxidized steel, powder-coated steel (including pink), brass, rubber/pneumatic tubing, nylon PA6, PEEK, 0.2 mm-layer ASA, white textile and steel-braided cables, and transparent or emissive controls. Procedural microstructure must remain physically plausible at product scale.

Reject broad clipped highlights, crushed shadows, missing roughness separation, black shaft troughs, flat cast surfaces, over-matte CNC faces, and identical treatment for distinct materials. Material approval is required before publishing `PIMM_PUBLISHED`, migrating render scenes, or producing native proof/final work.
