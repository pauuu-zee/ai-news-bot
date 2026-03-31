import os
import requests
import feedparser
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

# 소스 및 필터링 로직 (토큰 절약형)
RSS_FEEDS = [
    {"name": "OpenAI Blog", "url": "https://openai.com/news/rss.xml"},
    {"name": "The Verge AI", "url": "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml"},
    {"name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/"}
]

def summarize_with_gemini(articles):
    if not articles: return None
    
    api_key = os.environ["GEMINI_API_KEY"]
    # 사용자님이 확인해주신 최신 모델 Gemini 2.5 Flash 사용
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

    articles_payload = "\n".join([f"- {a['title']} ({a['source']})" for a in articles])
    prompt = f"일반인에게 유용한 AI 뉴스 3개만 골라 2줄 요약해줘. 대상 채널: C0APBBL0DC1\n\n목록:\n{articles_payload}"

    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(url, json=payload)
        data = response.json()
        
        # 에러 발생 시 상세 정보 출력 (GitHub Actions 로그에서 확인 가능)
        if "error" in data:
            print(f"❌ Gemini API Error: {data['error']}")
            return f"Gemini 에러 발생: {data['error'].get('message')}"
            
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"❌ 호출 실패: {str(e)}")
        return f"호출 실패 에러: {str(e)}"

def send_to_slack(text, webhook_url):
    # 슬랙 채널 ID(C0APBBL0DC1)를 페이로드에 직접 지정
    payload = {
        "text": text,
        "channel": "C0APBBL0DC1"  
    }
    response = requests.post(webhook_url, json=payload)
    if response.status_code != 200:
        print(f"❌ 슬랙 발송 실패 ({response.status_code}): {response.text}")

def main():
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    # ... 기사 수집 로직 수행 후 ...
    # (위에서 정의한 fetch_recent_articles 함수 결과 사용)
    articles = [{"title": "예시 뉴스", "source": "OpenAI"}] # 실제 실행시엔 fetch 함수 호출
    
    summary = summarize_with_gemini(articles)
    if summary:
        send_to_slack(summary, webhook_url)

if __name__ == "__main__":
    main()
