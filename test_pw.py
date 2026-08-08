import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            java_script_enabled=True,
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        page = await context.new_page()
        url = 'https://seas.harvard.edu/faculty?utm_source=PANTHEON_STRIPPED&search=&field_teaching_areas%5B51%5D=51&field_teaching_areas%5B56%5D=56&field_teaching_areas%5B81%5D=81&field_teaching_areas%5B86%5D=86&field_teaching_areas%5B91%5D=91&field_teaching_areas%5B96%5D=96&sort_by=field_last_name'
        await page.goto(url, wait_until="networkidle", timeout=45_000)
        await page.wait_for_timeout(2500)
        html = await page.content()
        await browser.close()
        
        print("PERSON COUNT:", html.count("person/"))
        print("CLOUDFLARE BLOCK:", "Just a moment" in html or "cloudflare" in html.lower())

asyncio.run(test())
