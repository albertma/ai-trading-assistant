"""仓位管理模块 — 常量定义"""

# 汇率（近似，用于汇总展示）
FX_RATES = {
    "a_stock": 1.0,    # A股 RMB
    "hk_stock": 0.93,  # HKD→CNY
    "us_stock": 7.25,  # USD→CNY
    "crypto": 7.25,    # Crypto→USD→CNY
}

MARKET_LABELS = {
    "a_stock": "A股",
    "hk_stock": "港股",
    "us_stock": "美股",
    "crypto": "加密货币",
}

CURRENCY_SYMBOLS = {
    "a_stock": "¥",
    "hk_stock": "HK$",
    "us_stock": "$",
    "crypto": "$",
}

CRYPTO_SYMBOLS = {
    "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "DOT",
    "AVAX", "MATIC", "LINK", "UNI", "ATOM", "LTC", "BCH", "FIL",
    "NEAR", "APT", "SUI", "OP", "ARB", "PEPE", "SHIB", "INJ",
    "TIA", "SEI", "STRK", "ZRO", "EIGEN", "TAO", "FET", "AGIX",
    "OCEAN", "RENDER", "GRT", "ICP", "EGLD", "KAS", "CRO", "FTM",
    "ALGO", "VET", "THETA", "TRX", "ALICE", "SAND", "MANA", "AXS",
    "GALA", "ENJ", "CHZ", "APE", "BLUR",
}

# 行业→主题映射
THEME_MAP = {
    "光伏设备": "新能源", "电池": "新能源", "能源金属": "新能源",
    "电力": "新能源", "电网设备": "新能源",
    "消费电子": "消费电子", "计算机设备": "科技",
    "化学制药": "医药", "中药Ⅱ": "医药",
    "农化制品": "化工", "化学制品": "化工", "化学原料": "化工",
    "旅游零售Ⅱ": "消费", "航运港口": "周期",
    "小金属": "有色", "汽车零部件": "汽车",
    "半导体": "半导体",
}

# 美股→行业映射
US_STOCK_INDUSTRY = {
    "TSLA": "汽车", "TSM": "半导体", "CSCO": "科技",
    "GOOG": "互联网", "XPEV": "汽车",
    "AAPL": "消费电子", "MSFT": "科技", "AMZN": "互联网",
    "NVDA": "半导体", "AMD": "半导体", "INTC": "半导体",
    "META": "互联网", "NFLX": "互联网", "BABA": "互联网",
    "JD": "互联网", "PDD": "互联网", "BIDU": "科技",
    "NIO": "汽车", "LI": "汽车", "CRCL": "区块链",
}

# 港股→行业映射
HK_STOCK_INDUSTRY = {
    "01211": "汽车",
}

# CSV 文件列名
POSITION_FIELDS = [
    "代码", "名称", "数量", "成本价", "当前价",
    "持仓成本", "当前市值", "盈亏金额", "盈亏比例", "备注", "市场",
]
