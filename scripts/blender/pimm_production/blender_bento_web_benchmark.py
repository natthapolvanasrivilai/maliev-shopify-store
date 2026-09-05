"""Measure web-sized capacity renders; diagnostic proofs, never storefront releases."""
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.blender.pimm_production.blender_bento_r22_native import approved_review
from scripts.blender.pimm_production.blender_bento_final import checked_file
from scripts.blender.pimm_production.blender_bento_stable_reveal_proof import verify_product
from scripts.blender.pimm_production.io_contract import sha256_file
from scripts.blender.pimm_production.paths import ASSET_ROOT

GENERATION = 'bento-20260903-r24-web-benchmark'
FRAMES = (1, 50, 100)
SIZE = (800, 1100)
SAMPLES = 48


def configure(scene):
    scene.render.resolution_x, scene.render.resolution_y = SIZE
    scene.render.resolution_percentage = 100
    scene.cycles.samples = SAMPLES
    # Preserve the verified fix, even though rebuilding costs time per frame.
    scene.render.use_persistent_data = False


def main():
    import bpy
    started = time.perf_counter()
    root = ASSET_ROOT / 'renders/proofs' / GENERATION
    if root.exists():
        raise FileExistsError('Immutable benchmark generation already exists')
    review = approved_review()
    entry = review['sequences']['capacity']
    contract = json.loads(Path(entry['contract_path']).read_text())
    bpy.ops.wm.open_mainfile(filepath=entry['scene_path'])
    scene = bpy.context.scene
    product = bpy.data.collections['PIMM_PUBLISHED']
    verify_product(product, contract['original_product'])
    configure(scene)
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.refresh_devices()
    prefs.compute_device_type = 'OPTIX'
    for device in prefs.devices:
        device.use = device.type == 'OPTIX'
    if not any(device.use for device in prefs.devices):
        raise RuntimeError('OptiX GPU unavailable')
    root.mkdir(parents=True)
    result = {
        'generation': GENERATION, 'purpose': 'web render benchmark, not release approved',
        'source_scene': entry['scene_path'], 'source_scene_sha256': entry['scene_sha256'],
        'source_contract_sha256': entry['contract_sha256'],
        'worker_sha256': sha256_file(Path(__file__)),
        'size': SIZE, 'samples': SAMPLES, 'persistent_data': False,
        'adaptive_threshold': scene.cycles.adaptive_threshold,
        'preflight_and_setup_seconds': time.perf_counter() - started,
        'frames': [],
    }
    for frame in FRAMES:
        scene.frame_set(frame)
        output = root / f'frame-{frame:04d}.png'
        scene.render.filepath = str(output)
        start = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        seconds = time.perf_counter() - start
        result['frames'].append({'frame': frame, 'path': str(output),
                                 'sha256': sha256_file(output), 'render_seconds': seconds})
        print(f'WEB_BENCHMARK frame={frame} seconds={seconds:.2f}', flush=True)
    verify_product(product, contract['original_product'])
    checked_file(entry['scene_path'], entry['scene_sha256'])
    (root / 'benchmark.json').write_text(json.dumps(result, indent=2) + '\n')
    print('WEB_BENCHMARK_READY=' + str(root), flush=True)


if __name__ == '__main__':
    main()
    os._exit(0)
