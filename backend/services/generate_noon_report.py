"""午盘分析报告生成器
读取 noon 行情CSV，生成盘中市场概览报告。
"""
import sys
from datetime import date
from pathlib import Path
import pandas as pd

HOME = Path.home()
MARKET_DATA_DIR = HOME / "Jarvis" / "A股行情信息"
REPORT_DIR = HOME / "Jarvis" / "复盘"

COL_MAP = {
    "代码": "code", "名称": "name", "最新": "close", "涨幅": "change_pct",
    "涨跌": "change", "成交量": "volume", "成交额": "amount",
    "换手": "turnover", "市盈率": "pe", "所属行业": "sector",
    "最高": "high", "最低": "low", "开盘": "open", "昨收": "pre_close",
    "振幅": "amplitude", "量比": "volume_ratio", "均价": "avg_price",
    "市净率": "pb", "总市值": "total_mv", "流通市值": "float_mv",
}


def read_noon_csv(date_str: str) -> pd.DataFrame | None:
    """读取指定日期的午盘CSV"""
    fname = MARKET_DATA_DIR / f"沪深京A股{date_str}_noon.csv"
    if not fname.exists():
        return None
    try:
        df = pd.read_csv(fname, encoding="utf-16", sep="\t", engine="python")
        if df.empty:
            return None
        if "代码" in df.columns:
            df["代码"] = df["代码"].astype(str).str.strip("'\"")
        rename = {k: v for k, v in COL_MAP.items() if k in df.columns}
        df = df.rename(columns=rename)
        return df
    except Exception:
        return None


