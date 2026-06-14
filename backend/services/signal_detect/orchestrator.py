"""AI驱动投资流程 — 编排器

负责整条流水线的调度：
  1. 获取HS300成分股
  2. 扫描每个成分股的技术面+基本面信号
  3. 评分融合
  4. 产出报告
  5. 可选推送
"""
import sqlite3
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional
import pandas as pd

from .models import StockScore, ScanReport
from .signal_detector import (
    detect_technical_signals,
    detect_fundamental_signals,
    get_kline_records,
)
from .scorer import build_score
from .ai_analyzer import enhance_with_ai

DB = str(Path.home() / 'Jarvis' / 'ai_trading' / 'stock_archive.db')
HS300_DIR = str(Path.home() / 'Jarvis' / 'A股行情信息')
REPORT_DIR = str(Path.home() / 'Jarvis' / 'AI研报')

# 行业白名单：精选系统最佳适配行业（基于中证500回测验证）
INDUSTRY_WHITELIST = frozenset({
    '电机Ⅱ', '自动化设备', '游戏Ⅱ', '通信设备', '消费电子',
    '电子化学品Ⅱ', '专用设备', '半导体', '计算机设备', '电池',
})

INDEX_DISPLAY = {
    'hs300': '沪深300',
    'csi500': '中证500',
    'star50': '科创50',
}


def _get_conn():
    return sqlite3.connect(DB)


def load_hs300_codes() -> list[tuple[str, str]]:
    """返回 (code, name) 列表 — 沪深300成分股"""
    conn = _get_conn()
    cur = conn.cursor()

    # 找最新的HS300文件
    hs300_pattern = Path(HS300_DIR).glob('HS300_*.csv')
    hs300_files = sorted(hs300_pattern, reverse=True)
    if not hs300_files:
        # 没有HS300文件，从stock_info取市值最大的300只
        cur.execute('SELECT code, name FROM stock_info WHERE market IS NOT NULL ORDER BY total_market_cap DESC LIMIT 300')
        return cur.fetchall()

    df = pd.read_csv(str(hs300_files[0]), encoding='utf-16', sep='\t')
    result = []
    names = {}
    cur.execute('SELECT code, name FROM stock_info')
    for row in cur.fetchall():
        names[row[0]] = row[1]

    for _, r in df.iterrows():
        code = str(r['代码']).strip().strip("'\"")
        if code.startswith('BK') or code == 'HS300_': continue
        name = names.get(code, r.get('名称', ''))
        result.append((code, name))

    conn.close()
    return result


def load_csi500_codes() -> list[tuple[str, str]]:
    """返回 (code, name) 列表 — 中证500成分股"""
    conn = _get_conn()
    cur = conn.cursor()
    csv_path = Path(HS300_DIR) / '中证500.csv'
    if not csv_path.exists():
        conn.close()
        return []

    df = pd.read_csv(str(csv_path), encoding='utf-16', sep='\t')
    result = []
    names = {}
    cur.execute('SELECT code, name FROM stock_info')
    for row in cur.fetchall():
        names[row[0]] = row[1]

    for _, r in df.iterrows():
        code = str(r['代码']).strip().strip("'\"")
        if code.startswith('BK') or code == '中证500_': continue
        name = names.get(code, r.get('名称', ''))
        result.append((code, name))

    conn.close()
    return result


def load_star50_codes() -> list[tuple[str, str]]:
    """返回 (code, name) 列表 — 科创50（科创板市值Top 50）"""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT code, name FROM stock_info WHERE market = '科创板' ORDER BY total_market_cap DESC LIMIT 50"
    )
    result = cur.fetchall()
    conn.close()
    return result


_LOADERS = {
    'hs300': load_hs300_codes,
    'csi500': load_csi500_codes,
    'star50': load_star50_codes,
}


def load_noon_data(date_str: str) -> dict:
    """加载指定日期的午盘行情，返回 {code: {涨幅, 价格, ...}}"""
    noon_path = Path(HS300_DIR) / f'沪深京A股{date_str}_noon.csv'
    if not noon_path.exists():
        return {}

    df = pd.read_csv(str(noon_path), sep='\t', encoding='utf-16')
    df['代码'] = df['代码'].astype(str).str.strip().str.strip("'\"")
    result = {}
    for _, r in df.iterrows():
        code = r['代码']
        result[code] = {
            'price': float(r['最新']),
            'change_pct': float(r['涨幅']),
            'volume': float(r['成交量']),
            'volume_ratio': float(r.get('量比', 0) or 0),
            'industry': str(r.get('所属行业', '')),
            'market_cap': float(r.get('总市值', 0) or 0),
        }
    return result


