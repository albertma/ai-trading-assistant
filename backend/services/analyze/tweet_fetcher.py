"""
X/Twitter 推文抓取服务
定时拉取关键人物的最新推文，保存到 person_statements 表。
依赖 xurl CLI（需预先配置 X API 认证）。
"""
from __future__ import annotations

import json
import subprocess
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from backend.services.analyze.person_tracker import (
    _get_db, get_key_people, save_statement
)


def is_xurl_available() -> bool:
    """检查 xurl 是否安装且已认证"""
    try:
        r = subprocess.run(["xurl", "auth", "status"],
                           capture_output=True, text=True, timeout=10)
        return "No apps registered" not in r.stdout and "error" not in r.stdout.lower()
    except Exception:
        return False


def fetch_user_tweets(handle: str, count: int = 10) -> list[dict]:
    """用 xurl 拉取某用户的最新推文"""
    try:
        r = subprocess.run(
            ["xurl", "search", f"from:{handle}", "-n", str(count)],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode != 0:
            print(f"[tweet_fetcher] xurl error for @{handle}: {r.stderr[:200]}", flush=True)
            return []
        data = json.loads(r.stdout)
        tweets = data.get("data", [])
        if isinstance(tweets, dict):
            tweets = [tweets]
        result = []
        for t in tweets:
            if isinstance(t, dict) and "text" in t:
                result.append({
                    "id": t.get("id", ""),
                    "text": t.get("text", ""),
                    "created_at": t.get("created_at", date.today().isoformat()),
                })
        return result
    except json.JSONDecodeError:
        print(f"[tweet_fetcher] JSON parse error for @{handle}", flush=True)
        return []
    except Exception as e:
        print(f"[tweet_fetcher] Error fetching @{handle}: {e}", flush=True)
        return []


def _classify_sentiment(text: str) -> str:
    """简单基于关键词的情绪分类"""
    text_lower = text.lower()
    positive_words = ["bullish", "buy", "great", "amazing", "breakthrough",
                      "growth", "opportunity", "innovation", "strong", "up",
                      "看多", "看好", "买入", "利好", "突破", "增长"]
    negative_words = ["bearish", "sell", "risk", "warning", "crash", "drop",
                      "concern", "uncertainty", "down", "problem",
                      "看空", "卖出", "风险", "下跌", "利空", "问题"]
    pos_score = sum(1 for w in positive_words if w in text_lower)
    neg_score = sum(1 for w in negative_words if w in text_lower)
    if pos_score > neg_score:
        return "positive"
    elif neg_score > pos_score:
        return "negative"
    return "neutral"


def _extract_tickers(text: str) -> str:
    """提取可能的 ticker 引用 ($BTC, $NVDA 等)"""
    import re
    tickers = re.findall(r'\$([A-Z]{1,5})', text)
    return ",".join(tickers)


def fetch_all_people_tweets(max_per_person: int = 5) -> dict:
    """拉取所有有关键人物 X 账号的推文并入库"""
    people = get_key_people()
    results = {"total_fetched": 0, "total_saved": 0, "errors": []}

    for p in people:
        handle = p.get("x_account", "")
        if not handle:
            continue

        tweets = fetch_user_tweets(handle, max_per_person)
        if not tweets:
            continue

        results["total_fetched"] += len(tweets)
        saved = 0
        for t in tweets:
            try:
                sentiment = _classify_sentiment(t["text"])
                tickers = _extract_tickers(t["text"])
                tweet_date = t.get("created_at", "")[:10]
                if not tweet_date:
                    tweet_date = date.today().isoformat()

                save_statement(
                    person_id=p["id"],
                    market=p["market"],
                    source="x",
                    statement=t["text"],
                    sentiment=sentiment,
                    related_tickers=tickers,
                    source_url=f"https://x.com/{handle}/status/{t['id']}",
                    statement_date=tweet_date,
                )
                saved += 1
            except Exception as e:
                results["errors"].append(f"{handle}: {e}")

        results["total_saved"] += saved
        print(f"[tweet_fetcher] @{handle}: {len(tweets)} fetched, {saved} saved", flush=True)

        # 避免触发 X API 限频
        time.sleep(1)

    return results


def run_once() -> dict:
    """供 cron 任务调用：一键拉取所有关键人物推文"""
    if not is_xurl_available():
        return {"status": "error", "message": "xurl not available or not authenticated"}
    return fetch_all_people_tweets(max_per_person=5)
