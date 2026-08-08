import asyncio
import logging
import os
import argparse
from dotenv import load_dotenv
from crawler import FacultyCrawler
from parser import FacultyParser
from exporter import FacultyExporter

load_dotenv()

def setup_logging():
    os.makedirs("logs", exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("logs/scraper.log"),
            logging.StreamHandler()
        ]
    )

async def main():
    setup_logging()
    logger = logging.getLogger("main")

    # Parse args
    parser = argparse.ArgumentParser(description="University Faculty Scraper — powered by Groq API")
    parser.add_argument("--urls", nargs="+", help="List of directory URLs to scrape")
    parser.add_argument("--file", help="Text file containing URLs (one per line)")
    parser.add_argument("--max-pages", type=int, default=100, help="Maximum number of directory pages to crawl per URL")
    parser.add_argument("--max-profiles", type=int, default=1000, help="Maximum number of profiles to scrape")
    parser.add_argument("--concurrency", type=int, default=10, help="Number of concurrent profile downloads (HTTPX)")
    parser.add_argument("--use-playwright-profiles", action="store_true", help="Use Playwright (slower, more robust) for profile downloads")
    parser.add_argument("--model", default="llama-3.3-70b-versatile", help="Groq model ID (default: llama-3.3-70b-versatile)")
    parser.add_argument("--groq-api-key", default=None, help="Groq API key (overrides GROQ_API_KEY env var)")

    args = parser.parse_args()

    # Resolve API key: CLI > env var
    groq_api_key = args.groq_api_key or os.environ.get("GROQ_API_KEY", "")
    if not groq_api_key:
        logger.error("No Groq API key found. Set GROQ_API_KEY in your .env file or pass --groq-api-key.")
        logger.error("Get a free key at: https://console.groq.com/keys")
        return

    # Resolve input URLs
    directory_urls = []
    if args.file and os.path.exists(args.file):
        with open(args.file, 'r', encoding='utf-8') as f:
            directory_urls = [line.strip() for line in f if line.strip()]
    elif args.urls:
        directory_urls = args.urls

    if not directory_urls:
        logger.error("No URLs provided. Use --urls or --file.")
        return

    logger.info("=========================================")
    logger.info("   Starting Faculty Extraction Pipeline   ")
    logger.info(f"   Backend : Groq API                    ")
    logger.info(f"   Model   : {args.model}                ")
    logger.info(f"   URLs    : {len(directory_urls)} source(s)")
    logger.info("=========================================")

    # ── Phase 1: Crawl ──
    logger.info("--- PHASE 1: CRAWLING ---")
    crawler = FacultyCrawler(
        raw_html_dir="raw_html",
        output_json="raw_data.json",
        max_pages=args.max_pages,
        max_profiles=args.max_profiles,
        concurrency=args.concurrency,
        use_playwright_profiles=args.use_playwright_profiles
    )
    await crawler.crawl_directories(directory_urls)

    # ── Phase 2: Parse + Classify ──
    logger.info("--- PHASE 2: PARSING & FILTERING (Groq AI) ---")
    fparser = FacultyParser(
        input_json="raw_data.json",
        output_json="cleaned_data.json",
        screenshots_dir="screenshots",
        model_name=args.model,
        groq_api_key=groq_api_key
    )
    await fparser.process()

    # ── Phase 3: Export ──
    logger.info("--- PHASE 3: EXPORTING ---")
    exporter = FacultyExporter(input_json="cleaned_data.json", output_dir="output")
    exporter.export()

    logger.info("Pipeline finished successfully.")

if __name__ == "__main__":
    asyncio.run(main())
