"""AI扫描信号持久化 — 每只股票一条记录"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

DB = str(Path.home() / 'Jarvis' / 'ai_trading' / 'stock_archive.db')

SCHEMA = '''
CREATE TABLE IF NOT EXISTS ai_scan_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_date TEXT NOT NULL,
    scan_type TEXT NOT NULL,        -- 'noon' / 'close'
    index_code TEXT NOT NULL,        -- 'hs300' / 'csi500' / 'star50'
    index_name TEXT NOT NULL,
    code TEXT NOT NULL,              -- 股票代码
    name TEXT NOT NULL,              -- 股票名称
    score REAL NOT NULL,             -- 总分
    change_pct REAL,                 -- 涨幅
    price REAL,                      -- 当前价
    confidence TEXT,                 -- AI置信度标签
    summary TEXT,                    -- 一句话摘要
    rationale TEXT,                  -- AI多空逻辑
    technical_score REAL,            -- 技术面评分
    fundamental_score REAL,          -- 基本面评分
    risk_score REAL,                 -- 风控分
    stop_loss REAL,                  -- 止损价
    take_profit REAL,                -- 止盈价
    position TEXT,                   -- 建议仓位
    technical_signals TEXT,          -- JSON: [{type, strength}]
    risk_factors TEXT,               -- JSON: [{name, severity}]
    market_summary TEXT,             -- 该次扫描的摘要（冗余，同一批次相同）
    total_scanned INTEGER,           -- 该次扫描总数（冗余）
    signal_count INTEGER,            -- 该次扫描信号总数（冗余）
    generated_at TEXT,               -- 扫描生成时间
    created_at TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(scan_date, scan_type, index_code, code)
);
'''


def init_db():
    conn = sqlite3.connect(DB)
    conn.execute(SCHEMA)
    conn.commit()
    conn.close()


def save_scan_signals(scan_result: dict, top_signals: list[dict] = None):
    """将信号股票逐只存为一条记录"""
    init_db()

    conn = sqlite3.connect(DB)
    signals = top_signals if top_signals is not None else scan_result.get('top_signals', [])
    if not signals:
        conn.close()
        return

    meta = {
        'scan_date': scan_result.get('date', ''),
        'scan_type': scan_result.get('scan_type', ''),
        'index_code': scan_result.get('index', ''),
        'index_name': scan_result.get('index_name', ''),
        'market_summary': scan_result.get('summary', ''),
        'total_scanned': scan_result.get('total_scanned', 0),
        'signal_count': scan_result.get('signal_count', 0),
        'generated_at': scan_result.get('generated_at', datetime.now().strftime('%Y-%m-%d %H:%M')),
    }

    for s in signals:
        conn.execute('''
            INSERT OR REPLACE INTO ai_scan_records
                (scan_date, scan_type, index_code, index_name,
                 code, name, score, change_pct, price, confidence,
                 summary, rationale,
                 technical_score, fundamental_score, risk_score,
                 stop_loss, take_profit, position,
                 technical_signals, risk_factors,
                 market_summary, total_scanned, signal_count, generated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?)
        ''', (
            meta['scan_date'], meta['scan_type'], meta['index_code'], meta['index_name'],
            s.get('code', ''), s.get('name', ''), s.get('score', 0), s.get('change'), s.get('price'), s.get('confidence'),
            s.get('summary', ''), s.get('rationale', ''),
            s.get('technical_score', 0), s.get('fundamental_score', 0), s.get('risk_score', 0),
            s.get('stop_loss'), s.get('take_profit'), s.get('position', ''),
            json.dumps(s.get('technical_signals', []), ensure_ascii=False),
            json.dumps(s.get('risk_factors', []), ensure_ascii=False),
            meta['market_summary'], meta['total_scanned'], meta['signal_count'], meta['generated_at'],
        ))

    conn.commit()
    conn.close()


def _rows_to_scan_result(rows: list[sqlite3.Row]) -> Optional[dict]:
    """将多行信号记录合并为前端需要的扫描结果格式"""
    if not rows:
        return None

    r0 = dict(rows[0])
    signals = []
    for r in rows:
        d = dict(r)
        signals.append({
            'code': d['code'],
            'name': d['name'],
            'score': d['score'],
            'change': d['change_pct'],
            'price': d['price'],
            'confidence': d['confidence'],
            'summary': d['summary'],
            'rationale': d['rationale'],
            'technical_score': d['technical_score'],
            'fundamental_score': d['fundamental_score'],
            'risk_score': d['risk_score'],
            'stop_loss': d['stop_loss'],
            'take_profit': d['take_profit'],
            'position': d['position'],
            'technical_signals': json.loads(d.get('technical_signals', '[]')),
            'risk_factors': json.loads(d.get('risk_factors', '[]')),
        })

    return {
        'success': True,
        'date': r0['scan_date'],
        'scan_type': r0['scan_type'],
        'index': r0['index_code'],
        'index_name': r0['index_name'],
        'total_scanned': r0['total_scanned'],
        'signal_count': r0['signal_count'],
        'summary': r0['market_summary'],
        'generated_at': r0['generated_at'],
        'top_signals': signals,
        'risk_warnings': _extract_risk_warnings(signals),
    }


def _extract_risk_warnings(signals: list[dict]) -> list[dict]:
    """从信号中提取高风险因素"""
    warnings = []
    for s in signals:
        for r in json.loads(s.get('risk_factors', '[]') if isinstance(s.get('risk_factors'), str) else '[]'):
            if r.get('severity', 0) >= 60:
                warnings.append({
                    'code': s['code'],
                    'name': s['name'],
                    'risk': r.get('name', ''),
                    'severity': r.get('severity', 0),
                    'desc': r.get('description', ''),
                })
    return warnings[:10]


def get_latest_scan(index_code: str = 'hs300', scan_type: str = 'noon') -> Optional[dict]:
    """获取指定指数+类型的最新扫描（合并所有信号）"""
    init_db()
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    # 先找最新批次
    batch = conn.execute('''
        SELECT scan_date, generated_at, market_summary, total_scanned, signal_count
        FROM ai_scan_records
        WHERE index_code = ? AND scan_type = ?
        ORDER BY scan_date DESC, id DESC LIMIT 1
    ''', (index_code, scan_type)).fetchone()
    if not batch:
        conn.close()
        return None

    # 取该批次的所有信号
    rows = conn.execute('''
        SELECT * FROM ai_scan_records
        WHERE index_code = ? AND scan_type = ? AND scan_date = ?
        ORDER BY score DESC
    ''', (index_code, scan_type, batch['scan_date'])).fetchall()
    conn.close()

    return _rows_to_scan_result(rows)


def get_scan_history(limit: int = 30) -> list[dict]:
    """获取历史扫描批次列表"""
    init_db()
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute('''
        SELECT scan_date, scan_type, index_code, index_name,
               market_summary, total_scanned, signal_count, generated_at,
               COUNT(*) as record_count
        FROM ai_scan_records
        GROUP BY scan_date, scan_type, index_code
        ORDER BY scan_date DESC, generated_at DESC
        LIMIT ?
    ''', (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_signals_by_date(index_code: str, scan_date: str, scan_type: str = 'noon') -> Optional[dict]:
    """按日期获取扫描结果"""
    init_db()
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute('''
        SELECT * FROM ai_scan_records
        WHERE index_code = ? AND scan_date = ? AND scan_type = ?
        ORDER BY score DESC
    ''', (index_code, scan_date, scan_type)).fetchall()
    conn.close()
    return _rows_to_scan_result(rows)


def get_available_dates(limit: int = 60) -> list[str]:
    init_db()
    conn = sqlite3.connect(DB)
    rows = conn.execute('''
        SELECT DISTINCT scan_date FROM ai_scan_records
        ORDER BY scan_date DESC LIMIT ?
    ''', (limit,)).fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_today_scan_summary() -> list[dict]:
    """获取今日所有指数的扫描汇总"""
    today_str = datetime.now().strftime('%Y-%m-%d')
    init_db()
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    # 先找最新日期
    latest = conn.execute('SELECT MAX(scan_date) as d FROM ai_scan_records').fetchone()
    target_date = latest['d'] if latest and latest['d'] else today_str
    rows = conn.execute('''
        SELECT scan_type, index_code, index_name,
               COUNT(*) as signal_count, total_scanned, generated_at,
               ROUND(AVG(score),1) as avg_score,
               ROUND(MAX(score),1) as max_score
        FROM ai_scan_records
        WHERE scan_date = ?
        GROUP BY scan_type, index_code
        ORDER BY index_code, scan_type
    ''', (target_date,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
