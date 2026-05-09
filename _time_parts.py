"""Pinpoint the slow part in fundamental_analysis"""
import sys, time
sys.path.insert(0, '.')
from backend.stock_db import get_financial_reports
from backend.routers.fundamental import _get_industry_data, _analyze_industry_cycle
import sqlite3

code = '603799'

# 1. SQLite - financial reports
t0 = time.time()
cached = get_financial_reports(code, 8)
t1 = time.time()
print(f"[1] get_financial_reports: {t1-t0:.3f}s -> {len(cached)} records")

# 2. SQLite - sector
t2 = time.time()
sector = None
conn = sqlite3.connect('/Users/albertma/Jarvis/ai_trading/stock_archive.db')
row = conn.execute("SELECT industry FROM stock_info WHERE code=?", (code,)).fetchone()
conn.close()
if row and row[0]:
    sector = row[0]
t3 = time.time()
print(f"[2] sector lookup: {t3-t2:.3f}s -> {sector}")

# 3. Industry data
t4 = time.time()
ind = _get_industry_data(sector)
t5 = time.time()
print(f"[3] _get_industry_data: {t5-t4:.3f}s -> {'yes' if ind else 'no'}")

# 4. Cycle analysis
t6 = time.time()
cycle = _analyze_industry_cycle(sector, ind)
t7 = time.time()
print(f"[4] _analyze_industry_cycle: {t7-t6:.3f}s -> {'yes' if cycle else 'no'}")
