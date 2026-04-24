"""Whitney recon — locate the desktop scope and verify row counts."""
import asyncio
from playwright.async_api import async_playwright

URL = "https://www.thewhitneyonredpath.com/apartments/"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(URL, wait_until="domcontentloaded")

        total = await page.locator(".clickable-row").count()
        print(f"Total .clickable-row page-wide: {total}")

        desktop = page.locator("div.elementor-element-de0643b")
        print(f"Desktop block (de0643b) found: {await desktop.count()}")
        print(f"  .clickable-row: {await desktop.locator('.clickable-row').count()}")
        print(f"  visible: {await desktop.locator('.clickable-row:not(.d-none)').count()}")
        print(f"  hidden: {await desktop.locator('.clickable-row.d-none').count()}")

        mobile = page.locator("div.elementor-element-2caecaa")
        print(f"\nMobile block (2caecaa) found: {await mobile.count()}")
        print(f"  .clickable-row: {await mobile.locator('.clickable-row').count()}")
        print(f"  visible: {await mobile.locator('.clickable-row:not(.d-none)').count()}")
        print(f"  hidden: {await mobile.locator('.clickable-row.d-none').count()}")

        visible = desktop.locator(".clickable-row:not(.d-none)")
        vcount = await visible.count()
        print(f"\n--- Visible desktop rows ({vcount}) ---")
        for i in range(vcount):
            row = visible.nth(i)
            paragraphs = await row.locator("p").all_text_contents()
            print(f"  [{i}] {paragraphs}")

        hidden = desktop.locator(".clickable-row.d-none")
        hcount = await hidden.count()
        print(f"\n--- Hidden desktop rows ({hcount}) ---")
        for i in range(hcount):
            row = hidden.nth(i)
            paragraphs = await row.locator("p").all_text_contents()
            print(f"  [{i}] {paragraphs}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
