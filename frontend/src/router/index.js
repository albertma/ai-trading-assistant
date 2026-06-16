import { createRouter, createWebHistory } from 'vue-router'

import Dashboard from '../views/Dashboard.vue'
import Positions from '../views/Positions.vue'
import Analysis from '../views/Analysis.vue'
import RiskCheck from '../views/RiskCheck.vue'
import RiskRules from '../views/RiskRules.vue'
import Reports from '../views/Reports.vue'
import Watchlist from '../views/Watchlist.vue'
import PositionsAnalysis from '../views/PositionsAnalysis.vue'
import ChainManager from '../views/ChainManager.vue'
import KnowledgeGraph from '../views/KnowledgeGraph.vue'
import MentalModels from '../views/MentalModels.vue'
import SectorAnalysis from '../views/SectorAnalysis.vue'
import CronHistory from '../views/CronHistory.vue'
import Narratives from '../views/Narratives.vue'
import NewsOverview from '../views/NewsOverview.vue'
import TradingPlans from '../views/TradingPlans.vue'
import StrategyBacktest from '../views/StrategyBacktest.vue'
import AIDrivenReport from '../views/AIDrivenReport.vue'
import StrategyResearch from '../views/StrategyResearch.vue'
import StrategyCreate from '../views/StrategyCreate.vue'
import StrategyConfig from '../views/StrategyConfig.vue'

const routes = [
    { path: '/', name: 'Dashboard', component: Dashboard, meta: { title: '市场概览', icon: 'DataAnalysis' } },
    { path: '/ai-driven', name: 'AIDrivenReport', component: AIDrivenReport, meta: { title: 'AI检测', icon: 'MagicStick' } },
    { path: '/sector-analysis', name: 'SectorAnalysis', component: SectorAnalysis, meta: { title: '板块分析', icon: 'DataBoard' } },
    { path: '/watchlist', name: 'Watchlist', component: Watchlist, meta: { title: '观察池', icon: 'View' } },
    { path: '/positions', name: 'Positions', component: Positions, meta: { title: '持仓看板', icon: 'Wallet' } },
    { path: '/positions-analysis', name: 'PositionsAnalysis', component: PositionsAnalysis, meta: { title: '持仓分析', icon: 'DataBoard' } },
    { path: '/analysis', name: 'Analysis', component: Analysis, meta: { title: '个股分析', icon: 'Search' } },
    { path: '/risk', name: 'RiskCheck', component: RiskCheck, meta: { title: '风控检查', icon: 'WarningFilled' } },
    { path: '/risk-rules', name: 'RiskRules', component: RiskRules, meta: { title: '风控规则', icon: 'Setting' } },
    { path: '/reports', name: 'Reports', component: Reports, meta: { title: '复盘报告', icon: 'Document' } },
    { path: '/chains', name: 'ChainManager', component: ChainManager, meta: { title: '产业链配置', icon: 'Connection' } },
    { path: '/knowledge-graph', name: 'KnowledgeGraph', component: KnowledgeGraph, meta: { title: '知识库', icon: 'Cpu' } },
    { path: '/mental-models', name: 'MentalModels', component: MentalModels, meta: { title: '模型库', icon: 'Platform' } },
    { path: '/mental-training', name: 'MentalTraining', component: () => import('../views/MentalTraining.vue'), meta: { title: '每日模型训练', icon: 'TrendCharts' } },
    { path: '/cron-history', name: 'CronHistory', component: CronHistory, meta: { title: 'Cron任务', icon: 'Timer' } },
    { path: '/narratives', name: 'Narratives', component: Narratives, meta: { title: '叙事分析', icon: 'TrendCharts' } },
    { path: '/news-overview', name: 'NewsOverview', component: NewsOverview, meta: { title: '新闻分析', icon: 'Reading' } },
    { path: '/trading-plans', name: 'TradingPlans', component: TradingPlans, meta: { title: '交易计划', icon: 'List' } },
    { path: '/strategy-backtest', name: 'StrategyBacktest', component: StrategyBacktest, meta: { title: '策略回测', icon: 'TrendCharts' } },
    { path: '/strategy-research', name: 'StrategyResearch', component: StrategyResearch, meta: { title: '策略管理', icon: 'Files' } },
    { path: '/strategy-create', name: 'StrategyCreate', component: StrategyCreate, meta: { title: '策略创建', icon: 'Edit' } },
    { path: '/strategy-create/:id', name: 'StrategyEdit', component: StrategyCreate, meta: { title: '编辑策略', icon: 'Edit' } },
    { path: '/strategy-config', name: 'StrategyConfig', component: StrategyConfig, meta: { title: '策略配置', icon: 'Setting' } },
]

const router = createRouter({
    history: createWebHistory(),
    routes,
})

export default router
