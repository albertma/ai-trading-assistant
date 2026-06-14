<template>
    <div class="ai-driven-page">
        <div class="page-header">
            <h1>🤖 AI研报</h1>
            <div class="header-actions">
                <el-select v-model="scanIndex" size="small" style="width:120px;margin-right:8px" @change="switchIndex">
                    <el-option label="📊 全部指数" value="" />
                    <el-option label="沪深300" value="hs300" />
                    <el-option label="中证500" value="csi500" />
                    <el-option label="科创50" value="star50" />
                </el-select>
                <el-select v-model="scanType" size="small" style="width:100px;margin-right:8px" @change="switchType" v-if="scanIndex">
                    <el-option label="午盘" value="noon" />
                    <el-option label="收盘" value="close" />
                </el-select>
                <el-date-picker v-model="browseDate" type="date" placeholder="浏览历史" size="small"
                    style="width:140px;margin-right:8px" :disabled-date="disabledDate"
                    @change="loadByDate" value-format="YYYY-MM-DD" />
                <el-button type="primary" @click="triggerScan" :loading="scanning">
                    <el-icon><Refresh /></el-icon> 手动扫描
                </el-button>
            </div>
        </div>

        <!-- 今日概览（显示所有指数） -->
        <el-card v-if="todaySummary.length" class="overview-card" shadow="never">
            <h3 style="margin:0 0 12px;color:#e0e0e0;font-size:15px">📋 今日数据概览</h3>
            <div class="summary-grid">
                <div v-for="item in todaySummary" :key="item.index_code + item.scan_type"
                     class="summary-card" :class="item.index_code"
                     @click="showIndexDetail(item)">
                    <div class="sc-name">{{ item.index_name }}</div>
                    <div class="sc-type">{{ item.scan_type === 'close' ? '收盘' : '午盘' }}</div>
                    <div class="sc-count">{{ item.signal_count }}<span class="sc-unit">个信号</span></div>
                    <div class="sc-meta">扫描{{ item.total_scanned }}只 · 最高{{ item.max_score }}分</div>
                    <div class="sc-time">{{ item.generated_at }}</div>
                </div>
            </div>
        </el-card>

        <!-- 当前指数详情 -->
        <div v-if="scanIndex">
            <!-- 扫描概览 -->
            <el-card v-if="report" class="overview-card detail-card" shadow="never">
                <div class="overview-grid">
                    <div class="overview-item">
                        <div class="ov-label">扫描日期</div>
                        <div class="ov-value">{{ report.date }}</div>
                    </div>
                    <div class="overview-item">
                        <div class="ov-label">扫描范围</div>
                        <div class="ov-value">{{ report.index_name || '沪深300' }}</div>
                    </div>
                    <div class="overview-item">
                        <div class="ov-label">扫描类型</div>
                        <div class="ov-value">{{ report.scan_type === 'close' ? '收盘' : '午盘' }}</div>
                    </div>
                    <div class="overview-item">
                        <div class="ov-label">扫描数量</div>
                        <div class="ov-value">{{ report.total_scanned }} 只</div>
                    </div>
                    <div class="overview-item">
                        <div class="ov-label">信号数量</div>
                        <div class="ov-value signal-count">{{ report.signal_count }} 只</div>
                    </div>
                    <div class="overview-item full-width">
                        <div class="ov-label">市场摘要</div>
                        <div class="ov-value">{{ report.summary }}</div>
                    </div>
                </div>
            </el-card>

            <div v-else-if="!loading" class="empty-state">
                <el-empty :description="`暂无${scanIndex === 'hs300' ? '沪深300' : scanIndex === 'csi500' ? '中证500' : '科创50'}${scanType === 'close' ? '收盘' : '午盘'}记录`">
                    <el-button type="primary" size="small" @click="triggerScan">手动扫描</el-button>
                </el-empty>
            </div>
            <div v-else class="empty-state">
                <el-skeleton :rows="4" animated />
            </div>
        </div>

        <!-- 信号列表 -->
        <div v-if="report && report.top_signals && report.top_signals.length" class="signals-section">
            <h2>⭐ 精选信号 · {{ report.top_signals.length }}只</h2>
            <div class="signal-list">
                <el-card v-for="(s, i) in report.top_signals" :key="s.code" class="signal-card" shadow="never">
                    <div class="signal-header" @click="toggleExpand(i)">
                        <div class="signal-rank">#{{ i + 1 }}</div>
                        <div class="signal-meta">
                            <div class="signal-code">{{ s.code }}</div>
                            <div class="signal-name">{{ s.name }}</div>
                        </div>
                        <div class="signal-score" :class="scoreClass(s.score)">
                            {{ s.score }}
                        </div>
                        <div class="signal-change" :class="s.change >= 0 ? 'up' : 'down'">
                            {{ s.change >= 0 ? '+' : '' }}{{ s.change }}%
                        </div>
                        <div class="signal-confidence">
                            <el-tag :type="tagType(s.score)" size="small" effect="dark">
                                {{ s.confidence }}
                            </el-tag>
                        </div>
                        <div class="signal-expand">
                            <el-icon><ArrowDown v-if="expanded !== i" /><ArrowUp v-else /></el-icon>
                        </div>
                    </div>

                    <el-collapse-transition>
                        <div v-show="expanded === i" class="signal-detail">
                            <el-divider style="margin:8px 0" />

                            <!-- 评分雷达 -->
                            <div class="score-bars">
                                <div class="bar-item">
                                    <span class="bar-label">技术面</span>
                                    <el-progress :percentage="s.technical_score" :color="scoreColor(s.technical_score)" :stroke-width="12" />
                                </div>
                                <div class="bar-item">
                                    <span class="bar-label">基本面</span>
                                    <el-progress :percentage="s.fundamental_score" :color="scoreColor(s.fundamental_score)" :stroke-width="12" />
                                </div>
                                <div class="bar-item">
                                    <span class="bar-label">风控分</span>
                                    <el-progress :percentage="s.risk_score" :color="scoreColor(s.risk_score)" :stroke-width="12" />
                                </div>
                            </div>

                            <!-- 摘要 -->
                            <div class="detail-summary">{{ s.summary }}</div>

                            <!-- 技术面信号 -->
                            <div v-if="s.technical_signals && s.technical_signals.length" class="detail-section">
                                <h4>📈 技术面信号 ({{ s.technical_signals.length }})</h4>
                                <div class="tag-list">
                                    <el-tag v-for="t in s.technical_signals" :key="t.type" size="small"
                                        :type="t.strength >= 80 ? 'danger' : t.strength >= 60 ? 'warning' : 'info'"
                                        effect="plain">
                                        {{ t.type }} ({{ t.strength }})
                                    </el-tag>
                                </div>
                            </div>

                            <!-- 风险 -->
                            <div v-if="s.risk_factors && s.risk_factors.length" class="detail-section">
                                <h4>⚠️ 风险因素 ({{ s.risk_factors.length }})</h4>
                                <div class="tag-list">
                                    <el-tag v-for="r in s.risk_factors" :key="r.name" size="small" type="danger" effect="plain">
                                        {{ r.name }} ({{ r.severity }})
                                    </el-tag>
                                </div>
                            </div>

                            <!-- 入场建议 -->
                            <div v-if="s.score >= 62" class="detail-section trade-suggestion">
                                <h4>💵 交易建议</h4>
                                <div class="trade-grid">
                                    <div class="trade-item"><label>入场价</label><span>{{ s.price }}</span></div>
                                    <div class="trade-item"><label>止损</label><span class="down">{{ s.stop_loss }}</span></div>
                                    <div class="trade-item"><label>止盈</label><span class="up">{{ s.take_profit }}</span></div>
                                    <div class="trade-item"><label>仓位</label><span>{{ s.position }}</span></div>
                                </div>
                            </div>

                            <!-- K线图表 -->
                            <div v-if="klineLoaded(s.code)" class="detail-section">
                                <h4>📉 K线分析 (120日)</h4>
                                <div :ref="el => klineRefs[s.code] = el" class="kline-chart"></div>
                            </div>
                            <div v-else-if="klineLoading(s.code)" class="detail-section" style="text-align:center;padding:12px">
                                <el-skeleton :rows="2" animated />
                            </div>
                        </div>
                    </el-collapse-transition>
                </el-card>
            </div>
        </div>

        <!-- 风险预警 -->
        <el-card v-if="report && report.risk_warnings && report.risk_warnings.length" class="risk-card" shadow="never">
            <h2>⚠️ 风险预警 · {{ report.risk_warnings.length }}条</h2>
            <div v-for="w in report.risk_warnings" :key="w.code + w.risk" class="risk-item">
                <el-tag size="small" :type="w.severity >= 70 ? 'danger' : 'warning'" effect="dark">
                    {{ w.code }} {{ w.name }}
                </el-tag>
                <span class="risk-desc">{{ w.risk }}: {{ w.desc }}</span>
            </div>
        </el-card>

        <!-- 底部 -->
        <div v-if="report" class="report-footer">
            <span v-if="report.db_id">DB #{{ report.db_id }} | </span>
            报告: {{ report.report_path }} | 生成: {{ report.generated_at }}
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import axios from 'axios'
import { Refresh, ArrowDown, ArrowUp } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'

