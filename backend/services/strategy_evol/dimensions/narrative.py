"""
市场叙事评分维度
从 analyze/narrative 获取热点叙事，检查股票所属行业是否匹配热点
从 analyze/news_fetcher / market_service 获取新闻数据
"""
from __future__ import annotations

import os
import sqlite3
from datetime import date, timedelta
from typing import Any

from backend.services.analyze.narrative import get_saved_narratives
from backend.services.db_client import get_stock_info
from backend.services.market_service import get_stock_news

ARCHIVE_DB = os.path.expanduser("~/Jarvis/ai_trading/stock_archive.db")

# 常见热点板块关键词映射（可后续进化）
HOT_SECTOR_KEYWORDS: dict[str, list[str]] = {
    "人工智能": ["人工智能", "AI", "大模型", "chatgpt", "openai", "算力", "AI芯片", "智能"],
    "半导体": ["半导体", "芯片", "集成电路", "光刻", "封测", "存储芯片"],
    "新能源车": ["新能源车", "电动汽车", "EV", "锂电", "充电桩", "整车", "汽车零部件"],
    "光伏": ["光伏", "太阳能", "逆变器", "HJT", "TOPCon", "钙钛矿"],
    "医药生物": ["医药", "生物", "创新药", "CXO", "医疗器械", "中药"],
    "消费": ["消费", "白酒", "食品饮料", "家电", "免税", "零售"],
    "军工": ["军工", "国防", "航天", "航空", "装备", "船舶"],
    "金融": ["金融", "银行", "券商", "保险", "财富管理", "证券"],
    "低空经济": ["低空经济", "无人机", "飞行汽车", "eVTOL"],
    "机器人": ["机器人", "人形机器人", "自动化", "智能制造"],
    "储能": ["储能", "电池", "钠离子", "氢能", "能源"],
    "数字经济": ["数字经济", "数据要素", "云计算", "大数据", "SaaS"],
}


def _get_db() -> sqlite3.Connection | None:
    """获取存档数据库连接"""
    try:
        conn = sqlite3.connect(ARCHIVE_DB)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception:
        return None


def _get_sentiment(title: str) -> str:
    """简单关键词情绪判断"""
    title_lower = title.lower()
    positive_words = ["涨", "利好", "突破", "增长", "看好", "买入", "牛市", "创新",
                      "bullish", "buy", "breakthrough", "growth", "rally", "gain"]
    negative_words = ["跌", "利空", "风险", "警告", "下跌", "看空", "卖出", "熊市",
                      "bearish", "sell", "risk", "warning", "crash", "drop"]
    pos = sum(1 for w in positive_words if w in title_lower)
    neg = sum(1 for w in negative_words if w in title_lower)
    if pos > neg:
        return "positive"
    elif neg > pos:
        return "negative"
    return "neutral"


def _get_stock_industry_info(stock_code: str) -> dict:
    """获取股票行业/概念信息"""
    info = get_stock_info(stock_code)
    if not info:
        return {"industry": "", "concepts": []}

    industry = info.get("industry") or ""
    concepts_str = info.get("concepts") or ""

    # concepts 可能是字符串列表或 JSON 字符串
    if isinstance(concepts_str, str):
        import json
        try:
            concepts = json.loads(concepts_str) if concepts_str.startswith("[") else [concepts_str]
        except (json.JSONDecodeError, TypeError):
            concepts = [] if not concepts_str else [concepts_str]
    elif isinstance(concepts_str, list):
        concepts = concepts_str
    else:
        concepts = []

    return {"industry": industry, "concepts": concepts}


