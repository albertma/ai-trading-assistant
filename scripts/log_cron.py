#!/usr/bin/env python3
"""
Cron 任务日志记录工具 — 配合定时任务使用

用法:
  python3 scripts/log_cron.py start 收盘数据          # 记录任务开始
  python3 scripts/log_cron.py end <id> success 完成   # 记录任务结束
  python3 scripts/log_cron.py end <id> failed 错误信息
  python3 scripts/log_cron.py list                    # 查看最近记录

示例:
  python3 scripts/log_cron.py start 收盘数据
  # ... 执行任务 ...
  python3 scripts/log_cron.py end 1 success "拉取完成，共4680只股票"
"""
import sys
import os
import json
import urllib.request
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API_BASE = "http://localhost:8080/api/v1"


def api_get(path: str) -> dict:
    url = f"{API_BASE}{path}"
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read())


def api_post(path: str, params: dict) -> dict:
    url = f"{API_BASE}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, method='POST', headers={'Content-Type': 'application/x-www-form-urlencoded'})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def api_put(path: str, params: dict) -> dict:
    url = f"{API_BASE}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, method='PUT')
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def cmd_start(task_name: str):
    data = api_post("/cron-history/create", {
        "task_name": task_name,
        "status": "running",
        "message": "任务开始"
    })
    print(f"✅ 任务记录已创建: id={data['id']}")


def cmd_end(log_id: str, status: str, message: str):
    data = api_put(f"/cron-history/{log_id}", {
        "status": status,
        "message": message
    })
    print(f"✅ 任务已更新: id={log_id} status={status}")


def cmd_list():
    data = api_get("/cron-history")
    records = data.get("records", [])
    print(f"📋 最近 {len(records)} 条记录:\n")
    for r in records:
        ico = "✅" if r["status"] == "success" else "❌" if r["status"] == "failed" else "🔄"
        print(f"  {ico} #{r['id']:3d} {r['task_name']:10s} | {r['started_at']} | {r['message'][:50]}")
    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "start":
        if len(sys.argv) < 3:
            print("用法: log_cron.py start <任务名>")
            sys.exit(1)
        cmd_start(sys.argv[2])

    elif cmd == "end":
        if len(sys.argv) < 5:
            print("用法: log_cron.py end <id> <success|failed> <消息>")
            sys.exit(1)
        cmd_end(sys.argv[2], sys.argv[3], sys.argv[4])

    elif cmd == "list":
        cmd_list()

    else:
        print(f"未知命令: {cmd}")
        print(__doc__)
        sys.exit(1)
