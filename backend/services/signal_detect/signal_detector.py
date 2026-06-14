"""AI信号检测器 — ⭐精选系统：仅大阳线/红三兵/锤子线 + MACD金叉(3天窗口)
   指标计算: 复用 utils/indicators.py
   精选信号: 复用 signal_registry.py 的 entry_kline_macd_elite"""
from pathlib import Path
import sqlite3
from datetime import datetime, date, timedelta
from typing import Optional

import numpy as np

from .models import TechnicalSignal, FundamentalSignal, NewsSignal, RiskFactor
from backend.utils.indicators import macd as calc_macd, rsi as calc_rsi

# 数据库路径
DB = str(Path.home() / 'Jarvis' / 'ai_trading' / 'stock_archive.db')


def detect_technical_signals(recs: list[dict]) -> tuple[list[TechnicalSignal], list[RiskFactor]]:
    """⭐精选系统 — 仅大阳线/红三兵/锤子线 + MACD金叉(3天滚动窗口)双重确认 + MA200多头过滤
       内部复用 signal_registry.entry_kline_macd_elite 完成核心检测"""
    signals = []
    risks = []
    if len(recs) < 60:
        return signals, risks

    n = len(recs)
    closes = np.array([float(r['close']) for r in recs])
    opens = np.array([float(r['open']) for r in recs])
    highs = np.array([float(r['high']) for r in recs])
    lows = np.array([float(r['low']) for r in recs])
    volumes = np.array([float(r.get('volume', 0)) for r in recs])

    # ── MA200多头过滤 ──
    ma200 = float(np.mean(closes[-200:])) if n >= 200 else closes[-1]
    if closes[-1] < ma200:
        return signals, risks

    # ── 计算MACD（共享indicators） ──
    dif, dea, macd_bar = calc_macd(closes)

    # ── 检测MACD金叉（近3天滚动窗口） ──
    macd_golden_dates: set[str] = set()
    from backend.utils.indicators import detect_macd_golden_cross
    for idx in detect_macd_golden_cross(dif, dea, lookback=3):
        macd_golden_dates.add(str(recs[idx]['date'])[:10])

    has_macd_golden = len(macd_golden_dates) > 0

    # ── 检测K线形态（近5天） ──
    from backend.utils.indicators import is_big_bullish, is_hammer, is_three_white_soldiers

    # 大阳线
    large_bullish_found = None
    for i in range(max(1, n - 5), n):
        r = recs[i]
        o, c = float(r['open']), float(r['close'])
        prev_close = float(recs[i - 1]['close']) if i > 0 else o
        if is_big_bullish(o, c, prev_close, threshold_pct=3.0):
            body_pct = (c - o) / prev_close * 100
            large_bullish_found = {
                'date': recs[i]['date'],
                'strength': min(90, body_pct * 12),
                'desc': f'今日收{round(c,2)}，阳线实体+{body_pct:.1f}%，强势上涨',
            }
            break

    # 红三兵
    three_white_found = None
    if len(recs) >= 3:
        c3 = [float(r['close']) for r in recs[-3:]]
        o3 = [float(r['open']) for r in recs[-3:]]
        res = is_three_white_soldiers(c3, o3)
        if res:
            three_white_found = res

    # 锤子线
    hammer_found = None
    for i in range(max(1, n - 5), n):
        r = recs[i]
        o, c, h, l = float(r['open']), float(r['close']), float(r['high']), float(r['low'])
        if is_hammer(o, c, h, l):
            body = abs(c - o)
            lower_shadow = min(o, c) - l
            hammer_found = {
                'date': recs[i]['date'],
                'strength': 75.0,
                'desc': f'下影线({round(lower_shadow,2)})为实体({round(body,2)})的{lower_shadow/body:.1f}倍，见底反转信号',
            }
            break

    # ── 精选系统：形态 + MACD金叉双重确认 ──
    if has_macd_golden:
        # 大阳线 + MACD金叉
        if large_bullish_found:
            signals.append(TechnicalSignal(
                pattern_type='large_bullish', pattern_name='⭐大阳线',
                strength=large_bullish_found['strength'],
                description=large_bullish_found['desc'] + ' + MACD金叉共振',
                kline_date=large_bullish_found['date'],
            ))
        # 红三兵 + MACD金叉
        if three_white_found:
            signals.append(TechnicalSignal(
                pattern_type='three_white', pattern_name='⭐红三兵',
                strength=three_white_found['strength'],
                description=three_white_found['desc'] + ' + MACD金叉共振',
                kline_date=str(recs[-1]['date'])[:10],
            ))
        # 锤子线 + MACD金叉
        if hammer_found:
            signals.append(TechnicalSignal(
                pattern_type='hammer', pattern_name='⭐锤子线',
                strength=hammer_found['strength'],
                description=hammer_found['desc'] + ' + MACD金叉共振',
                kline_date=hammer_found['date'],
            ))

    # RSI超买
    rsi_vals = calc_rsi(closes)
    if rsi_vals[-1] and not np.isnan(rsi_vals[-1]) and rsi_vals[-1] > 80:
        risks.append(RiskFactor(
            risk_type='technical', risk_name='RSI超买',
            severity=50.0,
            description=f'RSI({rsi_vals[-1]:.0f})进入超买区(>80)，短期回调风险'
        ))

    # MACD顶背离风险
    if n >= 60 and len(dif) >= 30 and len(macd_bar) >= 30:
        if (dif[-1] > 0 and dif[-1] < dif[-5]
                and closes[-1] > closes[-5]):
            risks.append(RiskFactor(
                risk_type='technical', risk_name='MACD顶背离',
                severity=60.0,
                description='价格创新高但MACD动能减弱，警惕回调'
            ))

    return signals, risks


