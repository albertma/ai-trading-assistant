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
                <el-col :span="2" v-if="sessionsAvailable.length > 1">
                    <el-radio-group v-model="dataSession" size="small" @change="onSessionChange">
                        <el-radio-button value="noon">午市</el-radio-button>
                        <el-radio-button value="close">收盘</el-radio-button>
                    </el-radio-group>
                </el-col>
                <el-col :span="2" v-else>
                    <el-tag v-if="dataDate" :type="dataSession === 'noon' ? 'warning' : 'success'" size="small">
                        {{ dataSession === 'noon' ? '🌤 午市' : '🌙 收盘' }}
                    </el-tag>
                </el-col>
                <el-col :span="8" style="text-align:right;">
                    <el-tag v-if="dataDate" :type="marketSentiment.type" effect="dark" size="large">
                        {{ marketSentiment.text }}
                    </el-tag>
                </el-col>
            </el-row>
        </el-card>

        <!-- 沪深300 vs 中证500 双轴对比图 -->
        <el-card v-if="indexData.hs300.length" shadow="hover" style="margin-top:16px;">
            <template #header>
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <b>📈 沪深300 vs 中证500</b>
                    <el-radio-group v-model="indexDays" size="small" @change="loadIndexHistory">
                        <el-radio-button value="30">30天</el-radio-button>
                        <el-radio-button value="60">60天</el-radio-button>
                        <el-radio-button value="120">120天</el-radio-button>
                        <el-radio-button value="730">2年</el-radio-button>
                    </el-radio-group>
                </div>
            </template>
            <div ref="indexChartRef" style="width:100%;height:380px;"></div>
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

        <!-- 市场情绪周期 -->
        <el-card v-if="!noData && cycleRecords.length" shadow="hover" style="margin-top:16px;margin-bottom:16px;">
            <template #header>
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <b>📊 市场情绪周期</b>
                    <div style="display:flex;align-items:center;gap:8px;">
                        <el-tag v-if="currentCycleLabel" :type="cycleTagType" size="large" effect="dark">
                            {{ currentCycleLabel }}
                        </el-tag>
                        <el-button size="small" text @click="cycleCollapsed = !cycleCollapsed">
                            {{ cycleCollapsed ? '展开分析' : '收起' }}
                        </el-button>
                    </div>
                </div>
            </template>
            <template v-if="!cycleCollapsed">
                <!-- 周期时间线 -->
                <div style="display:flex;gap:4px;margin-bottom:16px;overflow-x:auto;padding:8px 0;">
                    <div v-for="(r, i) in cycleRecords" :key="r.date"
                        style="flex:1;min-width:90px;text-align:center;padding:8px 6px;border-radius:8px;border:1px solid #334;position:relative;"
                        :style="{ background: cycleBgColor(r.stage) }">
                        <div style="font-size:11px;color:#909399;">{{ r.date.slice(5) }}</div>
                        <div style="font-size:13px;font-weight:bold;margin:4px 0;">{{ r.stage_label }}</div>
                        <div style="font-size:11px;">
                            <span :style="{color: r.avg_change_pct >= 0 ? '#f56c6c' : '#67c23a'}">{{ r.avg_change_pct >= 0 ? '+' : '' }}{{ r.avg_change_pct }}%</span>
                        </div>
                        <div style="font-size:10px;color:#909399;">↑{{ r.up }}/↓{{ r.down }}</div>
                        <div v-if="i < cycleRecords.length - 1" style="position:absolute;right:-6px;top:50%;transform:translateY(-50%);color:#555;font-size:14px;">→</div>
                    </div>
                </div>
                <!-- 详细数据表 -->
                <el-table :data="cycleRecords" size="small" stripe style="width:100%;margin-bottom:12px;">
                    <el-table-column label="日期" width="80">
                        <template #default="{ row }">{{ row.date.slice(5) }}</template>
                    </el-table-column>
                    <el-table-column label="周期阶段" width="110">
                        <template #default="{ row }">
                            <el-tag :type="cycleTagTypeByStage(row.stage)" size="small">{{ row.stage_label }}</el-tag>
                        </template>
                    </el-table-column>
                    <el-table-column label="涨跌比" width="70">
                        <template #default="{ row }">{{ row.ratio }}</template>
                    </el-table-column>
                    <el-table-column label="均涨幅" width="80">
                        <template #default="{ row }">
                            <span :style="{color: row.avg_change_pct >= 0 ? '#f56c6c' : '#67c23a'}">{{ row.avg_change_pct >= 0 ? '+' : '' }}{{ row.avg_change_pct }}%</span>
                        </template>
                    </el-table-column>
                    <el-table-column label="↑上涨" width="60">
                        <template #default="{ row }">{{ row.up }}</template>
                    </el-table-column>
                    <el-table-column label="↓下跌" width="60">
                        <template #default="{ row }">{{ row.down }}</template>
                    </el-table-column>
                    <el-table-column label="涨停" width="60">
                        <template #default="{ row }">{{ row.limit_up }}</template>
                    </el-table-column>
                    <el-table-column label="跌停" width="60">
                        <template #default="{ row }">{{ row.limit_down }}</template>
                    </el-table-column>
                </el-table>
                <!-- 趋势判断 -->
                <div v-if="cycleAssessment.outlook" style="padding:10px 14px;border-radius:8px;border:1px solid #334;font-size:13px;line-height:1.6;"
                    :style="{ background: cycleAssessmentBg }">
                    <div style="margin-bottom:4px;"><b>🔮 趋势判断</b></div>
                    <div>涨跌比趋势：<b>{{ cycleTrendLabel(cycleAssessment.ratio_trend) }}</b> · 均涨幅趋势：<b>{{ cycleTrendLabel(cycleAssessment.avg_trend) }}</b> · 涨停数趋势：<b>{{ cycleTrendLabel(cycleAssessment.limit_trend) }}</b></div>
                    <div style="margin-top:4px;">操作策略：<b>{{ cycleOutlookText }}</b></div>
                </div>
            </template>
        </el-card>

        <template v-if="!noData">
            <el-row :gutter="16" style="margin-top: 16px;">
                <el-col :span="12">
                    <el-card shadow="hover">
                        <template #header><b>📈 涨幅TOP10</b></template>
                        <el-table :data="gainers" size="small" stripe style="width:100%">
                            <el-table-column label="名称" min-width="120">
                                <template #default="{ row }">
                                    <router-link :to="`/analysis?code=${row.code}`" style="color:#409eff;text-decoration:none;">{{ row.name }}</router-link>
                                </template>
                            </el-table-column>
                            <el-table-column label="代码" width="90">
                                <template #default="{ row }">
                                    <router-link :to="`/analysis?code=${row.code}`" style="color:#409eff;text-decoration:none;">{{ row.code }}</router-link>
                                </template>
                            </el-table-column>
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
                            <el-table-column label="名称" min-width="120">
                                <template #default="{ row }">
                                    <router-link :to="`/analysis?code=${row.code}`" style="color:#409eff;text-decoration:none;">{{ row.name }}</router-link>
                                </template>
                            </el-table-column>
                            <el-table-column label="代码" width="90">
                                <template #default="{ row }">
                                    <router-link :to="`/analysis?code=${row.code}`" style="color:#409eff;text-decoration:none;">{{ row.code }}</router-link>
                                </template>
                            </el-table-column>
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
                            <el-table-column label="名称" min-width="120">
                                <template #default="{ row }">
                                    <router-link :to="`/analysis?code=${row.code}`" style="color:#409eff;text-decoration:none;">{{ row.name }}</router-link>
                                </template>
                            </el-table-column>
                            <el-table-column label="代码" width="90">
                                <template #default="{ row }">
                                    <router-link :to="`/analysis?code=${row.code}`" style="color:#409eff;text-decoration:none;">{{ row.code }}</router-link>
                                </template>
                            </el-table-column>
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
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { getMarketOverview, getMarketDates, getSentimentCycle, getIndexHistory } from '../api/index.js'
import * as echarts from 'echarts'

