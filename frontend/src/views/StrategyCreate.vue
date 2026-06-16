<template>
    <div>
        <el-card shadow="never">
            <template #header>
                <b style="font-size:16px;">{{ isEdit ? '✏️ 编辑策略' : '✨ 新建策略' }}</b>
            </template>
            <el-form :model="form" label-width="120px" style="max-width:700px;">
                <!-- 基本信息 -->
                <el-form-item label="策略名称" required>
                    <el-input v-model="form.name" placeholder="输入策略名称" />
                </el-form-item>
                <el-form-item label="描述">
                    <el-input v-model="form.description" type="textarea" :rows="2"
                        placeholder="策略描述（可选）" />
                </el-form-item>

                <!-- 信号 -->
                <el-form-item label="买入信号" required>
                    <el-select v-model="form.entry_signal" style="width:100%;" clearable filterable
                        placeholder="选择买入信号">
                        <el-option v-for="e in entries" :key="e.name" :label="e.label"
                            :value="e.name" />
                    </el-select>
                </el-form-item>
                <el-form-item label="卖出信号" required>
                    <el-select v-model="form.exit_signal" style="width:100%;" clearable filterable
                        placeholder="选择卖出信号">
                        <el-option v-for="e in exits" :key="e.name" :label="e.label"
                            :value="e.name" />
                    </el-select>
                </el-form-item>
                <el-form-item label="止损(%)">
                    <el-input-number v-model="form.sl_pct" :min="0" :max="30" :step="0.5" />
                </el-form-item>

                <!-- 作用域 -->
                <el-divider content-position="left">📌 作用域（策略适用的股票范围）</el-divider>
                <el-form-item label="作用域类型">
                    <el-radio-group v-model="form.scope_type">
                        <el-radio value="all">🌐 全部股票</el-radio>
                        <el-radio value="sector">📂 按板块</el-radio>
                        <el-radio value="stock">📈 单只个股</el-radio>
                        <el-radio value="group">📋 自定义群组</el-radio>
                    </el-radio-group>
                </el-form-item>

                <!-- 按板块 -->
                <el-form-item v-if="form.scope_type === 'sector'" label="选择板块" required>
                    <el-select v-model="form.scope_value" style="width:100%;" filterable clearable
                        placeholder="搜索并选择板块">
                        <el-option v-for="s in sectors" :key="s" :label="s" :value="s" />
                    </el-select>
                </el-form-item>

                <!-- 单只个股 -->
                <el-form-item v-if="form.scope_type === 'stock'" label="股票代码" required>
                    <el-input v-model="form.scope_value" placeholder="输入股票代码，如 002371"
                        style="width:300px;" />
                    <el-tag v-if="form.scope_value && stockName" type="info" style="margin-left:8px;">
                        {{ stockName }}
                    </el-tag>
                    <el-button v-if="form.scope_value" size="small" style="margin-left:4px;"
                        @click="lookupStock" :loading="lookingUp">
                        查询
                    </el-button>
                </el-form-item>

                <!-- 自定义群组 -->
                <el-form-item v-if="form.scope_type === 'group'" label="选择群组" required>
                    <div style="display:flex;gap:8px;width:100%;">
                        <el-select v-model="form.scope_value" filterable clearable
                            placeholder="选择已有群组" style="flex:1;">
                            <el-option v-for="g in groups" :key="g.name" :label="`${g.name} (${g.code_count}只)`"
                                :value="g.name" />
                        </el-select>
                        <el-button size="small" @click="showGroupDialog = true">
                            ＋ 新建群组
                        </el-button>
                    </div>
                    <div v-if="selectedGroupInfo" style="margin-top:6px;font-size:12px;color:#909399;">
                        {{ selectedGroupInfo }}
                    </div>
                </el-form-item>

                <!-- 配置参数 -->
                <el-divider content-position="left">⚙️ 高级参数</el-divider>
                <el-form-item label="配置参数">
                    <el-input v-model="form.config_json" type="textarea" :rows="3"
                        placeholder='可选 JSON 配置，例如：{"max_position_days": 20}' />
                </el-form-item>

                <!-- 操作 -->
                <el-form-item>
                    <el-button type="primary" @click="saveStrategy" :loading="saving">
                        {{ isEdit ? '保存修改' : '创建策略' }}
                    </el-button>
                    <el-button @click="$router.push('/strategy-research')">取消</el-button>
                </el-form-item>
            </el-form>
        </el-card>

        <!-- 新建群组弹窗 -->
        <el-dialog v-model="showGroupDialog" title="新建股票群组" width="500px">
            <el-form :model="groupForm" label-width="80px">
                <el-form-item label="群组名称" required>
                    <el-input v-model="groupForm.name" placeholder="输入群组名称" />
                </el-form-item>
                <el-form-item label="股票代码">
                    <el-input v-model="groupForm.codes" type="textarea" :rows="3"
                        placeholder="输入股票代码，逗号分隔，如：002371,300308,000063" />
                </el-form-item>
                <el-form-item label="说明">
                    <el-input v-model="groupForm.description" placeholder="群组说明（可选）" />
                </el-form-item>
            </el-form>
            <template #footer>
                <el-button @click="showGroupDialog = false">取消</el-button>
                <el-button type="primary" @click="createGroup" :loading="creatingGroup">创建</el-button>
            </template>
        </el-dialog>
    </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api/index.js'

