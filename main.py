import asyncio
import logging
import os
import argparse
from crawler import FacultyCrawler
from parser import FacultyParser
from exporter import FacultyExporter

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
    parser = argparse.ArgumentParser(description="University Faculty Scraper")
    parser.add_argument("--urls", nargs="+", help="List of directory URLs to scrape", default=["https://example.com/staff"])
    parser.add_argument("--file", help="Text file containing URLs (one per line)")
    parser.add_argument("--max-pages", type=int, default=100, help="Maximum number of directory pages to crawl")
    parser.add_argument("--max-profiles", type=int, default=1000, help="Maximum number of profiles to scrape")
    parser.add_argument("--concurrency", type=int, default=10, help="Number of concurrent profile downloads using HTTPX")
    parser.add_argument("--use-playwright-profiles", action="store_true", help="Use Playwright to download profile pages instead of fast HTTPX")
    
    args = parser.parse_args()
    
    directory_urls = []
    if args.file and os.path.exists(args.file):
        with open(args.file, 'r', encoding='utf-8') as f:
            directory_urls = [line.strip() for line in f if line.strip()]
    elif args.urls:
        directory_urls = args.urls
        
    if not directory_urls:
        logger.error("No URLs provided to crawl.")
        return

    logger.info("=========================================")
    logger.info("   Starting Faculty Extraction Pipeline   ")
    logger.info("=========================================")
    
    # 1. Crawl
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
    
    # 2. Parse
    logger.info("--- PHASE 2: PARSING & FILTERING ---")
    fparser = FacultyParser(input_json="raw_data.json", output_json="cleaned_data.json", screenshots_dir="screenshots")
    await fparser.process()
    
    # 3. Export
    logger.info("--- PHASE 3: EXPORTING ---")
    exporter = FacultyExporter(input_json="cleaned_data.json", output_dir="output")
    exporter.export()
    
