#!/opt/anaconda3/bin/python3
"""
每日A股复盘报告生成器 — 可被cron job重复调用。

用法:
    /opt/anaconda3/bin/python3 generate-daily-replay.py [YYYY-MM-DD]

若未传日期参数，自动取今天日期。
前置条件: 后端运行在 localhost:8080, 且已依次调用了
    POST /sector-dispersion/refresh
    GET  /sector-cycles
    POST /sector-indices/refresh

输出: ~/Jarvis/复盘/A股复盘_YYYY-MM-DD.md
"""

import json, os, subprocess, sys
from pathlib import Path

import pandas as pd

DATE = sys.argv[1] if len(sys.argv) > 1 else os.popen("date '+%Y-%m-%d'").read().strip()
WEEKDAY = os.popen(f"date -j -f '%Y-%m-%d' '{DATE}' '+%A'").read().strip()
DATA_DIR = os.path.expanduser("~/Jarvis/A股行情信息")
REPLAY_DIR = os.path.expanduser("~/Jarvis/复盘")
os.makedirs(REPLAY_DIR, exist_ok=True)

csv_path = os.path.join(DATA_DIR, f"沪深京A股{DATE}.csv")
if not os.path.exists(csv_path):
    print(f"NO_DATA: {csv_path} not found")
    sys.exit(0)


def _get_api(path: str) -> dict:
    try:
        r = subprocess.run(
            ["curl", "-s", f"http://localhost:8080{path}"],
            capture_output=True, text=True, timeout=15,
        )
        return json.loads(r.stdout) if r.stdout.strip() else {}
    except Exception:
        return {}


# ── 1. 从CSV读取基本统计 ──────────────────────────────────
df = pd.read_csv(csv_path, sep="\t", encoding="utf-16", dtype_backend="numpy_nullable")
chg_col = "涨幅" if "涨幅" in df.columns else "涨跌幅"
for c in [chg_col, "总市值", "成交额"]:
    if c in df.columns:
        df[c] = pd.to_numeric(
            df[c].astype(str).str.replace("--", "").str.replace("%", ""),
            errors="coerce",
        ).fillna(0)

total = len(df)
up = int((df[chg_col] > 0).sum())
down = int((df[chg_col] < 0).sum())
flat = total - up - down
ratio_total = up + down
up_ratio = round(up / ratio_total * 100, 1) if ratio_total else 0
avg_chg = round(df[chg_col].mean(), 2)
dispersion = round(df[chg_col].std(), 2)
limit_up = int((df[chg_col] > 9.8).sum())
limit_down = int((df[chg_col] < -9.8).sum())

# ── 2. 情绪周期 ──────────────────────────────────────────
sentiment = _get_api(f"/api/v1/market/sentiment-cycle?days=7")
srows, cstage, pstage, pdate, outlook = "", "N/A", "N/A", "N/A", "N/A"
if sentiment and "records" in sentiment:
    recs = sentiment["records"]
    for d in recs:
        sl = d.get("stage_label") or d.get("stage", "—")
        srows += f"| {d.get('date','')} | {sl} | {d.get('ratio',0):.2f} | {d.get('limit_up',0)} | {d.get('avg_change_pct',0):.2f}% |\n"
    cstage = sentiment.get("current_label", "N/A")
    # prev day = second-to-last record, or first if only one
    if len(recs) >= 2:
        pstage = recs[-2].get("stage_label", "N/A")
        pdate = recs[-2].get("date", "N/A")
    elif len(recs) == 1:
        pstage = "only_one_day"
        pdate = recs[0].get("date", "N/A")
    # assessment is a dict: {ratio_trend, avg_trend, limit_trend, outlook}
    assessment = sentiment.get("assessment", {})
    outlook = assessment.get("outlook", "N/A")
else:
    # fallback: 手动分类
    if up_ratio < 35:
        fallback_stage = "冰点期 ❄️"
    elif up_ratio > 65:
        fallback_stage = "发酵期 🟢"
    else:
        fallback_stage = "过渡期 ⚖️"
    srows = f"| {DATE} | {fallback_stage} | {up_ratio}% | {limit_up} | {avg_chg}% |\n"
    cstage = fallback_stage
    outlook = "wait_for_signal"

