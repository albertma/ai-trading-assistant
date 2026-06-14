<template>
    <div>
        <!-- 控制栏 -->
        <el-card shadow="never" style="margin-bottom:12px;">
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
                <b style="font-size:16px;">📈 策略回测</b>

                <!-- 预设策略标签 -->
                <el-dropdown trigger="click" size="small" style="margin-left:8px;">
                    <el-button size="small">
                        预设策略 <el-icon><ArrowDown /></el-icon>
                    </el-button>
                    <template #dropdown>
                        <el-dropdown-menu>
                            <el-dropdown-item v-for="p in presets" :key="p.name"
                                @click="loadPreset(p)">
                                {{ p.label }}
                            </el-dropdown-item>
                        </el-dropdown-menu>
                    </template>
                </el-dropdown>

                <el-divider direction="vertical" />

                <!-- 买入信号 -->
                <span style="font-size:12px;color:#909399;">买入:</span>
                <el-select v-model="buySignal" size="small" style="width:170px;" clearable>
                    <el-option v-for="e in entries" :key="e.name" :label="e.label" :value="e.name" />
                </el-select>

                <!-- 卖出信号 -->
                <span style="font-size:12px;color:#909399;">卖出:</span>
                <el-select v-model="sellSignal" size="small" style="width:170px;" clearable>
                    <el-option v-for="e in exits" :key="e.name" :label="e.label" :value="e.name" />
                </el-select>

                <!-- 止损% -->
                <span style="font-size:12px;color:#909399;">止损:</span>
                <el-input-number v-model="slPct" :min="0" :max="30" :step="1" size="small"
                    style="width:90px;" />

                <el-button size="small" type="primary" @click="runBacktest" :loading="running">
                    ▶ 跑回测
                </el-button>

                <div style="flex:1"></div>
                <el-tag type="info">共 {{ summary.total_trades || 0 }} 笔交易</el-tag>
            </div>
        </el-card>

        <!-- 汇总卡片 -->
        <el-row :gutter="12" style="margin-bottom:12px;">
            <el-col :span="4" v-for="card in summaryCards" :key="card.label">
                <el-card shadow="hover" style="text-align:center;padding:8px;">
                    <div style="font-size:11px;color:#909399;">{{ card.label }}</div>
                    <div :style="{ fontSize:'20px', fontWeight:'bold', color: card.color }">{{ card.value }}</div>
                </el-card>
            </el-col>
        </el-row>

        <!-- 策略对比表 -->
        <el-card shadow="never" style="margin-bottom:12px;">
            <template #header><b>📊 策略对比</b></template>
            <el-table :data="strategyComparison" size="small" style="width:100%;">
                <el-table-column label="策略组合" prop="name" min-width="200" />
                <el-table-column label="买入→卖出" prop="detail" min-width="180">
                    <template #default="{ row }">
                        <span style="font-size:11px;color:#909399;">{{ row.detail }}</span>
                    </template>
                </el-table-column>
                <el-table-column label="交易次数" prop="trades" width="70" align="center" />
                <el-table-column label="胜率" prop="winRate" width="70" align="center">
                    <template #default="{ row }"><span :style="{color:row.winRate>=40?'#67c23a':'#e6a23c'}">{{ row.winRate }}%</span></template>
                </el-table-column>
                <el-table-column label="盈亏比" prop="profitFactor" width="70" align="center">
                    <template #default="{ row }"><span :style="{color:row.profitFactor>=1?'#67c23a':'#e6a23c'}">{{ row.profitFactor }}:1</span></template>
                </el-table-column>
                <el-table-column label="总收益" prop="totalPnl" width="90" align="center">
                    <template #default="{ row }"><span :style="{color:row.totalPnl>=0?'#67c23a':'#f56c6c'}">¥{{ row.totalPnl }}</span></template>
                </el-table-column>
                <el-table-column label="平均收益率" prop="avgReturn" width="80" align="center">
                    <template #default="{ row }"><span :style="{color:row.avgReturn>=0?'#67c23a':'#f56c6c'}">{{ row.avgReturn }}%</span></template>
                </el-table-column>
                <el-table-column label="平均持有" prop="avgHolding" width="70" align="center" />
                <el-table-column label="最大回撤" prop="maxDD" width="80" align="center">
                    <template #default="{ row }"><span style="color:#f56c6c;">¥{{ row.maxDD }}</span></template>
                </el-table-column>
                <el-table-column label="操作" width="60">
                    <template #default="{ row }">
                        <el-button size="mini" link @click="viewTrades(row.strategy)">详情</el-button>
                    </template>
                </el-table-column>
            </el-table>
        </el-card>

        <!-- 交易明细 -->
        <el-card shadow="never">
            <template #header>
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <b>📋 交易明细</b>
                    <el-tag v-if="selectedStrategy" size="small">{{ selectedStrategy }}</el-tag>
                </div>
            </template>
            <el-table :data="tradeList" size="small" style="width:100%;" max-height="500" v-loading="loadingTrades">
                <el-table-column label="股票" width="70">
                    <template #default="{ row }">
                        <el-button link size="mini" @click="showKline(row)" style="font-weight:bold;">
                            {{ row.code }}
                        </el-button>
                    </template>
                </el-table-column>
                <el-table-column label="方向" width="50" align="center">
                    <template #default="{ row }">
                        <span :style="{color:row.direction==='long'?'#f56c6c':'#67c23a'}">{{ row.direction==='long'?'📈':'📉' }}</span>
                    </template>
                </el-table-column>
                <el-table-column label="入场" prop="entry_date" width="85" />
                <el-table-column label="入场价" prop="entry_price" width="70" align="center" />
                <el-table-column label="退出" prop="exit_date" width="85" />
                <el-table-column label="退出价" prop="exit_price" width="70" align="center" />
                <el-table-column label="退出原因" prop="exit_reason" width="100" />
                <el-table-column label="收益率" width="65" align="center">
                    <template #default="{ row }">
                        <span :style="{color:row.return_pct>=0?'#67c23a':'#f56c6c'}">{{ row.return_pct >=0?'+':'' }}{{ row.return_pct }}%</span>
                    </template>
                </el-table-column>
                <el-table-column label="持有" prop="holding_days" width="50" align="center" />
                <el-table-column label="信号" prop="signal_detail" min-width="130" />
            </el-table>
        </el-card>

        <!-- K线图表对话框 -->
        <el-dialog v-model="klineDialogVisible" :title="klineTitle" width="900px" top="5vh"
            @closed="disposeKlineChart">
            <div ref="klineChartRef" style="width:100%;height:520px;"></div>
        </el-dialog>
    </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import axios from 'axios'