const API = '/api/v1/ai-driven'

const report = ref(null)
const scanning = ref(false)
const loading = ref(true)
const scanType = ref('close')
const scanIndex = ref('')
const browseDate = ref(null)
const expanded = ref(-1)
const todaySummary = ref([])
const klineData = ref({})
const klineLoadingStates = ref({})
const klineRefs = ref({})
let charts = {}

function klineLoaded(code) {
    return !!klineData.value[code]
}
function klineLoading(code) {
    return !!klineLoadingStates.value[code]
}

function toggleExpand(i) {
    expanded.value = expanded.value === i ? -1 : i
    if (expanded.value === i) {
        const s = report.value?.top_signals?.[i]
        if (s && !klineData.value[s.code] && !klineLoadingStates.value[s.code]) {
            loadKline(s.code, i)
        }
    }
}

function scoreClass(score) {
    if (score >= 82) return 'score-excellent'
    if (score >= 73) return 'score-good'
    if (score >= 62) return 'score-watch'
    return 'score-neutral'
}

function scoreColor(s) {
    if (s >= 80) return '#67c23a'
    if (s >= 60) return '#e6a23c'
    return '#909399'
}

function tagType(score) {
    if (score >= 82) return 'danger'
    if (score >= 73) return 'warning'
    if (score >= 62) return 'success'
    return 'info'
}