def generate_noon_report(date_str: str) -> str:
    """生成午盘分析报告"""
    df = read_noon_csv(date_str)
    if df is None:
        return f"⚠️ 未找到 {date_str} 的午盘数据（文件不存在或为空）"

    dt = pd.Timestamp(date_str)
    weekday_name = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][dt.weekday()]

    valid = df[df["change_pct"].notna()].copy()
    valid["change_pct"] = pd.to_numeric(valid["change_pct"], errors="coerce")
    valid["amount"] = pd.to_numeric(valid["amount"], errors="coerce")

    total = len(df)
    up = int((valid["change_pct"] > 0).sum())
    down = int((valid["change_pct"] < 0).sum())
    flat = int((valid["change_pct"] == 0).sum())
    limit_up = int((valid["change_pct"] >= 9.8).sum())
    limit_down = int((valid["change_pct"] <= -9.8).sum())
    avg_change = round(float(valid["change_pct"].mean()), 2)
    dispersion = round(float(valid["change_pct"].std()), 2)
    total_amount = round(float(valid["amount"].sum()) / 1e8, 0)
    ratio = round(up / down, 2) if down > 0 else up

    # 板块统计
    sector_data = {}
    if "sector" in valid.columns:
        sv = valid[valid["sector"].notna() & (valid["sector"] != "--")].copy()
        if not sv.empty:
            ss = sv.groupby("sector").agg(
                avg_change=("change_pct", "mean"),
                up_pct=("change_pct", lambda x: (x > 0).sum() / len(x) * 100),
                count=("change_pct", "count"),
            ).reset_index()
            ss["avg_change"] = ss["avg_change"].round(2)
            ss["up_pct"] = ss["up_pct"].round(1)
            ok = ss[ss["count"] >= 5]
            sector_data["top"] = ok.sort_values("avg_change", ascending=False).head(8).to_dict("records")
            sector_data["worst"] = ok.sort_values("avg_change", ascending=True).head(8).to_dict("records")

    # 成交额TOP10
    top_vol = valid.dropna(subset=["amount"]).sort_values("amount", ascending=False).head(10)

    # 涨跌幅TOP5
    top_up = valid.sort_values("change_pct", ascending=False).head(5)
    top_down = valid.sort_values("change_pct", ascending=True).head(5)

    lines = []
    lines.append(f"# 午盘分析报告 {date_str}（{weekday_name}）\n")
    lines.append(f"> 🕐 {date_str} 午盘 | 总股票 {total}只 | 上涨 {up} ({round(up/total*100,1)}%) | 下跌 {down} ({round(down/total*100,1)}%) | 平盘 {flat} ({round(flat/total*100,1)}%)\n")
    lines.append("---\n")

    lines.append("## 一、盘中概览\n")
    lines.append("| 指标 | 数值 |")
    lines.append("|------|------|")
    lines.append(f"| 上涨家数 | {up} ({round(up/total*100,1)}%) |")
    lines.append(f"| 下跌家数 | {down} ({round(down/total*100,1)}%) |")
    lines.append(f"| **涨跌比** | **{ratio}** |")
    lines.append(f"| **平均涨幅** | **{avg_change}%** |")
    lines.append(f"| **涨停** | **{limit_up}只** |")
    lines.append(f"| **跌停** | **{limit_down}只** |")
    lines.append(f"| **涨停/跌停比** | **{round(limit_up/max(limit_down,1),2)}** |")
    disp_label = "高位波动" if dispersion > 3 else ("中位波动" if dispersion > 2 else "低位波动")
    lines.append(f"| **市场离散度** | **{dispersion}**（{disp_label}） |")
    lines.append(f"| **半日成交额** | **{total_amount:.0f}亿** |")
    lines.append("")
    lines.append("> ⚠️ 数据为午盘盘中快照，非收盘最终数据\n")
    lines.append("---\n")

    # 成交额TOP10
    lines.append("## 二、半日成交额排名（Top 10）\n")
    lines.append("| 排名 | 股票 | 涨幅 | 成交额(亿) | 所属行业 |")
    lines.append("|------|------|------|-----------|---------|")
    for i, (_, r) in enumerate(top_vol.iterrows(), 1):
        name = r.get("name", "--")
        code = str(r.get("code", ""))
        chg = r.get("change_pct", 0)
        amt = round(r.get("amount", 0) / 1e8, 1) if r.get("amount") else 0
        sector = r.get("sector", "--")
        chg_str = f"**+{chg:.2f}%**" if chg >= 9.8 else (f"**{chg:.2f}%**" if chg <= -9.8 else f"{chg:+.2f}%")
        lines.append(f"| {i} | {name}({code}) | {chg_str} | {amt} | {sector} |")
    lines.append("")
    lines.append("---\n")

    # 板块
    if sector_data:
        lines.append("## 三、盘中板块轮动\n")
        if sector_data.get("top"):
            lines.append("### 上午强势板块（成份股≥5只）\n")
            lines.append("| 板块 | 平均涨幅 | 上涨占比 | 成份股 |")
            lines.append("|------|---------|---------|-------|")
            for s in sector_data["top"]:
                lines.append(f"| {s['sector']} | **{s['avg_change']:+.2f}%** | {s['up_pct']}% | {s['count']} |")
            lines.append("")
        if sector_data.get("worst"):
            lines.append("### 上午弱势板块\n")
            lines.append("| 板块 | 平均涨幅 | 上涨占比 | 成份股 |")
            lines.append("|------|---------|---------|-------|")
            for s in sector_data["worst"]:
                lines.append(f"| {s['sector']} | **{s['avg_change']:+.2f}%** | {s['up_pct']}% | {s['count']} |")
            lines.append("")
        lines.append("---\n")

    # 明星个股
    lines.append("## 四、盘中明星个股\n")
    lines.append("### 上午涨幅榜\n")
    lines.append("| 股票 | 涨幅 | 行业 |")
    lines.append("|------|------|------|")
    for _, r in top_up.iterrows():
        lines.append(f"| {r.get('name','')}({r.get('code','')}) | **{r['change_pct']:+.2f}%** | {r.get('sector','--')} |")
    lines.append("")
    lines.append("### 上午跌幅榜\n")
    lines.append("| 股票 | 跌幅 | 行业 |")
    lines.append("|------|------|------|")
    for _, r in top_down.iterrows():
        lines.append(f"| {r.get('name','')}({r.get('code','')}) | **{r['change_pct']:+.2f}%** | {r.get('sector','--')} |")
    lines.append("")
    lines.append("---\n")

    # 综合评估
    lines.append("## 五、盘中综合评估\n")
    lines.append("```")
    if avg_change > 0.5:
        verdict = "上午偏强"
    elif avg_change > -0.3:
        verdict = "上午震荡"
    elif avg_change > -1:
        verdict = "上午偏弱"
    else:
        verdict = "上午大跌"
    lines.append(f"📋 盘中判断: {verdict}")
    lines.append("")
    lines.append(f"✅ 上涨 {up}只 ({round(up/total*100,1)}%) | 下跌 {down}只 ({round(down/total*100,1)}%)")
    lines.append(f"  涨停 {limit_up}只 | 跌停 {limit_down}只 | 半日成交 {total_amount:.0f}亿")
    lines.append(f"  涨跌比 {ratio} | 平均涨幅 {avg_change}% | 离散度 {dispersion}")
    if sector_data.get("top"):
        lines.append(f"  最强板块: {sector_data['top'][0]['sector']} ({sector_data['top'][0]['avg_change']:+.2f}%)")
    if sector_data.get("worst"):
        lines.append(f"  最弱板块: {sector_data['worst'][0]['sector']} ({sector_data['worst'][0]['avg_change']:+.2f}%)")
    lines.append("")
    lines.append("💡 下午关注:")
    if limit_up > 50:
        lines.append("  - 涨停家数活跃，关注上午强势板块能否延续")
    if limit_down > 15:
        lines.append("  - 跌停家数偏多，注意局部风险")
    if ratio < 0.5:
        lines.append("  - 涨跌比偏低，午后关注是否继续走弱")
    elif ratio > 1.5:
        lines.append("  - 涨跌比偏强，午后有望维持活跃")
    else:
        lines.append("  - 市场分化，等待午后方向选择")
    lines.append("```")
    lines.append("")
    lines.append("---\n")
    lines.append(f"*报告生成时间: {date.today().isoformat()} 自动*\n")
    lines.append(f"*数据来源: 沪深京A股午盘行情CSV*\n")

    return "\n".join(lines)


def save_noon_report(date_str: str = None):
    """生成并保存午盘分析报告"""
    if date_str is None:
        date_str = date.today().isoformat()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    content = generate_noon_report(date_str)
    if content.startswith("⚠️"):
        return False, content

    fpath = REPORT_DIR / f"午盘分析_{date_str}.md"
    fpath.write_text(content, encoding="utf-8")
    print(f"✅ 午盘分析已保存: {fpath} ({len(content)}字)")
    return True, content


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    ok, msg = save_noon_report(d)
    if not ok:
        print(msg)
        sys.exit(1)