const API = '/api/v1'
const running = ref(false)
const loadingTrades = ref(false)
const summary = ref({})
const tradeList = ref([])
const selectedStrategy = ref('')

// 信号选项（从后端加载）
const entries = ref([])
const exits = ref([])
const presets = ref([])

// 当前选择
const buySignal = ref('kline_macd_elite')
const sellSignal = ref('macd_death')
const slPct = ref(0)

const batchResults = ref([])

// 加载信号列表
async function loadSignals() {
    try {
        const r = await (await fetch(`${API}/strategy-backtest/signals`)).json()
        entries.value = r.entries || []
        exits.value = r.exits || []
        presets.value = r.presets || []
    } catch {}
}

// 加载预设策略
function loadPreset(preset) {
    buySignal.value = preset.entry
    sellSignal.value = preset.exit
    slPct.value = preset.default_sl
    ElMessage.info(`已加载: ${preset.label}`)
}

// 获取某个组合的显示名
function getComboLabel(strategy) {
    // 预设策略
    const preset = presets.value.find(p => p.name === strategy)
    if (preset) return preset.label
    // 组合格式: entry+exit
    const [entry, exit] = strategy.split('+')
    const eLabel = entries.value.find(e => e.name === entry)?.label || entry
    const xLabel = exits.value.find(e => e.name === exit)?.label || exit
    return `${eLabel} → ${xLabel}`
}

