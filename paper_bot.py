"""
디코봇 - 키워드별 최신 Hugging Face Papers 검색 & Discord 알림
매주 월요일 아침 10시에 GitHub Actions로 실행됨
"""

import os
import requests
from datetime import datetime

# ====== 여기에 원하는 키워드 5개를 입력하세요 ======
KEYWORDS = [
    "VLM OCR",
    "GUI grounding",
    "GUI agent"
]
PAPERS_PER_KEYWORD = 3

HF_SEARCH_API = "https://huggingface.co/api/papers/search"

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")


def search_hf_papers(keyword: str, max_results: int = 3):
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
        papers.append(
            {
                "title": p.get("title", "").strip(),
                "link": f"https://huggingface.co/papers/{p.get('id')}",
                "published": published_at[:10],
                "published_dt": published_at,
                "summary": (p.get("summary") or "").strip().replace("\n", " "),
                "upvotes": p.get("upvotes", 0),
                "github": p.get("githubRepo"),
            }
        )

    # 발행일 최신순 정렬 후 상위 N개 (최신 논문이 부족하면 오래된 논문으로 채워짐)
    papers.sort(key=lambda x: x["published_dt"], reverse=True)

    return papers[:max_results]


def build_embeds():
    embeds = []
    for kw in KEYWORDS:
        papers = search_hf_papers(kw, PAPERS_PER_KEYWORD)
        for p in papers:
            fields = [
                {"name": "📅 발행일", "value": p["published"], "inline": True},
                {"name": "⬆️ Upvotes", "value": str(p["upvotes"]), "inline": True},
            ]
            if p["github"]:
                fields.append({"name": "💻 GitHub", "value": p["github"], "inline": False})
            embeds.append(
                {
                    "title": p["title"][:256],
                    "url": p["link"],
                    "description": p["summary"][:4096],
                    "color": 3447003,
                    "fields": fields,
                    "footer": {"text": f"🔍 {kw}"},
                }
            )
    return embeds


def send_to_discord(embeds):
    if not DISCORD_WEBHOOK_URL:
        raise RuntimeError("DISCORD_WEBHOOK_URL 환경변수가 설정되어 있지 않습니다.")

    today = datetime.now().strftime("%Y-%m-%d")
    # 디스코드는 embed 하나당 하나의 메시지로 최대 10개까지 첨부 가능
    payload = {
        "content": f"📚 **주간 논문 알림 ({today})**",
        "embeds": embeds[:10],
    }
    resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=20)
    resp.raise_for_status()


if __name__ == "__main__":
    embeds = build_embeds()
    if embeds:
        send_to_discord(embeds)
        print(f"{len(embeds)}개 키워드에 대한 논문 알림 전송 완료")
    else:
        print("검색된 논문이 없습니다.")
