"""A股复盘报告生成器
读取当日行情CSV + akshare指数数据，生成 markdown 复盘报告。
"""
import sys
import os
from datetime import date, timedelta
from pathlib import Path
import pandas as pd

# 项目路径
PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_DIR))

# CSV目录
HOME = Path.home()
MARKET_DATA_DIR = HOME / "Jarvis" / "A股行情信息"
REPORT_DIR = HOME / "Jarvis" / "复盘"

# CSV列名映射（实际列名）
COL_MAP = {
    "代码": "code", "名称": "name", "最新": "close", "涨幅": "change_pct",
    "涨跌": "change", "成交量": "volume", "成交额": "amount",
    "换手": "turnover", "市盈率": "pe", "所属行业": "sector",
    "最高": "high", "最低": "low", "开盘": "open", "昨收": "pre_close",
    "振幅": "amplitude", "量比": "volume_ratio", "均价": "avg_price",
    "市净率": "pb", "总市值": "total_mv", "流通市值": "float_mv",
    "总股本": "total_shares", "流通股本": "float_shares",
    "3日涨幅": "chg_3d", "6日涨幅": "chg_6d", "3日换手": "turnover_3d", "6日换手": "turnover_6d",
}


def read_csv(date_str: str) -> pd.DataFrame | None:
    """读取指定日期的行情CSV"""
    fname = MARKET_DATA_DIR / f"沪深京A股{date_str}.csv"
    if not fname.exists():
        return None
    try:
        df = pd.read_csv(fname, encoding="utf-16", sep="\t", engine="python")
        if "代码" in df.columns:
            df["代码"] = df["代码"].astype(str).str.strip("'\"")
        # 统一列名
        rename = {k: v for k, v in COL_MAP.items() if k in df.columns}
        df = df.rename(columns=rename)
        return df
    except Exception as e:
        print(f"CSV读取失败: {e}", file=sys.stderr)
        return None


def get_index_data(date_str: str) -> dict:
    """获取沪深300/中证500数据"""
    try:
        import akshare as ak
        hs300 = ak.stock_zh_index_daily(symbol="sh000300")
        zz500 = ak.stock_zh_index_daily(symbol="sh000905")
        hs300["date"] = hs300["date"].astype(str).str[:10]
        zz500["date"] = zz500["date"].astype(str).str[:10]

        hs_row = hs300[hs300["date"] == date_str]
        zz_row = zz500[zz500["date"] == date_str]

        result = {}
        if not hs_row.empty:
            result["hs300"] = round(float(hs_row.iloc[0]["close"]), 2)
            hs_yest = hs300[hs300["date"] < date_str].iloc[-1]["close"] if len(hs300[hs300["date"] < date_str]) > 0 else None
            if hs_yest:
                result["hs300_chg"] = round((result["hs300"] - float(hs_yest)) / float(hs_yest) * 100, 2)
        if not zz_row.empty:
            result["zz500"] = round(float(zz_row.iloc[0]["close"]), 2)
            zz_yest = zz500[zz500["date"] < date_str].iloc[-1]["close"] if len(zz500[zz500["date"] < date_str]) > 0 else None
            if zz_yest:
                result["zz500_chg"] = round((result["zz500"] - float(zz_yest)) / float(zz_yest) * 100, 2)
        if result.get("hs300") and result.get("zz500"):
            result["ratio"] = round(result["hs300"] / result["zz500"], 3)
        return result
    except Exception as e:
        print(f"指数获取失败: {e}", file=sys.stderr)
        return {}


