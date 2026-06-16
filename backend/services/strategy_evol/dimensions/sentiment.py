"""
市场情绪评分维度
基于最近新闻数量、情绪和价格趋势评估市场情绪
"""
from __future__ import annotations

from datetime import date
from typing import Any

from backend.services.market_service import get_daily_history, get_stock_news


def _get_sentiment_score(title: str) -> tuple[str, int]:
    """获取新闻情绪和分数

    返回: (情绪标签, 情绪得分)
    正面 +20, 中性 +10, 负面 -20
    """
    title_lower = title.lower()
    positive_words = [
        "涨", "大涨", "涨停", "利好", "突破", "增长", "看好", "买入", "牛市",
        "创新高", "爆发", "超预期", "回暖", "复苏", "加速",
        "bullish", "rally", "breakthrough", "growth", "upgrade", "outperform",
    ]
    negative_words = [
        "跌", "大跌", "跌停", "利空", "风险", "下跌", "看空", "卖出", "熊市",
        "创新低", "崩盘", "暴雷", "亏损", "减持", "利空",
        "bearish", "crash", "decline", "downgrade", "sell-off", "risk",
    ]
    pos = sum(1 for w in positive_words if w in title_lower)
    neg = sum(1 for w in negative_words if w in title_lower)

    if pos > neg:
        return ("positive", 20)
    elif neg > pos:
        return ("negative", -20)
    return ("neutral", 10)


def _safe_pct_change(series) -> float:
    """安全计算最近5日涨幅"""
    if series is None or len(series) < 2:
        return 0.0
    latest = float(series.iloc[-1])
    prev = float(series.iloc[0])
    if prev == 0:
        return 0.0
    return (latest - prev) / prev * 100


def score_sentiment(stock_code: str) -> dict:
    """
    市场情绪评分（0-100）

    评分维度：
      - 最近7天新闻数量          40分
        新闻数量多 → 关注度高 → 高分
      - 新闻情绪                  40分
        最新新闻正面 +20，中性 +10，负面 -20
        取最近3条的平均
      - 价格最近5日涨幅 > 0      20分
    """
    evidence: list[dict] = []
    total_score = 0.0

    today = date.today()

    # ── 1. 获取新闻 ──
    try:
        news_list = get_stock_news(stock_code, limit=20)
    except Exception:
        news_list = []

    # ── 2. 新闻数量评分（40分） ──
    recent_news = []
    for news in news_list:
        pub_date = None
        raw_date = news.get("发布日期") or news.get("date") or news.get("pub_date")
        if raw_date:
            if isinstance(raw_date, str):
                try:
                    pub_date = date.fromisoformat(str(raw_date)[:10])
                except (ValueError, IndexError):
                    pass
            elif hasattr(raw_date, "date"):
                pub_date = raw_date.date() if hasattr(raw_date, "date") else raw_date

        if pub_date and (today - pub_date).days <= 7:
            recent_news.append(news)
        elif pub_date is None:
            # 没有日期信息，假设是近期的
            recent_news.append(news)

    # 确保不重复计数
    if len(news_list) > 0 and len(recent_news) == 0:
        recent_news = list(news_list)

    news_count = len(recent_news)

    if news_count >= 10:
        news_count_score = 40
        detail = f"最近7天{news_count}条新闻，关注度很高"
    elif news_count >= 5:
        news_count_score = 30
        detail = f"最近7天{news_count}条新闻，关注度较高"
    elif news_count >= 3:
        news_count_score = 20
        detail = f"最近7天{news_count}条新闻，关注度一般"
    elif news_count >= 1:
        news_count_score = 10
        detail = f"最近7天{news_count}条新闻，关注度较低"
    else:
        news_count_score = 0
        detail = "最近7天无新闻"

    evidence.append({
        "factor": "新闻数量",
        "detail": detail,
        "score": news_count_score,
    })
    total_score += news_count_score

    # ── 3. 新闻情绪评分（40分） ──
    if recent_news:
        # 取最近3条新闻的情绪
        sentiment_total = 0
        sentiment_count = 0
        sentiment_labels = []

        for news in recent_news[:3]:
            title = news.get("标题") or news.get("title") or ""
            if not title:
                continue
            label, score_val = _get_sentiment_score(title)
            sentiment_total += score_val
            sentiment_count += 1
            sentiment_labels.append(f"{label}({score_val:+d})")

        if sentiment_count > 0:
            avg_sentiment = sentiment_total / sentiment_count
            # 映射到 0-40 分
            # avg_sentiment 范围: -20 ~ +20
            # (avg_sentiment + 20) / 40 * 40 = avg_sentiment + 20
            sentiment_score = max(0, min(40, avg_sentiment + 20))
        else:
            sentiment_score = 20  # 中性
            sentiment_labels = ["中性"]
    else:
        sentiment_score = 20  # 无新闻时默认中性
        sentiment_labels = ["无新闻"]

    evidence.append({
        "factor": "新闻情绪",
        "detail": f"最近新闻情绪: {'、'.join(sentiment_labels)}，综合得分={sentiment_score:.1f}",
        "score": round(sentiment_score, 1),
    })
    total_score += sentiment_score

    # ── 4. 价格趋势评分（20分） ──
    df = get_daily_history(stock_code, max_days=30)
    if df is not None and not df.empty and len(df) >= 2:
        df_sorted = df.sort_values("date").reset_index(drop=True)
        closes = df_sorted["close"]

        if len(closes) >= 6:
            price_change_5d = (float(closes.iloc[-1]) - float(closes.iloc[-6])) / float(closes.iloc[-6]) * 100
        elif len(closes) >= 2:
            price_change_5d = (float(closes.iloc[-1]) - float(closes.iloc[0])) / float(closes.iloc[0]) * 100
        else:
            price_change_5d = 0.0

        if price_change_5d > 10:
            trend_score = 20
            trend_detail = f"最近5日涨幅{price_change_5d:+.1f}%，强势上涨"
        elif price_change_5d > 5:
            trend_score = 18
            trend_detail = f"最近5日涨幅{price_change_5d:+.1f}%，明显上涨"
        elif price_change_5d > 2:
            trend_score = 15
            trend_detail = f"最近5日涨幅{price_change_5d:+.1f}%，小幅上涨"
        elif price_change_5d > 0:
            trend_score = 12
            trend_detail = f"最近5日涨幅{price_change_5d:+.1f}%，微涨"
        elif price_change_5d > -3:
            trend_score = 8
            trend_detail = f"最近5日涨幅{price_change_5d:+.1f}%，小幅下跌"
        elif price_change_5d > -8:
            trend_score = 4
            trend_detail = f"最近5日涨幅{price_change_5d:+.1f}%，明显下跌"
        else:
            trend_score = 0
            trend_detail = f"最近5日涨幅{price_change_5d:+.1f}%，大幅下跌"
    else:
        trend_score = 10  # 数据不足，中性
        trend_detail = "价格数据不足"

    evidence.append({
        "factor": "价格趋势",
        "detail": trend_detail,
        "score": trend_score,
    })
    total_score += trend_score

    final_score = min(round(total_score, 1), 100)

    return {
        "score": final_score,
        "evidence": evidence,
    }
