<template>
    <div class="trading-plans-page">
        <!-- 顶部操作栏 -->
        <el-card shadow="never" style="margin-bottom:12px;">
            <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
                <b style="font-size:16px;">📋 交易计划</b>
                <el-radio-group v-model="statusFilter" size="small" @change="loadPlans">
                    <el-radio-button value="">全部</el-radio-button>
                    <el-radio-button value="draft">📝 草稿</el-radio-button>
                    <el-radio-button value="monitoring">👀 监控中</el-radio-button>
                    <el-radio-button value="entered">📌 已入场</el-radio-button>
                    <el-radio-button value="exited">✅ 已退出</el-radio-button>
                    <el-radio-button value="cancelled">❌ 已取消</el-radio-button>
                </el-radio-group>
                <div style="flex:1"></div>
                <el-button type="primary" size="small" @click="showCreateDialog = true">+ 新建计划</el-button>
            </div>
        </el-card>

        <!-- 计划列表 -->
        <div v-loading="loading">
            <el-empty v-if="!loading && !plans.length" description="暂无交易计划，点击「+ 新建计划」开始" :image-size="80" />

            <div v-for="plan in plans" :key="plan.id" class="plan-card" @click="selectPlan(plan)">
                <el-card shadow="hover" :style="{ borderLeft: `4px solid ${statusColor(plan.status)}`, cursor:'pointer', marginBottom:'8px' }">
                    <div style="display:flex;align-items:center;justify-content:space-between;">
                        <div style="display:flex;align-items:center;gap:8px;">
                            <el-tag :type="plan.direction === 'long' ? 'danger' : 'success'" size="small" effect="dark">
                                {{ plan.direction === 'long' ? '📈 做多' : '📉 做空' }}
                            </el-tag>
                            <b>{{ plan.name || plan.code }}</b>
                            <span style="color:#909399;font-size:12px;">{{ plan.code }}</span>
                            <el-tag :type="statusTag(plan.status)" size="small">{{ statusLabel(plan.status) }}</el-tag>
                        </div>
                        <div style="display:flex;align-items:center;gap:12px;font-size:12px;color:#909399;">
                            <span v-if="plan.entry_price">入场目标 ¥{{ plan.entry_price.toFixed(2) }}</span>
                            <span v-if="plan.stop_loss">止损 ¥{{ plan.stop_loss.toFixed(2) }}</span>
                            <span v-if="plan.take_profit">止盈 ¥{{ plan.take_profit.toFixed(2) }}</span>
                            <span>{{ plan.updated_at?.slice(5,16) || '' }}</span>
                        </div>
                    </div>
                </el-card>
            </div>
        </div>

        <!-- ===== 新建计划弹窗 ===== -->
        <el-dialog v-model="showCreateDialog" title="📋 新建交易计划" width="560px" :close-on-click-modal="false">
            <el-form label-width="80px" size="small">
                <el-form-item label="股票">
                    <el-autocomplete v-model="newPlan.code" :fetch-suggestions="searchStocks"
                        placeholder="输入代码/名称搜索" style="width:100%"
                        @select="(item) => { newPlan.code = item.code; newPlan.name = item.name; loadSR() }"
                        @change="() => { if(newPlan.code && newPlan.code.length>=2) loadSR() }"
                        clearable />
                </el-form-item>

                <!-- K线分析面板（加载后显示） -->
                <div v-if="srLoading" style="text-align:center;padding:12px;color:#909399;">
                    <el-icon class="is-loading" style="vertical-align:middle;"><i class="el-icon-loading"></i></el-icon>
                    <span style="margin-left:6px;">计算支撑/阻力中...</span>
                </div>
                <el-card v-else-if="srResult?.current_price" shadow="never" style="margin-bottom:12px;" :style="{ borderLeft: '4px solid ' + (srResult.risk_reward_ratio >= 2 ? '#67c23a' : '#e6a23c') }">
                    <div style="font-size:13px;">
                        <!-- 现价 + 盈亏比 -->
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                            <span><b>现价</b> ¥{{ srResult.current_price }}</span>
                            <span v-if="srResult.atr"><b>ATR(14)</b> ¥{{ srResult.atr }}</span>
                            <el-tag v-if="srResult.risk_reward_ratio > 0"
                                :type="srResult.risk_reward_ratio >= 2 ? 'success' : srResult.risk_reward_ratio >= 1 ? 'warning' : 'danger'"
                                size="small" effect="dark">
                                预期盈亏比 {{ srResult.risk_reward_ratio }}:1
                            </el-tag>
                        </div>

                        <!-- 均线信息 -->
                        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px;font-size:12px;">
                            <el-tag v-if="srResult.ma5" size="mini" type="info">MA5 {{ srResult.ma5 }}</el-tag>
                            <el-tag v-if="srResult.ma10" size="mini" type="info">MA10 {{ srResult.ma10 }}</el-tag>
                            <el-tag v-if="srResult.ma20" size="mini" type="info">MA20 {{ srResult.ma20 }}</el-tag>
                            <el-tag v-if="srResult.ma60" size="mini" type="info">MA60 {{ srResult.ma60 }}</el-tag>
                            <el-tag v-if="srResult.bollinger?.upper" size="mini" type="info">布林上 {{ srResult.bollinger.upper }}</el-tag>
                            <el-tag v-if="srResult.bollinger?.lower" size="mini" type="info">布林下 {{ srResult.bollinger.lower }}</el-tag>
                        </div>

                        <!-- 支撑位 -->
                        <div style="margin-bottom:6px;">
                            <span style="color:#67c23a;font-weight:bold;">▽ 支撑位</span>
                            <div style="display:flex;gap:4px;flex-wrap:wrap;margin-top:3px;">
                                <el-tag v-for="s in srResult.support_levels" :key="s" size="small" type="success" effect="plain"
                                    style="cursor:pointer;" @click="applySR('stop_loss', s)">
                                    ¥{{ s }}
                                </el-tag>
                                <span v-if="!srResult.support_levels?.length" style="color:#909399;">—</span>
                            </div>
                        </div>

                        <!-- 阻力位 -->
                        <div style="margin-bottom:6px;">
                            <span style="color:#f56c6c;font-weight:bold;">△ 阻力位</span>
                            <div style="display:flex;gap:4px;flex-wrap:wrap;margin-top:3px;">
                                <el-tag v-for="r in srResult.resistance_levels" :key="r" size="small" type="danger" effect="plain"
                                    style="cursor:pointer;" @click="applySR('take_profit', r)">
                                    ¥{{ r }}
                                </el-tag>
                                <span v-if="!srResult.resistance_levels?.length" style="color:#909399;">—</span>
                            </div>
                        </div>

                        <!-- 推荐方案 + 一键应用 -->
                        <div v-if="srResult.suggested_entry > 0" style="background:#f5f7fa;border-radius:6px;padding:8px;margin-top:6px;">
                            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                                <b style="font-size:13px;">📌 推荐方案</b>
                                <el-button size="small" type="primary" plain @click="applyAllSR">一键应用</el-button>
                            </div>
                            <div style="display:flex;gap:16px;font-size:12px;flex-wrap:wrap;">
                                <span>入场 <b style="color:#409eff;">¥{{ srResult.suggested_entry }}</b></span>
                                <span>止损 <b style="color:#f56c6c;">¥{{ srResult.suggested_stop_loss }}</b></span>
                                <span>止盈 <b style="color:#67c23a;">¥{{ srResult.suggested_take_profit }}</b></span>
                                <span v-if="srResult.risk_reward_ratio > 0">
                                    盈亏比 <b :style="{ color: srResult.risk_reward_ratio >= 2 ? '#67c23a' : '#e6a23c' }">{{ srResult.risk_reward_ratio }}:1</b>
                                </span>
                            </div>
                            <div v-if="srResult.notes" style="font-size:11px;color:#909399;margin-top:4px;">
                                {{ srResult.notes }}
                            </div>
                        </div>

                        <!-- K线形态卡片 -->
                        <div v-if="srResult.kline_patterns?.length" style="margin-top:8px;padding:8px 10px;background:#fdf6ec;border-radius:6px;border:1px solid #faecd8;">
                            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                                <b style="font-size:13px;">🕯️ K线形态分析</b>
                                <el-tag v-if="bullishCount > 0 && bearishCount === 0" size="mini" type="success">偏多</el-tag>
                                <el-tag v-else-if="bearishCount > 0 && bullishCount === 0" size="mini" type="danger">偏空</el-tag>
                                <el-tag v-else size="mini" type="info">中性</el-tag>
                            </div>
                            <div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:6px;">
                                <el-tag v-for="(p, i) in srResult.kline_patterns" :key="i"
                                    :type="p.direction === 'bullish' ? 'success' : p.direction === 'bearish' ? 'danger' : 'info'"
                                    size="small" effect="plain" style="cursor:default;">
                                    {{ p.pattern }}
                                    <el-tooltip :content="p.description" placement="top">
                                        <span style="margin-left:2px;cursor:help;opacity:0.6;">ⓘ</span>
                                    </el-tooltip>
                                </el-tag>
                            </div>
                            <!-- 形态推荐入场 -->
                            <div v-if="srResult.pattern_recommended_entry" style="display:flex;gap:12px;font-size:12px;flex-wrap:wrap;background:#fff;border-radius:4px;padding:6px;">
                                <span>形态推荐入场 <b style="color:#409eff;">¥{{ srResult.pattern_recommended_entry }}</b></span>
                                <span>止损 <b style="color:#f56c6c;">¥{{ srResult.pattern_stop_loss }}</b></span>
                                <el-button size="mini" type="warning" plain @click="applyPatternSR" style="margin-left:auto;">
                                    按形态入场
                                </el-button>
                            </div>
                            <div v-if="srResult.pattern_description" style="font-size:11px;color:#909399;margin-top:4px;">
                                {{ srResult.pattern_description }}
                            </div>
                        </div>
                    </div>
                </el-card>
                <!-- K线图 -->
                <div v-if="srResult?.kline_data?.length" style="margin-bottom:12px;border-radius:6px;overflow:hidden;">
                    <div ref="klineChartRef" style="width:100%;height:400px;"></div>
                </div>
                <div v-else-if="srError" style="text-align:center;padding:8px;color:#909399;font-size:12px;">
                    {{ srError }}
                </div>

                <el-form-item label="方向">
                    <el-radio-group v-model="newPlan.direction" @change="loadSR">
                        <el-radio value="long">📈 做多</el-radio>
                        <el-radio value="short">📉 做空</el-radio>
                    </el-radio-group>
                </el-form-item>
                <el-row :gutter="12">
                    <el-col :span="8">
                        <el-form-item label="入场价"><el-input-number v-model="newPlan.entry_price" :min="0" :step="0.01" :precision="2" style="width:100%" /></el-form-item>
                    </el-col>
                    <el-col :span="8">
                        <el-form-item label="止损价"><el-input-number v-model="newPlan.stop_loss" :min="0" :step="0.01" :precision="2" style="width:100%" /></el-form-item>
                    </el-col>
                    <el-col :span="8">
                        <el-form-item label="止盈价"><el-input-number v-model="newPlan.take_profit" :min="0" :step="0.01" :precision="2" style="width:100%" /></el-form-item>
                    </el-col>
                </el-row>
                <el-form-item label="数量"><el-input-number v-model="newPlan.plan_quantity" :min="0" :step="100" style="width:100%" /></el-form-item>
                <el-form-item label="入场理由"><el-input v-model="newPlan.entry_reason" type="textarea" :rows="2" placeholder="为什么在这个位置入场？" /></el-form-item>
                <el-form-item label="K线观察"><el-input v-model="newPlan.kline_notes" type="textarea" :rows="2" placeholder="K线形态、均线排列、技术指标观察..." /></el-form-item>
            </el-form>
            <template #footer>
                <el-button @click="showCreateDialog = false">取消</el-button>
                <el-button type="primary" @click="handleCreate" :loading="saving">创建计划</el-button>
            </template>
        </el-dialog>

        <!-- ===== 计划详情抽屉 ===== -->
        <el-drawer v-model="showDetail" :title="detailPlan?.name || detailPlan?.code" size="600px" :close-on-click-modal="false">
            <template v-if="detailPlan">
                <!-- 状态栏 -->
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:16px;flex-wrap:wrap;">
                    <el-tag :type="detailPlan.direction === 'long' ? 'danger' : 'success'" size="small" effect="dark">
                        {{ detailPlan.direction === 'long' ? '📈 做多' : '📉 做空' }}
                    </el-tag>
                    <el-tag :type="statusTag(detailPlan.status)" size="small">{{ statusLabel(detailPlan.status) }}</el-tag>
                    <span style="color:#909399;font-size:12px;">{{ detailPlan.code }}</span>
                    <span style="color:#909399;font-size:12px;">创建于 {{ detailPlan.created_at?.slice(0,10) }}</span>
                    <div style="flex:1"></div>
                    <el-button size="small" @click="goAnalysis(detailPlan.code)">🔍 K线分析</el-button>
                    <el-button size="small" @click="refreshSignals" :loading="signalLoading">🔄 刷新信号</el-button>
                </div>

                <!-- 信号区域 -->
                <el-card v-if="signals" shadow="hover" style="margin-bottom:12px;"
                    :style="{ borderLeft: `4px solid ${signalBorderColor}` }">
                    <template #header>
                        <div style="display:flex;justify-content:space-between;">
                            <b>📡 信号监控</b>
                            <span style="font-size:12px;color:#909399;">现价 ¥{{ signals.current_price?.toFixed(2) }}</span>
                        </div>
                    </template>
                    <div v-if="signals.signals?.length">
                        <div v-for="(s, i) in signals.signals" :key="i"
                            style="display:flex;align-items:center;gap:6px;padding:4px 0;font-size:13px;border-bottom:1px solid #f0f0f0;">
                            <el-tag :type="s.level === 'danger' ? 'danger' : s.level === 'warning' ? 'warning' : s.level === 'success' ? 'success' : 'info'"
                                size="mini" effect="dark" style="font-size:10px;">
                                {{ s.type === 'bullish' ? '📈 多' : s.type === 'bearish' ? '📉 空' : '⚪' }}
                            </el-tag>
                            <span>{{ s.text }}</span>
                        </div>
                    </div>
                    <div v-else style="color:#909399;font-size:13px;">暂无信号数据（需先有K线数据）</div>
                </el-card>

                <!-- 价格信息 -->
                <el-card shadow="hover" style="margin-bottom:12px;">
                    <template #header><b>💰 价格计划</b></template>
                    <el-row :gutter="12">
                        <el-col :span="8" v-for="item in priceItems" :key="item.label" style="text-align:center;">
                            <div style="font-size:12px;color:#909399;">{{ item.label }}</div>
                            <div :style="{ fontSize:'18px', fontWeight:'bold', color: item.color }">{{ item.value }}</div>
                        </el-col>
                    </el-row>
                    <!-- 风报比 -->
                    <div v-if="detailPlan.entry_price && detailPlan.stop_loss && detailPlan.take_profit" style="margin-top:8px;font-size:12px;color:#909399;">
                        风报比: 1 : {{ ((detailPlan.take_profit - detailPlan.entry_price) / (detailPlan.entry_price - detailPlan.stop_loss)).toFixed(2) }}
                        &nbsp;·&nbsp; 止损幅度: {{ ((detailPlan.entry_price - detailPlan.stop_loss) / detailPlan.entry_price * 100).toFixed(1) }}%
                        &nbsp;·&nbsp; 止盈幅度: {{ ((detailPlan.take_profit - detailPlan.entry_price) / detailPlan.entry_price * 100).toFixed(1) }}%
                    </div>
                </el-card>

                <!-- 入场理由 -->
                <el-card v-if="detailPlan.entry_reason" shadow="hover" style="margin-bottom:12px;">
                    <template #header><b>📝 入场理由</b></template>
                    <div style="font-size:13px;white-space:pre-wrap;">{{ detailPlan.entry_reason }}</div>
                </el-card>

                <!-- K线观察 -->
                <el-card v-if="detailPlan.kline_notes" shadow="hover" style="margin-bottom:12px;">
                    <template #header><b>🕯️ K线形态观察</b></template>
                    <div style="font-size:13px;white-space:pre-wrap;">{{ detailPlan.kline_notes }}</div>
                </el-card>

                <!-- 操作按钮 -->
                <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:16px;">
                    <el-button v-if="detailPlan.status === 'draft'" type="warning" size="small" @click="changeStatus('monitoring')">👀 开始监控</el-button>
                    <el-button v-if="detailPlan.status === 'monitoring' || detailPlan.status === 'draft'" type="success" size="small" @click="showEnterDialog = true">📌 标记入场</el-button>
                    <el-button v-if="detailPlan.status === 'entered'" type="primary" size="small" @click="showExitDialog = true">✅ 标记退出</el-button>
                    <el-button v-if="detailPlan.status !== 'exited' && detailPlan.status !== 'cancelled'" type="info" size="small" plain @click="changeStatus('cancelled')">❌ 取消计划</el-button>
                    <el-popconfirm title="确定删除？" @confirm="handleDelete">
                        <template #reference>
                            <el-button type="danger" size="small" link>删除</el-button>
                        </template>
                    </el-popconfirm>
                </div>

                <!-- 实际入场 form -->
                <el-dialog v-model="showEnterDialog" title="📌 标记入场" width="380px" append-to-body>
                    <el-form label-width="80px" size="small">
                        <el-form-item label="入场价"><el-input-number v-model="enterForm.price" :min="0.01" :step="0.01" :precision="2" style="width:100%" /></el-form-item>
                        <el-form-item label="入场日期"><el-input v-model="enterForm.date" placeholder="YYYY-MM-DD" /></el-form-item>
                        <el-form-item label="入场数量"><el-input-number v-model="enterForm.qty" :min="0" :step="100" style="width:100%" /></el-form-item>
                    </el-form>
                    <template #footer>
                        <el-button @click="showEnterDialog = false">取消</el-button>
                        <el-button type="primary" @click="handleEnter">确认入场</el-button>
                    </template>
                </el-dialog>

                <!-- 实际退出 form -->
                <el-dialog v-model="showExitDialog" title="✅ 标记退出" width="380px" append-to-body>
                    <el-form label-width="80px" size="small">
                        <el-form-item label="退出价"><el-input-number v-model="exitForm.price" :min="0.01" :step="0.01" :precision="2" style="width:100%" /></el-form-item>
                        <el-form-item label="退出日期"><el-input v-model="exitForm.date" placeholder="YYYY-MM-DD" /></el-form-item>
                        <el-form-item label="退出理由"><el-input v-model="exitForm.reason" type="textarea" :rows="2" placeholder="为什么退出？" /></el-form-item>
                    </el-form>
                    <template #footer>
                        <el-button @click="showExitDialog = false">取消</el-button>
                        <el-button type="primary" @click="handleExit">确认退出</el-button>
                    </template>
                </el-dialog>
            </template>
        </el-drawer>
    </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route = useRoute()
