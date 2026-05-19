# AI投研助手

金融AI投研助理 — 复盘、持仓、分析、风控

## 功能预览

### 📊 市场概览

大盘行情总览：涨跌家数、涨停跌停、涨幅/跌幅 TOP10、热门板块排行。

![市场概览](screenshots/dashboard.png)

### 🔭 观察池

自选股池管理：K线图、技术指标、基本面、行业前瞻、操作笔记。

![观察池](screenshots/watchlist.png)

### 📊 板块分析

板块周期研判：市场整体判定、相位分布、相位推演、关注板块、主线逻辑（AI动态摘要）、各板块周期相位表。

![板块分析](screenshots/sector-analysis.png)

### 💼 持仓看板

持仓明细、盈亏分析、主题分布、行业配置。

![持仓看板](screenshots/portfolio.png)

### 🔍 个股分析

个股多维度分析：技术面、基本面、行业面、AI预测。

![个股分析](screenshots/stock-analysis.png)

### ⚠️ 风控管理

持仓风控检查、规则管理、风险预警。

![风控管理](screenshots/risk-check.png)

### 📋 Cron任务

后台任务管理：手动触发收盘数据/午盘快照/复盘日报/板块分析/午盘分析，历史记录查询。

![Cron任务](screenshots/cron-history.png)

---

## 技术栈

- **后端**: Python FastAPI + SQLite
- **前端**: Vue 3 + Element Plus + ECharts
- **数据**: akshare（东方财富接口）
- **AI**: DeepSeek API（动态摘要生成）

---

## 快速启动

### 前提条件

- Python 3.10+
- Node.js 18+
- SQLite 3

### 方式一：一键初始化

```bash
# 克隆/进入项目
cd ai-trading-assistant

# 运行初始化脚本
bash setup/setup.sh
```

### 方式二：手动初始化

#### 1. 安装依赖

```bash
# Python 依赖
pip3 install fastapi uvicorn akshare pandas numpy openai pyyaml

# 前端依赖
cd frontend
npm install
npm run build
cd ..
```

#### 2. 初始化数据库

数据库位置：`~/Jarvis/ai_trading/stock_archive.db`

```bash
# 创建数据目录
mkdir -p ~/Jarvis/ai_trading
mkdir -p ~/Jarvis/A股行情信息
mkdir -p ~/Jarvis/复盘

# 创建表结构并导入种子数据（12371只A股基本信息 + 风控规则 + 思维模型）
sqlite3 ~/Jarvis/ai_trading/stock_archive.db < setup/seed.sql
```

> **seed.sql 包含：**
> - 全部 22 张表的结构定义（CREATE TABLE）
> - 12371 条个股基本信息（代码、名称、市场、行业、总市值等）
> - 16 条默认风控规则
> - 22 条思维模型数据
> - 130 条产业链关系数据

#### 3. 配置行情数据

系统运行时自动从东方财富（akshare）下载每日行情CSV。如需离线运行，可将历史CSV放入：

```
~/Jarvis/A股行情信息/沪深京A股YYYY-MM-DD.csv
```

#### 4. 启动服务

```bash
python3 run.py
```

访问 [http://localhost:8080](http://localhost:8080)

---

## 项目结构

```
ai-trading-assistant/
├── backend/               # Python 后端
│   ├── main.py           # FastAPI 入口 + 静态文件
│   ├── config.py         # 配置（HOST/PORT）
│   ├── routers/          # API 路由
│   │   ├── market.py     # 市场概览
│   │   ├── analysis.py   # 个股分析
│   │   ├── mental_models.py   # 板块周期 + 思维模型
│   │   └── ...
│   └── services/         # 业务逻辑
│       ├── database/     # 数据库 + init_db()
│       ├── tradingmgt/   # 持仓管理
│       └── external/     # akshare 封装
├── frontend/             # Vue 3 前端
│   ├── src/
│   │   └── views/        # 页面组件
│   └── dist/             # 构建产物
├── setup/                # 初始化脚本
│   ├── setup.sh          # 一键初始化
│   └── seed.sql          # 数据库种子文件
├── screenshots/          # 功能预览截图
└── run.py                # 启动入口
```
