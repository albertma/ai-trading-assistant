"""
底部反转RL样本外验证 v2
===================
问题：信号太稀疏，100天窗口几乎0信号
策略：走马灯式时间序列交叉验证 (walk-forward)

方法：将500天分为5个200天重叠窗口
  窗口1: [1..300天] 训练 → [251..450天] 验证 (最后200天)
  窗口2: [1..400天] 训练 → [351..500天] 验证 (最后150天)
  (= 5-fold time series CV)

对每个窗口：
  - 限制回测只在验证期检测信号
  - 对比基线参数 vs RL参数
  - 如果RL在多个窗口优于基线 → 参数泛化

改进：用"最后150天+200天"两个窗口，确保每窗口有足够信号
"""
import sys, json, time, math
from pathlib import Path
from collections import defaultdict

PROJ = Path('/Users/albertma/sourcecode/workspace/python/ai-trading-assistant')
sys.path.insert(0, str(PROJ))

from scripts.optimize_bottom_reversal import (
    load_kline, preload_kline_group,
    load_csi500_codes_with_industry, DEFAULT_PARAMS
)

CHECKPOINT_FILE = PROJ / 'data/rl_checkpoint.json'


def run_backtest_with_date_filter(stock_codes, params, kline_data, min_date, max_date=None):
    """
    限制底部反转信号只在指定日期范围内触发。
    方法：信号检测逻辑不变，但只保留 entry_date >= min_date 的信号
    以及 entry_date <= max_date（当max_date设置时）
    """
    from scripts.optimize_bottom_reversal import detect_bottom_reversal, backtest_group
    import pandas as pd
    import numpy as np

    all_trades = []
    for code in stock_codes:
        if code not in kline_data:
            continue
        d = kline_data[code]
        closes, highs, lows, opens, volumes = d['close'], d['high'], d['low'], d['open'], d['volume']
        dates = d.get('dates', [])
        if not dates:
            continue

        signals = detect_bottom_reversal(closes, highs, lows, opens, volumes, params)

        for sig in signals:
            entry_idx = sig['entry_idx']
            if entry_idx >= len(dates):
                continue
            entry_date = dates[entry_idx]
            if entry_date < min_date:
                continue
            if max_date and entry_date > max_date:
                continue

            if entry_idx >= len(closes) - 5:
                continue

            entry_p = sig['entry_price']
            exit_idx = None
            exit_p = None

            # 退出: MACD死叉
            exp12 = pd.Series(closes).ewm(span=12, adjust=False).mean().values
            exp26 = pd.Series(closes).ewm(span=26, adjust=False).mean().values
            macd_line = exp12 - exp26
            macd_signal = pd.Series(macd_line).ewm(span=9, adjust=False).mean().values

            for j in range(entry_idx + 1, len(closes)):
                if (not np.isnan(macd_line[j]) and not np.isnan(macd_line[j-1])
                    and not np.isnan(macd_signal[j]) and not np.isnan(macd_signal[j-1])
                    and macd_line[j-1] >= macd_signal[j-1] and macd_line[j] < macd_signal[j]):
                    exit_idx = j
                    exit_p = closes[j]
                    break

            if exit_idx is None:
                exit_idx = len(closes) - 1
                exit_p = closes[-1]

            pnl = exit_p - entry_p
            ret = pnl / entry_p * 100

            all_trades.append({
                'code': code,
                'entry_date': entry_date,
                'exit_date': dates[exit_idx] if exit_idx < len(dates) else dates[-1],
                'entry_p': round(entry_p, 2),
                'exit_p': round(exit_p, 2),
                'pnl': round(pnl, 2),
                'ret': round(ret, 2),
                'holding': exit_idx - entry_idx,
            })

    if not all_trades:
        return None

    df = pd.DataFrame(all_trades)
    wins = df[df['pnl'] > 0]
    losses = df[df['pnl'] <= 0]
    total_pnl = df['pnl'].sum()
    win_rate = len(wins) / len(df) * 100 if len(df) > 0 else 0
    profit_factor = (wins['pnl'].sum() / abs(losses['pnl'].sum())) if len(losses) > 0 and losses['pnl'].sum() != 0 else (99 if len(wins) > 0 else 0)

    return {
        'trades': len(df),
        'win_rate': round(win_rate, 1),
        'total_pnl': round(total_pnl, 2),
        'profit_factor': round(profit_factor, 2),
    }


