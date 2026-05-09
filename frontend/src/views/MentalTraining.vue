<template>
    <div class="training-page">
        <!-- 今日训练 -->
        <el-card v-if="training" class="today-card">
            <template #header>
                <div class="card-header">
                    <div>
                        <b>📅 今日思维模型训练</b>
                        <el-tag size="small" type="success" style="margin-left:8px;">{{ training.model_name }}</el-tag>
                        <el-tag size="small" type="info" style="margin-left:4px;">{{ training.training_date }}</el-tag>
                    </div>
                    <el-button size="small" @click="refreshTraining" :loading="refreshing">🔄 刷新</el-button>
                </div>
            </template>
            <div class="markdown-body" v-html="renderMarkdown(training.training_answer)"></div>
            <div v-if="training.prediction" class="prediction-box">
                <div class="section-label">🔮 模型预测（明日验证）</div>
                <p>{{ training.prediction }}</p>
                <div v-if="!training.next_day_result" style="margin-top:12px;">
                    <el-input v-model="verifyResult" placeholder="明日实际走势如何？验证预测..." size="small" style="max-width:400px;" />
                    <el-select v-model="verifyAccuracy" placeholder="准确度" size="small" style="width:120px;margin-left:8px;">
                        <el-option label="准确 ✅" value="准确" />
                        <el-option label="部分准确" value="部分准确" />
                        <el-option label="不准确 ❌" value="不准确" />
                    </el-select>
                    <el-button size="small" type="primary" style="margin-left:8px;" @click="submitVerification">提交验证</el-button>
                </div>
                <div v-else class="verified-result">
                    <el-tag :type="training.accuracy === '准确' ? 'success' : training.accuracy === '部分准确' ? 'warning' : 'danger'">
                        {{ training.accuracy === '准确' ? '✅ 准确' : training.accuracy === '部分准确' ? '🟡 部分准确' : '❌ 不准确' }}
                    </el-tag>
                    <span style="margin-left:8px;color:#606266;">{{ training.next_day_result }}</span>
                </div>
            </div>
        </el-card>

        <el-empty v-else description="暂无今日训练数据" />

        <!-- 训练历史 -->
        <el-card style="margin-top:16px;">
            <template #header>
                <b>📊 训练历史</b>
            </template>
            <el-table :data="history" border size="small" style="width:100%;" v-if="history.length">
                <el-table-column label="日期" width="100" prop="training_date" />
                <el-table-column label="模型" width="120" prop="model_name" />
                <el-table-column label="预测" min-width="250">
                    <template #default="{ row }">
                        <span class="pred-text">{{ row.prediction || '--' }}</span>
                    </template>
                </el-table-column>
                <el-table-column label="验证结果" width="200">
                    <template #default="{ row }">
                        <div v-if="row.next_day_result">
                            <el-tag :type="row.accuracy === '准确' ? 'success' : row.accuracy === '部分准确' ? 'warning' : 'danger'" size="mini">
                                {{ row.accuracy }}
                            </el-tag>
                            <span style="margin-left:4px;font-size:12px;">{{ row.next_day_result }}</span>
                        </div>
                        <span v-else style="color:#909399;">待验证</span>
                    </template>
                </el-table-column>
                <el-table-column label="反思" min-width="180">
                    <template #default="{ row }">
                        <span style="font-size:12px;color:#606266;">{{ row.reflection || '--' }}</span>
                    </template>
                </el-table-column>
            </el-table>
            <el-empty v-else description="暂无训练历史" />
        </el-card>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const API_BASE = '/api/v1/mental'

const training = ref(null)
const history = ref([])
const refreshing = ref(false)
const verifyResult = ref('')
const verifyAccuracy = ref('')

onMounted(async () => {
    await loadTraining()
    await loadHistory()
})

async function loadTraining() {
    try {
        const { data } = await axios.get(`${API_BASE}/daily-training`)
        training.value = data
    } catch { /* ignore */ }
}

async function loadHistory() {
    try {
        const { data } = await axios.get(`${API_BASE}/daily-training/history?limit=30`)
        history.value = data
    } catch { /* ignore */ }
}

async function refreshTraining() {
    refreshing.value = true
    await loadTraining()
    refreshing.value = false
}

async function submitVerification() {
    if (!training.value?.id || !verifyResult.value) return
    try {
        await axios.put(`${API_BASE}/daily-training/${training.value.id}/verify`, null, {
            params: {
                next_day_result: verifyResult.value,
                accuracy: verifyAccuracy.value || '部分准确',
            }
        })
        await loadTraining()
        await loadHistory()
        verifyResult.value = ''
        verifyAccuracy.value = ''
    } catch { /* ignore */ }
}

function renderMarkdown(text) {
    if (!text) return ''
    let html = text
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        .replace(/^# (.+)$/gm, '<h1>$1</h1>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/^- (.+)$/gm, '<li>$1</li>')
        .replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
        .replace(/\|(.+)\|/g, (match) => {
            const cells = match.split('|').filter(c => c.trim())
            return cells.map(c => `<span class="table-cell">${c.trim()}</span>`).join('')
        })
        .replace(/\n\n/g, '</p><p>')
    return `<p>${html}</p>`
}
</script>

<style scoped>
.training-page { padding: 0; max-width: 900px; margin: 0 auto; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.markdown-body { font-size: 13px; line-height: 1.7; color: #606266; }
.markdown-body h1 { font-size: 18px; margin: 12px 0 8px; color: #303133; }
.markdown-body h2 { font-size: 16px; margin: 10px 0 6px; color: #303133; }
.markdown-body h3 { font-size: 14px; margin: 8px 0 4px; color: #303133; }
.markdown-body strong { color: #303133; }
.markdown-body ul { padding-left: 20px; margin: 6px 0; }
.markdown-body li { margin: 3px 0; }
.markdown-body .table-cell { display: inline-block; padding: 2px 8px; margin: 1px; background: #f0f2f5; border-radius: 3px; font-size: 12px; }
.markdown-body p { margin: 6px 0; }
.today-card { border-left: 3px solid #67c23a; }
.section-label { font-size: 13px; font-weight: 600; color: #409eff; margin-bottom: 6px; }
.prediction-box { margin-top: 16px; padding: 16px; background: #fef7e0; border-radius: 8px; }
.prediction-box p { font-size: 13px; color: #b8860b; }
.verified-result { margin-top: 8px; display: flex; align-items: center; }
.pred-text { font-size: 12px; color: #606266; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: block; max-width: 350px; }
</style>
