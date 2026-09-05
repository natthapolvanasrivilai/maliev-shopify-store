"""Exact white-proof authorization and per-shot native still release regressions."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from unittest.mock import patch

from PIL import Image

from scripts.blender.pimm_production import blender_bento_r10_final as native
from scripts.blender.pimm_production import blender_bento_white_final as white
from scripts.blender.pimm_production import export_bento_approved_stills as release
from scripts.blender.pimm_production import export_bento_r10_assets as r10_export
from scripts.blender.pimm_production.io_contract import sha256_file


class WhiteFixture(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.asset_root = self.root / 'external'
        self.r10_approval = self.root / 'docs/r10-approval.json'
        self.white_approval = self.root / 'docs/white-approval.json'
        self.r10_output = self.asset_root / 'renders/final/r10'
        self.white_output = self.asset_root / 'renders/final/white'
        self.write_json(self.r10_approval, {'decision': 'approved', 'generation': 'r10'})
        self.write_json(self.white_approval, {'decision': 'approved', 'generation': 'white'})
        for module, pairs in (
            (native, [('APPROVAL', self.r10_approval), ('OUTPUT', self.r10_output), ('ASSET_ROOT', self.asset_root)]),
            (white, [('APPROVAL', self.white_approval), ('OUTPUT', self.white_output), ('ASSET_ROOT', self.asset_root)]),
            (r10_export, [('APPROVAL', self.r10_approval), ('OUTPUT', self.r10_output)]),
            (release, [('REPO_ROOT', self.root)]),
        ):
            for name, value in pairs:
                self.enterContext(patch.object(module, name, value))

    def write_json(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding='utf-8')


class WhiteContractTests(WhiteFixture):
    def prepare_contract(self):
        self.source = {'scene_sha256': 'r10-scene', 'master_sha256': 'master',
                       'material_library_sha256': 'material', 'tool_lock_sha256': 'lock'}
        scene = self.asset_root / 'scenes/stills/white.blend'
        scene.parent.mkdir(parents=True)
        scene.write_bytes(b'approved-white-studio-scene')
        proof = self.asset_root / 'renders/proofs/white/still.png'
        proof.parent.mkdir(parents=True)
        proof.write_bytes(b'approved-white-proof')
        self.contract_path = self.asset_root / 'scenes/contracts/white.json'
        self.contract = {
            'generation': 'bento-20260903-r11-white', 'shot': 'configuration',
            'source_scene_sha256': self.source['scene_sha256'],
            'master_sha256': self.source['master_sha256'],
            'material_library_sha256': self.source['material_library_sha256'],
            'tool_lock_sha256': self.source['tool_lock_sha256'],
            'scene_path': str(scene), 'scene_sha256': sha256_file(scene), 'native_size': [2400, 1200],
            'script_sha256': sha256_file(Path(white.__file__).with_name('blender_bento_white_proof.py')),
            'proofs': [{'path': str(proof), 'sha256': sha256_file(proof)}],
        }
        self.publish_contract()

    def publish_contract(self):
        self.write_json(self.contract_path, self.contract)
        self.approval = {'decision': 'approved', 'generation': 'bento-20260903-r11-white',
                         'contract_path': str(self.contract_path), 'contract_sha256': sha256_file(self.contract_path),
                         'scene_sha256': self.contract['scene_sha256'],
                         'proof_sha256': self.contract['proofs'][0]['sha256']}
        self.write_json(self.white_approval, self.approval)

    def load(self, shot='configuration'):
        with patch.object(white, 'contract_for', return_value=self.source):
            return white.white_contract(shot)

    def test_exact_white_contract_is_accepted(self):
        self.prepare_contract()
        self.assertEqual(self.load(), self.contract)

    def test_pending_approval_and_other_shots_are_rejected(self):
        self.prepare_contract()
        with self.assertRaises(ValueError):
            self.load('capacity')
        self.write_json(self.white_approval, dict(self.approval, decision='pending'))
        with self.assertRaises(ValueError):
            self.load()

    def test_contract_mutation_without_new_approval_is_rejected(self):
        self.prepare_contract()
        self.write_json(self.contract_path, dict(self.contract, native_size=[600, 300]))
        with self.assertRaises(ValueError):
            self.load()

    def test_source_scene_master_material_and_lock_changes_are_rejected(self):
        self.prepare_contract()
        original = deepcopy(self.source)
        for key in ('scene_sha256', 'master_sha256', 'material_library_sha256', 'tool_lock_sha256'):
            with self.subTest(key=key):
                self.source = dict(original, **{key: 'changed'})
                with self.assertRaises(ValueError):
                    self.load()

    def test_source_approval_failure_is_propagated(self):
        self.prepare_contract()
        with patch.object(white, 'contract_for', side_effect=ValueError('r10 approval changed')):
            with self.assertRaises(ValueError):
                white.white_contract('configuration')

    def test_proof_resolution_is_rejected_even_with_new_contract_hash(self):
        self.prepare_contract()
        self.contract['native_size'] = [600, 300]
        self.publish_contract()
        with self.assertRaises(ValueError):
            self.load()

    def test_scene_proof_and_script_hash_changes_are_rejected(self):
        self.prepare_contract()
        for path in (Path(self.contract['scene_path']), Path(self.contract['proofs'][0]['path'])):
            with self.subTest(path=path.name):
                original = path.read_bytes()
                path.write_bytes(b'changed')
                with self.assertRaises(ValueError):
                    self.load()
                path.write_bytes(original)
        self.contract['script_sha256'] = 'changed'
        self.publish_contract()
        with self.assertRaises(ValueError):
            self.load()

    def test_approval_proof_digest_must_match_reviewed_contract(self):
        self.prepare_contract()
        self.write_json(self.white_approval, dict(self.approval, proof_sha256='other-proof'))
        with self.assertRaises(ValueError):
            self.load()

    def test_white_scene_cannot_come_from_proof_or_arbitrary_directory(self):
        self.prepare_contract()
        outside = self.root / 'other.blend'
        outside.write_bytes(Path(self.contract['scene_path']).read_bytes())
        self.contract['scene_path'] = str(outside)
        self.publish_contract()
        with self.assertRaises(ValueError):
            self.load()


class ApprovedStillReleaseTests(WhiteFixture):
    def prepare_sources(self):
        self.contracts = {}
        self.receipts = {}
        for shot in ('capacity', 'controls-orbit', 'tooling', 'configuration'):
            is_white = shot == 'configuration'
            approval = self.white_approval if is_white else self.r10_approval
            output = self.white_output if is_white else self.r10_output
            contract = {'generation': 'bento-20260903-r11-white' if is_white else 'bento-20260903-r10-' + (
                'orbit' if shot == 'controls-orbit' else 'lighting'), 'scene_sha256': 'scene-' + shot,
                'native_size': [16, 8], 'master_sha256': 'master', 'shot': shot.removesuffix('-orbit')}
            path = output / shot / 'frame-0001.png'
            path.parent.mkdir(parents=True)
            Image.new('RGB', (16, 8), (80, 90, 120)).save(path)
            frame = {'frame': 1, 'native_path': str(path), 'native_sha256': sha256_file(path),
                     'approval_sha256': sha256_file(approval), 'scene_sha256': contract['scene_sha256']}
            receipt = {'generation': contract['generation'], 'shot': shot, 'size': contract['native_size'],
                       'approval_sha256': sha256_file(approval), 'scene_sha256': contract['scene_sha256'],
                       'master_sha256': contract['master_sha256'], 'frames': [frame]}
            self.write_json(path.with_suffix('.json'), frame)
            if shot != 'controls-orbit':
                self.write_json(output / shot / 'final.json', receipt)
            self.contracts[shot] = contract
            self.receipts[shot] = receipt
        self.enterContext(patch.object(native, 'contract_for', side_effect=lambda shot: self.contracts[shot]))
        self.enterContext(patch.object(r10_export, 'contract_for', side_effect=lambda shot: self.contracts[shot]))
        self.enterContext(patch.object(white, 'white_contract', side_effect=lambda shot: self.contracts[shot]))
        (self.root / 'assets').mkdir()

    def test_overridden_native_approval_and_output_validate_white_receipt(self):
        self.prepare_sources()
        receipt, contract = self.receipts['configuration'], self.contracts['configuration']
        self.assertEqual(native.validate_final(receipt, contract, 'configuration', self.white_approval, self.white_output), receipt)
        with self.assertRaises(ValueError):
            native.validate_final(receipt, contract, 'configuration')
        with self.assertRaises(ValueError):
            native.validate_final(receipt, contract, 'configuration', self.white_approval, self.r10_output)

    def test_actual_png_dimensions_override_self_reported_receipt_size(self):
        self.prepare_sources()
        receipt = deepcopy(self.receipts['configuration'])
        frame = receipt['frames'][0]
        Image.new('RGB', (4, 2)).save(frame['native_path'])
        frame['native_sha256'] = sha256_file(Path(frame['native_path']))
        with self.assertRaises(ValueError):
            native.validate_final(receipt, self.contracts['configuration'], 'configuration', self.white_approval, self.white_output)

    def test_each_selected_shot_keeps_its_own_approval_and_controls_first_frame(self):
        self.prepare_sources()
        selected = release.sources()
        self.assertEqual([item['shot'] for item in selected], ['capacity', 'controls', 'tooling', 'configuration'])
        for item in selected:
            approval = self.white_approval if item['shot'] == 'configuration' else self.r10_approval
            self.assertEqual(item['approval_sha256'], sha256_file(approval))
            self.assertEqual(item['approval'], approval.relative_to(self.root).as_posix())
        controls = selected[1]
        self.assertEqual(Path(controls['native_path']), self.r10_output / 'controls-orbit/frame-0001.png')
        self.assertEqual(controls['generation'], self.contracts['controls-orbit']['generation'])
        self.assertFalse((self.r10_output / 'controls-orbit/final.json').exists())

    def test_changed_white_approval_or_controls_frame_authority_blocks_selection(self):
        self.prepare_sources()
        original = self.white_approval.read_bytes()
        self.write_json(self.white_approval, {'decision': 'pending'})
        with self.assertRaises(ValueError):
            release.sources()
        self.white_approval.write_bytes(original)
        path = self.r10_output / 'controls-orbit/frame-0001.json'
        frame = json.loads(path.read_text())
        frame['scene_sha256'] = 'other'
        self.write_json(path, frame)
        with self.assertRaises(ValueError):
            release.sources()

    def test_static_export_is_native_size_pixel_exact_and_individually_attributed(self):
        self.prepare_sources()
        release.export()
        manifest = json.loads((self.root / 'assets/pimm-bento-r11-stills.v1.json').read_text())
        self.assertEqual(len(manifest['assets']), 4)
        for item in manifest['assets']:
            with Image.open(item['native_path']) as source, Image.open(self.root / 'assets' / item['filename']) as encoded:
                self.assertEqual(encoded.size, source.size)
                self.assertEqual(encoded.convert('RGB').tobytes(), source.convert('RGB').tobytes())
            approval = self.white_approval if item['shot'] == 'configuration' else self.r10_approval
            self.assertEqual(item['approval_sha256'], sha256_file(approval))

    def test_existing_still_prevents_any_other_release_writes(self):
        self.prepare_sources()
        existing = self.root / 'assets/pimm-bento-20260903-r11-30g-tooling.webp'
        existing.write_bytes(b'keep-existing')
        with self.assertRaises(FileExistsError):
            release.export()
        self.assertEqual(list((self.root / 'assets').iterdir()), [existing])
        self.assertEqual(existing.read_bytes(), b'keep-existing')

    def test_existing_manifest_prevents_any_still_writes(self):
        self.prepare_sources()
        existing = self.root / 'assets/pimm-bento-r11-stills.v1.json'
        existing.write_bytes(b'keep-existing-manifest')
        with self.assertRaises(FileExistsError):
            release.export()
        self.assertEqual(list((self.root / 'assets').iterdir()), [existing])
        self.assertEqual(existing.read_bytes(), b'keep-existing-manifest')

    def test_source_change_during_encoding_cannot_publish_release_manifest(self):
        self.prepare_sources()
        selected = release.sources()
        changed = deepcopy(selected)
        changed[3]['approval_sha256'] = 'changed'
        with patch.object(release, 'sources', side_effect=[selected, changed]):
            with self.assertRaises(ValueError):
                release.export()
        self.assertFalse((self.root / 'assets/pimm-bento-r11-stills.v1.json').exists())


if __name__ == '__main__':
    unittest.main()
