import httpx
import json
import asyncio

async def test():
    url = "https://seas.harvard.edu/faculty?utm_source=PANTHEON_STRIPPED&search=&field_teaching_areas%5B51%5D=51&field_teaching_areas%5B56%5D=56&field_teaching_areas%5B81%5D=81&field_teaching_areas%5B86%5D=86&field_teaching_areas%5B91%5D=91&field_teaching_areas%5B96%5D=96&sort_by=field_last_name"
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream("POST", "http://127.0.0.1:8765/scrape-directory", json={"url": url, "max_pages": 1, "max_profiles": 5}) as resp:
            async for chunk in resp.aiter_text():
                print(chunk, end="")

asyncio.run(test())
