<template>
    <div class="watchlist-page">
        <!-- ==================== 三栏布局 ==================== -->
        <el-row :gutter="12">
            <!-- ① 左侧：选中股票的详情 -->
            <el-col :span="11">
                <template v-if="!selected">
                    <el-empty description="请从右侧观察池选择一只股票" :image-size="80" />
                </template>

                <template v-else>
                    <!-- ①-a 备注 -->
                    <el-card shadow="hover" style="margin-bottom:12px;" :style="{ borderLeft: '4px solid #409eff' }">
                        <template #header>
                            <div style="display:flex;justify-content:space-between;align-items:center;">
                                <b>📝 备注 ({{ selected.name }})</b>
                                <el-button v-if="!editingNotes" size="small" type="primary" plain @click="startEditNotes">编辑</el-button>
                                <span v-else>
                                    <el-button size="small" @click="cancelEditNotes">取消</el-button>
                                    <el-button size="small" type="primary" @click="saveNotes">保存</el-button>
                                </span>
                            </div>
                        </template>
                        <div v-if="!editingNotes">
                            <div v-if="selected.notes" style="font-size:13px;color:#303133;line-height:1.6;white-space:pre-wrap;">{{ selected.notes }}</div>
                            <div v-else style="color:#909399;font-size:12px;">暂无备注，点击「编辑」添加</div>
                        </div>
                        <el-input v-else v-model="notesText" type="textarea" :rows="3"
                            placeholder="输入你的观察笔记、交易计划、分析结论..." />
                    </el-card>

                    <!-- ①-b 操作栏（始终显示） -->
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;flex-wrap:wrap;"
                        :style="{ borderLeft: profileData && profileData.risk_passed ? '4px solid #67c23a' : profileData && profileData.risk_passed === false ? '4px solid #f56c6c' : '4px solid #909399', paddingLeft: '10px' }">
                        <el-tag v-if="profileData && profileData.risk_passed === true" type="success" size="small" effect="dark">✅ 通过</el-tag>
                        <el-tag v-else-if="profileData && profileData.risk_passed === false" type="danger" size="small" effect="dark">❌ 禁止买入</el-tag>
                        <el-tag v-else type="info" size="small" effect="dark">⏳ 待分析</el-tag>
                        <b style="font-size:14px;">{{ selected.name }} ({{ selected.code }})</b>
                        <span v-if="profileData?.price" style="color:#909399;font-size:12px;">
                            现价 {{ profileData.price?.toFixed(2) }}
                        </span>
                        <span v-if="profileData?.change_pct !== null && profileData?.change_pct !== undefined" :style="{ color: (profileData.change_pct||0) >= 0 ? '#f56c6c' : '#67c23a', fontSize:'12px' }">
                            {{ (profileData.change_pct||0) >= 0 ? '+' : '' }}{{ (profileData.change_pct||0).toFixed(2) }}%
                        </span>
                        <div style="flex:1"></div>
                        <el-button size="small" @click="goAnalysis">🔍 分析</el-button>
                        <el-button size="small" @click="changePriority">
                            {{ selected.priority === 'high' ? '降为中' : selected.priority === 'medium' ? '升为高' : '升为中' }}
                        </el-button>
                        <el-popconfirm title="确定移除？" @confirm="handleRemove(selected.code)">
                            <template #reference>
                                <el-button size="small" type="danger">移除</el-button>
                            </template>
                        </el-popconfirm>
                    </div>

                    <!-- ①-c 技术面详情（有数据时才显示） -->
                    <el-card v-if="profileData" shadow="hover" style="margin-bottom:12px;">
                        <el-descriptions :column="4" border size="mini">
                            <el-descriptions-item label="行业">{{ profileData.sector || '--' }}</el-descriptions-item>
                            <el-descriptions-item label="MA5">{{ profileData.ma5?.toFixed(2) || '--' }}</el-descriptions-item>
                            <el-descriptions-item label="MA20">{{ profileData.ma20?.toFixed(2) || '--' }}</el-descriptions-item>
                            <el-descriptions-item label="MA60">{{ profileData.ma60?.toFixed(2) || '--' }}</el-descriptions-item>
                            <el-descriptions-item label="MA200">{{ profileData.ma200?.toFixed(2) || '--' }}</el-descriptions-item>
                            <el-descriptions-item label="RSI14">{{ profileData.rsi14 || '--' }}</el-descriptions-item>
                            <el-descriptions-item label="均线多头">
                                <el-tag :type="profileData.bullish_alignment ? 'success' : 'info'" size="small">{{ profileData.bullish_alignment ? '是' : '否' }}</el-tag>
                            </el-descriptions-item>
                            <el-descriptions-item label="关注理由">{{ selected.reason || '--' }}</el-descriptions-item>
                        </el-descriptions>
                    </el-card>
                    <div v-else-if="analyzing" style="text-align:center;padding:30px;">
                        <el-icon class="is-loading" :size="24"><Loading /></el-icon>
                        <p style="color:#909399;font-size:13px;margin-top:8px;">正在分析...</p>
                    </div>
                    <div v-else style="text-align:center;padding:30px;color:#909399;font-size:13px;">
                        点击「立即分析」获取技术面数据
                    </div>
                </template>
            </el-col>

            <!-- ② 中间：选中股票的历次分析记录 -->
            <el-col :span="7">
                <template v-if="!selected">
                    <el-empty description="请先选择一只股票" :image-size="60" />
                </template>

                <template v-else>
                    <el-card shadow="hover" class="panel-history">
                        <template #header>
                            <div style="display:flex;justify-content:space-between;align-items:center;">
                                <b>📋 {{ selected.name }} 历次分析 ({{ stockHistory.length }})</b>
                                <div>
                                    <el-button size="small" type="warning" plain @click="handleSaveSnapshot" :loading="savingSnapshot">💾 保存快照</el-button>
                                    <el-button v-if="stockHistory.length" size="small" type="primary" plain @click="loadStockHistory">刷新</el-button>
                                </div>
                            </div>
                        </template>

                        <div v-if="stockHistory.length" class="scroll-area">
                            <div v-for="(rec, i) in stockHistory" :key="'h' + i"
                                class="history-item"
                                :class="{ 'history-active': detailHist?.code === rec.code && detailHist?.analysis_date === rec.analysis_date }">
                                <div class="history-header">
                                    <el-tag v-if="rec.record_type === 'draft'" size="mini" type="warning" effect="dark">草稿</el-tag>
                                    <el-tag v-else size="mini" type="primary" effect="dark">快照</el-tag>
                                    <el-tag size="mini" :type="rec.risk_passed ? 'success' : 'danger'" effect="dark">
                                        {{ rec.risk_passed ? 'PASS' : 'FAIL' }}
                                    </el-tag>
                                    <el-tag v-if="rec.bullish_alignment" size="mini" type="success" plain>多头</el-tag>
                                    <el-tag v-else size="mini" type="info" plain>空头</el-tag>
                                    <span class="history-date">{{ rec.analysis_date }}</span>
                                    <div style="flex:1"></div>
                                    <el-popconfirm v-if="rec.record_type === 'snapshot'" title="确定删除此快照？" @confirm="handleDeleteSnapshot(rec)">
                                        <template #reference>
                                            <el-button size="mini" type="danger" link @click.stop>删除</el-button>
                                        </template>
                                    </el-popconfirm>
                                    <el-popconfirm v-else title="确定删除此草稿？" @confirm="handleDeleteDraft(rec)">
                                        <template #reference>
                                            <el-button size="mini" type="danger" link @click.stop>删除</el-button>
                                        </template>
                                    </el-popconfirm>
                                </div>
                                <div class="history-meta">
                                    <span style="font-weight:bold;">¥{{ rec.price?.toFixed(2) || '--' }}</span>
                                    <span :style="{ color: (rec.change_pct||0) >= 0 ? '#f56c6c' : '#67c23a' }">
                                        {{ (rec.change_pct||0) >= 0 ? '+' : '' }}{{ rec.change_pct?.toFixed(2) }}%
                                    </span>
                                    <span style="color:#909399;">
                                        MA5:{{ rec.ma5?.toFixed(1) || '--' }} MA20:{{ rec.ma20?.toFixed(1) || '--' }}
                                    </span>
                                    <span style="color:#909399;">RSI:{{ rec.rsi14 || '--' }}</span>
                                </div>
                            </div>
                        </div>

                        <div v-else style="text-align:center;padding:24px;color:#909399;font-size:13px;">
                            <p>暂无分析记录</p>
                            <p style="margin-top:4px;">点击「立即分析」生成第一条</p>
                        </div>
                    </el-card>
                </template>
            </el-col>

            <!-- ③ 右侧：观察池列表 -->
            <el-col :span="6">
                <el-card shadow="hover" class="panel-list">
                    <template #header>
                        <div style="display:flex;justify-content:space-between;align-items:center;">
                            <b>🔭 观察池 ({{ items.length }})</b>
                            <el-button size="small" type="primary" plain @click="showAddDialog = true">+</el-button>
                        </div>
                    </template>
                    <div v-if="items.length" class="scroll-area">
                        <div v-for="item in items" :key="item.code"
                            class="watch-item"
                            :class="'priority-' + item.priority"
                            @click="selectItem(item)"
                            :style="{ background: selected?.code === item.code ? '#ecf5ff' : '' }">
                            <div class="watch-code">
                                <el-tag size="small" :type="pType(item.priority)" effect="dark" style="margin-right:4px;">
                                    {{ pLabel(item.priority) }}
                                </el-tag>
                                {{ item.code }}
                            </div>
                            <div class="watch-name">{{ item.name }}</div>
                            <div class="watch-sector" v-if="item.sector">{{ item.sector }}</div>
                        </div>
                    </div>
                    <el-empty v-else description="观察池为空" :image-size="60" />
                </el-card>
            </el-col>
        </el-row>

        <!-- ==================== 添加股票对话框 ==================== -->
        <el-dialog v-model="showAddDialog" title="➕ 添加股票到观察池" width="480px">
            <el-form :model="form" label-width="60px" @submit.prevent>
                <el-form-item label="搜索">
                    <el-autocomplete
                        v-model="searchText"
                        :fetch-suggestions="querySearch"
                        :trigger-on-focus="false"
                        placeholder="输入代码、名称或拼音首字母搜索"
                        style="width:100%"
                        @select="handleSelect"
                        clearable
                        :debounce="300">
                        <template #default="{ item }">
                            <div style="display:flex;align-items:center;justify-content:space-between;">
                                <div>
                                    <span style="font-weight:bold;">{{ item.code }}</span>
                                    <span style="margin-left:8px;">{{ item.name }}</span>
                                </div>
                                <el-tag size="mini" effect="plain" type="info">
                                    {{ item.pinyin_initials || (item.market||'') }}
                                </el-tag>
                            </div>
                        </template>
                    </el-autocomplete>
                </el-form-item>
                <el-form-item label="代码">
                    <el-input v-model="form.code" disabled placeholder="从搜索中选择" />
                </el-form-item>
                <el-form-item label="名称">
                    <el-input v-model="form.name" disabled placeholder="从搜索中选择" />
                </el-form-item>
                <el-form-item label="优先级">
                    <el-select v-model="form.priority" style="width:100%">
                        <el-option label="🔴 高优先" value="high" />
                        <el-option label="🟡 中优先" value="medium" />
                        <el-option label="🟢 低优先" value="low" />
                    </el-select>
                </el-form-item>
                <el-form-item label="理由"><el-input v-model="form.reason" placeholder="关注理由" /></el-form-item>
            </el-form>
            <template #footer>
                <el-button @click="showAddDialog = false">取消</el-button>
                <el-button type="primary" @click="handleAdd" :disabled="!form.code" :loading="adding">添加</el-button>
            </template>
        </el-dialog>

        <!-- ==================== 历次分析详情对话框 ==================== -->
        <el-dialog v-model="showDetailDialog" :title="detailTitle" width="680px" top="5vh">
            <template v-if="detailHist">
                <!-- 顶部状态 -->
                <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px;flex-wrap:wrap;">
                    <el-tag :type="detailHist.risk_passed ? 'success' : 'danger'" size="medium" effect="dark">
                        {{ detailHist.risk_passed ? '✅ 风控通过' : '❌ 禁止买入' }}
                    </el-tag>
                    <el-tag :type="detailHist.bullish_alignment ? 'success' : 'info'" size="medium">
                        {{ detailHist.bullish_alignment ? '📈 均线多头' : '📉 均线空头' }}
                    </el-tag>
                    <span style="color:#909399;font-size:13px;">分析日期：{{ detailHist.analysis_date }}</span>
                    <span v-if="detailHist.sector" style="color:#909399;font-size:13px;">{{ detailHist.sector }}</span>
                </div>

                <!-- 技术面快照 -->
                <el-card shadow="hover" style="margin-bottom:12px;">
                    <template #header><b>📊 当时技术面快照</b></template>
                    <el-descriptions :column="4" border size="mini">
                        <el-descriptions-item label="当时价">
                            <span style="font-weight:bold;font-size:15px;">¥{{ detailHist.price?.toFixed(2) || '--' }}</span>
                        </el-descriptions-item>
                        <el-descriptions-item label="涨幅">
                            <span :style="{ color: (detailHist.change_pct||0) >= 0 ? '#f56c6c' : '#67c23a', fontWeight:'bold' }">
                                {{ (detailHist.change_pct||0) >= 0 ? '+' : '' }}{{ detailHist.change_pct?.toFixed(2) }}%
                            </span>
                        </el-descriptions-item>
                        <el-descriptions-item label="MA5">{{ detailHist.ma5?.toFixed(2) || '--' }}</el-descriptions-item>
                        <el-descriptions-item label="MA10">{{ detailHist.ma10?.toFixed(2) || '--' }}</el-descriptions-item>
                        <el-descriptions-item label="MA20">{{ detailHist.ma20?.toFixed(2) || '--' }}</el-descriptions-item>
                        <el-descriptions-item label="MA60">{{ detailHist.ma60?.toFixed(2) || '--' }}</el-descriptions-item>
                        <el-descriptions-item label="MA200">{{ detailHist.ma200?.toFixed(2) || '--' }}</el-descriptions-item>
                        <el-descriptions-item label="RSI(14)">{{ detailHist.rsi14 || '--' }}</el-descriptions-item>
                        <el-descriptions-item label="MACD(DIF)">{{ detailHist.macd_dif?.toFixed(4) || '--' }}</el-descriptions-item>
                        <el-descriptions-item label="MACD(DEA)">{{ detailHist.macd_dea?.toFixed(4) || '--' }}</el-descriptions-item>
                        <el-descriptions-item label="MACD(柱)" :span="2">
                            <span :style="{ color: (detailHist.macd_hist||0) >= 0 ? '#f56c6c' : '#67c23a' }">
                                {{ detailHist.macd_hist?.toFixed(4) || '--' }}
                            </span>
                        </el-descriptions-item>
                    </el-descriptions>
                </el-card>

                <!-- 基本面快照 -->
                <el-card v-if="detailHist.revenue || detailHist.net_profit" shadow="hover">
                    <template #header><b>💰 当时基本面快照</b></template>
                    <el-descriptions :column="4" border size="mini">
                        <el-descriptions-item label="营收">{{ detailHist.revenue || '--' }}</el-descriptions-item>
                        <el-descriptions-item label="净利">{{ detailHist.net_profit || '--' }}</el-descriptions-item>
                        <el-descriptions-item label="毛利率">{{ detailHist.gross_margin != null ? detailHist.gross_margin + '%' : '--' }}</el-descriptions-item>
                        <el-descriptions-item label="ROE">{{ detailHist.roe != null ? detailHist.roe + '%' : '--' }}</el-descriptions-item>
                    </el-descriptions>
                </el-card>

                <el-empty v-if="!detailHist.price && !detailHist.ma5" :image-size="40" description="该记录数据不完整" />
            </template>
        </el-dialog>
    </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { getWatchlist, addWatchItem, removeWatchItem, updateWatchItem, getStockProfile, searchStockInfo, saveSnapshot, deleteSnapshot, deleteDraft } from '../api/index.js'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

