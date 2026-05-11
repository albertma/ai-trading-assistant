<template>
    <div class="positions-page">
        <!-- 总汇（CNY） -->
        <el-row :gutter="16" style="margin-bottom: 16px;">
            <el-col :span="6">
                <el-card shadow="hover" class="summary-card total">
                    <div class="summary-label">持仓总数</div>
                    <div class="summary-value" style="color:#409eff;">{{ totalCny.count }} 只</div>
                </el-card>
            </el-col>
            <el-col :span="6">
                <el-card shadow="hover" class="summary-card total">
                    <div class="summary-label">总成本 (CNY)</div>
                    <div class="summary-value">¥{{ fmt(totalCny.cost_cny) }}</div>
                </el-card>
            </el-col>
            <el-col :span="6">
                <el-card shadow="hover" class="summary-card total">
                    <div class="summary-label">总市值 (CNY)</div>
                    <div class="summary-value">¥{{ fmt(totalCny.value_cny) }}</div>
                </el-card>
            </el-col>
            <el-col :span="6">
                <el-card shadow="hover" class="summary-card total">
                    <div class="summary-label">总盈亏 (CNY)</div>
                    <div class="summary-value" :style="{ color: (totalCny.profit_cny||0) >= 0 ? '#f56c6c' : '#67c23a' }">
                        {{ totalCny.profit_cny >= 0 ? '+' : '' }}¥{{ fmt(totalCny.profit_cny) }}
                        <span style="font-size:14px;margin-left:4px;">({{ totalCny.profit_pct }}%)</span>
                    </div>
                </el-card>
            </el-col>
        </el-row>

        <!-- 操作栏 -->
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
            <div></div>
            <div>
                <!-- 持仓分析按钮直接跳转到独立页面 -->
        <el-button size="small" @click="$router.push('/positions-analysis')">📊 持仓分析</el-button>
                <el-button type="primary" size="small" @click="openManageDialog" style="margin-left:8px;">🔄 修改持仓</el-button>
            </div>
        </div>

        <!-- 按市场分组 -->
        <div v-for="(items, market) in marketGroups" :key="market">
            <el-card shadow="hover" style="margin-bottom:12px;">
                <template #header>
                    <div style="display:flex;align-items:center;justify-content:space-between;">
                        <div style="display:flex;align-items:center;gap:8px;">
                            <el-tag :type="tagType(market)" size="large" effect="dark">
                                {{ marketLabel(market) }}
                            </el-tag>
                            <span style="font-size:13px;color:#909399;">
                                {{ items.length }} 只 · 成本 ¥{{ fmt(groupSummary(market).cost) }}
                            </span>
                        </div>
                        <div style="display:flex;align-items:center;gap:16px;">
                            <span style="font-size:14px;">市值 <b>{{ groupSummary(market).currency_symbol }}{{ fmt(groupSummary(market).value) }}</b></span>
                            <span :style="{ color: (groupSummary(market).profit||0) >= 0 ? '#f56c6c' : '#67c23a', fontSize:'14px' }">
                                盈亏 <b>{{ groupSummary(market).profit >= 0 ? '+' : '' }}{{ groupSummary(market).currency_symbol }}{{ fmt(groupSummary(market).profit) }}</b>
                                ({{ groupSummary(market).profit_pct }}%)
                            </span>
                            <el-tag type="info" size="small" effect="plain">≈ ¥{{ fmt(groupSummary(market).value_cny) }} CNY</el-tag>
                        </div>
                    </div>
                </template>
                <el-table :data="items" stripe style="width:100%" size="small">
                    <el-table-column label="名称" width="100">
                        <template #default="{ row }">
                            <router-link :to="`/analysis?code=${row.code}`" style="color:#409eff;text-decoration:none;">{{ row.name }}</router-link>
                        </template>
                    </el-table-column>
                    <el-table-column label="代码" width="90">
                        <template #default="{ row }">
                            <router-link :to="`/analysis?code=${row.code}`" style="color:#409eff;text-decoration:none;">{{ row.code }}</router-link>
                        </template>
                    </el-table-column>
                    <el-table-column prop="quantity" label="数量" width="80" align="right" />
                    <el-table-column prop="cost_price" label="成本价" width="90" align="right">
                        <template #default="{ row }">{{ row.cost_price.toFixed(2) }}</template>
                    </el-table-column>
                    <el-table-column prop="current_price" label="现价" width="90" align="right">
                        <template #default="{ row }">{{ row.currency_symbol }}{{ row.current_price.toFixed(2) }}</template>
                    </el-table-column>
                    <el-table-column prop="cost_total" label="成本" width="100" align="right">
                        <template #default="{ row }">{{ row.cost_total.toFixed(2) }}</template>
                    </el-table-column>
                    <el-table-column prop="market_value" label="市值" width="100" align="right">
                        <template #default="{ row }">{{ row.currency_symbol }}{{ row.market_value.toFixed(2) }}</template>
                    </el-table-column>
                    <el-table-column prop="profit_amount" label="盈亏" width="100" align="right">
                        <template #default="{ row }">
                            <span :style="{ color: row.profit_amount >= 0 ? '#f56c6c' : '#67c23a' }">
                                {{ row.profit_amount >= 0 ? '+' : '' }}{{ row.currency_symbol }}{{ row.profit_amount.toFixed(2) }}
                            </span>
                        </template>
                    </el-table-column>
                    <el-table-column prop="profit_pct" label="盈亏%" width="80" align="right">
                        <template #default="{ row }">
                            <el-tag :type="row.profit_pct >= 0 ? 'danger' : 'success'" size="small" effect="dark">
                                {{ row.profit_pct >= 0 ? '+' : '' }}{{ row.profit_pct.toFixed(2) }}%
                            </el-tag>
                        </template>
                    </el-table-column>
                    <el-table-column label="操作" width="140">
                        <template #default="{ row }">
                            <el-button size="small" text @click="handleEdit(row)">编辑</el-button>
                            <el-popconfirm title="确定删除？" @confirm="handleDelete(row.code)">
                                <template #reference>
                                    <el-button type="danger" size="small" link>删除</el-button>
                                </template>
                            </el-popconfirm>
                        </template>
                    </el-table-column>
                </el-table>
            </el-card>
        </div>

        <!-- 修改持仓弹窗（含股票选择 + 交易 + 历史） -->
        <el-dialog v-model="showManage" title="🔄 修改持仓" width="780px" top="5vh" :close-on-click-modal="false">
            <!-- 股票选择区 -->
            <div style="display:flex;gap:8px;margin-bottom:12px;align-items:center;">
                <el-select v-model="manageCode" filterable clearable placeholder="选择已有持仓股票" style="width:220px;"
                    @change="onManageCodeChange">
                    <el-option v-for="p in positions" :key="p.code" :label="`${p.code} ${p.name}`" :value="p.code" />
                </el-select>
                <span style="color:#909399;font-size:12px;">或检索</span>
                <el-autocomplete
                    v-model="searchQ"
                    :fetch-suggestions="searchStocks"
                    :trigger-on-focus="false"
                    placeholder="代码/名称/拼音首字母，如 zgd"
                    style="width:300px;"
                    size="small"
                    clearable
                    @select="selectStock"
                    @keyup.enter="searchStocks(searchQ, (r)=>r && r[0] && selectStock(r[0]))"
                >
                    <template #default="{ item }">
                        <div style="display:flex;align-items:center;justify-content:space-between;">
                            <span><b>{{ item.code }}</b> {{ item.name }}</span>
                            <el-tag :type="tagType(item.market)" size="mini" effect="plain">{{ marketLabel(item.market) }}</el-tag>
                        </div>
                    </template>
                </el-autocomplete>
                <el-button size="small" type="primary" @click="searchStocks(searchQ, r=>r && r[0] && selectStock(r[0]))">
                    🔍 搜索
                </el-button>
            </div>

            <template v-if="manageCode">
                <el-divider content-position="left">
                    📊 当前持仓
                    <el-tag size="small" type="info" style="margin-left:6px;">{{ manageCode }}</el-tag>
                </el-divider>

                <!-- 持仓概要 -->
                <div v-if="managePosition" style="display:flex;gap:24px;padding:12px;background:#f5f7fa;border-radius:8px;margin-bottom:12px;">
                    <div><span class="label">名称</span><br><b>{{ managePosition.name }}</b></div>
                    <div><span class="label">数量</span><br><b>{{ managePosition.quantity }}</b></div>
                    <div><span class="label">成本价</span><br><b>{{ managePosition.cost_price.toFixed(2) }}</b></div>
                    <div><span class="label">市值</span><br><b>{{ managePosition.currency_symbol }}{{ managePosition.market_value.toFixed(0) }}</b></div>
                    <div><span class="label">盈亏</span><br>
                        <b :style="{color: managePosition.profit_amount >= 0 ? '#f56c6c' : '#67c23a'}">
                            {{ managePosition.profit_amount >= 0 ? '+' : '' }}{{ managePosition.currency_symbol }}{{ managePosition.profit_amount.toFixed(0) }}
                        </b>
                    </div>
                </div>

                <!-- 交易输入区 -->
                <el-divider content-position="left">✏️ 新增交易</el-divider>
                <el-tabs v-model="tradeForm.direction" type="card" @tab-change="onTradeDirectionChange">
                    <el-tab-pane label="🔴 买入" name="买入" />
                    <el-tab-pane label="🟢 卖出" name="卖出" />
                </el-tabs>
                <div style="display:flex;gap:8px;align-items:flex-start;flex-wrap:wrap;margin-top:4px;">
                    <el-input v-model="tradeForm.trade_date" placeholder="日期 YYYY-MM-DD" size="small" style="width:130px;" />
                    <el-input-number v-model="tradeForm.quantity" :min="1" style="width:130px;" size="small" placeholder="数量" />
                    <el-input-number v-model="tradeForm.price" :min="0.01" :step="0.01" :precision="2" style="width:140px;" size="small" placeholder="价格" />
                    <el-input v-model="tradeForm.note" placeholder="备注" size="small" style="width:150px;" />
                    <el-button size="small" type="primary" @click="handleSaveTrade" :loading="tradeSaving">确认</el-button>
                </div>

                <!-- 交易历史 -->
                <el-divider content-position="left">📋 交易记录（{{ manageTrades.length }}笔）</el-divider>
                <el-table :data="manageTrades" border size="small" style="width:100%;" max-height="280" v-if="manageTrades.length">
                    <el-table-column label="日期" width="100" prop="trade_date" />
                    <el-table-column label="方向" width="65">
                        <template #default="{ row }">
                            <el-tag :type="row.direction === '买入' ? 'danger' : 'success'" size="small">
                                {{ row.direction }}
                            </el-tag>
                        </template>
                    </el-table-column>
                    <el-table-column label="数量" width="80" align="right" prop="quantity" />
                    <el-table-column label="价格" width="90" align="right">
                        <template #default="{ row }">{{ row.price.toFixed(2) }}</template>
                    </el-table-column>
                    <el-table-column label="金额" width="100" align="right">
                        <template #default="{ row }">{{ row.total.toFixed(0) }}</template>
                    </el-table-column>
                    <el-table-column label="备注" min-width="130">
                        <template #default="{ row }">{{ row.note || '--' }}</template>
                    </el-table-column>
                    <el-table-column label="操作" width="80">
                        <template #default="{ row }">
                            <el-popconfirm title="确定删除？" @confirm="removeManageTrade(row)">
                                <template #reference>
                                    <el-button type="danger" size="small" link>删除</el-button>
                                </template>
                            </el-popconfirm>
                        </template>
                    </el-table-column>
                </el-table>
                <el-empty v-else description="暂无交易记录" :image-size="60" />
            </template>

            <template v-else>
                <el-empty description="请选择或输入股票代码" :image-size="80" />
            </template>
        </el-dialog>

        <!-- 编辑持仓（列表行内快速调整） -->
        <el-dialog v-model="showEdit" title="编辑持仓" width="400px">
            <el-form :model="editForm" label-width="80px">
                <el-form-item label="代码"><el-input v-model="editForm.code" disabled /></el-form-item>
                <el-form-item label="名称"><el-input v-model="editForm.name" disabled /></el-form-item>
                <el-form-item label="数量" required>
                    <el-input-number v-model="editForm.quantity" :min="1" style="width:100%" />
                </el-form-item>
                <el-form-item label="成本价" required>
                    <el-input-number v-model="editForm.cost_price" :min="0.01" :step="0.01" :precision="2" style="width:100%" />
                </el-form-item>
                <el-form-item label="备注"><el-input v-model="editForm.note" /></el-form-item>
            </el-form>
            <template #footer>
                <el-button @click="showEdit = false">取消</el-button>
                <el-button type="primary" @click="handleUpdate" :loading="updating">保存修改</el-button>
            </template>
        </el-dialog>
    </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getPositions, updatePosition, deletePosition, getTrades, addTrade, deleteTrade } from '../api/index.js'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