def score_narrative(stock_code: str) -> dict:
    """
    市场叙事热度评分（0-100）

    评分维度：
      - 股票所属行业是否匹配当前热点叙事      40分
      - 最近7天新闻数量                       20分
      - 新闻情绪 > 0                          20分
      - 知识图谱关联度（概念/板块重叠度）      20分
    """
    evidence: list[dict] = []
    total_score = 0.0

    industry_info = _get_stock_industry_info(stock_code)
    industry = industry_info.get("industry", "")
    concepts = industry_info.get("concepts", [])

    # ── 1. 行业匹配热点叙事（40分） ──
    today = date.today()

    # 获取最近3个交易日的叙事数据
    all_narratives: list[dict] = []
    for i in range(5):
        d = (today - timedelta(days=i)).isoformat()
        try:
            narratives = get_saved_narratives(d)
            if narratives:
                all_narratives.extend(narratives)
        except Exception:
            pass
        if len(all_narratives) >= 3:
            break

    # 提取热点叙事中的板块名称
    hot_sectors: set[str] = set()
    narrative_names: set[str] = set()
    for n in all_narratives:
        name = n.get("name", "")
        if name:
            narrative_names.add(name)
        related_sectors = n.get("related_sectors") or []
        for s in related_sectors:
            hot_sectors.add(s)
        # 从 category 加入
        cat = n.get("category", "")
        if cat and cat != "其他":
            hot_sectors.add(cat)

    # 检查个股行业/概念是否匹配热点
    narrative_match_score = 0.0
    match_details: list[str] = []

    # 方式1：行业名直接匹配热点板块
    if industry:
        for hs in hot_sectors:
            if industry in hs or hs in industry:
                narrative_match_score += 20
                match_details.append(f"行业「{industry}」匹配热点板块「{hs}」")
                break
        else:
            for keyword, keywords_list in HOT_SECTOR_KEYWORDS.items():
                if any(kw in industry for kw in keywords_list):
                    narrative_match_score += 15
                    match_details.append(f"行业「{industry}」关键词匹配热点「{keyword}」")
                    break

    # 方式2：概念匹配
    concept_matches = []
    for concept in concepts:
        for hs in hot_sectors:
            if concept in hs or hs in concept:
                concept_matches.append(concept)
                break
        else:
            for keyword, keywords_list in HOT_SECTOR_KEYWORDS.items():
                if any(kw in concept for kw in keywords_list):
                    concept_matches.append(concept)
                    break

    if concept_matches:
        narrative_match_score = max(narrative_match_score, min(40, 10 * len(concept_matches)))
        match_details.append(f"概念「{'、'.join(concept_matches[:3])}」匹配热点")

    # 方式3：叙事名称匹配
    for n_name in narrative_names:
        if industry and (industry in n_name or n_name in industry):
            narrative_match_score = max(narrative_match_score, 30)
            match_details.append(f"叙事「{n_name}」与行业「{industry}」匹配")
            break

    narrative_match_score = min(narrative_match_score, 40)
    evidence.append({
        "factor": "行业匹配热点叙事",
        "detail": "；".join(match_details) if match_details else f"行业「{industry}」未匹配到当前热点叙事",
        "score": round(narrative_match_score, 1),
    })
    total_score += narrative_match_score

    # ── 2. 最近7天新闻数量（20分） ──
    try:
        news_list = get_stock_news(stock_code, limit=30)
    except Exception:
        news_list = []

    recent_news = 0
    positive_news = 0
    if news_list:
        for news in news_list:
            # 尝试解析新闻日期
            pub_date = None
            raw_date = news.get("发布日期") or news.get("date") or news.get("pub_date")
            if raw_date:
                if isinstance(raw_date, str):
                    try:
                        pub_date = date.fromisoformat(raw_date[:10])
                    except (ValueError, IndexError):
                        pass
                elif hasattr(raw_date, "date"):
                    pub_date = raw_date.date() if hasattr(raw_date, "date") else raw_date

            if pub_date and (today - pub_date).days <= 7:
                recent_news += 1
                title = news.get("标题") or news.get("title") or ""
                if _get_sentiment(title) == "positive":
                    positive_news += 1
        # fallback: 如果没有日期字段，假设所有新闻都是近期的
        if recent_news == 0 and len(news_list) > 0:
            recent_news = len(news_list)

    news_count_score = min(20, recent_news * 4)  # 每1条4分，5条满20
    evidence.append({
        "factor": "新闻数量",
        "detail": f"最近7天{recent_news}条新闻",
        "score": news_count_score,
    })
    total_score += news_count_score

    # ── 3. 新闻情绪（20分） ──
    if recent_news > 0:
        sentiment_score = min(20, positive_news / max(recent_news, 1) * 20)
    else:
        sentiment_score = 0
    evidence.append({
        "factor": "新闻情绪",
        "detail": f"最近7天正面新闻{positive_news}条，情绪得分={sentiment_score:.1f}",
        "score": round(sentiment_score, 1),
    })
    total_score += sentiment_score

    # ── 4. 知识图谱关联度（20分） ──
    # 简单实现：计算概念/行业与HOT_SECTOR_KEYWORDS的重叠度
    kg_score = 0.0
    matched_keywords = set()
    all_tags = [industry] + concepts
    for tag in all_tags:
        if not tag:
            continue
        for hot_name, keywords in HOT_SECTOR_KEYWORDS.items():
            if any(kw in tag for kw in keywords):
                matched_keywords.add(hot_name)

    kg_score = min(20, len(matched_keywords) * 5)
    evidence.append({
        "factor": "概念关联度",
        "detail": f"匹配{len(matched_keywords)}个热点领域（{'、'.join(matched_keywords) if matched_keywords else '无'}）",
        "score": kg_score,
    })
    total_score += kg_score

    final_score = min(round(total_score, 1), 100)

    return {
        "score": final_score,
        "evidence": evidence,
    }