// ─── K线图表 ───
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
    // DIF = EMA12 - EMA26 (标准MACD线，围绕0轴波动)
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

async function loadKline(code, idx) {
    klineLoadingStates.value[code] = true
    try {
        const { data } = await axios.get(`/api/v1/watchlist/local-kline/${code}?days=200`, { timeout: 15000 })
        const recs = (data.records || []).slice(-120)
        if (recs.length < 20) {
            klineLoadingStates.value[code] = false
            return
        }
        klineData.value[code] = recs
        await nextTick()
        renderKlineChart(code, recs)
    } catch { /* ignore */ }
    klineLoadingStates.value[code] = false
}

function renderKlineChart(code, recs) {
    const el = klineRefs.value[code]
    if (!el) return
    // 清理旧实例
    if (charts[code]) { charts[code].dispose(); delete charts[code] }

    const closes = recs.map(r => r.close)
    const dates = recs.map(r => r.date.slice(5, 10))
    const ma5 = calcSMA(closes, 5)
    const ma10 = calcSMA(closes, 10)
    const ma20 = calcSMA(closes, 20)
    const ma60 = calcSMA(closes, 60)
    const { dif, dea, macd } = calcMACD(closes)
    const macdBarData = macd.map(v => ({ value: +v.toFixed(4), itemStyle: { color: v >= 0 ? '#f56c6c' : '#67c23a' } }))

    const idx = (v) => ({ xAxisIndex: v, yAxisIndex: v })
    const option = {
        backgroundColor: '#1e1e3a',
        animation: false,
        grid: [
            { left: '8%', right: '4%', top: '4%', height: '50%' },
            { left: '8%', right: '4%', top: '60%', height: '14%' },
            { left: '8%', right: '4%', top: '78%', height: '16%' },
        ],
        xAxis: [
            { type: 'category', data: dates, gridIndex: 0, axisLabel: { color: '#888', fontSize: 9, interval: 15 }, axisLine: { lineStyle: { color: '#334' } } },
            { type: 'category', data: dates, gridIndex: 1, axisLabel: { show: false }, axisLine: { lineStyle: { color: '#334' } } },
            { type: 'category', data: dates, gridIndex: 2, axisLabel: { show: false }, axisLine: { lineStyle: { color: '#334' } } },
        ],
        yAxis: [
            { type: 'value', gridIndex: 0, scale: true, splitLine: { lineStyle: { color: '#2a2a3e' } }, axisLabel: { color: '#888', fontSize: 9 } },
            { type: 'value', gridIndex: 1, scale: true, splitLine: { show: false }, axisLabel: { color: '#888', fontSize: 9 } },
            { type: 'value', gridIndex: 2, scale: true, splitLine: { show: false }, axisLabel: { color: '#888', fontSize: 9 } },
        ],
        series: [
            { name: 'K线', type: 'candlestick', ...idx(0), data: recs.map(r => [+r.open, +r.close, +r.low, +r.high]),
                itemStyle: { color: '#f56c6c', color0: '#67c23a', borderColor: '#f56c6c', borderColor0: '#67c23a' } },
            { name: '成交量', type: 'bar', ...idx(1), data: recs.map(r => ({ value: r.volume, itemStyle: { color: r.close >= r.open ? '#f56c6c' : '#67c23a' } })) },
            { name: 'MA5', type: 'line', ...idx(0), data: ma5, smooth: true, symbol: 'none', lineStyle: { width: 1.5, color: '#e6a23c' } },
            { name: 'MA10', type: 'line', ...idx(0), data: ma10, smooth: true, symbol: 'none', lineStyle: { width: 1.5, color: '#409eff' } },
            { name: 'MA20', type: 'line', ...idx(0), data: ma20, smooth: true, symbol: 'none', lineStyle: { width: 1.5, color: '#b37feb' } },
            { name: 'MA60', type: 'line', ...idx(0), data: ma60, smooth: true, symbol: 'none', lineStyle: { width: 1.5, color: '#5cdbd3' } },
            { name: 'MACD', type: 'bar', ...idx(2), data: macdBarData },
            { name: 'DIF', type: 'line', ...idx(2), data: dif, smooth: true, symbol: 'none', lineStyle: { width: 1, color: '#fff' } },
            { name: 'DEA', type: 'line', ...idx(2), data: dea, smooth: true, symbol: 'none', lineStyle: { width: 1, color: '#ffd666' } },
        ],
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'cross' },
            backgroundColor: 'rgba(30,30,58,0.9)',
            borderColor: '#409eff',
            textStyle: { color: '#e0e0e0', fontSize: 11 },
        },
    }
    charts[code] = echarts.init(el)
    charts[code].setOption(option)
    // 窗口resize自适应
    const resizeHandler = () => charts[code]?.resize()
    window.addEventListener('resize', resizeHandler)
}