const router = useRouter()

// ===== 观察池 =====
const items = ref([])
const selected = ref(null)
const adding = ref(false)
const savingSnapshot = ref(false)
const showAddDialog = ref(false)
const form = ref({ code: '', name: '', priority: 'medium', reason: '' })
const searchText = ref('')

// 搜索股票建议（代码/名称/拼音首字母）
async function querySearch(q, cb) {
    if (!q || q.trim().length < 1) return cb([])
    try {
        const { data } = await searchStockInfo(q.trim())
        cb(data.results || [])
    } catch {
        cb([])
    }
}

function handleSelect(item) {
    form.value.code = item.code
    form.value.name = item.name
}

// ===== 备注 =====
const editingNotes = ref(false)
const notesText = ref('')

// ===== 当前分析数据 =====
const profileData = ref(null)
const analyzing = ref(false)

// ===== 选中股票的历次分析记录 =====
const stockHistory = ref([])
const detailHist = ref(null)
const showDetailDialog = ref(false)

onMounted(async () => {
    await loadData()
})

// 打开添加对话框时重置表单
watch(showAddDialog, (v) => {
    if (v) {
        form.value = { code: '', name: '', priority: 'medium', reason: '' }
        searchText.value = ''
    }
})

// ===== 观察池 =====
async function loadData() {
    try {
        const { data } = await getWatchlist()
        items.value = data.items || []
    } catch {
        ElMessage.error('加载观察池失败')
    }
}

