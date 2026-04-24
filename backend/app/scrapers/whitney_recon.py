"""Whitney recon v3 — use data-link anchors, check real visibility."""
import asyncio
from playwright.async_api import async_playwright

URL = "https://www.thewhitneyonredpath.com/apartments/"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(URL, wait_until="domcontentloaded")

        # All elements with data-link pointing to a floorplan page
        anchors = page.locator("[data-link]")
        total = await anchors.count()
        print(f"Total [data-link] anchors page-wide: {total}")

        # Get unique data-link values and parent row visibility
        seen_slugs = set()
        results = []
        for i in range(total):
            a = anchors.nth(i)
            slug = await a.get_attribute("data-link")
            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)
            # Climb to the floorplan row (parent that holds all 4 columns)
            # Each data-link anchor is ONE column; we want its parent row
            row = a.locator("xpath=..")
            visible = await row.is_visible()
            # Gather text from the row
            paragraphs = await row.locator("p").all_text_contents()
            results.append((slug, visible, paragraphs))

        print(f"\nUnique floorplan slugs: {len(results)}")
        print(f"\n--- All floorplan rows (slug, visible?, paragraphs) ---")
        for slug, vis, paras in results:
            marker = "VIS" if vis else "HID"
            print(f"  [{marker}] {slug}")
            print(f"        {paras}")

        # Also check: what does d-none look like in DOM?
        d_none = page.locator(".d-none")
        print(f"\n.d-none elements in DOM: {await d_none.count()}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
