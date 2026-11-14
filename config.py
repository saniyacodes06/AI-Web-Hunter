"""Central configuration for AI Web Signal Hunter.

Everything that can be tweaked (paths, domains, limits, AI models) lives here so
the other modules stay small and easy to explain.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Load .env once. This only reads the file; it never writes to it.
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
EXPORTS_DIR = BASE_DIR / "exports"
BASELINE_DIR = DATA_DIR / "baselines"
DB_PATH = DATA_DIR / "signals.db"

DATA_DIR.mkdir(parents=True, exist_ok=True)
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
BASELINE_DIR.mkdir(parents=True, exist_ok=True)

APP_NAME = "AI Web Signal Hunter"

# The assignment permits three sources. They are configurable so the same
# application still works if your assignment lists different domains.
DEFAULT_PERMITTED_DOMAINS = ("techcrunch.com", "venturebeat.com", "theverge.com")

_env_domains = os.getenv("PERMITTED_DOMAINS", "")
if _env_domains.strip():
    PERMITTED_DOMAINS = tuple(
        domain.strip().lower().replace("www.", "")
        for domain in _env_domains.split(",")
        if domain.strip()
    )
else:
    PERMITTED_DOMAINS = DEFAULT_PERMITTED_DOMAINS

# RSS feeds are a reliable, public fallback when search engines block bots.
DOMAIN_FEEDS = {
    "techcrunch.com": [
        "https://techcrunch.com/feed/",
        "https://techcrunch.com/category/artificial-intelligence/feed/",
    ],
    "venturebeat.com": [
        "https://venturebeat.com/feed/",
        "https://venturebeat.com/category/ai/feed/",
    ],
    "theverge.com": [
        "https://www.theverge.com/rss/index.xml",
        "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    ],
}

# Crawl and search limits.
MIN_REQUIRED_PAGES = 25
DEFAULT_PAGE_LIMIT = 30
MAX_PAGE_LIMIT = 60
REQUEST_TIMEOUT_SECONDS = 20
CRAWL_DELAY_SECONDS = 0.4
MIN_CONTENT_CHARS = 250
MAX_CONTENT_CHARS = 9000
NEAR_DUPLICATE_THRESHOLD = 0.92
MIN_RELEVANCE_SCORE = 0.05

# AI configuration.
AI_PROVIDER = os.getenv("AI_PROVIDER", "groq").strip().lower()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()

# Batching keeps the scan fast: one API call analyses several pages at once.
AI_BATCH_SIZE = int(os.getenv("AI_BATCH_SIZE", "3"))
AI_PAGE_CHARS = int(os.getenv("AI_PAGE_CHARS", "4500"))
AI_MAX_OUTPUT_TOKENS = int(os.getenv("AI_MAX_OUTPUT_TOKENS", "4000"))

# Transparent opportunity ranking weights. They must add up to 1.0.
OPPORTUNITY_WEIGHTS = {
    "evidence_strength": 0.25,
    "confidence": 0.20,
    "source_diversity": 0.20,
    "recurrence": 0.15,
    "relevance": 0.10,
    "recency": 0.10,
}

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36 "
    "AIWebSignalHunter/1.0"
)