function selectItem(item) {
    selected.value = item
    notesText.value = item.notes || ''
    editingNotes.value = false
    profileData.value = null
    stockHistory.value = []
    detailHist.value = null

    // 加载当前分析 + 历次分析
    loadProfile()
    loadStockHistory()
}

function pType(p) {
    return p === 'high' ? 'danger' : p === 'medium' ? 'warning' : 'info'
}
function pLabel(p) {
    return p === 'high' ? '高' : p === 'medium' ? '中' : '低'
}

async function handleAdd() {
    if (!form.value.code || !form.value.name) {
        ElMessage.warning('请填写代码和名称')
        return
    }
    adding.value = true
    try {
        await addWatchItem(form.value)
        ElMessage.success('添加成功')
        form.value = { code: '', name: '', priority: 'medium', reason: '' }
        showAddDialog.value = false
        await loadData()
    } catch (e) {
        ElMessage.error(e.response?.data?.detail || '添加失败')
    } finally {
        adding.value = false
    }
}

async function handleRemove(code) {
    try {
        await removeWatchItem(code)
        ElMessage.success('已移除')
        if (selected.value?.code === code) {
            selected.value = null
            profileData.value = null
            stockHistory.value = []
        }
        await loadData()
    } catch {
        ElMessage.error('移除失败')
    }
}

