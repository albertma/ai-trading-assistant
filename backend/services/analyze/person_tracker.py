"""
关键人物言论追踪服务 (Person Statement Tracker)
追踪三个市场(美股/A股/加密)中关键人物的公开言论,
为叙事分析提供「人说了什么」的上下文。
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

DB_PATH = Path.home() / "Jarvis" / "ai_trading" / "stock_archive.db"


# ── 数据定义 ────────────────────────────────────────

KEY_PEOPLE = [
    # ── 美股 ──
    {"market": "us", "name": "Cathie Wood", "handle": "@CathieWood",
     "title": "ARK Invest CEO", "category": "科技/创新",
     "x_account": "CathieWood", "relevance": "科技股叙事风向标"},
    {"market": "us", "name": "Elon Musk", "handle": "@elonmusk",
     "title": "Tesla / xAI CEO", "category": "科技/加密",
     "x_account": "elonmusk", "relevance": "AI/DOGE/机器人"},
    {"market": "us", "name": "Michael Saylor", "handle": "@saylor",
     "title": "Strategy (MicroStrategy) 董事长", "category": "加密/企业",
     "x_account": "saylor", "relevance": "BTC机构化叙事"},
    {"market": "us", "name": "Jerome Powell", "handle": "—",
     "title": "美联储主席", "category": "宏观",
     "x_account": "", "relevance": "利率/货币政策"},
    {"market": "us", "name": "Warren Buffett", "handle": "—",
     "title": "Berkshire Hathaway CEO", "category": "价值投资",
     "x_account": "", "relevance": "13F持仓/股东信"},
    {"market": "us", "name": "Bill Ackman", "handle": "@BillAckman",
     "title": "Pershing Square CEO", "category": "对冲基金",
     "x_account": "BillAckman", "relevance": "宏观/激进投资"},
    {"market": "us", "name": "David Einhorn", "handle": "—",
     "title": "Greenlight Capital", "category": "对冲基金",
     "x_account": "", "relevance": "价值/做空观点"},
    {"market": "us", "name": "Ming-Chi Kuo", "handle": "@mingchikuo",
     "title": "天风国际证券分析师", "category": "供应链",
     "x_account": "mingchikuo", "relevance": "苹果/半导体供应链"},
    {"market": "us", "name": "Stanley Druckenmiller", "handle": "—",
     "title": "Duquesne Family Office", "category": "宏观",
     "x_account": "", "relevance": "宏观/大仓位变动"},
    # ── A股 ──
    {"market": "cn", "name": "但斌", "handle": "但斌",
     "title": "东方港湾投资董事长", "category": "消费/科技",
     "x_account": "", "relevance": "白酒/互联网/科技龙头"},
    {"market": "cn", "name": "林园", "handle": "林园",
     "title": "林园投资董事长", "category": "消费/医药",
     "x_account": "", "relevance": "白酒/医药/高股息"},
    {"market": "cn", "name": "李蓓", "handle": "李蓓",
     "title": "半夏投资创始合伙人", "category": "宏观对冲",
     "x_account": "", "relevance": "宏观/地产/周期"},
    {"market": "cn", "name": "管清友", "handle": "管清友",
     "title": "经济学家", "category": "宏观",
     "x_account": "", "relevance": "宏观经济/政策解读"},
    # ── 加密货币 ──
    {"market": "crypto", "name": "CZ (Binance)", "handle": "@cz_binance",
     "title": "Binance 创始人", "category": "交易所",
     "x_account": "cz_binance", "relevance": "交易所生态/监管"},
    {"market": "crypto", "name": "Vitalik Buterin", "handle": "@VitalikButerin",
     "title": "以太坊创始人", "category": "公链",
     "x_account": "VitalikButerin", "relevance": "ETH/L2/技术路线"},
    {"market": "crypto", "name": "Arthur Hayes", "handle": "@cryptoHayes",
     "title": "BitMEX 联合创始人", "category": "宏观/交易",
     "x_account": "cryptoHayes", "relevance": "宏观/周期/加密市场"},
    {"market": "crypto", "name": "Murad Mahmudov", "handle": "@MustStopMurad",
     "title": "独立研究员", "category": "链上分析",
     "x_account": "MustStopMurad", "relevance": "链上数据/周期"},
]


# ── 数据库操作 ──────────────────────────────────────

def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    _ensure_tables(conn)
    return conn


def _ensure_tables(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS key_people (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market TEXT NOT NULL,
            name TEXT NOT NULL,
            handle TEXT DEFAULT '',
            title TEXT DEFAULT '',
            category TEXT DEFAULT '',
            x_account TEXT DEFAULT '',
            relevance TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(name, market)
        );

        CREATE TABLE IF NOT EXISTS person_statements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL,
            market TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'x',
            source_url TEXT DEFAULT '',
            statement TEXT NOT NULL,
            sentiment TEXT DEFAULT 'neutral',
            related_tickers TEXT DEFAULT '',
            related_topics TEXT DEFAULT '',
            statement_date TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (person_id) REFERENCES key_people(id)
        );

        CREATE INDEX IF NOT EXISTS idx_statements_date ON person_statements(statement_date);
        CREATE INDEX IF NOT EXISTS idx_statements_market ON person_statements(market);
        CREATE INDEX IF NOT EXISTS idx_statements_person ON person_statements(person_id);
    """)


