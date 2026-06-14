"""
K线工具函数
"""
import numpy as np
import pandas as pd


def daily_to_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """
    将日K线数据转换为周K线数据

    参数:
        df: 包含 date, open, close, high, low, volume 列的DataFrame
            date可以是字符串('YYYY-MM-DD')或datetime类型

    返回:
        周K线DataFrame，列:
          week_label  - 'YYYY-WW'格式 (如 '2026-W23')
          week_end    - 周五日期
          open, high, low, close, volume
    """
    _df = df.copy()

    # 确保date是datetime类型
    if not np.issubdtype(_df['date'].dtype, np.datetime64):
        _df['date'] = pd.to_datetime(_df['date'])

    _df = _df.set_index('date').sort_index()

    # 按周resample（以周五为周K结束日）
    weekly = _df.resample('W-FRI').agg({
        'open':   'first',   # 周一开盘价
        'high':   'max',     # 全周最高价
        'low':    'min',     # 全周最低价
        'close':  'last',    # 周五收盘价
        'volume': 'sum',     # 全周成交量
    }).dropna(subset=['open'])

    # 周标签
    iso = weekly.index.isocalendar()
    weekly['week_label'] = (
        iso['year'].astype(str)
        + '-W'
        + iso['week'].astype(str).str.zfill(2)
    )

    weekly = weekly.reset_index().rename(columns={'date': 'week_end'})

    return weekly[['week_label', 'week_end', 'open', 'high', 'low', 'close', 'volume']]