const route = useRoute()
const router = useRouter()

const isEdit = computed(() => !!route.params.id)
const entries = ref([])
const exits = ref([])
const sectors = ref([])
const groups = ref([])
const saving = ref(false)
const lookingUp = ref(false)
const showGroupDialog = ref(false)
const creatingGroup = ref(false)
const stockName = ref('')
const createGroupLater = ref(false)

const form = ref({
    name: '',
    description: '',
    entry_signal: '',
    exit_signal: '',
    sl_pct: 0,
    config_json: '',
    scope_type: 'all',
    scope_value: '',
})

const groupForm = ref({
    name: '',
    codes: '',
    description: '',
})

// 选中群组的股票数量展示
const selectedGroupInfo = computed(() => {
    if (!form.value.scope_value) return ''
    const g = groups.value.find(x => x.name === form.value.scope_value)
    if (!g) return ''
    return `包含 ${g.code_count || 0} 只股票`
})

async function loadSignals() {
    try {
        const resp = await api.get('/strategy-backtest/signals')
        const data = resp.data
        entries.value = data.entries || []
        exits.value = data.exits || []
    } catch {
        ElMessage.error('加载信号列表失败')
    }
}

async function loadCandidates() {
    try {
        const resp = await api.get('/strategies/candidates')
        const data = resp.data
        sectors.value = data.sectors || []
    } catch {
        // not critical
    }
}

async function loadGroups() {
    try {
        const resp = await api.get('/strategies/groups')
        groups.value = resp.data || []
    } catch {
        // not critical
    }
}

async function lookupStock() {
    const code = form.value.scope_value
    if (!code) return
    lookingUp.value = true
    try {
        const resp = await api.get('/stock-info/search', { params: { q: code, limit: 5 } })
        const data = resp.data || {}
        const list = data.results || []
        if (list && list.length > 0) {
            const found = list.find(x => x.code === code)
            stockName.value = found ? found.name : ''
        } else {
            stockName.value = ''
        }
    } catch {
        stockName.value = ''
    } finally {
        lookingUp.value = false
    }
}

watch(() => form.value.scope_value, () => {
    if (form.value.scope_type === 'stock') {
        lookupStock()
    }
})

async function loadStrategy(id) {
    try {
        const resp = await api.get(`/strategies/${id}`)
        const data = resp.data
        form.value.name = data.name || ''
        form.value.description = data.description || ''
        form.value.entry_signal = data.buy_signal || data.entry_signal || ''
        form.value.exit_signal = data.sell_signal || data.exit_signal || ''
        form.value.sl_pct = data.stop_loss ?? data.sl_pct ?? 0
        form.value.scope_type = data.scope_type || 'all'
        form.value.scope_value = data.scope_value || ''
        form.value.config_json = data.config_json
            ? (typeof data.config_json === 'string' ? data.config_json : JSON.stringify(data.config_json, null, 2))
            : ''
        if (form.value.scope_type === 'stock') {
            await lookupStock()
        }
    } catch {
        ElMessage.error('加载策略失败')
    }
}

async function saveStrategy() {
    if (!form.value.name) { ElMessage.warning('请输入策略名称'); return }
    if (!form.value.entry_signal) { ElMessage.warning('请选择买入信号'); return }
    if (!form.value.exit_signal) { ElMessage.warning('请选择卖出信号'); return }
    if (form.value.scope_type !== 'all' && !form.value.scope_value) {
        ElMessage.warning('请选择作用域目标'); return
    }

    saving.value = true
    try {
        const payload = {
            name: form.value.name,
            description: form.value.description,
            buy_signal: form.value.entry_signal,
            sell_signal: form.value.exit_signal,
            stop_loss: form.value.sl_pct,
            scope_type: form.value.scope_type,
            scope_value: form.value.scope_value,
        }
        if (form.value.config_json) {
            try {
                payload.config_json = JSON.parse(form.value.config_json)
            } catch {
                payload.config_json = form.value.config_json
            }
        }

        if (isEdit.value) {
            await api.put(`/strategies/${route.params.id}`, payload)
            ElMessage.success('策略已更新')
        } else {
            await api.post('/strategies', payload)
            ElMessage.success('策略已创建')
        }
        router.push('/strategy-research')
    } catch (e) {
        const msg = e.response?.data?.detail || ''
        ElMessage.error(isEdit.value ? `更新失败: ${msg}` : `创建失败: ${msg}`)
    } finally {
        saving.value = false
    }
}

async function createGroup() {
    if (!groupForm.value.name) { ElMessage.warning('请输入群组名称'); return }
    creatingGroup.value = true
    try {
        await api.post('/strategies/groups', groupForm.value)
        ElMessage.success('群组已创建')
        showGroupDialog.value = false
        groupForm.value = { name: '', codes: '', description: '' }
        await loadGroups()
    } catch (e) {
        const msg = e.response?.data?.detail || ''
        ElMessage.error(`创建失败: ${msg}`)
    } finally {
        creatingGroup.value = false
    }
}

onMounted(async () => {
    await Promise.all([loadSignals(), loadCandidates(), loadGroups()])
    if (isEdit.value) {
        await loadStrategy(route.params.id)
    }
})
</script>
