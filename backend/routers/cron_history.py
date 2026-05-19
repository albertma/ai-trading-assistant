"""Cron任务历史记录 + 手动触发 API"""
import subprocess
import sys
import os
from datetime import date
from pathlib import Path
from fastapi import APIRouter, Query, HTTPException
from backend.services.db_client import add_cron_log, update_cron_log, delete_cron_log, get_cron_history as _get_history

router = APIRouter()

# ═══════════════════════════════════════════════════════════
# 可执行 cron 任务注册表
# ═══════════════════════════════════════════════════════════

CRON_TASKS = [
    {
        "name": "收盘数据",
        "description": "拉取当日A股收盘行情数据（15:30定时执行）",
        "icon": "📊",
        "schedule": "15:30",
    },
    {
        "name": "午盘快照",
        "description": "拉取盘中A股行情快照（11:30定时执行）",
        "icon": "📸",
        "schedule": "11:30",
    },
    {
        "name": "复盘日报",
        "description": "生成当日复盘报告（含市场总结+持仓回顾+交易铁律）",
        "icon": "📋",
        "schedule": "20:30",
    },
    {
        "name": "午盘分析",
        "description": "生成午盘分析报告（盘中概览+板块轮动）",
        "icon": "🌤️",
        "schedule": "11:40",
    },
    {
        "name": "午盘板块分析",
        "description": "基于午盘快照生成盘中板块轮动分析",
        "icon": "🌤️",
        "schedule": "11:40",
    },
    {
        "name": "收盘板块分析",
        "description": "基于收盘数据生成板块轮动分析（涨跌排名+资金流向+涨停分布）",
        "icon": "📊",
        "schedule": "20:35",
    },
    {
        "name": "思维模型反思",
        "description": "用今日行情自动反思昨日的训练预测",
        "icon": "🧠",
        "schedule": "收盘后手动",
    },
]


def _run_shell(cmd: list[str], timeout: int = 300) -> dict:
    """执行 shell 命令并返回结果"""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {
            "returncode": r.returncode,
            "stdout": r.stdout.strip().split("\n")[-10:],
            "stderr": r.stderr.strip().split("\n")[-5:],
        }
    except subprocess.TimeoutExpired:
        return {"returncode": -1, "stdout": [], "stderr": ["超时（>{}秒）".format(timeout)]}
    except Exception as e:
        return {"returncode": -1, "stdout": [], "stderr": [str(e)]}


# ═══════════════════════════════════════════════════════════
# API: 获取可执行的 cron 任务列表
# ═══════════════════════════════════════════════════════════

@router.get("/cron-jobs")
def list_cron_jobs():
    """返回可手动触发的 cron 任务列表"""
    return {"jobs": CRON_TASKS}


# ═══════════════════════════════════════════════════════════
# API: 手动触发某个 cron 任务
# ═══════════════════════════════════════════════════════════

