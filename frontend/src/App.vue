<template>
    <el-container class="app-container">
        <!-- 侧边栏 -->
        <el-aside width="200px" class="app-aside">
            <div class="logo">
                <span class="logo-icon">📊</span>
                <span class="logo-text">AI投研助手</span>
            </div>
        <el-menu
                :default-active="route.path"
                router
                :collapse="false"
                class="side-menu"
                background-color="#001529"
                text-color="#ffffffb3"
                active-text-color="#fff"
            >
                <!-- 工作台 -->
                <el-menu-item index="/ai-driven">
                    <el-icon><MagicStick /></el-icon>
                    <span>🧭 工作台</span>
                </el-menu-item>

                <div class="menu-divider" />

                <!-- 市场洞察 -->
                <el-sub-menu index="market-group">
                    <template #title>
                        <el-icon><DataAnalysis /></el-icon>
                        <span>📊 市场洞察</span>
                    </template>
                    <el-menu-item index="/">
                        <span>📈 大盘行情</span>
                    </el-menu-item>
                    <el-menu-item index="/sector-analysis">
                        <span>🧩 板块分析</span>
                    </el-menu-item>
                    <el-menu-item index="/narratives">
                        <span>🎯 叙事分析</span>
                    </el-menu-item>
                    <el-menu-item index="/news-overview">
                        <span>📰 新闻分析</span>
                    </el-menu-item>
                </el-sub-menu>

                <div class="menu-divider" />

                <!-- 研究工具 -->
                <el-sub-menu index="research-group">
                    <template #title>
                        <el-icon><Search /></el-icon>
                        <span>🔬 研究工具</span>
                    </template>
                    <el-menu-item index="/analysis">
                        <span>🔍 个股分析</span>
                    </el-menu-item>
                    <el-menu-item index="/chains">
                        <span>📎 产业链</span>
                    </el-menu-item>
                    <el-menu-item index="/knowledge-graph">
                        <span>🗄️ 知识库</span>
                    </el-menu-item>
                    <el-sub-menu index="mental-group">
                        <template #title>
                            <span>🧠 思维模型</span>
                        </template>
                        <el-menu-item index="/mental-models">
                            <span>📚 模型库</span>
                        </el-menu-item>
                        <el-menu-item index="/mental-training">
                            <span>🧪 每日训练</span>
                        </el-menu-item>
                    </el-sub-menu>
                </el-sub-menu>

                <div class="menu-divider" />

                <!-- 交易决策 -->
                <el-sub-menu index="trade-group">
                    <template #title>
                        <el-icon><TrendCharts /></el-icon>
                        <span>⚡ 交易决策</span>
                    </template>
                    <el-menu-item index="/watchlist">
                        <span>👁️ 观察池</span>
                    </el-menu-item>
                    <el-menu-item index="/strategy-backtest">
                        <span>📐 策略回测</span>
                    </el-menu-item>
                    <el-menu-item index="/trading-plans">
                        <span>📝 交易计划</span>
                    </el-menu-item>
                </el-sub-menu>

                <div class="menu-divider" />

                <!-- 持仓管理 -->
                <el-sub-menu index="portfolio-group">
                    <template #title>
                        <el-icon><Wallet /></el-icon>
                        <span>💼 持仓管理</span>
                    </template>
                    <el-menu-item index="/positions">
                        <span>📋 持仓明细</span>
                    </el-menu-item>
                    <el-menu-item index="/positions-analysis">
                        <span>📊 持仓分析</span>
                    </el-menu-item>
                    <el-sub-menu index="risk-group">
                        <template #title>
                            <span>🛡️ 风控</span>
                        </template>
                        <el-menu-item index="/risk">
                            <span>⚠️ 风控检查</span>
                        </el-menu-item>
                        <el-menu-item index="/risk-rules">
                            <span>⚙️ 风控规则</span>
                        </el-menu-item>
                    </el-sub-menu>
                </el-sub-menu>

                <div class="menu-divider" />

                <!-- 复盘总结 -->
                <el-menu-item index="/reports">
                    <el-icon><Document /></el-icon>
                    <span>🔄 复盘总结</span>
                </el-menu-item>

                <!-- 系统 -->
                <el-sub-menu index="system-group">
                    <template #title>
                        <el-icon><Setting /></el-icon>
                        <span>⚙️ 系统</span>
                    </template>
                    <el-menu-item index="/cron-history">
                        <span>⏱ Cron任务</span>
                    </el-menu-item>
                </el-sub-menu>
            </el-menu>
        </el-aside>

        <!-- 主区域 -->
        <el-container>
            <el-header class="app-header">
                <h2>{{ pageTitle }}</h2>
                <div class="header-right">
                </div>
            </el-header>
            <el-main class="app-main">
                <router-view />
            </el-main>
        </el-container>
    </el-container>
</template>

<script setup>
import { computed, ref, provide } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const stockName = ref('')
const stockCode = ref('')
provide('stockName', stockName)
provide('stockCode', stockCode)
const pageTitle = computed(() => {
    const base = route.meta?.title || 'AI投研助手'
    if (stockName.value && stockCode.value) {
        return `${base} - ${stockName.value}(${stockCode.value})`
    }
    return base
})
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body, #app { height: 100%; width: 100%; font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif; }

.app-container { height: 100vh; }
.app-aside { background-color: #001529; overflow: hidden; display: flex; flex-direction: column; }
.logo {
    flex-shrink: 0;
    height: 60px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    font-size: 18px;
    font-weight: bold;
    border-bottom: 1px solid rgba(255,255,255,0.1);
}
.logo-icon { font-size: 24px; margin-right: 8px; }
.side-menu { border-right: none; overflow-y: auto; flex: 1; }
.menu-divider {
    height: 1px;
    margin: 4px 16px;
    background: rgba(255,255,255,0.08);
}
.app-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: #fff;
    border-bottom: 1px solid #e4e7ed;
    padding: 0 24px;
    height: 60px;
}
.app-header h2 { font-size: 18px; font-weight: 600; color: #303133; }
.header-right { display: flex; align-items: center; gap: 12px; }
.app-main {
    background: #f0f2f5;
    padding: 20px;
    overflow-y: auto;
    height: calc(100vh - 60px);
}
</style>
