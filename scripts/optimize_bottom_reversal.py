"""
底部反转策略 RL 分群调优引擎
================================
1. 加载CSI500成分股，按板块分组
2. 对每个板块用REINFORCE优化底部反转参数
3. 注册最优策略到信号系统
4. 输出对比表

优化参数空间:
  min_days:   [5, 10, 15, 20, 25, 30]
  max_days:   [25, 35, 45, 60, 75, 90]
  vol_ratio:  [0.2, 0.3, 0.4, 0.5, 0.6]  (筑底期缩量比例阈值)
  ma60_tol:   [0.90, 0.93, 0.95, 0.97, 0.98] (MA60容忍度)
  dif_thresh: [-5, -3, -1, 0, 2] (金叉时DIF/DEA允许最低值)
  gc_window:  [3, 5, 7, 10] (金叉检测窗口)
"""
import sys, os, json, random, math, time, sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd
import numpy as np

# ── 项目路径 ──
PROJ = Path('/Users/albertma/sourcecode/workspace/python/ai-trading-assistant')
sys.path.insert(0, str(PROJ))

DB_PATH = Path.home() / 'Jarvis' / 'ai_trading' / 'stock_archive.db'
CSI500_CSV = Path.home() / 'Jarvis/A股行情信息/中证500.csv'
STOCK_INFO_DB = Path.home() / 'Jarvis/ai_trading/stock_archive.db'

# ── 参数搜索空间 ──
PARAM_GRID = {
    'min_days': [5, 10, 15, 20, 25, 30],
    'max_days': [25, 35, 45, 60, 75, 90],
    'vol_ratio': [0.2, 0.3, 0.4, 0.5, 0.6],
    'ma60_tol': [0.90, 0.93, 0.95, 0.97, 0.98],
    'dif_thresh': [-5, -3, -1, 0, 2],
    'gc_window': [3, 5, 7, 10],
}

DEFAULT_PARAMS = {'min_days': 10, 'max_days': 45, 'vol_ratio': 0.4,
                  'ma60_tol': 0.95, 'dif_thresh': -1, 'gc_window': 5}

# ── 信号检测函数（从signal_registry移植核心逻辑） ──
def sma(arr, window):
    if len(arr) < window:
        return np.full_like(arr, np.nan)
    res = np.full_like(arr, np.nan)
    for i in range(window - 1, len(arr)):
        res[i] = np.nanmean(arr[i - window + 1:i + 1])
    return res

