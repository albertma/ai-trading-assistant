<template>
    <div class="dashboard">
        <!-- 日期选择条 -->
        <el-card shadow="hover" style="margin-bottom: 16px;">
            <el-row :gutter="16" align="middle">
                <el-col :span="4">
                    <el-date-picker
                        v-model="selectedDate"
                        type="date"
                        placeholder="选择日期"
                        :disabled-date="disabledDate"
                        format="YYYY-MM-DD"
                        value-format="YYYY-MM-DD"
                        @change="onDateChange"
                        style="width:100%"
                    />
                </el-col>
                <el-col :span="2">
                    <el-button @click="toPrevDay" :disabled="!prevDate" size="default">‹ 前一天</el-button>
                </el-col>
                <el-col :span="2">
                    <el-button @click="toNextDay" :disabled="!nextDate" size="default">后一天 ›</el-button>
                </el-col>
                <el-col :span="4">
                    <el-tag v-if="dataDate" type="info" effect="plain" size="large">
                        📅 {{ dataDate }}
                    </el-tag>
                </el-col>
                <el-col :span="12" style="text-align:right;">
                    <el-tag v-if="dataDate" :type="marketSentiment.type" effect="dark" size="large">
                        {{ marketSentiment.text }}
                    </el-tag>
                </el-col>
            </el-row>
        </el-card>

        <!-- 市场状态卡片 -->
        <el-row v-if="!noData" :gutter="16">
            <el-col :span="6" v-for="card in statCards" :key="card.label">
                <el-card shadow="hover" class="stat-card" :class="card.cls">
                    <div class="stat-value" :style="{ color: card.color }">{{ card.value }}</div>
                    <div class="stat-label">{{ card.label }}</div>
                </el-card>
            </el-col>
        </el-row>

        <template v-if="!noData">
            <el-row :gutter="16" style="margin-top: 16px;">
                <el-col :span="12">
                    <el-card shadow="hover">
                        <template #header><b>📈 涨幅TOP10</b></template>
                        <el-table :data="gainers" size="small" stripe style="width:100%">
                            <el-table-column prop="code" label="代码" width="90" />
                            <el-table-column prop="name" label="名称" min-width="120" />
                            <el-table-column prop="change_pct" label="涨幅" width="90">
                                <template #default="{ row }">
                                    <span :style="{ color: (row.change_pct||0) >= 0 ? '#f56c6c' : '#67c23a' }">
                                        {{ (row.change_pct||0).toFixed(2) }}%
                                    </span>
                                </template>
                            </el-table-column>
                        </el-table>
                    </el-card>
                </el-col>
                <el-col :span="12">
                    <el-card shadow="hover">
                        <template #header><b>📉 跌幅TOP10</b></template>
                        <el-table :data="losers" size="small" stripe style="width:100%">
                            <el-table-column prop="code" label="代码" width="90" />
                            <el-table-column prop="name" label="名称" min-width="120" />
                            <el-table-column prop="change_pct" label="涨幅" width="90">
                                <template #default="{ row }">
                                    <span :style="{ color: (row.change_pct||0) >= 0 ? '#f56c6c' : '#67c23a' }">
                                        {{ (row.change_pct||0).toFixed(2) }}%
                                    </span>
                                </template>
                            </el-table-column>
                        </el-table>
                    </el-card>
                </el-col>
            </el-row>

            <el-row :gutter="16" style="margin-top: 16px;">
                <el-col :span="12">
                    <el-card shadow="hover">
                        <template #header><b>🔥 热门板块 TOP10</b></template>
                        <el-table :data="hotSectors" size="small" stripe style="width:100%">
                            <el-table-column type="index" label="#" width="50" />
                            <el-table-column prop="name" label="板块" min-width="140" />
                            <el-table-column prop="avg_change" label="平均涨幅" width="100">
                                <template #default="{ row }">
                                    <span :style="{ color: row.avg_change >= 0 ? '#f56c6c' : '#67c23a', fontWeight: 'bold' }">
                                        {{ row.avg_change.toFixed(2) }}%
                                    </span>
                                </template>
                            </el-table-column>
                            <el-table-column prop="count" label="数量" width="60" />
                        </el-table>
                    </el-card>
                </el-col>
                <el-col :span="12">
                    <el-card shadow="hover">
                        <template #header><b>💰 成交额 TOP10</b></template>
                        <el-table :data="topVolume" size="small" stripe style="width:100%">
                            <el-table-column prop="code" label="代码" width="90" />
                            <el-table-column prop="name" label="名称" min-width="120" />
                            <el-table-column prop="amount" label="成交额(亿)" width="100">
                                <template #default="{ row }">
                                    {{ (row.amount||0).toFixed(1) }}
                                </template>
                            </el-table-column>
                            <el-table-column prop="change_pct" label="涨幅" width="80">
                                <template #default="{ row }">
                                    <span :style="{ color: (row.change_pct||0) >= 0 ? '#f56c6c' : '#67c23a' }">
                                        {{ (row.change_pct||0).toFixed(2) }}%
                                    </span>
                                </template>
                            </el-table-column>
                        </el-table>
                    </el-card>
                </el-col>
            </el-row>
        </template>

        <!-- 加载 / 无数据 -->
        <el-row v-if="loading" style="margin-top:40px;text-align:center;">
            <el-col><el-icon class="is-loading" :size="24"><Loading /></el-icon> 加载中...</el-col>
        </el-row>
        <el-row v-if="noData && !loading" style="margin-top:40px;text-align:center;">
            <el-col>
                <el-empty :description="noDataMsg" />
            </el-col>
        </el-row>
    </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { getMarketOverview, getMarketDates } from '../api/index.js'

