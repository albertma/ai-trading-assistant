"""
市场叙事分析服务
用AI动态发现市场叙事主题，定位生命周期阶段，追踪证实/证伪信号
支持按日期存储/查询，AI分析时注入前日叙事作为上下文
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
from openai import OpenAI

from backend.services.external.csv_client import find_latest_csv, _read_csv, _parse_csv_date

ARCHIVE_DB = os.path.expanduser("~/Jarvis/ai_trading/stock_archive.db")


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(ARCHIVE_DB)
    conn.row_factory = sqlite3.Row
    _ensure_table(conn)
    return conn


def _ensure_table(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS narratives_cache (
            date TEXT PRIMARY KEY,
            narratives TEXT NOT NULL,
            market_avg_change REAL,
            total_stocks INTEGER,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)


def _get_deepseek_client() -> OpenAI:
    """复用已有 DeepSeek API 客户端"""
    from pathlib import Path
    import yaml
    config_path = Path.home() / ".hermes" / "config.yaml"
    try:
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        providers = cfg.get("custom_providers", [])
        for p in providers:
            if p.get("name") == "deepseek-v4-flash":
                return OpenAI(api_key=p["api_key"], base_url=p["base_url"])
        return OpenAI(
            api_key=cfg.get("model", {}).get("api_key", ""),
            base_url=cfg.get("model", {}).get("base_url", "https://api.deepseek.com"),
        )
    except Exception:
        return OpenAI(api_key="", base_url="https://api.deepseek.com")


# ── 叙事生命周期定义 ────────────────────────────────

NARRATIVE_LIFECYCLE_STAGES = {
    "萌芽": {
        "score_range": (0, 25),
        "desc": "叙事刚刚出现，市场关注度低，只有少数独立事件或个别股票异动",
        "color": "#909399",
    },
    "发酵": {
        "score_range": (26, 50),
        "desc": "叙事开始被市场讨论，相关板块联动上涨，但尚未形成共识",
        "color": "#409eff",
    },
    "高潮": {
        "score_range": (51, 75),
        "desc": "叙事成为市场主线，板块全面爆发，龙头股大幅上涨，成交量放大",
        "color": "#e6a23c",
    },
    "退潮": {
        "score_range": (76, 90),
        "desc": "叙事热度开始下降，板块内部分化，龙头走弱，资金流出",
        "color": "#f56c6c",
    },
    "证伪": {
        "score_range": (91, 100),
        "desc": "核心逻辑被证伪，板块大幅下跌，资金撤离",
        "color": "#909399",
    },
}

# ── 认知偏差映射 ──────────────────────────────────────

BIAS_MAP = {
    "availability": "可得性启发 — 近期大涨个股/板块更容易被注意到",
    "confirmation": "确认偏误 — 更容易接受支持已有叙事的信息",
    "recency": "近因效应 — 最近的事件被过度放大",
    "anchoring": "锚定效应 — 早期价格/估值成为非理性参考点",
    "narrative_parsimony": "叙事简约 — 简单故事更容易传播和信服",
    "herding": "羊群效应 — 跟风买入，强化趋势",
    "hindsight": "事后聪明 — 事件后觉得'早就应该想到'",
}


def get_market_snapshot(csv_date_str: str | None = None) -> dict | None:
    """从CSV获取市场快照。csv_date_str 指定日期，None则自动找最新"""
    if csv_date_str:
        from backend.config import MARKET_DATA_DIR
        from pathlib import Path
        path = MARKET_DATA_DIR / f"沪深京A股{csv_date_str}.csv"
        if not path.exists():
            return None
        csv_path = str(path)
    else:
        csv_path = find_latest_csv()
    if not csv_path:
        return None
    csv_date = _parse_csv_date(csv_path)
    df = _read_csv(csv_path)
    if df is None or df.empty:
        return None

    # 统一列名
    col_map = {}
    for c in df.columns:
        cl = c.strip()
        if cl in ("代码",):
            col_map["代码"] = cl
        elif cl in ("名称",):
            col_map["名称"] = cl
        elif cl in ("涨幅", "涨跌幅", "change_pct"):
            col_map["涨幅"] = cl
        elif cl in ("所属行业", "行业", "sector"):
            col_map["行业"] = cl
        elif cl in ("成交额", "成交额(元)", "amount"):
            col_map["成交额"] = cl
        elif cl in ("总市值",):
            col_map["总市值"] = cl
        elif cl in ("市盈率", "pe"):
            col_map["市盈率"] = cl
        elif cl in ("换手率", "换手", "turnover"):
            col_map["换手率"] = cl

    rename = {}
    for k, v in col_map.items():
        rename[v] = k
    df = df.rename(columns=rename)

    for col in ("涨幅", "成交额", "总市值", "市盈率", "换手率"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", "", regex=False).str.replace("%", "", regex=False), errors="coerce")

    valid = df[df["涨幅"].notna()].copy()
    total = len(valid)
    up = int((valid["涨幅"] > 0).sum())
    down = int((valid["涨幅"] < 0).sum())
    avg_chg = round(float(valid["涨幅"].mean()), 2)

    top_volume = []
    if "成交额" in df.columns:
        vol_sorted = valid.dropna(subset=["成交额"]).sort_values("成交额", ascending=False).head(10)
        for _, r in vol_sorted.iterrows():
            top_volume.append({
                "name": r.get("名称", ""),
                "change_pct": r.get("涨幅"),
                "volume_yi": round(r["成交额"] / 1e8, 2) if r["成交额"] else 0,
                "sector": r.get("行业", ""),
            })

    top_gainers = []
    for _, r in valid.sort_values("涨幅", ascending=False).head(20).iterrows():
        top_gainers.append({
            "name": r.get("名称", ""),
            "change_pct": r.get("涨幅"),
            "sector": r.get("行业", ""),
            "volume_yi": round(r.get("成交额", 0) / 1e8, 2) if r.get("成交额") else 0,
        })

    top_losers = []
    for _, r in valid.sort_values("涨幅", ascending=True).head(20).iterrows():
        top_losers.append({
            "name": r.get("名称", ""),
            "change_pct": r.get("涨幅"),
            "sector": r.get("行业", ""),
        })

    sector_stats = {}
    if "行业" in df.columns:
        sector_valid = valid[valid["行业"].notna() & (valid["行业"] != "--")].copy()
        if not sector_valid.empty:
            for sector, grp in sector_valid.groupby("行业"):
                chgs = grp["涨幅"].dropna()
                if len(chgs) == 0:
                    continue
                sector_stats[sector] = {
                    "avg_change": round(float(chgs.mean()), 2),
                    "stock_count": int(len(chgs)),
                    "up_count": int((chgs > 0).sum()),
                    "top_stock": grp.sort_values("涨幅", ascending=False).iloc[0].get("名称", ""),
                    "top_change": round(float(chgs.max()), 2),
                }

    sorted_sectors = sorted(sector_stats.items(), key=lambda x: x[1]["avg_change"], reverse=True)
    top_sectors = sorted_sectors[:15]
    bottom_sectors = sorted_sectors[-10:] if len(sorted_sectors) > 10 else []

    return {
        "date": csv_date,
        "total_stocks": total,
        "up": up,
        "down": down,
        "avg_change": avg_chg,
        "top_gainers": top_gainers,
        "top_losers": top_losers,
        "top_volume": top_volume,
        "top_sectors": [
            {"name": s[0], "avg_change": s[1]["avg_change"],
             "stock_count": s[1]["stock_count"],
             "up_count": s[1]["up_count"],
             "top_stock": s[1]["top_stock"],
             "top_change": s[1]["top_change"]}
            for s in top_sectors
        ],
        "bottom_sectors": [
            {"name": s[0], "avg_change": s[1]["avg_change"],
             "stock_count": s[1]["stock_count"],
             "up_count": s[1]["up_count"]}
            for s in bottom_sectors
        ],
        "sector_stats": sector_stats,
    }


def get_saved_narratives(target_date: str) -> list[dict]:
    """从SQLite读取指定日期的叙事分析结果"""
    try:
        conn = _get_db()
        row = conn.execute("SELECT narratives FROM narratives_cache WHERE date=?", (target_date,)).fetchone()
        conn.close()
        if row:
            return json.loads(row["narratives"])
    except Exception as e:
        print(f"[narrative] load from db failed: {e}", flush=True)
    return []


def get_prev_narratives(target_date: str, days: int = 3) -> list[dict]:
    """获取target_date之前最近N个有叙事数据的交易日的历史叙事（用于AI上下文注入）"""
    prev_all = []
    d = datetime.strptime(target_date, "%Y-%m-%d")
    for _ in range(days * 5):  # 最多找 days*5 天前的数据
        d -= timedelta(days=1)
        ds = d.strftime("%Y-%m-%d")
        prev = get_saved_narratives(ds)
        if prev:
            prev_all.append({"date": ds, "narratives": prev})
            if len(prev_all) >= days:
                break
    return prev_all


def save_narratives(target_date: str, narratives: list[dict], market_avg_change: float | None, total_stocks: int | None):
    """将叙事分析结果写入SQLite"""
    try:
        conn = _get_db()
        conn.execute(
            "INSERT OR REPLACE INTO narratives_cache (date, narratives, market_avg_change, total_stocks) VALUES (?, ?, ?, ?)",
            (target_date, json.dumps(narratives, ensure_ascii=False), market_avg_change, total_stocks),
        )
        conn.commit()
        conn.close()
        print(f"[narrative] saved {len(narratives)} narratives for {target_date}", flush=True)
    except Exception as e:
        print(f"[narrative] save to db failed: {e}", flush=True)


def analyze_narratives(market_snapshot: dict | None = None, force_date: str | None = None) -> list[dict]:
    """
    核心：用AI分析市场快照，发现叙事主题
    force_date: 指定分析哪天的数据，None则用最新
    自动加载前日叙事作为上下文
    """
    if market_snapshot is None:
        snapshot_date = force_date or date.today().isoformat()
        market_snapshot = get_market_snapshot(force_date)
    else:
        snapshot_date = market_snapshot.get("date", "")

    if market_snapshot is None:
        print(f"[narrative] no market data for {snapshot_date}", flush=True)
        return _fallback_narratives(market_snapshot)

    # 先查DB有没有已有结果
    existing = get_saved_narratives(snapshot_date)
    if existing:
        print(f"[narrative] found cached narratives for {snapshot_date}", flush=True)
        return existing

    # 加载前3个交易日的叙事作为上下文
    prev_narratives = get_prev_narratives(snapshot_date, days=3)

    try:
        client = _get_deepseek_client()
        snapshot_json = json.dumps(market_snapshot, ensure_ascii=False, indent=2)

        # 上下文：前几天的叙事
        prev_context = ""
        if prev_narratives:
            prev_context = "\n## 近期叙事历史（用于追踪趋势变化）\n"
            for pn in prev_narratives:
                prev_context += f"\n### {pn['date']}\n"
                for n in pn["narratives"]:
                    prev_context += f"- **{n['name']}** | 阶段:{n.get('lifecycle_stage','')} | 证实:{n.get('confirmation_score',0)}% ({n.get('confirmation_trend','')})\n"
                    prev_context += f"  逻辑: {n.get('description','')}\n"
                    prev_context += f"  证据: 支持{len(n.get('evidence_supporting',[]))}条 / 反对{len(n.get('evidence_contradicting',[]))}条\n"

        # 上下文：关键人物近期言论
        person_context = ""
        try:
            from backend.services.analyze.person_tracker import get_statements_as_context
            person_context = get_statements_as_context(days=5, max_statements=20)
        except Exception:
            pass

        prompt = f"""你是资深A股市场叙事分析师。根据 {snapshot_date} 的市场数据，找出当前市场中最重要的 5-8 个叙事主题（narratives）。

