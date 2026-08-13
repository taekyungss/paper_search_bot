"""
디코봇 - 키워드별 최신 Hugging Face Papers 검색 & Discord 알림
매일 아침 10시에 GitHub Actions로 실행됨
논문마다 메시지를 따로 보내고, message_id를 data/paper_log.json에 기록해서
reaction_checker.py가 나중에 ⭐ 리액션을 개별 논문 단위로 추적할 수 있게 한다.
"""

import json
import os
from datetime import datetime
from pathlib import Path

import requests

# ====== 여기에 원하는 키워드 5개를 입력하세요 ======
KEYWORDS = [
    "VLM OCR",
    "GUI grounding",
    "GUI agent",
]
PAPERS_PER_KEYWORD = 1
STAR_EMOJI = "⭐"

HF_SEARCH_API = "https://huggingface.co/api/papers/search"
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

PAPER_LOG_PATH = Path(__file__).parent / "data" / "paper_log.json"


def search_hf_papers(keyword: str, max_results: int = 1):
    """HF Papers에서 키워드로 검색 후, 발행일(publishedAt) 기준 최신순으로 정렬해 반환"""
    resp = requests.get(HF_SEARCH_API, params={"q": keyword}, timeout=20)
    resp.raise_for_status()
    raw = resp.json()

    papers = []
    for item in raw:
        p = item.get("paper", item)
        published_at = p.get("publishedAt") or item.get("publishedAt")
        if not published_at:
            continue
        authors = [a.get("name", "").strip() for a in p.get("authors", []) if a.get("name")]
        papers.append(
            {
                "title": p.get("title", "").strip(),
                "link": f"https://huggingface.co/papers/{p.get('id')}",
                "arxiv_id": p.get("id"),
                "published": published_at[:10],
                "published_dt": published_at,
                "summary": (p.get("summary") or "").strip().replace("\n", " "),
                "upvotes": p.get("upvotes", 0),
                "github": p.get("githubRepo"),
                "authors": authors,
            }
        )

    # 발행일 최신순 정렬 후 상위 N개 (최신 논문이 부족하면 오래된 논문으로 채워짐)
    papers.sort(key=lambda x: x["published_dt"], reverse=True)

    return papers[:max_results]


def build_posts():
    """키워드별 논문을 (keyword, paper) 쌍으로 평탄화해서 반환"""
    posts = []
    for kw in KEYWORDS:
        for p in search_hf_papers(kw, PAPERS_PER_KEYWORD):
            posts.append((kw, p))
    return posts


def embed_for(kw: str, p: dict):
    fields = [
        {"name": "📅 발행일", "value": p["published"], "inline": True},
        {"name": "⬆️ Upvotes", "value": str(p["upvotes"]), "inline": True},
    ]
    if p["github"]:
        fields.append({"name": "💻 GitHub", "value": p["github"], "inline": False})
    return {
        "title": p["title"][:256],
        "url": p["link"],
        "description": p["summary"][:4096],
        "color": 3447003,
        "fields": fields,
        "footer": {"text": f"🔍 {kw}  ·  마음에 들면 {STAR_EMOJI} 를 눌러 Zotero에 저장하세요"},
    }


def send_paper(kw: str, p: dict):
    """논문 1개를 개별 메시지로 전송하고 message_id/channel_id를 반환"""
    if not DISCORD_WEBHOOK_URL:
        raise RuntimeError("DISCORD_WEBHOOK_URL 환경변수가 설정되어 있지 않습니다.")

    resp = requests.post(
        DISCORD_WEBHOOK_URL,
        params={"wait": "true"},
        json={"username": f"📄 {kw}", "embeds": [embed_for(kw, p)]},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["id"], data["channel_id"]


def load_paper_log():
    if PAPER_LOG_PATH.exists():
        return json.loads(PAPER_LOG_PATH.read_text(encoding="utf-8"))
    return []


def save_paper_log(entries):
    PAPER_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    PAPER_LOG_PATH.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    posts = build_posts()
    if not posts:
        print("검색된 논문이 없습니다.")
        return

    log = load_paper_log()
    today = datetime.now().strftime("%Y-%m-%d")

    for kw, p in posts:
        message_id, channel_id = send_paper(kw, p)
        log.append(
            {
                "message_id": message_id,
                "channel_id": channel_id,
                "date": today,
                "keyword": kw,
                "title": p["title"],
                "authors": p["authors"],
                "link": p["link"],
                "arxiv_id": p["arxiv_id"],
                "published": p["published"],
                "summary": p["summary"],
                "github": p["github"],
                "zotero_synced": False,
            }
        )

    save_paper_log(log)
    print(f"{len(posts)}개 논문 전송 완료")


if __name__ == "__main__":
    main()
