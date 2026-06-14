"""
策略回测 API — 支持预设策略和自由组合
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from backend.services.signal_detect.strategy_backtest import (
    ensure_table, run_backtest, run_multi,
    list_results, list_batches, delete_batch, calc_summary,
)
from backend.services.signal_detect.signal_registry import (
    ENTRY_SIGNALS, EXIT_SIGNALS, STRATEGY_PRESETS, STRATEGY_LABELS,
    combo_name, combo_label,
)

router = APIRouter(tags=["策略回测"])


@router.get("/strategy-backtest/signals")
def get_available_signals():
    """获取所有可用的买入/卖出信号"""
    entries = [{"name": k, "label": v["label"],
                "needs_patterns": v["needs_patterns"],
                "needs_cup": v["needs_cup"],
                "params_schema": v["params_schema"]}
               for k, v in ENTRY_SIGNALS.items()]
    exits = [{"name": k, "label": v["label"],
              "params_schema": v.get("params_schema", {})}
             for k, v in EXIT_SIGNALS.items()]
    presets = [{"name": k, "label": v, "entry": STRATEGY_PRESETS[k][0],
                "exit": STRATEGY_PRESETS[k][1], "default_sl": STRATEGY_PRESETS[k][2]}
               for k, v in STRATEGY_LABELS.items()]
    return {"entries": entries, "exits": exits, "presets": presets}


@router.post("/strategy-backtest/run")
def run_strategy_backtest(
    code: str,
    strategy: str = Query("", description="预设策略名（留空则用entry+exit）"),
    entry_signal: str = Query("", description="买入信号名"),
    exit_signal: str = Query("", description="卖出信号名"),
    sl_pct: float = 0,
    tp_pct: float = 0,
    slow: int = 10,
    fast: int = 5,
    rsi_period: int = 14,
    rsi_overbought: int = 70,
    rsi_oversold: int = 30,
    bb_period: int = 20,
    bb_std: float = 2.0,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
    weekly: bool = False,
):
    """对单个标的运行策略回测"""
    ensure_table()
    params = {
        "fast": fast, "slow": slow,
        "period": rsi_period, "overbought": rsi_overbought, "oversold": rsi_oversold,
        "bb_period": bb_period, "bb_std": bb_std,
        "macd_fast": macd_fast, "macd_slow": macd_slow, "macd_signal": macd_signal,
    }
    trades = run_backtest(code, strategy=strategy,
                          entry_signal=entry_signal, exit_signal=exit_signal,
                          sl_pct=sl_pct, tp_pct=tp_pct, params=params,
                          weekly=weekly)
    summary = calc_summary(trades)
    return {"trades": trades, "summary": summary, "total": len(trades)}


@router.post("/strategy-backtest/run-multi")
def run_strategy_backtest_multi(
    codes: str = Query(..., description="逗号分隔的股票代码"),
    strategy: str = Query("", description="预设策略名"),
    entry_signal: str = Query("", description="买入信号名（留空则用预设）"),
    exit_signal: str = Query("", description="卖出信号名（留空则用预设）"),
    sl_pct: float = 0,
    tp_pct: float = 0,
    fast: int = 5,
    slow: int = 10,
    rsi_period: int = 14,
    rsi_overbought: int = 70,
    rsi_oversold: int = 30,
    bb_period: int = 20,
    bb_std: float = 2.0,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
    weekly: bool = False,
):
    """对多个标的批量跑回测"""
    ensure_table()
    code_list = [c.strip() for c in codes.split(",") if c.strip()]
    params = {
        "fast": fast, "slow": slow,
        "period": rsi_period, "overbought": rsi_overbought, "oversold": rsi_oversold,
        "bb_period": bb_period, "bb_std": bb_std,
        "macd_fast": macd_fast, "macd_slow": macd_slow, "macd_signal": macd_signal,
    }
    result = run_multi(code_list, strategy=strategy,
                       entry_signal=entry_signal, exit_signal=exit_signal,
                       sl_pct=sl_pct, tp_pct=tp_pct, params=params,
                       weekly=weekly)
    return result


@router.get("/strategy-backtest/results")
def get_strategy_results(
    strategy: str = "",
    code: str = "",
    batch_id: str = "",
    limit: int = 500,
):
    """获取回测交易记录"""
    ensure_table()
    return {"results": list_results(strategy, code, batch_id, limit)}


@router.get("/strategy-backtest/batches")
def get_batches():
    """获取所有回测批次列表"""
    ensure_table()
    return {"batches": list_batches()}


@router.delete("/strategy-backtest/batch/{batch_id}")
def delete_batch_api(batch_id: str):
    """删除指定批次的回测结果"""
    ok = delete_batch(batch_id)
    return {"message": "已删除" if ok else "无记录"}
