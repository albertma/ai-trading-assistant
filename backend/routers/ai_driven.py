"""AI驱动投资 — API路由"""
from fastapi import APIRouter, Query, Path
from datetime import date, datetime
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
    index: str = Query('all', description='all=全部(策略驱动), hs300/csi500/star50=指定指数(旧模式)'),
    industry_filter: bool = Query(True, description='是否按行业白名单过滤'),
):
    """策略驱动扫描：使用策略管理系统的策略与作用域进行检测"""
    from backend.services.strategy_scan import run_strategy_scan
    from backend.services.signal_detect.persistence import save_scan_signals
    import uuid

    if index == 'all':
        # ── 策略驱动模式：遍历所有策略 × 作用域 ──
        try:
            session = 'close' if scan_type == 'close' else 'noon'
            result = run_strategy_scan(session=session, max_stocks_per_strategy=200)

            # 策略扫描结果 → 按指数分组写入 ai_scan_records
            all_signals = []
            for sname, sinfo in result.get('signals_by_strategy', {}).items():
                for sig in sinfo.get('signals', []):
                    all_signals.append({
                        'code': sig['stock_code'],
                        'name': sig.get('stock_name', ''),
                        'score': sig.get('confidence', 0),
                        'change': None,
                        'price': sig.get('entry_price', 0),
                        'confidence': sig.get('confidence', 0) >= 60 and '高' or '中',
                        'summary': sig.get('signal_detail', ''),
                        'rationale': f"策略: {sname} | {sig.get('signal_detail','')}",
                        'technical_score': sig.get('confidence', 0),
                        'fundamental_score': 0,
                        'risk_score': 0,
                        'stop_loss': sig.get('stop_loss', 0),
                        'take_profit': sig.get('target_price', 0),
                        'position': '',
                        'technical_signals': [{'type': sname, 'strength': sig.get('confidence', 0)}],
                        'risk_factors': [],
                    })

            # 按指数分组，无信号组也补meta记录
            index_signals = _group_by_index(all_signals)
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
            today_str = date.today().isoformat()

            # 确保所有6个组都有记录
            all_indices = [
                ('hs300', '沪深300', 300),
                ('csi500', '中证500', 500),
                ('star50', '科创50', 50),
            ]
            for icode, iname, itotal in all_indices:
                idata = index_signals.get(icode, {'total': itotal, 'signals': []})
                scan_result = {
                    'success': True,
                    'date': today_str,
                    'scan_type': scan_type,
                    'index': icode,
                    'index_name': iname,
                    'total_scanned': itotal,
                    'signal_count': len(idata['signals']),
                    'generated_at': now_str,
                    'summary': f"策略扫描{len(result.get('signals_by_strategy',{}))}个策略，{result.get('total_stocks_scanned',0)}只股票",
                    'report_path': '',
                }
                save_scan_signals(scan_result, idata['signals'])

            # 构造返回
            top_all = sorted(all_signals, key=lambda x: -x['score'])[:20]
            return {
                'success': True,
                'date': today_str,
                'scan_type': scan_type,
                'index': index,
                'index_name': '策略驱动全市场',
                'total_scanned': result.get('total_stocks_scanned', 0),
                'summary': f"策略驱动扫描: {result.get('total_strategies',0)}个策略, {result.get('total_signals',0)}个信号",
                'signal_count': len(top_all),
                'generated_at': now_str,
                'report_path': '',
                'top_signals': top_all,
                'risk_warnings': [],
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    else:
        # ── 旧模式：单指数扫描（保留兼容） ──
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

            all_signals = [
                {
                    'code': s.code, 'name': s.name, 'score': s.total_score,
                    'change': s.daily_change_pct, 'price': s.current_price,
                    'confidence': s.ai_confidence, 'summary': s.ai_summary,
                    'rationale': s.ai_rationale,
                    'technical_score': s.technical_score,
                    'fundamental_score': s.fundamental_score,
                    'risk_score': s.risk_score,
                    'stop_loss': s.stop_loss, 'take_profit': s.take_profit,
                    'position': s.suggested_position,
                    'technical_signals': [{'type': t.pattern_name, 'strength': t.strength} for t in s.technical_signals],
                    'risk_factors': [{'name': r.risk_name, 'severity': r.severity, 'description': r.description} for r in s.risk_factors],
                }
                for s in report.top_signals
            ]
            save_scan_signals(result, all_signals)
            result['top_signals'] = all_signals[:20]
            result['risk_warnings'] = report.risk_warnings[:10]
            return result
        except Exception as e:
            return {'success': False, 'error': str(e)}


def _group_by_index(signals: list[dict]) -> dict:
    """将信号按指数分组（hs300/csi500/star50）"""
    grouped = {
        'hs300': {'total': 300, 'signals': []},
        'csi500': {'total': 500, 'signals': []},
        'star50': {'total': 50, 'signals': []},
    }

    for sig in signals:
        code = sig.get('code', '')
        # 股票代码前缀规则（粗粒度分组，仅供展示）
        if code.startswith(('688', '689')):
            grouped['star50']['signals'].append(sig)
        elif code.startswith(('600', '601', '603')):
            grouped['hs300']['signals'].append(sig)
        elif code.startswith(('000', '002', '001', '003')):
            grouped['csi500']['signals'].append(sig)
        else:
            grouped['hs300']['signals'].append(sig) if hash(code) % 2 == 0 else grouped['csi500']['signals'].append(sig)

    return {k: v for k, v in grouped.items() if v['signals']}


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
