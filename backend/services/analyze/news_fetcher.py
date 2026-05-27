"""
新闻言论抓取服务 - 替代 X/Twitter 推文
使用 Google News RSS + 定向爬取，追踪关键人物的公开言论

数据源（免认证）：
  - Google News RSS：覆盖全部 17 位关键人物
  - 定向爬取：ARK Invest、OpenAI Blog、vitalik.ca 等（后续扩展）
"""
from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.parse
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from backend.services.analyze.person_tracker import (
    _get_db, get_key_people, save_statement
)

# ── 每人配置 Google News 搜索关键词 ────────────────
# 每个关键词会单独搜索，去重后合并
PERSON_QUERIES: dict[str, list[str]] = {
    # ── 美股 ──
    "Cathie Wood": [
        "Cathie Wood says",
        "Cathie Wood ARK Invest outlook",
        "Cathie Wood market prediction",
    ],
    "Elon Musk": [
        "Elon Musk says",
        "Elon Musk Tesla",
        "Elon Musk AI prediction",
    ],
    "Michael Saylor": [
        "Michael Saylor bitcoin",
        "Michael Saylor MicroStrategy",
    ],
    "Jerome Powell": [
        "Jerome Powell Fed speech",
        "Jerome Powell interest rates",
        "Federal Reserve Powell outlook",
    ],
    "Warren Buffett": [
        "Warren Buffett says",
        "Berkshire Hathaway Buffett",
        "Warren Buffett investment",
    ],
    "Bill Ackman": [
        "Bill Ackman says",
        "Bill Ackman Pershing Square",
    ],
    "David Einhorn": [
        "David Einhorn Greenlight",
        "David Einhorn short",
    ],
    "Ming-Chi Kuo": [
        "Ming-Chi Kuo Apple",
        "郭明錤 供应链",
    ],
    "Stanley Druckenmiller": [
        "Stanley Druckenmiller",
        "Druckenmiller portfolio",
    ],
    # ── A股 ──
    "但斌": [
        "但斌 看好",
        "但斌 投资 观点",
        "东方港湾 但斌",
    ],
    "林园": [
        "林园 投资",
        "林园 看好",
    ],
    "李蓓": [
        "李蓓 市场 观点",
        "半夏投资 李蓓",
    ],
    "管清友": [
        "管清友 经济",
        "管清友 股市",
    ],
    # ── 加密货币 ──
    "CZ (Binance)": [
        "CZ Binance crypto",
        "Binance CEO says",
    ],
    "Vitalik Buterin": [
        "Vitalik Buterin Ethereum",
        "Vitalik Buterin says",
    ],
    "Arthur Hayes": [
        "Arthur Hayes crypto",
        "Arthur Hayes market outlook",
    ],
    "Murad Mahmudov": [
        "Murad Mahmudov bitcoin",
        "Murad Mahmudov crypto",
    ],
}

# ── 人名搜索黑名单：标题中含这些词的文章跳过 ──────
BLACKLIST_PATTERNS = [
    r"crypto\.com", r"coinbase", r"press release", r"sponsored",
    r"advertisement", r"promoted", r"opinion\s*:",
]

# Google News RSS 最大搜索页数（每页约 10 条）
MAX_RESULTS_PER_QUERY = 5


# ═══════════════════════════════════════════════════
# 核心抓取逻辑
# ═══════════════════════════════════════════════════

def fetch_person_news(person_name: str, max_articles: int = 5) -> list[dict]:
    """用 Google News RSS 搜索某个人的最新新闻
    
    返回格式: [{"title": ..., "url": ..., "date": ...}, ...]
    """
    queries = PERSON_QUERIES.get(person_name, [person_name])
    seen_urls: set[str] = set()
    articles: list[dict] = []

    for query in queries:
        if len(articles) >= max_articles:
            break
        try:
            results = _search_google_news(query)
            for art in results:
                url = art.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    articles.append(art)
                    if len(articles) >= max_articles:
                        break
        except Exception as e:
            print(f"[news_fetcher] 搜索 '{query}' 失败: {e}", flush=True)

        time.sleep(0.5)  # 礼貌间隔

    return articles


def _search_google_news(query: str) -> list[dict]:
    """执行一次 Google News RSS 搜索，返回文章列表"""
    encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"

    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", "12", url],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode != 0:
            return []
        return _parse_rss_articles(r.stdout, query)
    except Exception as e:
        print(f"[news_fetcher] curl 失败: {e}", flush=True)
        return []


