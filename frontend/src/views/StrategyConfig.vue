<template>
    <div>
        <el-card shadow="never">
            <template #header>
                <b style="font-size:16px;">📌 新建策略配置</b>
                <span style="color:#909399;font-size:13px;margin-left:8px;">
                    选择预置策略并绑定到板块/个股/群组
                </span>
            </template>

            <el-form :model="form" label-width="120px" style="max-width:700px;">

                <!-- 选择策略 -->
                <el-form-item label="选择策略" required>
                    <el-select v-model="form.preset_name" filterable style="width:100%;"
                        placeholder="搜索并选择预置策略" @change="onPresetChange">
                        <el-option-group label="🔥 精选系统">
                            <el-option v-for="p in presets.filter(x => x.name.startsWith('kline'))"
                                :key="p.name" :label="p.label" :value="p.name" />
                        </el-option-group>
                        <el-option-group label="📊 底部反转(分板块)">
                            <el-option v-for="p in presets.filter(x => x.name.startsWith('bottom_reversal_') && x.name !== 'bottom_reversal')"
                                :key="p.name" :label="p.label" :value="p.name" />
                        </el-option-group>
                        <el-option-group label="🧘 底部反转(通用)">
                            <el-option v-for="p in presets.filter(x => x.name === 'bottom_reversal')"
                                :key="p.name" :label="p.label" :value="p.name" />
                        </el-option-group>
                        <el-option-group label="📈 其他策略">
                            <el-option v-for="p in presets.filter(x => !x.name.startsWith('kline') && !x.name.startsWith('bottom_reversal'))"
                                :key="p.name" :label="p.label" :value="p.name" />
                        </el-option-group>
                    </el-select>
                    <div v-if="selectedPreset" style="margin-top:4px;font-size:12px;color:#909399;">
                        买入: {{ selectedPreset.entry }} → 卖出: {{ selectedPreset.exit }}
                        <el-tag v-if="selectedPreset.default_sl > 0" size="mini" type="warning" style="margin-left:4px;">
                            默认止损 {{ selectedPreset.default_sl }}%
                        </el-tag>
                    </div>
                </el-form-item>

                <!-- 作用域类型 -->
                <el-form-item label="作用域类型" required>
                    <el-radio-group v-model="form.scope_type">
                        <el-radio value="all">🌐 全部股票</el-radio>
                        <el-radio value="sector">📂 板块</el-radio>
                        <el-radio value="stock">📈 个股</el-radio>
                        <el-radio value="group">📋 自定义群组</el-radio>
                    </el-radio-group>
                </el-form-item>

                <!-- 板块下拉 -->
                <el-form-item v-if="form.scope_type === 'sector'" label="选择板块" required>
                    <el-select v-model="form.scope_value" filterable style="width:100%;"
                        placeholder="搜索板块名称（已按该板块精选信号优化过）">
                        <el-option v-for="s in sectors" :key="s" :label="s" :value="s" />
                    </el-select>
                </el-form-item>

                <!-- 个股 -->
                <el-form-item v-if="form.scope_type === 'stock'" label="股票代码" required>
                    <div style="display:flex;gap:8px;">
                        <el-input v-model="form.stock_code" placeholder="输入股票代码" style="width:200px;" />
                        <el-button size="small" @click="lookupStock" :loading="lookingUp">查询</el-button>
                    </div>
                    <div v-if="stockName" style="margin-top:4px;color:#67c23a;">{{ stockName }}</div>
                    <div v-if="form.stock_code && !stockName && !lookingUp"
                        style="margin-top:4px;color:#909399;">输入代码后点击查询</div>
                </el-form-item>

                <!-- 群组 -->
                <el-form-item v-if="form.scope_type === 'group'" label="选择群组" required>
                    <div style="display:flex;gap:8px;">
                        <el-select v-model="form.scope_value" filterable style="flex:1;"
                            placeholder="选择已有群组">
                            <el-option v-for="g in groups" :key="g.name"
                                :label="`${g.name}（${g.code_count}只）`" :value="g.name" />
                        </el-select>
                        <el-button size="small" @click="showGroupDialog = true">＋新建</el-button>
                    </div>
                </el-form-item>

                <!-- 描述 -->
                <el-form-item label="备注">
                    <el-input v-model="form.description" type="textarea" :rows="2"
                        placeholder="可选备注，如：仅用于日K级信号（非周K）" />
                </el-form-item>

                <el-form-item>
                    <el-button type="primary" @click="saveConfig" :loading="saving"
                        :disabled="!canSave">
                        ✅ 保存配置
                    </el-button>
                    <el-button @click="resetForm">重置</el-button>
                </el-form-item>
            </el-form>
        </el-card>

        <!-- 最近创建列表 -->
        <el-card shadow="never" style="margin-top:12px;">
            <template #header>
                <span><b>📋 已配置的策略</b>（共 {{ configs.length }} 条）</span>
            </template>
            <el-table :data="configs" size="small" stripe style="width:100%;">
                <el-table-column label="策略" prop="entry_signal" width="140" />
                <el-table-column label="买入" prop="buy_signal" width="100" />
                <el-table-column label="卖出" prop="sell_signal" width="100" />
                <el-table-column label="作用域" width="200">
                    <template #default="{ row }">
                        <el-tag v-if="row.scope_type === 'all'" size="small" type="info">🌐 全部</el-tag>
                        <el-tag v-else-if="row.scope_type === 'sector'" size="small" type="success">📂 {{ row.scope_value }}</el-tag>
                        <el-tag v-else-if="row.scope_type === 'stock'" size="small" type="warning">📈 {{ row.scope_value }}</el-tag>
                        <el-tag v-else-if="row.scope_type === 'group'" size="small" type="primary">📋 {{ row.scope_value }}</el-tag>
                    </template>
                </el-table-column>
                <el-table-column label="创建时间" prop="created_at" width="150" />
                <el-table-column label="操作" width="100" align="center">
                    <template #default="{ row }">
                        <el-popconfirm title="删除此配置？" @confirm="deleteConfig(row.id)">
                            <template #reference>
                                <el-button size="mini" type="danger" link>删除</el-button>
                            </template>
                        </el-popconfirm>
                    </template>
                </el-table-column>
            </el-table>
        </el-card>

        <!-- 新建群组弹窗 -->
        <el-dialog v-model="showGroupDialog" title="新建股票群组" width="500px">
            <el-form :model="groupForm" label-width="80px">
                <el-form-item label="名称">
                    <el-input v-model="groupForm.name" placeholder="如：科技核心" />
                </el-form-item>
                <el-form-item label="股票代码">
                    <el-input v-model="groupForm.codes" type="textarea" :rows="2"
                        placeholder="逗号分隔，如：002371,300308,000063" />
                </el-form-item>
                <el-form-item label="说明">
                    <el-input v-model="groupForm.description" placeholder="可选" />
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
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api/index.js'