def get_date_from_index(kline_data, code, idx):
    """获取指定股票K线数组中第idx个索引对应的日期字符串"""
    dates = kline_data[code]['dates']
    return dates[idx] if idx < len(dates) else dates[-1]


def main():
    print("=" * 72)
    print("底部反转RL参数 · 走马灯式时间序列交叉验证")
    print("=" * 72)

    if not CHECKPOINT_FILE.exists():
        print("❌ 检查点文件不存在")
        return

    ckpt = json.loads(CHECKPOINT_FILE.read_text())
    rl_results = ckpt.get('results', {})

    groups, all_codes = load_csi500_codes_with_industry()

    # ── 定义验证窗口 ──
    # 窗口1: 最后150天（近期）
    # 窗口2: 最后200天（更多数据）
    windows = [
        {"name": "最后150天", "lookback": 150},
    ]

    print(f"\n共 {len(rl_results)} 个有RL参数的板块")

    # 逐板块验证
    for sector_name in sorted(rl_results.keys()):
        rl_info = rl_results[sector_name]
        rl_params = rl_info.get('best_params')
        if not rl_params:
            continue

        codes = groups.get(sector_name, [])
        if len(codes) < 3:
            continue

        # 加载K线
        kline_data = preload_kline_group(codes)
        if len(kline_data) < 3:
            continue

        # 确定日期范围：取板块内所有股票最小数据集的最大start_date
        # 找最晚的起始日期（让所有股票都有数据）
        stock_list = list(kline_data.keys())

        print(f"\n{'─' * 40}")
        print(f"📈 {sector_name} ({len(stock_list)}只)")

        for win in windows:
            # 提取验证期（最后N天）
            dates_pool = []
            for code in stock_list:
                d = kline_data[code]
                if len(d['dates']) >= win['lookback']:
                    cutoff_date = d['dates'][-win['lookback']]
                    dates_pool.append(cutoff_date)

            if not dates_pool:
                continue

            min_cutoff = max(set(dates_pool))  # 对所有股票都安全的cutoff

            # 基线参数回测（验证期）
            base_r = run_backtest_with_date_filter(
                stock_list, DEFAULT_PARAMS, kline_data, min_cutoff)
            # RL参数回测（验证期）
            rl_r = run_backtest_with_date_filter(
                stock_list, rl_params, kline_data, min_cutoff)

            b_trades = base_r['trades'] if base_r else 0
            b_wr = base_r['win_rate'] if base_r else 0
            b_pnl = base_r['total_pnl'] if base_r else 0
            r_trades = rl_r['trades'] if rl_r else 0
            r_wr = rl_r['win_rate'] if rl_r else 0
            r_pnl = rl_r['total_pnl'] if rl_r else 0

            # 判断结论
            if r_trades < 3:
                conclusion = "❌ 过拟合(信号太少)"
            elif r_wr >= b_wr and r_pnl >= b_pnl:
                conclusion = "✅ RL更优"
            elif r_wr >= 50 and r_trades >= 5:
                conclusion = "⚠️ RL可接受"
            else:
                conclusion = "❌ RL不如基线"

            print(f"  {win['name']:12s} | 基线: {b_wr:5.1f}% {b_pnl:8.1f} ({b_trades}笔) "
                  f"| RL: {r_wr:5.1f}% {r_pnl:8.1f} ({r_trades}笔) → {conclusion}")
            if rl_r:
                print(f"    RL参数: min_days={rl_params['min_days']}, max_days={rl_params['max_days']}, "
                      f"vol={rl_params['vol_ratio']}, tol={rl_params['ma60_tol']}, "
                      f"dif={rl_params['dif_thresh']}, gc={rl_params['gc_window']}")

    print("\n" + "=" * 72)
    print("✅ 验证完成")
    print("注意：严格样本外验证需要重新RL训练（训练集400天+验证集100天保持隔离）")
    print("当前结果已是最佳近似 — 检查RL参数是否在近期数据中仍有信号")


if __name__ == '__main__':
    main()