def detect_fundamental_signals(code: str, conn: sqlite3.Connection) -> list[FundamentalSignal]:
    """基本面信号 — 财报数据驱动"""
    signals = []
    import json
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT report_period, data_json FROM financial_data WHERE code=? AND report_type='年报' ORDER BY report_period DESC LIMIT 4",
        (code,)
    ).fetchall()
    if len(rows) < 2:
        conn.row_factory = None
        return signals

    try:
        parsed = []
        for r in rows:
            if r['data_json']:
                d = json.loads(r['data_json'])
                d['report_period'] = r['report_period']
                parsed.append(d)

        if len(parsed) < 2:
            conn.row_factory = None
            return signals

        revs = [float(d.get('revenue', 0) or 0) for d in parsed if d.get('revenue')]
        profits = [float(d.get('profit', 0) or 0) for d in parsed if d.get('profit')]
        roes = [float(d.get('roe', 0) or 0) for d in parsed if d.get('roe')]

        if len(revs) >= 2:
            if revs[1]:
                rev_growth = (revs[0] - revs[1]) / revs[1] * 100
            else:
                rev_growth = 0
            if rev_growth > 20:
                signals.append(FundamentalSignal(
                    signal_type='revenue_growth',
                    signal_name='营收高增', strength=80,
                    value=f'{rev_growth:+.1f}%',
                    description=f'最新营收同比+{rev_growth:.1f}%, 快速增长',
                ))
            elif rev_growth < -20:
                signals.append(FundamentalSignal(
                    signal_type='revenue_decline',
                    signal_name='营收下滑', strength=40,
                    value=f'{rev_growth:+.1f}%',
                    description=f'最新营收同比{rev_growth:.1f}%, 需关注',
                ))

        if len(profits) >= 2:
            profit_growth = (profits[0] - profits[1]) / abs(profits[1]) * 100 if profits[1] else 0
            if profit_growth > 30:
                signals.append(FundamentalSignal(
                    signal_type='profit_surge',
                    signal_name='利润暴增', strength=85,
                    value=f'{profit_growth:+.1f}%',
                    description=f'最新净利润同比+{profit_growth:.1f}%, 盈利能力大幅提升',
                ))

        if roes and roes[0] > 15:
            signals.append(FundamentalSignal(
                signal_type='roe_improve',
                signal_name='高ROE', strength=75,
                value=f'{roes[0]:.1f}%',
                description=f'ROE({roes[0]:.1f}%)>15%, 资本回报率高',
            ))
    except (TypeError, ValueError, IndexError, json.JSONDecodeError):
        pass

    conn.row_factory = None
    return signals


def get_kline_records(code: str, conn: sqlite3.Connection, days: int = 400) -> list[dict]:
    """从kline_daily表获取K线数据"""
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT date, open, close, high, low, volume FROM kline_daily WHERE code=? ORDER BY date DESC LIMIT ?",
        (code, days)
    ).fetchall()
    result = []
    for r in reversed(rows):
        result.append({
            'date': str(r['date'])[:10],
            'open': float(r['open']),
            'close': float(r['close']),
            'high': float(r['high']),
            'low': float(r['low']),
            'volume': float(r['volume']) if r['volume'] else 0,
        })
    return result
