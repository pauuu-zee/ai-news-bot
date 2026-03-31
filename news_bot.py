import os
import feedparser
import requests
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

# 유료 구독 모델이 강한 매체 제외 및 일반인 친화적 소스 유지
RSS_FEEDS = [
    {"name": "OpenAI Blog", "url": "https://openai.com/news/rss.xml"}, # 공식 소식 (영향력 최상)
    {"name": "The Verge AI", "url": "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml"},
    {"name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
    {"name": "MIT Tech Review", "url": "https://www.technologyreview.com/feed/"},
]

def fetch_recent_articles(hours=24):
    articles = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    # 유료 기사 및 일반인 부적합 키워드 (토큰 절약용 사전 필터링)
    SKIP_KEYWORDS = ["subscription", "premium", "exclusive", "funding", "round series", "hiring", "lawsuit", "patent"]

    for feed_info in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries[:10]: # 더 많은 후보를 보되 필터링 강화
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

                if published and published < cutoff:
                    continue

                title = entry.get("title", "")
                summary = entry.get("summary", "").lower()
                link = entry.get("link", "").lower()

                # 1차 필터링: 유료 기사 및 투자/소송 뉴스 제외 (토큰 소모 방지)
                if any(kw in (title.lower() + summary + link) for kw in SKIP_KEYWORDS):
                    continue

                # 버즈량 대용: 제목에 'Top', 'Best', 'New', 'Launch' 등이 포함되거나 공식 블로그면 가점
                articles.append({
                    "source": feed_info["name"],
                    "title": title,
                    "link": entry.get("link", ""),
                    "summary": summary[:200], # 요약 길이를 줄여 토큰 절약
                    "published": published.astimezone(KST).strftime("%m/%d %H:%M") if published else "확인불가",
                })
        except Exception as e:
            print(f"Error ({feed_info['name']}): {e}")

    # 상위 10개로 제한하여 Gemini에 전달 (토큰 최적화)
    return articles[:10]

def summarize_with_gemini(articles):
    if not articles: return None
    
    api_key = os.environ["GEMINI_API_KEY"]
    # 최신 모델명 확인 필요 (현재 기준 1.5 flash가 비용 대비 효율적)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"

    # 토큰 절약을 위해 기사 리스트를 아주 간결한 텍스트로 변환
    articles_payload = "\n".join([f"- {a['title']} ({a['source']})" for a in articles])

    prompt = f"""당신은 일반인 대상 AI 뉴스 큐레이터입니다. 아래 뉴스 중 **실생활 영향력**이 가장 큰 3개만 골라 요약하세요.

[필터링 기준]
1. 일반인 실생활 활용도 위주 (도구 출시, 편의성 개선 등)
2. 투자/채용/소송 뉴스는 무조건 제외
3. 제목만 보고 가치가 낮으면 버릴 것

[출력 양식]
- 기사당 2줄 요약 (쉬운 용어)
- "일반인에게 중요한 이유" 1줄 포함
- 링크 포함

목록:
{articles_payload}"""

    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    response = requests.post(url, json=payload)
    
    try:
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]
    except:
        return "요약 생성 중 오류가 발생했습니다."

def send_to_slack(text, webhook_url):
    payload = {"text": text}
    requests.post(webhook_url, json=payload)

def main():
    # 환경변수 로드 및 실행 로직
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    articles = fetch_recent_articles(hours=24)
    
    if not articles:
        print("새로운 주요 뉴스가 없습니다.")
        return

    summary = summarize_with_gemini(articles)
    if summary:
        send_to_slack(summary, webhook_url)

if __name__ == "__main__":
    main()