const API = '/api/v1'

const loading = ref(false)
const plans = ref([])
const statusFilter = ref('')

// 创建计划
const showCreateDialog = ref(false)
const saving = ref(false)
const newPlan = ref({ code: '', name: '', direction: 'long', entry_price: 0, stop_loss: 0, take_profit: 0, plan_quantity: 0, entry_reason: '', kline_notes: '' })
// 支撑/阻力分析
const srLoading = ref(false)
const srResult = ref(null)
const srError = ref('')

// 详情
const showDetail = ref(false)
const detailPlan = ref(null)
const signals = ref(null)
const signalLoading = ref(false)

// 入场/退出
const showEnterDialog = ref(false)
const enterForm = ref({ price: 0, date: '', qty: 0 })
const showExitDialog = ref(false)
const exitForm = ref({ price: 0, date: '', reason: '' })

// K线图表
const klineChartRef = ref(null)
let klineChartInstance = null

// ===== 工具函数 =====
const STATUS_MAP = { draft: '📝 草稿', monitoring: '👀 监控中', entered: '📌 已入场', exited: '✅ 已退出', cancelled: '❌ 已取消' }
const STATUS_TAG = { draft: 'info', monitoring: 'warning', entered: 'success', exited: '', cancelled: 'danger' }
const STATUS_COLOR = { draft: '#909399', monitoring: '#e6a23c', entered: '#67c23a', exited: '#409eff', cancelled: '#f56c6c' }

