<template>
    <div>
        <el-card shadow="never" style="margin-bottom:12px;">
            <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
                <b style="font-size:16px;">📋 策略管理</b>
                <el-tag size="small" type="info">{{ strategies.length }} 条配置</el-tag>

                <el-input v-model="matchCode" placeholder="输入代码查匹配策略" style="width:200px;"
                    clearable @clear="matchCode=''" size="small" />
                <el-button size="small" type="success" plain @click="doMatch">🔍 匹配</el-button>

                <div style="flex:1"></div>
                <el-button type="primary" size="small" @click="$router.push('/strategy-config')">
                    ＋ 新建策略配置
                </el-button>
            </div>
        </el-card>

        <el-card shadow="never">
            <el-table :data="displayList" size="small" v-loading="loading" stripe style="width:100%;">
                <el-table-column label="策略" prop="name" min-width="200" />
                <el-table-column label="买入" prop="buy_signal" width="120" />
                <el-table-column label="卖出" prop="sell_signal" width="120" />
                <el-table-column label="作用域" width="200">
                    <template #default="{ row }">
                        <el-tag v-if="!row.scope_type || row.scope_type === 'all'" size="small" type="info">
                            🌐 全部
                        </el-tag>
                        <el-tag v-else-if="row.scope_type === 'sector'" size="small" type="success">
                            📂 {{ row.scope_value }}
                        </el-tag>
                        <el-tag v-else-if="row.scope_type === 'stock'" size="small" type="warning">
                            📈 {{ row.scope_value }}
                        </el-tag>
                        <el-tag v-else-if="row.scope_type === 'group'" size="small" type="primary">
                            📋 {{ row.scope_value }}
                        </el-tag>
                    </template>
                </el-table-column>
                <el-table-column label="创建时间" prop="created_at" width="150">
                    <template #default="{ row }">
                        {{ formatTime(row.created_at) }}
                    </template>
                </el-table-column>
                <el-table-column label="操作" width="140" align="center">
                    <template #default="{ row }">
                        <el-button size="mini" type="danger" link
                            @click="openMatchDialog(row)">
                            🔍 匹配
                        </el-button>
                        <el-popconfirm title="删除此配置？" @confirm="deleteStrategy(row.id)">
                            <template #reference>
                                <el-button size="mini" type="danger" link>删除</el-button>
                            </template>
                        </el-popconfirm>
                    </template>
                </el-table-column>
            </el-table>
        </el-card>

        <!-- 匹配弹窗 -->
        <el-dialog v-model="matchDialog.visible" title="🔍 匹配检测" width="500px">
            <div v-if="matchDialog.strategy" style="margin-bottom:12px;">
                <b>{{ matchDialog.strategy.name }}</b>
                <el-tag size="small" style="margin-left:8px;" type="success" v-if="matchDialog.strategy.scope_type === 'sector'">
                    📂 {{ matchDialog.strategy.scope_value }}
                </el-tag>
            </div>
            <el-input v-model="matchDialog.code" placeholder="输入股票代码" size="small" style="margin-bottom:12px;" clearable />
            <el-button size="small" type="primary" @click="doManualMatch" :loading="matchDialog.loading">检测</el-button>
            <div v-if="matchDialog.matched !== null" style="margin-top:12px;">
                <el-result v-if="matchDialog.matched" icon="success" title="✅ 匹配"
                    :sub-title="`${matchDialog.strategy?.name} 适用于 ${matchDialog.code}`" />
                <el-result v-else icon="warning" title="❌ 不匹配"
                    :sub-title="`${matchDialog.code} 不在该策略的作用域内`" />
            </div>
        </el-dialog>
    </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api/index.js'

const strategies = ref([])
const loading = ref(false)
const matchCode = ref('')

const matchDialog = ref({
    visible: false, strategy: null, code: '', matched: null, loading: false,
})

const displayList = computed(() => {
    if (!matchCode.value) return strategies.value
    const mc = matchCode.value
    return strategies.value.filter(s => {
        const st = s.scope_type || 'all'
        const sv = s.scope_value || ''
        if (st === 'all') return true
        if (st === 'stock') return sv === mc
        if (st === 'sector') return true
        if (st === 'group') return true
        return false
    })
})

function formatTime(t) {
    if (!t) return '-'
    return t.slice(0, 19).replace('T', ' ')
}

async function loadStrategies() {
    loading.value = true
    try {
        const r = await api.get('/strategies')
        strategies.value = r.data || []
    } catch { ElMessage.error('加载失败') }
    finally { loading.value = false }
}

function doMatch() {}

async function deleteStrategy(id) {
    try {
        await api.delete(`/strategies/${id}`)
        ElMessage.success('已删除')
        await loadStrategies()
    } catch { ElMessage.error('删除失败') }
}

function openMatchDialog(row) {
    matchDialog.value = { visible: true, strategy: row, code: '', matched: null, loading: false }
}

async function doManualMatch() {
    const code = matchDialog.value.code
    if (!code) { ElMessage.warning('输入代码'); return }
    matchDialog.value.loading = true
    matchDialog.value.matched = null
    try {
        const r = await api.get(`/strategies/match?code=${code}`)
        const found = (r.data || []).some(s => s.id === matchDialog.value.strategy.id)
        matchDialog.value.matched = found
    } catch { ElMessage.error('查询失败') }
    finally { matchDialog.value.loading = false }
}

onMounted(loadStrategies)
</script>