def detect_bottom_reversal(closes, highs, lows, opens, volumes, params):
    """简化版底部反转检测，返回买入信号列表"""
    n = len(closes)
    if n < 220:
        return []
    
    min_days = params['min_days']
    max_days = params['max_days']
    vol_ratio = params['vol_ratio']
    ma60_tol = params['ma60_tol']
    dif_thresh = params['dif_thresh']
    gc_window = params['gc_window']
    check_before = 10
    
    # 预计算指标
    ma5 = sma(closes, 5)
    ma10 = sma(closes, 10)
    ma20 = sma(closes, 20)
    ma60 = sma(closes, 60)
    
    exp12 = pd.Series(closes).ewm(span=12, adjust=False).mean().values
    exp26 = pd.Series(closes).ewm(span=26, adjust=False).mean().values
    macd_line = exp12 - exp26
    macd_signal = pd.Series(macd_line).ewm(span=9, adjust=False).mean().values
    
    vol_sma5 = sma(volumes, 5)
    vol_sma10 = sma(volumes, 10)
    
    signals = []
    max_lookback = max_days + 10
    min_bars = 220
    
    for i in range(min_bars, n):
        window_start = max(0, i - max_lookback)
        
        # 阶段④: MACD金叉
        gc_found = False
        gc_idx = None
        for j in range(max(window_start, i - gc_window), i + 1):
            if j < 1: continue
            if (not np.isnan(macd_line[j]) and not np.isnan(macd_line[j-1])
                and not np.isnan(macd_signal[j]) and not np.isnan(macd_signal[j-1])
                and macd_line[j-1] <= macd_signal[j-1] and macd_line[j] > macd_signal[j]
                and macd_line[j] >= dif_thresh and macd_signal[j] >= dif_thresh):
                gc_found = True
                gc_idx = j
                break
        
        if not gc_found: continue
        
        # 阶段②: 找死叉(DIF>0, DEA>0)
        death_indices = []
        for j in range(window_start, gc_idx):
            if j < 1: continue
            if (not np.isnan(macd_line[j]) and not np.isnan(macd_line[j-1])
                and not np.isnan(macd_signal[j]) and not np.isnan(macd_signal[j-1])
                and macd_line[j-1] >= macd_signal[j-1] and macd_line[j] < macd_signal[j]
                and macd_line[j] > 0 and macd_signal[j] > 0):
                death_indices.append(j)
        
        valid = [(gc_idx - d, d) for d in death_indices if min_days <= gc_idx - d <= max_days]
        if not valid: continue
        
        interval, death_idx = max(valid)
        
        # 阶段①: 死叉前多头排列
        pre_idx = death_idx - check_before
        if pre_idx < 200: continue
        if any(np.isnan(x) for x in [ma5[pre_idx], ma10[pre_idx], ma20[pre_idx], ma60[pre_idx]]):
            continue
        if not (ma5[pre_idx] > ma10[pre_idx] > ma20[pre_idx]): continue
        if closes[pre_idx] < ma60[pre_idx]: continue
        
        pre_ma60_lb = max(0, pre_idx - 5)
        if np.isnan(ma60[pre_idx]) or np.isnan(ma60[pre_ma60_lb]): continue
        if ma60[pre_idx] <= ma60[pre_ma60_lb]: continue
        
        # 阶段③: 筑底期价格在MA60附近
        price_ok = True
        for j in range(death_idx, gc_idx):
            if np.isnan(ma60[j]) or np.isnan(closes[j]): continue
            if closes[j] < ma60[j] * ma60_tol:
                price_ok = False
                break
        if not price_ok: continue
        
        # 阶段③: 缩量检查
        low_vol_count = 0
        total_check = 0
        for j in range(death_idx, gc_idx):
            if j < 10: continue
            if not np.isnan(vol_sma5[j]) and not np.isnan(vol_sma10[j]):
                total_check += 1
                if vol_sma5[j] < vol_sma10[j]:
                    low_vol_count += 1
        
        if total_check < 5 or low_vol_count < total_check * vol_ratio:
            continue
        
        # 阶段④: 放量确认
        vol_ok = False
        for offset in range(gc_window):
            vi = gc_idx + offset
            if vi >= n: break
            if not np.isnan(volumes[vi]) and not np.isnan(vol_sma5[vi]):
                if volumes[vi] > vol_sma5[vi]:
                    vol_ok = True
                    break
            if vi > 0 and not np.isnan(vol_sma5[vi]) and not np.isnan(vol_sma5[vi-1]) \
               and not np.isnan(vol_sma10[vi]) and not np.isnan(vol_sma10[vi-1]):
                if vol_sma5[vi-1] <= vol_sma10[vi-1] and vol_sma5[vi] > vol_sma10[vi]:
                    vol_ok = True
                    break
        
        if not vol_ok: continue
        
        # 信号确认 → T+1入场
        entry_idx = i + 1
        if entry_idx >= n: continue
        signals.append({
            'entry_idx': entry_idx,
            'entry_price': closes[entry_idx] if not np.isnan(closes[entry_idx]) else closes[i],
            'death_idx': death_idx,
            'gc_idx': gc_idx,
            'signal': f'底部反转({interval}d间隔)'
        })
    
    return signals


# ── 回测函数 ──
# ── 预加载K线缓存（避免每个epoch重复SQLite读取） ──
_kline_cache = {}

def preload_kline_group(stock_codes, max_days_back=500):
    """一次性加载板块所有K线数据到内存缓存"""
    key = tuple(sorted(stock_codes))
    if key in _kline_cache:
        return _kline_cache[key]
    
    data = {}
    for code in stock_codes:
        kline = load_kline(code, max_days_back)
        if kline is not None and len(kline) >= 250:
            data[code] = {
                'close': kline['close'].values.astype(float),
                'high': kline['high'].values.astype(float),
                'low': kline['low'].values.astype(float),
                'open': kline['open'].values.astype(float),
                'volume': kline['volume'].values.astype(float),
                'dates': [str(d.date()) for d in kline.index],  # 保存日期索引
            }
    _kline_cache[key] = data
    return data


