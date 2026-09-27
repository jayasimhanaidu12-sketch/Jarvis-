"""
news_agent.py  –  Daily AI News Agent integrated into JARVIS
=============================================================
Cloned logic from: https://github.com/jayasimhanaidu12-sketch/daily-ai-news-agent

Pipeline:
  RSS Feeds → Fetch → Deduplicate → Filter → Rank → Return top-N headlines
"""

import re
import feedparser
import requests
from datetime import datetime, timezone, timedelta
from time import mktime
from difflib import SequenceMatcher
from typing import List, Optional
from dataclasses import dataclass, field

# ── RSS Feed Sources (same 10 as the repo) ──────────────────────────────────
RSS_FEEDS = [
    {"name": "TechCrunch - AI",         "url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
    {"name": "The Verge - Tech",         "url": "https://www.theverge.com/rss/index.xml"},
    {"name": "Ars Technica",             "url": "https://feeds.arstechnica.com/arstechnica/technology-lab"},
    {"name": "Wired - AI",               "url": "https://www.wired.com/feed/tag/ai/latest/rss"},
    {"name": "VentureBeat",              "url": "https://venturebeat.com/feed/"},
    {"name": "MIT Tech Review",          "url": "https://www.technologyreview.com/feed/"},
    {"name": "Google AI Blog",           "url": "https://blog.google/technology/ai/rss/"},
    {"name": "OpenAI Blog",              "url": "https://openai.com/blog/rss.xml"},
    {"name": "NVIDIA Blog",              "url": "https://blogs.nvidia.com/feed/"},
    {"name": "Hacker News",              "url": "https://news.ycombinator.com/rss"},
]

MAX_ARTICLES_PER_FEED = 20
TARGET_STORY_COUNT    = 10
NEWS_LOOKBACK_HOURS   = 48

RELEVANCE_KEYWORDS = [
    "artificial intelligence", "machine learning", "deep learning",
    "neural network", "large language model", "llm", "generative ai",
    "chatgpt", "gpt", "gemini", "claude", "mistral", "llama",
    "openai", "google deepmind", "anthropic", "meta ai",
    "robotics", "autonomous", "computer vision", "natural language",
    "transformer", "diffusion model", "stable diffusion",
    "ai regulation", "ai safety", "alignment",
    "nvidia", "gpu", "tpu", "chip", "semiconductor",
    "tech", "startup", "funding", "venture capital",
]

TITLE_POWER_WORDS = [
    "launch", "launches", "launched", "announce", "announces", "announced",
    "release", "releases", "released", "reveal", "reveals", "revealed",
    "introduce", "introduces", "introduced", "unveil", "unveils", "unveiled",
    "breakthrough", "new", "first", "major", "biggest",
    "raises", "funding", "acquisition", "acquires",
    "open-source", "open source", "partnership",
    "ban", "regulation", "record", "surpass", "milestone",
]

SOURCE_QUALITY = {
    "Google AI Blog": 3, "OpenAI Blog": 3, "MIT Tech Review": 3,
    "TechCrunch - AI": 2, "Wired - AI": 2, "VentureBeat": 2, "NVIDIA Blog": 2, "Ars Technica": 2,
    "The Verge - Tech": 1, "Hacker News": 1,
}

# ── Data model ───────────────────────────────────────────────────────────────
@dataclass
class Article:
    title:     str
    url:       str
    summary:   str
    source:    str
    published: Optional[datetime] = None
    score:     float = 0.0

# ── Stage 1: Fetch ───────────────────────────────────────────────────────────
def _parse_date(entry) -> Optional[datetime]:
    ds = entry.get("published_parsed") or entry.get("updated_parsed")
    if ds:
        return datetime.fromtimestamp(mktime(ds), tz=timezone.utc)
    return None

def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()

def fetch_news() -> List[Article]:
    articles = []
    for feed in RSS_FEEDS:
        try:
            parsed = feedparser.parse(feed["url"])
            for entry in parsed.entries[:MAX_ARTICLES_PER_FEED]:
                title   = _strip_html(entry.get("title", "")).strip()
                url     = entry.get("link", "")
                summary = _strip_html(
                    entry.get("summary", "") or entry.get("description", "")
                )[:400]
                published = _parse_date(entry)
                if title and url:
                    articles.append(Article(
                        title=title, url=url, summary=summary,
                        source=feed["name"], published=published
                    ))
        except Exception as e:
            print(f"  [NEWS] Feed failed ({feed['name']}): {e}")
    print(f"  [NEWS] Fetched {len(articles)} raw articles from {len(RSS_FEEDS)} feeds.")
    return articles

# ── Stage 2: Deduplicate & filter ────────────────────────────────────────────
def _normalize_url(url: str) -> str:
    url = url.lower().strip()
    url = re.sub(r"^https?://", "", url)
    url = re.sub(r"^www\.", "", url)
    url = url.rstrip("/")
    url = re.sub(r"\?.*$", "", url)
    return url

def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", title.lower().strip()))

def _similar(a: str, b: str, threshold=0.75) -> bool:
    return SequenceMatcher(None, a, b).ratio() >= threshold

def deduplicate(articles: List[Article]) -> List[Article]:
    seen_urls:   set = set()
    seen_titles: List[str] = []
    unique = []
    for art in articles:
        norm_url   = _normalize_url(art.url)
        norm_title = _normalize_title(art.title)
        if norm_url in seen_urls:
            continue
        if any(_similar(norm_title, t) for t in seen_titles):
            continue
        seen_urls.add(norm_url)
        seen_titles.append(norm_title)
        unique.append(art)
    return unique

def is_relevant(article: Article) -> bool:
    text = (article.title + " " + article.summary).lower()
    return any(kw in text for kw in RELEVANCE_KEYWORDS)

def is_recent(article: Article, hours: int = NEWS_LOOKBACK_HOURS) -> bool:
    if article.published is None:
        return True  # No date → assume recent
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
    return article.published >= cutoff

# ── Stage 3: Rank ────────────────────────────────────────────────────────────
def score_article(article: Article) -> float:
    text  = (article.title + " " + article.summary).lower()
    score = 0.0

    # Keyword relevance (max 40)
    hits = sum(1 for kw in RELEVANCE_KEYWORDS if kw in text)
    score += min(hits * 5, 40)

    # Recency (max 25)
    if article.published:
        age_hours = (datetime.now(tz=timezone.utc) - article.published).total_seconds() / 3600
        score += max(0, 25 - age_hours * 0.5)

    # Source quality (max 20)
    tier = SOURCE_QUALITY.get(article.source, 0)
    score += {3: 20, 2: 14, 1: 8, 0: 3}.get(tier, 3)

    # Title power words (max 15)
    title_lower = article.title.lower()
    power_hits  = sum(1 for w in TITLE_POWER_WORDS if w in title_lower)
    score += min(power_hits * 5, 15)

    return score

# ── Public API ────────────────────────────────────────────────────────────────
def get_top_ai_news(count: int = TARGET_STORY_COUNT) -> List[Article]:
    """
    Full pipeline: fetch → deduplicate → filter → rank → return top N.
    This is what JARVIS calls.
    """
    raw      = fetch_news()
    unique   = deduplicate(raw)
    relevant = [a for a in unique if is_relevant(a) and is_recent(a)]
    for a in relevant:
        a.score = score_article(a)
    ranked = sorted(relevant, key=lambda a: a.score, reverse=True)
    print(f"  [NEWS] {len(raw)} raw -> {len(unique)} unique -> {len(relevant)} relevant -> top {min(count, len(ranked))} returned.")
    return ranked[:count]

def format_news_for_speech(articles: List[Article], max_items: int = 5) -> str:
    """
    Convert top articles to a concise spoken briefing string.
    """
    if not articles:
        return "I could not retrieve any AI news at the moment, sir."
    lines = [f"Here are the top {min(max_items, len(articles))} AI and tech stories, sir."]
    for i, art in enumerate(articles[:max_items], 1):
        lines.append(f"Story {i}: {art.title}. Source: {art.source}.")
    return " ".join(lines)

def format_news_for_display(articles: List[Article], max_items: int = 10) -> list:
    """Return a list of dicts for the frontend news panel."""
    return [
        {"title": a.title, "source": a.source, "url": a.url,
         "summary": a.summary[:200], "score": round(a.score, 1)}
        for a in articles[:max_items]
    ]
