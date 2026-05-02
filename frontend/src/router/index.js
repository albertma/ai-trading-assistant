import { createRouter, createWebHistory } from 'vue-router'

import Dashboard from '../views/Dashboard.vue'
import Positions from '../views/Positions.vue'
import Analysis from '../views/Analysis.vue'
import RiskCheck from '../views/RiskCheck.vue'
import RiskRules from '../views/RiskRules.vue'
import Reports from '../views/Reports.vue'
import Watchlist from '../views/Watchlist.vue'
import PositionsAnalysis from '../views/PositionsAnalysis.vue'

const routes = [
    { path: '/', name: 'Dashboard', component: Dashboard, meta: { title: '市场概览', icon: 'DataAnalysis' } },
    { path: '/watchlist', name: 'Watchlist', component: Watchlist, meta: { title: '观察池', icon: 'View' } },
    { path: '/positions', name: 'Positions', component: Positions, meta: { title: '持仓看板', icon: 'Wallet' } },
    { path: '/positions-analysis', name: 'PositionsAnalysis', component: PositionsAnalysis, meta: { title: '持仓分析', icon: 'DataBoard' } },
    { path: '/analysis', name: 'Analysis', component: Analysis, meta: { title: '个股分析', icon: 'Search' } },
    { path: '/risk', name: 'RiskCheck', component: RiskCheck, meta: { title: '风控检查', icon: 'WarningFilled' } },
    { path: '/risk-rules', name: 'RiskRules', component: RiskRules, meta: { title: '风控规则', icon: 'Setting' } },
    { path: '/reports', name: 'Reports', component: Reports, meta: { title: '复盘报告', icon: 'Document' } },
]

const router = createRouter({
    history: createWebHistory(),
    routes,
})

export default router
