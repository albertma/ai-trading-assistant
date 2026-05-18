<template>
    <div class="cron-page">
        <!-- 头部 -->
        <div class="page-header">
            <div>
                <h2>⏱️ Cron 任务历史</h2>
                <p class="subtitle">定时任务运行记录 — 数据拉取、复盘报告等</p>
            </div>
            <div style="display:flex;gap:8px;">
                <el-select v-model="filterTask" placeholder="全部任务" size="small" clearable style="width:160px;" @change="loadData">
                    <el-option v-for="t in taskList" :key="t" :label="t" :value="t" />
                </el-select>
                <el-button size="small" @click="loadData" :loading="loading">🔄 刷新</el-button>
            </div>
        </div>

        <!-- 统计卡片 -->
        <el-row :gutter="16" style="margin-bottom:16px;">
            <el-col :span="6">
                <el-card shadow="hover" class="stat-card">
                    <div class="stat-value">{{ stats.total }}</div>
                    <div class="stat-label">总记录</div>
                </el-card>
            </el-col>
            <el-col :span="6">
                <el-card shadow="hover" class="stat-card" style="border-left:3px solid #67c23a;">
                    <div class="stat-value" style="color:#67c23a;">{{ stats.success }}</div>
                    <div class="stat-label">✅ 成功</div>
                </el-card>
            </el-col>
            <el-col :span="6">
                <el-card shadow="hover" class="stat-card" style="border-left:3px solid #f56c6c;">
                    <div class="stat-value" style="color:#f56c6c;">{{ stats.failed }}</div>
                    <div class="stat-label">❌ 失败</div>
                </el-card>
            </el-col>
            <el-col :span="6">
                <el-card shadow="hover" class="stat-card" style="border-left:3px solid #e6a23c;">
                    <div class="stat-value" style="color:#e6a23c;">{{ stats.running }}</div>
                    <div class="stat-label">🔄 运行中</div>
                </el-card>
            </el-col>
        </el-row>

        <!-- 表格 -->
        <el-card shadow="hover">
            <el-table :data="records" border size="small" style="width:100%;" stripe v-loading="loading"
                @row-click="showDetail" :row-class-name="'clickable-row'">
                <el-table-column label="ID" width="55" prop="id" align="center" />
                <el-table-column label="任务名" width="130" prop="task_name">
                    <template #default="{ row }">
                        <el-tag size="small" effect="plain">{{ row.task_name }}</el-tag>
                    </template>
                </el-table-column>
                <el-table-column label="状态" width="90" align="center">
                    <template #default="{ row }">
                        <el-tag v-if="row.status === 'success'" size="small" type="success" effect="dark">✅ 成功</el-tag>
                        <el-tag v-else-if="row.status === 'failed'" size="small" type="danger" effect="dark">❌ 失败</el-tag>
                        <el-tag v-else size="small" type="warning" effect="dark">🔄 运行中</el-tag>
                    </template>
                </el-table-column>
                <el-table-column label="开始时间" width="170" prop="started_at" />
                <el-table-column label="完成时间" width="170" prop="finished_at">
                    <template #default="{ row }">{{ row.finished_at || '--' }}</template>
                </el-table-column>
                <el-table-column label="消息" min-width="250">
                    <template #default="{ row }">
                        <span class="msg-text">{{ row.message || '--' }}</span>
                    </template>
                </el-table-column>
                <el-table-column label="耗时" width="80" align="center">
                    <template #default="{ row }">
                        <span v-if="row.finished_at" style="font-size:12px;color:#909399;">
                            {{ calcDuration(row.started_at, row.finished_at) }}
                        </span>
                        <span v-else style="font-size:12px;color:#e6a23c;">进行中</span>
                    </template>
                </el-table-column>
                <el-table-column label="操作" width="70" align="center">
                    <template #default="{ row }">
                        <el-button v-if="row.status === 'failed'" size="small" type="danger"
                            @click.stop="retryJob(row)" plain :disabled="retryingId === row.id">
                            {{ retryingId === row.id ? '...' : '🔁 重试' }}
                        </el-button>
                    </template>
                </el-table-column>
            </el-table>
            <div v-if="!records.length && !loading" style="text-align:center;padding:30px;color:#909399;">
                <p>暂无 cron 任务记录</p>
                <p style="font-size:12px;margin-top:8px;">定时任务执行时会自动记录到这里</p>
            </div>
        </el-card>
    </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessageBox } from 'element-plus'