function goAnalysis() {
    if (!selected.value?.code) return
    router.push({ path: '/analysis', query: { code: selected.value.code } })
}

async function changePriority() {
    if (!selected.value) return
    const cur = selected.value.priority
    const next = cur === 'high' ? 'medium' : cur === 'medium' ? 'low' : 'high'
    try {
        await updateWatchItem(selected.value.code, next)
        selected.value.priority = next
        await loadData()
    } catch {
        ElMessage.error('更新失败')
    }
}

// ===== 备注 =====
function startEditNotes() {
    notesText.value = selected.value.notes || ''
    editingNotes.value = true
}
function cancelEditNotes() {
    editingNotes.value = false
    notesText.value = selected.value.notes || ''
}
async function saveNotes() {
    if (!selected.value) return
    try {
        await updateWatchItem(selected.value.code, selected.value.priority, notesText.value.trim())
        selected.value.notes = notesText.value.trim()
        editingNotes.value = false
        ElMessage.success('备注已保存')
        await loadData()
    } catch {
        ElMessage.error('保存失败')
    }
}

// ===== 分析 =====
async function loadProfile() {
    if (!selected.value?.code) return
    analyzing.value = true
    profileData.value = null
    try {
        const { data } = await getStockProfile(selected.value.code)
        profileData.value = data
        // profileData.analysis_history 里也包含历次记录，提取出来
        if (data.analysis_history?.length) {
            stockHistory.value = data.analysis_history
        }
    } catch {
        // 静默
    } finally {
        analyzing.value = false
    }
}