分析要求：
1. 如果某个叙事与前几天的叙事有延续性，请在描述中体现趋势变化（如"本周连续第三日发酵"、"较前日从发酵转为退潮"）
2. 对比前后日期的 evidence_supporting / evidence_contradicting，判断叙事是被证实还是被证伪
3. 前日处于高潮/退潮期的叙事如果今日数据不支持了，要如实反映（退化/消亡）
4. 结合下方关键人物近期言论，判断哪些叙事得到了权威人物的背书或质疑，并标注出**具体人物名字**
{prev_context}
{person_context}
## 市场数据快照
```json
{snapshot_json}
```

## 输出要求
请严格以JSON数组格式输出，不要有markdown包裹。每个元素包含以下字段：
- "name": 叙事名称，简短有力
- "description": 一句话描述核心逻辑
- "category": 所属大类（科技/新能源/医药/消费/金融/周期/军工/其他）
- "lifecycle_stage": 生命周期阶段，「萌芽」「发酵」「高潮」「退潮」「证伪」之一
- "lifecycle_score": 生命周期评分 0-100
- "trigger_event": 触发/驱动该叙事的关键事件
- "evidence_supporting": 支持该叙事的证据列表（基于实际数据，不要编造）
- "evidence_contradicting": 反对/削弱该叙事的证据列表
- "confirmation_score": 被证实程度 0-100
- "confirmation_trend": 趋势方向，「confirming」「disproving」「stable」之一
- "related_sectors": 相关板块/概念名称列表
|- "related_stocks": 相关个股名称列表
|- "related_people": 与叙事相关的关键人物名称列表（如Cathie Wood、但斌、CZ等），没有则不填
|- "biases": 认知偏差列表

