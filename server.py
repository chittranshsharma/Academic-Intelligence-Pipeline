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
from fastapi.responses import StreamingResponse
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

# ── Parser Singleton ─────────────────────────────────────────────────────────
groq_api_key = os.environ.get("GROQ_API_KEY", "")
if not groq_api_key:
    logger.warning("⚠  GROQ_API_KEY not set in environment / .env file.")
    logger.warning("   Get a free key at: https://console.groq.com/keys")

_parser: Optional[FacultyParser] = None


def get_parser() -> FacultyParser:
    """Return (or lazily create) the shared FacultyParser instance."""
    global _parser
    if _parser is None:
        _parser = FacultyParser(
            model_name=DEFAULT_MODEL,
            groq_api_key=groq_api_key,
        )
    return _parser


# ── Request / Response Models ─────────────────────────────────────────────────
class ClassifyRequest(BaseModel):
    html: str
    url: str


class ScrapeDirectoryRequest(BaseModel):
    url: str                     # Starting directory URL
    max_pages: int = 100         # Max pagination pages to follow
    max_profiles: int = 1000     # Hard cap on profiles to process
    concurrency: int = 5         # Parallel Groq calls per batch


class SaveRequest(BaseModel):
    record: dict


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/status")
async def status():
    """Health check — extension polls this to show connection indicator."""
    return {
        "status": "running",
        "model": DEFAULT_MODEL,
        "api_key_set": bool(groq_api_key),
        "data_file": DATA_FILE,
        "record_count": _get_record_count(),
    }


@app.post("/classify")
async def classify(req: ClassifyRequest):
    """
    Classify a faculty profile page.
    Accepts: {html: str, url: str}
    Returns: structured profile dict with is_south_asian, is_valid_role, etc.
    """
    if not groq_api_key:
        raise HTTPException(
            status_code=503,
            detail="GROQ_API_KEY not configured. Add it to your .env file and restart the server.",
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
    if not groq_api_key:
        raise HTTPException(
            status_code=503,
            detail="GROQ_API_KEY not configured. Add it to your .env file and restart the server.",
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

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }

            async with httpx.AsyncClient(
                headers=headers, follow_redirects=True, timeout=20.0
            ) as client:

                while current_page_url and page_num < req.max_pages:
                    if current_page_url in visited_pages:
                        break
                    visited_pages.add(current_page_url)
                    page_num += 1

                    try:
                        resp = await client.get(current_page_url)
                        resp.raise_for_status()
                        html = resp.text
                    except Exception as e:
                        yield sse({"type": "error", "message": f"Failed to fetch page {page_num}: {e}"})
                        break

                    # Extract profile links from this directory page
                    page_profiles = _extract_profile_links(html, current_page_url)
                    new_profiles = [
                        u for u in page_profiles
                        if u not in all_profile_urls
                    ]
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
                        break  # End of pagination
                    current_page_url = next_url
                    await asyncio.sleep(0.3)  # Polite delay

            if not all_profile_urls:
                yield sse({"type": "error", "message": "No profile links found on this page. Make sure you're on a faculty directory page (not an individual profile)."})
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

                    # Fetch profile HTML
                    try:
                        async with httpx.AsyncClient(
                            headers=headers, follow_redirects=True, timeout=15.0
                        ) as c:
                            pr = await c.get(url)
                            pr.raise_for_status()
                            profile_html = pr.text
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


# ── Helpers ───────────────────────────────────────────────────────────────────

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
    """Mirror of crawler.py's heuristic — kept here so server has no import dep on crawler."""
    try:
        parsed = urlparse(url)
        parsed_base = urlparse(base_url)
        if parsed.netloc and parsed.netloc != parsed_base.netloc:
            return False
        path = parsed.path.lower()
        parts = [p for p in path.split("/") if p]
        if not parts:
            return False
        for kw in ["people", "profile", "staff", "faculty", "expert", "member", "academics", "researchers"]:
            if kw in parts:
                idx = parts.index(kw)
                if idx < len(parts) - 1:
                    after_kw = parts[idx + 1]
                    if after_kw not in ["index.html", "index.php", "search", "all", "list"]:
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
