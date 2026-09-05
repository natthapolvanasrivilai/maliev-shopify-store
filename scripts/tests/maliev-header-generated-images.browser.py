"""Verify generated mega-menu images against a running local Shopify preview."""

import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


PREVIEW_URL = os.environ.get(
    "MALIEV_PREVIEW_URL",
    "http://127.0.0.1:9494/products/pneumatic-injection-molding-machine",
)
EVIDENCE = Path(".codex-tmp/header-generated-images")
EVIDENCE.mkdir(parents=True, exist_ok=True)


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(PREVIEW_URL, wait_until="domcontentloaded")
    page.wait_for_selector("[data-mc-mega-menu]")
    page.evaluate("document.querySelector('#shopify-pc__banner')?.remove()")

    previews = {}
    groups = page.locator("[data-mc-mega-menu]")
    for group_index in range(groups.count()):
        group = groups.nth(group_index)
        group.locator(":scope > summary").click()
        links = group.locator("[data-mc-menu-preview]")
        feature_image = group.locator("[data-mc-menu-feature] img")

        for link_index in range(links.count()):
            link = links.nth(link_index)
            title = link.get_attribute("data-preview-title")
            source = link.get_attribute("data-preview-image")
            link.hover()
            feature_image.wait_for()
            expect(feature_image).to_have_attribute("src", source)
            feature_image.evaluate("image => image.decode()")
            assert feature_image.evaluate("image => image.complete && image.naturalWidth > 0")
            assert previews.get(title, source) == source
            previews[title] = source

            if title == "3D Printing Services":
                page.screenshot(path=str(EVIDENCE / "manufacturing-3d-printing-hover.png"))

        group.locator(":scope > summary").click()

    assert len(previews) >= 13
    assert len(set(previews.values())) == len(previews)
    assert all("maliev-nav-preview-" in source for source in previews.values())
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")

    for width, height in [(1024, 768), (768, 1024), (390, 844)]:
        page.set_viewport_size({"width": width, "height": height})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")

    print(f"{len(previews)} interactive menu previews use distinct generated images; responsive overflow PASS")
    browser.close()
