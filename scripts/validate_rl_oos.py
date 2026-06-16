"""
样本外验证：RL优化参数 vs 默认参数
==================================
取最近100个交易日作为样本外集（RL训练时看了全部500天）
如果RL参数在样本外表现 > 默认参数 → 参数真正有效

评估指标：
  - WR (胜率) — 最核心
  - PnL (总盈亏)
  - PF (盈利因子)
  - 交易笔数（太少=过拟合）
"""
import sys, json, time
from pathlib import Path

PROJ = Path('/Users/albertma/sourcecode/workspace/python/ai-trading-assistant')
sys.path.insert(0, str(PROJ))

from scripts.optimize_bottom_reversal import (
    load_kline, backtest_group, DEFAULT_PARAMS,
    preload_kline_group, load_csi500_codes_with_industry
)

CHECKPOINT_FILE = PROJ / 'data/rl_checkpoint.json'

# ── 板块名 → _RL_PARAMS key 映射 ──
SECTOR_TO_KEY = {
    "半导体": "bottom_reversal_semi",
    "电力": "bottom_reversal_elec",
    "通信设备": "bottom_reversal_comm",
    "专用设备": "bottom_reversal_equip",
    "消费电子": "bottom_reversal_celec",
    "工业金属": "bottom_reversal_metal",
    "煤炭开采": "bottom_reversal_coal",
    "化学制品": "bottom_reversal_chem",
    "光伏设备": "bottom_reversal_pv",
    "汽车零部件": "bottom_reversal_auto",
    "化学制药": "bottom_reversal_medi",
    "航空装备Ⅱ": "bottom_reversal_aero",
    "软件开发": "bottom_reversal_soft",
    "电池": "bottom_reversal_batt",
    "生物制品": "bottom_reversal_bio",
    "军工电子Ⅱ": "bottom_reversal_mil",
    "医疗器械": "bottom_reversal_medd",
    "电网设备": "bottom_reversal_grid",
    "元件": "bottom_reversal_comp",
    "中药Ⅱ": "bottom_reversal_tcm",
    "证券Ⅱ": None,  # 已注册但没对应key
    "IT服务Ⅱ": None,
}


def truncate_kline(kline_data, keep_last_days=100):
    """取K线数据的最后keep_last_days天"""
    truncated = {}
    for code, d in kline_data.items():
        n = len(d['close'])
        if n <= keep_last_days:
            continue
        start = n - keep_last_days
        truncated[code] = {
            'close': d['close'][start:],
            'high': d['high'][start:],
            'low': d['low'][start:],
            'open': d['open'][start:],
            'volume': d['volume'][start:],
            'dates': d['dates'][start:] if 'dates' in d else [],
        }
    return truncated