const loading = ref(true)
const noData = ref(false)
const noDataMsg = ref('')
const dataDate = ref('')
const dataSession = ref('close')
const sessionsAvailable = ref(['close'])
const availableDates = ref([])
const sessionsByDate = ref({})

// 情绪周期
const cycleRecords = ref([])
const currentCycleLabel = ref('')
const currentCycleStage = ref('')
const cycleAssessment = ref({})
const cycleCollapsed = ref(false)
const cycleLoading = ref(false)

// 指数双轴图
const indexChartRef = ref(null)
let indexChartInstance = null
const indexData = ref({ hs300: [], zz500: [], ratio: [] })
const indexDays = ref(60)

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
        const params = {}
        if (dateStr) params.date = dateStr
        if (dataSession.value) params.session = dataSession.value
        const { data } = await getMarketOverview(params)
        if (data.status === 'no_data') {
            noData.value = true
            noDataMsg.value = data.message || '暂无行情数据'
            return
        }
        dataDate.value = data.date
        dataSession.value = data.session || 'close'
        sessionsAvailable.value = data.sessions_available || []
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

function onSessionChange(val) {
    loadData(dataDate.value)
}

// ===== 情绪周期 =====
const cycleTagType = computed(() => {
    const m = { ice: 'danger', ice_recovery: 'warning', launch: 'info', fermentation: 'success', climax: 'danger', recession: 'warning', transition: 'info' }
    return m[currentCycleStage.value] || 'info'
})