function statusLabel(s) { return STATUS_MAP[s] || s }
function statusTag(s) { return STATUS_TAG[s] || 'info' }
function statusColor(s) { return STATUS_COLOR[s] || '#909399' }

const priceItems = computed(() => {
    if (!detailPlan.value) return []
    const items = [
        { label: '目标入场', value: detailPlan.value.entry_price ? `¥${detailPlan.value.entry_price.toFixed(2)}` : '--', color: '#409eff' },
        { label: '止损', value: detailPlan.value.stop_loss ? `¥${detailPlan.value.stop_loss.toFixed(2)}` : '--', color: detailPlan.value.stop_loss ? '#f56c6c' : '#909399' },
        { label: '止盈', value: detailPlan.value.take_profit ? `¥${detailPlan.value.take_profit.toFixed(2)}` : '--', color: detailPlan.value.take_profit ? '#67c23a' : '#909399' },
    ]
    if (detailPlan.value.actual_entry_price) {
        items.push({ label: '实际入场', value: `¥${detailPlan.value.actual_entry_price.toFixed(2)}`, color: '#e6a23c' })
    }
    if (detailPlan.value.actual_exit_price) {
        items.push({ label: '实际退出', value: `¥${detailPlan.value.actual_exit_price.toFixed(2)}`, color: '#909399' })
    }
    return items
})