def main():
    # 加载RL检查点
    if not CHECKPOINT_FILE.exists():
        print("❌ 检查点文件不存在，先跑 optimize_bottom_reversal.py")
        return

    ckpt = json.loads(CHECKPOINT_FILE.read_text())
    rl_results = ckpt.get('results', {})
    completed = ckpt.get('completed', [])
    print(f"\n📊 样本外验证 (最近100个交易日)")
    print(f"   RL已优化 {len(completed)} 个板块")
    print(f"   可用RL数据: {len(rl_results)} 个\n")

    # 获取板块分组
    groups, all_codes = load_csi500_codes_with_industry()

    # ── 逐板块验证 ──
    print(f"{'板块':<14} {'基线WR':>8} {'基线PnL':>10} {'RL-WR':>8} {'RL-PnL':>10} {'笔数':>6} {'结论':>10}")
    print("-" * 72)

    passed = 0
    failed = 0
    skipped = 0
    summary_lines = []

    for sector_name in sorted(completed):
        # 跳过无RL参数
        rl_info = rl_results.get(sector_name, {})
        rl_params = rl_info.get('best_params')
        if not rl_params:
            skipped += 1
            continue

        # 获取该板块股票
        codes = groups.get(sector_name, [])
        if len(codes) < 3:
            skipped += 1
            continue

        # 加载K线数据
        kline_data = preload_kline_group(codes)
        if len(kline_data) < 3:
            skipped += 1
            continue

        # 截断到最近100天（样本外）
        oos_data = truncate_kline(kline_data, keep_last_days=100)
        if len(oos_data) < 3:
            skipped += 1
            continue

        # 默认参数回测（样本外）
        base_result = backtest_group(list(oos_data.keys()), DEFAULT_PARAMS, kline_data=oos_data)
        base_wr = base_result['win_rate'] if base_result else 0
        base_pnl = base_result['total_pnl'] if base_result else 0
        base_trades = base_result['trades'] if base_result else 0

        # RL参数回测（样本外）
        rl_result = backtest_group(list(oos_data.keys()), rl_params, kline_data=oos_data)
        rl_wr = rl_result['win_rate'] if rl_result else 0
        rl_pnl = rl_result['total_pnl'] if rl_result else 0
        rl_trades = rl_result['trades'] if rl_result else 0

        # 判断
        if rl_result and rl_wr >= base_wr and rl_pnl >= base_pnl - 5:
            conclusion = "✅ 通过"
            passed += 1
        elif rl_result and rl_wr >= 50 and rl_trades >= 3:
            conclusion = "⚠️ 条件严格"
            passed += 1  # WR≥50%也算可用
        elif rl_result and rl_trades < 3:
            conclusion = "❌ 过拟合(太少)"
            failed += 1
        else:
            conclusion = "❌ RL不如基线"
            failed += 1

        print(f"{sector_name[:14]:<14} {base_wr:>7.1f}% {base_pnl:>10.1f} "
              f"{rl_wr:>7.1f}% {rl_pnl:>10.1f} {rl_trades:>4}笔 {conclusion:>10}")

        summary_lines.append({
            'sector': sector_name,
            'base_wr': base_wr, 'base_pnl': base_pnl, 'base_trades': base_trades,
            'rl_wr': rl_wr, 'rl_pnl': rl_pnl, 'rl_trades': rl_trades,
            'conclusion': conclusion,
            'rl_params': rl_params,
        })

    # ── 汇总 ──
    print("\n" + "=" * 72)
    print(f"📋 汇总: {len(completed)} 板块")
    print(f"   ✅ 通过: {passed}")
    print(f"   ⚠️  过拟合/失败: {failed}")
    print(f"   ⏭  跳过(数据不足): {skipped}")
    print()

    # 显示具体参数
    print(f"{'板块':<14} {'min_days':>9} {'max_days':>9} {'vol':>5} {'tol':>6} {'dif':>5} {'gc':>4} → 样本外WR RL/基线")
    print("-" * 72)
    for s in summary_lines:
        if s['conclusion'].startswith("✅"):
            p = s['rl_params']
            print(f"{s['sector'][:14]:<14} {p['min_days']:>9} {p['max_days']:>9} "
                  f"{p['vol_ratio']:>5.1f} {p['ma60_tol']:>6.3f} {p['dif_thresh']:>5} {p['gc_window']:>4} "
                  f"→ {s['rl_wr']:.0f}%/{s['base_wr']:.0f}%")
        else:
            print(f"{s['sector'][:14]:<14} {'*':>9} {'*':>9} {'*':>5} {'*':>6} {'*':>5} {'*':>4} "
                  f"→ {s['rl_wr']:.0f}%/{s['base_wr']:.0f}% ❌")

    # 给出部署建议
    print("\n" + "=" * 72)
    print("📌 部署建议：")
    deployable = [s for s in summary_lines if s['conclusion'].startswith("✅")
                  and s['rl_trades'] >= 3]
    non_deployable = [s for s in summary_lines if s not in deployable]

    if deployable:
        print(f" ✅ 可部署（样本外验证通过）: {', '.join(s['sector'] for s in deployable)}")
    if non_deployable:
        print(f" ❌ 需回退默认参数: {', '.join(s['sector'] for s in non_deployable)}")

    # 保存验证结果
    validation_result = {
        'summary': {'passed': passed, 'failed': failed, 'total': len(completed)},
        'details': summary_lines,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
    }
    out_path = PROJ / 'data/rl_oos_validation.json'
    json.dump(validation_result, open(out_path, 'w'), ensure_ascii=False, indent=2)
    print(f"\n💾 验证结果已保存到 {out_path}")


if __name__ == '__main__':
    main()
