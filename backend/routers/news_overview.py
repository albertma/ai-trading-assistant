"""新闻聚合 API — 中美欧日产业/财经/政治新闻"""
from fastapi import APIRouter, HTTPException
import urllib.request, urllib.parse
import xml.etree.ElementTree as ET
import re, json
from datetime import datetime

router = APIRouter(tags=["新闻聚合"])

# 新闻源配置：地区 + 分类 → 搜索关键词
NEWS_SOURCES = {
    "中国": {
        "icon": "🇨🇳",
        "categories": {
            "产业": "A股 产业 行业 新能源 半导体 AI 汽车",
            "财经": "中国经济 财经 政策 央行 A股市场",
            "政治": "中国 政治 外交 政策 中美",
        }
    },
    "美国": {
        "icon": "🇺🇸",
        "categories": {
            "产业": "US industry tech AI semiconductor automotive",
            "财经": "US economy Fed stock market finance",
            "政治": "US politics policy tariff election",
        }
    },
    "欧洲": {
        "icon": "🇪🇺",
        "categories": {
            "产业": "Europe industry tech auto AI energy",
            "财经": "European economy ECB finance market",
            "政治": "Europe politics EU policy geopolitics",
        }
    },
    "日本": {
        "icon": "🇯🇵",
        "categories": {
            "产业": "日本 产业 半导体 AI 汽车 科技",
            "财经": "日本 经济 央行 日经 财经",
            "政治": "日本 政治 外交 政策",
        }
    },
    "加密": {
        "icon": "🪙",
        "categories": {
            "市场": "Bitcoin Ethereum crypto market price blockchain DeFi",
            "生态": "Solana Ethereum L2 DeFi NFT Web3 dApp",
            "监管": "crypto regulation SEC stablecoin ETF policy",
        }
    },
}


def _fetch_google_news(query: str, max_results: int = 8) -> list[dict]:
    """从 Google News RSS 抓取新闻（5s超时）"""
    try:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=zh-CN&gl=CN"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        resp = urllib.request.urlopen(req, timeout=5)
        html = resp.read().decode("utf-8", errors="replace")

        # 解析 RSS XML
        items = []
        # 简单方法：直接提取 <item> 块
        for item_match in re.finditer(r'<item>(.*?)</item>', html, re.DOTALL):
            item_xml = item_match.group(1)
            title_m = re.search(r'<title>(.*?)</title>', item_xml)
            link_m = re.search(r'<link>(.*?)</link>', item_xml)
            date_m = re.search(r'<pubDate>(.*?)</pubDate>', item_xml)
            source_m = re.search(r'<source>(.*?)</source>', item_xml)
            desc_m = re.search(r'<description>(.*?)</description>', item_xml)

            title = title_m.group(1) if title_m else ""
            # 清理 HTML 实体
            title = title.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"').replace('&#39;', "'")
            if not title or title == "Google 新闻":
                continue

            link = link_m.group(1) if link_m else ""
            pub_date = date_m.group(1) if date_m else ""
            source = source_m.group(1) if source_m else ""
            desc = desc_m.group(1) if desc_m else ""
            desc = desc.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"').replace('&#39;', "'")
            # 清理 HTML tag
            desc = re.sub(r'<[^>]+>', '', desc)[:200]

            items.append({
                "title": title,
                "link": link,
                "source": source,
                "published": pub_date,
                "summary": desc[:150],
            })

            if len(items) >= max_results:
                break
        return items
    except Exception as e:
        return []


@router.get("/news/overview")
def get_news_overview(region: str = "", category: str = ""):
    """获取新闻概览

    参数:
        region: 地区筛选 (中国/美国/欧洲/日本)，为空返回全部
        category: 分类筛选 (产业/财经/政治)，为空返回全部
    """
    results = {}
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # 收集所有要抓取的任务
    tasks = []
    for reg_name, reg_info in NEWS_SOURCES.items():
        if region and reg_name != region:
            continue
        for cat_name, query in reg_info["categories"].items():
            if category and cat_name != category:
                continue
            tasks.append((reg_name, cat_name, query))

    # 并发抓取
    def fetch_task(reg, cat, q):
        news = _fetch_google_news(q, max_results=5)
        return reg, cat, news

    with ThreadPoolExecutor(max_workers=8) as pool:
        fut_map = {pool.submit(fetch_task, r, c, q): (r, c) for r, c, q in tasks}
        for fut in as_completed(fut_map, timeout=30):
            reg_name, cat_name, news = fut.result()
            if reg_name not in results:
                results[reg_name] = {"name": reg_name, "icon": NEWS_SOURCES[reg_name]["icon"], "categories": {}}
            results[reg_name]["categories"][cat_name] = news

    return {"success": True, "data": results, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M")}