def load_eod_data(date_str: str) -> dict:
    """加载指定日期的收盘行情"""
    # 收盘数据可能还没下载，先用午盘
    return load_noon_data(date_str)


def scan_single_stock(
    code: str, name: str,
    conn: sqlite3.Connection,
    market_data: dict,
    scan_date: str,
    industry_filter: bool = True,
) -> Optional[StockScore]:
    """扫描单只股票

    Args:
        industry_filter: 是否按行业白名单过滤。开启后只扫描精选系统最佳适配行业。
    """
    stock_market = market_data.get(code, {})
    if not stock_market:
        return None

    # 行业白名单过滤
    if industry_filter:
        ind = stock_market.get('industry', '')
        if ind and ind not in INDUSTRY_WHITELIST:
            return None

    # 获取K线
    recs = get_kline_records(code, conn)
    if len(recs) < 30:
        return None

    # 技术面信号
    technical_signals, risk_factors = detect_technical_signals(recs)

    # 基本面信号
    fundamental_signals = detect_fundamental_signals(code, conn)

    # 如果都没有信号，跳过
    if not technical_signals and not fundamental_signals:
        return None

    # 构造评分
    score = build_score(
        code=code, name=name,
        technical_signals=technical_signals,
        fundamental_signals=fundamental_signals,
        news_signals=[],
        risk_factors=risk_factors,
        current_price=stock_market.get('price', 0),
        daily_change_pct=stock_market.get('change_pct', 0),
        volume_ratio=stock_market.get('volume_ratio', 0),
        industry=stock_market.get('industry', ''),
        market_cap=stock_market.get('market_cap', 0),
    )

    return score


async def run_scan(scan_type: str = 'noon', scan_date: Optional[str] = None, index: str = 'hs300',
                   industry_filter: bool = True) -> ScanReport:
    """运行完整扫描

    Args:
        scan_type: 'noon'（午盘）或 'close'（收盘）
        scan_date: 可选指定日期，默认今天。周末自动回退到周五
        index: 'hs300'（沪深300）, 'csi500'（中证500）, 'star50'（科创50）
        industry_filter: 是否按行业白名单过滤。开启后只扫描精选系统最佳适配行业。
    """
    raw_date = scan_date  # 保存原始值，仅用于反馈
    if scan_date is None:
        scan_date = date.today().isoformat()

    # 周末自动回退到最近交易日
    d = date.fromisoformat(scan_date)
    if d.weekday() >= 5:  # 5=周六, 6=周日
        # 回退到周五
        days_back = d.weekday() - 4
        d = d - timedelta(days=days_back)
        scan_date = d.isoformat()
        # 回退到的日期只有收盘数据，午盘数据只有当天11:30才有
        if scan_type == 'noon':
            scan_type = 'close'

    report = ScanReport(date=scan_date, scan_type=scan_type, scanned_index=index)

    # 确保报告目录存在
    Path(REPORT_DIR).mkdir(parents=True, exist_ok=True)

    # 1. 加载成分股（按index选择）
    loader = _LOADERS.get(index)
    if not loader:
        report.market_summary = f'未知指数: {index}'
        return report

    stock_list = loader()
    if not stock_list:
        report.market_summary = f'{INDEX_DISPLAY.get(index, index)} 成分股数据未就绪'
        return report

    report.total_scanned = len(stock_list)

    # 2. 加载行情
    if scan_type == 'close':
        market_data = load_eod_data(scan_date)
    else:
        market_data = load_noon_data(scan_date)

    if not market_data:
        report.market_summary = f'{scan_date} 数据未就绪'
        return report

    # 3. 逐个扫描
    conn = _get_conn()
    all_scores = []

    for code, name in stock_list:
        score = scan_single_stock(code, name, conn, market_data, scan_date,
                                   industry_filter=industry_filter)
        if score:
            all_scores.append(score)

    conn.close()

    # 4. 排序
    all_scores.sort(key=lambda s: s.total_score, reverse=True)

    # 5. 取top信号（精选系统评分≥50）
    report.top_signals = [s for s in all_scores if s.total_score >= 50]

    # 6. 市场摘要
    up_count = sum(1 for s in all_scores if s.daily_change_pct > 0)
    down_count = sum(1 for s in all_scores if s.daily_change_pct < 0)
    avg_change = sum(s.daily_change_pct for s in all_scores) / max(len(all_scores), 1)

    idx_name = INDEX_DISPLAY.get(index, index)
    report.market_summary = (
        f'扫描{len(stock_list)}只{idx_name}成分股，'
        f'发现{len(report.top_signals)}个信号\n'
        f'上涨{up_count}只，下跌{down_count}只，'
        f'平均涨幅{avg_change:+.2f}%'
    )

    # 7. AI深度分析（异步调用）
    import asyncio
    try:
        report.top_signals = await enhance_with_ai(report.top_signals)
    except Exception:
        pass  # AI分析失败不阻塞

    # 8. 风险预警
    for s in all_scores:
        if s.risk_factors:
            for r in s.risk_factors:
                if r.severity >= 60:
                    report.risk_warnings.append({
                        'code': s.code,
                        'name': s.name,
                        'risk': r.risk_name,
                        'severity': r.severity,
                        'desc': r.description,
                    })

    return report


