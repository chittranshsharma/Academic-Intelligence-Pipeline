"""
Faculty Intelligence — Local FastAPI Server
===========================================
Acts as the bridge between the Chrome browser extension and Groq API.

Run with:
    python server.py

The server listens on http://localhost:8765
The Chrome extension connects to this server to classify faculty profiles
you browse to in real-time, using the same Groq AI pipeline as the batch tool.

Endpoints:
    GET  /status                — Health check (extension polls this)
    POST /classify              — Classify a single faculty page (html + url)
    POST /scrape-directory      — Auto-paginate + classify a full faculty directory (SSE stream)
    POST /save                  — Append a confirmed record to cleaned_data.json
    GET  /records               — Return total count + last 5 records
    GET  /export                — Trigger CSV/XLSX export
"""

import asyncio
import json
import logging
import os
import re
import sys
from datetime import datetime
from typing import AsyncGenerator, Optional
from urllib.parse import urljoin, urlparse

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

# ── Environment ──────────────────────────────────────────────────────────────
load_dotenv()

# ── Logging ──────────────────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/server.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("server")

# ── Lazy import parser (after logging is configured) ─────────────────────────
from parser import FacultyParser  # noqa: E402

# ── Constants ────────────────────────────────────────────────────────────────
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8765
DEFAULT_MODEL = "llama-3.3-70b-versatile"
DATA_FILE = "cleaned_data.json"

# ── App Setup ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Faculty Intelligence Server",
    description="Local AI server for the Faculty Intelligence Chrome Extension",
    version="1.0.0",
)

# Allow Chrome extension origin (chrome-extension://*) and local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Local-only server — fine to allow all
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── Browser-like HTTP helpers ────────────────────────────────────────────────────

_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]


def _make_headers(referer: str = "") -> dict:
    """Return a realistic set of browser HTTP headers that avoid WAF 403s."""
    ua = random.choice(_UA_POOL)
    is_firefox = "Firefox" in ua
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
    }
    if not is_firefox:
        headers.update({
            "Sec-CH-UA": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin" if referer else "none",
            "Sec-Fetch-User": "?1",
        })
    if referer:
        headers["Referer"] = referer
    return headers


async def _fetch_page(
    client: httpx.AsyncClient,
    url: str,
    referer: str = "",
    retries: int = 3,
) -> str:
    """
    Fetch a URL with retry / back-off logic.
    Rotates headers on each retry to reduce the chance of fingerprint-based blocks.
    Returns the response text on success, raises on repeated failure.
    """
    last_exc: Exception = RuntimeError("Unknown error")
    for attempt in range(1, retries + 1):
        try:
            resp = await client.get(
                url,
                headers=_make_headers(referer),
                follow_redirects=True,
            )
            if resp.status_code == 403:
                # Hard bot-block: back off more aggressively
                wait = 2 ** attempt + random.uniform(0, 1)
                logger.warning(f"403 on {url} (attempt {attempt}/{retries}) — backing off {wait:.1f}s")
                if attempt < retries:
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()  # will raise on final attempt
            resp.raise_for_status()
            return resp.text
        except httpx.HTTPStatusError as e:
            last_exc = e
            if e.response.status_code in (429, 503):
                wait = 5 * attempt + random.uniform(0, 2)
                logger.warning(f"Rate-limited on {url} (attempt {attempt}/{retries}) — waiting {wait:.1f}s")
                await asyncio.sleep(wait)
            elif attempt < retries:
                await asyncio.sleep(1.5 * attempt)
            else:
                raise
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as e:
            last_exc = e
            if attempt < retries:
                await asyncio.sleep(1.5 * attempt)
            else:
                raise
    raise last_exc