const signalBorderColor = computed(() => {
    if (!signals.value) return '#909399'
    if (signals.value.exit_signal === 'triggered') return '#f56c6c'
    if (signals.value.entry_signal === 'triggered') return '#67c23a'
    return '#909399'
})

// K线形态计数（在创建弹窗中显示方向标签）
const bullishCount = computed(() => srResult.value?.kline_patterns?.filter(p => p.direction === 'bullish')?.length || 0)
const bearishCount = computed(() => srResult.value?.kline_patterns?.filter(p => p.direction === 'bearish')?.length || 0)

// ===== API 调用 =====

async function loadPlans() {
    loading.value = true
    try {
        const params = new URLSearchParams()
        if (statusFilter.value) params.set('status', statusFilter.value)
        const res = await fetch(`${API}/trading-plans?${params}`)
        const data = await res.json()
        plans.value = data.plans || []
    } catch { ElMessage.error('加载计划失败') }
    finally { loading.value = false }
}

const stockSearchCache = {}
async function searchStocks(query, cb) {
    if (!query || query.trim().length < 1) { cb([]); return }
    const q = query.trim()
    if (stockSearchCache[q]) { cb(stockSearchCache[q]); return }
    try {
        const res = await fetch(`/api/v1/stock-info/search?q=${encodeURIComponent(q)}&limit=15`)
        const data = await res.json()
        const items = (data.results || []).map(r => ({
            value: `${r.code} ${r.name}`,
            code: r.code,
            name: r.name,
        }))
        stockSearchCache[q] = items
        cb(items)
    } catch { cb([]) }
}