// 获取买入/卖出详情
function getComboDetail(strategy) {
    const [entry, exit] = strategy.split('+')
    const eLabel = entries.value.find(e => e.name === entry)?.label || entry
    const xLabel = exits.value.find(e => e.name === exit)?.label || exit
    return `${eLabel} → ${xLabel}`
}

const summaryCards = computed(() => [
    { label: '交易次数', value: summary.value.total_trades ?? 0, color: '#409eff' },
    { label: '胜率', value: (summary.value.win_rate ?? 0) + '%', color: (summary.value.win_rate ?? 0) >= 40 ? '#67c23a' : '#e6a23c' },
    { label: '盈亏比', value: (summary.value.profit_factor ?? 0) + ':1', color: (summary.value.profit_factor ?? 0) >= 1 ? '#67c23a' : '#e6a23c' },
    { label: '总收益', value: '¥' + (summary.value.total_pnl ?? 0).toFixed(2), color: (summary.value.total_pnl ?? 0) >= 0 ? '#67c23a' : '#f56c6c' },
    { label: '平均收益率', value: (summary.value.avg_return ?? 0) + '%', color: (summary.value.avg_return ?? 0) >= 0 ? '#67c23a' : '#f56c6c' },
    { label: '平均持有', value: (summary.value.avg_holding_days ?? 0) + '天', color: '#909399' },
    { label: '最大回撤', value: '¥' + (summary.value.max_drawdown ?? 0).toFixed(2), color: '#f56c6c' },
    { label: '胜/负', value: (summary.value.wins ?? 0) + '胜 / ' + (summary.value.losses ?? 0) + '负', color: '#909399' },
])

const strategyComparison = computed(() => {
    if (!batchResults.value.length) return []
    // 每种组合只显示最新一次
    const latest = {}
    for (const b of batchResults.value) {
        if (!latest[b.strategy] || b.created_at > latest[b.strategy].created_at) {
            latest[b.strategy] = b
        }
    }
    return Object.values(latest).map(b => ({
        strategy: b.strategy,
        name: getComboLabel(b.strategy),
        detail: getComboDetail(b.strategy),
        trades: b.trade_count || 0,
        winRate: b.win_rate != null ? b.win_rate : '-',
        profitFactor: b.profit_factor != null ? b.profit_factor : '-',
        totalPnl: b.total_pnl?.toFixed(2) || 0,
        avgReturn: b.avg_return != null ? b.avg_return : '-',
        avgHolding: b.avg_holding_days != null ? b.avg_holding_days + '天' : '-',
        maxDD: b.max_drawdown != null ? b.max_drawdown.toFixed(2) : '-',
    }))
})

async function loadBatches() {
    try {
        const r = await (await fetch(`${API}/strategy-backtest/batches`)).json()
        batchResults.value = r.batches || []
    } catch {}
}

async function runBacktest() {
    if (!buySignal.value) { ElMessage.warning('请选择买入信号'); return }
    if (!sellSignal.value) { ElMessage.warning('请选择卖出信号'); return }

    running.value = true
    try {
        // 取观察池
        const wResp = await (await fetch(`${API}/watchlist`)).json()
        const items = wResp.watchlist || wResp.items || wResp.data || []
        const codes = items
            .filter(i => /^[0-36]/.test(i.code || '') && (i.code || '').length === 6)
            .map(i => i.code)
            .join(',')

        if (!codes) { ElMessage.warning('观察池无A股'); return }

        const resp = await fetch(`${API}/strategy-backtest/run-multi` +
            `?codes=${encodeURIComponent(codes)}` +
            `&entry_signal=${buySignal.value}` +
            `&exit_signal=${sellSignal.value}` +
            `&sl_pct=${slPct.value}`, { method: 'POST' })
        const data = await resp.json()
        summary.value = data
        ElMessage.success(`回测完成: ${data.total_trades || 0} 笔交易`)
        await loadBatches()
        // 显示当前组合的交易明细
        await loadTrades(comboName(buySignal.value, sellSignal.value))
    } catch { ElMessage.error('回测失败') }
    finally { running.value = false }
}

function comboName(buy, sell) {
    return `${buy}+${sell}`
}