async function handleSaveSnapshot() {
    if (!selected.value?.code || !profileData.value) {
        ElMessage.warning('请先分析该股票')
        return
    }
    savingSnapshot.value = true
    try {
        const analysisData = {
            technical: profileData.value,
            fundamental: profileData.value,
            risk_check: { passed: profileData.value.risk_passed },
        }
        await saveSnapshot(selected.value.code, {
            name: selected.value.name,
            sector: profileData.value.sector || '',
            analysis_data: analysisData,
        })
        ElMessage.success('快照已保存')
        await loadStockHistory()
    } catch (e) {
        ElMessage.error(e.response?.data?.detail || '保存快照失败')
    } finally {
        savingSnapshot.value = false
    }
}

async function handleDeleteSnapshot(rec) {
    try {
        await deleteSnapshot(selected.value.code, rec.snapshot_id)
        ElMessage.success('快照已删除')
        stockHistory.value = stockHistory.value.filter(r => !(r.record_type === 'snapshot' && r.snapshot_id === rec.snapshot_id))
    } catch (e) {
        ElMessage.error(e.response?.data?.detail || '删除失败')
    }
}

async function handleDeleteDraft(rec) {
    try {
        await deleteDraft(selected.value.code, rec.analysis_date)
        ElMessage.success('草稿已删除')
        stockHistory.value = stockHistory.value.filter(r => !(r.record_type === 'draft' && r.analysis_date === rec.analysis_date && r.code === rec.code))
    } catch (e) {
        ElMessage.error(e.response?.data?.detail || '删除失败')
    }
}