async def _fetch_page_js(url: str, wait_extra_ms: int = 2500) -> str:
    """
    Fetch a JavaScript-rendered page using a headless Chromium browser (Playwright).
    Used automatically when httpx returns a page with no profile links (SPA detection).

    Mimics a real browser session: full viewport, realistic UA, waits for network idle
    then an extra delay to let React/Vue/Angular finish rendering.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise RuntimeError(
            "Playwright not installed. Run: pip install playwright && playwright install chromium"
        )

    logger.info(f"[Playwright] Launching headless Chromium for: {url}")
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
            user_agent=random.choice(_UA_POOL),
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            java_script_enabled=True,
            # Mask automation fingerprint
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )

        # Remove the webdriver property that sites use to detect bots
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        page = await context.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=45_000)
            # Extra wait for lazy-loaded / paginated content
            await page.wait_for_timeout(wait_extra_ms)
            html = await page.content()
        finally:
            await browser.close()

    logger.info(f"[Playwright] Got {len(html)} bytes from {url}")
    return html


def _looks_like_js_page(html: str) -> bool:
    """
    Heuristic: returns True if the page is likely a JS SPA that rendered no useful content.
    Checks for very low anchor-tag count + React/Vue/Angular script fingerprints.
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a", href=True)
    scripts = soup.find_all("script", src=True)
    script_text = " ".join(s.get("src", "") for s in scripts).lower()
    # Signs of a JS-heavy SPA
    is_spa = any(k in script_text for k in ("react", "vue", "angular", "next", "nuxt", "chunk", "bundle"))
    return len(links) < 15 or is_spa


# ── Parser Singleton ─────────────────────────────────────────────────────────
groq_api_key = os.environ.get("GROQ_API_KEY", "")
if not groq_api_key:
    logger.warning("⚠  GROQ_API_KEY not set in environment / .env file.")
    logger.warning("   Get a free key at: https://console.groq.com/keys")

_parser: Optional[FacultyParser] = None


def get_parser() -> FacultyParser:
    """Return (or lazily create) the shared FacultyParser instance."""
    global _parser, groq_api_key
    if _parser is None:
        _parser = FacultyParser(
            model_name=DEFAULT_MODEL,
            groq_api_key=groq_api_key,
        )
    return _parser


def update_api_key(new_key: str):
    """Dynamically update the active GROQ_API_KEY and re-initialize FacultyParser."""
    global groq_api_key, _parser
    groq_api_key = new_key.strip()
    _parser = FacultyParser(
        model_name=DEFAULT_MODEL,
        groq_api_key=groq_api_key,
    )
    logger.info(f"GROQ_API_KEY dynamically updated (key: {groq_api_key[:4]}...{groq_api_key[-4:] if len(groq_api_key) > 8 else '***'})")

    # Persist to .env file so server restarts retain the updated key
    try:
        env_path = ".env"
        env_lines = []
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                env_lines = f.readlines()

        key_found = False
        new_lines = []
        for line in env_lines:
            if line.startswith("GROQ_API_KEY="):
                new_lines.append(f"GROQ_API_KEY={groq_api_key}\n")
                key_found = True
            else:
                new_lines.append(line)
        if not key_found:
            new_lines.append(f"\nGROQ_API_KEY={groq_api_key}\n")

        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    except Exception as e:
        logger.warning(f"Could not persist GROQ_API_KEY to .env: {e}")


# ── Request / Response Models ─────────────────────────────────────────────────
class ApiKeyRequest(BaseModel):
    groq_api_key: str


class ClassifyRequest(BaseModel):
    html: str
    url: str
    groq_api_key: Optional[str] = None


class ScrapeDirectoryRequest(BaseModel):
    url: str                     # Starting directory URL
    max_pages: int = 100         # Max pagination pages to follow
    max_profiles: int = 1000     # Hard cap on profiles to process
    concurrency: int = 5         # Parallel Groq calls per batch
    groq_api_key: Optional[str] = None


class SaveRequest(BaseModel):
    record: dict


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/status")
async def status():
    """Health check — extension polls this to show connection indicator and key status."""
    masked_key = ""
    if groq_api_key:
        masked_key = f"{groq_api_key[:4]}...{groq_api_key[-4:]}" if len(groq_api_key) > 8 else "***"
    return {
        "status": "running",
        "model": DEFAULT_MODEL,
        "api_key_set": bool(groq_api_key),
        "api_key_masked": masked_key,
        "data_file": DATA_FILE,
        "record_count": _get_record_count(),
    }


