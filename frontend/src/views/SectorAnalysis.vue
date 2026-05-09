<template>
    <div class="sector-page">
        <!-- ═══ 全市场周期总览（完整摘要） ═══ -->
        <el-card v-if="summary" class="summary-card">
            <template #header>
                <div class="card-header">
                    <b>📊 板块周期研判</b>
                    <div style="display:flex;align-items:center;gap:8px;">
                        <el-date-picker v-model="selectedDate" type="date" placeholder="选择日期"
                            size="small" style="width:160px;" value-format="YYYY-MM-DD"
                            :disabled-date="disabledDate" @change="onDateChange"
                            :clearable="false" />
                        <el-button size="small" @click="refreshData" :loading="loading">🔄 刷新</el-button>
                    </div>
                </div>
            </template>

            <!-- ① 市场总体判断 -->
            <div class="assess-row">
                <span class="bias-tag" :style="{ background: summary.bias_color }">{{ summary.bias }}</span>
                <span class="assess-text">{{ summary.assessment }}</span>
            </div>

            <!-- ② 相位分布标签 -->
            <div class="phase-tags">
                <el-tag v-for="(cnt, phase) in summary.phase_distribution" :key="phase"
                    :color="getPhaseColor(phase)" effect="dark" size="small" style="margin:2px;color:#fff;">
                    {{ phase }} {{ cnt }}
                </el-tag>
            </div>

            <!-- ③ 相位预判流（仅显示有板块的相位） -->
            <div class="predictions-section" v-if="summary.phase_predictions && Object.keys(summary.phase_predictions).length">
                <div class="section-title">📈 相位推演</div>
                <div class="flow-chart">
                    <div v-for="(pred, phase) in summary.phase_predictions" :key="phase" class="flow-item">
                        <div class="flow-icon-wrap">
                            <span class="flow-icon" :style="{ background: pred.color + '20', color: pred.color }">{{ phase.slice(0,2) }}</span>
                        </div>
                        <div class="flow-body">
                            <div class="flow-header">
                                <el-tag :color="pred.color" effect="dark" size="mini" style="color:#fff;border:none;">
                                    {{ phase }} {{ pred.count }}
                                </el-tag>
                                <span class="flow-next">
                                    → {{ pred.next }}
                                </span>
                                <span class="flow-type" :style="{ color: pred.color }">{{ pred.type }}</span>
                            </div>
                            <div class="flow-predict">{{ pred.predict }}</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- ④ 关注板块 -->
            <div class="focus-section" v-if="summary.focus_sectors && Object.keys(summary.focus_sectors).length">
                <div class="section-title">🎯 关注板块</div>
                <div v-for="(items, category) in summary.focus_sectors" :key="category" class="focus-group">
                    <div class="focus-category">{{ category }}</div>
                    <div class="focus-grid">
                        <div v-for="item in items" :key="item.sector" class="focus-chip"
                            @click="showSectorDetailByName(item.sector)">
                            <span class="focus-name">{{ item.sector }}</span>
                            <span class="focus-reason">{{ item.reason }}</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- ⑤ 主题主线 -->
            <div class="themes-section" v-if="summary.themes && summary.themes.length">
                <div class="section-title">🔗 主线逻辑</div>
                <div class="themes-grid">
                    <div v-for="theme in summary.themes" :key="theme.name" class="theme-card">
                        <div class="theme-name">{{ theme.name }}</div>
                        <div class="theme-sectors">{{ theme.sectors.join(' · ') }}</div>
                        <div class="theme-summary">{{ theme.summary }}</div>
                    </div>
                </div>
            </div>

            <!-- ⑥ 风险提示 -->
            <div class="warnings-section" v-if="summary.warnings && summary.warnings.length">
                <div class="section-title">⚠️ 风险提示</div>
                <div class="warnings-list">
                    <div v-for="(w, i) in summary.warnings" :key="i" class="warning-item"
                        :class="'level-' + w.level">
                        <span class="warning-icon">{{ w.level === 'alert' ? '🔴' : w.level === 'warning' ? '🟡' : '🟢' }}</span>
                        <span class="warning-msg">{{ w.msg }}</span>
                    </div>
                </div>
            </div>
        </el-card>

        <!-- ═══ 板块详情列表 ═══ -->
        <el-card style="margin-top:16px;">
            <template #header>
                <div class="card-header">
                    <b>📋 各板块周期相位</b>
                    <div>
                        <el-select v-model="phaseFilter" placeholder="筛选相位" size="small" clearable style="width:150px;">
                            <el-option v-for="p in phaseOptions" :key="p" :label="p" :value="p" />
                        </el-select>
                        <el-input v-model="searchQuery" placeholder="搜索板块" size="small" style="width:180px;margin-left:8px;" clearable />
                    </div>
                </div>
            </template>
            <el-table :data="filteredSectors" border size="small" style="width:100%;" v-if="sectors.length" @row-click="showSectorDetail">
                <el-table-column label="周期" width="100">
                    <template #default="{ row }">
                        <span :style="{ fontSize: '16px' }">{{ row.icon }}</span>
                        <el-tag :color="row.color" effect="dark" size="mini" style="margin-left:4px;color:#fff;border:none;">
                            {{ row.phase }}
                        </el-tag>
                    </template>
                </el-table-column>
                <el-table-column label="板块" min-width="130" prop="sector" />
                <el-table-column label="平均涨幅" width="90">
                    <template #default="{ row }">
                        <span :style="{ color: row.avg_change > 0 ? '#f56c6c' : '#67c23a', fontWeight:'bold' }">
                            {{ row.avg_change > 0 ? '+' : '' }}{{ row.avg_change }}%
                        </span>
                    </template>
                </el-table-column>
                <el-table-column label="分化(σ)" width="80" prop="dispersion" />
                <el-table-column label="上涨占比" width="90">
                    <template #default="{ row }">
                        <el-progress :percentage="row.up_pct" :stroke-width="12"
                            :color="row.up_pct > 70 ? '#67c23a' : row.up_pct > 40 ? '#e6a23c' : '#f56c6c'"
                            :format="() => row.up_pct + '%'" />
                    </template>
                </el-table-column>
                <el-table-column label="个股数" width="80">
                    <template #default="{ row }">
                        <el-link type="primary" :underline="false" @click="showSectorStocks(row, $event)"
                            style="font-weight:600;">
                            {{ row.stock_count }}
                        </el-link>
                    </template>
                </el-table-column>
                <el-table-column label="最强/最弱" min-width="130">
                    <template #default="{ row }">
                        <span style="color:#f56c6c;">{{ row.max_change > 0 ? '+' : '' }}{{ row.max_change }}%</span>
                        <span style="color:#909399;"> / </span>
                        <span style="color:#67c23a;">{{ row.min_change > 0 ? '+' : '' }}{{ row.min_change }}%</span>
                    </template>
                </el-table-column>
                <el-table-column label="说明" min-width="220">
                    <template #default="{ row }">
                        <span style="font-size:12px;color:#606266;">{{ row.desc }}</span>
                    </template>
                </el-table-column>
            </el-table>
            <el-empty v-else-if="!loading" description="暂无板块数据，请先刷新" />
            <div v-else style="text-align:center;padding:40px;"><el-icon class="is-loading" :size="24"><Loading /></el-icon></div>
        </el-card>

        <!-- 板块详情弹窗 -->
        <el-dialog v-model="detailVisible" :title="'📈 ' + selectedSector + ' 周期历史'" width="800px">
            <div v-if="sectorHistory.length">
                <div class="timeline">
                    <div v-for="(h, i) in sectorHistory" :key="i" class="timeline-item">
                        <div class="timeline-dot" :style="{ background: h.color }"></div>
                        <div class="timeline-content">
                            <div class="tl-header">
                                <span class="tl-date">{{ h.date }}</span>
                                <el-tag :color="h.color" effect="dark" size="mini" style="color:#fff;border:none;">
                                    {{ h.icon }} {{ h.phase }}
                                </el-tag>
                            </div>
                            <div class="tl-stats">
                                <span>涨幅：<b :style="{color: h.avg_change > 0 ? '#f56c6c' : '#67c23a'}">{{ h.avg_change > 0 ? '+' : '' }}{{ h.avg_change }}%</b></span>
                                <span>分化：{{ h.dispersion }}</span>
                                <span>上涨占比：{{ h.up_pct }}%</span>
                            </div>
                            <div class="tl-desc">{{ h.desc }}</div>
                        </div>
                    </div>
                </div>
            </div>
            <el-empty v-else description="暂无历史数据" />
        </el-dialog>

        <!-- 行业个股列表弹窗 -->
        <el-dialog v-model="stocksVisible" :title="'📋 ' + stocksSector + ' 成份股 (' + stocksDate + ')'" width="900px">
            <el-table :data="sectorStocks" border size="small" style="width:100%;" max-height="500"
                @row-click="goToStockAnalysis" v-if="sectorStocks.length">
                <el-table-column label="代码" width="110" prop="code" />
                <el-table-column label="名称" min-width="120" prop="name" />
                <el-table-column label="最新价" width="90">
                    <template #default="{ row }">
                        <span>{{ row.close != null ? row.close.toFixed(2) : '-' }}</span>
                    </template>
                </el-table-column>
                <el-table-column label="涨幅" width="90">
                    <template #default="{ row }">
                        <span :style="{ color: row.change_pct > 0 ? '#f56c6c' : '#67c23a', fontWeight: 'bold' }">
                            {{ row.change_pct != null ? (row.change_pct > 0 ? '+' : '') + row.change_pct.toFixed(2) + '%' : '-' }}
                        </span>
                    </template>
                </el-table-column>
                <el-table-column label="成交额(亿)" width="100">
                    <template #default="{ row }">
                        <span>{{ row.amount != null ? row.amount.toFixed(2) : '-' }}</span>
                    </template>
                </el-table-column>
                <el-table-column label="换手率" width="80">
                    <template #default="{ row }">
                        <span>{{ row.turnover != null ? row.turnover.toFixed(2) + '%' : '-' }}</span>
                    </template>
                </el-table-column>
                <el-table-column label="总市值(亿)" width="110">
                    <template #default="{ row }">
                        <span>{{ row.market_cap != null ? row.market_cap.toFixed(2) : '-' }}</span>
                    </template>
                </el-table-column>
                <el-table-column label="市盈率" width="80">
                    <template #default="{ row }">
                        <span>{{ row.pe != null ? row.pe.toFixed(2) : '-' }}</span>
                    </template>
                </el-table-column>
            </el-table>
            <div v-else style="text-align:center;padding:20px;">加载中...</div>
        </el-dialog>
    </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const API_BASE = '/api/v1/mental'