// ===== 支撑/阻力分析 =====
async function loadSR() {
    const code = newPlan.value.code?.trim()
    const direction = newPlan.value.direction
    if (!code || code.length < 2) return
    srLoading.value = true
    srError.value = ''
    try {
        const res = await fetch(`/api/v1/trading-plans/support-resistance/${encodeURIComponent(code)}?direction=${direction}`)
        srResult.value = await res.json()
    } catch {
        srError.value = '加载K线数据失败'
        srResult.value = null
    } finally { srLoading.value = false }
}
function applySR(field, value) {
    if (field === 'stop_loss') newPlan.value.stop_loss = value
    else if (field === 'take_profit') newPlan.value.take_profit = value
}
function applyAllSR() {
    if (!srResult.value) return
    newPlan.value.entry_price = srResult.value.suggested_entry || 0
    newPlan.value.stop_loss = srResult.value.suggested_stop_loss || 0
    newPlan.value.take_profit = srResult.value.suggested_take_profit || 0
}
function applyPatternSR() {
    if (!srResult.value) return
    newPlan.value.entry_price = srResult.value.pattern_recommended_entry || 0
    newPlan.value.stop_loss = srResult.value.pattern_stop_loss || 0
}

async function handleCreate() {
    if (!newPlan.value.code) { ElMessage.warning('请选择股票'); return }
    saving.value = true
    try {
        await (await fetch(`${API}/trading-plans`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(newPlan.value),
        })).json()
        ElMessage.success('交易计划已创建')
        showCreateDialog.value = false
        newPlan.value = { code: '', name: '', direction: 'long', entry_price: 0, stop_loss: 0, take_profit: 0, plan_quantity: 0, entry_reason: '', kline_notes: '' }
        srResult.value = null
        srError.value = ''
        await loadPlans()
    } catch { ElMessage.error('创建失败') }
    finally { saving.value = false }
}

