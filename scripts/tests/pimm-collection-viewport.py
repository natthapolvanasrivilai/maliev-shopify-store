"""Live regression: the comparison must fit one desktop viewport, not clip."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

parser = argparse.ArgumentParser()
parser.add_argument('--url', required=True)
parser.add_argument('--motion', action='store_true')
parser.add_argument('--pixel-density', type=float, default=1)
parser.add_argument('--check-native-resolution', action='store_true')
parser.add_argument('--evidence', default='.codex-tmp/pimm-motion-browser')
args = parser.parse_args()
out = Path(args.evidence)
out.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True)
    for language in ['en', 'th']:
        url = args.url.replace('/products_preview', '/th/products_preview') if language == 'th' else args.url
        for width, height in [(1280, 720), (1440, 900), (1536, 864), (1920, 720), (1920, 1080), (390, 844)]:
            page = browser.new_page(viewport={'width': width, 'height': height}, device_scale_factor=args.pixel_density)
            page.goto(url, wait_until='domcontentloaded')
            try:
                page.wait_for_load_state('networkidle', timeout=3000)
            except PlaywrightTimeout:
                pass  # Shopify dev's event stream stays open; use component readiness below.
            page.locator('[data-pimm-collection-card]').first.wait_for()
            page.evaluate('document.fonts.ready')
            page.wait_for_function('''() => [...document.querySelectorAll('[data-pimm-collection-frame="front"] img')].every(i=>i.complete && i.naturalWidth > 0)''')
            page.add_style_tag(content='#shopify-pc__banner, #shopify-privacy-banner, [data-shopify-privacy-banner] { display:none!important }')
            page.screenshot(path=str(out / f'{language}-{width}x{height}.png'), full_page=True)
            geometry = page.evaluate('''() => {
              const cards = [...document.querySelectorAll('[data-pimm-collection-card]')];
              const root = document.querySelector('pimm-collection-comparison');
              const rect = e => { const r = e.getBoundingClientRect(); return {x:r.x,y:r.y,w:r.width,h:r.height,bottom:r.bottom}; };
              const dossier = document.querySelector('.pimm-collection__dossier--desktop');
              return {height:document.documentElement.scrollHeight,width:document.documentElement.scrollWidth,
                sourcePixelRatios:[...root.querySelectorAll('[data-pimm-collection-frame="front"] img')].map(image=>{
                  const r=image.getBoundingClientRect();
                  return {width:image.naturalWidth,height:image.naturalHeight,
                    ratio:Math.max(r.width/image.naturalWidth,r.height/image.naturalHeight)*devicePixelRatio};
                }),
                root:rect(root),cards:cards.map(rect),dossier:rect(dossier),
                dossierChildren:[...dossier.querySelectorAll('a,dd,p,h2')].filter(e=>e.getBoundingClientRect().height>0).map(rect),
                clipped:[...root.querySelectorAll('a,button,h1,h2,dd,p')].filter(e => e.clientHeight > 0 && e.scrollHeight > e.clientHeight + 2).map(e=>({tag:e.tagName,text:e.textContent,client:e.clientHeight,scroll:e.scrollHeight}))};
            }''')
            print(language, width, height, json.dumps({key:value for key,value in geometry.items() if key != 'dossierChildren'}), flush=True)
            assert geometry['width'] <= width, 'horizontal overflow'
            if args.check_native_resolution:
                assert all(image['width'] == 1440 and image['height'] == 1920 for image in geometry['sourcePixelRatios']), 'wrong native source dimensions'
                assert all(image['ratio'] <= 1 for image in geometry['sourcePixelRatios']), 'source is upscaled beyond native screen pixels'
            if width >= 1280:
                assert geometry['height'] <= height + 1, 'desktop document exceeds viewport'
                assert all(c['bottom'] <= height for c in geometry['cards']), 'cards below fold'
                assert geometry['dossier']['bottom'] <= height, 'dossier below fold'
                assert all(c['bottom'] <= geometry['dossier']['bottom'] for c in geometry['dossierChildren']), 'dossier content outside panel'
                assert not geometry['clipped'], 'text clipped'
            if args.motion and width == 1440:
                for model in ['30G', '50G']:
                    card = page.locator(f'[data-pimm-collection-card][data-model="{model}"]')
                    card.hover()
                    video = card.locator('[data-pimm-collection-video]')
                    page.wait_for_function('(v)=>v.currentTime > 0.3', arg=video.element_handle())
                    assert video.evaluate('(v)=>v.muted && !v.loop && v.videoWidth === v.parentElement.querySelector("img").naturalWidth')
                    page.wait_for_function('(v)=>v.paused && !v.classList.contains("is-playing")', arg=video.element_handle())
                page.emulate_media(reduced_motion='reduce')
                page.mouse.move(0, 0)
                page.locator('[data-pimm-collection-card]').first.hover()
                assert page.locator('video').first.evaluate('(v)=>v.paused')
            page.close()
    browser.close()
