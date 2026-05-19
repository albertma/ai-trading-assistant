"""板块轮动分析报告生成器
读取收盘行情CSV，生成独立板块分析报告。
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
    "总市值": "total_mv", "流通市值": "float_mv",
}


def read_csv(date_str: str, suffix: str = "") -> pd.DataFrame | None:
    """读取CSV"""
    fname = MARKET_DATA_DIR / f"沪深京A股{date_str}{('_' + suffix) if suffix else ''}.csv"
    if not fname.exists() or fname.stat().st_size < 1000:
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


def _fmt_chg(v):
    return f"{v:+.2f}%" if pd.notna(v) else "--"


def generate_sector_report(date_str: str, suffix: str = "") -> str:
    """生成板块分析报告
    suffix: ""=收盘数据, "noon"=午盘快照数据
    """
    df = read_csv(date_str, suffix=suffix)
    if df is None:
        return f"⚠️ 未找到 {date_str} 的收盘行情数据"

    dt = pd.Timestamp(date_str)
    weekday_name = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][dt.weekday()]

    valid = df[df["change_pct"].notna()].copy()
    valid["change_pct"] = pd.to_numeric(valid["change_pct"], errors="coerce")
    valid["amount"] = pd.to_numeric(valid["amount"], errors="coerce")
    valid["total_mv"] = pd.to_numeric(valid["total_mv"], errors="coerce")

    total = len(valid)
    up = int((valid["change_pct"] > 0).sum())
    down = int((valid["change_pct"] < 0).sum())

    # 板块统计
    sv = valid[valid["sector"].notna() & (valid["sector"] != "--")].copy()
    sector_stats = sv.groupby("sector").agg(
        avg_change=("change_pct", "mean"),
        up_pct=("change_pct", lambda x: (x > 0).sum() / len(x) * 100),
        up_count=("change_pct", lambda x: (x > 0).sum()),
        down_count=("change_pct", lambda x: (x < 0).sum()),
        count=("change_pct", "count"),
        total_amount=("amount", "sum"),
        limit_up=("change_pct", lambda x: (x >= 9.8).sum()),
        limit_down=("change_pct", lambda x: (x <= -9.8).sum()),
    ).reset_index()

    sector_stats["avg_change"] = sector_stats["avg_change"].round(2)
    sector_stats["up_pct"] = sector_stats["up_pct"].round(1)
    sector_stats["total_amount"] = (sector_stats["total_amount"] / 1e8).round(1)

    # 只分析成份股≥5只的板块
    valid_sectors = sector_stats[sector_stats["count"] >= 5].copy()

    # 按不同维度排序
    top_by_change = valid_sectors.sort_values("avg_change", ascending=False)
    worst_by_change = valid_sectors.sort_values("avg_change", ascending=True)
    top_by_vol = valid_sectors.sort_values("total_amount", ascending=False)
    top_by_up_pct = valid_sectors.sort_values("up_pct", ascending=False)

    lines = []
    prefix = "午盘" if suffix == "noon" else "收盘"
    lines.append(f"# {prefix}板块轮动分析 {date_str}（{weekday_name}）\n")
    period_label = "午盘" if suffix == "noon" else "收盘"
    lines.append(f"> 📅 {date_str} {period_label} | 全市场 {total}只 | 上涨 {up} ({round(up/total*100,1)}%) | 下跌 {down} ({round(down/total*100,1)}%)\n")
    lines.append("---\n")

    # 一、最强/最弱板块
    lines.append("## 一、板块涨跌幅排名\n")

    lines.append("### 🟢 涨幅前20\n")
    lines.append("| 排名 | 板块 | 平均涨幅 | 上涨占比 | 上涨/下跌 | 成份股 | 涨停 | 跌停 |")
    lines.append("|------|------|---------|---------|----------|-------|------|------|")
    for i, (_, r) in enumerate(top_by_change.head(20).iterrows(), 1):
        lines.append(f"| {i} | {r['sector']} | **{r['avg_change']:+.2f}%** | {r['up_pct']}% | {int(r['up_count'])}/{int(r['down_count'])} | {int(r['count'])} | {int(r['limit_up'])} | {int(r['limit_down'])} |")
    lines.append("")

    lines.append("### 🔴 跌幅前20\n")
    lines.append("| 排名 | 板块 | 平均涨幅 | 上涨占比 | 上涨/下跌 | 成份股 | 涨停 | 跌停 |")
    lines.append("|------|------|---------|---------|----------|-------|------|------|")
    for i, (_, r) in enumerate(worst_by_change.head(20).iterrows(), 1):
        lines.append(f"| {i} | {r['sector']} | **{r['avg_change']:+.2f}%** | {r['up_pct']}% | {int(r['up_count'])}/{int(r['down_count'])} | {int(r['count'])} | {int(r['limit_up'])} | {int(r['limit_down'])} |")
    lines.append("")
    lines.append("---\n")

    # 二、成交额排名
    lines.append("## 二、板块资金流向\n")
    lines.append("### 💰 成交额前20\n")
    lines.append("| 排名 | 板块 | 成交额(亿) | 平均涨幅 | 成份股 |")
    lines.append("|------|------|-----------|---------|-------|")
    for i, (_, r) in enumerate(top_by_vol.head(20).iterrows(), 1):
        lines.append(f"| {i} | {r['sector']} | {r['total_amount']} | {r['avg_change']:+.2f}% | {int(r['count'])} |")
    lines.append("")
    lines.append("---\n")

    # 三、板块涨跌分布
    lines.append("## 三、板块涨跌分布\n")

    total_sectors = len(valid_sectors)
    up_sectors = int((valid_sectors["avg_change"] > 0).sum())
    down_sectors = int((valid_sectors["avg_change"] < 0).sum())
    flat_sectors = total_sectors - up_sectors - down_sectors
    hot = int((valid_sectors["avg_change"] >= 3).sum())  # 大涨≥3%
    ice = int((valid_sectors["avg_change"] <= -3).sum())  # 大跌≤-3%

    lines.append(f"| 指标 | 数值 |")
    lines.append(f"|------|------|")
    lines.append(f"| 总板块数（成份股≥5） | {total_sectors} |")
    lines.append(f"| **上涨板块** | **{up_sectors}** ({round(up_sectors/total_sectors*100,1)}%) |")
    lines.append(f"| 下跌板块 | {down_sectors} ({round(down_sectors/total_sectors*100,1)}%) |")
    lines.append(f"| 平盘板块 | {flat_sectors} |")
    lines.append(f"| 大涨板块（≥+3%） | {hot} |")
    lines.append(f"| 大跌板块（≤-3%） | {ice} |")
    if up_sectors > down_sectors * 1.5:
        lines.append(f"| **总体判断** | **🟢 板块普涨** |")
    elif down_sectors > up_sectors * 1.5:
        lines.append(f"| **总体判断** | **🔴 板块普跌** |")
    else:
        lines.append(f"| **总体判断** | **⚖️ 板块分化** |")
    lines.append("")
    lines.append("---\n")

    # 四、涨停集中度
    lines.append("## 四、涨停跌停分布\n")
    limit_up_total = int(valid_sectors["limit_up"].sum())
    limit_down_total = int(valid_sectors["limit_down"].sum())

    lines.append(f"| 指标 | 数值 |")
    lines.append(f"|------|------|")
    lines.append(f"| 全市场涨停 | {limit_up_total}只 |")
    lines.append(f"| 全市场跌停 | {limit_down_total}只 |")
    lines.append(f"| 涨停/跌停比 | {round(limit_up_total/max(limit_down_total,1),2)} |")
    lines.append("")

    # 涨停聚集板块TOP
    top_limit_up = valid_sectors.sort_values("limit_up", ascending=False).head(10)
    if top_limit_up["limit_up"].sum() > 0:
        lines.append("### 涨停集中板块\n")
        lines.append("| 板块 | 涨停 | 跌停 | 成份股 |")
        lines.append("|------|------|------|-------|")
        for _, r in top_limit_up.iterrows():
            if r["limit_up"] > 0:
                lines.append(f"| {r['sector']} | {int(r['limit_up'])} | {int(r['limit_down'])} | {int(r['count'])} |")
        lines.append("")

    lines.append("---\n")

    # 五、板块轮动总结
    lines.append("## 五、轮动总结\n")
    lines.append("```")

    # 找出最突出的特征
    if up_sectors > down_sectors * 2:
        lines.append("📋 板块整体强势，大部分行业上涨")
    elif down_sectors > up_sectors * 2:
        lines.append("📋 板块整体弱势，大部分行业下跌")
    else:
        lines.append("📋 板块分化明显，结构性行情")

    # 最强板块特征
    top3 = top_by_change.head(3)
    lines.append("")
    lines.append(f"🔝 领涨三强:")
    for _, r in top3.iterrows():
        lines.append(f"   • {r['sector']}: {r['avg_change']:+.2f}%, 上涨占比{r['up_pct']}%, {int(r['count'])}只成份股")

    # 最弱板块特征
    worst3 = worst_by_change.head(3)
    lines.append("")
    lines.append(f"🔻 领跌三弱:")
    for _, r in worst3.iterrows():
        lines.append(f"   • {r['sector']}: {r['avg_change']:+.2f}%, 上涨占比{r['up_pct']}%, {int(r['count'])}只成份股")

    # 资金聚集
    top3_vol = top_by_vol.head(3)
    lines.append("")
    lines.append(f"💰 资金聚集前三:")
    for _, r in top3_vol.iterrows():
        lines.append(f"   • {r['sector']}: {r['total_amount']}亿, {r['avg_change']:+.2f}%")

    lines.append("")
    lines.append("💡 策略参考:")
    if ice > 5:
        lines.append(f"  - {ice}个板块大跌(≤-3%)，短线超跌反弹机会关注")
    if hot > 5:
        lines.append(f"  - {hot}个板块大涨(≥+3%)，追高风险较大")
    if up_sectors > down_sectors:
        lines.append("  - 板块涨多跌少，可适当参与主线板块")
    else:
        lines.append("  - 板块跌多涨少，防御为主等待信号")
    lines.append("```")
    lines.append("")
    lines.append("---\n")
    lines.append(f"*报告生成时间: {date.today().isoformat()} 自动*\n")
    lines.append(f"*数据来源: 沪深京A股行情CSV*\n")

    return "\n".join(lines)


def save_sector_report(date_str: str = None, suffix: str = ""):
    """生成并保存板块分析报告
    suffix: ""=收盘数据, "noon"=午盘快照数据
    """
    if date_str is None:
        date_str = date.today().isoformat()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    content = generate_sector_report(date_str, suffix=suffix)
    if content.startswith("⚠️"):
        return False, content

    prefix = "午盘板块分析" if suffix == "noon" else "板块分析"
    fpath = REPORT_DIR / f"{prefix}_{date_str}.md"
    fpath.write_text(content, encoding="utf-8")
    print(f"✅ 板块分析已保存: {fpath} ({len(content)}字)")
    return True, content


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    suffix = sys.argv[2] if len(sys.argv) > 2 else ""
    ok, msg = save_sector_report(d, suffix=suffix)
    if not ok:
        print(msg)
        sys.exit(1)
