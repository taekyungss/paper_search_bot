"""
data/paper_log.json에 기록된 논문 메시지들의 ⭐ 리액션을 확인해서,
사용자가 새로 선택한 논문을 reviews/YYYY-MM-DD.md에 정리한다.
GitHub Actions에서 주기적으로 실행됨.
"""

import json
import os
from datetime import datetime
from pathlib import Path

import requests

DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")

STAR_EMOJI_ENCODED = "%E2%AD%90"  # ⭐
DISCORD_API = "https://discord.com/api/v10"

PAPER_LOG_PATH = Path(__file__).parent / "data" / "paper_log.json"
REVIEWS_DIR = Path(__file__).parent / "reviews"


def load_paper_log():
    if not PAPER_LOG_PATH.exists():
        return []
    return json.loads(PAPER_LOG_PATH.read_text(encoding="utf-8"))


def save_paper_log(entries):
    PAPER_LOG_PATH.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def has_human_star(channel_id: str, message_id: str) -> bool:
    """해당 메시지에 봇이 아닌 사용자가 ⭐ 리액션을 남겼는지 확인"""
    url = f"{DISCORD_API}/channels/{channel_id}/messages/{message_id}/reactions/{STAR_EMOJI_ENCODED}"
    resp = requests.get(url, headers={"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}, timeout=20)
    if resp.status_code == 404:
        return False
    resp.raise_for_status()
    return any(not user.get("bot") for user in resp.json())


def append_daily_review(entry: dict):
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    path = REVIEWS_DIR / f"{today}.md"

    if not path.exists():
        path.write_text(f"# {today} 논문 리뷰\n\n", encoding="utf-8")

    authors = ", ".join(entry.get("authors", [])) or "저자 정보 없음"
    section = (
        f"## {entry['title']}\n\n"
        f"- 키워드: {entry['keyword']}\n"
        f"- 저자: {authors}\n"
        f"- 발행일: {entry['published']}\n"
        f"- 링크: {entry['link']}\n"
    )
    if entry.get("github"):
        section += f"- GitHub: {entry['github']}\n"
    section += f"\n{entry['summary']}\n\n---\n\n"

    with path.open("a", encoding="utf-8") as f:
        f.write(section)


def main():
    if not DISCORD_BOT_TOKEN:
        raise RuntimeError("DISCORD_BOT_TOKEN 환경변수가 설정되어 있지 않습니다.")

    log = load_paper_log()
    saved_count = 0

    for entry in log:
        if entry.get("review_saved"):
            continue
        if not has_human_star(entry["channel_id"], entry["message_id"]):
            continue

        append_daily_review(entry)
        entry["review_saved"] = True
        saved_count += 1
        print(f"리뷰 저장 완료: {entry['title']}")

    if saved_count:
        save_paper_log(log)

    print(f"이번 실행에서 새로 저장된 논문: {saved_count}개")


if __name__ == "__main__":
    main()