def _parse_rss_articles(xml_text: str, query: str) -> list[dict]:
    """从 RSS XML 中解析文章标题和链接"""
    articles: list[dict] = []
    # 提取 item 块
    items = re.findall(r"<item>(.*?)</item>", xml_text, re.DOTALL)
    if not items:
        # fallback: 从 XML 直接提取
        titles = re.findall(r"<title>(.*?)</title>", xml_text)
        links = re.findall(r"<link>(.*?)</link>", xml_text)
        # 跳过第一个（"Google News"）
        for i, title in enumerate(titles[1:], 1):
            if i < len(links):
                articles.append({"title": title, "url": links[i], "source": "Google News"})
        return articles

    for item in items:
        title_match = re.search(r"<title>(.*?)</title>", item)
        link_match = re.search(r"<link>(.*?)</link>", item)
        # 尝试提取 pubDate
        date_match = re.search(r"<pubDate>(.*?)</pubDate>", item)
        source_match = re.search(r"<source>(.*?)</source>", item)

        if not title_match:
            continue
        title = _unescape_xml(title_match.group(1))
        link = link_match.group(1) if link_match else ""

        # 黑名单过滤
        if any(re.search(p, title, re.I) for p in BLACKLIST_PATTERNS):
            continue

        pub_date = ""
        if date_match:
            try:
                # RSS pubDate 格式: "Thu, 30 Apr 2026 12:00:00 GMT"
                dt = datetime.strptime(
                    date_match.group(1)[:25], "%a, %d %b %Y %H:%M:%S"
                )
                pub_date = dt.strftime("%Y-%m-%d")
            except ValueError:
                pub_date = date.today().isoformat()
        else:
            pub_date = date.today().isoformat()

        source_name = source_match.group(1) if source_match else "Google News"

        articles.append({
            "title": title,
            "url": link,
            "date": pub_date,
            "source": source_name,
        })

    return articles


def _unescape_xml(text: str) -> str:
    """XML 实体解码"""
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&apos;", "'")
    # 去掉 CDATA
    text = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", text)
    return text.strip()


# ═══════════════════════════════════════════════════
# AI 分析层
# ═══════════════════════════════════════════════════

def _analyze_with_ai(title: str, person_name: str) -> dict:
    """用 DeepSeek AI 从新闻标题中提取观点、情绪、关联Ticker
    
    返回: {"statement": str, "sentiment": str, "tickers": str, "topics": str}
    """
    try:
        from openai import OpenAI
        client = OpenAI(
            base_url="https://api.deepseek.com/v1",
            api_key=Path.home().joinpath(
                ".hermes", "config.yaml"
            ).read_text() if False else "",  # will be set from env
        )
    except ImportError:
        pass  # fallback to keyword-based

    # 简单关键词分析作为 fallback
    return _classify_by_keywords(title, person_name)


