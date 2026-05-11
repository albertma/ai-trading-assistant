"""仓位管理模块 — CSV 文件读写"""

import csv
import os

from backend.config import POSITION_FILE
from .constants import POSITION_FIELDS


def read_all() -> list[dict]:
    """读持仓 CSV，返回 dict 列表"""
    if not os.path.exists(POSITION_FILE):
        return []
    with open(POSITION_FILE, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_all(rows: list[dict]):
    """写入持仓 CSV"""
    os.makedirs(os.path.dirname(POSITION_FILE), exist_ok=True)
    with open(POSITION_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=POSITION_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
