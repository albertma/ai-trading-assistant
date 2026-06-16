"""
策略管理 API — CRUD + 触发回测 + 作用域(板块/个股/群组)
"""
import json
import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from backend.services.database.stock_db import KLINE_DB_PATH

router = APIRouter(tags=["策略研究"])

DB_PATH = Path.home() / "Jarvis" / "ai_trading" / "stock_archive.db"


# ═══════════════════════════════════════════════════════════════
# 内部工具
# ═══════════════════════════════════════════════════════════════

def _get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


SCOPE_TYPES = ["all", "sector", "stock", "group"]


def _ensure_table():
    conn = _get_db()
    # 策略主表（兼容原有字段）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS strategies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT DEFAULT '',
            buy_signal TEXT NOT NULL,
            sell_signal TEXT NOT NULL,
            stop_loss REAL DEFAULT 5.0,
            config_json TEXT DEFAULT '{}',
            scope_type TEXT DEFAULT 'all',
            scope_value TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    # 兼容旧表：没有scope字段则添加
    for col in ("scope_type", "scope_value"):
        try:
            conn.execute(f"ALTER TABLE strategies ADD COLUMN {col} TEXT DEFAULT 'all'")
        except sqlite3.OperationalError:
            pass  # 字段已存在

    # 自定义股票群组表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stock_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            codes TEXT NOT NULL DEFAULT '',
            description TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    conn.commit()
    conn.close()


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    return d


@router.get("")
def list_strategies():
    """列表所有策略（含scope信息）"""
    _ensure_table()
    conn = _get_db()
    rows = conn.execute("""
        SELECT id, name, description, buy_signal, sell_signal,
               stop_loss, config_json, scope_type, scope_value,
               created_at, updated_at
        FROM strategies ORDER BY id DESC
    """).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["config_json"] = json.loads(d["config_json"])
        except (json.JSONDecodeError, TypeError):
            d["config_json"] = {}
        result.append(d)
    return result