def init_people():
    """初始化关键人物种子数据（幂等）"""
    conn = _get_db()
    for p in KEY_PEOPLE:
        conn.execute("""
            INSERT OR IGNORE INTO key_people (market, name, handle, title, category, x_account, relevance)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (p["market"], p["name"], p["handle"], p["title"], p["category"], p["x_account"], p["relevance"]))
    conn.commit()
    conn.close()


def get_key_people(market: str | None = None) -> list[dict]:
    """获取关键人物列表，可按市场筛选"""
    conn = _get_db()
    if market and market != "all":
        rows = conn.execute(
            "SELECT * FROM key_people WHERE market = ? ORDER BY market, name", (market,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM key_people ORDER BY market, name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_statement(person_id: int, market: str, source: str, statement: str,
                   sentiment: str = "neutral", related_tickers: str = "",
                   related_topics: str = "", source_url: str = "",
                   statement_date: str | None = None) -> int:
    """保存一条人物言论"""
    if not statement_date:
        statement_date = date.today().isoformat()
    conn = _get_db()
    cur = conn.execute("""
        INSERT INTO person_statements
            (person_id, market, source, source_url, statement, sentiment, related_tickers, related_topics, statement_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (person_id, market, source, source_url, statement, sentiment, related_tickers, related_topics, statement_date))
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def get_statements(market: str | None = None, days: int = 3,
                   limit: int = 30, person_id: int | None = None) -> list[dict]:
    """获取近期人物言论，可按市场和人物筛选"""
    since = (date.today() - timedelta(days=days)).isoformat()
    conn = _get_db()
    where_clauses = ["s.statement_date >= ?"]
    params = [since]

    if market and market != "all":
        where_clauses.append("s.market = ?")
        params.append(market)
    if person_id:
        where_clauses.append("s.person_id = ?")
        params.append(person_id)

    where_str = " AND ".join(where_clauses)
    rows = conn.execute(f"""
        SELECT s.*, p.name as person_name, p.handle as person_handle,
               p.title as person_title, p.category as person_category
        FROM person_statements s
        JOIN key_people p ON s.person_id = p.id
        WHERE {where_str}
        ORDER BY s.statement_date DESC, s.id DESC
        LIMIT ?
    """, (*params, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_statements_as_context(days: int = 3, max_statements: int = 15) -> str:
    """生成供AI prompt注入的人物言论上下文文本"""
    statements = get_statements(days=days, limit=max_statements)
    if not statements:
        return ""
    lines = ["## 📢 近期关键人物言论（叙事信号源）\n"]
    for s in statements:
        sentiment_icon = {"positive": "📈", "negative": "📉", "neutral": "📌"}.get(s["sentiment"], "📌")
        lines.append(
            f"- {sentiment_icon} **{s['person_name']}** ({s['person_handle']}, {s['market'].upper()}) "
            f"[{s['statement_date']}]: "
            f"{s['statement']}"
        )
        if s.get("related_tickers"):
            lines[-1] += f"  → 相关: {s['related_tickers']}"
    return "\n".join(lines)


# ── 按人物汇总分析 ──────────────────────────────


def get_person_summary(market: str | None = None, days: int = 7) -> list[dict]:
    """按人物汇总近期言论：情绪分布、关联Ticker、AI总结

    返回: [{
        person_id, person_name, person_handle, person_title, person_category,
        market, statement_count,
        sentiment_distribution: {positive: N, negative: N, neutral: N},
        top_tickers: ["BTC", "TSLA", ...],
        top_topics: ["AI/科技", "加密货币", ...],
        latest_statements: [...],
        summary: str (AI生成的总结),
    }, ...]
    """
    people = get_key_people(market)
    statements = get_statements(market, days=days, limit=200)

    # 按 person_id 分组
    by_person: dict[int, dict] = {}
    for p in people:
        by_person[p["id"]] = {
            "person_id": p["id"],
            "person_name": p["name"],
            "person_handle": p["handle"],
            "person_title": p["title"],
            "person_category": p["category"],
            "market": p["market"],
            "statement_count": 0,
            "sentiment_distribution": {"positive": 0, "negative": 0, "neutral": 0},
            "ticker_counts": {},
            "topic_counts": {},
            "statements": [],
        }

    for s in statements:
        pid = s["person_id"]
        if pid not in by_person:
            continue
        entry = by_person[pid]
        entry["statement_count"] += 1
        sent = s["sentiment"]
        if sent in entry["sentiment_distribution"]:
            entry["sentiment_distribution"][sent] += 1
        else:
            entry["sentiment_distribution"]["neutral"] += 1

        # 统计 Ticker
        for t in s.get("related_tickers", "").split(","):
            t = t.strip()
            if t:
                entry["ticker_counts"][t] = entry["ticker_counts"].get(t, 0) + 1

        # 统计 Topic
        for tp in s.get("related_topics", "").split(","):
            tp = tp.strip()
            if tp:
                entry["topic_counts"][tp] = entry["topic_counts"].get(tp, 0) + 1

        entry["statements"].append(s)

    # 排序 & 格式化输出
    result = []
    for pid, entry in by_person.items():
        # 按日期排序言论（最新的在前）
        entry["statements"].sort(key=lambda x: x["statement_date"], reverse=True)

        # 取前5条最新言论
        entry["latest_statements"] = entry["statements"][:5]

        # Top tickers
        sorted_tickers = sorted(
            entry["ticker_counts"].items(), key=lambda x: -x[1]
        )
        entry["top_tickers"] = [t for t, _ in sorted_tickers[:5]]

        # Top topics
        sorted_topics = sorted(
            entry["topic_counts"].items(), key=lambda x: -x[1]
        )
        entry["top_topics"] = [t for t, _ in sorted_topics[:5]]

        # 清除原始 statements 列表（太大）
        del entry["statements"]

        result.append(entry)

    # 按 statement_count 降序排列
    result.sort(key=lambda x: -x["statement_count"])
    return result


# ── 言论去重 ──────────────────────────────


def deduplicate_statements(days: int = 30) -> dict:
    """对近期同一个人含义相似的言论去重，保留最早/链接最完整的一条"""
    from difflib import SequenceMatcher

    conn = _get_db()
    since = (date.today() - timedelta(days=days)).isoformat()

    # 获取所有近期言论，按 person_id 分组
    rows = conn.execute("""
        SELECT id, person_id, statement, source_url, statement_date
        FROM person_statements
        WHERE statement_date >= ?
        ORDER BY person_id, statement_date DESC
    """, (since,)).fetchall()

    by_person: dict[int, list[dict]] = {}
    for r in rows:
        by_person.setdefault(r["person_id"], []).append(dict(r))

    SIMILARITY_THRESHOLD = 0.65  # 相似度门槛
    deleted = 0
    kept = 0

    for pid, stmts in by_person.items():
        if len(stmts) < 2:
            continue

        # 按日期降序，保留最新的，删除老重复的
        to_remove: set[int] = set()
        for i in range(len(stmts)):
            if stmts[i]["id"] in to_remove:
                continue
            for j in range(i + 1, len(stmts)):
                if stmts[j]["id"] in to_remove:
                    continue
                # 比较文本相似度
                a = stmts[i]["statement"].lower()
                b = stmts[j]["statement"].lower()
                ratio = SequenceMatcher(None, a, b).ratio()
                if ratio >= SIMILARITY_THRESHOLD:
                    # 保留有链接的或日期更新的
                    keep_i_url = bool(stmts[i].get("source_url", ""))
                    keep_j_url = bool(stmts[j].get("source_url", ""))
                    if keep_i_url and not keep_j_url:
                        to_remove.add(stmts[j]["id"])
                    elif keep_j_url and not keep_i_url:
                        to_remove.add(stmts[i]["id"])
                    else:
                        # 都没链接或都有链接，留新的
                        to_remove.add(stmts[j]["id"])

        if to_remove:
            ids_str = ",".join(str(x) for x in to_remove)
            conn.execute(f"DELETE FROM person_statements WHERE id IN ({ids_str})")
            deleted += len(to_remove)
            kept += len(stmts) - len(to_remove)

    conn.commit()
    conn.close()
    return {"deleted": deleted, "kept": kept}


# ── 启动初始化 ──────────────────────────────────────

def init():
    """启动时调用：确保表存在 + 种子数据"""
    conn = _get_db()
    conn.close()
    init_people()