function cycleTagTypeByStage(stage) {
    const m = { ice: 'danger', ice_recovery: 'warning', launch: 'info', fermentation: 'success', climax: 'danger', recession: 'warning', transition: 'info' }
    return m[stage] || 'info'
}

function cycleBgColor(stage) {
    const m = { ice: 'rgba(245,108,108,0.15)', ice_recovery: 'rgba(230,162,60,0.15)', launch: 'rgba(64,158,255,0.15)', fermentation: 'rgba(103,194,58,0.15)', climax: 'rgba(245,108,108,0.25)', recession: 'rgba(230,162,60,0.15)', transition: 'rgba(144,147,153,0.1)' }
    return m[stage] || 'rgba(144,147,153,0.1)'
}

function cycleTrendLabel(t) {
    return { rising: '📈 上升', falling: '📉 下降', flat: '➡️ 持平' }[t] || t
}

const cycleAssessmentBg = computed(() => {
    const o = cycleAssessment.value?.outlook
    if (o === 'bullish' || o === 'cautious_bullish') return 'rgba(103,194,58,0.08)'
    if (o === 'defensive' || o === 'wait_for_signal') return 'rgba(245,108,108,0.08)'
    if (o === 'watch_for_reversal') return 'rgba(230,162,60,0.08)'
    return 'rgba(144,147,153,0.06)'
})

const cycleOutlookText = computed(() => {
    const m = {
        cautious_bullish: '谨慎看多 — 情绪处于高位，注意分歧加大，建议控制仓位参与主线',
        watch_for_reversal: '警惕回调 — 情绪从高位回落，注意退潮风险，建议减仓防御',
        wait_for_signal: '等待信号 — 市场冰点，不要抄底，等反弹确认后再入场',
        recovery_emerging: '冰点反弹初现 — 小仓位试盘，确认放量再加仓',
        bullish: '积极看多 — 情绪回暖，可适当加仓参与新题材',
        defensive: '防御为主 — 情绪走弱，减仓观望，等待冰点后的机会',
        neutral: '中性观望 — 方向不明，多看少动',
    }
    return m[cycleAssessment.value?.outlook] || '观望'
})

async function loadSentimentCycle() {
    cycleLoading.value = true
    try {
        const { data } = await getSentimentCycle(7)
        cycleRecords.value = data.records || []
        currentCycleLabel.value = data.current_label || ''
        currentCycleStage.value = data.current_stage || ''
        cycleAssessment.value = data.assessment || {}
    } catch (e) {
        console.error('情绪周期加载失败', e)
    } finally {
        cycleLoading.value = false
    }
}