def backtest_group(stock_codes, params, max_days_back=500, kline_data=None):
    """对一组股票跑底部反转回测，返回汇总指标
    可传入预加载的kline_data加速多epoch优化"""
    all_trades = []
    
    for code in stock_codes:
        if kline_data and code in kline_data:
            d = kline_data[code]
            closes, highs, lows, opens, volumes = d['close'], d['high'], d['low'], d['open'], d['volume']
        else:
            kline = load_kline(code, max_days_back)
            if kline is None or len(kline) < 250:
                continue
            closes = kline['close'].values.astype(float)
            highs = kline['high'].values.astype(float)
            lows = kline['low'].values.astype(float)
            opens = kline['open'].values.astype(float)
            volumes = kline['volume'].values.astype(float)
        
        signals = detect_bottom_reversal(closes, highs, lows, opens, volumes, params)
        
        for sig in signals:
            entry_idx = sig['entry_idx']
            if entry_idx >= len(closes) - 5:
                continue
            
            entry_p = sig['entry_price']
            exit_idx = None
            exit_p = None
            exit_reason = 'data_end'
            
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
                    exit_reason = 'macd_death'
                    break
            
            if exit_idx is None:
                exit_idx = len(closes) - 1
                exit_p = closes[-1]
            
            pnl = exit_p - entry_p
            ret = pnl / entry_p * 100
            holding = exit_idx - entry_idx
            
            if kline_data and code in kline_data:
                dates_list = kline_data[code]['dates']
            else:
                dates_list = [str(d.date()) for d in kline.index]
            
            all_trades.append({
                'code': code,
                'entry_date': dates_list[entry_idx],
                'exit_date': dates_list[exit_idx] if exit_idx < len(dates_list) else dates_list[-1],
                'entry_p': round(entry_p, 2),
                'exit_p': round(exit_p, 2),
                'pnl': round(pnl, 2),
                'ret': round(ret, 2),
                'holding': holding,
                'exit_reason': exit_reason,
            })
    
    if not all_trades:
        return None
    
    df_t = pd.DataFrame(all_trades)
    wins = df_t[df_t['pnl'] > 0]
    losses = df_t[df_t['pnl'] <= 0]
    total_pnl = df_t['pnl'].sum()
    win_rate = len(wins) / len(df_t) * 100 if len(df_t) > 0 else 0
    avg_win = wins['pnl'].mean() if len(wins) > 0 else 0
    avg_loss = abs(losses['pnl'].mean()) if len(losses) > 0 else 1
    profit_factor = (wins['pnl'].sum() / abs(losses['pnl'].sum())) if len(losses) > 0 and losses['pnl'].sum() != 0 else (99 if len(wins) > 0 else 0)
    avg_hold = df_t['holding'].mean()
    
    # 期望值
    ew = (win_rate / 100) * (avg_win / avg_loss if avg_loss > 0 else 99) - (1 - win_rate / 100)
    
    return {
        'trades': len(df_t),
        'win_rate': round(win_rate, 1),
        'total_pnl': round(total_pnl, 2),
        'profit_factor': round(profit_factor, 2),
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'avg_hold': round(avg_hold, 1),
        'ew': round(ew, 3),
    }


def load_kline(code, max_days=500):
    """从SQLite加载K线数据"""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cutoff = (datetime.now() - timedelta(days=max_days * 1.5)).strftime('%Y-%m-%d')
        df = pd.read_sql(
            f"SELECT date AS trade_date, open, close, high, low, volume FROM kline_daily "
            f"WHERE code=? AND date>=? ORDER BY date ASC",
            conn, params=(code, cutoff))
        if len(df) < 200:
            return None
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df.set_index('trade_date', inplace=True)
        return df
    except Exception:
        return None
    finally:
        conn.close()