const router = useRouter()
const loading = ref(true)
const positions = ref([])
const groups = ref({})
const groupSummaries = ref({})
const totalCny = ref({})

// 修改持仓（统一入口）
const showManage = ref(false)
const manageCode = ref('')
const searchQ = ref('')
const managePosition = computed(() => positions.value.find(p => p.code === manageCode.value))
const manageTrades = ref([])
const tradeForm = ref({ direction: '买入', trade_date: '', quantity: 100, price: 0, note: '' })
const tradeSaving = ref(false)

// 编辑（列表行内快速调整）
const showEdit = ref(false)
const updating = ref(false)
const editForm = ref({ code: '', name: '', quantity: 0, cost_price: 0, note: '' })

const MARKET_ORDER = ['a_stock', 'hk_stock', 'us_stock', 'crypto']

const marketGroups = computed(() => {
    const g = {}
    for (const m of MARKET_ORDER) {
        if (groups.value[m]?.length) g[m] = groups.value[m]
    }
    return g
})

function marketLabel(m) { return { a_stock:'A股', hk_stock:'港股', us_stock:'美股', crypto:'加密货币' }[m] || m }
function tagType(m) { return { a_stock:'', hk_stock:'warning', us_stock:'primary', crypto:'danger' }[m] || 'info' }
function groupSummary(market) { return groupSummaries.value[market] || {} }
function fmt(v) {
    if (v == null) return '0'
    return Math.abs(v).toLocaleString('zh-CN', { minimumFractionDigits:0, maximumFractionDigits:0 })
}