async function loadTrades(strategy) {
    loadingTrades.value = true
    selectedStrategy.value = strategy
    try {
        const r = await (await fetch(`${API}/strategy-backtest/results?strategy=${encodeURIComponent(strategy)}&limit=200`)).json()
        tradeList.value = r.results || []
    } catch {}
    finally { loadingTrades.value = false }
}

function viewTrades(strategy) {
    loadTrades(strategy)
}

// ─── K线图表 ───
const klineDialogVisible = ref(false)
const klineTitle = ref('')
const klineChartRef = ref(null)
let klineChartInstance = null

function calcSMA(data, period) {
    const result = []
    for (let i = 0; i < data.length; i++) {
        if (i < period - 1) { result.push(NaN); continue }
        let sum = 0
        for (let j = i - period + 1; j <= i; j++) sum += data[j]
        result.push(+(sum / period).toFixed(2))
    }
    return result
}
function calcEMA(data, period) {
    const k = 2 / (period + 1)
    const result = []
    let ema = data[0]
    for (let i = 0; i < data.length; i++) {
        ema = i === 0 ? data[i] : data[i] * k + ema * (1 - k)
        result.push(+(ema).toFixed(4))
    }
    return result
}
function calcMACD(close) {
    const ema12 = calcEMA(close, 12)
    const ema26 = calcEMA(close, 26)
    const dif = ema12.map((v, i) => +(v - ema26[i]).toFixed(4))
    const dea = []
    let ema_dea = dif[0]
    const k_dea = 2 / (9 + 1)
    for (let i = 0; i < dif.length; i++) {
        ema_dea = i === 0 ? dif[i] : dif[i] * k_dea + ema_dea * (1 - k_dea)
        dea.push(+(ema_dea).toFixed(4))
    }
    const macd = dif.map((d, i) => +((d - dea[i]) * 2).toFixed(4))
    return { dif, dea, macd }
}

async function showKline(row) {
    const code = row.code
    klineTitle.value = `${code} ${row.signal_detail || ''}`
    klineDialogVisible.value = true
    await nextTick()

    try {
        const resp = await axios.get(`/api/v1/watchlist/local-kline/${code}?days=250`, { timeout: 15000 })
        const recs = (resp.data.records || []).slice(-150)
        if (recs.length < 30) { ElMessage.warning('K线数据不足'); return }

        renderKlineChart(code, recs, row)
    } catch {
        ElMessage.error('加载K线失败')
    }
}

