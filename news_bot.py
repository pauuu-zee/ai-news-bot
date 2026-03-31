import os
import feedparser
import requests
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

RSS_FEEDS = [
    {"name": "MIT Technology Review", "url": "https://www.technologyreview.com/feed/"},
    {"name": "The Verge AI", "url": "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml"},
    {"name": "BBC Technology", "url": "http://feeds.bbci.co.uk/news/technology/rss.xml"},
    {"name": "Reuters Technology", "url": "https://feeds.reuters.com/reuters/technologyNews"},
    {"name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
]


def fetch_recent_articles(hours=48):
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
                    # 발행 시각을 KST로 변환해서 저장
                    published_kst = (
                        published.astimezone(KST).strftime("%m/%d %H:%M KST")
                        if published else "발행시각 미확인"
                    )
                    articles.append({
                        "source": feed_info["name"],
                        "title": title,
                        "link": entry.get("link", ""),
                        "summary": summary[:300],
                        "published": published_kst,
                    })
        except Exception as e:
            print(f"피드 오류 ({feed_info['name']}): {e}")

    return articles[:8]


def summarize_with_gemini(articles):
    if not articles:
        return None

    api_key = os.environ["GEMINI_API_KEY"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

    articles_text = ""
    for i, a in enumerate(articles, 1):
        articles_text += (
            f"{i}. [{a['source']}] {a['title']}\n"
            f"   발행: {a['published']}\n"
            f"   링크: {a['link']}\n"
            f"   내용: {a['summary']}\n\n"
        )

    prompt = f"""다음은 최근 48시간 내 수집된 AI 관련 뉴스 후보입니다.

[모임 정보]
- 대상: AI를 잘 모르는 일반인 모임
- 관심사: 실생활 활용법, 업계 동향, 기술 발전, 사회 이슈

[1단계: 관련도 채점]
각 기사를 아래 기준으로 1~10점 채점하세요.

채점 기준 (높은 점수):
- 일반인이 공감하거나 실생활에 직접 영향을 주는 AI 소식 (+3)
- AI 기술의 사회적 의미나 파급력이 큰 이슈 (+2)
- 국내외 주요 AI 서비스/제품 출시 또는 변화 (+2)
- AI 업계 주요 동향 (기업 전략, 규제, 경쟁 구도 등) (+2)

채점 기준 (낮은 점수):
- 주식/투자/펀딩 뉴스 (-3)
- 채용 공고, 인사 발령 (-3)
- 특허 분쟁, 법적 소송 세부 사항 (-2)
- 개발자 전용 기술 문서, API 업데이트 (-2)
- 기업 IR, 실적 발표 (-2)

[2단계: 선별 및 요약]
- 6점 이상인 기사만 선별하여 요약하세요.
- 6점 미만 기사는 완전히 제외하세요.
- 선별된 기사가 없으면 "오늘은 일반인 관심사에 맞는 AI 뉴스가 없습니다."라고만 출력하세요.

[요약 규칙]
- 전문 용어는 쉬운 말로 풀어서 설명
- 각 기사마다 2~3문장으로 핵심만 요약
- "이게 왜 중요한가"를 한 줄로 추가
- 관련도 점수를 "[8/10]" 형식으로 제목 앞에 표기
- 발행 시각과 원문 링크 반드시 포함
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
    now_kst = datetime.now(KST)
    time_str = now_kst.strftime("%Y년 %m월 %d일 %H:%M")
    is_morning = now_kst.hour < 12

    header = f"{'🌅 아침' if is_morning else '🌆 저녁'} AI 뉴스 브리핑 | {time_str}\n{'='*40}\n\n"
    payload = {
        "text": header + text,
        "channel": "C0APBBL0DC1"
    }
    response = requests.post(webhook_url, json=payload)

    if response.status_code == 200:
        print("슬랙 발송 성공!")
    else:
        print(f"슬랙 발송 실패: {response.status_code} {response.text}")


def main():
    webhook_url = os.environ["SLACK_WEBHOOK_URL"]

    print("뉴스 수집 중...")
    articles = fetch_recent_articles(hours=48)
    print(f"{len(articles)}개 기사 수집됨")

    if not articles:
        send_to_slack("오늘은 새로운 AI 뉴스가 없습니다. 🤷", webhook_url)
        return

    print("Gemini로 채점, 선별 및 요약 중...")
    summary = summarize_with_gemini(articles)

    if summary:
        send_to_slack(summary, webhook_url)
    else:
        send_to_slack("뉴스 요약 중 오류가 발생했습니다.", webhook_url)


if __name__ == "__main__":
    main()