# ── 3. 指数 ──────────────────────────────────────────────
idx = _get_api("/api/v1/market/index-history?days=60")
hs_list = idx.get("hs300", [])
zz_list = idx.get("zz500", [])
rt_list = idx.get("ratio", [])
hs_val = round(hs_list[-1]["close"], 2) if hs_list else "N/A"
zz_val = round(zz_list[-1]["close"], 2) if zz_list else "N/A"
rt_val = round(rt_list[-1]["ratio"], 3) if rt_list else "N/A"

# ── 4. 板块轮动 ──────────────────────────────────────────
overview = _get_api(f"/api/v1/market/overview?date={DATE}&session=close")
cycles = _get_api(f"/api/v1/mental/sector-cycles?date={DATE}")

# hot sectors from overview
hs_list_api = overview.get("hot_sectors", [])
hot_sectors = ""
for i, h in enumerate(hs_list_api[:10], 1):
    hot_sectors += (
        f"| {i} | {h.get('name','')} | {h.get('avg_change',0):+.2f}%"
        f" | {h.get('up_pct',0):.0f}% | {h.get('count',0)}只 |\n"
    )

# cold sectors from cycles (126 sectors, sorted ascending)
secs = cycles.get("sectors", [])
cold_sectors = ""
if secs:
    cold = sorted(secs, key=lambda s: s.get("avg_change", 0))[:5]
    for i, c in enumerate(cold, 1):
        cold_sectors += f"| {i} | {c['sector']} | {c.get('avg_change',0):+.2f}% |\n"
    # phase distribution
    pc: dict[str, int] = {}
    for s in secs:
        p = s.get("phase", "unknown")
        pc[p] = pc.get(p, 0) + 1
    sp = sorted(pc.items(), key=lambda x: -x[1])
    phase_dist = "\n".join(f"- **{p}**: {c}个板块" for p, c in sp)
    # focus: 复苏/启动/酝酿 phases
    fkw = ["启动", "酝酿", "复苏"]
    focus = sorted(
        [s for s in secs if any(f in (s.get("phase", "") or "") for f in fkw)],
        key=lambda s: s.get("avg_change", 0), reverse=True,
    )[:5]
    fo = "\n".join(
        f"- **{s['sector']}** ({s.get('avg_change',0):+.2f}%, {s.get('phase','')})"
        for s in focus
    ) or "- 无明确复苏/启动信号板块\n"
else:
    cold_sectors = "N/A"
    phase_dist = "N/A"
    fo = "- 无板块周期数据\n"

# ── 5. 成交额 TOP10 ──────────────────────────────────────
volume_top10 = ""
for v in overview.get("top_volume", []):
    volume_top10 += (
        f"| {v['name']}({v['code']}) | {v.get('amount',0):.1f}亿"
        f" | {v.get('change_pct',0):+.2f}% |\n"
    )

# ── 6. 涨幅/跌幅 TOP5 ────────────────────────────────────
gainers_top5 = "".join(
    f"| {i} | {v['name']}({v['code']}) | {v.get('change_pct',0):+.2f}% |\n"
    for i, v in enumerate(overview.get("top_gainers", [])[:5], 1)
)
losers_top5 = "".join(
    f"| {i} | {v['name']}({v['code']}) | {v.get('change_pct',0):+.2f}% |\n"
    for i, v in enumerate(overview.get("top_losers", [])[:5], 1)
)

# ── 7. 思维模型问题 ──────────────────────────────────────
top_name = hs_list_api[0].get("name", "市场") if hs_list_api else "市场"
top_chg = hs_list_api[0].get("avg_change", 0) if hs_list_api else 0
cold_name = cold[0]["sector"] if secs and cold else "某板块"
cold_chg = cold[0].get("avg_change", 0) if secs and cold else 0

# 找次强板块用于题目3
second_name = hs_list_api[1].get("name", "次强板块") if len(hs_list_api) > 1 else "次强板块"
second_chg = hs_list_api[1].get("avg_change", 0) if len(hs_list_api) > 1 else 0

