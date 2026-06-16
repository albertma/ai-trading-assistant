"""评分引擎 — 综合5个维度评分，加权计算最终分 + 决策"""

from datetime import date
from typing import Optional
from backend.services.strategy_evol.db import get_db, ensure_tables
from backend.services.strategy_evol.scan_pool import get_scan_pool
from backend.services.strategy_evol.dimensions.technical import score_technical
from backend.services.strategy_evol.dimensions.fundamental import score_fundamental
from backend.services.strategy_evol.dimensions.narrative import score_narrative
from backend.services.strategy_evol.dimensions.capital_flow import score_capital_flow
from backend.services.strategy_evol.dimensions.sentiment import score_sentiment
import json
import uuid
import concurrent.futures
import threading
import time

# ── 异步扫描状态追踪 ──
_scan_status: dict = {
    "running": False,
    "batch_id": "",
    "progress": {"total": 0, "scored": 0, "failures": 0},
    "started_at": "",
    "finished_at": "",
}
_scan_lock = threading.Lock()


def get_scan_status() -> dict:
    with _scan_lock:
        return dict(_scan_status)


def _set_scan_status(**kwargs):
    with _scan_lock:
        for key, value in kwargs.items():
            if key == "progress" and isinstance(value, dict):
                _scan_status["progress"].update(value)
            else:
                _scan_status[key] = value


# ── 扫描日志持久化 ──


