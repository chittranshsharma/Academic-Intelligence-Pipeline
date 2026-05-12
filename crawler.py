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
    if parsed.netloc and parsed.netloc != parsed_base.netloc:
        return False
        
    path = parsed.path.lower()
    parts = [p for p in path.split('/') if p]
    if not parts:
        return False
        
    # Generic rule: must have a directory keyword, AND an identifier AFTER the keyword
    for kw in ['people', 'profile', 'staff', 'faculty', 'expert', 'member']:
        if kw in parts:
            idx = parts.index(kw)
            # The path must continue after the keyword (e.g. /staff/john-doe)
            if idx < len(parts) - 1:
                after_kw = parts[idx+1]
                # Filter out obvious non-profile directory paths
                if after_kw not in ['index.html', 'index.php', 'search', 'all']:
                    return True
    return False
