"""Fail-closed regression coverage for the approved native r10 release pipeline."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import json
import sys
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image

from scripts.blender.pimm_production import blender_bento_r10_final as native
from scripts.blender.pimm_production import encode_bento_r10_video as encoder
from scripts.blender.pimm_production import export_bento_r10_assets as exporter
from scripts.blender.pimm_production.io_contract import sha256_file


class NativeFixture(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.asset_root = self.root / 'external'
        self.output = self.asset_root / 'renders/final/bento-20260903-r10-native'
        self.approval = self.root / 'approval.json'
        self.write_json(self.approval, {'decision': 'approved'})
        for module in (native, exporter, encoder):
            for name, value in (('OUTPUT', self.output), ('APPROVAL', self.approval)):
                self.enterContext(patch.object(module, name, value))
        self.enterContext(patch.object(native, 'ASSET_ROOT', self.asset_root))
        self.enterContext(patch.object(native, 'REPO_ROOT', self.root))
        self.enterContext(patch.object(exporter, 'REPO_ROOT', self.root))
        self.source_approval = self.root / 'source-approval.json'
        self.enterContext(patch.object(native, 'SOURCE_APPROVAL', self.source_approval))
        self.contracts = {}

    def write_json(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding='utf-8')

    def make_final(self, shot='capacity'):
        animated = shot == 'controls-orbit'
        contract = {'generation': 'bento-20260903-r10-' + ('orbit' if animated else 'lighting'),
                    'shot': shot.removesuffix('-orbit'), 'scene_sha256': 'scene-' + shot,
                    'master_sha256': 'master', 'native_size': [16, 8]}
        self.contracts[shot] = contract
        records = []
        for frame in range(1, 193 if animated else 2):
            path = self.output / shot / f'frame-{frame:04d}.png'
            path.parent.mkdir(parents=True, exist_ok=True)
            Image.new('RGB', (16, 8), (frame % 256, 20, 80)).save(path)
            records.append({'frame': frame, 'native_path': str(path), 'native_sha256': sha256_file(path),
                            'approval_sha256': sha256_file(self.approval), 'scene_sha256': contract['scene_sha256']})
        receipt = {'schema': 'maliev.pimm-bento-final/v2', 'generation': contract['generation'],
                   'shot': shot, 'approval_sha256': sha256_file(self.approval),
                   'scene_sha256': contract['scene_sha256'], 'master_sha256': contract['master_sha256'],
                   'size': contract['native_size'], 'frames': records}
        self.write_json(self.output / shot / 'final.json', receipt)
        return receipt

    def check_final(self, shot='capacity'):
        with patch.object(exporter, 'contract_for', side_effect=lambda name: self.contracts[name]):
            return exporter.final_for(shot)


class NativeReceiptTests(NativeFixture):
    def test_matching_hash_cannot_disguise_proof_sized_pixels_as_native(self):
        receipt = self.make_final()
        path = Path(receipt['frames'][0]['native_path'])
        Image.new('RGB', (4, 2), 'white').save(path)
        receipt['frames'][0]['native_sha256'] = sha256_file(path)
        self.write_json(self.output / 'capacity/final.json', receipt)
        with self.assertRaisesRegex(ValueError, 'dimensions'):
            self.check_final()

    def test_exact_native_receipt_is_accepted(self):
        receipt = self.make_final()
        self.assertEqual(self.check_final(), receipt)

    def test_changed_receipt_authority_and_metadata_are_rejected(self):
        original = self.make_final()
        for field, bad in [('approval_sha256', 'other'), ('scene_sha256', 'other'),
                           ('master_sha256', 'other'), ('generation', 'proof'),
                           ('shot', 'tooling'), ('size', [4, 2])]:
            with self.subTest(field=field):
                receipt = deepcopy(original)
                receipt[field] = bad
                self.write_json(self.output / 'capacity/final.json', receipt)
                with self.assertRaises((ValueError, AssertionError)):
                    self.check_final()

    def test_frame_identity_and_authority_are_rejected(self):
        original = self.make_final()
        for field, bad in [('frame', 2), ('approval_sha256', 'other'), ('scene_sha256', 'other')]:
            with self.subTest(field=field):
                receipt = deepcopy(original)
                receipt['frames'][0][field] = bad
                self.write_json(self.output / 'capacity/final.json', receipt)
                with self.assertRaises((ValueError, AssertionError)):
                    self.check_final()

    def test_native_bytes_cannot_change_after_receipt(self):
        receipt = self.make_final()
        Path(receipt['frames'][0]['native_path']).write_bytes(b'tampered')
        with self.assertRaises(ValueError):
            self.check_final()

    def test_valid_proof_hash_does_not_authorize_proof_as_native(self):
        receipt = self.make_final()
        proof = self.asset_root / 'renders/proofs/capacity/frame-0001.png'
        proof.parent.mkdir(parents=True)
        Image.new('RGB', (4, 2)).save(proof)
        receipt['frames'][0].update(native_path=str(proof), native_sha256=sha256_file(proof))
        self.write_json(self.output / 'capacity/final.json', receipt)
        with self.assertRaises((ValueError, AssertionError)):
            self.check_final()

    def test_wrong_native_basename_cannot_replace_expected_frame(self):
        receipt = self.make_final()
        other = self.output / 'capacity/frame-0999.png'
        Image.new('RGB', (16, 8)).save(other)
        receipt['frames'][0].update(native_path=str(other), native_sha256=sha256_file(other))
        self.write_json(self.output / 'capacity/final.json', receipt)
        with self.assertRaises((ValueError, AssertionError)):
            self.check_final()

    def test_incomplete_native_orbit_is_rejected(self):
        receipt = self.make_final('controls-orbit')
        receipt['frames'].pop()
        self.write_json(self.output / 'controls-orbit/final.json', receipt)
        with self.assertRaises((ValueError, AssertionError)):
            self.check_final('controls-orbit')

    def test_encoder_rejects_reordered_native_frames_before_render(self):
        receipt = self.make_final('controls-orbit')
        receipt['frames'][0], receipt['frames'][1] = receipt['frames'][1], receipt['frames'][0]
        self.write_json(self.output / 'controls-orbit/final.json', receipt)
        with patch.object(encoder, 'contract_for', side_effect=lambda shot: self.contracts[shot]), \
                patch.object(exporter, 'contract_for', side_effect=lambda shot: self.contracts[shot]), \
                patch.object(encoder, 'encode') as encode:
            with self.assertRaises((ValueError, AssertionError)):
                encoder.main()
            encode.assert_not_called()


class ExactApprovalTests(NativeFixture):
    def make_contract(self):
        scene = self.asset_root / 'scenes/stills/capacity.blend'
        scene.parent.mkdir(parents=True)
        scene.write_bytes(b'approved-scene')
        proof = self.asset_root / 'renders/proofs/capacity/still.png'
        proof.parent.mkdir(parents=True)
        proof.write_bytes(b'approved-proof')
        self.source = {'master_sha256': 'master', 'material_library_sha256': 'materials', 'tool_lock_sha256': 'lock'}
        self.write_json(self.source_approval, {'shots': [{'shot': 'capacity', 'contract_sha256': 'source-contract'}]})
        self.contract = dict(self.source, generation='bento-20260903-r10-lighting', shot='capacity',
                             scene_path=str(scene), scene_sha256=sha256_file(scene), native_size=[16, 8], samples=128,
                             source_contract_sha256='source-contract', source_approval_sha256=sha256_file(self.source_approval),
                             script_sha256=sha256_file(Path(native.__file__).with_name('blender_bento_lighting_orbit_proof.py')),
                             proofs=[{'path': str(proof), 'sha256': sha256_file(proof)}])
        self.contract_path = self.asset_root / 'scenes/contracts/capacity.json'
        self.publish_contract()

    def publish_contract(self):
        self.write_json(self.contract_path, self.contract)
        digest = sha256_file(self.contract_path)
        self.write_json(self.root / 'review.json', {'contracts': [{'path': str(self.contract_path), 'sha256': digest}]})
        self.write_json(self.approval, {'decision': 'approved', 'review_manifest': 'review.json',
                                       'contracts': {'capacity': digest}})

    def get_contract(self):
        with patch.object(native, 'approved_contract', return_value=self.source):
            return native.contract_for('capacity')

    def test_exact_approved_contract_is_accepted(self):
        self.make_contract()
        self.assertEqual(self.get_contract(), self.contract)

    def test_pending_decision_is_not_release_authority(self):
        self.make_contract()
        approval = json.loads(self.approval.read_text())
        approval['decision'] = 'pending'
        self.write_json(self.approval, approval)
        with self.assertRaises(ValueError):
            self.get_contract()

    def test_contract_file_cannot_change_without_new_exact_approval(self):
        self.make_contract()
        self.contract['samples'] = 1
        self.write_json(self.contract_path, self.contract)
        with self.assertRaises(ValueError):
            self.get_contract()

    def test_source_authority_changes_are_rejected(self):
        self.make_contract()
        original = deepcopy(self.source)
        for key in ('master_sha256', 'material_library_sha256', 'tool_lock_sha256'):
            with self.subTest(key=key):
                self.source = dict(original, **{key: 'changed'})
                with self.assertRaises(ValueError):
                    self.get_contract()

    def test_scene_and_proof_byte_changes_are_rejected(self):
        self.make_contract()
        for path in (Path(self.contract['scene_path']), Path(self.contract['proofs'][0]['path'])):
            with self.subTest(path=path.name):
                original = path.read_bytes()
                path.write_bytes(b'changed')
                with self.assertRaises(ValueError):
                    self.get_contract()
                path.write_bytes(original)

    def test_source_approval_file_change_is_rejected(self):
        self.make_contract()
        self.write_json(self.source_approval, {'shots': []})
        with self.assertRaises(ValueError):
            self.get_contract()

    def test_different_source_contract_is_rejected_even_with_current_approval_hash(self):
        self.make_contract()
        self.contract['source_contract_sha256'] = 'other-source-contract'
        self.publish_contract()
        with self.assertRaises(ValueError):
            self.get_contract()

    def test_even_hashed_contract_must_match_requested_generation_and_shot(self):
        self.make_contract()
        original = deepcopy(self.contract)
        for key, value in [('generation', 'bento-20260903-r06'), ('shot', 'controls')]:
            with self.subTest(key=key):
                self.contract = dict(original, **{key: value})
                self.publish_contract()
                with self.assertRaises(ValueError):
                    self.get_contract()


class NativeRenderTests(NativeFixture):
    def prepare_render(self):
        contract = {'generation': 'bento-20260903-r10-lighting', 'shot': 'capacity',
                    'scene_sha256': 'scene-capacity', 'scene_path': str(self.root / 'capacity.blend'),
                    'master_sha256': 'master', 'native_size': [16, 8], 'samples': 128}
        scene = MagicMock()
        scene.render.resolution_x, scene.render.resolution_y = 16, 8
        scene.render.resolution_percentage, scene.cycles.samples = 100, 128
        mesh = SimpleNamespace(type='MESH', library=True, data=SimpleNamespace(library=True),
                               override_library=None, animation_data=None)
        product = SimpleNamespace(all_objects=[mesh] * 556)
        preferences = MagicMock(devices=[SimpleNamespace(type='OPTIX', use=False)])
        bpy = SimpleNamespace(context=SimpleNamespace(scene=scene, preferences=SimpleNamespace(
            addons={'cycles': SimpleNamespace(preferences=preferences)})),
            data=SimpleNamespace(collections={'PIMM_PUBLISHED': product}), ops=MagicMock())
        bpy.ops.render.render.side_effect = lambda **kwargs: Image.new('RGB', (16, 8)).save(scene.render.filepath)
        return contract, scene, bpy

    def test_saved_native_settings_render_one_exact_receipted_frame(self):
        contract, scene, bpy = self.prepare_render()
        with patch.dict(sys.modules, {'bpy': bpy}), patch.object(native, 'contract_for', return_value=contract):
            native.render('capacity')
        receipt = json.loads((self.output / 'capacity/final.json').read_text())
        self.assertEqual(receipt['size'], [16, 8])
        self.assertEqual(len(receipt['frames']), 1)
        self.assertEqual(receipt['frames'][0]['scene_sha256'], contract['scene_sha256'])
        bpy.ops.wm.open_mainfile.assert_called_once_with(filepath=contract['scene_path'])
        bpy.ops.render.render.assert_called_once_with(write_still=True)
        self.assertEqual(scene.render.resolution_percentage, 100)
        self.assertEqual(scene.cycles.samples, 128)

    def test_proof_resolution_cannot_be_silently_upscaled(self):
        contract, scene, bpy = self.prepare_render()
        scene.render.resolution_percentage = 25
        with patch.dict(sys.modules, {'bpy': bpy}), patch.object(native, 'contract_for', return_value=contract):
            with self.assertRaises(AssertionError):
                native.render('capacity')
        bpy.ops.render.render.assert_not_called()

    def test_resumed_frame_must_match_ordinal_path_and_authority(self):
        receipt = self.make_final()
        record = receipt['frames'][0]
        contract, scene, bpy = self.prepare_render()
        for field, bad in [('frame', 2), ('native_path', str(self.root / 'other.png')),
                           ('approval_sha256', 'other'), ('scene_sha256', 'other')]:
            with self.subTest(field=field):
                self.write_json(self.output / 'capacity/frame-0001.json', dict(record, **{field: bad}))
                with patch.dict(sys.modules, {'bpy': bpy}), patch.object(native, 'contract_for', return_value=contract):
                    with self.assertRaises(ValueError):
                        native.render('capacity')
                bpy.ops.render.render.assert_not_called()

    def test_source_authorization_change_during_render_prevents_final_manifest(self):
        contract, scene, bpy = self.prepare_render()
        with patch.dict(sys.modules, {'bpy': bpy}), \
                patch.object(native, 'contract_for', side_effect=[contract, ValueError('Changed source authority')]):
            with self.assertRaises(ValueError):
                native.render('capacity')
        self.assertFalse((self.output / 'capacity/final.json').exists())

    def test_r10_approval_change_during_render_prevents_final_manifest(self):
        contract, scene, bpy = self.prepare_render()

        def changed_approval(**kwargs):
            Image.new('RGB', (16, 8)).save(scene.render.filepath)
            self.write_json(self.approval, {'decision': 'pending'})

        bpy.ops.render.render.side_effect = changed_approval
        with patch.dict(sys.modules, {'bpy': bpy}), patch.object(native, 'contract_for', return_value=contract):
            with self.assertRaises(ValueError):
                native.render('capacity')
        self.assertFalse((self.output / 'capacity/final.json').exists())


class BlenderEncodingTests(NativeFixture):
    def test_encoder_uses_native_size_blender_video_and_neutral_color_transform(self):
        scene = MagicMock()
        bpy = SimpleNamespace(context=SimpleNamespace(scene=scene), ops=SimpleNamespace(render=MagicMock()))
        paths = [self.root / 'frame-0001.png', self.root / 'frame-0002.png']
        with patch.dict(sys.modules, {'bpy': bpy}):
            encoder.encode(paths, self.root / 'native.mp4', [2400, 1200])
        self.assertEqual((scene.render.resolution_x, scene.render.resolution_y), (2400, 1200))
        self.assertEqual(scene.render.resolution_percentage, 100)
        self.assertEqual((scene.render.fps, scene.render.fps_base), (24, 1))
        self.assertEqual(scene.render.image_settings.media_type, 'VIDEO')
        self.assertEqual(scene.render.image_settings.file_format, 'FFMPEG')
        self.assertEqual(scene.render.ffmpeg.codec, 'H264')
        self.assertEqual(scene.view_settings.view_transform, 'Standard')
        self.assertEqual(scene.view_settings.exposure, 0)
        self.assertEqual(scene.view_settings.gamma, 1)
        bpy.ops.render.render.assert_called_once_with(animation=True)

    def test_encoder_does_not_overwrite_existing_derivative(self):
        output = self.root / 'existing.mp4'
        output.write_bytes(b'keep')
        with patch.dict(sys.modules, {'bpy': MagicMock()}):
            with self.assertRaises(FileExistsError):
                encoder.encode([self.root / 'frame-0001.png'], output, [2400, 1200])
        self.assertEqual(output.read_bytes(), b'keep')

    def test_release_sources_have_no_resizing_or_external_ffmpeg(self):
        for module in (native, encoder, exporter):
            source = Path(module.__file__).read_text()
            with self.subTest(module=module.__name__):
                self.assertNotIn('.resize(', source)
                self.assertNotIn('.thumbnail(', source)
                self.assertNotIn('subprocess', source)
                self.assertNotIn('resolution_percentage = 25', source)

    def test_approval_change_during_encoding_cannot_publish_video_receipt(self):
        self.make_final('controls-orbit')
        output = self.output / 'controls-orbit/pimm-bento-20260903-r10-30g-controls-orbit.mp4'

        def changing_encode(paths, path, size):
            path.write_bytes(b'encoded-video')
            self.write_json(self.approval, {'decision': 'pending'})

        with patch.object(encoder, 'contract_for', side_effect=lambda shot: self.contracts[shot]), \
                patch.object(encoder, 'encode', side_effect=changing_encode):
            with self.assertRaises((ValueError, AssertionError)):
                encoder.main()
        self.assertFalse(output.with_suffix('.json').exists())


class NativeExportTests(NativeFixture):
    def prepare_export(self):
        for shot in native.SHOTS:
            self.make_final(shot)
        (self.root / 'assets').mkdir()
        manifest = self.output / 'controls-orbit/final.json'
        video_path = self.output / 'controls-orbit/pimm-bento-20260903-r10-30g-controls-orbit.mp4'
        video_path.write_bytes(b'blender-encoded-video')
        self.video_receipt = video_path.with_suffix('.json')
        self.video = {'filename': video_path.name, 'path': str(video_path), 'sha256': sha256_file(video_path),
                      'bytes': video_path.stat().st_size, 'size': [16, 8], 'frames': 192, 'fps': 24,
                      'duration_ms': 8000, 'approval_sha256': sha256_file(self.approval),
                      'scene_sha256': self.contracts['controls-orbit']['scene_sha256'],
                      'native_manifest': str(manifest), 'native_manifest_sha256': sha256_file(manifest)}
        self.write_json(self.video_receipt, self.video)

    def run_export(self):
        with patch.object(exporter, 'contract_for', side_effect=lambda shot: self.contracts[shot]):
            exporter.export()

    def test_export_retains_native_pixels_and_orbit_first_frame_fallback(self):
        self.prepare_export()
        self.run_export()
        manifest = json.loads((self.root / 'assets/pimm-bento-assets.v1.json').read_text())
        self.assertEqual(len(manifest['assets']), 4)
        for item in manifest['assets']:
            with Image.open(item['native_path']) as original, Image.open(self.root / 'assets' / item['filename']) as encoded:
                self.assertEqual(encoded.size, original.size)
                self.assertEqual(encoded.convert('RGB').tobytes(), original.convert('RGB').tobytes())
        controls = next(item for item in manifest['assets'] if item['shot'] == 'controls')
        self.assertEqual(Path(controls['native_path']), self.output / 'controls-orbit/frame-0001.png')
        self.assertEqual(controls['scene_sha256'], self.contracts['controls-orbit']['scene_sha256'])
        self.assertEqual(controls['generation'], self.contracts['controls-orbit']['generation'])

    def test_missing_video_receipt_does_not_partially_export_stills(self):
        self.prepare_export()
        self.video_receipt.unlink()
        with self.assertRaises(FileNotFoundError):
            self.run_export()
        self.assertEqual(list((self.root / 'assets').iterdir()), [])

    def test_changed_video_bytes_do_not_partially_export_stills(self):
        self.prepare_export()
        Path(self.video['path']).write_bytes(b'changed')
        with self.assertRaises(ValueError):
            self.run_export()
        self.assertEqual(list((self.root / 'assets').iterdir()), [])

    def test_existing_asset_prevents_any_release_writes(self):
        self.prepare_export()
        existing = self.root / 'assets/pimm-bento-20260903-r10-30g-tooling.webp'
        existing.write_bytes(b'preserve')
        with self.assertRaises(FileExistsError):
            self.run_export()
        self.assertEqual(list((self.root / 'assets').iterdir()), [existing])
        self.assertEqual(existing.read_bytes(), b'preserve')

    def test_wrong_video_metadata_rejected_before_any_asset_write(self):
        self.prepare_export()
        for field, value in [('fps', 3), ('frames', 3), ('size', [4, 2]), ('duration_ms', 1000)]:
            with self.subTest(field=field):
                self.write_json(self.video_receipt, dict(self.video, **{field: value}))
                with self.assertRaises((ValueError, AssertionError)):
                    self.run_export()
                self.assertEqual(list((self.root / 'assets').iterdir()), [])

    def test_proof_video_path_cannot_be_promoted_as_native_video(self):
        self.prepare_export()
        proof = self.asset_root / 'renders/proofs/review/controls.mp4'
        proof.parent.mkdir(parents=True)
        proof.write_bytes(b'proof-video')
        self.video.update(path=str(proof), sha256=sha256_file(proof))
        self.write_json(self.video_receipt, self.video)
        with self.assertRaises((ValueError, AssertionError)):
            self.run_export()
        self.assertEqual(list((self.root / 'assets').iterdir()), [])


if __name__ == '__main__':
    unittest.main()