# ── REINFORCE 优化 ──
def reinforce_optimize(stock_codes, group_name, n_epochs=50, alpha=0.1, kline_data=None):
    """REINFORCE算法优化策略参数（支持预加载kline_data）"""
    print(f'\n  🔄 REINFORCE优化 [{group_name}] ({len(stock_codes)}只, {n_epochs}轮)...')
    
    # 参数编码: 每个参数离散值 → 概率权重
    param_keys = list(PARAM_GRID.keys())
    
    # 初始化策略权重 (softmax logits)
    theta = {}
    for k in param_keys:
        theta[k] = np.zeros(len(PARAM_GRID[k]))
    
    # 基线: 默认参数（使用预加载数据）
    baseline = backtest_group(stock_codes, DEFAULT_PARAMS, kline_data=kline_data)
    baseline_score = _calc_score(baseline) if baseline else -999
    print(f'    基线({DEFAULT_PARAMS}): trades={baseline["trades"] if baseline else 0}, '
          f'wr={baseline["win_rate"] if baseline else 0}%, '
          f'pnl={baseline["total_pnl"] if baseline else 0}, '
          f'score={baseline_score:.2f}')
    
    best_score = baseline_score
    best_params = dict(DEFAULT_PARAMS)
    best_result = baseline
    history = []
    
    for epoch in range(n_epochs):
        # 从策略中采样参数
        params = {}
        log_prob = 0
        for k in param_keys:
            probs = _softmax(theta[k])
            idx = np.random.choice(len(probs), p=probs)
            params[k] = PARAM_GRID[k][idx]
            log_prob += math.log(probs[idx] + 1e-10)
        
        # 跑回测（使用预加载数据）
        result = backtest_group(stock_codes, params, kline_data=kline_data)
        score = _calc_score(result) if result else -999
        
        history.append({'epoch': epoch, 'params': params.copy(), 'score': score, 'result': result})
        
        # REINFORCE更新
        advantage = score - baseline_score
        if advantage > 0 and result:
            grad = advantage * alpha
            for k in param_keys:
                idx = PARAM_GRID[k].index(params[k])
                theta[k][idx] += grad
        
        # 跟踪最优
        if score > best_score and result:
            best_score = score
            best_params = dict(params)
            best_result = result
        
        if (epoch + 1) % 20 == 0 or epoch == 0:
            lr = f'wr={result["win_rate"] if result else 0}%'
            lp = f'pnl={result["total_pnl"] if result else 0}'
            print(f'    epoch {epoch+1}/{n_epochs}: {params} → {lr} {lp} score={score:.2f} (adv={advantage:+.2f})')
    
    print(f'  ✅ 最优: {best_params}')
    print(f'     trades={best_result["trades"]}, wr={best_result["win_rate"]}%, '
          f'pnl={best_result["total_pnl"]}, pf={best_result["profit_factor"]}, '
          f'score={best_score:.2f}')
    
    return best_params, best_result, history


def _softmax(x):
    e_x = np.exp(x - np.max(x))
    return e_x / e_x.sum()


def _calc_score(result):
    """综合评分: 期望值优先，兼顾交易次数"""
    if result is None or result['trades'] < 3:
        return -999
    # 核心: 期望值 × sqrt(交易数) — 平衡质量和数量
    return result['ew'] * math.sqrt(result['trades'])


# ── 加载CSI500成分股信息 ──
def load_csi500_codes_with_industry():
    conn = sqlite3.connect(str(STOCK_INFO_DB))
    df = pd.read_csv(str(CSI500_CSV), encoding='utf-16', sep='\t')
    codes = []
    for _, r in df.iterrows():
        c = str(r['代码']).strip("'\"")
        if not c.startswith('BK') and c != '中证500_':
            codes.append(c)
    
    placeholders = ','.join(['?'] * len(codes))
    cur = conn.execute(f"SELECT code, industry FROM stock_info WHERE code IN ({placeholders})", codes)
    code_to_ind = dict(cur.fetchall())
    conn.close()
    
    groups = defaultdict(list)
    for c in codes:
        ind = code_to_ind.get(c, '其他')
        if ind and ind != '--':
            groups[ind].append(c)
    
    return groups, codes


