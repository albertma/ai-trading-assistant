"""AI驱动投资 — API路由"""
from fastapi import APIRouter, Query, Path
from datetime import date
from pathlib import Path
import asyncio

router = APIRouter(prefix='/api/v1/ai-driven', tags=['ai-driven'])

from backend.services.signal_detect.orchestrator import INDEX_DISPLAY
from backend.services.signal_detect.persistence import (
    save_scan_signals,
    get_latest_scan,
    get_scan_history,
    get_signals_by_date,
    get_available_dates,
    get_today_scan_summary,
)

REPORT_DIR = str(Path.home() / 'Jarvis' / 'AI研报')


@router.post('/scan')
async def trigger_scan(
    scan_type: str = Query('noon', description='noon=午盘, close=收盘'),
    index: str = Query('hs300', description='hs300=沪深300, csi500=中证500, star50=科创50'),
    industry_filter: bool = Query(True, description='是否按行业白名单过滤（仅10个最佳适配行业）'),
):
    """手动触发扫描，信号股票逐只持久化到DB"""
    try:
        from backend.services.signal_detect.orchestrator import run_scan, save_report
        today = date.today().isoformat()
        report = await run_scan(scan_type=scan_type, scan_date=today, index=index,
                                industry_filter=industry_filter)
        path = save_report(report)

        result = {
            'success': True,
            'date': report.date,
            'scan_type': report.scan_type,
            'index': report.scanned_index,
            'index_name': INDEX_DISPLAY.get(report.scanned_index, report.scanned_index),
            'total_scanned': report.total_scanned,
            'summary': report.market_summary,
            'signal_count': len(report.top_signals),
            'generated_at': report.generated_at,
            'report_path': path,
        }

        # 全量信号存入DB
        all_signals = [
            {
                'code': s.code,
                'name': s.name,
                'score': s.total_score,
                'change': s.daily_change_pct,
                'price': s.current_price,
                'confidence': s.ai_confidence,
                'summary': s.ai_summary,
                'rationale': s.ai_rationale,
                'technical_score': s.technical_score,
                'fundamental_score': s.fundamental_score,
                'risk_score': s.risk_score,
                'stop_loss': s.stop_loss,
                'take_profit': s.take_profit,
                'position': s.suggested_position,
                'technical_signals': [{'type': t.pattern_name, 'strength': t.strength} for t in s.technical_signals],
                'risk_factors': [{'name': r.risk_name, 'severity': r.severity, 'description': r.description} for r in s.risk_factors],
            }
            for s in report.top_signals
        ]
        save_scan_signals(result, all_signals)

        # 返回只取top 20
        result['top_signals'] = all_signals[:20]
        result['risk_warnings'] = report.risk_warnings[:10]

        return result
    except Exception as e:
        return {'success': False, 'error': str(e)}


@router.get('/scan/latest')
async def get_latest_scan_result(
    index: str = Query('hs300', description='hs300=沪深300, csi500=中证500, star50=科创50'),
    scan_type: str = Query('noon', description='noon=午盘, close=收盘'),
):
    """从DB获取最新扫描结果（不触发扫描）"""
    try:
        result = get_latest_scan(index_code=index, scan_type=scan_type)
        if not result:
            return {'success': False, 'error': '暂无扫描记录，请先手动触发扫描'}
        return result
    except Exception as e:
        return {'success': False, 'error': str(e)}


@router.get('/scan/history')
async def list_scan_history(limit: int = Query(30, description='返回条数')):
    """列出历史扫描批次"""
    try:
        records = get_scan_history(limit=limit)
        return {'success': True, 'records': records}
    except Exception as e:
        return {'success': False, 'error': str(e)}


@router.get('/scan/by-date')
async def get_scan_by_date_result(
    date_str: str = Query(..., description='日期 YYYY-MM-DD'),
    index: str = Query('hs300', description='hs300=沪深300, csi500=中证500, star50=科创50'),
    scan_type: str = Query('noon', description='noon=午盘, close=收盘'),
):
    """按日期获取指定扫描"""
    try:
        result = get_signals_by_date(index_code=index, scan_date=date_str, scan_type=scan_type)
        if not result:
            return {'success': False, 'error': f'{date_str} {index} {scan_type} 无记录'}
        return result
    except Exception as e:
        return {'success': False, 'error': str(e)}


@router.get('/scan/today-summary')
async def get_today_summary():
    """获取今日所有指数的扫描汇总"""
    try:
        result = get_today_scan_summary()
        return {'success': True, 'records': result}
    except Exception as e:
        return {'success': False, 'error': str(e)}


@router.get('/scan/dates')
async def list_available_dates(limit: int = Query(60, description='返回多少天')):
    """列出有数据的日期"""
    try:
        dates = get_available_dates(limit=limit)
        return {'success': True, 'dates': dates}
    except Exception as e:
        return {'success': False, 'error': str(e)}
