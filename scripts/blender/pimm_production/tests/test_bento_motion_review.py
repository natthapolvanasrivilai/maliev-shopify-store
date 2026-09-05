"""Combined proof packaging fails closed on incomplete, changed or misleading media."""
import json
from pathlib import Path
import struct
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts.blender.pimm_production import package_bento_motion_review as review
from scripts.blender.pimm_production.io_contract import sha256_file
from scripts.blender.pimm_production.blender_bento_stable_reveal_proof import stabilize


class MotionReviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.worker = self.root / 'worker.py'
        self.worker.write_text('immutable worker')
        self.scene = self.root / 'scene.blend'
        self.scene.write_bytes(b'Blender native scene')

    def sequence(self, shot='tooling', count=192, size=(1600, 2000)):
        root = self.root / shot
        root.mkdir(exist_ok=True)
        records = []
        for index in range(1, count + 1):
            row, frame = divmod(index - 1, 120) if shot == 'configuration' else (0, index - 1)
            directory = root / f'row-{row:02d}' if shot == 'configuration' else root
            directory.mkdir(exist_ok=True)
            path = directory / f'frame-{frame + 1:04d}.png'
            path.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\0' * 8 + struct.pack('>II', *(value // 4 for value in size)))
            records.append({'index': index, 'row': row, 'frame': frame + 1, 'path': str(path), 'sha256': sha256_file(path)})
        contract = {'approval': 'pending', 'generation': 'test-generation', 'shot': shot,
                    'proofs': records, 'script_sha256': sha256_file(self.worker), 'scene_path': str(self.scene),
                    'scene_sha256': sha256_file(self.scene), 'native_size': list(size), 'proof_percentage': 25,
                    'source_scene_sha256': sha256_file(self.scene),
                    'motion': {'frames': count, 'fps': 24, 'yaw_views': 120, 'elevation_degrees': [-6, -4, -2, 0, 2, 4, 6]},
                    'technical_visualization': True, 'focus_objects': list(review.TARGETS), 'ghost_opacity': .2,
                    'render_stability': {'persistent_data': False}}
        path = root / 'contract.json'
        path.write_text(json.dumps(contract))
        return root, path, contract

    def validate(self, sequence, shot='tooling', count=192):
        root, contract, _ = sequence
        return review.validate_sequence(contract, root, self.worker, 'test-generation', shot, count)

    def video(self, sequence):
        root = Path(sequence['contract_path']).parent
        output = root / f"{sequence['shot']}.mp4"
        output.write_bytes(b'\0\0\0\x18ftypmp42' + b'fixture')
        receipt = {'generation': sequence['generation'], 'shot': sequence['shot'],
                   'contract_path': sequence['contract_path'], 'contract_sha256': sequence['contract_sha256'],
                   'path': str(output), 'sha256': sha256_file(output), 'bytes': output.stat().st_size,
                   'size': sequence['proof_size'], 'frames': 192, 'fps': 24, 'duration_ms': 8000,
                   'encoder': 'Locked Blender 5.2 bundled FFmpeg; H264 perceptually lossless, sRGB, no resizing or retouching',
                   'status': 'pending_owner_approval'}
        output.with_suffix('.json').write_text(json.dumps(receipt))
        return output, receipt

    def test_native_sizes_are_derived_and_all_1224_frames_verified(self):
        count = 0
        for shot, frames, native, proof in [('configuration', 840, (2400, 1200), [600, 300]),
                                           ('tooling', 192, (1600, 2000), [400, 500]),
                                           ('capacity', 192, (1600, 2200), [400, 550])]:
            result = self.validate(self.sequence(shot, frames, native), shot, frames)
            self.assertEqual(result['proof_size'], proof)
            self.assertEqual(len(result['proofs']), frames)
            count += result['frames']
        self.assertEqual(count, 1224)

    def test_incomplete_sequence_or_nonpending_approval_is_rejected(self):
        fixture = self.sequence()
        for key, value in [('proofs', fixture[2]['proofs'][:-1]), ('approval', 'approved')]:
            changed = dict(fixture[2], **{key: value})
            fixture[1].write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, 'complete, pending'):
                self.validate(fixture)

    def test_wrong_png_dimensions_rejected_even_with_matching_hash(self):
        fixture = self.sequence()
        path = Path(fixture[2]['proofs'][0]['path'])
        path.write_bytes(path.read_bytes()[:16] + struct.pack('>II', 500, 400))
        fixture[2]['proofs'][0]['sha256'] = sha256_file(path)
        fixture[1].write_text(json.dumps(fixture[2]))
        with self.assertRaisesRegex(ValueError, 'dimensions'):
            self.validate(fixture)

    def test_png_worker_and_scene_mutations_are_rejected(self):
        fixture = self.sequence()
        for path in [Path(fixture[2]['proofs'][0]['path']), self.worker, self.scene]:
            original = path.read_bytes()
            path.write_bytes(original + b'changed')
            with self.assertRaises(ValueError):
                self.validate(fixture)
            path.write_bytes(original)

    def test_capacity_cannot_silently_change_the_four_opaque_components(self):
        fixture = self.sequence('capacity', 192, (1600, 2200))
        fixture[2]['focus_objects'][0] = 'unapproved component'
        fixture[1].write_text(json.dumps(fixture[2]))
        with self.assertRaisesRegex(ValueError, 'four approved 30G'):
            self.validate(fixture, 'capacity')

    def test_capacity_rejects_persistent_data_and_missing_stability_contract(self):
        fixture = self.sequence('capacity', 192, (1600, 2200))
        for settings in ({}, {'persistent_data': True}, {'persistent_data': 0}):
            fixture[2]['render_stability'] = settings
            fixture[1].write_text(json.dumps(fixture[2]))
            with self.assertRaisesRegex(ValueError, 'disable persistent render data'):
                self.validate(fixture, 'capacity')

    def test_stabilize_changes_only_the_render_cache_not_visual_settings(self):
        scene = SimpleNamespace(render=SimpleNamespace(use_persistent_data=True, resolution_percentage=100),
                                cycles=SimpleNamespace(samples=128, use_denoising=True),
                                camera=object(), compositing_node_group=object())
        camera, compositor = scene.camera, scene.compositing_node_group
        stabilize(scene)
        self.assertIs(scene.render.use_persistent_data, False)
        self.assertEqual(scene.render.resolution_percentage, 100)
        self.assertEqual(scene.cycles.samples, 128)
        self.assertIs(scene.cycles.use_denoising, True)
        self.assertIs(scene.camera, camera)
        self.assertIs(scene.compositing_node_group, compositor)

    def test_video_receipt_pins_size_frame_count_contract_and_file(self):
        sequence = self.validate(self.sequence())
        output, receipt = self.video(sequence)
        verified = review.validate_video(output.parent, 'tooling', sequence)
        self.assertEqual(verified['size'], [400, 500])
        for key, value in [('size', [400, 550]), ('frames', 191), ('contract_sha256', 'bad'), ('status', 'approved')]:
            output.with_suffix('.json').write_text(json.dumps(dict(receipt, **{key: value})))
            with self.assertRaises(ValueError):
                review.validate_video(output.parent, 'tooling', sequence)
        output.with_suffix('.json').write_text(json.dumps(receipt))
        output.write_bytes(b'changed')
        with self.assertRaises(ValueError):
            review.validate_video(output.parent, 'tooling', sequence)

    def test_existing_package_is_immutable_before_source_reads(self):
        destination = self.root / 'renders/proofs' / review.GENERATION
        destination.mkdir(parents=True)
        (destination / 'index.html').write_text('existing proof')
        with patch.object(review, 'ASSET_ROOT', self.root):
            with self.assertRaises(FileExistsError):
                review.package()
        self.assertEqual((destination / 'index.html').read_text(), 'existing proof')

    def source_authority(self):
        return {shot: {'source_scene_sha256': sha256_file(self.scene), 'approval_path': str(self.worker),
                       'approval_sha256': sha256_file(self.worker)} for shot in ('configuration', 'tooling', 'capacity')}

    def test_current_source_scene_mismatch_and_changed_approval_are_rejected(self):
        authority = self.source_authority()
        sequences = {shot: {'source_scene_sha256': value['source_scene_sha256']} for shot, value in authority.items()}
        review.validate_source_authority(sequences, authority)
        sequences['capacity']['source_scene_sha256'] = 'older approved scene'
        with self.assertRaisesRegex(ValueError, 'current approved source: capacity'):
            review.validate_source_authority(sequences, authority)
        sequences['capacity']['source_scene_sha256'] = authority['capacity']['source_scene_sha256']
        self.worker.write_text('changed approval')
        with self.assertRaises(ValueError):
            review.validate_source_authority(sequences, authority)

    def package_fixture(self):
        proofs = self.root / 'renders/proofs'
        proofs.mkdir(parents=True)
        assets = self.root / 'assets'
        assets.mkdir()
        for name in ('pimm-bento-spin.js', 'pimm-bento-spin.css', 'pimm-bento-orbit.js', 'Outfit-Latin.woff2'):
            (assets / name).write_bytes(b'static asset')
        workers = self.root / 'workers'
        (workers / 'review').mkdir(parents=True)
        (workers / 'review/bento-motion.html').write_text('<p>Combined proof</p>')

        def sequence(contract, root, worker, generation, shot, count):
            return {'generation': generation, 'shot': shot, 'contract_path': str(self.scene),
                    'contract_sha256': sha256_file(self.scene), 'scene_path': str(self.scene),
                    'scene_sha256': sha256_file(self.scene), 'worker_path': str(self.worker),
                    'worker_sha256': sha256_file(self.worker), 'source_scene_sha256': sha256_file(self.scene),
                    'proof_size': [600, 300] if shot == 'configuration' else [400, 500],
                    'native_intent': [2400, 1200], 'frames': count, 'proofs': []}

        def video(root, shot, sequence):
            return {'path': str(self.scene), 'sha256': sha256_file(self.scene),
                    'receipt_path': str(self.worker), 'receipt_sha256': sha256_file(self.worker)}

        patches = [patch.object(review, 'ASSET_ROOT', self.root), patch.object(review, 'REPO_ROOT', self.root),
                   patch.object(review, 'WORKER_ROOT', workers), patch.object(review, 'validate_sequence', side_effect=sequence),
                   patch.object(review, 'validate_video', side_effect=video),
                   patch.object(review, 'current_source_authority', return_value=self.source_authority())]
        mocks = [item.start() for item in patches]
        for item in patches:
            self.addCleanup(item.stop)
        return proofs, mocks[-1]

    def test_failed_copy_retains_unique_staging_and_does_not_create_final_package(self):
        proofs, _ = self.package_fixture()
        with patch.object(review.shutil, 'copyfile', side_effect=OSError('copy interrupted')):
            with self.assertRaisesRegex(RuntimeError, 'staging retained at .*copy interrupted'):
                review.package()
        self.assertFalse((proofs / review.GENERATION).exists())
        stages = list(proofs.glob(f'.{review.GENERATION}-staging-*'))
        self.assertEqual(len(stages), 1)
        self.assertTrue((stages[0] / 'index.html').exists())
        self.assertFalse((stages[0] / 'review.json').exists())

    def test_success_renames_complete_stage_and_pins_revalidated_approval_paths(self):
        proofs, authority = self.package_fixture()
        destination = review.package()
        self.assertEqual(destination, proofs / review.GENERATION)
        self.assertEqual(authority.call_count, 2)
        self.assertEqual(list(proofs.glob(f'.{review.GENERATION}-staging-*')), [])
        receipt = json.loads((destination / 'review.json').read_text())
        self.assertEqual(receipt['current_source_authority'], self.source_authority())
        self.assertEqual(len(receipt['files']), 7)

    def test_missing_static_asset_fails_before_any_staging_is_created(self):
        proofs, _ = self.package_fixture()
        with patch.object(review, 'REPO_ROOT', self.root / 'missing-assets'):
            with self.assertRaises(FileNotFoundError):
                review.package()
        self.assertFalse((proofs / review.GENERATION).exists())
        self.assertEqual(list(proofs.glob(f'.{review.GENERATION}-staging-*')), [])

    def test_review_preserves_native_media_and_explicit_technical_label(self):
        html = (review.WORKER_ROOT / 'review/bento-motion.html').read_text(encoding='utf-8')
        self.assertEqual(html.count('<pimm-bento-orbit'), 2)
        self.assertEqual(html.count('<pimm-bento-spin '), 1)
        self.assertIn('Technical visualization — protective cover and surrounding components shown transparent', html)
        self.assertIn('not final renders and not the storefront', html)
        self.assertIn('data-row-count="7"', html)
        self.assertIn('prefers-reduced-motion: reduce', html)
        self.assertNotIn('<button', html)
        self.assertNotIn('filter:', html)


if __name__ == '__main__':
    unittest.main()