// ===== 指数双轴图 =====
async function loadIndexHistory() {
    try {
        const { data } = await getIndexHistory(indexDays.value)
        indexData.value = { hs300: data.hs300 || [], zz500: data.zz500 || [], ratio: data.ratio || [] }
        await nextTick()
        renderIndexChart()
    } catch (e) {
        console.error('指数数据加载失败', e)
    }
}

function renderIndexChart() {
    if (!indexChartRef.value) return
    if (!indexChartInstance) {
        indexChartInstance = echarts.init(indexChartRef.value)
    }
    const hs300 = indexData.value.hs300
    const zz500 = indexData.value.zz500
    const ratio = indexData.value.ratio
    // 对齐日期
    const dates = [...new Set([...hs300.map(d => d.date), ...zz500.map(d => d.date)])].sort()
    const hsMap = Object.fromEntries(hs300.map(d => [d.date, d.close]))
    const zzMap = Object.fromEntries(zz500.map(d => [d.date, d.close]))
    const ratioMap = Object.fromEntries(ratio.map(d => [d.date, d.ratio]))
    const hsLine = dates.map(d => hsMap[d] ?? null)
    const zzLine = dates.map(d => zzMap[d] ?? null)
    const ratioLine = dates.map(d => ratioMap[d] ?? null)
    const option = {
        tooltip: {
            trigger: 'axis',
            formatter: function(params) {
                let s = `<b>${params[0].axisValue}</b><br/>`
                params.forEach(p => {
                    if (p.value != null) {
                        const v = p.seriesName === '沪深300/中证500' ? p.value.toFixed(4) : p.value.toFixed(2)
                        s += `${p.marker} ${p.seriesName}: ${v}<br/>`
                    }
                })
                return s
            }
        },
        legend: { data: ['沪深300', '中证500', '沪深300/中证500'], top: 12 },
        grid: { left: 60, right: 140, bottom: 40, top: 60 },
        xAxis: {
            type: 'category', data: dates, axisLabel: { rotate: 45, fontSize: 10 }
        },
        yAxis: [
            { type: 'value', name: '沪深300', nameTextStyle: { color: '#5470c6' } },
            { type: 'value', name: '中证500', nameTextStyle: { color: '#91cc75' } },
            { type: 'value', name: '比值', nameTextStyle: { color: '#fc8452', padding: [0, 0, 0, 60] },
              min: 'dataMin', max: 'dataMax', splitLine: { show: false },
              axisLabel: { formatter: v => v.toFixed(3) }, position: 'right', offset: 60 },
        ],
        series: [
            {
                name: '沪深300', type: 'line', data: hsLine,
                smooth: true, symbol: 'none',
                lineStyle: { width: 2 },
                yAxisIndex: 0,
            },
            {
                name: '中证500', type: 'line', data: zzLine,
                smooth: true, symbol: 'none',
                lineStyle: { width: 2 },
                yAxisIndex: 1,
            },
            {
                name: '沪深300/中证500', type: 'line', data: ratioLine,
                smooth: true, symbol: 'none',
                lineStyle: { width: 1.5, type: 'dashed' },
                itemStyle: { color: '#fc8452' },
                yAxisIndex: 2,
            },
        ],
    }
    indexChartInstance.setOption(option, true)
}

// resize on window resize
window.addEventListener('resize', () => {
    if (indexChartInstance) indexChartInstance.resize()
})

onMounted(async () => {
    // 先获取可选日期列表
    try {
        const { data } = await getMarketDates()
        availableDates.value = data.dates || []
        sessionsByDate.value = data.sessions_by_date || {}
        selectedDate.value = data.latest || null
        // 设置默认session
        if (data.latest_sessions?.length) {
            const s = data.latest_sessions
            dataSession.value = s.includes('close') ? 'close' : s[0]
            sessionsAvailable.value = s
        }
    } catch (e) {
        console.error(e)
    }
    // 加载最新数据
    await loadData(selectedDate.value)
    // 加载情绪周期
    await loadSentimentCycle()
    // 加载指数历史
    await loadIndexHistory()
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