@router.post("/cron-jobs/{job_name}/run")
def run_cron_job(job_name: str):
    """手动触发执行指定的 cron 任务"""
    job_names = [j["name"] for j in CRON_TASKS]
    if job_name not in job_names:
        raise HTTPException(400, f"未知任务: {job_name}，可选: {', '.join(job_names)}")

    log_id = add_cron_log(job_name, "running", "手动触发执行中...")

    result = {"log_id": log_id, "job_name": job_name, "status": "running", "message": "", "detail": {}}

    try:
        if job_name == "收盘数据":
            fetch_script = str(Path.home() / "Jarvis" / "fetch_a_stock_data.py")
            # 清理今日空壳文件
            today_str = date.today().isoformat()
            today_path = str(Path.home() / "Jarvis" / "A股行情信息" / f"沪深京A股{today_str}.csv")
            if os.path.exists(today_path) and os.path.getsize(today_path) < 1000:
                os.remove(today_path)
            if os.path.exists(fetch_script):
                r = _run_shell([sys.executable, fetch_script, "--date", today_str])
            else:
                r = {"returncode": -1, "stdout": [], "stderr": [f"脚本不存在: {fetch_script}"]}

            if r["returncode"] == 0:
                msg = "拉取完成"
                update_cron_log(log_id, "success", msg)
                result.update({"status": "success", "message": msg})
            else:
                err = "; ".join(r["stderr"][:3])
                update_cron_log(log_id, "failed", f"拉取失败: {err}")
                result.update({"status": "failed", "message": f"失败: {err}"})
            result["detail"] = r

        elif job_name == "午盘快照":
            fetch_script = str(Path.home() / "Jarvis" / "fetch_a_stock_data.py")
            # 清理今日空壳文件（akshare失败留下的空headers），否则fetch脚本读不到股票列表
            today_str = date.today().isoformat()
            today_close = str(Path.home() / "Jarvis" / "A股行情信息" / f"沪深京A股{today_str}.csv")
            today_noon = str(Path.home() / "Jarvis" / "A股行情信息" / f"沪深京A股{today_str}_noon.csv")
            for f in [today_close, today_noon]:
                if os.path.exists(f) and os.path.getsize(f) < 1000:
                    os.remove(f)
                    print(f"  🧹 已清理空壳文件: {os.path.basename(f)}")
            if os.path.exists(fetch_script):
                r = _run_shell([sys.executable, fetch_script, "--date", today_str, "--suffix", "noon"])
            else:
                r = {"returncode": -1, "stdout": [], "stderr": [f"脚本不存在: {fetch_script}"]}

            if r["returncode"] == 0:
                msg = "午盘快照完成"
                update_cron_log(log_id, "success", msg)
                result.update({"status": "success", "message": msg})
            else:
                err = "; ".join(r["stderr"][:3])
                update_cron_log(log_id, "failed", f"快照失败: {err}")
                result.update({"status": "failed", "message": f"失败: {err}"})
            result["detail"] = r

        elif job_name == "复盘日报":
            # 实际生成复盘报告
            from backend.services.generate_daily_report import save_report
            from backend.config import REPORT_DIR
            today_str = date.today().isoformat()
            ok, msg_or_content = save_report(today_str)
            if ok:
                lines = msg_or_content.strip().split("\n")
                preview = lines[0][:60] if lines else ""
                msg = f"✅ 复盘报告已生成（{len(msg_or_content)}字）"
                update_cron_log(log_id, "success", msg)
                result.update({"status": "success", "message": msg, "preview": preview})
            else:
                # 报告生成失败
                msg = msg_or_content
                candidates = sorted(REPORT_DIR.glob("A股复盘_*.md"), reverse=True)
                if candidates:
                    latest = candidates[0]
                    latest_date = latest.stem.replace("A股复盘_", "")
                    msg += f" | 最新报告为{latest_date}"
                update_cron_log(log_id, "failed", msg)
                result.update({"status": "failed", "message": msg})

        elif job_name == "午盘分析":
            # 生成午盘分析报告
            from backend.services.generate_noon_report import save_noon_report
            from backend.config import REPORT_DIR
            today_str = date.today().isoformat()
            ok, msg_or_content = save_noon_report(today_str)
            if ok:
                lines = msg_or_content.strip().split("\n")
                preview = lines[0][:60] if lines else ""
                msg = f"✅ 午盘分析已生成（{len(msg_or_content)}字）"
                update_cron_log(log_id, "success", msg)
                result.update({"status": "success", "message": msg, "preview": preview})
            else:
                msg = msg_or_content
                candidates = sorted(REPORT_DIR.glob("午盘分析_*.md"), reverse=True)
                if candidates:
                    latest = candidates[0]
                    latest_date = latest.stem.replace("午盘分析_", "")
                    msg += f" | 最新分析为{latest_date}"
                update_cron_log(log_id, "failed", msg)
                result.update({"status": "failed", "message": msg})

        elif job_name == "收盘板块分析":
            # 先刷新数据库行业数据（收盘才刷新）
            from backend.routers.mental_models import refresh_sector_dispersion
            from backend.services.generate_sector_report import save_sector_report
            from backend.config import REPORT_DIR
            today_str = date.today().isoformat()
            try:
                refresh_result = refresh_sector_dispersion(today_str)
                refresh_msg = f"已刷新{refresh_result.get('sectors',0)}个板块 → "
            except Exception as e:
                refresh_msg = f"刷新失败({e}) → "
            # 生成收盘板块轮动分析
            ok, msg_or_content = save_sector_report(today_str, suffix="")
            if ok:
                lines = msg_or_content.strip().split("\n")
                preview = lines[0][:60] if lines else ""
                msg = refresh_msg + f"✅ 收盘板块分析已生成（{len(msg_or_content)}字）"
                update_cron_log(log_id, "success", msg)
                result.update({"status": "success", "message": msg, "preview": preview})
            else:
                msg = msg_or_content
                candidates = sorted(REPORT_DIR.glob("板块分析_*.md"), reverse=True)
                if candidates:
                    latest = candidates[0]
                    latest_date = latest.stem.replace("板块分析_", "")
                    msg += f" | 最新分析为{latest_date}"
                update_cron_log(log_id, "failed", msg)
                result.update({"status": "failed", "message": msg})

        elif job_name == "午盘板块分析":
            # 基于午盘快照生成盘中板块轮动分析（不刷新数据库）
            from backend.services.generate_sector_report import save_sector_report
            from backend.config import REPORT_DIR
            today_str = date.today().isoformat()
            ok, msg_or_content = save_sector_report(today_str, suffix="noon")
            if ok:
                lines = msg_or_content.strip().split("\n")
                preview = lines[0][:60] if lines else ""
                msg = f"✅ 午盘板块分析已生成（{len(msg_or_content)}字）"
                update_cron_log(log_id, "success", msg)
                result.update({"status": "success", "message": msg, "preview": preview})
            else:
                msg = msg_or_content
                candidates = sorted(REPORT_DIR.glob("午盘板块分析_*.md"), reverse=True)
                if candidates:
                    latest = candidates[0]
                    latest_date = latest.stem.replace("午盘板块分析_", "")
                    msg += f" | 最新分析为{latest_date}"
                update_cron_log(log_id, "failed", msg)
                result.update({"status": "failed", "message": msg})

        elif job_name == "思维模型反思":
            from backend.routers.mental_models import auto_reflect_all
            ref_result = auto_reflect_all()
            count = ref_result.get("reflected", 0)
            if count > 0:
                msg = f"已自动反思 {count} 条"
                update_cron_log(log_id, "success", msg)
                result.update({"status": "success", "message": msg})
            else:
                msg = ref_result.get("message", "无不需反思的记录")
                update_cron_log(log_id, "success", msg)
                result.update({"status": "success", "message": msg})

    except Exception as e:
        update_cron_log(log_id, "failed", str(e))
        result.update({"status": "failed", "message": str(e)})

    return result


