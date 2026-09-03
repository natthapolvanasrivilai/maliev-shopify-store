"""Render the separately approved white configuration shot without scene edits."""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.blender.pimm_production.blender_bento_r10_final import contract_for, render
from scripts.blender.pimm_production.blender_bento_final import checked_file
from scripts.blender.pimm_production.paths import ASSET_ROOT, REPO_ROOT, require_within

APPROVAL = REPO_ROOT / 'docs/pimm-blender-governance/bento-r11-white-approval.json'
OUTPUT = ASSET_ROOT / 'renders/final/bento-20260903-r11-white-native'


def white_contract(shot, approval_path=None, source_loader=None, proof_script='blender_bento_white_proof.py'):
    approval = json.loads((approval_path or APPROVAL).read_text())
    if approval['decision'] != 'approved' or shot != 'configuration':
        raise ValueError('Exact white configuration approval required')
    path = checked_file(require_within(Path(approval['contract_path']), ASSET_ROOT / 'scenes/contracts'), approval['contract_sha256'])
    contract = json.loads(path.read_text())
    if contract['generation'] != approval['generation'] or contract['shot'] != shot:
        raise ValueError('Wrong white configuration contract')
    source = (source_loader or contract_for)('configuration')
    if contract['source_scene_sha256'] != source['scene_sha256']:
        raise ValueError('White studio source changed')
    for key in ('master_sha256', 'material_library_sha256', 'tool_lock_sha256'):
        if contract[key] != source[key]:
            raise ValueError('White studio product authority changed')
    if contract['scene_sha256'] != approval['scene_sha256'] or contract['native_size'] != [2400, 1200]:
        raise ValueError('White scene or native size changed')
    checked_file(require_within(Path(contract['scene_path']), ASSET_ROOT / 'scenes/stills'), approval['scene_sha256'])
    checked_file(Path(__file__).with_name(proof_script), contract['script_sha256'])
    if len(contract['proofs']) != 1 or contract['proofs'][0]['sha256'] != approval['proof_sha256']:
        raise ValueError('White proof approval changed')
    checked_file(require_within(Path(contract['proofs'][0]['path']), ASSET_ROOT / 'renders/proofs'), approval['proof_sha256'])
    return contract


if __name__ == '__main__':
    render('configuration', white_contract, APPROVAL, OUTPUT)
    os._exit(0)
