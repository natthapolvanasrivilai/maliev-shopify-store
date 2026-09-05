"""Package reviewed proof pixels only; never generate storefront assets."""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from scripts.blender.pimm_production.paths import ASSET_ROOT
from scripts.blender.pimm_production.io_contract import sha256_file


def frame_durations(count=192, fps=24):
    return [round((i+1)*1000/fps)-round(i*1000/fps) for i in range(count)]


def main():
    folder = ASSET_ROOT / 'renders/proofs/bento-20260903-r10-orbit'
    destination = folder / 'review'
    if destination.exists():
        raise FileExistsError(destination)
    paths = sorted((folder / 'controls').glob('frame-*.png'))
    if len(paths) != 192:
        raise ValueError(f'Expected all 192 Blender frames, found {len(paths)}')
    contract_path = ASSET_ROOT / 'scenes/contracts/pimm-30g--bento-bento-20260903-r10-orbit--controls.json'
    contract = json.loads(contract_path.read_text())
    assert len(contract['proofs']) == 192 and contract['approval'] == 'pending'
    for path, record in zip(paths, contract['proofs']):
        assert sha256_file(path) == record['sha256']
    frames = [Image.open(path).convert('RGB') for path in paths]
    assert all(frame.size == (600,300) for frame in frames)
    destination.mkdir()
    animation = destination / 'controls-orbit-review.webp'
    frames[0].save(animation, save_all=True, append_images=frames[1:], duration=frame_durations(), loop=0, lossless=True, method=4)
    with Image.open(animation) as result:
        assert result.n_frames == 192 and result.size == (600,300)
    sheet = Image.new('RGB', (1040, 1180), 'white')
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=20)
    draw.text((20,15), 'PROOF ONLY - revised Blender lighting / camera-only orbit', fill='black', font=font)
    for shot, xy in [('controls',(420,80)), ('configuration',(420,450)), ('capacity',(0,80)), ('tooling',(0,670))]:
        image = Image.open(ASSET_ROOT / f'renders/proofs/bento-20260903-r10-lighting/{shot}/still.png').convert('RGB')
        draw.text((xy[0]+16,xy[1]-28), shot.upper(), fill='black', font=font)
        sheet.paste(image, xy)
    draw.text((436,810), 'Controls orbit: +/-3 degrees, 8 seconds, 24 fps', fill='black', font=font)
    draw.text((436,845), 'Machine geometry, materials and displays unchanged.', fill='black', font=ImageFont.load_default(size=18))
    sheet.save(destination / 'lighting-contact-sheet.png')
    (destination / 'index.html').write_text('''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>30G lighting and orbit proof</title>
<style>body{margin:0;background:#f3f5f6;color:#111315;font:18px/1.5 system-ui,sans-serif}main{max-width:1040px;margin:auto;padding:32px 20px}h1{font-size:32px;line-height:1.15}img{display:block;max-width:100%;height:auto;border-radius:14px}#orbit{width:100%}button{font:inherit;padding:10px 18px;margin:16px 0 40px;background:#111315;color:white;border:0;border-radius:4px}button:focus-visible{outline:3px solid #006fd6;outline-offset:4px}button:disabled{opacity:.6}</style>
<main><h1>30G lighting and camera-orbit proof</h1>
<p>Review only. These are low-resolution Blender proofs, not the final storefront assets.</p>
<img id="orbit" src="../controls/frame-0001.png" width="600" height="300" alt="30G pneumatic controls, subtle camera orbit">
<button id="motion" type="button">Play motion</button>
<p>Camera only: ±3°, eight seconds, 24 fps. Reduced motion displays the static frame.</p>
<img src="lighting-contact-sheet.png" width="1040" height="1180" alt="Four revised lighting proofs: capacity, pneumatic controls, mold area and full machine">
</main><script>
const preference=matchMedia('(prefers-reduced-motion: reduce)'), image=document.querySelector('#orbit'),button=document.querySelector('#motion');
let paused=false;
function sync(){const active=!preference.matches&&!paused;image.src=active?'controls-orbit-review.webp':'../controls/frame-0001.png';button.textContent=preference.matches?'Reduced motion: static image':active?'Pause motion':'Play motion';button.disabled=preference.matches;}
button.addEventListener('click',()=>{paused=!paused;sync()});preference.addEventListener('change',sync);sync();
</script></html>''', encoding='utf-8')
    receipt = {'status':'pending_owner_approval','animation_sha256':sha256_file(animation),
               'frames':192,'duration_ms':sum(frame_durations()),'size':[600,300],
               'contract_sha256':sha256_file(contract_path),'encoding':'lossless native-proof-size animated WebP',
               'contact_sheet_sha256':sha256_file(destination / 'lighting-contact-sheet.png')}
    (destination / 'review.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