async function selectPlan(plan) {
    detailPlan.value = plan
    showDetail.value = true
    signals.value = null
    enterForm.value = { price: plan.entry_price || 0, date: new Date().toISOString().slice(0, 10), qty: plan.plan_quantity || 0 }
    exitForm.value = { price: plan.actual_exit_price || 0, date: new Date().toISOString().slice(0, 10), reason: '' }
    await refreshSignals()
}

async function refreshSignals() {
    if (!detailPlan.value?.id) return
    signalLoading.value = true
    try {
        const res = await fetch(`${API}/trading-plans/${detailPlan.value.id}/signals`)
        const data = await res.json()
        signals.value = data
    } catch { /* 无K线数据时静默失败 */ }
    finally { signalLoading.value = false }
}

async function changeStatus(status) {
    try {
        await (await fetch(`${API}/trading-plans/${detailPlan.value.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status }),
        })).json()
        ElMessage.success(`状态已更新为${statusLabel(status)}`)
        await loadPlans()
        detailPlan.value.status = status
    } catch { ElMessage.error('更新失败') }
}

async function handleEnter() {
    const f = enterForm.value
    try {
        await (await fetch(`${API}/trading-plans/${detailPlan.value.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: 'entered', actual_entry_price: f.price, entry_date: f.date, plan_quantity: f.qty }),
        })).json()
        ElMessage.success('已标记入场')
        showEnterDialog.value = false
        await loadPlans()
        detailPlan.value.status = 'entered'
        detailPlan.value.actual_entry_price = f.price
        detailPlan.value.entry_date = f.date
        await refreshSignals()
    } catch { ElMessage.error('操作失败') }
}