@app.post("/set-api-key")
async def set_api_key(req: ApiKeyRequest):
    """Dynamically upload/update Groq API key from browser extension."""
    if not req.groq_api_key or not req.groq_api_key.strip():
        raise HTTPException(status_code=400, detail="API key cannot be empty.")

    update_api_key(req.groq_api_key)
    masked = f"{groq_api_key[:4]}...{groq_api_key[-4:]}" if len(groq_api_key) > 8 else "***"
    return {
        "status": "updated",
        "api_key_set": True,
        "api_key_masked": masked,
        "message": "Groq API key updated successfully."
    }


@app.post("/classify")
async def classify(req: ClassifyRequest):
    """
    Classify a faculty profile page.
    Accepts: {html: str, url: str, groq_api_key: optional str}
    Returns: structured profile dict with is_south_asian, is_valid_role, etc.
    """
    if req.groq_api_key and req.groq_api_key.strip():
        update_api_key(req.groq_api_key)

    if not groq_api_key:
        raise HTTPException(
            status_code=503,
            detail="GROQ_API_KEY not configured. Please paste your Groq API Key in the extension popup.",
        )

    if not req.html or not req.url:
        raise HTTPException(status_code=400, detail="Both 'html' and 'url' fields are required.")

    # Truncate HTML to 2MB before processing (safety guard)
    html = req.html[:2_000_000]

    try:
        parser = get_parser()
        result = await parser.classify_html(html, req.url)
    except Exception as e:
        logger.error(f"classify_html error for {req.url}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")

    if result is None:
        raise HTTPException(
            status_code=422,
            detail="Could not extract profile data. The LLM returned no usable output.",
        )

    logger.info(f"Classified: {req.url} → is_south_asian={result.get('is_south_asian')}, is_valid_role={result.get('is_valid_role')}")
    return result