function renderKlineChart(code, recs, currentTrade) {
    const el = klineChartRef.value
    if (!el) return
    if (klineChartInstance) { klineChartInstance.dispose(); klineChartInstance = null }

    const closes = recs.map(r => r.close)
    const dates = recs.map(r => r.date.slice(5, 10))
    const ma5 = calcSMA(closes, 5)
    const ma10 = calcSMA(closes, 10)
    const ma30 = calcSMA(closes, 30)
    const ma60 = calcSMA(closes, 60)
    const ma200 = calcSMA(closes, 200)
    const { dif, dea, macd } = calcMACD(closes)

    // 买入/卖出标记
    const markLines = []
    const tradeInFilter = row => row.code === currentTrade.code
    const sameStockTrades = tradeList.value.filter(t => t.code === code)

    sameStockTrades.forEach(t => {
        const entryIdx = recs.findIndex(r => r.date === t.entry_date)
        const exitIdx = recs.findIndex(r => r.date === t.exit_date)
        if (entryIdx >= 0) {
            markLines.push({
                xAxis: dates[entryIdx],
                label: { formatter: `买入 ${t.entry_price}`, color: '#f56c6c', fontSize: 10 },
                lineStyle: { color: '#f56c6c', type: 'solid', width: 2 },
            })
        }
        if (exitIdx >= 0) {
            const color = (t.return_pct || 0) >= 0 ? '#67c23a' : '#909399'
            markLines.push({
                xAxis: dates[exitIdx],
                label: { formatter: `卖出 ${t.exit_price}`, color, fontSize: 10 },
                lineStyle: { color, type: 'dashed', width: 1.5 },
            })
        }
    })

    const ohlc = recs.map(r => [r.open, r.close, r.low, r.high])
    const volumes = recs.map(r => r.volume)

    klineChartInstance = echarts.init(el)
    const option = {
        backgroundColor: '#1e1e3a',
        animation: false,
        grid: [
            { left: '8%', right: '3%', top: '5%', height: '55%' },
            { left: '8%', right: '3%', top: '68%', height: '12%' },
            { left: '8%', right: '3%', top: '84%', height: '12%' },
        ],
        xAxis: [
            { type: 'category', data: dates, gridIndex: 0, axisLabel: { show: true, fontSize: 9, color: '#aaa' } },
            { type: 'category', data: dates, gridIndex: 1, axisLabel: { show: false } },
            { type: 'category', data: dates, gridIndex: 2, axisLabel: { show: false } },
        ],
        yAxis: [
            { scale: true, gridIndex: 0, splitLine: { lineStyle: { color: '#333' } }, axisLabel: { color: '#aaa' } },
            { scale: true, gridIndex: 1, splitLine: { show: false }, axisLabel: { color: '#aaa' } },
            { scale: true, gridIndex: 2, splitLine: { show: false }, axisLabel: { color: '#aaa' } },
        ],
        dataZoom: [
            { type: 'inside', xAxisIndex: [0, 1, 2], start: Math.max(0, 100 - 60), end: 100 },
            { type: 'slider', xAxisIndex: [0, 1, 2], bottom: 0, height: 12, borderColor: '#444',
                backgroundColor: '#2a2a4a', fillerColor: '#3a3a6a' },
        ],
        tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
        series: [
            {
                name: 'K线', type: 'candlestick', xAxisIndex: 0, yAxisIndex: 0,
                data: ohlc,
                itemStyle: { color: '#f56c6c', color0: '#67c23a', borderColor: '#f56c6c', borderColor0: '#67c23a' },
                markLine: {
                    silent: true,
                    symbol: 'none',
                    data: markLines,
                },
            },
            {
                name: 'MA5', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
                data: ma5, smooth: true, symbol: 'none', lineStyle: { width: 1, color: '#ff9800' },
            },
            {
                name: 'MA10', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
                data: ma10, smooth: true, symbol: 'none', lineStyle: { width: 1, color: '#2196f3' },
            },
            {
                name: 'MA30', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
                data: ma30, smooth: true, symbol: 'none', lineStyle: { width: 1, color: '#9c27b0' },
            },
            {
                name: 'MA60', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
                data: ma60, smooth: true, symbol: 'none', lineStyle: { width: 1, color: '#ff4081' },
            },
            {
                name: 'MA200', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
                data: ma200, smooth: true, symbol: 'none', lineStyle: { width: 1, color: '#ffeb3b', type: 'dashed' },
            },
            {
                name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1,
                data: volumes.map((v, i) => ({
                    value: v,
                    itemStyle: { color: ohlc[i][0] <= ohlc[i][1] ? '#f56c6c' : '#67c23a', opacity: 0.4 }
                })),
            },
            {
                name: 'DIF', type: 'line', xAxisIndex: 2, yAxisIndex: 2,
                data: dif, smooth: true, symbol: 'none', lineStyle: { width: 1.2, color: '#fff' },
            },
            {
                name: 'DEA', type: 'line', xAxisIndex: 2, yAxisIndex: 2,
                data: dea, smooth: true, symbol: 'none', lineStyle: { width: 1.2, color: '#ff9800' },
            },
            {
                name: 'MACD', type: 'bar', xAxisIndex: 2, yAxisIndex: 2,
                data: macd.map(v => ({
                    value: +v.toFixed(4),
                    itemStyle: { color: v >= 0 ? '#f56c6c' : '#67c23a', opacity: 0.5 }
                })),
            },
        ],
    }
    klineChartInstance.setOption(option)
    klineChartInstance.on('click', function () {})
}

function disposeKlineChart() {
    if (klineChartInstance) { klineChartInstance.dispose(); klineChartInstance = null }
}

onMounted(async () => {
    await loadSignals()
    await loadBatches()
})
</script>
