# PIMM 30G Machine Operation Contract

## Authority and current state

This document records only owner-approved machine facts. The PIMM 30G neutral master is the current pose authority. No stable controller segment IDs, material IDs, or motion controls are owner-approved in this contract.

The 30G controller must show physical seven-segment `300/300`. Both rows are geometry, not text: FONT objects, flat text, composited text, and image overlays are prohibited. Active segments require the applicable approved emissive material; inactive segment geometry must remain present. The candidate report is evidence for review only and is not approval to assign materials, alter digits, or promote an ID.

## Animation gate

Animation is **blocked_pending_owner_motion_map**. `allowed_controls` is empty. Do not move a platen, mold, injection component, pneumatic component, controller, hose, cable, or any other object. Do not infer an axis, travel limit, operating sequence, collision clearance, or cable dependency from the neutral scene.

Animation can begin only after the owner approves a complete named control/axis/limit map and it is recorded in the 30G JSON contract. That approval must identify physical MESH display segments and their approved emissive material IDs as well as every motion control.

An enabled contract must also name a nonempty machine/controller-local material-ID allowlist. Each active and inactive physical MESH segment must use one of those IDs; `UNASSIGNED` is never allowed. Each approved motion control records its transform channel and axis, and its Blender F-curve must contain only the approved channel/axis with start, operating, and final key values in that order and within the owner-approved limits.

## Required owner approval table

| stable object ID | human part name | control ID | axis | minimum | maximum | neutral | start | operating | final | hose/cable dependency | collision note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| _Owner approval required_ | _Owner approval required_ | _Owner approval required_ | _Owner approval required_ | _Owner approval required_ | _Owner approval required_ | _Owner approval required_ | _Owner approval required_ | _Owner approval required_ | _Owner approval required_ | _Owner approval required_ | _Owner approval required_ |

Until the owner supplies this table, the static neutral pose is the only authorized state.