请严格基于市场数据，不要编造。与前期叙事延续时，在description里标注趋势变化。"""

        resp = client.chat.completions.create(
            model="deepseek-v4-flash",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=4000,
            timeout=60,
        )

        content = resp.choices[0].message.content.strip()
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
        narratives = json.loads(content)

        if not isinstance(narratives, list):
            narratives = []

        seen = set()
        result = []
        for n in narratives:
            key = n.get("name", "")
            if not key or key in seen:
                continue
            seen.add(key)
            n["biases_detail"] = [
                {"name": b, "desc": BIAS_MAP.get(b, "")}
                for b in (n.get("biases") or [])
                if b in BIAS_MAP
            ]
            n["date"] = snapshot_date
            result.append(n)

        result = result[:10]

        # 保存到DB
        save_narratives(snapshot_date, result, market_snapshot.get("avg_change"), market_snapshot.get("total_stocks"))

        return result

    except Exception as e:
        print(f"[narrative] AI analysis failed: {e}", flush=True)
        fallback = _fallback_narratives(market_snapshot)
        if fallback:
            save_narratives(snapshot_date, fallback, market_snapshot.get("avg_change"), market_snapshot.get("total_stocks"))
        return fallback


def _fallback_narratives(market_snapshot: dict | None = None) -> list[dict]:
    """AI失败时的兜底：基于板块排名生成简单叙事"""
    if not market_snapshot:
        return []

    sectors = market_snapshot.get("top_sectors", [])[:8]
    narrative_map = {
        "人工智能": {"cat": "科技", "trigger": "AI概念活跃"},
        "半导体": {"cat": "科技", "trigger": "国产芯片替代"},
        "新能源车": {"cat": "新能源", "trigger": "新能源汽车销量增长"},
        "光伏": {"cat": "新能源", "trigger": "光伏装机超预期"},
        "医药": {"cat": "医药", "trigger": "医药政策利好"},
        "军工": {"cat": "军工", "trigger": "国防装备升级"},
        "消费": {"cat": "消费", "trigger": "消费复苏"},
        "金融": {"cat": "金融", "trigger": "金融政策利好"},
    }

    narratives = []
    seen_cats = set()
    for s in sectors:
        name = s["name"]
        avg = s.get("avg_change", 0) or 0
        # 先匹配关键词
        matched = None
        for keyword, info in narrative_map.items():
            if keyword in name or name in keyword:
                matched = keyword
                break
        if matched:
            stage = "发酵" if avg > 2 else ("萌芽" if avg > 0 else "退潮")
            score = min(int(40 + abs(avg) * 5), 100)
            cat = narrative_map[matched]["cat"]
            if cat in seen_cats:
                continue
            seen_cats.add(cat)
            narratives.append(_make_fallback_narrative(name, avg, matched, cat, narrative_map[matched]["trigger"], market_snapshot))
        else:
            # 兜底：关键词不匹配也生成（去掉行业后缀）
            base_name = name.replace("Ⅱ", "").replace("I", "").replace(" ", "")
            stage = "发酵" if avg > 2 else ("萌芽" if avg > 0 else "退潮")
            cat = "其他"
            trigger = f"{name}板块今日表现突出，平均涨幅{avg:+.1f}%"
            narratives.append(_make_fallback_narrative(name, avg, base_name, cat, trigger, market_snapshot))

    return narratives[:6]


def _make_fallback_narrative(name, avg, matched_name, cat, trigger, market_snapshot):
    """构造兜底叙事对象"""
    stage = "发酵" if avg > 2 else ("萌芽" if avg > 0 else "退潮")
    score = min(int(40 + abs(avg) * 5), 100)
    return {
        "name": matched_name,
        "description": f"{name}板块今日表现{'强势' if avg > 0 else '弱势'}，平均涨幅{avg:+.1f}%",
        "category": cat,
        "lifecycle_stage": stage,
        "lifecycle_score": score,
        "trigger_event": trigger,
        "evidence_supporting": [f"{name}板块今日涨幅{avg:+.1f}%"],
        "evidence_contradicting": [],
        "confirmation_score": 50 if avg > 0 else 30,
        "confirmation_trend": "confirming" if avg > 0 else "disproving",
        "related_sectors": [name],
        "related_stocks": [s.get("top_stock", "") for s in (market_snapshot.get("top_sectors") or []) if s.get("name") == name and s.get("top_stock")],
        "biases": ["recency", "herding"],
        "biases_detail": [
            {"name": "recency", "desc": BIAS_MAP.get("recency", "")},
            {"name": "herding", "desc": BIAS_MAP.get("herding", "")},
        ],
        "date": market_snapshot.get("date", date.today().isoformat()),
    }


def get_available_dates() -> list[str]:
    """获取有叙事数据的日期列表"""
    try:
        conn = _get_db()
        rows = conn.execute("SELECT date FROM narratives_cache ORDER BY date DESC").fetchall()
        conn.close()
        return [r["date"] for r in rows]
    except Exception:
        return []


def get_market_snapshot_for_date(target_date: str) -> dict | None:
    """获取某日市场快照，并合并该日叙事的DB记录"""
    snapshot = get_market_snapshot(target_date)
    if snapshot is None:
        return None
    saved = get_saved_narratives(target_date)
    if saved:
        snapshot["narratives"] = saved
    return snapshot


# ── 缓存 ──────────────────────────────────────────

_narrative_cache: dict = {}
_NARRATIVE_CACHE_TTL = 600


def get_cached_narratives(target_date: str | None = None) -> list[dict]:
    """带缓存的叙事分析。target_date 指定日期，None则用最新数据"""
    now = datetime.now().timestamp()
    cache_key = target_date or "latest"

    if cache_key in _narrative_cache:
        entry = _narrative_cache[cache_key]
        if now - entry["_time"] < _NARRATIVE_CACHE_TTL:
            return entry["narratives"]

    snapshot = get_market_snapshot(target_date)
    if snapshot is None:
        return []

    # 先看DB
    saved = get_saved_narratives(snapshot["date"])
    if saved:
        _narrative_cache[cache_key] = {"narratives": saved, "_time": now}
        return saved

    narratives = analyze_narratives(snapshot)
    _narrative_cache[cache_key] = {"narratives": narratives, "_time": now}
    return narratives