import axios from 'axios'

const API_BASE = '/api/v1'

const records = ref([])
const taskList = ref([])
const loading = ref(false)
const filterTask = ref('')
const retryingId = ref(null)

const stats = computed(() => {
    const r = records.value
    return {
        total: r.length,
        success: r.filter(x => x.status === 'success').length,
        failed: r.filter(x => x.status === 'failed').length,
        running: r.filter(x => x.status === 'running').length,
    }
})

onMounted(async () => {
    await loadTasks()
    await loadData()
})

async function loadTasks() {
    try {
        const { data } = await axios.get(`${API_BASE}/cron-history/tasks`)
        taskList.value = data.tasks || []
    } catch { /* ignore */ }
}

async function loadData() {
    loading.value = true
    try {
        const params = { limit: 100 }
        if (filterTask.value) params.task_name = filterTask.value
        const { data } = await axios.get(`${API_BASE}/cron-history`, { params })
        records.value = data.records || []
    } catch (e) {
        console.error('加载Cron历史失败', e)
    } finally {
        loading.value = false
    }
}

function showDetail(row) {
    ElMessageBox.alert(
            `<div style="font-size:13px;line-height:1.8;">
                <p><b>ID：</b>${row.id}</p>
                <p><b>任务：</b>${row.task_name}</p>
                <p><b>状态：</b>${row.status === 'success' ? '✅ 成功' : row.status === 'failed' ? '❌ 失败' : '🔄 运行中'}</p>
                <p><b>开始：</b>${row.started_at}</p>
                <p><b>结束：</b>${row.finished_at || '--'}</p>
                <p><b>耗时：</b>${row.finished_at ? calcDuration(row.started_at, row.finished_at) : '--'}</p>
                <p style="margin-top:8px;"><b>消息：</b></p>
                <pre style="background:#f5f7fa;padding:10px;border-radius:4px;font-size:12px;white-space:pre-wrap;">${row.message || '无'}</pre>
            </div>`,
            `📋 Cron任务 #${row.id} 详情`,
            { dangerouslyUseHTMLString: true, customStyle: { maxWidth: '600px' } }
        )
    }

function retryJob(row) {
    retryingId.value = row.id
    axios.post(`${API_BASE}/cron-jobs/${encodeURIComponent(row.task_name)}/run`).then(({ data }) => {
        if (data.status === 'success') {
            ElMessageBox.alert(data.message || '执行成功', '✅ 重试结果', { type: 'success' })
        } else {
            ElMessageBox.alert(data.message || '执行失败', '❌ 重试结果', { type: 'error' })
        }
    }).catch(e => {
        ElMessageBox.alert('请求失败: ' + (e.response?.data?.detail || e.message), '❌ 错误', { type: 'error' })
    }).finally(() => {
        retryingId.value = null
        loadData()
    })
}

function calcDuration(start, end) {
    if (!start || !end) return '--'
    const s = new Date(start.replace('T', ' ').replace(/-/g, '/')).getTime()
    const e = new Date(end.replace('T', ' ').replace(/-/g, '/')).getTime()
    if (isNaN(s) || isNaN(e)) return '--'
    const diff = Math.floor((e - s) / 1000)
    if (diff < 60) return `${diff}秒`
    const m = Math.floor(diff / 60)
    const sec = diff % 60
    return `${m}分${sec}秒`
}
</script>

<style scoped>
.cron-page { padding: 0; max-width: 1100px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.page-header h2 { font-size: 20px; margin: 0; color: #303133; }
.subtitle { font-size: 12px; color: #909399; margin: 4px 0 0; }
.stat-card { text-align: center; padding: 8px 0; }
.stat-value { font-size: 28px; font-weight: bold; }
.stat-label { font-size: 12px; color: #909399; margin-top: 4px; }
.msg-text { font-size: 12px; color: #606266; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: block; max-width: 300px; }
.clickable-row { cursor: pointer; }
.clickable-row:hover td { background-color: #f5f7fa; }
</style>
