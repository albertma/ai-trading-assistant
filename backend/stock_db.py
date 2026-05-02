"""
个股档案 + 分析日志 (SQLite)
"""
import sqlite3
from datetime import date, datetime
from pathlib import Path

DB_PATH = Path.home() / "Jarvis" / "ai_trading" / "stock_archive.db"

def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS stock_archive (
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            sector TEXT,
            analysis_date TEXT NOT NULL,
            price REAL,
            change_pct REAL,
            pe REAL,
            pb REAL,
            market_cap REAL,
            turnover REAL,
            ma5 REAL, ma10 REAL, ma20 REAL, ma60 REAL, ma200 REAL,
            rsi14 REAL,
            macd_dif REAL, macd_dea REAL, macd_hist REAL,
            bullish_alignment INTEGER DEFAULT 0,
            risk_passed INTEGER DEFAULT 0,
            revenue TEXT,
            net_profit TEXT,
            gross_margin REAL,
            roe REAL,
            industry_rank INTEGER,
            industry_total INTEGER,
            industry_avg_chg REAL,
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            PRIMARY KEY (code, analysis_date)
        );
        CREATE TABLE IF NOT EXISTS stock_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            note TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
        CREATE TABLE IF NOT EXISTS analysis_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            sector TEXT,
            analysis_date TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            price REAL, change_pct REAL,
            ma5 REAL, ma10 REAL, ma20 REAL, ma60 REAL, ma200 REAL,
            rsi14 REAL,
            macd_dif REAL, macd_dea REAL, macd_hist REAL,
            bullish_alignment INTEGER DEFAULT 0,
            risk_passed INTEGER DEFAULT 0,
            revenue TEXT, net_profit TEXT, gross_margin REAL, roe REAL
        );
        CREATE TABLE IF NOT EXISTS watchlist (
            code TEXT PRIMARY KEY NOT NULL,
            name TEXT NOT NULL,
            sector TEXT,
            reason TEXT DEFAULT '',
            priority TEXT DEFAULT 'medium' CHECK(priority IN ('high','medium','low')),
            added_date TEXT DEFAULT (date('now','localtime')),
            last_analysis_date TEXT,
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
        CREATE TABLE IF NOT EXISTS kline_daily (
            code TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            close REAL,
            high REAL,
            low REAL,
            volume REAL,
            PRIMARY KEY (code, date)
        );
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            stock_name TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
        CREATE TABLE IF NOT EXISTS ai_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            name TEXT DEFAULT '',
            summary TEXT NOT NULL,
            chat_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
        CREATE TABLE IF NOT EXISTS financial_reports (
            code TEXT NOT NULL,
            period TEXT NOT NULL,
            revenue REAL,
            revenue_yoy REAL,
            net_profit REAL,
            net_profit_yoy REAL,
            gross_margin REAL,
            net_margin REAL,
            eps REAL,
            bps REAL,
            roe REAL,
            debt_ratio REAL,
            current_ratio REAL,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            PRIMARY KEY (code, period)
        );
        CREATE TABLE IF NOT EXISTS stock_info (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            market TEXT DEFAULT '',
            concepts TEXT DEFAULT '[]',
            industry TEXT DEFAULT '',
            total_shares REAL,
            circulating_shares REAL,
            total_market_cap REAL,
            circulating_market_cap REAL,
            listing_date TEXT DEFAULT '',
            pinyin_initials TEXT DEFAULT '',
            pinyin_full TEXT DEFAULT '',
            data_source TEXT DEFAULT 'csv',
            last_updated TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_si_name ON stock_info(name);
        CREATE INDEX IF NOT EXISTS idx_si_pinyin ON stock_info(pinyin_initials);
        CREATE TABLE IF NOT EXISTS risk_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            rule_type TEXT NOT NULL,
            field TEXT NOT NULL,
            operator TEXT NOT NULL,
            value TEXT NOT NULL,
            unit TEXT DEFAULT '',
            severity TEXT DEFAULT 'fail',
            custom_detail TEXT DEFAULT '',
            enabled INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_rr_enabled ON risk_rules(enabled);
    """)
    conn.commit()
    conn.close()

def save_analysis(code: str, name: str, sector: str, data: dict) -> bool:
    """保存/更新分析记录"""
    conn = get_db()
    try:
        tech = data.get("technical") or {}
        fund = data.get("fundamental") or {}
        risk = data.get("risk_check") or {}
        ind = data.get("industry_outlook") or {}

        conn.execute("""
            INSERT OR REPLACE INTO stock_archive (
                code, name, sector, analysis_date,
                price, change_pct, pe, pb, market_cap, turnover,
                ma5, ma10, ma20, ma60, ma200,
                rsi14, macd_dif, macd_dea, macd_hist,
                bullish_alignment, risk_passed,
                revenue, net_profit, gross_margin, roe,
                industry_rank, industry_total, industry_avg_chg
            ) VALUES (?,?,?,?, ?,?,?,?,?,?, ?,?,?,?,?, ?,?,?,?, ?,?, ?,?,?,?, ?,?,?)
        """, (
            code, name, sector, date.today().isoformat(),
            tech.get("current_price"), tech.get("change_pct"),
            data.get("pe"), data.get("pb"), data.get("market_cap"), tech.get("turnover"),
            tech.get("ma5"), tech.get("ma10"), tech.get("ma20"), tech.get("ma60"), tech.get("ma200"),
            tech.get("rsi_14"),
            tech.get("macd", {}).get("dif"), tech.get("macd", {}).get("dea"), tech.get("macd", {}).get("hist"),
            1 if tech.get("bullish_alignment") else 0,
            1 if risk.get("passed") else 0,
            fund.get("revenue"), fund.get("net_profit"),
            fund.get("gross_margin"), fund.get("roe"),
            ind.get("rank"), ind.get("total_sectors"), ind.get("avg_change"),
        ))
        conn.commit()
        return True
    except Exception as e:
        return False
    finally:
        conn.close()

def get_all_history(limit: int = 100) -> list:
    """获取所有股票的全部分析历史记录（不去重），合并草稿和快照"""
    conn = get_db()
    rows = conn.execute(
        "SELECT *, 'draft' as record_type FROM stock_archive ORDER BY created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    snapshots = conn.execute(
        "SELECT id as snapshot_id, *, 'snapshot' as record_type FROM analysis_snapshots ORDER BY created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    combined = [dict(r) for r in rows] + [dict(r) for r in snapshots]
    combined.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return combined[:limit]

def get_history(limit: int = 50) -> list:
    """获取最近分析记录（每只股票最新一条）"""
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY code ORDER BY analysis_date DESC) as rn
            FROM stock_archive
        ) WHERE rn = 1
        ORDER BY created_at DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_stock_history(code: str) -> list:
    """获取某只股票的所有分析记录：合并stock_archive（草稿）和analysis_snapshots（快照）"""
    conn = get_db()
    rows = conn.execute(
        "SELECT *, 'draft' as record_type FROM stock_archive WHERE code = ? ORDER BY analysis_date DESC",
        (code,)
    ).fetchall()
    snapshots = conn.execute(
        "SELECT id as snapshot_id, code, name, sector, analysis_date, created_at, price, change_pct, ma5, ma10, ma20, ma60, ma200, rsi14, macd_dif, macd_dea, macd_hist, bullish_alignment, risk_passed, revenue, net_profit, gross_margin, roe, 'snapshot' as record_type FROM analysis_snapshots WHERE code = ? ORDER BY analysis_date DESC, created_at DESC",
        (code,)
    ).fetchall()
    conn.close()
    result = [dict(r) for r in rows] + [dict(s) for s in snapshots]
    result.sort(key=lambda x: (x.get("analysis_date") or "", 0 if x.get("record_type") == "snapshot" else 1), reverse=True)
    return result


def save_snapshot(code: str, name: str, sector: str, data: dict) -> int | None:
    """保存分析快照（手动保存），返回快照ID"""
    from datetime import date
    tech = data.get("technical") or {}
    fund = data.get("fundamental") or {}
    risk = data.get("risk_check") or {}
    conn = get_db()
    try:
        cur = conn.execute("""INSERT INTO analysis_snapshots (
            code, name, sector, analysis_date,
            price, change_pct,
            ma5, ma10, ma20, ma60, ma200,
            rsi14, macd_dif, macd_dea, macd_hist,
            bullish_alignment, risk_passed,
            revenue, net_profit, gross_margin, roe
        ) VALUES (?,?,?,?, ?,?, ?,?,?,?,?, ?,?,?,?, ?,?, ?,?,?,?)""", (
            code, name, sector, date.today().isoformat(),
            tech.get("current_price"), tech.get("change_pct"),
            tech.get("ma5"), tech.get("ma10"), tech.get("ma20"), tech.get("ma60"), tech.get("ma200"),
            tech.get("rsi_14"),
            tech.get("macd", {}).get("dif"), tech.get("macd", {}).get("dea"), tech.get("macd", {}).get("hist"),
            1 if tech.get("bullish_alignment") else 0,
            1 if risk.get("passed") else 0,
            fund.get("revenue"), fund.get("net_profit"), fund.get("gross_margin"), fund.get("roe"),
        ))
        conn.commit()
        return cur.lastrowid
    except Exception:
        return None
    finally:
        conn.close()


def delete_snapshot(snapshot_id: int) -> bool:
    """删除分析快照"""
    conn = get_db()
    try:
        conn.execute("DELETE FROM analysis_snapshots WHERE id = ?", (snapshot_id,))
        conn.commit()
        return conn.total_changes > 0
    except Exception:
        return False
    finally:
        conn.close()


def delete_draft(code: str, analysis_date: str) -> bool:
    """删除草稿（stock_archive记录）"""
    conn = get_db()
    try:
        conn.execute("DELETE FROM stock_archive WHERE code = ? AND analysis_date = ?", (code, analysis_date))
        conn.commit()
        return conn.total_changes > 0
    except Exception:
        return False
    finally:
        conn.close()


def add_note(code: str, note: str) -> int:
    conn = get_db()
    cur = conn.execute("INSERT INTO stock_notes (code, note) VALUES (?, ?)", (code, note))
    conn.commit()
    conn.close()
    return cur.lastrowid


def get_notes(code: str) -> list:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM stock_notes WHERE code = ? ORDER BY created_at DESC",
        (code,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ===== 观察池 =====

def get_watchlist() -> list:
    """获取观察池所有股票"""
    conn = get_db()
    rows = conn.execute("""
        SELECT w.*, s.price as last_price, s.change_pct, s.ma5, s.ma20, s.rsi14,
               s.bullish_alignment, s.risk_passed
        FROM watchlist w
        LEFT JOIN (
            SELECT code, price, change_pct, ma5, ma20, rsi14, bullish_alignment, risk_passed,
                   ROW_NUMBER() OVER (PARTITION BY code ORDER BY analysis_date DESC) as rn
            FROM stock_archive
        ) s ON w.code = s.code AND s.rn = 1
        ORDER BY
            CASE w.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
            w.added_date DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_to_watchlist(code: str, name: str, sector: str = "", reason: str = "", priority: str = "medium") -> bool:
    """添加到观察池"""
    conn = get_db()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO watchlist (code, name, sector, reason, priority)
            VALUES (?, ?, ?, ?, ?)
        """, (code, name, sector, reason, priority))
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()


def remove_from_watchlist(code: str) -> bool:
    conn = get_db()
    cur = conn.execute("DELETE FROM watchlist WHERE code = ?", (code,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def update_watchlist(code: str, **kwargs) -> bool:
    """更新观察池（priority/reason/notes）"""
    allowed = {"priority", "reason", "notes", "last_analysis_date"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [code]
    conn = get_db()
    conn.execute(f"UPDATE watchlist SET {set_clause} WHERE code = ?", vals)
    conn.commit()
    conn.close()
    return True


# ===== K线数据持久化 =====

KLINE_MAX_DAYS = 400  # 最大保留400条

def save_kline_records(code: str, records: list[dict]) -> int:
    """批量写入K线记录，自动去重"""
    conn = get_db()
    saved = 0
    for r in records:
        try:
            conn.execute("""
                INSERT OR REPLACE INTO kline_daily (code, date, open, close, high, low, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (code, r["date"], r.get("open"), r.get("close"),
                  r.get("high"), r.get("low"), r.get("volume")))
            saved += 1
        except:
            pass
    conn.commit()
    conn.close()
    return saved



def get_kline_records(code: str, limit: int = KLINE_MAX_DAYS) -> list[dict]:
    """获取K线记录（按日期倒序）"""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM kline_daily WHERE code = ? ORDER BY date DESC LIMIT ?",
        (code, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def prune_kline(code: str = None, max_days: int = KLINE_MAX_DAYS) -> int:
    """删除超出的旧K线记录，返回删除条数"""
    conn = get_db()
    if code:
        sub = conn.execute(
            "SELECT date FROM kline_daily WHERE code = ? ORDER BY date DESC LIMIT 1 OFFSET ?",
            (code, max_days - 1)
        ).fetchone()
        if sub:
            deleted = conn.execute(
                "DELETE FROM kline_daily WHERE code = ? AND date < ?",
                (code, sub["date"])
            ).rowcount
        else:
            deleted = 0
    else:
        deleted = 0
        codes = conn.execute("SELECT DISTINCT code FROM kline_daily").fetchall()
        for row in codes:
            sub = conn.execute(
                "SELECT date FROM kline_daily WHERE code = ? ORDER BY date DESC LIMIT 1 OFFSET ?",
                (row["code"], max_days - 1)
            ).fetchone()
            if sub:
                d = conn.execute(
                    "DELETE FROM kline_daily WHERE code = ? AND date < ?",
                    (row["code"], sub["date"])
                ).rowcount
                deleted += d
    conn.commit()
    conn.close()
    return deleted


def fetch_and_save_kline(code: str, days: int = 400) -> tuple[bool, int]:
    import json, urllib.request
    # 策略1: akshare
    try:
        import akshare as ak
        df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date="20000101", adjust="qfq")
        records = []
        for _, r in df.iterrows():
            records.append({
                "date": str(r["日期"]), "open": float(r["开盘"]), "close": float(r["收盘"]),
                "high": float(r["最高"]), "low": float(r["最低"]), "volume": float(r["成交量"]),
            })
        saved = save_kline_records(code, records)
        pruned = prune_kline(code)
        return True, saved
    except Exception:
        pass
    # 策略2: 腾讯行情API（akshare不可用时备用）
    try:
        market = "sz" if code.startswith(("0", "3", "2")) else "sh"
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={market}{code},day,,,{days},qfq"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        d = data.get("data", {})
        sz = d.get(f"{market}{code}", {})
        raw = sz.get("qfqday", sz.get("day", []))
        records = []
        for r in raw:
            records.append({
                "date": str(r[0]), "open": float(r[1]), "close": float(r[2]),
                "high": float(r[3]), "low": float(r[4]), "volume": float(r[5]),
            })
        saved = save_kline_records(code, records)
        pruned = prune_kline(code)
        return True, saved
    except Exception as e:
        return False, 0

# 启动时初始化
init_db()


# ===== 聊天记录 =====

def save_chat_message(code: str, role: str, content: str, stock_name: str = "") -> int:
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO chat_history (code, role, content, stock_name) VALUES (?, ?, ?, ?)",
            (code, role, content, stock_name)
        )
        conn.commit()
        return cur.lastrowid
    except Exception:
        return -1
    finally:
        conn.close()


def get_chat_history(code: str, limit: int = 50) -> list:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM chat_history WHERE code = ? ORDER BY created_at ASC LIMIT ?",
        (code, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ===== AI 分析摘要 =====

def save_ai_analysis(code: str, name: str, summary: str, chat_count: int = 0) -> int:
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO ai_analysis (code, name, summary, chat_count) VALUES (?, ?, ?, ?)",
            (code, name, summary, chat_count)
        )
        conn.commit()
        return cur.lastrowid
    except Exception:
        return -1
    finally:
        conn.close()


def get_ai_analysis(code: str, limit: int = 10) -> list:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM ai_analysis WHERE code = ? ORDER BY created_at DESC LIMIT ?",
        (code, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ===== 财报缓存 =====

def save_financial_reports(code: str, records: list[dict]) -> int:
    conn = get_db()
    saved = 0
    for r in records[-20:]:
        try:
            conn.execute("""INSERT OR REPLACE INTO financial_reports
                (code, period, revenue, revenue_yoy, net_profit, net_profit_yoy,
                 gross_margin, net_margin, eps, bps, roe, debt_ratio, current_ratio)
                VALUES (?,?,?,?,?,?, ?,?,?,?,?,?,?)""", (
                code,
                r.get("报告期", ""),
                r.get("营业总收入") or r.get("revenue"),
                r.get("营业总收入同比增长") or r.get("revenue_yoy"),
                r.get("净利润") or r.get("net_profit"),
                r.get("净利润同比增长") or r.get("net_profit_yoy"),
                r.get("销售毛利率") or r.get("gross_margin"),
                r.get("销售净利率"),
                r.get("每股收益") or r.get("eps"),
                r.get("每股净资产") or r.get("bps"),
                r.get("净资产收益率") or r.get("roe"),
                r.get("资产负债率"),
                r.get("流动比率"),
            ))
            saved += 1
        except Exception:
            pass
    conn.commit()
    conn.close()
    return saved


def get_financial_reports(code: str, limit: int = 20) -> list:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM financial_reports WHERE code = ? ORDER BY period DESC LIMIT ?",
        (code, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_latest_financial_report(code: str) -> dict | None:
    reports = get_financial_reports(code, 1)
    return reports[0] if reports else None


# ===== 股票信息（代码/名称/拼音） =====

def refresh_stock_info_from_csv() -> int:
    import glob
    csv_dir = Path.home() / "Jarvis" / "A股行情信息"
    files = sorted(glob.glob(str(csv_dir / "沪深京A股*.csv")))
    if not files:
        return 0
    latest = files[-1]
    import pandas as pd
    df = pd.read_csv(latest, encoding="utf-16", sep="\t")
    count = 0
    for _, r in df.iterrows():
        code = str(r.get("代码", "")).strip("'\"")
        name = str(r.get("名称", ""))
        if not code or not name:
            continue
        try:
            add_to_stock_info(code, name, industry=str(r.get("行业", "")),
                            market_cap=r.get("总市值"), concepts=[])
            count += 1
        except Exception:
            pass
    return count


def refresh_stock_detail_from_akshare(code: str) -> dict | None:
    try:
        import akshare as ak
        df = ak.stock_individual_info_em(symbol=code)
        info = {}
        for _, r in df.iterrows():
            info[str(r["item"])] = r["value"]
        return info
    except Exception:
        return None


def _get_pinyin_initials(name: str) -> str:
    try:
        import pypinyin
        return "".join(p[0] for p in pypinyin.pinyin(name, style=pypinyin.Style.FIRST_LETTER))
    except Exception:
        return ""


def search_stock_info(q: str, limit: int = 15) -> list:
    conn = get_db()
    q = q.strip().upper()
    if not q:
        return []
    rows = conn.execute("""
        SELECT code, name, market, industry, pinyin_initials
        FROM stock_info
        WHERE code LIKE ? OR name LIKE ? OR pinyin_initials LIKE ?
        ORDER BY
            CASE WHEN code = ? THEN 0 WHEN code LIKE ? THEN 1
                 WHEN name = ? THEN 2 WHEN name LIKE ? THEN 3 ELSE 4 END
        LIMIT ?
    """, (f"{q}%", f"{q}%", f"{q}%", q, f"{q}%", q, f"%{q}%", limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stock_info(code: str) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM stock_info WHERE code = ?", (code,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_stock_info_count() -> int:
    conn = get_db()
    row = conn.execute("SELECT COUNT(*) as cnt FROM stock_info").fetchone()
    conn.close()
    return row["cnt"] if row else 0


def add_to_stock_info(code: str, name: str, industry: str = "", market_cap: float = None, concepts: list = None) -> bool:
    pinyin = _get_pinyin_initials(name)
    conn = get_db()
    try:
        conn.execute("""INSERT OR REPLACE INTO stock_info (code, name, market, industry, concepts, total_market_cap, pinyin_initials)
            VALUES (?, ?, '', ?, ?, ?, ?)""",
            (code, name, industry, str(concepts or []), market_cap, pinyin))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


# ===== 风控规则 =====

def get_risk_rules(enabled_only: bool = False) -> list:
    conn = get_db()
    if enabled_only:
        rows = conn.execute("SELECT * FROM risk_rules WHERE enabled = 1 ORDER BY sort_order, id").fetchall()
    else:
        rows = conn.execute("SELECT * FROM risk_rules ORDER BY sort_order, id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_risk_rule(data: dict) -> int | None:
    conn = get_db()
    try:
        cur = conn.execute("""INSERT INTO risk_rules (name, description, rule_type, field, operator, value, unit, severity, custom_detail, enabled, sort_order)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (
            data["name"], data.get("description", ""), data["rule_type"],
            data["field"], data["operator"], data["value"],
            data.get("unit", ""), data.get("severity", "fail"),
            data.get("custom_detail", ""), data.get("enabled", 1), data.get("sort_order", 0),
        ))
        conn.commit()
        return cur.lastrowid
    except Exception:
        return None
    finally:
        conn.close()


def update_risk_rule(rule_id: int, data: dict) -> bool:
    conn = get_db()
    try:
        allowed = {"name", "description", "rule_type", "field", "operator", "value",
                   "unit", "severity", "custom_detail", "enabled", "sort_order"}
        updates = {k: v for k, v in data.items() if k in allowed}
        if not updates:
            return False
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [rule_id]
        conn.execute(f"UPDATE risk_rules SET {set_clause}, updated_at = datetime('now','localtime') WHERE id = ?", vals)
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def delete_risk_rule(rule_id: int) -> bool:
    conn = get_db()
    cur = conn.execute("DELETE FROM risk_rules WHERE id = ?", (rule_id,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def toggle_risk_rule(rule_id: int) -> bool | None:
    """切换规则的启用/禁用状态，返回新状态或 None(不存在)"""
    conn = get_db()
    try:
        row = conn.execute("SELECT enabled FROM risk_rules WHERE id = ?", (rule_id,)).fetchone()
        if not row:
            return None
        new_state = 0 if row["enabled"] else 1
        conn.execute("UPDATE risk_rules SET enabled = ?, updated_at = datetime('now','localtime') WHERE id = ?", (new_state, rule_id))
        conn.commit()
        return bool(new_state)
    except Exception:
        return None
    finally:
        conn.close()


def get_rule_types() -> list:
    """获取可用的规则定义字段"""
    return [
        {"type": "technical", "label": "技术指标", "fields": [
            {"field": "ma5", "label": "MA5"},
            {"field": "ma10", "label": "MA10"},
            {"field": "ma20", "label": "MA20"},
            {"field": "ma60", "label": "MA60"},
            {"field": "ma200", "label": "MA200"},
            {"field": "rsi14", "label": "RSI(14)"},
            {"field": "macd_dif", "label": "MACD.DIF"},
            {"field": "macd_dea", "label": "MACD.DEA"},
            {"field": "macd_hist", "label": "MACD.HIST"},
            {"field": "change_pct", "label": "涨跌幅"},
            {"field": "price", "label": "当前价"},
            {"field": "turnover", "label": "换手率"},
        ]},
        {"type": "fundamental", "label": "基本面", "fields": [
            {"field": "pe", "label": "市盈率(PE)"},
            {"field": "pb", "label": "市净率(PB)"},
            {"field": "market_cap", "label": "总市值"},
            {"field": "gross_margin", "label": "毛利率"},
            {"field": "roe", "label": "净资产收益率(ROE)"},
            {"field": "revenue", "label": "营收"},
            {"field": "net_profit", "label": "净利润"},
        ]},
        {"type": "pattern", "label": "K线形态", "fields": [
            {"field": "patterns", "label": "形态识别结果"},
        ]},
        {"type": "custom", "label": "自定义", "fields": [
            {"field": "amount_10d", "label": "10日均成交额"},
            {"field": "avg_amount_10d", "label": "10日均额（万元）"},
        ]},
    ]


def seed_default_rules() -> int:
    """初始化预设风控规则（如果不存在）"""
    conn = get_db()
    existing = conn.execute("SELECT COUNT(*) as cnt FROM risk_rules").fetchone()
    if existing and existing["cnt"] > 0:
        conn.close()
        return 0
    defaults = [
        # 技术指标
        ("MA60 趋势", "价格低于MA60，短期趋势偏弱，需警惕", "technical", "ma60", "<", "ma20", "", "warn", "", 1, 1),
        ("MA200 多空线", "价格低于MA200，长期趋势偏空，禁止买入", "technical", "ma200", "<", "price", "", "fail", "价格在MA200下方，长期趋势为空头", 1, 2),
        ("RSI 超买", "RSI大于70，短期超买，追高风险大", "technical", "rsi14", ">", "70", "", "warn", "", 1, 3),
        ("RSI 超卖", "RSI小于30，短期超卖，可能企稳反弹", "technical", "rsi14", "<", "30", "", "info", "", 1, 4),
        ("MACD 金叉", "MACD DIF上穿DEA，短期偏多信号", "technical", "macd_hist", ">", "0", "", "info", "", 1, 5),
        ("MACD 死叉", "MACD DIF下穿DEA，短期偏空信号", "technical", "macd_hist", "<", "0", "", "warn", "", 1, 6),
        # 基本面
        ("PE 过高", "市盈率过高，估值风险较大", "fundamental", "pe", ">", "100", "", "warn", "", 1, 7),
        ("PE 为负", "市盈率为负，公司当前亏损", "fundamental", "pe", "<", "0", "", "fail", "公司亏损状态下买入风险较高", 1, 8),
        ("PB < 1", "市净率小于1，破净状态", "fundamental", "pb", "<", "1", "", "info", "", 1, 9),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO risk_rules (name, description, rule_type, field, operator, value, unit, severity, custom_detail, enabled, sort_order) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        defaults
    )
    conn.commit()
    cnt = conn.execute("SELECT COUNT(*) as cnt FROM risk_rules").fetchone()["cnt"]
    conn.close()
    return cnt


def evaluate_risk_rules(code: str, tech: dict | None, fundamental: dict | None,
                        valuation: dict | None, patterns: list | None,
                        avg_amount_10d: float | None = None) -> list[dict]:
    """根据启用的规则对股票进行风控评估，只返回触发了的规则"""
    rules = get_risk_rules(enabled_only=True)
    results = []

    # 标准化操作符
    OP_MAP = {"gte": ">=", "gt": ">", "lte": "<=", "lt": "<", "eq": "=="}
    FIELD_REF = {  # 技术面字段，用于字段对字段比较
        "current_price", "ma5", "ma10", "ma20", "ma30", "ma60", "ma200",
        "macd_dif", "macd_dea", "macd_hist", "rsi_14", "change_pct",
    }

    for r in rules:
        field = r["field"]
        operator = r["operator"]
        op = OP_MAP.get(operator, operator)
        severity = r["severity"]
        detail = r.get("custom_detail") or r.get("description", "")

        # 从数据中取值
        actual = None
        if tech and field in tech:
            actual = tech[field]
        elif fundamental and field in fundamental:
            actual = fundamental[field]
        elif valuation and field in valuation:
            actual = valuation[field]
        elif field == "kline_pattern" and patterns:
            actual = ", ".join(p for p in (patterns or []) if "看跌" in p or "跌" in p)
        elif field in ("amount_10d", "avg_amount_10d"):
            if avg_amount_10d is not None:
                # 腾讯K线API 单位为元，规则 value 单位为亿
                actual = avg_amount_10d / 100_000_000
        elif field == "bullish_alignment":
            actual = tech.get("bullish_alignment") if tech else None

        if actual is None:
            continue

        # 解析比较值
        value_str = str(r["value"]).strip()

        # 字段对字段比较（如 ma200 > current_price）
        if value_str in FIELD_REF:
            compare_target = None
            if tech and value_str in tech:
                compare_target = tech[value_str]
            if compare_target is None:
                continue
            try:
                a = float(actual)
                v = float(compare_target)
            except (ValueError, TypeError):
                continue
            triggered = (
                (op == "<" and a < v) or
                (op == "<=" and a <= v) or
                (op == ">" and a > v) or
                (op == ">=" and a >= v) or
                (op == "==" and abs(a - v) < 0.0001) or
                (op == "!=" and abs(a - v) >= 0.0001)
            )
            if triggered:
                results.append({
                    "rule": r["name"], "status": severity, "detail": detail,
                    "field": field, "operator": op, "expected": value_str, "actual": round(a, 2),
                })
            continue

        # 数值比较
        try:
            # 布尔值转字符串比较
            if isinstance(actual, bool):
                raise TypeError  # 走字符串路径
            a = float(actual)
            v = float(value_str)
        except (ValueError, TypeError):
            # 字符串比较（如 contains 看跌）
            a_str = str(actual)
            v_str = value_str
            triggered = (
                (op == "==" and a_str.lower() == v_str.lower()) or
                (op == "!=" and a_str.lower() != v_str.lower()) or
                (op == "contains" and v_str in a_str) or
                (op == "not_contains" and v_str not in a_str) or
                (op == "=" and a_str == v_str)  # 兼容"true"/"false"
            )
            if triggered:
                results.append({
                    "rule": r["name"], "status": severity, "detail": detail,
                    "field": field, "operator": op, "expected": v_str, "actual": a_str,
                })
            continue

        triggered = (
            (op == "<" and a < v) or
            (op == "<=" and a <= v) or
            (op == ">" and a > v) or
            (op == ">=" and a >= v) or
            (op == "==" and abs(a - v) < 0.0001) or
            (op == "!=" and abs(a - v) >= 0.0001)
        )
        if triggered:
            results.append({
                "rule": r["name"], "status": severity, "detail": detail,
                "field": field, "operator": op, "expected": v, "actual": a,
            })

    return results
