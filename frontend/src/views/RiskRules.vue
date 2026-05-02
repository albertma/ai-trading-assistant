<template>
    <div class="risk-rules-page">
        <el-card shadow="hover">
            <template #header>
                <div style="display:flex;align-items:center;gap:12px;">
                    <span style="font-size:16px;font-weight:600;">⚙️ 风控规则管理</span>
                    <el-button type="primary" size="small" @click="showAddDialog" :icon="Plus">新增规则</el-button>
                    <el-button size="small" @click="initDefaults">恢复预设</el-button>
                    <el-tag v-if="editing" type="warning" effect="plain">编辑模式</el-tag>
                </div>
            </template>

            <!-- 规则表格 -->
            <el-table :data="rules" stripe style="width:100%" v-loading="loading" size="small">
                <el-table-column prop="id" label="ID" width="60" />
                <el-table-column prop="name" label="规则名称" min-width="160" />
                <el-table-column prop="rule_type" label="类型" width="80">
                    <template #default="{ row }">
                        <el-tag :type="typeColor(row.rule_type)" size="small" effect="plain">
                            {{ typeLabel(row.rule_type) }}
                        </el-tag>
                    </template>
                </el-table-column>
                <el-table-column prop="field" label="指标字段" width="140" />
                <el-table-column label="条件" width="220">
                    <template #default="{ row }">
                        <code>{{ operatorLabel(row.operator) }} {{ row.value }}{{ row.unit }}</code>
                    </template>
                </el-table-column>
                <el-table-column prop="severity" label="等级" width="70">
                    <template #default="{ row }">
                        <el-tag :type="row.severity === 'fail' ? 'danger' : row.severity === 'warning' ? 'warning' : 'info'" size="small">
                            {{ row.severity === 'fail' ? '禁止' : row.severity === 'warning' ? '警告' : '提示' }}
                        </el-tag>
                    </template>
                </el-table-column>
                <el-table-column label="启用" width="70" align="center">
                    <template #default="{ row }">
                        <el-switch v-model="row.enabled" :active-value="1" :inactive-value="0"
                            @change="toggleRule(row)" size="small" />
                    </template>
                </el-table-column>
                <el-table-column label="操作" width="120" fixed="right">
                    <template #default="{ row }">
                        <el-button size="small" text @click="editRule(row)">编辑</el-button>
                        <el-button size="small" text type="danger" @click="deleteRule(row)">删除</el-button>
                    </template>
                </el-table-column>
            </el-table>
        </el-card>

        <!-- 编辑对话框 -->
        <el-dialog v-model="dialogVisible" :title="editing ? '编辑规则' : '新增规则'" width="550px">
            <el-form :model="form" label-width="100px" size="small">
                <el-form-item label="规则名称" required>
                    <el-input v-model="form.name" placeholder="如：营收增长率告警" />
                </el-form-item>
                <el-form-item label="描述">
                    <el-input v-model="form.description" placeholder="规则说明" />
                </el-form-item>
                <el-row :gutter="12">
                    <el-col :span="12">
                        <el-form-item label="规则类型" required>
                            <el-select v-model="form.rule_type" style="width:100%" @change="onTypeChange">
                                <el-option label="价格类" value="price" />
                                <el-option label="均线类" value="ma" />
                                <el-option label="量能类" value="volume" />
                                <el-option label="基本面" value="fundamental" />
                                <el-option label="K线形态" value="kline" />
                            </el-select>
                        </el-form-item>
                    </el-col>
                    <el-col :span="12">
                        <el-form-item label="指标字段" required>
                            <el-select v-model="form.field" style="width:100%" @change="onFieldChange">
                                <el-option v-for="f in filteredFields" :key="f.field" :label="f.label" :value="f.field" />
                            </el-select>
                        </el-form-item>
                    </el-col>
                </el-row>
                <el-row :gutter="12">
                    <el-col :span="8">
                        <el-form-item label="操作符" required>
                            <el-select v-model="form.operator" style="width:100%">
                                <el-option label=">" value="gt" />
                                <el-option label=">=" value="gte" />
                                <el-option label="<" value="lt" />
                                <el-option label="<=" value="lte" />
                                <el-option label="=" value="eq" />
                                <el-option label="包含" value="contains" />
                                <el-option label="介于" value="between" />
                            </el-select>
                        </el-form-item>
                    </el-col>
                    <el-col :span="8">
                        <el-form-item label="阈值" required>
                            <el-input v-model="form.value" placeholder="阈值" />
                        </el-form-item>
                    </el-col>
                    <el-col :span="8">
                        <el-form-item label="等级" required>
                            <el-select v-model="form.severity" style="width:100%">
                                <el-option label="禁止 (fail)" value="fail" />
                                <el-option label="警告 (warning)" value="warning" />
                                <el-option label="提示 (pass)" value="pass" />
                            </el-select>
                        </el-form-item>
                    </el-col>
                </el-row>
                <el-form-item label="提示文案">
                    <el-input v-model="form.custom_detail" placeholder="不满足规则时的提示" type="textarea" :rows="2" />
                </el-form-item>
            </el-form>
            <template #footer>
                <el-button @click="dialogVisible = false">取消</el-button>
                <el-button type="primary" @click="saveRule" :loading="saving">保存</el-button>
            </template>
        </el-dialog>
    </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import api from '../api/index.js'

