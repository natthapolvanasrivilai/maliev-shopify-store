"""Render only the exact owner-approved r12 lighting state at native resolution."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.blender.pimm_production.blender_bento_white_final import white_contract
from scripts.blender.pimm_production.blender_bento_r10_final import render
from scripts.blender.pimm_production.paths import ASSET_ROOT, REPO_ROOT

APPROVAL = REPO_ROOT / 'docs/pimm-blender-governance/bento-r12-white-detail-approval.json'
OUTPUT = ASSET_ROOT / 'renders/final/bento-20260903-r12-white-detail-native'


def detail_contract(shot):
    return white_contract(shot, APPROVAL, white_contract, 'blender_bento_white_detail_proof.py')


if __name__ == '__main__':
    render('configuration', detail_contract, APPROVAL, OUTPUT)
    os._exit(0)
