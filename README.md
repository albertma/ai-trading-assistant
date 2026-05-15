# AI 投研助手

智能投资研究助手 — **复盘、持仓管理、个股分析、风控检查、思维模型训练** 一站式平台。

![Python](https://img.shields.io/badge/Python-3.11+-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green) ![Vue3](https://img.shields.io/badge/Vue-3.5-4FC08D) ![License](https://img.shields.io/badge/license-MIT-yellow)

---

## 📦 项目结构

```
ai-trading-assistant/
├── backend/
│   ├── main.py                  # FastAPI 主入口
│   ├── config.py                # 配置项（路径、端口等）
│   ├── patterns.py              # K线形态识别 + 量价模式
│   ├── models/                  # 数据模型
│   ├── routers/                 # API 路由
│   │   ├── market.py            # 市场行情、情绪周期
│   │   ├── analysis.py          # 个股深度分析
│   │   ├── positions.py         # 持仓管理
│   │   ├── watchlist.py         # 观察池
│   │   ├── risk.py / risk_rules.py  # 风控
│   │   ├── reports.py           # 复盘报告
│   │   ├── mental_models.py     # 思维模型训练
│   │   ├── fundamental.py       # 基本面分析
│   │   ├── profile.py           # 个股档案
│   │   ├── predict.py           # AI 预测
│   │   ├── chat.py              # AI 聊天
│   │   └── stock_info.py        # 个股信息
│   └── services/                # 业务逻辑
│       ├── database/            # SQLite 数据库操作
│       ├── external/            # 外部数据源（akshare、CSV）
│       └── analyze/             # 技术面/基本面分析引擎
├── frontend/
│   ├── src/
│   │   ├── views/               # 页面组件
│   │   ├── components/          # 通用组件
│   │   └── api/index.js         # API 封装
│   └── package.json
├── run.py                       # 启动入口
└── scripts/                     # 辅助脚本
```

---

## 🚀 快速启动

### 前置条件

- Python **3.11+**
- Node.js **18+**（仅构建前端时需要）
- macOS / Linux

### 1. 克隆项目

```bash
git clone git@github.com:albertma/ai-trading-assistant.git
cd ai-trading-assistant
```

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

如果项目没有 `requirements.txt`，手动安装核心依赖：

```bash
pip install fastapi uvicorn[standard] pandas numpy requests httpx akshare
```

> **akshare** 是 A 股数据源核心依赖，建议安装最新版：
> `pip install akshare --upgrade`

### 3. 构建前端

```bash
cd frontend
npm install
npm run build
cd ..
```

前端为 Vue3 + Element Plus + ECharts，构建产物输出到 `frontend/dist/`。

### 4. 准备数据目录

项目运行时需要在 `~/Jarvis/` 下存放数据，目录结构：

```
~/Jarvis/
├── A股行情信息/          # 沪深京A股日线CSV（UTF-16 TSV）
├── 仓位管理.csv           # 持仓数据
├── 复盘/                  # 复盘报告
├── 个股分析/              # 个股分析输出
├── reports/               # 新闻/早报
└── ai_trading/
    └── stock_archive.db   # SQLite数据库（首次启动自动创建）
```

**A 股日线数据**可从 akshare 自动拉取，也可手动下载 CSV 放入 `~/Jarvis/A股行情信息/`，格式为：

- 文件名：`沪深京A股YYYY-MM-DD.csv`
- 编码：UTF-16
- 分隔符：Tab

### 5. 启动服务

```bash
python3 run.py
```

访问 http://localhost:8080

---

## 🧭 核心功能

### 📊 市场概览
- 全市场涨跌统计、涨跌比、情绪周期（30日回溯）
- 行业涨幅/跌幅/成交额 TOP10
- 大盘指数走势图（沪深300 + 中证500）

### 📋 持仓管理
- 多标的持仓看板（盈亏、占比、涨跌幅）
- 交易日志管理（买入/卖出/调仓）
- 组合分析（集中度、行业分布）

### 🔍 个股深度分析
- **技术面**：均线系统、MACD、RSI、K线形态识别（17种经典形态 + 杯柄形态）
- **量价分析**：量价齐升、放量突破、天量天价、地量地价、堆量上涨等10种高级模式
- **基本面**：杜邦分析、财务报告、行业对比、供应链分析
- **估值**：PE/PB 分位、历史对比
- **AI 预测**：基于技术指标的趋势判断

### 🛡️ 风控
- 交易铁律检查（MA200、涨幅限制等）
- 自定义风控规则
- 持仓风险预警

### 🧠 思维模型训练
- 22个投资思维模型（均值回归、反脆弱、涌现等）
- 每日 AI 出题 + 结合行情
- 用户预测 → 次日自动反思评分

### 📝 复盘报告
- 每日自动复盘（市场总结 + 持仓回顾 + 交易检查）
- 历史复盘报告检索

---

## 🔧 技术栈

| 层级 | 技术 |
|------|------|
| **后端框架** | FastAPI + Uvicorn |
| **前端框架** | Vue 3 + Vite |
| **UI 组件** | Element Plus |
| **图表** | ECharts |
| **数据源** | akshare（A股）、CSV 文件 |
| **数据库** | SQLite（本地存储） |
| **形态识别** | NumPy + Pandas |

---

## 📁 数据流

```
akshare / CSV 文件
       ↓
    Pandas DataFrame
       ↓
    FastAPI Router  ← 前端 Axios 调用
       ↓
    SQLite 持久化（持仓、缓存、训练记录等）
```

---

## 🔌 外部数据依赖

| 数据 | 来源 | 说明 |
|------|------|------|
| 沪深京A股行情 | `~/Jarvis/A股行情信息/*.csv` + akshare | 日线数据 |
| 指数数据 | akshare | 沪深300、中证500 |
| 财务数据 | akshare | 财报、杜邦分析 |
| 板块数据 | 本地 CSV | 行业分类 |
| 美股/加密货币 | akshare / yfinance | 可选 |

---

## 🕐 定时任务

项目依赖以下定时任务（cron），由外部调度器触发：

| 时间 | 任务 | 说明 |
|------|------|------|
| 11:30 | 午盘快照 | 盘中数据采集 |
| 15:30 | 收盘数据 | 收盘后拉取完整行情 |
| 20:00 | 双保险 | 补拉当天数据 |
| 20:30 | 复盘日报 | 自动生成当日复盘 |

> cron 脚本在 `~/Jarvis/fetch_a_stock_data.py`

---

## 📌 注意

- A 股 CS V 文件编码为 **UTF-16**，分隔符为 **Tab**
- 数据库路径：`~/Jarvis/ai_trading/stock_archive.db`
- 所有时间基于北京时间（Asia/Shanghai）
- 前端是预编译 SPA，修改 `.vue` 后需执行 `npm run build`