onMounted(async () => { await loadData() })

async function loadData() {
    loading.value = true
    try {
        const { data } = await getPositions()
        positions.value = data.positions || []
        const g = {}
        for (const p of positions.value) {
            const m = p.market || 'other'
            if (!g[m]) g[m] = []
            g[m].push(p)
        }
        groups.value = g
        groupSummaries.value = data.group_summaries || {}
        totalCny.value = data.total_cny || {}
    } catch (e) {
        ElMessage.error('加载持仓失败')
    } finally { loading.value = false }
}

function handleEdit(row) {
    editForm.value = { code: row.code, name: row.name, quantity: row.quantity, cost_price: row.cost_price, note: row.note || '' }
    showEdit.value = true
}

async function handleUpdate() {
    if (!editForm.value.quantity || !editForm.value.cost_price) {
        ElMessage.warning('数量和成本价不能为空'); return
    }
    updating.value = true
    try {
        await updatePosition(editForm.value.code, {
            quantity: editForm.value.quantity,
            cost_price: editForm.value.cost_price,
            note: editForm.value.note,
        })
        ElMessage.success('已更新')
        showEdit.value = false
        await loadData()
    } catch (e) { ElMessage.error(e.response?.data?.detail || '更新失败')
    } finally { updating.value = false }
}

