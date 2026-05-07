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