def get_sector_stats(df: pd.DataFrame) -> dict:
    """计算板块统计数据"""
    if "sector" not in df.columns:
        return {"sectors": [], "worst_sectors": [], "top_volume_sectors": [], "hot_sectors": []}

    valid = df[df["change_pct"].notna() & df["sector"].notna() & (df["sector"] != "--")].copy()
    if valid.empty:
        return {"sectors": [], "worst_sectors": [], "top_volume_sectors": [], "hot_sectors": []}

    valid["change_pct"] = pd.to_numeric(valid["change_pct"], errors="coerce")
    valid["amount"] = pd.to_numeric(valid["amount"], errors="coerce")

    sector_stats = valid.groupby("sector").agg(
        avg_change=("change_pct", "mean"),
        up_pct=("change_pct", lambda x: (x > 0).sum() / len(x) * 100),
        count=("change_pct", "count"),
        total_amount=("amount", "sum"),
    ).reset_index()

    sector_stats["avg_change"] = sector_stats["avg_change"].round(2)
    sector_stats["up_pct"] = sector_stats["up_pct"].round(1)

    # 过滤成份股≥5只
    valid_sectors = sector_stats[sector_stats["count"] >= 5].copy()

    top = valid_sectors.sort_values("avg_change", ascending=False).head(10)
    worst = valid_sectors.sort_values("avg_change", ascending=True).head(10)
    by_vol = valid_sectors.sort_values("total_amount", ascending=False).head(10)

    return {
        "sectors": top.to_dict("records"),
        "worst_sectors": worst.to_dict("records"),
        "top_volume_sectors": by_vol.to_dict("records"),
    }


