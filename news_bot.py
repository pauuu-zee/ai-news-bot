import os
import feedparser
import requests
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

# 유료 장벽이 낮고 일반인에게 유용한 소스 위주로 재편성
RSS_FEEDS = [
    {"name": "OpenAI Blog", "url": "https://openai.com/news/rss.xml"},
    {"name": "The Verge AI", "url": "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml"},
    {"name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/"}
]

def fetch_recent_articles(hours=48):
    articles = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    # 유료 기사(Paywall) 및 불필요한 노이즈 키워드 차단
    # 이 키워드가 걸리면 LLM에 보내지도 않고 즉시 버립니다.
    SKIP_KEYWORDS = [
        "subscription", "premium", "exclusive", "paywall", "pro content",
        "hiring", "funding", "round series", "lawsuit", "legal battle", "patent"
    ]

    for feed_info in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries[:5]:
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                if published and published < cutoff: continue

                title = entry.get("title", "")
                link = entry.get("link", "")
                summary = entry.get("summary", "")[:200]

                # 유료 기사 및 부적합 카테고리 1차 필터링
                if any(kw in (title.lower() + link.lower()) for kw in SKIP_KEYWORDS):
                    continue

                articles.append({
                    "source": feed_info["name"],
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "published": published.astimezone(KST).strftime("%m/%d %H:%M") if published else "시간미상"
                })
        except Exception as e:
            print(f"피드 오류: {e}")

    return articles[:5]

def summarize_with_gemini(articles):
    if not articles: return None
    api_key = os.environ["GEMINI_API_KEY"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

    # 기사 제목과 요약만 전달하여 토큰 절약
    articles_text = "\n".join([f"- [{a['source']}] {a['title']}\n  내용요약: {a['summary']}" for a in articles])
    
    prompt = f"""AI 비전문가 일반인 모임을 위한 뉴스 큐레이터입니다. 
다음 뉴스 중 '실생활 활용도'와 '사회적 파급력'이 큰 기사 3개만 선정하세요.

[선별 및 채점 로직]
1. 일반인 실생활에 도움되는 도구/서비스 소식 (최우선)
2. AI로 인한 사회 변화나 중요한 트렌드 (우선)
3. 주식, 투자, 기업 내부 채용, 소송 뉴스는 0점 처리 (제외)
4. 유료 구독이 필요한 기사로 판단되면 제외

[출력 양식]
- [관련도 점수/10] 제목
- 쉬운 용어로 설명한 2줄 요약
- '이게 왜 중요한가' (일반인 관점) 1줄
- 원문 링크

뉴스 목록:
{articles_text}"""

    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(url, json=payload)
        data = response.json()
        if "error" in data:
            # Spending Cap 에러 발생 시 로그 출력
            print(f"❌ Gemini API 에러: {data['error']}")
            return f"에러 발생: {data['error'].get('message')}"
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except:
        return "요약 생성 중 오류가 발생했습니다."

def send_to_slack(text, webhook_url):
    # 슬랙 채널 C0APBBL0DC1로 고정 전송
    payload = {
        "channel": "C0APBBL0DC1",
        "text": f"📢 *실시간 AI 뉴스 브리핑*\n\n{text}",
        "link_names": 1
    }
    requests.post(webhook_url, json=payload)

def main():
    webhook_url = os.environ["SLACK_WEBHOOK_URL"]
    articles = fetch_recent_articles(hours=48)
    if not articles: return
    
    summary = summarize_with_gemini(articles)
    if summary:
        send_to_slack(summary, webhook_url)

if __name__ == "__main__":
    main()