def _classify_by_keywords(title: str, person_name: str) -> dict:
    """基于关键词的情绪和关联Ticker提取"""
    title_lower = title.lower()

    # 情绪判断
    positive_words = [
        "bullish", "buy", "great", "amazing", "breakthrough", "growth",
        "opportunity", "innovation", "strong", "up", "rally", "gain",
        "看好", "买入", "利好", "突破", "增长", "乐观", "上涨", "做多",
    ]
    negative_words = [
        "bearish", "sell", "risk", "warning", "crash", "drop", "concern",
        "uncertainty", "down", "problem", "fall", "decline", "loss",
        "看空", "卖出", "风险", "下跌", "利空", "问题", "悲观", "做空",
    ]
    pos_score = sum(1 for w in positive_words if w in title_lower)
    neg_score = sum(1 for w in negative_words if w in title_lower)
    sentiment = "positive" if pos_score > neg_score else ("negative" if neg_score > pos_score else "neutral")

    # Ticker 提取 (\$NVDA 或常见大写缩写)
    tickers = re.findall(r'\$([A-Z]{1,5})', title)

    # 常见股票名/主题词匹配
    ticker_map = {
        "bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL", "bnb": "BNB",
        "tesla": "TSLA", "apple": "AAPL", "nvidia": "NVDA", "microsoft": "MSFT",
        "amazon": "AMZN", "google": "GOOGL", "meta": "META", "berkshire": "BRK.A",
        "sp500": "SPY", "qqq": "QQQ",
        "hyperliquid": "HYPE", "ondo": "ONDO", "chainlink": "LINK",
        "microstrategy": "MSTR", "strategy": "MSTR",
    }
    for word, ticker in ticker_map.items():
        if word in title_lower and ticker not in tickers:
            tickers.append(ticker)

    # 主题提取
    topic_keywords = {
        "AI/科技": ["ai", "artificial intelligence", "machine learning", "chatgpt",
                     "openai", "llm", "大模型", "人工智能", "半导体"],
        "加密货币": ["bitcoin", "crypto", "ethereum", "blockchain", "btc", "eth",
                     "加密", "区块链", "数字资产"],
        "宏观/利率": ["fed", "federal reserve", "interest rate", "inflation",
                      "cpi", "利率", "降息", "加息", "通胀", "美联储"],
        "新能源": ["ev", "electric vehicle", "tesla", "新能源", "电动车"],
        "医药": ["biotech", "pharma", "genome", "医疗", "医药", "基因"],
        "消费": ["consumer", "retail", "消费", "白酒"],
        "RWA/代币化": ["tokenized", "tokenization", "rwa", "real world asset",
                       "代币化", "rwa资产", "链上资产", "hyperliquid", "ondo finance",
                       "buidl", "securitize", "onchain fund"],
    }
    topics = []
    for topic, keywords in topic_keywords.items():
        if any(kw in title_lower for kw in keywords):
            topics.append(topic)

    return {
        "statement": title,
        "sentiment": sentiment,
        "tickers": ",".join(set(tickers)),
        "topics": ",".join(topics),
    }


# ═══════════════════════════════════════════════════
# 执行入口
# ═══════════════════════════════════════════════════

def fetch_all_news(max_articles_per_person: int = 3) -> dict:
    """抓取所有关键人物的最新新闻言论并入库"""
    people = get_key_people()
    results = {
        "total_fetched": 0,
        "total_saved": 0,
        "by_person": {},
        "errors": [],
    }

    for p in people:
        name = p["name"]
        articles = fetch_person_news(name, max_articles_per_person)
        if not articles:
            results["by_person"][name] = {"fetched": 0, "saved": 0}
            continue

        results["total_fetched"] += len(articles)
        saved = 0

        for art in articles:
            try:
                # 用 AI/关键词分析
                analysis = _classify_by_keywords(art["title"], name)

                save_statement(
                    person_id=p["id"],
                    market=p["market"],
                    source=f"news:{art.get('source', 'Google News')}",
                    statement=art["title"],
                    sentiment=analysis["sentiment"],
                    related_tickers=analysis["tickers"],
                    related_topics=analysis["topics"],
                    source_url=art.get("url", ""),
                    statement_date=art.get("date", date.today().isoformat()),
                )
                saved += 1
            except Exception as e:
                results["errors"].append(f"{name}: {e}")

        results["total_saved"] += saved
        results["by_person"][name] = {"fetched": len(articles), "saved": saved}
        print(f"[news_fetcher] {name}: {len(articles)} fetched, {saved} saved", flush=True)

        time.sleep(0.5)  # 礼貌间隔

    return results


def is_available() -> bool:
    """检查网络连接是否正常（curl 可用性）"""
    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", "5", "https://news.google.com"],
            capture_output=True, text=True, timeout=10
        )
        return r.returncode == 0
    except Exception:
        return False


def run_once() -> dict:
    """一键抓取（供 API / cron 调用）"""
    if not is_available():
        return {"status": "error", "message": "网络不可达（Google News）"}
    result = fetch_all_news(max_articles_per_person=3)
    result["status"] = "ok"
    return result


# ═══════════════════════════════════════════════════
# 测试入口
# ═══════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    test_person = sys.argv[1] if len(sys.argv) > 1 else "Cathie Wood"
    print(f"测试抓取: {test_person}")
    articles = fetch_person_news(test_person, 3)
    for a in articles:
        analysis = _classify_by_keywords(a["title"], test_person)
        print(f"  [{a['date']}] {a['title']}")
        print(f"    → 情绪: {analysis['sentiment']}, Ticker: {analysis['tickers']}, 主题: {analysis['topics']}")
    print(f"\n共 {len(articles)} 条")
