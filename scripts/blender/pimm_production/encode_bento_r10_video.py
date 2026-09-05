"""Encode approved native PNG frames with the locked Blender's bundled FFmpeg."""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.blender.pimm_production.blender_bento_r10_final import APPROVAL, OUTPUT, contract_for, validate_final
from scripts.blender.pimm_production.blender_bento_final import checked_file
from scripts.blender.pimm_production.io_contract import sha256_file


def encode(paths, output, size, fps=24):
    import bpy
    if output.exists():
        raise FileExistsError(output)
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.fps, scene.render.fps_base = fps, 1
    scene.frame_start, scene.frame_end = 1, len(paths)
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    scene.sequencer_colorspace_settings.name = 'sRGB'
    editor = scene.sequence_editor_create()
    strip = editor.strips.new_image('Native Blender frames', str(paths[0]), channel=1, frame_start=1)
    for path in paths[1:]:
        strip.elements.append(path.name)
    strip.frame_final_duration = len(paths)
    strip.colorspace_settings.name = 'sRGB'
    scene.render.image_settings.media_type = 'VIDEO'
    scene.render.image_settings.file_format = 'FFMPEG'
    scene.render.ffmpeg.format = 'MPEG4'
    scene.render.ffmpeg.codec = 'H264'
    scene.render.ffmpeg.constant_rate_factor = 'PERC_LOSSLESS'
    scene.render.ffmpeg.ffmpeg_preset = 'GOOD'
    scene.render.ffmpeg.audio_codec = 'NONE'
    scene.render.filepath = str(output)
    bpy.ops.render.render(animation=True)


def main():
    contract = contract_for('controls-orbit')
    manifest = OUTPUT / 'controls-orbit/final.json'
    receipt = json.loads(manifest.read_text())
    validate_final(receipt, contract, 'controls-orbit')
    manifest_hash = sha256_file(manifest)
    paths = [checked_file(record['native_path'], record['native_sha256']) for record in receipt['frames']]
    output = OUTPUT / 'controls-orbit/pimm-bento-20260903-r10-30g-controls-orbit.mp4'
    encode(paths, output, contract['native_size'])
    contract_for('controls-orbit')
    checked_file(APPROVAL, receipt['approval_sha256'])
    checked_file(manifest, manifest_hash)
    result = {'filename': output.name, 'path': str(output), 'sha256': sha256_file(output),
              'bytes': output.stat().st_size, 'size': contract['native_size'], 'frames': 192,
              'fps': 24, 'duration_ms': 8000, 'approval_sha256': receipt['approval_sha256'],
              'scene_sha256': receipt['scene_sha256'], 'native_manifest': str(manifest),
              'native_manifest_sha256': manifest_hash,
              'encoder': 'Locked Blender 5.2 bundled FFmpeg; H264 perceptually lossless, sRGB, no resizing or retouching'}
    output.with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
    print('R10_VIDEO_READY=' + str(output), flush=True)


if __name__ == '__main__':
    main()
    os._exit(0)