bg1 = (
    f"今日{top_name}板块逆势大涨{top_chg:+.2f}%"
    f"（全市场均跌幅{avg_chg}%），"
    f"{second_name}({second_chg:+.2f}%)板块同步走强。"
)
bg2 = (
    f"今日涨停{limit_up}只、跌停{limit_down}只，"
    f"市场涨跌比仅{up_ratio}%（{up}涨/{down}跌），普跌格局明显。"
)
bg3 = (
    f"今日{top_name}({top_chg:+.2f}%)"
    f"与{cold_name}({cold_chg:+.2f}%)走势严重分化，"
    f"同时{second_name}({second_chg:+.2f}%)也表现强势。"
)

report = f"""# A股复盘日报 — {DATE}（{WEEKDAY}）

---

## 📊 一、市场总览

| 指标 | 数值 |
|------|------|
| 总股票数 | {total}只 |
| 上涨 | **{up}只** |
| 下跌 | {down}只 |
| 平盘 | {flat}只 |
| **涨跌比** | **{up_ratio}%** |
| **均涨幅** | **{avg_chg}%** |
| 市场分化度 σ | {dispersion} |
| 涨停 | 🚀 **{limit_up}只** |
| 跌停 | 💀 {limit_down}只 |

**沪深300**: {hs_val} | **中证500**: {zz_val} | **沪深300/中证500**: {rt_val}

---

## 🔥 二、情绪周期分析

| 日期 | 阶段 | 涨跌比 | 涨停 | 均涨幅 |
|------|------|--------|------|--------|
{srows}

**当前阶段**: {cstage}
**上日阶段**: {pstage}（{pdate}）
**综合判断**: {outlook}

---

## 🏭 三、板块轮动分析

### 🔥 最强板块 TOP 10

| # | 板块 | 均涨幅 | 涨比 | 成份股 |
|---|------|--------|------|--------|
{hot_sectors}

### ❄️ 最弱板块 TOP 5

| # | 板块 | 均涨幅 |
|---|------|--------|
{cold_sectors}

### 📌 板块周期分布

{phase_dist}

**重点机会方向**：
{fo}

---

## 💰 四、成交额排名 TOP 10

| 股票 | 成交额 | 涨幅 |
|------|--------|------|
{volume_top10}

---

## 📈 五、涨幅/跌幅 TOP 5

### 🚀 涨幅榜

| # | 股票 | 涨幅 |
|---|------|------|
{gainers_top5}

### 💀 跌幅榜

| # | 股票 | 跌幅 |
|---|------|------|
{losers_top5}

---

## 🧠 六、今日思维模型训练

基于今日（{DATE}）市场数据，请完成以下3道思维模型训练题：

### 🎯 题目1：二阶效应（第二层思维）

> **背景**: {bg1}
>
> **第二层思考（请回答）**:
> 市场普遍认为强势板块今日上涨是「行情启动」。但如果这是短期资金避险或事件驱动，而非景气反转呢？哪些信号可以提前识别「假启动」？

### 🎯 题目2：反脆弱 — 尾部风险管理

> **背景**: {bg2}
>
> **请回答**:
> 1. 如果明天再跌1%，哪些持仓会触发止损？
> 2. 今日逆势的{top_name}({top_chg:+.2f}%)板块如果补跌，对你的净值影响多大？
> 3. 列举至少一个「反脆弱措施」应对当前格局。

### 🎯 题目3：行业生命周期 — 景气相位推演

> **背景**: {bg3}
>
> **请回答**:
> 1. {top_name}（{top_chg:+.2f}%）在产业链中处于什么位置？驱动因素是什么？
> 2. {cold_name}（{cold_chg:+.2f}%）与{top_name}的严重分化说明资金在如何轮动？需要什么数据验证？
> 3. 次强板块的上涨是独立逻辑还是产业链上下游传导？

---

*报告生成时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}*
*数据来源: 腾讯行情API / 东方财富行情CSV / akshare*
*板块周期系统: 12相体系 v2026-05-07*
"""

out_path = os.path.join(REPLAY_DIR, f"A股复盘_{DATE}.md")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(report)
print(f"OK:{out_path}")