function disabledDate(time) {
    return time.getTime() > Date.now()
}

async function switchIndex(idx) {
    scanIndex.value = idx
    if (idx) {
        await loadActiveIndex()
    }
}

function switchType() {
    if (scanIndex.value) {
        loadActiveIndex()
    }
}

function showIndexDetail(item) {
    scanIndex.value = item.index_code
    scanType.value = item.scan_type
    loadActiveIndex()
}

async function loadActiveIndex() {
    loading.value = true
    browseDate.value = null
    try {
        const { data } = await axios.get(`${API}/scan/latest`, {
            params: { index: scanIndex.value, scan_type: scanType.value },
            timeout: 10000,
        })
        if (data.success) {
            report.value = data
        } else {
            // 当前类型无数据，尝试另一个类型
            const fallback = scanType.value === 'close' ? 'noon' : 'close'
            const { data: fb } = await axios.get(`${API}/scan/latest`, {
                params: { index: scanIndex.value, scan_type: fallback },
                timeout: 10000,
            })
            if (fb.success) {
                scanType.value = fallback
                report.value = fb
            } else {
                report.value = null
            }
        }
    } catch {
        report.value = null
    } finally {
        loading.value = false
    }
}

async function fetchTodaySummary() {
    try {
        const { data } = await axios.get(`${API}/scan/today-summary`, { timeout: 10000 })
        if (data.success && data.records.length) {
            todaySummary.value = data.records
        }
    } catch { /* ignore */ }
}