@router.post("", status_code=201)
def create_strategy(body: dict):
    """创建新策略（支持scope）"""
    _ensure_table()
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(400, "name 不能为空")
    buy_signal = body.get("buy_signal", body.get("entry_signal", "")).strip()
    if not buy_signal:
        raise HTTPException(400, "buy_signal/entry_signal 不能为空")
    sell_signal = body.get("sell_signal", body.get("exit_signal", "")).strip()
    if not sell_signal:
        raise HTTPException(400, "sell_signal/exit_signal 不能为空")
    description = body.get("description", "")
    stop_loss = body.get("stop_loss", body.get("sl_pct", 5.0))
    config_raw = body.get("config_json", {})
    config_str = json.dumps(config_raw, ensure_ascii=False) if isinstance(config_raw, dict) else str(config_raw)
    scope_type = body.get("scope_type", "all")
    if scope_type not in SCOPE_TYPES:
        raise HTTPException(400, f"scope_type 必须是 {SCOPE_TYPES}")
    scope_value = body.get("scope_value", "")
    conn = _get_db()
    try:
        cur = conn.execute("""
            INSERT INTO strategies
                (name, description, buy_signal, sell_signal, stop_loss, config_json, scope_type, scope_value)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, description, buy_signal, sell_signal, stop_loss, config_str, scope_type, scope_value))
        conn.commit()
        strategy_id = cur.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(409, f"策略名称「{name}」已存在")
    conn.close()
    return get_strategy_by_id(strategy_id)


def get_strategy_by_id(strategy_id: int) -> dict:
    _ensure_table()
    conn = _get_db()
    row = conn.execute("""
        SELECT id, name, description, buy_signal, sell_signal,
               stop_loss, config_json, scope_type, scope_value,
               created_at, updated_at
        FROM strategies WHERE id = ?
    """, (strategy_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, f"策略 #{strategy_id} 不存在")
    d = dict(row)
    try:
        d["config_json"] = json.loads(d["config_json"])
    except (json.JSONDecodeError, TypeError):
        d["config_json"] = {}
    return d


# ═══════════════════════════════════════════════════════════════
# 静态路径路由（必须在/{strategy_id}之前定义，避免被捕获）
# ═══════════════════════════════════════════════════════════════

@router.get("/match")
def match_strategies(code: str = ""):
    """根据股票代码 / 板块名，返回匹配的策略列表"""
    _ensure_table()
    conn = _get_db()
    rows = conn.execute("SELECT * FROM strategies ORDER BY id DESC").fetchall()
    conn.close()
    industry = ""
    if code:
        try:
            c2 = _get_db()
            row = c2.execute("SELECT industry FROM stock_info WHERE code=?", (code,)).fetchone()
            if row:
                industry = row["industry"] or ""
            c2.close()
        except Exception:
            pass
    matched = []
    for r in rows:
        d = dict(r)
        st = d.get("scope_type", "all")
        sv = d.get("scope_value", "")
        if st == "all":
            matched.append(d)
        elif st == "sector" and industry and sv and sv == industry:
            matched.append(d)
        elif st == "stock" and code and sv and sv == code:
            matched.append(d)
        elif st == "group":
            try:
                c3 = _get_db()
                grp = c3.execute("SELECT codes FROM stock_groups WHERE name=?", (sv,)).fetchone()
                c3.close()
                if grp:
                    group_codes = [c.strip() for c in grp["codes"].split(",") if c.strip()]
                    if code in group_codes:
                        matched.append(d)
            except Exception:
                pass
    for d in matched:
        try:
            d["config_json"] = json.loads(d["config_json"])
        except (json.JSONDecodeError, TypeError):
            d["config_json"] = {}
    return matched


@router.get("/candidates")
def get_candidates():
    """返回所有板块名 + 股票群组列表，供前端下拉使用"""
    _ensure_table()
    conn = _get_db()
    sectors = [r["sector"] for r in conn.execute("""
        SELECT DISTINCT industry AS sector FROM stock_info
        WHERE industry IS NOT NULL AND industry != '' AND industry != '--'
        ORDER BY industry
    """).fetchall()]
    conn.close()
    conn = _get_db()
    groups = [{"name": r["name"], "codes": r["codes"]}
              for r in conn.execute("SELECT name, codes FROM stock_groups ORDER BY name").fetchall()]
    conn.close()
    return {"sectors": sectors, "groups": groups}


@router.get("/groups")
def list_groups():
    """列表所有自定义股票群组"""
    _ensure_table()
    conn = _get_db()
    rows = conn.execute("""
        SELECT id, name, codes, description, created_at
        FROM stock_groups ORDER BY id DESC
    """).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        codes = [c.strip() for c in d.get("codes", "").split(",") if c.strip()]
        d["code_count"] = len(codes)
        d["code_list"] = codes
        result.append(d)
    return result


@router.post("/groups", status_code=201)
def create_group(body: dict):
    """创建自定义股票群组"""
    _ensure_table()
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(400, "name 不能为空")
    codes_raw = body.get("codes", "")
    codes = ",".join([c.strip() for c in codes_raw.split(",") if c.strip()])
    description = body.get("description", "")
    conn = _get_db()
    try:
        cur = conn.execute("""
            INSERT INTO stock_groups (name, codes, description)
            VALUES (?, ?, ?)
        """, (name, codes, description))
        conn.commit()
        gid = cur.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(409, f"群组名称「{name}」已存在")
    conn.close()
    return {"id": gid, "name": name, "codes": codes, "description": description}


# ═══════════════════════════════════════════════════════════════
# 策略信号扫描 — 检查所有已配置策略在当前行情下的信号
# ═══════════════════════════════════════════════════════════════

@router.get("/scan-signals")
def scan_strategy_signals():
    """扫描所有已配置策略，在每个策略的作用域内检查当前是否有实时买入信号

    返回每个策略下有实时信号的股票，包含信号类型、置信度、建议点位（入场/止损/目标/盈亏比）。
    """
    _ensure_table()
    conn = _get_db()
    rows = conn.execute("SELECT * FROM strategies ORDER BY id DESC").fetchall()
    conn.close()

    from backend.services.signal_detect.strategy_backtest import (
        ensure_table, check_current_signal,
    )
    ensure_table()

    results = []
    for row in rows:
        strategy = dict(row)
        try:
            config = json.loads(strategy["config_json"])
        except:
            config = {}

        st = strategy.get("scope_type", "all")
        sv = strategy.get("scope_value", "")
        entry = strategy["buy_signal"]
        params = config.get("params", {})

        candidates = _find_scope_stocks(st, sv)
        if not candidates:
            continue

        hits = []
        for code, name in candidates[:20]:
            try:
                sig = check_current_signal(
                    code=code,
                    entry_signal=entry,
                    params=params,
                )
                if sig and sig.get("triggered"):
                    hits.append({
                        "code": code,
                        "name": name or code,
                        "signal_detail": sig.get("signal_detail", ""),
                        "confidence": sig.get("confidence", 0),
                        "entry_price": sig.get("entry_price", 0),
                        "stop_loss_price": sig.get("stop_loss_price", 0),
                        "target_price": sig.get("target_price", 0),
                        "risk_reward_ratio": sig.get("risk_reward_ratio", 0),
                        "current_price": sig.get("current_price", 0),
                        "ma60_support": sig.get("ma60_support", 0),
                        "consolidation_low": sig.get("consolidation_low", 0),
                    })
            except:
                pass

        if hits:
            avg_conf = sum(h["confidence"] for h in hits) / len(hits)
            results.append({
                "strategy_id": strategy["id"],
                "strategy_name": strategy["name"],
                "entry_signal": entry,
                "scope_type": st,
                "scope_value": sv,
                "total_stocks_scanned": len(candidates),
                "stocks_with_signals": len(hits),
                "avg_confidence": round(avg_conf, 0),
                "hits": hits,
            })

    results.sort(key=lambda r: -r["stocks_with_signals"])
    return {"total_strategies": len(rows), "active_strategies": len(results), "results": results}


def _find_scope_stocks(scope_type: str, scope_value: str) -> list:
    """根据作用域返回股票代码列表 [(code, name), ...]"""
    try:
        conn = _get_db()
        conn.execute(f"ATTACH DATABASE '{KLINE_DB_PATH}' AS kline")
        if scope_type == "all":
            rows = conn.execute("""
                SELECT code, name FROM stock_info
                WHERE code IN (SELECT DISTINCT code FROM kline.kline_daily WHERE date >= date('now', '-60 days'))
                LIMIT 20
            """).fetchall()
            conn.execute("DETACH DATABASE kline")
            conn.close()
            return [(r["code"], r["name"]) for r in rows]

        elif scope_type == "sector":
            rows = conn.execute("""
                SELECT code, name FROM stock_info
                WHERE industry = ? AND code IN (
                    SELECT DISTINCT code FROM kline.kline_daily WHERE date >= date('now', '-60 days')
                )
                LIMIT 20
            """, (scope_value,)).fetchall()
            conn.execute("DETACH DATABASE kline")
            conn.close()
            return [(r["code"], r["name"]) for r in rows]

        elif scope_type == "stock":
            row = conn.execute("SELECT code, name FROM stock_info WHERE code=?", (scope_value,)).fetchone()
            conn.close()
            return [(row["code"], row["name"])] if row else []

        elif scope_type == "group":
            grp = conn.execute("SELECT codes FROM stock_groups WHERE name=?", (scope_value,)).fetchone()
            conn.close()
            if grp:
                codes = [c.strip() for c in grp["codes"].split(",") if c.strip()]
                result = []
                for c in codes[:20]:
                    row = conn.execute("SELECT code, name FROM stock_info WHERE code=?", (c,)).fetchone()
                    if row:
                        result.append((row["code"], row["name"]))
                return result
        return []
    except Exception:
        return []


@router.put("/groups/{group_id}")
def update_group(group_id: int, body: dict):
    """更新自定义股票群组"""
    _ensure_table()
    conn = _get_db()
    old = conn.execute("SELECT * FROM stock_groups WHERE id=?", (group_id,)).fetchone()
    if not old:
        conn.close()
        raise HTTPException(404, "群组不存在")
    name = body.get("name", old["name"]).strip()
    codes_raw = body.get("codes", old["codes"])
    codes = ",".join([c.strip() for c in codes_raw.split(",") if c.strip()])
    description = body.get("description", old["description"])
    try:
        conn.execute("""
            UPDATE stock_groups SET name=?, codes=?, description=?
            WHERE id=?
        """, (name, codes, description, group_id))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(409, f"群组名称「{name}」已存在")
    conn.close()
    return {"id": group_id, "name": name, "codes": codes, "description": description}


@router.delete("/groups/{group_id}")
def delete_group(group_id: int):
    _ensure_table()
    conn = _get_db()
    cur = conn.execute("DELETE FROM stock_groups WHERE id=?", (group_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    if not deleted:
        raise HTTPException(404, "群组不存在")
    return {"message": "已删除", "id": group_id}


# ═══════════════════════════════════════════════════════════════
# 参数化路由（必须在静态路由之后，/{strategy_id} 会匹配任意单段）
# ═══════════════════════════════════════════════════════════════

@router.get("/{strategy_id}")
def get_strategy(strategy_id: int):
    return get_strategy_by_id(strategy_id)


@router.put("/{strategy_id}")
def update_strategy(strategy_id: int, body: dict):
    """更新策略（含scope）"""
    _ensure_table()
    conn = _get_db()
    old = conn.execute("SELECT * FROM strategies WHERE id = ?", (strategy_id,)).fetchone()
    if not old:
        conn.close()
        raise HTTPException(404, f"策略 #{strategy_id} 不存在")
    old = dict(old)
    name = body.get("name", old["name"]).strip()
    description = body.get("description", old["description"])
    buy_signal = body.get("buy_signal", body.get("entry_signal", old["buy_signal"])).strip()
    sell_signal = body.get("sell_signal", body.get("exit_signal", old["sell_signal"])).strip()
    stop_loss = body.get("stop_loss", body.get("sl_pct", old["stop_loss"]))
    if "config_json" in body:
        config_raw = body["config_json"]
        config_str = json.dumps(config_raw, ensure_ascii=False) if isinstance(config_raw, dict) else str(config_raw)
    else:
        config_str = old["config_json"]
    scope_type = body.get("scope_type", old.get("scope_type", "all"))
    scope_value = body.get("scope_value", old.get("scope_value", ""))
    try:
        conn.execute("""
            UPDATE strategies
            SET name=?, description=?, buy_signal=?, sell_signal=?, stop_loss=?,
                config_json=?, scope_type=?, scope_value=?,
                updated_at=datetime('now','localtime')
            WHERE id=?
        """, (name, description, buy_signal, sell_signal, stop_loss, config_str,
              scope_type, scope_value, strategy_id))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(409, f"策略名称「{name}」已存在")
    conn.close()
    return get_strategy_by_id(strategy_id)


@router.delete("/{strategy_id}")
def delete_strategy(strategy_id: int):
    _ensure_table()
    conn = _get_db()
    cur = conn.execute("DELETE FROM strategies WHERE id = ?", (strategy_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    if not deleted:
        raise HTTPException(404, f"策略 #{strategy_id} 不存在")
    return {"message": "已删除", "id": strategy_id}


@router.post("/{strategy_id}/run-backtest")
def run_strategy_backtest(
    strategy_id: int,
    code: str = Query(..., description="股票代码"),
):
    """按策略定义运行回测"""
    strategy = get_strategy_by_id(strategy_id)
    from backend.services.signal_detect.strategy_backtest import (
        ensure_table, run_backtest, calc_summary,
    )
    ensure_table()
    config = strategy.get("config_json") or {}
    trades = run_backtest(
        code=code,
        entry_signal=strategy["buy_signal"],
        exit_signal=strategy["sell_signal"],
        sl_pct=strategy["stop_loss"] or 0,
        tp_pct=config.get("tp_pct", 0),
        params=config.get("params", {}),
        weekly=config.get("weekly", False),
    )
    summary = calc_summary(trades)
    return {
        "strategy_id": strategy_id,
        "strategy_name": strategy["name"],
        "code": code,
        "trades": trades,
        "summary": summary,
        "total": len(trades),
    }