const presets = ref([])
const sectors = ref([])
const groups = ref([])
const configs = ref([])
const saving = ref(false)
const lookingUp = ref(false)
const stockName = ref('')
const showGroupDialog = ref(false)
const creatingGroup = ref(false)

const form = ref({
    preset_name: '',
    scope_type: 'all',
    scope_value: '',
    stock_code: '',
    description: '',
})

const groupForm = ref({ name: '', codes: '', description: '' })

const selectedPreset = computed(() => {
    return presets.value.find(p => p.name === form.value.preset_name) || null
})

const canSave = computed(() => {
    if (!form.value.preset_name) return false
    if (form.value.scope_type !== 'all' && !form.value.scope_value) return false
    return true
})

function onPresetChange(name) {
    if (!name) return
    // 如果选的是板块专用策略，自动匹配板块
    const p = presets.value.find(x => x.name === name)
    if (p && name.startsWith('bottom_reversal_')) {
        const label = p.label || ''
        const match = label.match(/(.+?)底部反转/)
        if (match && match[1]) {
            form.value.scope_type = 'sector'
            form.value.scope_value = match[1]
        }
    }
}

async function loadPresets() {
    try {
        const r = await api.get('/strategy-backtest/signals')
        presets.value = r.data.presets || []
    } catch { /* ignore */ }
}

async function loadCandidates() {
    try {
        const r = await api.get('/strategies/candidates')
        sectors.value = r.data.sectors || []
    } catch { /* ignore */ }
}

async function loadGroups() {
    try {
        const r = await api.get('/strategies/groups')
        groups.value = r.data || []
    } catch { /* ignore */ }
}

async function loadConfigs() {
    try {
        const r = await api.get('/strategies')
        configs.value = r.data || []
    } catch { /* ignore */ }
}

async function lookupStock() {
    const code = form.value.stock_code
    if (!code) return
    lookingUp.value = true
    try {
        const r = await api.get('/stock-info/search', { params: { q: code, limit: 5 } })
        const list = r.data?.results || []
        const found = list.find(x => x.code === code)
        stockName.value = found ? found.name : '未找到'
        if (found) {
            form.value.scope_value = code
        }
    } catch {
        stockName.value = '查询失败'
    } finally {
        lookingUp.value = false
    }
}

async function saveConfig() {
    if (!canSave.value) { ElMessage.warning('请选择策略和作用域'); return }

    const p = selectedPreset.value
    if (!p) { ElMessage.warning('请选择策略'); return }

    saving.value = true
    try {
        await api.post('/strategies', {
            name: `${p.label} @ ${form.value.scope_type === 'all' ? '全部股票' : form.value.scope_value}`,
            buy_signal: p.entry,
            sell_signal: p.exit,
            stop_loss: p.default_sl || 0,
            scope_type: form.value.scope_type,
            scope_value: form.value.scope_value,
            description: form.value.description,
            config_json: {},
        })
        ElMessage.success('策略配置已保存')
        resetForm()
        await loadConfigs()
    } catch (e) {
        ElMessage.error('保存失败: ' + (e.response?.data?.detail || ''))
    } finally {
        saving.value = false
    }
}

async function deleteConfig(id) {
    try {
        await api.delete(`/strategies/${id}`)
        ElMessage.success('已删除')
        await loadConfigs()
    } catch { ElMessage.error('删除失败') }
}

function resetForm() {
    form.value = { preset_name: '', scope_type: 'all', scope_value: '', stock_code: '', description: '' }
    stockName.value = ''
}

async function createGroup() {
    if (!groupForm.value.name) { ElMessage.warning('请输入名称'); return }
    creatingGroup.value = true
    try {
        await api.post('/strategies/groups', groupForm.value)
        ElMessage.success('群组已创建')
        showGroupDialog.value = false
        groupForm.value = { name: '', codes: '', description: '' }
        await loadGroups()
    } catch (e) {
        ElMessage.error('创建失败: ' + (e.response?.data?.detail || ''))
    } finally {
        creatingGroup.value = false
    }
}

onMounted(async () => {
    await Promise.all([loadPresets(), loadCandidates(), loadGroups(), loadConfigs()])
})
</script>