async function loadByDate(dateStr) {
    if (!dateStr) return
    loading.value = true
    try {
        const { data } = await axios.get(`${API}/scan/by-date`, {
            params: { date_str: dateStr, index: scanIndex.value, scan_type: scanType.value },
            timeout: 10000,
        })
        if (data.success) {
            report.value = data
            expanded.value = -1
        } else {
            ElMessage.info(data.error || '该日期暂无记录')
            report.value = null
        }
    } catch {
        ElMessage.error('加载失败')
        report.value = null
    } finally {
        loading.value = false
    }
}

async function triggerScan() {
    scanning.value = true
    browseDate.value = null
    const idx = scanIndex.value || 'hs300'
    try {
        const { data } = await axios.post(`${API}/scan?scan_type=${scanType.value}&index=${idx}`, {}, { timeout: 120000 })
        if (data.success) {
            report.value = data
            scanIndex.value = idx
            expanded.value = -1
            // 刷新今日概览
            await fetchTodaySummary()
        } else {
            ElMessage.error(data.error || '扫描失败')
        }
    } catch (e) {
        ElMessage.error('扫描失败: ' + (e.message || '网络错误'))
    } finally {
        scanning.value = false
    }
}

onMounted(async () => {
    await fetchTodaySummary()
})
</script>