const loading = ref(false)
const saving = ref(false)
const rules = ref([])
const fieldTypes = ref([])
const dialogVisible = ref(false)
const editing = ref(null)

const form = ref({
    name: '', description: '', rule_type: 'price', field: 'change_pct',
    operator: 'gte', value: '', severity: 'fail', custom_detail: '', unit: '',
})

const filteredFields = computed(() => {
    return fieldTypes.value.filter(f => f.type === form.value.rule_type)
})

function typeLabel(t) {
    const m = { price: '价格', ma: '均线', volume: '量能', fundamental: '基本面', kline: 'K线', shareholder: '股东' }
    return m[t] || t
}
function typeColor(t) {
    const m = { price: '', ma: 'primary', volume: 'warning', fundamental: 'success', kline: 'info' }
    return m[t] || ''
}
function operatorLabel(op) {
    const m = { gt: '>', gte: '>=', lt: '<', lte: '<=', eq: '=', contains: '包含', between: '介于' }
    return m[op] || op
}

function onTypeChange() {
    const f = filteredFields.value[0]
    if (f) form.value.field = f.field
}
function onFieldChange() {
    const f = fieldTypes.value.find(x => x.field === form.value.field)
    if (f) form.value.unit = f.unit
}

async function loadRules() {
    loading.value = true
    try {
        const { data } = await api.get('/risk-rules')
        rules.value = data.rules || []
    } catch {
        ElMessage.error('加载风控规则失败')
    } finally {
        loading.value = false
    }
}

async function loadTypes() {
    try {
        const { data } = await api.get('/risk-rules/types')
        fieldTypes.value = data.types || []
    } catch {}
}

function showAddDialog() {
    editing.value = null
    form.value = { name: '', description: '', rule_type: 'price', field: 'change_pct',
        operator: 'gte', value: '5', severity: 'fail', custom_detail: '', unit: '%' }
    dialogVisible.value = true
}

function editRule(row) {
    editing.value = row.id
    form.value = { ...row }
    dialogVisible.value = true
}

async function saveRule() {
    if (!form.value.name || !form.value.value) {
        ElMessage.warning('请填写规则名称和阈值')
        return
    }
    saving.value = true
    try {
        if (editing.value) {
            await api.put(`/risk-rules/${editing.value}`, form.value)
            ElMessage.success('规则已更新')
        } else {
            await api.post('/risk-rules', form.value)
            ElMessage.success('规则已创建')
        }
        dialogVisible.value = false
        loadRules()
    } catch (e) {
        ElMessage.error(e.response?.data?.detail || '保存失败')
    } finally {
        saving.value = false
    }
}

async function toggleRule(row) {
    try {
        await api.patch(`/risk-rules/${row.id}/toggle`)
    } catch {
        row.enabled = row.enabled ? 0 : 1
    }
}

async function deleteRule(row) {
    try {
        await ElMessageBox.confirm(`确定删除规则「${row.name}」？`, '确认删除')
        await api.delete(`/risk-rules/${row.id}`)
        ElMessage.success('已删除')
        loadRules()
    } catch {}
}

async function initDefaults() {
    try {
        await ElMessageBox.confirm('这将恢复预设规则，已有规则将保留。确定？', '确认')
        const { data } = await api.post('/risk-rules/init-defaults')
        ElMessage.success(data.message)
        loadRules()
    } catch {}
}

onMounted(() => {
    loadTypes()
    loadRules()
})
</script>
