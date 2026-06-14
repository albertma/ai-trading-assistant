#!/usr/bin/env python3
"""AI研报 — 自动扫描Cron入口

用法:
  python3 scripts/ai_scan_cron.py noon    # 午盘扫描
  python3 scripts/ai_scan_cron.py close   # 收盘扫描
"""
import sys, asyncio
from pathlib import Path

# 项目根目录
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


async def main():
    scan_type = sys.argv[1] if len(sys.argv) > 1 else 'noon'

    from backend.services.signal_detect.orchestrator import run_scan, save_report, format_report_markdown

    print(f'🤖 AI扫描启动 ({scan_type})...')
    report = await run_scan(scan_type=scan_type)
    path = save_report(report)

    print(f'📄 报告已保存: {path}')
    print(f'📊 扫描: {report.total_scanned}只')
    print(f'⭐ 信号: {len(report.top_signals)}只')

    for s in report.top_signals[:8]:
        print(f'  [{s.total_score:5.1f}] {s.code} {s.name:<8s} {s.daily_change_pct:+.2f}% {s.industry}')
        for t in s.technical_signals[:2]:
            print(f'       📈 {t.pattern_name}')

    print(f'⚠️ 风险: {len(report.risk_warnings)}条')


if __name__ == '__main__':
    asyncio.run(main())
