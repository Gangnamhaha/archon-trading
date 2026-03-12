"""
뉴스 수집 + 감성 분석 모듈
- RSS 피드 기반 금융 뉴스 수집
- 키워드 기반 감성 분석
"""
import feedparser
import requests
import re
from datetime import datetime
import pandas as pd


# 금융 뉴스 RSS 피드 소스
NEWS_SOURCES = {
    "한국경제": "https://www.hankyung.com/feed/stock",
    "매일경제": "https://www.mk.co.kr/rss/30000001/",
    "연합뉴스 경제": "https://www.yna.co.kr/rss/economy.xml",
    "조선비즈": "https://biz.chosun.com/rss/economy/",
    "Yahoo Finance": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US",
    "MarketWatch": "http://feeds.marketwatch.com/marketwatch/topstories/",
    "CNBC": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
}

# 감성 분석 키워드
POSITIVE_KEYWORDS_KR = [
    "상승", "급등", "호재", "최고가", "신고가", "돌파", "강세", "매수", "성장",
    "실적개선", "호실적", "흑자", "상향", "기대감", "회복", "반등", "랠리",
    "수주", "계약", "인수", "투자확대", "배당", "자사주", "호전"
]
NEGATIVE_KEYWORDS_KR = [
    "하락", "급락", "악재", "최저가", "폭락", "약세", "매도", "위기",
    "실적악화", "적자", "하향", "우려", "불안", "조정", "리스크",
    "손실", "파산", "소송", "제재", "규제", "인플레이션", "금리인상"
]
POSITIVE_KEYWORDS_EN = [
    "surge", "rally", "bullish", "gain", "profit", "growth", "upgrade",
    "breakout", "record high", "beat", "outperform", "buy", "strong",
    "recovery", "optimistic", "dividend", "acquisition"
]
NEGATIVE_KEYWORDS_EN = [
    "plunge", "crash", "bearish", "loss", "decline", "downgrade",
    "sell", "weak", "crisis", "recession", "inflation", "risk",
    "debt", "bankruptcy", "layoff", "miss", "underperform", "concern"
]


def fetch_news(sources: list = None, max_per_source: int = 10) -> list:
    """RSS 피드에서 뉴스 수집"""
    if sources is None:
        sources = list(NEWS_SOURCES.keys())

    all_news = []
    for source_name in sources:
        url = NEWS_SOURCES.get(source_name)
        if not url:
            continue
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_source]:
                published = ""
                if hasattr(entry, "published"):
                    published = entry.published
                elif hasattr(entry, "updated"):
                    published = entry.updated

                all_news.append({
                    "source": source_name,
                    "title": entry.get("title", ""),
                    "summary": _clean_html(entry.get("summary", "")),
                    "link": entry.get("link", ""),
                    "published": published,
                })
        except Exception:
            continue

    return all_news


def analyze_sentiment(text: str) -> dict:
    """텍스트 감성 분석 (키워드 기반)"""
    text_lower = text.lower()
    pos_score = 0
    neg_score = 0
    pos_keywords_found = []
    neg_keywords_found = []

    # 한국어 키워드
    for kw in POSITIVE_KEYWORDS_KR:
        if kw in text:
            pos_score += 1
            pos_keywords_found.append(kw)
    for kw in NEGATIVE_KEYWORDS_KR:
        if kw in text:
            neg_score += 1
            neg_keywords_found.append(kw)

    # 영어 키워드
    for kw in POSITIVE_KEYWORDS_EN:
        if kw in text_lower:
            pos_score += 1
            pos_keywords_found.append(kw)
    for kw in NEGATIVE_KEYWORDS_EN:
        if kw in text_lower:
            neg_score += 1
            neg_keywords_found.append(kw)

    total = pos_score + neg_score
    if total == 0:
        sentiment = "중립"
        score = 0
    elif pos_score > neg_score:
        sentiment = "긍정"
        score = round(pos_score / total * 100, 1)
    elif neg_score > pos_score:
        sentiment = "부정"
        score = round(-neg_score / total * 100, 1)
    else:
        sentiment = "중립"
        score = 0

    return {
        "sentiment": sentiment,
        "score": score,
        "positive_count": pos_score,
        "negative_count": neg_score,
        "positive_keywords": pos_keywords_found,
        "negative_keywords": neg_keywords_found,
    }


def fetch_and_analyze(sources: list = None, keyword: str = None) -> pd.DataFrame:
    """뉴스 수집 + 감성 분석 통합"""
    news_list = fetch_news(sources)

    if keyword:
        news_list = [n for n in news_list if keyword.lower() in (n["title"] + n["summary"]).lower()]

    results = []
    for news in news_list:
        text = news["title"] + " " + news["summary"]
        sentiment = analyze_sentiment(text)
        results.append({
            "출처": news["source"],
            "제목": news["title"],
            "링크": news["link"],
            "발행일": news["published"],
            "감성": sentiment["sentiment"],
            "점수": sentiment["score"],
            "긍정키워드": ", ".join(sentiment["positive_keywords"]),
            "부정키워드": ", ".join(sentiment["negative_keywords"]),
        })

    return pd.DataFrame(results)


def get_market_sentiment(sources: list = None) -> dict:
    """전체 시장 감성 요약"""
    df = fetch_and_analyze(sources)
    if df.empty:
        return {"overall": "데이터 없음", "positive_pct": 0, "negative_pct": 0, "neutral_pct": 0, "total": 0}

    total = len(df)
    pos = len(df[df["감성"] == "긍정"])
    neg = len(df[df["감성"] == "부정"])
    neu = len(df[df["감성"] == "중립"])

    if pos > neg:
        overall = "긍정적"
    elif neg > pos:
        overall = "부정적"
    else:
        overall = "중립"

    return {
        "overall": overall,
        "positive_pct": round(pos / total * 100, 1),
        "negative_pct": round(neg / total * 100, 1),
        "neutral_pct": round(neu / total * 100, 1),
        "total": total,
        "avg_score": round(df["점수"].mean(), 1),
    }


def _clean_html(text: str) -> str:
    """HTML 태그 제거"""
    clean = re.sub(r"<[^>]+>", "", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:300]