const sectors = ref([])
const summary = ref(null)
const dataDate = ref('')
const loading = ref(false)
const phaseFilter = ref('')
const searchQuery = ref('')
const selectedDate = ref('')
const availableDates = ref([])

// Detail dialog
const detailVisible = ref(false)
const selectedSector = ref('')
// Stock list dialog
const stocksVisible = ref(false)
const stocksSector = ref('')
const stocksDate = ref('')
const sectorStocks = ref([])

const sectorHistory = ref([])

const phaseOptions = ['高潮🎯', '普涨🚀', '启动🔥', '冰点反弹🌱', '筑底🏗️', '酝酿🌋', '分化⚡', '退潮🌊', '防御🛡️', '冰点❄️', '普跌📉', '震荡⚖️']

const filteredSectors = computed(() => {
    let result = sectors.value
    if (phaseFilter.value) {
        result = result.filter(s => s.phase === phaseFilter.value)
    }
    if (searchQuery.value) {
        const q = searchQuery.value.toLowerCase()
        result = result.filter(s => s.sector.toLowerCase().includes(q))
    }
    return result
})

onMounted(async () => {
    await loadDates()
    await loadData()
})

function disabledDate(time) {
    const str = time.getFullYear() + '-' +
        String(time.getMonth() + 1).padStart(2, '0') + '-' +
        String(time.getDate()).padStart(2, '0')
    return !availableDates.value.includes(str)
}