# ═══════════════════════════════════════════════════════════
# 原有 Cron 历史记录 API
# ═══════════════════════════════════════════════════════════

@router.get("/cron-history")
def list_cron_history(
    limit: int = Query(50, description="返回条数"),
    task_name: str = Query(None, description="按任务名筛选"),
):
    records = _get_history(limit=limit, task_name=task_name)
    return {"records": records, "total": len(records)}


@router.get("/cron-history/tasks")
def list_cron_tasks():
    from backend.services.database.stock_db import get_db
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT task_name FROM cron_history ORDER BY task_name").fetchall()
    conn.close()
    return {"tasks": [r["task_name"] for r in rows]}


@router.post("/cron-history/create")
def create_cron_log(
    task_name: str = Query(..., description="任务名称"),
    status: str = Query("running", description="状态: running/success/failed"),
    message: str = Query("", description="日志消息"),
):
    log_id = add_cron_log(task_name, status, message)
    return {"id": log_id, "status": "created"}


@router.put("/cron-history/{log_id}")
def edit_cron_log(
    log_id: int,
    status: str = Query(..., description="状态: running/success/failed"),
    message: str = Query("", description="日志消息"),
):
    update_cron_log(log_id, status, message)
    return {"id": log_id, "status": "updated"}


@router.delete("/cron-history/{log_id}")
def remove_cron_log(log_id: int):
    """删除cron任务记录"""
    deleted = delete_cron_log(log_id)
    if not deleted:
        raise HTTPException(404, f"记录 {log_id} 不存在")
    return {"id": log_id, "status": "deleted"}


@router.get("/cron-history/{log_id}")
def get_cron_log(log_id: int):
    from backend.services.database.stock_db import get_db
    conn = get_db()
    row = conn.execute("SELECT * FROM cron_history WHERE id = ?", (log_id,)).fetchone()
    conn.close()
    if not row:
        return {"error": "not found"}
    return dict(row)
