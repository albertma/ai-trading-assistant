"""
每日A股行情自动下载
用法: python3 download_daily.py [YYYY-MM-DD]
不传日期则默认今天

数据源: akshare (stock_zh_a_spot_em)
输出: ~/Jarvis/A股行情信息/沪深京A股YYYY-MM-DD.csv
"""
import sys
import os
from datetime import date, timedelta
from pathlib import Path

HOME = Path.home()
OUTPUT_DIR = HOME / "Jarvis" / "A股行情信息"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def download(date_str: str = None) -> str | None:
    """下载指定日期的A股行情，保存为CSV"""
    if date_str is None:
        date_str = date.today().isoformat()

    output_path = OUTPUT_DIR / f"沪深京A股{date_str}.csv"
    if output_path.exists():
        print(f"⏭️  {date_str} 已存在，跳过")
        return None

    print(f"🔄 正在获取 {date_str} A股行情...")
    try:
        import akshare as ak
        import pandas as pd

        # 获取A股实时行情（含全部股票）
        df = ak.stock_zh_a_spot_em()
        if df is None or df.empty:
            print(f"❌ {date_str} 获取失败：数据为空（可能非交易日）")
            return None

        # 标准化列名为东方财富导出格式
        # akshare返回的列名与东方财富导出的略有不同，统一映射
        col_map = {
            "序号": "序",
            "代码": "代码",
            "名称": "名称",
            "最新价": "最新",
            "涨跌幅": "涨幅",
            "涨跌额": "涨跌",
            "成交量": "成交量",
            "成交额": "成交额",
            "振幅": "振幅",
            "最高": "最高",
            "最低": "最低",
            "今开": "开盘",
            "昨收": "昨收",
            "量比": "量比",
            "换手率": "换手",
            "市盈率-动态": "市盈率",
            "市净率": "市净率",
            "总市值": "总市值",
            "流通市值": "流通市值",
            "涨速": "涨速",
            "60日涨跌幅": "6日涨幅",
            "5分钟涨跌": "涨速",
            "代码代码": "代码",
        }
        # 只保留东方财富导出格式中有的列
        target_cols = [
            "序", "代码", "名称", "最新", "涨幅", "涨跌",
            "成交量", "现量", "买一价", "卖一价", "涨速", "换手",
            "成交额", "市盈率", "所属行业", "最高", "最低",
            "开盘", "昨收", "振幅", "量比", "委比", "委差",
            "均价", "内盘", "外盘", "内外比", "买一量", "卖一量",
            "市净率", "总股本", "总市值", "流通股本", "流通市值",
            "3日涨幅", "6日涨幅", "3日换手", "6日换手",
        ]

        # 重命名
        df.rename(columns={v: k for k, v in col_map.items() if v in df.columns}, inplace=True)

        # 添加东方财富格式中缺少的列（用"--"填充）
        for col in target_cols:
            if col not in df.columns:
                df[col] = "--"

        # 限定列顺序
        df = df[[c for c in target_cols if c in df.columns]]

        # 添加序号
        df.insert(0, "序", range(1, len(df) + 1))

        # UTF-16 + Tab 保存（与原有文件格式一致）
        df.to_csv(output_path, index=False, encoding="utf-16", sep="\t")
        print(f"✅ 已保存: {output_path} ({len(df)}只股票)")
        return str(output_path)

    except Exception as e:
        print(f"❌ 下载失败: {e}")
        return None


if __name__ == "__main__":
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    download(date_arg)
