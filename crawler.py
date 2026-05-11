import asyncio
import json
import logging
import os
import re
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import httpx
from datetime import datetime

logger = logging.getLogger(__name__)

def is_likely_profile_link(url, base_url):
    """
    Smart heuristic to determine if a URL is likely an individual faculty profile
    rather than a general site link (about, courses, help, terms, etc.)
    """
    parsed = urlparse(url)
    parsed_base = urlparse(base_url)