def _log_scan_start(batch_id: str, session: str, total: int):
    """记录扫描启动到 scan_run_log"""
    try:
        conn = get_db()
        conn.execute(
            """INSERT INTO scan_run_log
               (batch_id, session, status, total_stocks, started_at, message)
               VALUES (?,?, 'running', ?, datetime('now','localtime'), ?)""",
            (batch_id, session, total, f"开始扫描{total}只股票"),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def _log_scan_finish(
    batch_id: str, total: int, scored: int, failures: int, duration: float
):
    """记录扫描完成到 scan_run_log"""
    try:
        conn = get_db()
        status = "completed" if scored > 0 else "failed"
        msg = (
            f"扫描完成: {scored}/{total}只成功, {failures}只失败"
            if scored > 0
            else f"全部失败 ({failures}/{total})"
        )
        conn.execute(
            """UPDATE scan_run_log SET
               status=?, scored_stocks=?, failed_stocks=?,
               finished_at=datetime('now','localtime'),
               duration_seconds=?, message=?
               WHERE batch_id=?""",
            (status, scored, failures, duration, msg, batch_id),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_scan_run_logs(limit: int = 30) -> list:
    """获取扫描运行历史"""
    try:
        conn = get_db()
        rows = conn.execute(
            """SELECT * FROM scan_run_log
               ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []

DIMENSION_SCORERS = {
    "technical": score_technical,
    "fundamental": score_fundamental,
    "narrative": score_narrative,
    "capital_flow": score_capital_flow,
    "sentiment": score_sentiment,
}

SCORE_TIMEOUT = 30  # 单只股票超时（秒）


def get_dimension_weights() -> dict:
    """从数据库读取当前维度权重"""
    conn = get_db()
    rows = conn.execute("SELECT dimension, weight FROM dimension_weights").fetchall()
    conn.close()
    return {r["dimension"]: r["weight"] for r in rows}


def score_stock(
    stock_code: str,
    stock_name: str = "",
    session: str = "close",
    score_date: Optional[str] = None,
    dims: Optional[list[str]] = None,
) -> dict:
    """对一只股票跑所有维度评分，返回综合结果

    Args:
        stock_code: 股票代码
        stock_name: 股票名称
        session: close / noon
        score_date: 评分日期，默认今天
        dims: 要跑的维度列表，默认全部

    Returns:
        {
            "stock_code": "...",
            "stock_name": "...",
            "session": "...",
            "date": "...",
            "scores": {"technical": 75, "fundamental": 62, ...},
            "evidences": {"technical": [...], ...},
            "final_score": 68.0,
            "decision": "BUY",
            "decision_label": "建议买入",
        }
    """
    ensure_tables()
    score_date = score_date or str(date.today())
    weights = get_dimension_weights()
    dims = dims or list(DIMENSION_SCORERS.keys())

    scores = {}
    evidences = {}
    for dim in dims:
        scorer = DIMENSION_SCORERS.get(dim)
        if not scorer:
            continue
        try:
            result = scorer(stock_code)
            scores[dim] = result.get("score", 0)
            evidences[dim] = result.get("evidence", [])
        except Exception:
            scores[dim] = 0
            evidences[dim] = []

    # 加权计算最终分
    total_weight = 0
    weighted_sum = 0
    for dim in dims:
        w = weights.get(dim, 1.0)
        total_weight += w
        weighted_sum += scores.get(dim, 0) * w

    final_score = round(weighted_sum / total_weight, 1) if total_weight > 0 else 0

    # 决策
    if final_score >= 80:
        decision = "STRONG_BUY"
        label = "强烈买入"
    elif final_score >= 60:
        decision = "BUY"
        label = "建议买入"
    elif final_score >= 40:
        decision = "HOLD"
        label = "观望"
    else:
        decision = "SKIP"
        label = "不进场"

    return {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "session": session,
        "date": score_date,
        "scores": scores,
        "evidences": evidences,
        "final_score": final_score,
        "decision": decision,
        "decision_label": label,
    }


def run_batch_scan(
    session: str = "close",
    max_stocks: int = 200,
    batch_id: str = "",
) -> dict:
    """全池扫描评分 — 同步执行，会阻塞直到完成

    遍历扫描池所有股票，每只跑5个维度评分，入库 stock_scores。
    """
    ensure_tables()
    batch_id = batch_id or uuid.uuid4().hex[:12]
    score_date = str(date.today())

    _set_scan_status(
        running=True,
        batch_id=batch_id,
        progress={"total": 0, "scored": 0, "failures": 0},
        started_at=str(date.today()),
        finished_at="",
    )

    pool = get_scan_pool(max_per_source=max_stocks)
    if not pool:
        _set_scan_status(running=False, finished_at=str(date.today()))
        _log_scan_start(batch_id, session, 0)
        _log_scan_finish(batch_id, 0, 0, 0, 0)
        return {"batch_id": batch_id, "total": 0, "scored": 0, "date": score_date}

    pool = pool[:max_stocks]
    _set_scan_status(progress={"total": len(pool), "scored": 0, "failures": 0})
    _log_scan_start(batch_id, session, len(pool))
    t0 = time.time()

    results = []
    conn = get_db()
    for idx, (code, name) in enumerate(pool):
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(score_stock, code, name, session, score_date)
                try:
                    result = fut.result(timeout=SCORE_TIMEOUT)
                except concurrent.futures.TimeoutError:
                    _set_scan_status(progress={"failures": _scan_status["progress"]["failures"] + 1})
                    continue

            conn.execute("""INSERT OR REPLACE INTO stock_scores
                (stock_code, stock_name, session, date,
                 tech_score, fund_score, narr_score, flow_score, sent_score,
                 final_score, decision, evidence, batch_id)
                VALUES (?,?,?,?, ?,?,?,?,?, ?,?,?,?)""", (
                code, name, session, score_date,
                result["scores"].get("technical", 0),
                result["scores"].get("fundamental", 0),
                result["scores"].get("narrative", 0),
                result["scores"].get("capital_flow", 0),
                result["scores"].get("sentiment", 0),
                result["final_score"],
                result["decision"],
                json.dumps(result["evidences"], ensure_ascii=False),
                batch_id,
            ))
            results.append(result)
            _set_scan_status(progress={"scored": idx + 1})
        except Exception:
            _set_scan_status(progress={"failures": _scan_status["progress"]["failures"] + 1})
            continue

    conn.commit()
    conn.close()

    decisions = {}
    for r in results:
        d = r["decision"]
        decisions[d] = decisions.get(d, 0) + 1
    results.sort(key=lambda r: -r["final_score"])

    _set_scan_status(running=False, finished_at=str(date.today()))
    duration = time.time() - t0
    _log_scan_finish(batch_id, len(pool), len(results),
                     len(pool) - len(results), round(duration, 1))

    return {
        "batch_id": batch_id,
        "total": len(pool),
        "scored": len(results),
        "date": score_date,
        "session": session,
        "decision_summary": decisions,
        "results": results,
    }


def get_latest_scores(code: str = "", limit: int = 50) -> list:
    """获取最近一次评分结果"""
    conn = get_db()
    if code:
        rows = conn.execute(
            """SELECT * FROM stock_scores
               WHERE stock_code=? ORDER BY date DESC, id DESC LIMIT ?""",
            (code, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT * FROM stock_scores
               ORDER BY date DESC, id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_latest_batch() -> list:
    """获取最新一次批量扫描的所有结果，按 final_score 降序"""
    conn = get_db()
    last = conn.execute(
        "SELECT batch_id FROM stock_scores ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if not last:
        conn.close()
        return []
    bid = last["batch_id"]
    rows = conn.execute(
        """SELECT * FROM stock_scores
           WHERE batch_id=? ORDER BY final_score DESC""",
        (bid,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
