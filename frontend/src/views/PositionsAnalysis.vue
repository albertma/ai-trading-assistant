<template>
    <div class="analysis-page">
        <div v-loading="analyzing" style="min-height:400px;">
            <template v-if="analysisData">
                <!-- 顶部概览卡片 -->
                <el-row :gutter="16" style="margin-bottom:16px;">
                    <el-col :span="6" v-for="s in overviewCards" :key="s.label">
                        <el-card shadow="hover" class="summary-card" :style="{ borderLeft: `4px solid ${s.color}` }">
                            <div class="summary-value" :style="{ color: s.color }">{{ s.value }}</div>
                            <div class="summary-label">{{ s.label }}</div>
                        </el-card>
                    </el-col>
                </el-row>

                <!-- Tab分页 -->
                <el-tabs v-model="activeTab" type="border-card" @tab-change="onTabChange">
                    <el-tab-pane label="🌐 市场分布" name="market">
                        <div class="chart-container">
                            <div ref="marketChartRef" class="pie-chart"></div>
                        </div>
                        <el-table :data="marketList" size="small" stripe style="margin-top:8px;">
                            <el-table-column prop="label" label="市场" width="80" />
                            <el-table-column prop="count" label="数量" width="60" />
                            <el-table-column label="市值" width="130">
                                <template #default="{ row }">¥{{ fmt(row.value) }}</template>
                            </el-table-column>
                            <el-table-column label="盈亏" width="130">
                                <template #default="{ row }">
                                    <span :style="{ color: row.profit >= 0 ? '#f56c6c' : '#67c23a' }">{{ row.profit >= 0 ? '+' : '' }}¥{{ fmt(row.profit) }}</span>
                                </template>
                            </el-table-column>
                            <el-table-column label="占比" width="80">
                                <template #default="{ row }">{{ totalValue > 0 ? (row.value / totalValue * 100).toFixed(1) : 0 }}%</template>
                            </el-table-column>
                        </el-table>
                    </el-tab-pane>

                    <el-tab-pane label="🏭 行业分布" name="industry">
                        <div class="chart-container">
                            <div ref="industryChartRef" class="pie-chart"></div>
                        </div>
                        <el-table :data="industryList" size="small" stripe style="margin-top:8px;" max-height="250">
                            <el-table-column prop="industry" label="行业" width="110" />
                            <el-table-column prop="count" label="数量" width="60" />
                            <el-table-column label="市值" width="130">
                                <template #default="{ row }">¥{{ fmt(row.value) }}</template>
                            </el-table-column>
                            <el-table-column label="盈亏" width="130">
                                <template #default="{ row }">
                                    <span :style="{ color: row.profit >= 0 ? '#f56c6c' : '#67c23a' }">{{ row.profit >= 0 ? '+' : '' }}¥{{ fmt(row.profit) }}</span>
                                </template>
                            </el-table-column>
                        </el-table>
                    </el-tab-pane>

                    <el-tab-pane label="🎯 主题分布" name="theme">
                        <div class="chart-container">
                            <div ref="themeChartRef" class="pie-chart"></div>
                        </div>
                        <el-table :data="themeList" size="small" stripe style="margin-top:8px;">
                            <el-table-column prop="theme" label="主题" width="90" />
                            <el-table-column prop="count" label="数量" width="60" />
                            <el-table-column label="市值" width="130">
                                <template #default="{ row }">¥{{ fmt(row.value) }}</template>
                            </el-table-column>
                            <el-table-column label="盈亏" width="130">
                                <template #default="{ row }">
                                    <span :style="{ color: row.profit >= 0 ? '#f56c6c' : '#67c23a' }">{{ row.profit >= 0 ? '+' : '' }}¥{{ fmt(row.profit) }}</span>
                                </template>
                            </el-table-column>
                        </el-table>
                    </el-tab-pane>

                    <el-tab-pane label="🏆 盈亏排行" name="ranking">
                        <el-row :gutter="16">
                            <el-col :span="12">
                                <el-card shadow="hover">
                                    <template #header><b style="color:#f56c6c;">🟢 盈利 TOP</b></template>
                                    <el-table :data="topWinners" size="small" stripe>
                                        <el-table-column label="#" type="index" width="40" />
                                        <el-table-column label="名称" width="90">
                                            <template #default="{ row }">
                                                <router-link :to="`/analysis?code=${row.code}`" style="color:#409eff;text-decoration:none;">{{ row.name }}</router-link>
                                            </template>
                                        </el-table-column>
                                        <el-table-column label="代码" width="80">
                                            <template #default="{ row }">
                                                <router-link :to="`/analysis?code=${row.code}`" style="color:#409eff;text-decoration:none;">{{ row.code }}</router-link>
                                            </template>
                                        </el-table-column>
                                        <el-table-column label="盈亏" width="100">
                                            <template #default="{ row }">
                                                <el-tag type="danger" size="small" effect="dark">+{{ row.profit.toFixed(0) }}</el-tag>
                                            </template>
                                        </el-table-column>
                                    </el-table>
                                </el-card>
                            </el-col>
                            <el-col :span="12">
                                <el-card shadow="hover">
                                    <template #header><b style="color:#67c23a;">🔴 亏损 TOP</b></template>
                                    <el-table :data="topLosers" size="small" stripe>
                                        <el-table-column label="#" type="index" width="40" />
                                        <el-table-column label="名称" width="90">
                                            <template #default="{ row }">
                                                <router-link :to="`/analysis?code=${row.code}`" style="color:#409eff;text-decoration:none;">{{ row.name }}</router-link>
                                            </template>
                                        </el-table-column>
                                        <el-table-column label="代码" width="80">
                                            <template #default="{ row }">
                                                <router-link :to="`/analysis?code=${row.code}`" style="color:#409eff;text-decoration:none;">{{ row.code }}</router-link>
                                            </template>
                                        </el-table-column>
                                        <el-table-column label="盈亏" width="100">
                                            <template #default="{ row }">
                                                <el-tag type="success" size="small" effect="dark">{{ row.profit.toFixed(0) }}</el-tag>
                                            </template>
                                        </el-table-column>
                                    </el-table>
                                </el-card>
                            </el-col>
                        </el-row>
                    </el-tab-pane>
                </el-tabs>
            </template>
            <el-empty v-else-if="!analyzing" description="暂无持仓数据" />
        </div>
    </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, onBeforeUnmount } from 'vue'