<style scoped>
.ai-driven-page {
    padding: 20px;
    max-width: 1200px;
    margin: 0 auto;
}
.page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
}
.page-header h1 {
    margin: 0;
    font-size: 22px;
}
.header-actions {
    display: flex;
    align-items: center;
}
.overview-card {
    margin-bottom: 20px;
    background: linear-gradient(135deg, #1a1a2e, #16213e);
    border: 1px solid #2a2a4e;
}
.detail-card {
    background: #1e1e3a !important;
}
.summary-grid {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
}
.summary-card {
    flex: 1;
    min-width: 180px;
    background: rgba(255,255,255,.04);
    border: 1px solid #2a2a4e;
    border-radius: 8px;
    padding: 14px 16px;
    cursor: pointer;
    transition: all .2s;
}
.summary-card:hover {
    border-color: #409eff;
    background: rgba(64,158,255,.08);
    transform: translateY(-2px);
}
.summary-card .sc-name {
    font-size: 16px;
    font-weight: 700;
    color: #e0e0e0;
}
.summary-card .sc-type {
    font-size: 11px;
    color: #909399;
    margin-bottom: 8px;
}
.summary-card .sc-count {
    font-size: 28px;
    font-weight: 700;
    color: #e6a23c;
}
.summary-card .sc-unit {
    font-size: 13px;
    font-weight: 400;
    color: #606266;
    margin-left: 4px;
}
.summary-card .sc-meta {
    font-size: 12px;
    color: #606266;
    margin-top: 4px;
}
.summary-card .sc-time {
    font-size: 11px;
    color: #434343;
    margin-top: 4px;
}
.overview-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
}
.overview-item {
    flex: 1;
    min-width: 120px;
}
.overview-item.full-width {
    flex: 0 0 100%;
    margin-top: 8px;
}
.ov-label {
    font-size: 12px;
    color: #909399;
    margin-bottom: 4px;
}
.ov-value {
    font-size: 18px;
    font-weight: 600;
    color: #e0e0e0;
}
.signal-count {
    color: #e6a23c;
}
.empty-state {
    padding: 60px 0;
}
.signals-section h2,
.risk-card h2 {
    font-size: 18px;
    margin-bottom: 16px;
}
.signal-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
}
.signal-card {
    background: #1e1e3a;
    border: 1px solid #2a2a4e;
    cursor: pointer;
    transition: border-color .2s;
}
.signal-card:hover {
    border-color: #409eff;
}
.signal-header {
    display: flex;
    align-items: center;
    gap: 12px;
}
.signal-rank {
    font-size: 20px;
    font-weight: 700;
    color: #606266;
    width: 36px;
}
.signal-meta {
    flex: 1;
}
.signal-code {
    font-size: 16px;
    font-weight: 600;
    color: #e0e0e0;
}
.signal-name {
    font-size: 13px;
    color: #909399;
}
.signal-score {
    font-size: 24px;
    font-weight: 700;
    width: 50px;
    text-align: center;
}
.score-excellent { color: #f56c6c; }
.score-good { color: #e6a23c; }
.score-watch { color: #67c23a; }
.score-neutral { color: #909399; }
.signal-change {
    font-size: 16px;
    font-weight: 600;
    width: 80px;
    text-align: center;
}
.signal-change.up { color: #f56c6c; }
.signal-change.down { color: #67c23a; }
.signal-confidence {
    width: 120px;
}
.signal-expand {
    color: #606266;
}
.signal-detail {
    padding: 12px 0 4px;
}
.score-bars {
    display: flex;
    gap: 20px;
    margin-bottom: 12px;
}
.bar-item {
    flex: 1;
}
.bar-label {
    font-size: 12px;
    color: #909399;
    display: block;
    margin-bottom: 4px;
}
.detail-summary {
    font-size: 13px;
    color: #a0a4b0;
    margin-bottom: 12px;
    padding: 8px 12px;
    background: rgba(64, 158, 255, .08);
    border-radius: 4px;
}
.detail-section {
    margin-bottom: 10px;
}
.detail-section h4 {
    font-size: 13px;
    margin: 0 0 6px;
    color: #ccc;
}
.tag-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}
.trade-suggestion {
    background: rgba(103, 194, 58, .06);
    border-radius: 4px;
    padding: 8px;
}
.trade-grid {
    display: flex;
    gap: 24px;
}
.trade-item {
    display: flex;
    flex-direction: column;
}
.trade-item label {
    font-size: 11px;
    color: #909399;
}
.trade-item span {
    font-size: 16px;
    font-weight: 600;
    color: #e0e0e0;
}
.trade-item span.up { color: #f56c6c; }
.trade-item span.down { color: #67c23a; }
.kline-chart {
    width: 100%;
    height: 420px;
    border-radius: 4px;
    overflow: hidden;
}
.risk-card {
    margin-top: 20px;
    background: rgba(245, 108, 108, .04);
    border: 1px solid rgba(245, 108, 108, .2);
}
.risk-item {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
}
.risk-desc {
    font-size: 13px;
    color: #a0a4b0;
}
.report-footer {
    text-align: center;
    margin-top: 20px;
    font-size: 11px;
    color: #606266;
}
</style>
