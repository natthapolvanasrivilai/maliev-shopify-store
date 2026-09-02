"""Run against the local preview only; no Shopify writes or checkout requests."""
from pathlib import Path
from playwright.sync_api import sync_playwright

EVIDENCE = Path('.codex-tmp/hero-reveal-browser')
EVIDENCE.mkdir(parents=True, exist_ok=True)
BASE = 'http://127.0.0.1:9494'
PATH = '/products/pneumatic-injection-molding-machine'

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True)
    for locale in ['', '/th']:
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        page.goto(BASE + locale + PATH, wait_until='domcontentloaded')
        reveal = page.locator('pimm-hero-reveal')
        reveal.wait_for()
        page.wait_for_function("document.querySelector('pimm-hero-reveal').finished === true")
        video, poster = reveal.locator('video'), reveal.locator('img')
        assert video.evaluate('(v) => v.videoWidth') == 1440
        assert video.evaluate('(v) => v.videoHeight') == 1920
        assert video.evaluate('(v) => v.duration') == 2
        assert reveal.locator('button').count() == 0 and poster.is_visible()
        assert video.get_attribute('controls') is None
        page.evaluate('scrollTo(0, document.body.scrollHeight)')
        page.wait_for_timeout(250)
        page.evaluate('scrollTo(0, 0)')
        page.wait_for_timeout(250)
        assert video.evaluate('(v) => v.paused && v.currentTime === v.duration')
        page.wait_for_function("document.querySelector('pimm-hero-reveal video').hidden")
        for w, h in [(360,800),(390,844),(768,1024),(1024,768),(1440,900),(1920,1080)]:
            page.set_viewport_size({'width': w, 'height': h})
            page.evaluate('scrollTo(0,0)')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            image_box = poster.bounding_box()
            stage = page.locator('.pimm-machine__hero-stage').bounding_box()
            assert image_box['y'] + image_box['height'] <= stage['y'] + stage['height'] + 1
            assert poster.evaluate('(e)=>getComputedStyle(e).objectFit') == 'contain'
            if w in [390,1440]:
                page.screenshot(path=str(EVIDENCE / f'{locale.replace("/", "") or "en"}-rest-{w}.png'))
        page.close()
        reduced = browser.new_page(reduced_motion='reduce')
        reduced.goto(BASE + locale + PATH, wait_until='domcontentloaded')
        reduced.wait_for_selector('pimm-hero-reveal')
        assert reduced.locator('pimm-hero-reveal video').get_attribute('src') is None
        assert reduced.locator('pimm-hero-reveal button').count() == 0
        assert reduced.locator('pimm-hero-reveal img').get_attribute('src').split('?')[0].endswith('-rest.webp')
        reduced.close()
        print(locale or 'en', 'native one-shot playback, no replay, 6 widths and reduced-motion PASS')
    failed = browser.new_page()
    failed.route('**/*pimm-30g-hero-reveal*.mp4*', lambda route: route.abort())
    failed.goto(BASE + PATH, wait_until='domcontentloaded')
    failed.wait_for_selector('pimm-hero-reveal')
    failed.wait_for_function("document.querySelector('pimm-hero-reveal').finished")
    assert failed.locator('pimm-hero-reveal img').is_visible()
    assert not failed.locator('pimm-hero-reveal video').is_visible()
    print('Failed-video bright fallback PASS')
    browser.close()