import { getPositionAnalysis, getPositions } from '../api/index.js'
import * as echarts from 'echarts'

const loading = ref(true)
const analyzing = ref(false)
const analysisData = ref(null)
const activeTab = ref('market')

// 图表refs
const marketChartRef = ref(null)
const industryChartRef = ref(null)
const themeChartRef = ref(null)
let marketChart = null
let industryChart = null
let themeChart = null

const CHART_COLORS = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399', '#b37feb', '#36cfc9', '#ff85c0', '#ffd666', '#5cdbd3']

const overviewCards = computed(() => {
    const t = analysisData.value?.total || {}
    return [
        { label: '持仓总数', value: `${t.count} 只`, color: '#409eff' },
        { label: '总成本', value: `¥${fmt(t.cost)}`, color: '#606266' },
        { label: '总市值', value: `¥${fmt(t.value)}`, color: '#606266' },
        { label: '总盈亏', value: `${(t.profit||0) >= 0 ? '+' : ''}¥${fmt(t.profit)} (${t.profit_pct}%)`, color: (t.profit||0) >= 0 ? '#f56c6c' : '#67c23a' },
    ]
})
const totalValue = computed(() => analysisData.value?.total?.value || 1)
const marketList = computed(() => Object.values(analysisData.value?.market_breakdown || {}))
const industryList = computed(() => analysisData.value?.industry_distribution || [])
const themeList = computed(() => analysisData.value?.theme_distribution || [])
const topWinners = computed(() => analysisData.value?.top_winners || [])
const topLosers = computed(() => analysisData.value?.top_losers || [])

