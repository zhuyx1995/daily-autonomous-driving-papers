#!/usr/bin/env python3
import hashlib
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

query = sys.argv[1] if len(sys.argv) > 1 else "autonomous driving arXiv"
headers = {
    "User-Agent": "daily-autonomous-driving-papers/1.2 (contact: local-bot)",
    "Accept": "application/atom+xml,text/html;q=0.9,*/*;q=0.8",
}

# arXiv API etiquette recommends spacing requests by ~3 seconds.
REQUEST_GAP_SECONDS = 3.5
CACHE_MAX_AGE_SECONDS = 36 * 3600
CACHE_DIR = Path("/Users/zhuyuxiao/.openclaw/workspace/tmp/arxiv_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_path(q: str) -> Path:
    h = hashlib.sha1(q.encode("utf-8")).hexdigest()[:16]
    return CACHE_DIR / f"{h}.txt"


def _load_cache(q: str) -> str:
    p = _cache_path(q)
    if not p.exists():
        return ""
    age = time.time() - p.stat().st_mtime
    if age > CACHE_MAX_AGE_SECONDS:
        return ""
    data = p.read_text(encoding="utf-8", errors="replace")
    if data.strip():
        print(f"[WARN] using cached arXiv search result (age={age/3600:.1f}h)", file=sys.stderr)
    return data


def _save_cache(q: str, data: str) -> None:
    if data.strip():
        _cache_path(q).write_text(data, encoding="utf-8")


def _exp_backoff(attempt: int, base: float = 2.0, jitter: float = 0.8) -> float:
    """attempt starts from 1"""
    return base ** (attempt - 1) + random.uniform(0, jitter)


def _retry_after_seconds(err: urllib.error.HTTPError):
    try:
        ra = err.headers.get("Retry-After")
        if ra is None:
            return None
        return max(float(ra), REQUEST_GAP_SECONDS)
    except Exception:
        return None


def fetch_with_retry(url: str, timeout: int, max_attempts: int, label: str) -> str:
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            last_error = e
            if e.code in (429, 500, 502, 503, 504) and attempt < max_attempts:
                retry_after = _retry_after_seconds(e)
                wait_s = retry_after if retry_after is not None else max(REQUEST_GAP_SECONDS, _exp_backoff(attempt))
                print(
                    f"[WARN] {label} HTTP {e.code}, retry {attempt}/{max_attempts} after {wait_s:.1f}s",
                    file=sys.stderr,
                )
                time.sleep(wait_s)
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            last_error = e
            if attempt < max_attempts:
                wait_s = max(REQUEST_GAP_SECONDS, _exp_backoff(attempt))
                print(
                    f"[WARN] {label} network timeout/error, retry {attempt}/{max_attempts} after {wait_s:.1f}s",
                    file=sys.stderr,
                )
                time.sleep(wait_s)
                continue
            raise
        except Exception as e:
            last_error = e
            if attempt < max_attempts:
                wait_s = max(REQUEST_GAP_SECONDS, _exp_backoff(attempt))
                print(
                    f"[WARN] {label} unexpected error, retry {attempt}/{max_attempts} after {wait_s:.1f}s",
                    file=sys.stderr,
                )
                time.sleep(wait_s)
                continue
            raise

    raise RuntimeError(f"{label} failed after retries: {last_error}")


api_url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(
    {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": 30,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
)

web_url = "https://arxiv.org/search/?" + urllib.parse.urlencode(
    {
        "query": query,
        "searchtype": "all",
        "abstracts": "show",
        "order": "-announced_date_first",
        "size": 50,
    }
)

try:
    data = fetch_with_retry(api_url, timeout=30, max_attempts=4, label="arXiv API")
    _save_cache(query, data)
except Exception as api_err:
    print(f"[WARN] arXiv API failed after retries: {api_err}", file=sys.stderr)
    time.sleep(REQUEST_GAP_SECONDS)
    try:
        data = fetch_with_retry(web_url, timeout=30, max_attempts=3, label="arXiv Web")
        _save_cache(query, data)
    except Exception as web_err:
        print(f"[WARN] arXiv Web failed after retries: {web_err}", file=sys.stderr)
        cached = _load_cache(query)
        if cached:
            data = cached
        else:
            raise

print(data)