async function handleExit() {
    const f = exitForm.value
    try {
        await (await fetch(`${API}/trading-plans/${detailPlan.value.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: 'exited', actual_exit_price: f.price, exit_date: f.date, exit_reason: f.reason }),
        })).json()
        ElMessage.success('已标记退出')
        showExitDialog.value = false
        await loadPlans()
        detailPlan.value.status = 'exited'
        detailPlan.value.actual_exit_price = f.price
        detailPlan.value.exit_reason = f.reason
    } catch { ElMessage.error('操作失败') }
}

async function handleDelete() {
    try {
        await (await fetch(`${API}/trading-plans/${detailPlan.value.id}`, { method: 'DELETE' })).json()
        ElMessage.success('已删除')
        showDetail.value = false
        await loadPlans()
    } catch { ElMessage.error('删除失败') }
}

function goAnalysis(code) {
    router.push({ path: '/analysis', query: { code } })
}

// ===== K线图表渲染 =====
function renderKlineChart() {
    const sr = srResult.value
    if (!sr?.kline_data?.length) return
    nextTick(() => {
        const el = klineChartRef.value
        if (!el) return
        if (klineChartInstance) { klineChartInstance.dispose(); klineChartInstance = null }
        klineChartInstance = echarts.init(el, null, { renderer: 'canvas' })

        const data = sr.kline_data
        const dates = data.map(r => r.date.slice(5))
        const opens = data.map(r => r.open)
        const closes = data.map(r => r.close)
        const highs = data.map(r => r.high)
        const lows = data.map(r => r.low)
        const vols = data.map(r => r.volume)

        // 均线
        function calcMA(arr, period) {
            const result = []
            for (let i = 0; i < arr.length; i++) {
                if (i < period - 1) { result.push('-'); continue }
                const sum = arr.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0)
                result.push(+(sum / period).toFixed(2))
            }
            return result
        }
        const ma5 = calcMA(closes, 5)
        const ma10 = calcMA(closes, 10)
        const ma20 = calcMA(closes, 20)
        const ma60 = calcMA(closes, 60)

        // markLines (K线区域)
        function makeMarkLine(price, label, color, lineStyle) {
            return {
                silent: true,
                symbol: 'none',
                data: [{ yAxis: price, label: { formatter: label + ' ¥' + price, color: color, fontSize: 10 }, lineStyle: { color, ...lineStyle } }]
            }
        }

        const markLines = []
        // 支撑线（绿色虚线）
        for (const s of (sr.support_levels || [])) {
            markLines.push(makeMarkLine(s, '支撑', '#67c23a', { type: 'dashed', width: 1, opacity: 0.7 }))
        }
        // 阻力线（红色虚线）
        for (const r of (sr.resistance_levels || [])) {
            markLines.push(makeMarkLine(r, '阻力', '#f56c6c', { type: 'dashed', width: 1, opacity: 0.7 }))
        }
        // 推荐入场（蓝色实线）
        if (sr.suggested_entry > 0) {
            markLines.push(makeMarkLine(sr.suggested_entry, '入场', '#409eff', { width: 2 }))
        }
        // 止损（红色实线）
        if (sr.suggested_stop_loss > 0) {
            markLines.push(makeMarkLine(sr.suggested_stop_loss, '止损', '#f56c6c', { width: 2 }))
        }
        // 止盈（绿色实线）
        if (sr.suggested_take_profit > 0) {
            markLines.push(makeMarkLine(sr.suggested_take_profit, '止盈', '#67c23a', { width: 2 }))
        }

        const candlestickData = data.map(r => [r.open, r.close, r.low, r.high])

        const option = {
            backgroundColor: '#1a1a2e',
            animation: false,
            grid: [
                { left: '8%', right: '8%', top: '6%', height: '58%' },
                { left: '8%', right: '8%', top: '72%', height: '18%' },
            ],
            xAxis: [
                { type: 'category', data: dates, gridIndex: 0, axisLabel: { show: false }, axisLine: { show: false }, axisTick: { show: false } },
                { type: 'category', data: dates, gridIndex: 1, axisLabel: { color: '#888', fontSize: 10 }, axisLine: { lineStyle: { color: '#334' } } },
            ],
            yAxis: [
                { type: 'value', gridIndex: 0, scale: true, splitLine: { lineStyle: { color: '#223', type: 'dashed' } }, axisLabel: { color: '#888', fontSize: 10 } },
                { type: 'value', gridIndex: 1, scale: false, splitLine: { show: false }, axisLabel: { color: '#888', fontSize: 9 } },
            ],
            dataZoom: [
                { type: 'inside', xAxisIndex: [0, 1], start: 40, end: 100 },
                { type: 'slider', xAxisIndex: [0, 1], start: 40, end: 100, bottom: 0, height: 20, borderColor: '#334', fillerColor: 'rgba(64,158,255,0.15)', handleSize: 0 },
            ],
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'cross' },
                backgroundColor: 'rgba(26,26,46,0.9)',
                borderColor: '#334',
                textStyle: { color: '#ccc', fontSize: 11 },
            },
            series: [
                {
                    name: 'K线', type: 'candlestick', xAxisIndex: 0, yAxisIndex: 0,
                    data: candlestickData,
                    itemStyle: { color: '#f56c6c', color0: '#67c23a', borderColor: '#f56c6c', borderColor0: '#67c23a' },
                    markLine: markLines.length > 0 ? { silent: true, symbol: 'none', data: markLines.flatMap(m => m.data), lineStyle: {} } : undefined,
                },
                {
                    name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1,
                    data: data.map(r => ({ value: r.volume, itemStyle: { color: r.close >= r.open ? '#f56c6c' : '#67c23a' } })),
                },
                { name: 'MA5', type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: ma5, smooth: true, symbol: 'none', lineStyle: { width: 1.5, color: '#e6a23c' } },
                { name: 'MA10', type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: ma10, smooth: true, symbol: 'none', lineStyle: { width: 1.5, color: '#409eff' } },
                { name: 'MA20', type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: ma20, smooth: true, symbol: 'none', lineStyle: { width: 1.5, color: '#b37feb' } },
                { name: 'MA60', type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: ma60, smooth: true, symbol: 'none', lineStyle: { width: 1.5, color: '#ff85c0' } },
            ],
        }

        klineChartInstance.setOption(option)
        klineChartInstance.resize()
    })
}

// 监听 srResult 变化 → 渲染K线图
watch(srResult, (val) => {
    if (val?.kline_data?.length) renderKlineChart()
})

// 对话框弹出后重新渲染图表（解决动画导致的尺寸问题）
watch(showCreateDialog, (val) => {
    if (val && srResult.value?.kline_data?.length) {
        nextTick(() => renderKlineChart())
    } else if (!val && klineChartInstance) {
        klineChartInstance.dispose()
        klineChartInstance = null
    }
})

// 窗口resize时自适应图表
let resizeHandler = null
onMounted(() => {
    resizeHandler = () => { if (klineChartInstance) klineChartInstance.resize() }
    window.addEventListener('resize', resizeHandler)
})

onUnmounted(() => {
    if (klineChartInstance) { klineChartInstance.dispose(); klineChartInstance = null }
    if (resizeHandler) window.removeEventListener('resize', resizeHandler)
})

onMounted(() => {
    // 如果是从观察池/个股分析跳转过来，预填股票信息并弹窗
    const code = route.query.code
    const name = route.query.name
    if (code) {
        newPlan.value.code = code
        newPlan.value.name = name || ''
        showCreateDialog.value = true
    }
    loadPlans()
})
</script>

<style scoped>
.trading-plans-page { max-width: 1200px; margin: 0 auto; }
.plan-card:hover .el-card { border-color: #409eff !important; }
</style>