def generate_report(date_str: str) -> str:
    """生成复盘报告，返回报告内容"""
    df = read_csv(date_str)
    if df is None:
        return f"⚠️ 未找到 {date_str} 的行情数据（文件不存在）"
    if df.empty:
        return f"⚠️ {date_str} 的行情文件为空，请先下载数据后重试"

    # 解析日期
    dt = pd.Timestamp(date_str)
    weekday_name = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][dt.weekday()]

    # 基础统计
    valid = df[df["change_pct"].notna()].copy()
    valid["change_pct"] = pd.to_numeric(valid["change_pct"], errors="coerce")
    valid["amount"] = pd.to_numeric(valid["amount"], errors="coerce")

    total = len(df)
    up = int((valid["change_pct"] > 0).sum())
    down = int((valid["change_pct"] < 0).sum())
    flat = total - up - down
    limit_up = int((valid["change_pct"] >= 9.8).sum())
    limit_down = int((valid["change_pct"] <= -9.8).sum())
    avg_change = round(float(valid["change_pct"].mean()), 2)
    dispersion = round(float(valid["change_pct"].std()), 2)
    total_amount = round(float(valid["amount"].sum()) / 1e8, 0)

    # 涨跌比
    ratio = round(up / down, 2) if down > 0 else up

    # 指数数据
    idx = get_index_data(date_str)

    # 板块数据
    sector_data = get_sector_stats(valid)

    # 成交额TOP10
    top_volume = valid.dropna(subset=["amount"]).sort_values("amount", ascending=False).head(10)

    # 涨幅/跌幅股票
    top_gainers = valid.sort_values("change_pct", ascending=False).head(5)
    top_losers = valid.sort_values("change_pct", ascending=True).head(5)

    # 开始生成markdown
    lines = []
    lines.append(f"# A股复盘报告 {date_str}（{weekday_name}）\n")
    lines.append(f"> 📅 {date_str} 收盘 | 总股票 {total}只 | 上涨 {up} ({round(up/total*100,1)}%) | 下跌 {down} ({round(down/total*100,1)}%) | 平盘 {flat} ({round(flat/total*100,1)}%)\n")
    lines.append("---\n")
    lines.append("## 一、市场总览\n")
    lines.append("### 指数表现\n")

    if idx:
        lines.append("| 指数 | 收盘价 | 涨跌幅 |")
        lines.append("|------|--------|--------|")
        lines.append(f"| 📊 沪深300 | {idx.get('hs300', '--'):,} | **{idx.get('hs300_chg', '--')}%** |")
        lines.append(f"| 📊 中证500 | {idx.get('zz500', '--'):,} | **{idx.get('zz500_chg', '--')}%** |")
        if "ratio" in idx:
            lines.append(f"| 沪深300/中证500比值 | {idx['ratio']} | — |")
    else:
        lines.append("> 指数数据获取失败\n")
    lines.append("")

    lines.append("### 全市场统计\n")
    lines.append("| 指标 | 数值 |")
    lines.append("|------|------|")
    lines.append(f"| 上涨家数 | {up} ({round(up/total*100,1)}%) |")
    lines.append(f"| 下跌家数 | {down} ({round(down/total*100,1)}%) |")
    lines.append(f"| 平盘家数 | {flat} ({round(flat/total*100,1)}%) |")
    lines.append(f"| **涨跌比** | **{ratio}** |")
    lines.append(f"| **平均涨幅** | **{avg_change}%** |")
    lines.append(f"| **涨停** | **{limit_up}只** |")
    lines.append(f"| **跌停** | **{limit_down}只** |")
    disp_label = "高位波动" if dispersion > 3 else ("中位波动" if dispersion > 2 else "低位波动")
    lines.append(f"| **市场离散度** | **{dispersion}**（{disp_label}） |")
    lines.append(f"| **总成交额** | **{total_amount:.0f}亿** |")
    lines.append("")
    lines.append("---\n")

    # 成交额排名
    lines.append("## 二、成交额排名（Top 10）\n")
    lines.append("| 排名 | 股票 | 涨幅 | 成交额(亿) | 所属行业 |")
    lines.append("|------|------|------|-----------|---------|")
    for i, (_, r) in enumerate(top_volume.iterrows(), 1):
        name = r.get("name", "--")
        code = str(r.get("code", ""))
        chg = r.get("change_pct", 0)
        amt = round(r.get("amount", 0) / 1e8, 1) if r.get("amount") else 0
        sector = r.get("sector", "--")
        # 标注涨停/跌停
        chg_str = f"**+{chg:.2f}%**" if chg >= 9.8 else (f"**{chg:.2f}%**" if chg <= -9.8 else f"{chg:+.2f}%")
        lines.append(f"| {i} | {name}({code}) | {chg_str} | {amt} | {sector} |")
    lines.append("")
    lines.append("---\n")

    # 板块轮动
    lines.append("## 三、板块轮动分析\n")

    if sector_data["sectors"]:
        lines.append("### 今日最强板块（Top 10，成份股≥5只）\n")
        lines.append("| 板块 | 平均涨幅 | 上涨占比 | 成份股 |")
        lines.append("|------|---------|---------|-------|")
        for s in sector_data["sectors"]:
            lines.append(f"| {s['sector']} | **{s['avg_change']:+.2f}%** | {s['up_pct']}% | {s['count']} |")
        lines.append("")

    if sector_data["worst_sectors"]:
        lines.append("### 今日最弱板块（Bottom 10）\n")
        lines.append("| 板块 | 平均涨幅 | 上涨占比 | 成份股 |")
        lines.append("|------|---------|---------|-------|")
        for s in sector_data["worst_sectors"]:
            lines.append(f"| {s['sector']} | **{s['avg_change']:+.2f}%** | {s['up_pct']}% | {s['count']} |")
        lines.append("")
    lines.append("---\n")

    # 涨跌停统计
    lines.append("## 四、涨跌停统计\n")
    lines.append("| 指标 | 数值 |")
    lines.append("|------|------|")
    lines.append(f"| 涨停（≥9.8%） | **{limit_up}只** |")
    lines.append(f"| 跌停（≤-9.8%） | **{limit_down}只** |")
    lines.append(f"| 涨停/跌停比 | **{round(limit_up/max(limit_down,1), 2)}** |")
    # 新股
    new_stocks = valid[valid["change_pct"] > 50]
    if not new_stocks.empty:
        for _, r in new_stocks.head(3).iterrows():
            lines.append(f"| 新股 | {r.get('name','')}({r.get('code','')}) 涨{r.get('change_pct',0):+.2f}% |")
    lines.append("")
    lines.append("---\n")

    # 明星个股
    lines.append("## 五、明星个股\n")
    lines.append("### 涨幅榜（剔除新股）\n")
    regular = valid[(valid["change_pct"] <= 50)].sort_values("change_pct", ascending=False).head(5)
    lines.append("| 股票 | 涨幅 | 行业 |")
    lines.append("|------|------|------|")
    for _, r in regular.iterrows():
        lines.append(f"| {r.get('name','')}({r.get('code','')}) | **+{r['change_pct']:.2f}%** | {r.get('sector','--')} |")
    lines.append("")
    lines.append("### 跌幅榜\n")
    lines.append("| 股票 | 跌幅 | 行业 |")
    lines.append("|------|------|------|")
    for _, r in top_losers.head(5).iterrows():
        lines.append(f"| {r.get('name','')}({r.get('code','')}) | **{r['change_pct']:.2f}%** | {r.get('sector','--')} |")
    lines.append("")
    lines.append("---\n")

    # 市场综合评估
    lines.append("## 六、市场综合评估\n")
    lines.append("```")
    # 简单判断
    if avg_change > 1:
        verdict = "强势上涨"
    elif avg_change > 0:
        verdict = "震荡偏强"
    elif avg_change > -0.5:
        verdict = "弱势震荡"
    elif avg_change > -1:
        verdict = "普遍下跌"
    else:
        verdict = "大幅调整"
    lines.append(f"📋 整体判断: {verdict}")
    lines.append("")
    # 乐观信号
    lines.append("✅ 乐观信号:")
    if up > down * 1.5:
        lines.append("  - 上涨家数远超下跌，市场整体偏强")
    if limit_up > limit_down * 2:
        lines.append(f"  - 涨停{limit_up}只 > 跌停{limit_down}只，赚钱效应明显")
    if total_amount > 15000:
        lines.append(f"  - 成交额{total_amount:.0f}亿维持高活跃度")
    if not sector_data.get("sectors"):
        pass
    else:
        top_sector = sector_data["sectors"][0]
        if top_sector["avg_change"] > 3:
            lines.append(f"  - {top_sector['sector']}板块强势领涨（+{top_sector['avg_change']:.2f}%）")
    lines.append("")
    lines.append("⚠️ 风险提示:")
    if down > up:
        lines.append(f"  - 仅{round(up/total*100,1)}%个股上涨，市场广度较差")
    if limit_down > 10:
        lines.append(f"  - 跌停{limit_down}只，局部风险较大")
    if idx.get("hs300_chg", 0) < -1 and idx.get("zz500_chg", 0) < -1:
        lines.append("  - 沪深300与中证500双杀，大小盘齐跌")
    lines.append("")
    lines.append("💡 操作建议:")
    if verdict in ("大幅调整", "普遍下跌"):
        lines.append("  - 防御为主，不宜盲目抄底，等待企稳信号")
    elif verdict == "弱势震荡":
        lines.append("  - 控制仓位，关注结构性机会（领涨板块）")
    elif verdict == "震荡偏强":
        lines.append("  - 可适度参与，注意板块轮动节奏")
    else:
        lines.append("  - 顺势而为，注意高位板块的回调风险")
    lines.append("```")
    lines.append("")
    lines.append("---\n")
    lines.append(f"*报告生成时间: {date.today().isoformat()} 自动*\n")
    lines.append(f"*数据来源: 沪深京A股行情CSV + 东方财富指数数据*\n")

    return "\n".join(lines)


def save_report(date_str: str = None):
    """生成并保存复盘报告"""
    if date_str is None:
        date_str = date.today().isoformat()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    content = generate_report(date_str)
    if content.startswith("⚠️"):
        return False, content

    fpath = REPORT_DIR / f"A股复盘_{date_str}.md"
    fpath.write_text(content, encoding="utf-8")
    print(f"✅ 复盘报告已保存: {fpath} ({len(content)}字)")
    return True, content


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    ok, msg = save_report(d)
    if not ok:
        print(msg)
        sys.exit(1)
