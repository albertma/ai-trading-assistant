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
                <el-sub-menu index="dashboard-group">
                    <template #title>
                        <el-icon><DataAnalysis /></el-icon>
                        <span>市场概览</span>
                    </template>
                    <el-menu-item index="/">
                        <span>📊 大盘行情</span>
                    </el-menu-item>
                    <el-menu-item index="/reports">
                        <span>📋 复盘报告</span>
                    </el-menu-item>
                </el-sub-menu>
                <el-menu-item index="/watchlist">
                    <el-icon><View /></el-icon>
                    <span>观察池</span>
                </el-menu-item>
                <el-sub-menu index="positions-group">
                    <template #title>
                        <el-icon><Wallet /></el-icon>
                        <span>持仓看板</span>
                    </template>
                    <el-menu-item index="/positions">
                        <span>📋 持仓明细</span>
                    </el-menu-item>
                    <el-menu-item index="/positions-analysis">
                        <span>📊 持仓分析</span>
                    </el-menu-item>
                </el-sub-menu>
                <el-menu-item index="/analysis">
                    <el-icon><Search /></el-icon>
                    <span>个股分析</span>
                </el-menu-item>
                <el-menu-item index="/risk">
                    <el-icon><WarningFilled /></el-icon>
                    <span>风控检查</span>
                </el-menu-item>
                <el-menu-item index="/risk-rules">
                    <el-icon><Setting /></el-icon>
                    <span>风控规则</span>
                </el-menu-item>
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
.app-aside { background-color: #001529; overflow: hidden; }
.logo {
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
.side-menu { border-right: none; }
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
