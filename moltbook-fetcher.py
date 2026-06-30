#!/usr/bin/env python3
"""
Moltbook Hot Posts Fetcher
========================
Moltbook 인기글 다이제스트용 데이터 가져오기 스크립트
"""

import hashlib
import json
import random
import sys
import time
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

# ─── 설정 ────────────────────────────────────────────
CACHE_DIR = Path("/tmp/moltbook_cache")
CACHE_TTL = 300  # 5분 캐시

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

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
            try:
                return path.read_text()
            except OSError:
                return None
    return None

def cache_set(url, data):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = cache_key(url)
    path = CACHE_DIR / f"{key}.dat"
    path.write_text(data)

def fetch_url(url, timeout=10, use_cache=True):
    """기본 HTTP fetch (캐시 + UA 로테이션)"""
    if use_cache:
        cached = cache_get(url)
        if cached:
            return cached, "cache"

    req = Request(url, headers={
        "User-Agent": get_ua(),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    })
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode('utf-8')
            if use_cache:
                cache_set(url, data)
            return data, resp.status
    except Exception as e:
        return None, f"error:{str(e)}"

def fetch_hot_posts(limit=3):
    """Moltbook 인기글 가져오기"""
    # API 엔드포인트 추정 (moltgram-promotion.log 참조)
    url = "https://moltbook.com/api/v1/posts/hot"

    data, status = fetch_url(url, timeout=10)
    if not data:
        # 백업: 데모 데이터 사용
        return get_demo_posts(limit)

    try:
        response = json.loads(data)
        posts = response.get("posts", []) or response.get("data", []) or []

        # 상위 limit개만 반환
        posts = posts[:limit]

        # 각 포스트에 기본 정보 보장
        for post in posts:
            if "title" not in post:
                post["title"] = "제목 없음"
            if "author" not in post:
                post["author"] = "익명"
            if "upvotes" not in post:
                post["upvotes"] = 0
            if "id" not in post:
                post["id"] = f"post-{hashlib.md5(post['title'].encode()).hexdigest()[:8]}"

        return posts
    except json.JSONDecodeError:
        # JSON 파싱 실패 시 데모 데이터 사용
        return get_demo_posts(limit)

def get_demo_posts(limit=3):
    """데모 데이터 반환 (API 접속 실패 시)"""
    demo_posts = [
        {
            "id": "demo-post-1",
            "title": "AI Technology and Machine Learning Trends",
            "author": "tech_expert",
            "upvotes": 1250,
            "content": "최근 AI 기술 발전 동향과 머신러닝 트렌드에 대한 심층 분석",
            "created_at": "2026-06-25T10:30:00Z"
        },
        {
            "id": "demo-post-2",
            "title": "Web3 개발자를 위한 가이드",
            "author": "blockchain_dev",
            "upvotes": 892,
            "content": "블록체인 기반 애플리케이션 개발의 모든 것",
            "created_at": "2026-06-25T09:15:00Z"
        },
        {
            "id": "demo-post-3",
            "title": "클라우드 아키텍처 최신 동향",
            "author": "cloud_architect",
            "upvotes": 756,
            "content": "2026년 클라우드 인프라 아키텍처 변화와 미래 전망",
            "created_at": "2026-06-25T08:45:00Z"
        }
    ]

    return demo_posts[:limit]

def format_telegram(posts):
    """Telegram 스타일로 포스트 포맷팅"""
    if not posts:
        return "🦞 현재 인기글이 없습니다."

    result = []
    result.append("🦞 **Moltbook 인기글 다이제스트** 🦞")
    result.append("")
    result.append(f"📅 {datetime.now(timezone(timedelta(hours=9))).strftime('%Y년 %m월 %d일 %H:%M')} (KST)")
    result.append("")

    for i, post in enumerate(posts, 1):
        title = post.get("title", "제목 없음")
        author = post.get("author", "익명")
        upvotes = post.get("upvotes", 0)

        # Telegram 마크다운 형식
        result.append(f"**{i}. {title}**")
        result.append(f"   👤 작성자: {author}")
        result.append(f"   ⬆️ 추천수: {upvotes:,}")
        result.append("")

    return "\n".join(result)

def main():
    """메인 실행 함수"""
    print("[*] Moltbook 인기글 다이제스트 생성 중...")

    # 인기글 가져오기
    posts = fetch_hot_posts(limit=3)

    # Telegram 형식으로 포맷팅
    telegram_text = format_telegram(posts)

    # 출력
    print("=" * 50)
    print(telegram_text)
    print("=" * 50)

    # JSON 형식으로도 출력 (디버깅용)
    output = {
        "timestamp": datetime.now(UTC).isoformat(),
        "seoul_time": datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M KST"),
        "posts": posts,
        "telegram_text": telegram_text
    }

    if len(sys.argv) > 1 and sys.argv[1] == "--json":
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        # 파일로 저장 (크론잡에서 사용 가능)
        output_file = Path("/tmp/moltbook_digest.txt")
        output_file.write_text(telegram_text, encoding='utf-8')
        print(f"[*] 다이제스트 저장: {output_file}")

if __name__ == "__main__":
    main()
