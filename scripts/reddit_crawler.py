#!/usr/bin/env python3
"""
Reddit Adaptive Crawler v1.0
============================
다중 전략 Reddit 크롤러 — Reddit의 anti-automation을 우회하며 데이터를 수집.

전략 (우선순위 순):
  1. Reddit RSS (r/all) — 가장 안정적
  2. 개별 서브레딧 RSS — 지연 포함
  3. Reddit JSON API (old.reddit.com) — 간헐적 동작
  4. web_search 백업 — 다른 소스에서 Reddit 콘텐츠 검색

특징:
  - 전략별 health check + 자동 failover
  - 429/403 시 백오프 및 전략 전환
  - User-Agent 로테이션
  - 결과 캐싱 (중복 요청 방지)
  - 통일된 JSON 출력 형식

Usage:
  python3 reddit_crawler.py --mode all --limit 10
  python3 reddit_crawler.py --mode ai --limit 10
  python3 reddit_crawler.py --mode both --limit 10
"""

import argparse
import hashlib
import json
import random
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

# ─── 설정 ────────────────────────────────────────────
CACHE_DIR = Path("/tmp/reddit_crawler_cache")
CACHE_TTL = 300  # 5분 캐시

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
]

AI_SUBREDDITS = [
    "artificial",
    "MachineLearning",
    "ChatGPT",
    "LocalLLaMA",
    "singularity",
    "AIgateway",
    "StableDiffusion",
    "ZAI",
]

# AI 관련 키워드 (r/all에서 필터링용)
AI_KEYWORDS = [
    "ai", "gpt", "llm", "machine learning", "deep learning", "neural",
    "zai", "anthropic", "claude", "gemini", "diffusion", "transformer",
    "chatbot", "chatgpt", "copilot", "midjourney", "stable diffusion",
    "llama", "mistral", "grok", "agi", "generative", "huggingface",
    "rag", "fine-tun", "prompt", "token", "inference", "embedding",
]

ATOM_NS = "{http://www.w3.org/2005/Atom}"

# ─── 유틸 ────────────────────────────────────────────
def get_ua():
    return random.choice(USER_AGENTS)

def cache_key(url):
    return hashlib.md5(url.encode()).hexdigest()

def cache_get(url):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = cache_key(url)
    path = CACHE_DIR / f"{key}.dat"
    if path.exists():
        age = time.time() - path.stat().st_mtime
        if age < CACHE_TTL:
            return path.read_bytes()
    return None

def cache_set(url, data):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = cache_key(url)
    path = CACHE_DIR / f"{key}.dat"
    path.write_bytes(data)

