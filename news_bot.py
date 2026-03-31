import os
import feedparser
import requests
from datetime import datetime, timezone, timedelta

# 신뢰 출처 RSS 목록
RSS_FEEDS = [
    {"name": "MIT Technology Review", "url": "https://www.technologyreview.com/feed/"},
    {"name": "The Verge AI", "url": "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml"},
    {"name": "BBC Technology", "url": "http://feeds.bbci.co.uk/news/technology/rss.xml"},
    {"name": "Reuters Technology", "url": "https://feeds.reuters.com/reuters/technologyNews"},
    {"name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
]

def fetch_recent_articles(hours=12):
    articles = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    for feed_info in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries[:5]:
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

                if published and published < cutoff:
                    continue

                title = entry.get("title", "")
                summary = entry.get("summary", "")
                text = (title + " " + summary).lower()
                keywords = ["ai", "artificial intelligence", "chatgpt", "openai", "google ai",
                           "anthropic", "claude", "llm", "machine learning", "deepmind", "gemini"]

                if any(kw in text for kw in keywords):
                    articles.append({
                        "source": feed_info["name"],
                        "title": title,
                        "link": entry.get("link", ""),
                        "summary": summary[:300],
                    })
        except Exception as e:
            print(f"피드 오류 ({feed_info['name']}): {e}")

    return articles[:8]


def summarize_with_gemini(articles):
    if not articles:
        return None

    api_key = os.environ["GEMINI_API_KEY"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"

    articles_text = ""
    for i, a in enumerate(articles, 1):
        articles_text += f"{i}. [{a['source']}] {a['title']}\n링크: {a['link']}\n내용: {a['summary']}\n\n"

    prompt = f"""다음은 오늘의 AI 관련 주요 뉴스입니다.
AI를 잘 모르는 일반인도 쉽게 이해할 수 있도록 각 기사를 한국어로 요약해주세요.

규칙:
- 전문 용어는 쉬운 말로 풀어서 설명
- 각 기사마다 2~3문장으로 핵심만 요약
- "이게 왜 중요한가"를 한 줄로 추가
- 원문 링크는 반드시 포함
- 슬랙 메시지 형식으로 출력 (이모지 적절히 사용)

기사 목록:
{articles_text}"""

    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    response = requests.post(url, json=payload)
    data = response.json()

    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"Gemini 응답 오류: {e}, 응답: {data}")
        return None


def send_to_slack(text, webhook_url):
    now_kst = datetime.now(timezone(timedelta(hours=9)))
    time_str = now_kst.strftime("%Y년 %m월 %d일 %H:%M")
    is_morning = now_kst.hour < 12

    header = f"{'🌅 아침' if is_morning else '🌆 저녁'} AI 뉴스 브리핑 | {time_str}\n{'='*40}\n\n"
    payload = {"text": header + text}
    response = requests.post(webhook_url, json=payload)

    if response.status_code == 200:
        print("슬랙 발송 성공!")
    else:
        print(f"슬랙 발송 실패: {response.status_code} {response.text}")


def main():
    webhook_url = os.environ["SLACK_WEBHOOK_URL"]

    print("뉴스 수집 중...")
    articles = fetch_recent_articles(hours=12)
    print(f"{len(articles)}개 기사 수집됨")

    if not articles:
        send_to_slack("오늘은 새로운 AI 뉴스가 없습니다. 🤷", webhook_url)
        return

    print("Gemini로 요약 중...")
    summary = summarize_with_gemini(articles)

    if summary:
        send_to_slack(summary, webhook_url)
    else:
        send_to_slack("뉴스 요약 중 오류가 발생했습니다.", webhook_url)


if __name__ == "__main__":
    main()