def format_report_markdown(report: ScanReport) -> str:
    """将扫描报告格式化成Markdown"""
    lines = []
    lines.append(f'# 🤖 AI投研日报 · {report.date}')
    idx_name = INDEX_DISPLAY.get(report.scanned_index, report.scanned_index)
    lines.append(f'扫描范围：{idx_name} | 扫描类型：{"收盘" if report.scan_type == "close" else "午盘"}扫描')
    lines.append(f'生成时间：{report.generated_at}')
    lines.append('')

    # 市场概览
    lines.append('## 📊 市场概览')
    lines.append(report.market_summary)
    lines.append('')

    # 精选信号
    lines.append(f'## ⭐ 全天候信号 · {len(report.top_signals)}只')
    lines.append('')
    for s in report.top_signals[:10]:
        lines.append(f'### {s.code} {s.name}')
        lines.append(f'当前价: {s.current_price} | 涨幅: {s.daily_change_pct:+.2f}% | 行业: {s.industry}')
        lines.append(f'**总分: {s.total_score}/100** | 技术面: {s.technical_score} | 基本面: {s.fundamental_score} | 风险分: {s.risk_score}')
        lines.append(f'置信度: {s.ai_confidence}')
        lines.append('')
        lines.append(s.ai_summary)
        lines.append('')
        lines.append(s.ai_rationale)
        lines.append('')
        lines.append('---')
        lines.append('')

    # 风险预警
    if report.risk_warnings:
        lines.append('## ⚠️ 风险预警')
        lines.append('')
        for w in report.risk_warnings[:5]:
            lines.append(f'- **{w["code"]} {w["name"]}**: {w["risk"]}(严重度{w["severity"]:.0f}) — {w["desc"]}')
        lines.append('')

    return '\n'.join(lines)


def save_report(report: ScanReport) -> str:
    """保存报告到文件"""
    md = format_report_markdown(report)
    filepath = Path(REPORT_DIR) / f'AI研报_{report.date}_{report.scan_type}.md'
    filepath.write_text(md, encoding='utf-8')
    return str(filepath)


if __name__ == '__main__':
    # 手动测试
    scan_type = 'noon'
    index = 'hs300'
    import sys
    if len(sys.argv) > 1:
        scan_type = sys.argv[1]
    if len(sys.argv) > 2:
        index = sys.argv[2]

    import asyncio
    report = asyncio.run(run_scan(scan_type, index=index))
    path = save_report(report)
    print(f'📄 报告已保存: {path}')

    for s in report.top_signals[:5]:
        print(f'\n⭐ [{s.total_score}] {s.code} {s.name} ({s.daily_change_pct:+.2f}%)')
        print(f'   {s.ai_confidence}')
        print(f'   {s.ai_summary}')
        if s.technical_signals:
            for sig in s.technical_signals:
                print(f'   📈 {sig.pattern_name}({sig.strength}): {sig.description}')
        if s.risk_factors:
            for r in s.risk_factors:
                print(f'   ⚠️ {r.risk_name}({r.severity}): {r.description}')