async function refreshAnalysis() {
    if (!selected.value?.code) return
    analyzing.value = true
    try {
        const { data } = await getStockProfile(selected.value.code)
        profileData.value = data
        ElMessage.success('分析已完成')
        // 从profile结果中提取历次分析记录
        if (data.analysis_history?.length) {
            stockHistory.value = data.analysis_history
        } else {
            await loadStockHistory()
        }
    } catch {
        ElMessage.error('分析失败')
    } finally {
        analyzing.value = false
    }
}

// ===== 历次分析记录（从 profile API 的 analysis_history 提取） =====
async function loadStockHistory() {
    if (!selected.value?.code) return
    // 如果已经有 profileData 且有 analysis_history，直接用
    if (profileData.value?.analysis_history?.length) {
        stockHistory.value = profileData.value.analysis_history
        return
    }
    // 否则重新请求 profile
    try {
        const { data } = await getStockProfile(selected.value.code)
        if (data.analysis_history?.length) {
            stockHistory.value = data.analysis_history
        }
    } catch {
        // 静默
    }
}

function showDetail(rec) {
    detailHist.value = rec
    showDetailDialog.value = true
}

const detailTitle = computed(() => {
    if (!detailHist.value) return '分析详情'
    return `📋 ${detailHist.value.name} (${detailHist.value.code}) — ${detailHist.value.analysis_date}`
})
</script>

<style scoped>
.watchlist-page { max-width: 1500px; margin: 0 auto; }
.panel-list { min-height: 500px; }
.panel-history { min-height: 500px; }

.scroll-area {
    max-height: 620px; overflow-y: auto;
}

/* 观察池列表 */
.watch-item {
    padding: 10px 8px;
    border-bottom: 1px solid #f0f0f0;
    cursor: pointer;
    border-left: 3px solid transparent;
    transition: background 0.2s;
}
.watch-item:hover { background: #f5f7fa; }
.watch-item.priority-high { border-left-color: #f56c6c; }
.watch-item.priority-medium { border-left-color: #e6a23c; }
.watch-item.priority-low { border-left-color: #909399; }
.watch-code { font-size: 13px; font-weight: bold; color: #303133; display: flex; align-items: center; }
.watch-name { font-size: 12px; color: #606266; margin-top: 2px; }
.watch-sector { font-size: 11px; color: #909399; margin-top: 1px; }

/* 历次分析列表 */
.history-item {
    padding: 10px 8px;
    border-bottom: 1px solid #f0f0f0;
    cursor: pointer;
    transition: background 0.15s;
    border-left: 3px solid transparent;
}
.history-item:hover { background: #f5f7fa; border-left-color: #409eff; }
.history-active {
    background: #ecf5ff;
    border-left-color: #409eff;
}
.history-header {
    display: flex; align-items: center; gap: 4px;
    font-size: 12px; margin-bottom: 4px;
}
.history-date {
    margin-left: auto;
    color: #909399;
    font-size: 11px;
}
.history-meta {
    display: flex; align-items: center; gap: 8px;
    font-size: 11px; color: #606266; flex-wrap: wrap;
}
</style>
