"""Render the complete approved r24 capacity sequence, with float masters and receipts."""
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.blender.pimm_production.blender_bento_r22_native import (
    approved_review, frame_path, save_float_master, validate_frame)
from scripts.blender.pimm_production.blender_bento_final import checked_file
from scripts.blender.pimm_production.blender_bento_stable_reveal_proof import verify_product
from scripts.blender.pimm_production.blender_bento_web_benchmark import configure
from scripts.blender.pimm_production.io_contract import sha256_file
from scripts.blender.pimm_production.paths import ASSET_ROOT, REPO_ROOT

APPROVAL = REPO_ROOT / 'docs/pimm-blender-governance/bento-r24-web-approval.json'
GENERATION = 'bento-20260903-r27-capacity-web-final'
OUTPUT = ASSET_ROOT / 'renders/final' / GENERATION
SIZE = [800, 1100]


def validate_approval(approval, benchmark, entry):
    if (approval.get('decision') != 'approved' or
            approval.get('review_generation') != 'bento-20260903-r24-web-benchmark'):
        raise ValueError('Exact web-quality owner approval required')
    if (benchmark.get('size') != SIZE or benchmark.get('samples') != 48 or
            benchmark.get('persistent_data') is not False or
            benchmark.get('source_scene_sha256') != entry['scene_sha256'] or
            benchmark.get('source_contract_sha256') != entry['contract_sha256']):
        raise ValueError('Approved web settings or scene changed')


def main():
    import bpy
    review = approved_review()
    entry = review['sequences']['capacity']
    approval = json.loads(APPROVAL.read_text())
    benchmark_path = ASSET_ROOT / 'renders/proofs/bento-20260903-r24-web-benchmark/benchmark.json'
    checked_file(benchmark_path, approval['review_sha256'])
    benchmark = json.loads(benchmark_path.read_text())
    validate_approval(approval, benchmark, entry)
    for record in benchmark['frames']:
        checked_file(record['path'], record['sha256'])
    checked_file(Path(__file__).with_name('blender_bento_web_benchmark.py'), benchmark['worker_sha256'])
    contract = json.loads(Path(entry['contract_path']).read_text())
    authority = {
        'approval_sha256': sha256_file(APPROVAL),
        'review_sha256': approval['review_sha256'],
        'scene_sha256': entry['scene_sha256'], 'contract_sha256': entry['contract_sha256'],
        'worker_sha256': sha256_file(Path(__file__)),
    }
    bpy.ops.wm.open_mainfile(filepath=entry['scene_path'])
    scene = bpy.context.scene
    assert [scene.render.resolution_x, scene.render.resolution_y] == entry['native_intent']
    assert scene.frame_end == 192 and scene.render.fps == 24 and scene.render.fps_base == 1
    configure(scene)
    assert scene.cycles.adaptive_threshold == benchmark['adaptive_threshold']
    product = bpy.data.collections['PIMM_PUBLISHED']
    verify_product(product, contract['original_product'])
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.refresh_devices()
    prefs.compute_device_type = 'OPTIX'
    for device in prefs.devices:
        device.use = device.type == 'OPTIX'
    if not any(device.use for device in prefs.devices):
        raise RuntimeError('Approved OptiX GPU unavailable')
    print('CAPACITY_WEB_START=800x1100:48 samples:192 frames', flush=True)
    records = []
    for index in range(1, 193):
        output = frame_path(OUTPUT, 'capacity', index)
        receipt = output.with_suffix('.json')
        if receipt.exists():
            record = json.loads(receipt.read_text())
            validate_frame(record, output, SIZE, authority, index)
        else:
            if output.exists() or output.with_suffix('.exr').exists():
                raise FileExistsError('Unreceipted output preserved; inspect before resuming')
            output.parent.mkdir(parents=True, exist_ok=True)
            scene.frame_set(index)
            scene.render.filepath = str(output)
            started = time.perf_counter()
            bpy.ops.render.render(write_still=True)
            exr = output.with_suffix('.exr')
            save_float_master(scene, exr)
            record = {
                'index': index, 'path': str(output), 'sha256': sha256_file(output),
                'exr_path': str(exr), 'exr_sha256': sha256_file(exr), 'authority': authority,
                'render_seconds': time.perf_counter() - started,
            }
            validate_frame(record, output, SIZE, authority, index)
            receipt.write_text(json.dumps(record, indent=2) + '\n')
            print(f'CAPACITY_WEB_FRAME={index}/192 seconds={record["render_seconds"]:.2f}', flush=True)
        records.append(record)
    verify_product(product, contract['original_product'])
    checked_file(entry['scene_path'], authority['scene_sha256'])
    checked_file(entry['contract_path'], authority['contract_sha256'])
    checked_file(APPROVAL, authority['approval_sha256'])
    result = {
        'generation': GENERATION, 'shot': 'capacity', 'size': SIZE, 'samples': 48,
        'resolution_percentage': 100, 'persistent_data': False,
        'authority': authority, 'frames': records,
    }
    manifest = OUTPUT / 'capacity/final.json'
    if manifest.exists() and json.loads(manifest.read_text()) != result:
        raise ValueError('Immutable complete manifest differs')
    if not manifest.exists():
        manifest.write_text(json.dumps(result, indent=2) + '\n')
    print('CAPACITY_WEB_READY=' + str(manifest), flush=True)


if __name__ == '__main__':
    main()
    os._exit(0)
