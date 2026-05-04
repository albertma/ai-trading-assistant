<template>
    <div class="risk-page">
        <!-- 快速检查 -->
        <el-card shadow="hover" style="margin-bottom: 16px;">
            <template #header><b>🔍 买入风控检查</b></template>
            <el-row :gutter="12">
                <el-col :span="6">
                    <el-input v-model="checkCode" placeholder="输入代码（如 600519）" clearable
                        @keyup.enter="doCheck" />
                </el-col>
                <el-col :span="3">
                    <el-button type="primary" @click="doCheck" :loading="checking">检查</el-button>
                </el-col>
            </el-row>
            <el-result v-if="checkResult" :icon="checkResult.passed ? 'success' : 'error'"
                :title="checkResult.passed ? '✅ 符合买入条件' : '❌ 禁止买入'"
                :sub-title="checkResult.name + ' (' + checkResult.code + ')'" style="padding-top:20px;">
                <template #extra>
                    <div style="text-align:left;">
                        <div v-for="c in checkResult.checks" :key="c.rule" class="check-item">
                            <el-tag :type="c.status === 'pass' ? 'success' : c.status === 'warning' ? 'warning' : 'danger'" size="small" style="margin-right:8px;">
                                {{ c.status === 'pass' ? '通过' : c.status === 'warning' ? '谨慎' : '禁止' }}
                            </el-tag>
                            <b>{{ c.rule }}:</b> {{ c.detail }}
                        </div>
                    </div>
                </template>
            </el-result>
        </el-card>

        <!-- 持仓预警 -->
        <el-card shadow="hover">
            <template #header>
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <b>⚠️ 持仓预警</b>
                    <el-button size="small" @click="loadAlerts">刷新</el-button>
                </div>
            </template>
            <el-table :data="alerts" stripe style="width:100%" v-loading="loadingAlerts">
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
                <el-table-column prop="type" label="级别" width="80">
                    <template #default="{ row }">
                        <el-tag :type="row.type === 'danger' ? 'danger' : row.type === 'warning' ? 'warning' : 'info'" size="small">
                            {{ row.type === 'danger' ? '危险' : row.type === 'warning' ? '预警' : '提示' }}
                        </el-tag>
                    </template>
                </el-table-column>
                <el-table-column prop="message" label="消息" min-width="300" />
                <el-table-column prop="value" label="数值" width="80" />
            </el-table>
            <el-empty v-if="!loadingAlerts && !alerts.length" description="暂无预警" />
        </el-card>
    </div>
</template>

<script setup>
import { ref } from 'vue'
import { getRiskAlerts, analyzeStock } from '../api/index.js'
import { ElMessage } from 'element-plus'

const checkCode = ref('')
const checking = ref(false)
const checkResult = ref(null)
const alerts = ref([])
const loadingAlerts = ref(true)

async function doCheck() {
    const code = checkCode.value?.trim()
    if (!code) {
        ElMessage.warning('请输入代码')
        return
    }
    checking.value = true
    checkResult.value = null
    try {
        const { data } = await analyzeStock(code)
        if (data.risk_check) {
            checkResult.value = { ...data.risk_check, code: data.code, name: data.name }
        } else {
            ElMessage.warning('数据不足，无法检查')
        }
    } catch (e) {
        ElMessage.error('检查失败')
    } finally {
        checking.value = false
    }
}

async function loadAlerts() {
    loadingAlerts.value = true
    try {
        const { data } = await getRiskAlerts()
        alerts.value = data.alerts || []
    } catch (e) {
        // ignore
    } finally {
        loadingAlerts.value = false
    }
}

loadAlerts()
</script>

<style scoped>
.risk-page { max-width: 1400px; margin: 0 auto; }
.check-item { margin: 8px 0; font-size: 14px; }
</style>