const loading = ref(true)
const noData = ref(false)
const noDataMsg = ref('')
const dataDate = ref('')
const availableDates = ref([])

// 日期选择
const selectedDate = ref(null)

const gainers = ref([])
const losers = ref([])
const hotSectors = ref([])
const topVolume = ref([])
const statCards = ref([
    { label: '上涨家数', value: '--', color: '#f56c6c', cls: '' },
    { label: '下跌家数', value: '--', color: '#67c23a', cls: '' },
    { label: '涨停', value: '--', color: '#e6a23c', cls: '' },
    { label: '跌停', value: '--', color: '#909399', cls: '' },
])

// 前后一天导航
const dateSet = computed(() => new Set(availableDates.value))
const prevDate = computed(() => {
    if (!dataDate.value || !availableDates.value.length) return null
    const idx = availableDates.value.indexOf(dataDate.value)
    return idx < availableDates.value.length - 1 ? availableDates.value[idx + 1] : null
})
const nextDate = computed(() => {
    if (!dataDate.value || !availableDates.value.length) return null
    const idx = availableDates.value.indexOf(dataDate.value)
    return idx > 0 ? availableDates.value[idx - 1] : null
})

// 市场情绪标签
const marketSentiment = computed(() => {
    if (!statCards.value.length) return { type: 'info', text: '--' }
    const up = statCards.value[0]?.value || 0
    const down = statCards.value[1]?.value || 0
    const total = up + down
    if (!total) return { type: 'info', text: '中性' }
    const ratio = up / total
    if (ratio > 0.6) return { type: 'danger', text: '🔥 普涨' }
    if (ratio < 0.4) return { type: 'success', text: '❄️ 普跌' }
    return { type: 'warning', text: '⚖️ 分化' }
})

// 不可选日期（非交易日灰掉）
function disabledDate(time) {
    const d = time.getFullYear() + '-' +
        String(time.getMonth() + 1).padStart(2, '0') + '-' +
        String(time.getDate()).padStart(2, '0')
    return !dateSet.value.has(d)
}

function toPrevDay() {
    if (prevDate.value) {
        selectedDate.value = prevDate.value
        loadData(prevDate.value)
    }
}

function toNextDay() {
    if (nextDate.value) {
        selectedDate.value = nextDate.value
        loadData(nextDate.value)
    }
}

function onDateChange(val) {
    if (val) loadData(val)
}

async function loadData(dateStr) {
    loading.value = true
    noData.value = false
    try {
        const { data } = await getMarketOverview(dateStr || undefined)
        if (data.status === 'no_data') {
            noData.value = true
            noDataMsg.value = data.message || '暂无行情数据'
            return
        }
        dataDate.value = data.date
        const s = data.summary
        statCards.value = [
            { label: '上涨家数', value: s.up, color: '#f56c6c', cls: 'stat-up' },
            { label: '下跌家数', value: s.down, color: '#67c23a', cls: 'stat-down' },
            { label: '涨停', value: s.limit_up, color: '#e6a23c', cls: 'stat-limit' },
            { label: '跌停', value: s.limit_down, color: '#909399', cls: 'stat-limit-down' },
        ]
        gainers.value = (data.top_gainers || []).slice(0, 10)
        losers.value = (data.top_losers || []).slice(0, 10)
        hotSectors.value = (data.hot_sectors || []).slice(0, 10)
        topVolume.value = (data.top_volume || []).slice(0, 10)
    } catch (e) {
        console.error(e)
        noData.value = true
        noDataMsg.value = '加载失败'
    } finally {
        loading.value = false
    }
}

onMounted(async () => {
    // 先获取可选日期列表
    try {
        const { data } = await getMarketDates()
        availableDates.value = data.dates || []
        selectedDate.value = data.latest || null
    } catch (e) {
        console.error(e)
    }
    // 加载最新数据
    await loadData(selectedDate.value)
})
</script>

<style scoped>
.dashboard { max-width: 1400px; margin: 0 auto; }
.stat-card { text-align: center; }
.stat-card :deep(.el-card__body) { padding: 20px; }
.stat-value { font-size: 32px; font-weight: bold; }
.stat-label { font-size: 14px; color: #909399; margin-top: 4px; }
.stat-up { border-top: 3px solid #f56c6c; }
.stat-down { border-top: 3px solid #67c23a; }
.stat-limit { border-top: 3px solid #e6a23c; }
.stat-limit-down { border-top: 3px solid #909399; }
</style>
