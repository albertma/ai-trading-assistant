"""复盘报告 API"""
from fastapi import APIRouter, HTTPException
from datetime import date
import json
import os
from pathlib import Path

from backend.config import REPORT_DIR

# 每日操盘笔记存储路径
NOTES_DIR = Path.home() / "Jarvis" / "daily_notes"

router = APIRouter()


# ===== 固定路由（必须在 /{report_date} 之前） =====

@router.get("/daily")
def daily_report():
    """获取当日复盘报告"""
    today = date.today()
    candidates = sorted(REPORT_DIR.glob("A股复盘_*.md"), reverse=True)
    if not candidates:
        raise HTTPException(404, "暂无复盘报告，请先生成")

    latest = candidates[0]
    report_date = latest.stem.replace("A股复盘_", "")

    content = latest.read_text(encoding="utf-8")
    return {
        "date": report_date,
        "title": f"A股复盘 {report_date}",
        "content": content,
    }


@router.get("/daily/json")
def daily_report_json():
    """获取当日复盘报告（结构化JSON版）"""
    candidates = sorted(REPORT_DIR.glob("A股复盘_*.md"), reverse=True)
    if not candidates:
        raise HTTPException(404, "暂无复盘报告")

    latest = candidates[0]
    content = latest.read_text(encoding="utf-8")

    sections = {}
    current_section = "header"
    for line in content.split("\n"):
        if line.startswith("## "):
            current_section = line.strip("## ").strip()
            sections[current_section] = ""
        elif current_section in sections:
            sections[current_section] += line + "\n"
        else:
            sections[current_section] = line + "\n"

    return {
        "date": latest.stem.replace("A股复盘_", ""),
        "title": f"A股复盘 {latest.stem.replace('A股复盘_', '')}",
        "sections": {k: v.strip() for k, v in sections.items() if v.strip()},
    }


@router.get("/list")
def report_list():
    """获取最近复盘报告列表"""
    reports = sorted(REPORT_DIR.glob("A股复盘_*.md"), reverse=True)
    return {
        "reports": [
            {
                "date": r.stem.replace("A股复盘_", ""),
                "file": r.name,
                "size": r.stat().st_size,
            }
            for r in reports[:30]
        ]
    }


# ===== 动态路由 =====

@router.get("/{report_date}")
def report_by_date(report_date: str):
    """获取指定日期的复盘报告"""
    # 先查 A股复盘
    fpath = REPORT_DIR / f"A股复盘_{report_date}.md"
    if fpath.exists():
        content = fpath.read_text(encoding="utf-8")
        return {"date": report_date, "title": f"A股复盘 {report_date}", "content": content}

    # 再查非A股持仓复盘
    fpath2 = REPORT_DIR / f"非A股持仓复盘_{report_date}.md"
    if fpath2.exists():
        content = fpath2.read_text(encoding="utf-8")
        return {"date": report_date, "title": f"非A股持仓复盘 {report_date}", "content": content}

    raise HTTPException(404, f"未找到 {report_date} 的复盘报告")


# ===== 每日操盘笔记 =====

def _notes_path(d: str = None) -> Path:
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    d = d or date.today().isoformat()
    return NOTES_DIR / f"{d}.json"


@router.get("/notes/{report_date}")
def get_daily_note(report_date: str):
    f = _notes_path(report_date)
    if f.exists():
        return {"date": report_date, "note": json.loads(f.read_text("utf-8"))}
    return {"date": report_date, "note": ""}


@router.put("/notes/{report_date}")
def save_daily_note(report_date: str, data: dict):
    f = _notes_path(report_date)
    note = (data or {}).get("note", "").strip()
    f.write_text(json.dumps(note, ensure_ascii=False), "utf-8")
    return {"status": "ok", "date": report_date}