function fmt(v) {
    if (v == null) return '0'
    return Math.abs(v).toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

/** 生成饼图配置 - 使用外部标签避免文字重叠 */
function makePieOption(data, nameKey, valueKey) {
    const items = data.filter(d => d[valueKey] > 0)
    if (!items.length) return null
    return {
        tooltip: { trigger: 'item', formatter: '{b}: ¥{c} ({d}%)' },
        legend: { bottom: 0, textStyle: { fontSize: 12 } },
        series: [{
            type: 'pie',
            radius: ['25%', '50%'],
            center: ['50%', '42%'],
            avoidLabelOverlap: true,
            padAngle: 1.5,
            itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
            label: {
                show: true,
                position: 'outside',
                formatter: '{b}\n{d}%',
                fontSize: 11,
                lineHeight: 15,
            },
            labelLine: {
                show: true,
                length: 8,
                length2: 12,
                smooth: true,
            },
            emphasis: {
                label: { show: true, fontSize: 13, fontWeight: 'bold' },
                itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.2)' }
            },
            data: items.map((d, i) => ({
                name: d[nameKey],
                value: d[valueKey],
                itemStyle: { color: CHART_COLORS[i % CHART_COLORS.length] }
            }))
        }]
    }
}

function initCharts() {
    // 市场饼图
    if (marketChartRef.value) {
        if (marketChart) marketChart.dispose()
        marketChart = echarts.init(marketChartRef.value)
        const opt = makePieOption(marketList.value, 'label', 'value')
        if (opt) { marketChart.setOption(opt) }
        else { marketChart.setOption({ title: { text: '暂无数据', left: 'center', top: 'center' } }) }
    }
    // 行业饼图
    if (industryChartRef.value) {
        if (industryChart) industryChart.dispose()
        industryChart = echarts.init(industryChartRef.value)
        const opt = makePieOption(industryList.value, 'industry', 'value')
        if (opt) { industryChart.setOption(opt) }
        else { industryChart.setOption({ title: { text: '暂无数据', left: 'center', top: 'center' } }) }
    }
    // 主题饼图
    if (themeChartRef.value) {
        if (themeChart) themeChart.dispose()
        themeChart = echarts.init(themeChartRef.value)
        const opt = makePieOption(themeList.value, 'theme', 'value')
        if (opt) { themeChart.setOption(opt) }
        else { themeChart.setOption({ title: { text: '暂无数据', left: 'center', top: 'center' } }) }
    }
}

function destroyCharts() {
    if (marketChart) { marketChart.dispose(); marketChart = null }
    if (industryChart) { industryChart.dispose(); industryChart = null }
    if (themeChart) { themeChart.dispose(); themeChart = null }
}

function onTabChange() {
    setTimeout(() => nextTick(() => initCharts()), 200)
}

async function loadData() {
    analyzing.value = true
    try {
        const { data } = await getPositionAnalysis()
        analysisData.value = data.analysis || null
        if (analysisData.value) {
            await nextTick()
            // 等layout稳定后再初始化图表
            setTimeout(() => initCharts(), 200)
        }
    } catch (e) {
        console.error('加载分析失败', e)
    } finally {
        analyzing.value = false
        loading.value = false
    }
}

onMounted(() => loadData())
onBeforeUnmount(() => destroyCharts())
</script>

<style scoped>
.analysis-page {
    max-width: 1200px;
    margin: 0 auto;
}
.summary-card {
    text-align: center;
    cursor: default;
}
.summary-value {
    font-size: 22px;
    font-weight: bold;
}
.summary-label {
    font-size: 12px;
    color: #909399;
    margin-top: 4px;
}
.chart-container {
    width: 100%;
    display: flex;
    justify-content: center;
}
.pie-chart {
    width: 100%;
    max-width: 700px;
    height: 320px;
}
</style>