@app.post("/scrape-directory")
async def scrape_directory(req: ScrapeDirectoryRequest):
    """
    Auto-paginate a faculty directory and classify all profile pages.
    Returns a Server-Sent Events (SSE) stream so the extension can show
    live progress without polling.

    Event format (one JSON object per line, prefixed with 'data: '):
        {"type": "start",    "message": str, "url": str}
        {"type": "page",     "page": int, "url": str, "profiles_found": int}
        {"type": "progress", "index": int, "total": int, "url": str, "status": str, "name": str}
        {"type": "saved",    "record": {...}, "total_saved": int}
        {"type": "done",     "pages": int, "profiles": int, "saved": int, "skipped": int}
        {"type": "error",    "message": str}
    """
    if req.groq_api_key and req.groq_api_key.strip():
        update_api_key(req.groq_api_key)

    if not groq_api_key:
        raise HTTPException(
            status_code=503,
            detail="GROQ_API_KEY not configured. Please paste your Groq API Key in the extension popup.",
        )

    async def event_stream() -> AsyncGenerator[str, None]:
        def sse(obj: dict) -> str:
            """Format a dict as an SSE data line."""
            return f"data: {json.dumps(obj)}\n\n"

        try:
            yield sse({"type": "start", "message": f"Starting directory scrape: {req.url}", "url": req.url})

            # ── Phase 1: Discover all profile URLs by paginating ──────────────
            all_profile_urls: list[str] = []
            visited_pages: set[str] = set()
            current_page_url = req.url
            page_num = 0
            use_playwright = False   # auto-set to True if SPA detected

            async with httpx.AsyncClient(follow_redirects=True, timeout=25.0) as client:

                while current_page_url and page_num < req.max_pages:
                    if current_page_url in visited_pages:
                        break
                    visited_pages.add(current_page_url)
                    page_num += 1

                    # ── Fetch the directory page ─────────────────────────────
                    try:
                        if use_playwright:
                            html = await _fetch_page_js(current_page_url)
                        else:
                            html = await _fetch_page(client, current_page_url)
                    except Exception as e:
                        yield sse({"type": "error", "message": f"Failed to fetch page {page_num}: {e}"})
                        break

                    # ── Auto-detect JS-rendered SPA on first page ────────────
                    page_profiles = _extract_profile_links(html, current_page_url)
                    if not page_profiles and page_num == 1 and not use_playwright:
                        js_hint = _looks_like_js_page(html)
                        yield sse({
                            "type": "info",
                            "message": (
                                "🤖 Detected JavaScript-rendered page"
                                + (" (React/Vue/Angular SPA)" if js_hint else "")
                                + " — switching to headless Chromium (Playwright). "
                                "This may take 10-20s per page…"
                            ),
                        })
                        try:
                            html = await _fetch_page_js(current_page_url)
                            page_profiles = _extract_profile_links(html, current_page_url)
                            use_playwright = True
                            yield sse({"type": "mode", "engine": "playwright"})
                        except Exception as pw_err:
                            yield sse({
                                "type": "error",
                                "message": (
                                    f"Headless browser failed: {pw_err}\n"
                                    "Make sure Playwright is installed: "
                                    "pip install playwright && playwright install chromium"
                                ),
                            })
                            return
                    elif page_num == 1:
                        yield sse({"type": "mode", "engine": "httpx"})

                    new_profiles = [u for u in page_profiles if u not in all_profile_urls]
                    all_profile_urls.extend(new_profiles)

                    yield sse({
                        "type": "page",
                        "page": page_num,
                        "url": current_page_url,
                        "profiles_found": len(new_profiles),
                        "total_profiles": len(all_profile_urls),
                    })

                    if len(all_profile_urls) >= req.max_profiles:
                        all_profile_urls = all_profile_urls[:req.max_profiles]
                        break

                    # Find next page
                    next_url = _find_next_page(html, current_page_url)
                    if not next_url:
                        break
                    current_page_url = next_url
                    # Longer polite delay for headless browser (heavier)
                    await asyncio.sleep(random.uniform(2.5, 4.0) if use_playwright else random.uniform(0.8, 2.0))

            if not all_profile_urls:
                yield sse({
                    "type": "error",
                    "message": (
                        "No profile links found even after trying headless browser.\n"
                        "The site may require login, use non-standard URL patterns, "
                        "or the profile links use paths not in our heuristic list.\n"
                        "Try: https://www.ece.uw.edu/people/faculty/ or "
                        "https://www.cs.ubc.ca/people/faculty (these are static HTML)"
                    ),
                })
                return


            # ── Phase 2: Classify all profiles in concurrent batches ──────────
            parser = get_parser()
            total = len(all_profile_urls)
            saved_count = 0
            skipped_count = 0

            # Load existing URLs to skip duplicates upfront
            existing_data = _load_data()
            existing_urls = {r.get("profile_link", "") for r in existing_data}

            semaphore = asyncio.Semaphore(req.concurrency)

            async def classify_one(url: str, idx: int):
                nonlocal saved_count, skipped_count
                async with semaphore:
                    # Skip if already in dataset
                    if url in existing_urls:
                        skipped_count += 1
                        return None, url, "duplicate"

                    # Fetch profile HTML with browser headers + retry
                    try:
                        async with httpx.AsyncClient(
                            follow_redirects=True, timeout=20.0
                        ) as c:
                            profile_html = await _fetch_page(c, url, referer=req.url)
                    except Exception as e:
                        skipped_count += 1
                        return None, url, f"fetch_error: {e}"

                    # Classify with Groq
                    try:
                        result = await parser.classify_html(profile_html, url)
                    except Exception as e:
                        skipped_count += 1
                        return None, url, f"llm_error: {e}"

                    if result is None:
                        skipped_count += 1
                        return None, url, "llm_no_output"

                    return result, url, "ok"

            # Process in batches so we can stream progress after each batch
            BATCH = req.concurrency
            for batch_start in range(0, total, BATCH):
                batch_urls = all_profile_urls[batch_start:batch_start + BATCH]
                batch_idx  = batch_start

                tasks = [
                    asyncio.create_task(classify_one(u, batch_idx + i))
                    for i, u in enumerate(batch_urls)
                ]
                results = await asyncio.gather(*tasks)

                for (result, url, status), local_i in zip(results, range(len(batch_urls))):
                    global_idx = batch_idx + local_i + 1
                    name = result.get("name", "") if result else ""

                    # Determine display status
                    if status == "duplicate":
                        display = "duplicate"
                    elif result and result.get("is_south_asian") and result.get("is_valid_role"):
                        display = "included"
                    elif result and result.get("is_south_asian"):
                        display = "not_faculty"
                    elif result:
                        display = "excluded"
                    else:
                        display = status

                    yield sse({
                        "type": "progress",
                        "index": global_idx,
                        "total": total,
                        "url": url,
                        "status": display,
                        "name": name,
                    })

                    # Auto-save qualifying profiles
                    if result and result.get("is_south_asian") and result.get("is_valid_role"):
                        record = dict(result)
                        record.setdefault("scraped_at", datetime.now().isoformat())
                        record.setdefault("source_page", req.url)
                        record.setdefault("country", "UK")

                        fresh_data = _load_data()
                        fresh_urls = {r.get("profile_link", "") for r in fresh_data}
                        if url not in fresh_urls:
                            fresh_data.append(record)
                            _save_data(fresh_data)
                            existing_urls.add(url)  # prevent re-save in same run
                            saved_count += 1

                            yield sse({
                                "type": "saved",
                                "name": record.get("name"),
                                "university": record.get("university"),
                                "origin": record.get("origin"),
                                "total_saved": saved_count,
                            })
                        else:
                            skipped_count += 1
                    else:
                        if status not in ("duplicate",):
                            skipped_count += 1

            yield sse({
                "type": "done",
                "pages_crawled": page_num,
                "profiles_found": total,
                "saved": saved_count,
                "skipped": skipped_count,
            })
            logger.info(f"Directory scrape done | pages={page_num} profiles={total} saved={saved_count}")

        except Exception as e:
            logger.error(f"scrape_directory error: {e}", exc_info=True)
            yield sse({"type": "error", "message": str(e)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/save")
async def save(req: SaveRequest):
    """
    Append a confirmed record to cleaned_data.json.
    Deduplicates by profile_link before saving.
    """
    record = req.record
    if not record:
        raise HTTPException(status_code=400, detail="No record data provided.")

    # Load existing data
    data = _load_data()

    # Deduplication check
    existing_urls = {r.get("profile_link", "") for r in data}
    profile_link = record.get("profile_link", "")
    if profile_link and profile_link in existing_urls:
        return {
            "status": "duplicate",
            "message": f"Record for '{profile_link}' already exists in the dataset.",
            "total": len(data),
        }

    # Stamp metadata
    record.setdefault("scraped_at", datetime.now().isoformat())
    record.setdefault("source_page", "browser_extension")

    data.append(record)
    _save_data(data)

    logger.info(f"Saved: {record.get('name', '?')} | {profile_link} | total={len(data)}")
    return {"status": "saved", "name": record.get("name"), "total": len(data)}


@app.get("/records")
async def records():
    """Return total record count and the 5 most recently added records."""
    data = _load_data()
    return {
        "count": len(data),
        "recent": data[-5:][::-1] if data else [],  # Most recent first
    }


@app.get("/export")
async def export():
    """Trigger CSV + XLSX export using the existing FacultyExporter."""
    from exporter import FacultyExporter

    try:
        exporter = FacultyExporter(input_json=DATA_FILE, output_dir="output")
        exporter.export()
        return {
            "status": "exported",
            "output_dir": os.path.abspath("output"),
            "files": ["faculty_data.csv", "faculty_data.xlsx"],
        }
    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}") 


class FetchUrlRequest(BaseModel):
    url: str


@app.post("/fetch-url")
async def fetch_url(req: FetchUrlRequest):
    """
    Server-side URL fetcher / proxy used by the dashboard to retrieve faculty profile HTML.
    Avoids CORS issues since the server makes the request on behalf of the browser.
    """
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=15.0) as client:
            resp = await client.get(req.url)
            resp.raise_for_status()
            return {"html": resp.text, "url": str(resp.url), "status": resp.status_code}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch URL: {str(e)}")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Serve the Faculty Intelligence web dashboard."""
    dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
    if os.path.exists(dashboard_path):
        with open(dashboard_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    # Fallback minimal page if dashboard.html not found
    return HTMLResponse(content="""<!DOCTYPE html>
<html><head><meta charset='UTF-8'><title>Faculty Intelligence</title>
<style>body{background:#080c12;color:#e2eaf4;font-family:Inter,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}
.box{text-align:center;}.icon{font-size:48px;margin-bottom:16px;}.title{font-size:24px;font-weight:700;margin-bottom:8px;}
.sub{color:#7a90aa;font-size:14px;}</style></head>
<body><div class='box'><div class='icon'>🎓</div><div class='title'>Faculty Intelligence</div>
<div class='sub'>dashboard.html not found. Place it in your project root and restart server.py.</div></div></body></html>""")




def _load_data() -> list:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def _save_data(data: list) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def _get_record_count() -> int:
    data = _load_data()
    return len(data)


def _is_likely_profile_link(url: str, base_url: str) -> bool:
    """Heuristic to decide if a link is an individual faculty profile page."""
    try:
        parsed = urlparse(url)
        parsed_base = urlparse(base_url)
        if parsed.netloc and parsed.netloc != parsed_base.netloc:
            return False
        path = parsed.path.lower()
        parts = [p for p in path.split("/") if p]
        if not parts:
            return False

        # Expanded keyword list covering Harvard /person/, MIT /bio/, etc.
        PROFILE_KEYWORDS = {
            "people", "profile", "profiles", "staff", "faculty", "expert", "experts",
            "member", "members", "academics", "researchers", "researcher",
            "person",        # Harvard SEAS: /person/<name>
            "bio",           # MIT, Caltech: /bio/<name>
            "directory",     # Some UK universities
            "team",          # /team/<name>
            "our-team",
            "professors",
            "lecturer",
            "instructor",
        }
        BLACKLIST_SUFFIXES = {
            "index.html", "index.php", "index.htm",
            "search", "all", "list", "listing", "listings",
            "page", "filter", "results", "browse",
        }

        for kw in PROFILE_KEYWORDS:
            if kw in parts:
                idx = parts.index(kw)
                if idx < len(parts) - 1:
                    after_kw = parts[idx + 1]
                    if after_kw not in BLACKLIST_SUFFIXES:
                        return True

        # Also catch pattern where the keyword IS the last segment but there's a slug after it
        # e.g. /faculty/priya-nair  where faculty is parts[-2] and priya-nair is parts[-1]
        if len(parts) >= 2 and parts[-2] in PROFILE_KEYWORDS and parts[-1] not in BLACKLIST_SUFFIXES:
            return True

        return False
    except Exception:
        return False


def _extract_profile_links(html: str, page_url: str) -> list[str]:
    """Parse HTML and return deduplicated, heuristic-filtered profile URLs."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    links: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].split("#")[0].strip()
        if not href:
            continue
        abs_url = urljoin(page_url, href)
        if abs_url in seen:
            continue
        seen.add(abs_url)
        if _is_likely_profile_link(abs_url, page_url):
            links.append(abs_url)
    return links


def _find_next_page(html: str, base_url: str) -> str | None:
    """Detect the 'Next' pagination link from directory page HTML."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    # 1. rel="next" (SEO-standard)
    tag = soup.find("a", rel=lambda v: v and "next" in v)
    if tag and tag.get("href"):
        return urljoin(base_url, tag["href"])

    # 2. Class contains 'next'
    tag = soup.find("a", class_=re.compile(r"next", re.I))
    if tag and tag.get("href") and "prev" not in (tag.get("class") or [""])[0].lower():
        return urljoin(base_url, tag["href"])

    # 3. Link text is 'Next' / '>>' / '›'
    for a in soup.find_all("a", href=True):
        txt = a.get_text(strip=True).lower()
        if txt in ("next", "next page", "»", "›", ">", "next ›", "next »"):
            return urljoin(base_url, a["href"])

    # 4. aria-label="Next"
    tag = soup.find("a", attrs={"aria-label": re.compile(r"next", re.I)})
    if tag and tag.get("href"):
        return urljoin(base_url, tag["href"])

    return None


# ── Entry Point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("=" * 55)
    logger.info("  Faculty Intelligence Server  ")
    logger.info(f"  Model  : {DEFAULT_MODEL}")
    logger.info(f"  API Key: {'✓ Set' if groq_api_key else '✗ NOT SET — set GROQ_API_KEY in .env'}")
    logger.info(f"  URL    : http://{SERVER_HOST}:{SERVER_PORT}")
    logger.info("=" * 55)

    uvicorn.run(
        app,
        host=SERVER_HOST,
        port=SERVER_PORT,
        log_level="info",
    )