async function onDateChange(val) {
    if (val) {
        selectedDate.value = val
        await loadData()
    }
}

async function loadDates() {
    try {
        const { data } = await axios.get(`${API_BASE}/sector-cycles/dates`)
        availableDates.value = data.dates || []
        selectedDate.value = data.latest || ''
    } catch { /* ignore */ }
}

async function loadData(targetDate) {
    loading.value = true
    const date = targetDate || selectedDate.value
    try {
        const params = date ? { date } : {}
        const { data } = await axios.get(`${API_BASE}/sector-cycles`, { params })
        sectors.value = data.sectors || []
        summary.value = data.summary
        dataDate.value = data.date
        if (data.date) selectedDate.value = data.date
    } catch { /* ignore */ }
    loading.value = false
}

async function refreshData() {
    await loadData()
}

function getPhaseColor(phase) {
    const map = {
        '高潮🎯': '#f56c6c', '普涨🚀': '#67c23a', '启动🔥': '#e6a23c',
        '冰点反弹🌱': '#67c23a', '筑底🏗️': '#67c23a', '酝酿🌋': '#e6a23c',
        '分化⚡': '#f56c6c', '退潮🌊': '#909399', '防御🛡️': '#909399',
        '冰点❄️': '#409eff', '普跌📉': '#909399', '震荡⚖️': '#909399',
    }
    return map[phase] || '#909399'
}

