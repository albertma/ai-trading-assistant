"""策略进化 — DB连接 + 表结构定义 + 建表"""

import sqlite3
from pathlib import Path

DB_PATH = Path.home() / "Jarvis" / "ai_trading" / "stock_archive.db"


def get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def ensure_tables():
    """创建/迁移策略进化系统所需的所有表"""
    conn = get_db()

    # ── strategies 表 ──
    conn.execute("""CREATE TABLE IF NOT EXISTS strategies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        description TEXT DEFAULT '',
        buy_signal TEXT NOT NULL,
        sell_signal TEXT NOT NULL,
        stop_loss REAL DEFAULT 5.0,
        config_json TEXT DEFAULT '{}',
        dimension TEXT DEFAULT 'technical',
        weight REAL DEFAULT 1.0,
        scope_type TEXT DEFAULT 'all',
        scope_value TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now','localtime')),
        updated_at TEXT DEFAULT (datetime('now','localtime'))
    )""")
    for col in ("dimension", "weight", "scope_type", "scope_value"):
        try:
            conn.execute(f"ALTER TABLE strategies ADD COLUMN {col} TEXT DEFAULT 'technical'")
        except sqlite3.OperationalError:
            pass

    # ── 策略-股票显式映射表（N对N） ──
    conn.execute("""CREATE TABLE IF NOT EXISTS strategy_mappings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_code TEXT NOT NULL,
        strategy_id INTEGER NOT NULL,
        priority INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE,
        UNIQUE(stock_code, strategy_id)
    )""")

    # ── 每日评分快照 ──
    conn.execute("""CREATE TABLE IF NOT EXISTS stock_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_code TEXT NOT NULL,
        stock_name TEXT DEFAULT '',
        session TEXT NOT NULL,
        date TEXT NOT NULL,
        tech_score REAL DEFAULT 0,
        fund_score REAL DEFAULT 0,
        narr_score REAL DEFAULT 0,
        flow_score REAL DEFAULT 0,
        sent_score REAL DEFAULT 0,
        final_score REAL DEFAULT 0,
        decision TEXT DEFAULT 'HOLD',
        evidence TEXT DEFAULT '{}',
        batch_id TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )""")
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_scores_stock ON stock_scores(stock_code, date, session)")
    except sqlite3.OperationalError:
        pass

    # ── 维度权重表 ──
    conn.execute("""CREATE TABLE IF NOT EXISTS dimension_weights (
        dimension TEXT PRIMARY KEY,
        weight REAL DEFAULT 1.0,
        last_updated TEXT DEFAULT (datetime('now','localtime'))
    )""")
    # 插入默认权重
    defaults = {
        "technical": 1.0, "fundamental": 1.0,
        "narrative": 0.8, "capital_flow": 0.8, "sentiment": 0.6,
    }
    for dim, w in defaults.items():
        conn.execute(
            "INSERT OR IGNORE INTO dimension_weights(dimension, weight) VALUES (?,?)",
            (dim, w),
        )

    # ── 进化日志 ──
    conn.execute("""CREATE TABLE IF NOT EXISTS evolution_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cycle_date TEXT NOT NULL,
        dimension TEXT NOT NULL,
        weight_before REAL,
        weight_after REAL,
        accuracy REAL,
        total_predictions INTEGER,
        correct_predictions INTEGER,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )""")

    # ── 策略信号结果表 ──
    conn.execute("""CREATE TABLE IF NOT EXISTS strategy_signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        strategy_id INTEGER NOT NULL,
        strategy_name TEXT NOT NULL,
        stock_code TEXT NOT NULL,
        stock_name TEXT DEFAULT '',
        session TEXT NOT NULL DEFAULT 'close',
        signal_type TEXT NOT NULL DEFAULT 'entry',
        confidence REAL DEFAULT 0,
        entry_price REAL DEFAULT 0,
        stop_loss REAL DEFAULT 0,
        target_price REAL DEFAULT 0,
        signal_detail TEXT DEFAULT '',
        batch_id TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )""")
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_strat_sig_batch ON strategy_signals(batch_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_strat_sig_code ON strategy_signals(stock_code)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_strat_sig_strat ON strategy_signals(strategy_id)")
    except Exception:
        pass

    # ── 指数成分缓存 ──
    conn.execute("""CREATE TABLE IF NOT EXISTS index_constituents_cache (
        index_name TEXT PRIMARY KEY,
        codes_json TEXT NOT NULL,
        fetched_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    )""")

    # ── 扫描运行日志 ──
    conn.execute("""CREATE TABLE IF NOT EXISTS scan_run_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id TEXT NOT NULL,
        session TEXT NOT NULL DEFAULT 'close',
        status TEXT NOT NULL DEFAULT 'running',
        total_stocks INTEGER DEFAULT 0,
        scored_stocks INTEGER DEFAULT 0,
        failed_stocks INTEGER DEFAULT 0,
        started_at TEXT,
        finished_at TEXT,
        duration_seconds REAL,
        message TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )""")

    conn.commit()
