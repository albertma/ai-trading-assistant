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
                <el-button type="primary" size="small" @click="showAdd = true" style="margin-left:8px;">+ 添加持仓</el-button>
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
                            <span style="font-size:14px;">市值 <b>¥{{ fmt(groupSummary(market).value) }}</b></span>
                            <span :style="{ color: (groupSummary(market).profit||0) >= 0 ? '#f56c6c' : '#67c23a', fontSize:'14px' }">
                                盈亏 <b>{{ groupSummary(market).profit >= 0 ? '+' : '' }}¥{{ fmt(groupSummary(market).profit) }}</b>
                                ({{ groupSummary(market).profit_pct }}%)
                            </span>
                            <el-tag type="info" size="small" effect="plain">≈ ¥{{ fmt(groupSummary(market).value_cny) }} CNY</el-tag>
                        </div>
                    </div>
                </template>
                <el-table :data="items" stripe style="width:100%" size="small">
                    <el-table-column prop="code" label="代码" width="90">
                        <template #default="{ row }">
                            <el-button type="primary" link size="small" @click="goAnalysis(row.code)">{{ row.code }}</el-button>
                        </template>
                    </el-table-column>
                    <el-table-column prop="name" label="名称" width="100">
                        <template #default="{ row }">
                            <el-button type="primary" link size="small" @click="goAnalysis(row.code)">{{ row.name }}</el-button>
                        </template>
                    </el-table-column>
                    <el-table-column prop="quantity" label="数量" width="80" align="right" />
                    <el-table-column prop="cost_price" label="成本价" width="90" align="right">
                        <template #default="{ row }">{{ row.cost_price.toFixed(2) }}</template>
                    </el-table-column>
                    <el-table-column prop="current_price" label="现价" width="90" align="right">
                        <template #default="{ row }">{{ row.current_price.toFixed(2) }}</template>
                    </el-table-column>
                    <el-table-column prop="cost_total" label="成本" width="100" align="right">
                        <template #default="{ row }">{{ row.cost_total.toFixed(2) }}</template>
                    </el-table-column>
                    <el-table-column prop="market_value" label="市值" width="100" align="right">
                        <template #default="{ row }">{{ row.market_value.toFixed(2) }}</template>
                    </el-table-column>
                    <el-table-column prop="profit_amount" label="盈亏" width="100" align="right">
                        <template #default="{ row }">
                            <span :style="{ color: row.profit_amount >= 0 ? '#f56c6c' : '#67c23a' }">
                                {{ row.profit_amount >= 0 ? '+' : '' }}{{ row.profit_amount.toFixed(2) }}
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

        <!-- 添加持仓弹窗 -->
        <el-dialog v-model="showAdd" title="添加持仓" width="400px">
            <el-form :model="form" label-width="80px">
                <el-form-item label="代码" required>
                    <el-input v-model="form.code" placeholder="如 600519 / AAPL / BTC" />
                </el-form-item>
                <el-form-item label="名称" required>
                    <el-input v-model="form.name" placeholder="如 贵州茅台" />
                </el-form-item>
                <el-form-item label="数量" required>
                    <el-input-number v-model="form.quantity" :min="1" style="width:100%" />
                </el-form-item>
                <el-form-item label="成本价" required>
                    <el-input-number v-model="form.cost_price" :min="0.01" :step="0.01" :precision="2" style="width:100%" />
                </el-form-item>
                <el-form-item label="备注">
                    <el-input v-model="form.note" />
                </el-form-item>
            </el-form>
            <template #footer>
                <el-button @click="showAdd = false">取消</el-button>
                <el-button type="primary" @click="handleAdd" :loading="adding">确认添加</el-button>
            </template>
        </el-dialog>

        <!-- 编辑持仓弹窗 -->
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
import { getPositions, addPosition, updatePosition, deletePosition } from '../api/index.js'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

const router = useRouter()
const loading = ref(true)
const positions = ref([])
const groups = ref({})
const totalCny = ref({})

// 增
const showAdd = ref(false)
const adding = ref(false)
const form = ref({ code: '', name: '', quantity: 100, cost_price: 0, note: '' })

// 改
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
function groupSummary(market) { return groups.value[market] || {} }
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
        totalCny.value = data.total_cny || {}
    } catch (e) {
        ElMessage.error('加载持仓失败')
    } finally { loading.value = false }
}

async function handleAdd() {
    if (!form.value.code || !form.value.name || !form.value.quantity || !form.value.cost_price) {
        ElMessage.warning('请填写完整信息'); return
    }
    adding.value = true
    try {
        await addPosition(form.value)
        ElMessage.success('添加成功')
        showAdd.value = false
        form.value = { code: '', name: '', quantity: 100, cost_price: 0, note: '' }
        await loadData()
    } catch (e) { ElMessage.error(e.response?.data?.detail || '添加失败')
    } finally { adding.value = false }
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

function goAnalysis(code) { router.push({ path: '/analysis', query: { code } }) }
</script>

<style scoped>
.positions-page { max-width: 1400px; margin: 0 auto; }
.summary-card { text-align: center; cursor: default; }
.summary-card.total { border-left: 4px solid #409eff; }
.summary-value { font-size: 24px; font-weight: bold; }
.summary-label { font-size: 13px; color: #909399; margin-top: 4px; }
</style>