async function handleDelete(code) {
    try {
        await deletePosition(code)
        ElMessage.success('删除成功')
        await loadData()
    } catch (e) { ElMessage.error('删除失败') }
}

// ===== 修改持仓（统一入口）=====
const stockSearchCache = {}
async function searchStocks(query, cb) {
    if (!query || query.trim().length < 1) { cb([]); return }
    const q = query.trim()
    // 简单缓存
    if (stockSearchCache[q]) { cb(stockSearchCache[q]); return }
    try {
        const res = await fetch(`/api/v1/stock-info/search?q=${encodeURIComponent(q)}&limit=15`)
        const data = await res.json()
        const items = (data.results || []).map(r => ({
            value: `${r.code} ${r.name}`,
            code: r.code,
            name: r.name,
            market: r.market || 'a_stock',
        }))
        stockSearchCache[q] = items
        cb(items)
    } catch (e) {
        cb([])
    }
}
function selectStock(item) {
    if (!item || !item.code) return
    manageCode.value = item.code
    searchQ.value = `${item.code} ${item.name}`
    onManageCodeChange()
}
function openManageDialog() {
    const today = new Date().toISOString().slice(0, 10)
    tradeForm.value = { direction: '买入', trade_date: today, quantity: 100, price: 0, note: '' }
    manageCode.value = ''
    searchQ.value = ''
    manageTrades.value = []
    showManage.value = true
}
async function onManageCodeChange() {
    tradeForm.value.trade_date = new Date().toISOString().slice(0, 10)
    if (!manageCode.value) { manageTrades.value = []; return }
    try {
        const { data } = await getTrades(manageCode.value)
        manageTrades.value = data
    } catch (e) { manageTrades.value = [] }
    // 切换股票时默认填现价和数量
    const pos = positions.value.find(p => p.code === manageCode.value)
    if (pos) {
        tradeForm.value.price = pos.current_price
        tradeForm.value.quantity = 100  // A股默认100
    }
}