def fetch_url(url, timeout=10, use_cache=True):
    """기본 HTTP fetch (캐시 + UA 로테이션)"""
    if use_cache:
        cached = cache_get(url)
        if cached:
            return cached, "cache"

    req = Request(url, headers={
        "User-Agent": get_ua(),
        "Accept": "application/json, application/xml, text/xml, */*",
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        if use_cache:
            cache_set(url, data)
        return data, resp.status

# ─── 전략 1: Reddit RSS ──────────────────────────────
def fetch_rss_feed(url, timeout=10):
    """RSS 피드를 가져와 파싱"""
    try:
        data, status = fetch_url(url, timeout=timeout)
        if not data:
            return [], "empty"

        root = ET.fromstring(data)
        entries = root.findall(f"{ATOM_NS}entry")
        results = []

        for entry in entries:
            title_el = entry.find(f"{ATOM_NS}title")
            link_el = entry.find(f"{ATOM_NS}link")
            cat_el = entry.find(f"{ATOM_NS}category")
            author_el = entry.find(f"{ATOM_NS}author")
            updated_el = entry.find(f"{ATOM_NS}updated")

            title = title_el.text if title_el is not None else "Unknown"
            link = link_el.get("href") if link_el is not None else ""
            subreddit = cat_el.get("term") if cat_el is not None else "unknown"
            author = ""
            if author_el is not None:
                name_el = author_el.find(f"{ATOM_NS}name")
                if name_el is not None:
                    author = name_el.text or ""
            updated = updated_el.text if updated_el is not None else ""

            # 링크에서 게시물 ID 추출
            post_id = entry.find(f"{ATOM_NS}id")
            post_id = post_id.text if post_id is not None else ""

            results.append({
                "title": title,
                "subreddit": subreddit,
                "link": link,
                "author": author,
                "updated": updated,
                "id": post_id,
                "upvotes": None,  # RSS에는 upvote 정보 없음
            })

        return results, "rss_ok"
    except HTTPError as e:
        return [], f"http_{e.code}"
    except Exception as e:
        return [], f"error:{type(e).__name__}"

def strategy_rss_all(limit=25):
    """r/all RSS에서 가져오기"""
    url = f"https://www.reddit.com/r/all/hot.rss?limit={limit}"
    posts, status = fetch_rss_feed(url)
    if posts:
        return posts, "rss_all"
    return [], status

def strategy_rss_subreddit(subreddit, limit=10, delay=3):
    """개별 서브레딧 RSS (지연 포함)"""
    time.sleep(delay)
    url = f"https://www.reddit.com/r/{subreddit}/hot.rss?limit={limit}"
    posts, status = fetch_rss_feed(url)
    if posts:
        for p in posts:
            p["subreddit"] = subreddit
        return posts, f"rss_{subreddit}"
    return [], status

def strategy_rss_multi(subreddits, limit=5, max_time=30):
    """여러 서브레딧을 순회하며 RSS 수집 (시간 제한 포함)"""
    all_posts = []
    used_strategy = "rss_multi"
    success_count = 0
    start = time.time()

    for i, sub in enumerate(subreddits):
        # 시간 초과 시 조기 종료
        if time.time() - start > max_time:
            break
        if i > 0:
            delay = random.uniform(2, 4)
            time.sleep(delay)

        posts, status = strategy_rss_subreddit(sub, limit=limit, delay=0)
        if posts:
            all_posts.extend(posts)
            success_count += 1
        elif "429" in status:
            # 연속 429이면 포기
            if not all_posts:
                break

    return all_posts, f"{used_strategy}({success_count}/{len(subreddits)})"

# ─── 전략 2: JSON API (간헐적) ───────────────────────
def strategy_json_api(subreddit="all", limit=25):
    """old.reddit.com JSON API 시도"""
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
    try:
        data, status = fetch_url(url, timeout=10, use_cache=True)
        if not data or status == "cache":
            if isinstance(data, bytes) and len(data) > 100:
                pass
            elif data:
                return [], "json_short"

        obj = json.loads(data)
        children = obj.get("data", {}).get("children", [])
        results = []
        for child in children:
            d = child.get("data", {})
            results.append({
                "title": d.get("title", ""),
                "subreddit": d.get("subreddit", "unknown"),
                "link": f"https://www.reddit.com{d.get('permalink', '')}",
                "author": d.get("author", ""),
                "updated": "",
                "id": d.get("name", ""),
                "upvotes": d.get("ups", 0),
                "num_comments": d.get("num_comments", 0),
            })
        return results, "json_api"
    except HTTPError as e:
        return [], f"json_http_{e.code}"
    except Exception:
        return [], "json_error"

# ─── 전략 3: 검색 기반 백업 ──────────────────────────
def strategy_search_fallback():
    """다른 수단이 모두 실패 시 빈 결과 반환 (크론잡에서 web_search 사용 유도)"""
    return [], "search_fallback"

# ─── 필터링 & 랭킹 ──────────────────────────────────
def is_ai_related(post):
    """AI 관련 게시물인지 키워드 기반 판별 (word boundary 매칭)"""
    text = (post.get("title", "") + " " + post.get("subreddit", "")).lower()
    # 서브레딧명 직접 매치
    if post.get("subreddit", "") in AI_SUBREDDITS:
        return True
    # 단어 경계 매칭 (regex)
    for kw in AI_KEYWORDS:
        if re.search(rf'\b{re.escape(kw)}\b', text):
            return True
    return False

def deduplicate(posts):
    """ID/링크 기반 중복 제거"""
    seen = set()
    unique = []
    for p in posts:
        key = p.get("id") or p.get("link") or p.get("title")
        if key and key not in seen:
            seen.add(key)
            unique.append(p)
    return unique

# ─── 메인 오케스트레이터 ─────────────────────────────
def crawl_all(limit=25):
    """r/all에서 핫 게시물 수집 (다중 전략)"""
    strategies = [
        ("rss_all", lambda: strategy_rss_all(limit=limit)),
        ("json_api", lambda: strategy_json_api("all", limit=limit)),
    ]

    for name, fn in strategies:
        posts, strategy = fn()
        if posts:
            posts = deduplicate(posts)[:limit]
            for p in posts:
                p["source_strategy"] = strategy
            return posts, strategy

    return [], "all_failed"

def crawl_ai(limit=10):
    """AI 관련 서브레딧에서 수집 (다중 전략)"""
    strategies = [
        # 1차: r/all에서 AI 키워드+서브레딧 필터링 (가장 빠르고 신뢰성 높음)
        ("rss_all_filter", lambda: _ai_from_all(limit)),
        # 2차: 개별 서브레딧 RSS (지연 포함, 느림)
        ("rss_multi", lambda: strategy_rss_multi(AI_SUBREDDITS[:4], limit=limit)),
        # 3차: JSON API 시도
        ("json_api_multi", lambda: _try_json_multi(AI_SUBREDDITS[:4], limit=limit)),
    ]

    for name, fn in strategies:
        posts, strategy = fn()
        if posts:
            posts = deduplicate(posts)[:limit]
            for p in posts:
                p["source_strategy"] = strategy
            return posts, strategy

    return [], "ai_failed"

def _try_json_multi(subreddits, limit=5):
    """JSON API로 여러 서브레딧 시도"""
    all_posts = []
    success = 0
    for i, sub in enumerate(subreddits):
        if i > 0:
            time.sleep(random.uniform(1, 3))
        posts, status = strategy_json_api(sub, limit=limit)
        if posts:
            all_posts.extend(posts)
            success += 1
    if all_posts:
        return all_posts, f"json_multi({success}/{len(subreddits)})"
    return [], "json_multi_failed"

def _ai_from_all(limit=25):
    """r/all에서 AI 키워드 + AI 서브레딧 필터링 (확장, word boundary)"""
    # r/all에서 대량 수집
    posts, strategy = strategy_rss_all(limit=100)
    if not posts:
        return [], strategy

    # AI 키워드 매치 + AI 서브레딧 매치 (채점 시스템)
    scored = []
    for p in posts:
        score = 0
        title_lower = p.get("title", "").lower()
        sub = p.get("subreddit", "")

        # AI 서브레딧이면 높은 점수
        if sub in AI_SUBREDDITS:
            score += 10
        # AI 키워드 매치 (word boundary)
        for kw in AI_KEYWORDS:
            if re.search(rf'\b{re.escape(kw)}\b', title_lower):
                score += 2
            if re.search(rf'\b{re.escape(kw)}\b', sub.lower()):
                score += 3

        if score > 0:
            p["_score"] = score
            scored.append(p)

    # 점수순 정렬 후 상위 limit 개 반환
    scored.sort(key=lambda x: x.get("_score", 0), reverse=True)
    result = scored[:limit]
    for p in result:
        del p["_score"]

    return result, f"ai_filtered_from_{strategy}({len(scored)}cands)"

# ─── 출력 ────────────────────────────────────────────
def format_output(all_posts, ai_posts, strategy_all, strategy_ai):
    """통일된 JSON 출력"""
    output = {
        "timestamp": datetime.now(UTC).isoformat(),
        "seoul_time": datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M KST"),
        "strategies_used": {
            "all": strategy_all,
            "ai": strategy_ai,
        },
        "all_top": [
            {
                "title": p.get("title", ""),
                "subreddit": p.get("subreddit", ""),
                "link": p.get("link", ""),
                "upvotes": p.get("upvotes"),
                "source": p.get("source_strategy", ""),
            }
            for p in all_posts
        ],
        "ai_top": [
            {
                "title": p.get("title", ""),
                "subreddit": p.get("subreddit", ""),
                "link": p.get("link", ""),
                "upvotes": p.get("upvotes"),
                "source": p.get("source_strategy", ""),
            }
            for p in ai_posts
        ],
        "stats": {
            "all_count": len(all_posts),
            "ai_count": len(ai_posts),
        },
    }
    return output

# ─── CLI ────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Reddit Adaptive Crawler")
    parser.add_argument("--mode", choices=["all", "ai", "both"], default="both",
                        help="수집 모드 (기본: both)")
    parser.add_argument("--limit", type=int, default=10,
                        help="카테고리당 게시물 수 (기본: 10)")
    parser.add_argument("--output", choices=["json", "summary"], default="json",
                        help="출력 형식 (기본: json)")
    args = parser.parse_args()

    all_posts, ai_posts = [], []
    strategy_all, strategy_ai = "skip", "skip"

    if args.mode in ("all", "both"):
        print(f"[*] r/all 수집 중... (limit={args.limit})", file=sys.stderr)
        all_posts, strategy_all = crawl_all(limit=args.limit)
        print(f"    → {len(all_posts)}건 수집 ({strategy_all})", file=sys.stderr)

    if args.mode in ("ai", "both"):
        print(f"[*] AI 서브레딧 수집 중... (limit={args.limit})", file=sys.stderr)
        ai_posts, strategy_ai = crawl_ai(limit=args.limit)
        print(f"    → {len(ai_posts)}건 수집 ({strategy_ai})", file=sys.stderr)

    if args.output == "json":
        result = format_output(all_posts, ai_posts, strategy_all, strategy_ai)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"📡 Reddit Crawler Report — {datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M KST')}")
        print(f"{'='*60}")
        print(f"전략: all={strategy_all}, ai={strategy_ai}")
        print(f"\n📌 전체 Top {len(all_posts)}:")
        for i, p in enumerate(all_posts, 1):
            up = f" ⬆️{p['upvotes']}" if p.get("upvotes") else ""
            print(f"  {i}. [{p.get('subreddit','?')}] {p.get('title','?')[:70]}{up}")
        print(f"\n🤖 AI Top {len(ai_posts)}:")
        for i, p in enumerate(ai_posts, 1):
            up = f" ⬆️{p['upvotes']}" if p.get("upvotes") else ""
            print(f"  {i}. [{p.get('subreddit','?')}] {p.get('title','?')[:70]}{up}")

if __name__ == "__main__":
    main()