# ── 主流程 ──
def main():
    print('=' * 70)
    print('底部反转策略 RL 分群调优')
    print('=' * 70)
    
    groups, all_codes = load_csi500_codes_with_industry()
    print(f'\nCSI500共{len(all_codes)}只股票，分为{len(groups)}个行业')
    
    # 选择有足够股票的板块（≥8只）
    valid_groups = {k: v for k, v in groups.items() if len(v) >= 8}
    print(f'其中≥8只的板块: {len(valid_groups)}个\n')
    
    # 对所有股票做基线
    print('━' * 50)
    print('📊 全量基线回测（默认参数）')
    all_result = backtest_group(all_codes, DEFAULT_PARAMS)
    if all_result:
        print(f'  全部CSI500({len(all_codes)}只): trades={all_result["trades"]}, '
              f'wr={all_result["win_rate"]}%, pnl={all_result["total_pnl"]}, '
              f'pf={all_result["profit_factor"]}, score={_calc_score(all_result):.2f}')
    
    # ── 设置检查点文件 ──
    CHECKPOINT_FILE = PROJ / 'data/rl_checkpoint.json'
    if not os.path.exists(PROJ / 'data'):
        os.makedirs(PROJ / 'data')
    
    # 加载已有检查点（支持断点续跑）
    completed = []
    if CHECKPOINT_FILE.exists():
        try:
            checkpoint_data = json.loads(CHECKPOINT_FILE.read_text())
            completed = checkpoint_data.get('completed', [])
            print(f'📌 检测到已有检查点: 已完成 {len(completed)} 个板块')
        except Exception:
            pass
    
    # 分板块调优
    results = {}
    for name, codes in sorted(valid_groups.items(), key=lambda x: -len(x[1])):
        if name in completed:
            print(f'\n⏭ {name} 已优化，跳过')
            continue
        
        print(f'\n{"━" * 50}')
        print(f'📈 {name} ({len(codes)}只)')
        
        # 预加载K线数据（一次性加载，避免每个epoch重复读取）
        t0 = time.time()
        kline_data = preload_kline_group(codes)
        print(f'  ⏳ K线数据加载: {len(kline_data)}/{len(codes)} 只 OK ({time.time()-t0:.1f}s)')
        
        if len(kline_data) < 5:
            print('  ⏭ 跳过（可用K线数据太少）')
            continue
        
        # 板块基线（使用预加载数据）
        grp_base = backtest_group(codes, DEFAULT_PARAMS, kline_data=kline_data)
        base_score = _calc_score(grp_base) if grp_base else -999
        if grp_base:
            print(f'  基线: trades={grp_base["trades"]}, wr={grp_base["win_rate"]}%, '
                  f'pnl={grp_base["total_pnl"]}, pf={grp_base["profit_factor"]}, score={base_score:.2f}')
        
        if not grp_base or grp_base['trades'] < 3:
            print('  ⏭ 跳过（交易太少）')
            completed.append(name)
            json.dump({'completed': completed, 'results': results}, open(CHECKPOINT_FILE, 'w'))
            continue
        
        # REINFORCE优化（传入预加载数据）
        best_p, best_r, hist = reinforce_optimize(codes, name, n_epochs=50, kline_data=kline_data)
        
        results[name] = {
            'codes': len(codes),
            'baseline': grp_base,
            'best_params': best_p,
            'best_result': best_r,
            'improvement': round(_calc_score(best_r) - base_score, 2) if best_r else 0,
        }
        
        # 保存检查点
        completed.append(name)
        json.dump({'completed': completed, 'results': results}, open(CHECKPOINT_FILE, 'w'), ensure_ascii=False, indent=2)
        print(f'  💾 检查点已保存 ({len(completed)}/{len(valid_groups)})')
    
    # ── 输出汇总表 ──
    print('\n' + '=' * 70)
    print('📊 分板块策略优化汇总')
    print('=' * 70)
    header = f'{"板块":<12} {"只数":>4} {"基线交易":>8} {"基线WR":>8} {"基线PnL":>10} {"最优WR":>8} {"最优PnL":>10} {"改进分":>8} {"参数":>30}'
    print(header)
    print('-' * 100)
    
    for name, r in sorted(results.items(), key=lambda x: -x[1]['best_result']['trades']):
        b = r['baseline']
        br = r['best_result']
        p = r['best_params']
        p_str = f'min={p["min_days"]} max={p["max_days"]} vol={p["vol_ratio"]} tol={p["ma60_tol"]} dif={p["dif_thresh"]}'
        print(f'{name[:12]:<12} {r["codes"]:>4} {b["trades"]:>8} {b["win_rate"]:>8}% {b["total_pnl"]:>10.1f} '
              f'{br["win_rate"]:>8}% {br["total_pnl"]:>10.1f} {r["improvement"]:>+8.2f} {p_str}')
    
    # ── 注册策略 ──
    print('\n' + '=' * 70)
    print('🔌 注册优化后策略到信号系统')
    print('=' * 70)
    
    # 生成signal_registry补丁
    patch_lines = ['# === RL优化底部反转策略（分板块） ===']
    for name, r in sorted(results.items(), key=lambda x: -x[1]['best_result']['trades']):
        if r['improvement'] <= 0 and r['best_result']['ew'] < 0.1:
            continue
        p = r['best_params']
        safe_name = f'bottom_reversal_{name[:8]}'
        # 清理特殊字符
        safe_name = safe_name.replace('Ⅱ', '2').replace(' ', '_').replace('(', '').replace(')', '')
        label = f'{name}底部反转(RL优化:min={p["min_days"]},max={p["max_days"]},vol={p["vol_ratio"]},dif={p["dif_thresh"]})'
        patch_lines.append(f'    "{safe_name}": ("bottom_reversal", "macd_death", 0.0),  # {label}')
        patch_lines.append(f'# STRATEGY_PRESETS[{safe_name}] = ("bottom_reversal", "macd_death", 0.0)')
    
    for line in patch_lines:
        print(f'  {line}')
    
    print('\n✅ 完成')
    return results


if __name__ == '__main__':
    main()