function onTradeDirectionChange() {
    // 切换买入/卖出tab时价格默认填现价
    const pos = positions.value.find(p => p.code === manageCode.value)
    if (pos) {
        tradeForm.value.price = pos.current_price
    }
    // 卖出默认数量也设为100
    tradeForm.value.quantity = 100
}
async function handleSaveTrade() {
    const f = tradeForm.value
    const code = manageCode.value
    if (!code || !f.direction || !f.trade_date || !f.quantity || !f.price) {
        ElMessage.warning('请填写完整信息'); return
    }
    tradeSaving.value = true
    try {
        await addTrade(code, f)
        ElMessage.success(`${f.direction} ${f.quantity}股 @ ${f.price}`)
        // 刷新交易记录 + 持仓列表
        const { data } = await getTrades(code)
        manageTrades.value = data
        await loadData()
        // 重置表单（日期保留今天）
        const today = new Date().toISOString().slice(0, 10)
        tradeForm.value = { direction: '买入', trade_date: today, quantity: 100, price: 0, note: '' }
    } catch (e) { ElMessage.error(e.response?.data?.detail || '保存失败')
    } finally { tradeSaving.value = false }
}
async function removeManageTrade(row) {
    const code = manageCode.value
    try {
        await deleteTrade(code, row.id)
        ElMessage.success('已删除')
        const { data } = await getTrades(code)
        manageTrades.value = data
        await loadData()
    } catch (e) { ElMessage.error('删除失败') }
}

function goAnalysis(code) { router.push({ path: '/analysis', query: { code } }) }
</script>

<style scoped>
.positions-page { max-width: 1400px; margin: 0 auto; }
.summary-card { text-align: center; cursor: default; }
.summary-card.total { border-left: 4px solid #409eff; }
.summary-value { font-size: 24px; font-weight: bold; }
.summary-label { font-size: 13px; color: #909399; margin-top: 4px; }
.label { font-size: 12px; color: #909399; }
</style>
