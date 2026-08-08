import asyncio
from server import _fetch_page_js, _extract_profile_links

async def main():
    url = "https://seas.harvard.edu/faculty?utm_source=PANTHEON_STRIPPED&search=&field_teaching_areas%5B51%5D=51&field_teaching_areas%5B56%5D=56&field_teaching_areas%5B81%5D=81&field_teaching_areas%5B86%5D=86&field_teaching_areas%5B91%5D=91&field_teaching_areas%5B96%5D=96&sort_by=field_last_name"
    html = await _fetch_page_js(url)
    print(f"HTML LENGTH: {len(html)}")
    profiles = _extract_profile_links(html, url)
    print(f"PROFILES: {len(profiles)}")

asyncio.run(main())
