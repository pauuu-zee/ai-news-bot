import os
import feedparser
import requests
from datetime import datetime, timezone, timedelta

# 한국 시간 설정
KST = timezone(timedelta(hours=9))

# 뉴스 소스 (일반인 영향력 및 공신력 기준)
RSS_FEEDS = [
    {"name": "OpenAI Blog", "url": "https://openai.com/news/rss.xml"},
    {"name": "MIT Technology Review", "url": "https://www.technologyreview.com/feed/"},
    {"name": "The Verge AI", "url": "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml"},
    {"name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
    {"name": "BBC Technology", "url": "http://feeds.bbci.co.uk/news/technology/rss.xml"}
]

def fetch_recent_articles(hours=24):
    articles = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    # 유료/불필요 기사 1차 필터링 (토큰 절약용)
    SKIP_KEYWORDS = ["subscription", "premium", "exclusive", "hiring", "lawsuit", "patent"]

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
                link = entry.get("link", "")
                
                # 유료 기사 및 관심 외 항목 제외
                if any(kw in (title.lower() + link.lower()) for kw in SKIP_KEYWORDS):
                    continue

                articles.append({
                    "source": feed_info["name"],
                    "title": title,
                    "link": link,
                    "published": published.astimezone(KST).strftime("%m/%d %H:%M") if published else "확인불가"
                })
        except Exception as e:
            print(f"피드 오류 ({feed_info['name']}): {e}")

    # 할당량 에러 방지를 위해 최종 후보를 5개로 제한
    return articles[:5]

def summarize_with_gemini(articles):
    if not articles:
        return None

    api_key = os.environ["GEMINI_API_KEY"]
    # 사용자 확인 완료: gemini-2.5-flash 모델 사용
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

    # 토큰 최소화를 위해 제목과 출처만 전달
    articles_text = "\n".join([f"{i+1}. [{a['source']}] {a['title']}" for i, a in enumerate(articles)])

    prompt = f"""AI 비전문가 일반인 모임을 위한 뉴스 큐레이터입니다. 
다음 뉴스 중 실생활 영향력이 큰 3개만 골라 슬랙 메시지 형식으로 요약하세요.

[규칙]
1. 주식/투자/채용/소송 뉴스는 제외.
2. 기사당 2문장 요약 + '중요한 이유' 1줄.
3. 관련도 점수 [0/10] 표기.
4. 전문 용어 대신 쉬운 말 사용.

대상 뉴스:
{articles_text}"""

    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(url, json=payload)
        data = response.json()
        
        if "error" in data:
            print(f"❌ Gemini 에러: {data['error']}")
            return f"에러 발생: {data['error'].get('message')}"
            
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"❌ 호출 오류: {e}")
        return None

def send_to_slack(text, webhook_url):
    now_kst = datetime.now(KST)
    time_str = now_kst.strftime("%Y년 %m월 %d일 %H:%M")
    
    # 헤더 구성
    header = f"📢 *AI 주요 뉴스 브리핑* ({time_str})\n"
    
    # 채널 ID(C0APBBL0DC1) 고정 및 멘션 포함
    payload = {
        "channel": "C0APBBL0DC1",
        "text": f"<#C0APBBL0DC1>\n{header}\n{text}",
        "link_names": 1
    }
    
    res = requests.post(webhook_url, json=payload)
    if res.status_code == 200:
        print("✅ 슬랙 발송 성공")
    else:
        print(f"❌ 슬랙 발송 실패: {res.status_code}, {res.text}")

def main():
    if "SLACK_WEBHOOK_URL" not in os.environ or "GEMINI_API_KEY" not in os.environ:
        print("환경변수 설정이 누락되었습니다.")
        return

    webhook_url = os.environ["SLACK_WEBHOOK_URL"]
    
    print("뉴스 수집 중...")
    articles = fetch_recent_articles(hours=24)
    
    if not articles:
        print("새로운 뉴스가 없습니다.")
        return

    print(f"Gemini 요약 중 (후보 {len(articles)}개)...")
    summary = summarize_with_gemini(articles)
    
    if summary:
        send_to_slack(summary, webhook_url)

if __name__ == "__main__":
    main()