async function showSectorDetail(row) {
    selectedSector.value = row.sector
    await loadSectorHistory(row.sector)
}

async function showSectorDetailByName(name) {
    selectedSector.value = name
    await loadSectorHistory(name)
}

async function loadSectorHistory(name) {
    try {
        const { data } = await axios.get(`${API_BASE}/sector-cycles/history`, {
            params: { sector: name }
        })
        sectorHistory.value = data.history || []
        detailVisible.value = true
    } catch { /* ignore */ }
}

async function showSectorStocks(row) {
    stocksSector.value = row.sector
    stocksDate.value = dataDate.value
    stocksVisible.value = true
    sectorStocks.value = []
    try {
        const { data } = await axios.get(`${API_BASE}/sector-stocks`, {
            params: { sector: row.sector, date: dataDate.value }
        })
        sectorStocks.value = data.stocks || []
    } catch { /* ignore */ }
}

function goToStockAnalysis(row) {
    // 跳转到个股分析页面
    window.open(`/stock/${row.code}`, '_blank')
}
</script>

<style scoped>
.sector-page { padding: 0; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.summary-card { border-left: 3px solid #409eff; }

/* ① 市场判断 */
.assess-row { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 12px; }
.bias-tag {
    display: inline-block; padding: 2px 10px; border-radius: 4px;
    color: #fff; font-size: 13px; font-weight: 600; white-space: nowrap;
}
.assess-text { font-size: 13.5px; color: #303133; line-height: 1.6; }

/* ② 相位标签 */
.phase-tags { display: flex; flex-wrap: wrap; gap: 2px; margin-bottom: 10px; }

/* 共性小标题 */
.section-title {
    font-size: 14px; font-weight: 600; color: #303133;
    margin-top: 14px; margin-bottom: 10px; padding-bottom: 4px;
    border-bottom: 1px solid #ebeef5;
}

/* ③ 相位预判流 */
.predictions-section { margin-bottom: 4px; }
.flow-chart { display: flex; flex-direction: column; gap: 6px; }
.flow-item {
    display: flex; gap: 10px; align-items: flex-start;
    padding: 8px 10px; border-radius: 6px;
    background: #fafafa; border-left: 3px solid #e4e7ed;
}
.flow-icon-wrap { flex-shrink: 0; width: 28px; text-align: center; padding-top: 2px; }
.flow-icon {
    display: inline-flex; align-items: center; justify-content: center;
    width: 26px; height: 26px; border-radius: 50%;
    font-size: 14px; font-weight: bold;
}
.flow-body { flex: 1; min-width: 0; }
.flow-header { display: flex; align-items: center; gap: 8px; margin-bottom: 2px; }
.flow-next { font-size: 12px; color: #909399; }
.flow-type { font-size: 11px; }
.flow-predict { font-size: 12.5px; color: #606266; line-height: 1.5; margin-top: 2px; }

/* ④ 关注板块 */
.focus-section { margin-bottom: 4px; }
.focus-group { margin-bottom: 8px; }
.focus-category {
    font-size: 12px; font-weight: 600; color: #409eff; margin-bottom: 4px;
}
.focus-grid { display: flex; flex-wrap: wrap; gap: 4px; }
.focus-chip {
    display: inline-flex; flex-direction: column;
    padding: 5px 10px; border-radius: 6px;
    background: #ecf5ff; border: 1px solid #d9ecff;
    cursor: pointer; transition: all .15s;
    min-width: 120px;
}
.focus-chip:hover { background: #d9ecff; border-color: #409eff; }
.focus-name { font-size: 13px; font-weight: 600; color: #303133; }
.focus-reason { font-size: 10px; color: #909399; }

/* ⑤ 主线主题 */
.themes-section { margin-bottom: 4px; }
.themes-grid { display: flex; gap: 8px; flex-wrap: wrap; }
.theme-card {
    flex: 1; min-width: 200px;
    padding: 10px 12px; border-radius: 6px;
    background: linear-gradient(135deg, #f0f9ff, #f5f0ff);
    border: 1px solid #e8e0f0;
}
.theme-name { font-size: 14px; font-weight: 600; color: #303133; margin-bottom: 2px; }
.theme-sectors { font-size: 11px; color: #409eff; margin-bottom: 4px; }
.theme-summary { font-size: 12px; color: #606266; line-height: 1.5; }

/* ⑥ 风险提示 */
.warnings-section { margin-top: 4px; }
.warnings-list { display: flex; flex-direction: column; gap: 4px; }
.warning-item {
    display: flex; align-items: center; gap: 8px;
    padding: 6px 10px; border-radius: 4px;
    font-size: 13px;
}
.warning-item.level-alert { background: #fef0f0; }
.warning-item.level-warning { background: #fdf6ec; }
.warning-item.level-info { background: #f4f4f5; }
.warning-icon { flex-shrink: 0; }
.warning-msg { color: #606266; }

/* 历史时间线（原有） */
.timeline { position: relative; padding-left: 20px; }
.timeline::before {
    content: '';
    position: absolute;
    left: 8px;
    top: 0;
    bottom: 0;
    width: 2px;
    background: #e4e7ed;
}
.timeline-item { position: relative; margin-bottom: 16px; }
.timeline-dot {
    position: absolute;
    left: -16px;
    top: 4px;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    border: 2px solid #fff;
    box-shadow: 0 0 0 1px #e4e7ed;
}
.timeline-content {
    background: #f5f7fa;
    padding: 10px 14px;
    border-radius: 8px;
}
.tl-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.tl-date { font-size: 12px; color: #909399; }
.tl-stats { display: flex; gap: 16px; font-size: 12px; color: #606266; margin-bottom: 4px; }
.tl-desc { font-size: 12px; color: #909399; }
</style>
