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
                    <div>
                        <el-button size="small" @click="refreshTraining" :loading="refreshing">🔄 刷新</el-button>
                    </div>
                </div>
            </template>
            <div class="markdown-body" v-html="renderMarkdown(training.training_answer)"></div>

            <!-- 模型参考预测（系统自动生成，作为参考提示） -->
            <div v-if="training.prediction" class="hint-box">
                <div class="section-label">💡 模型参考</div>
                <p>{{ training.prediction }}</p>
            </div>

            <!-- 用户预测 -->
            <div class="prediction-section">
                <div class="section-label">✍️ 你的预测</div>
                <p class="section-desc">根据模型和今日行情，写下你对明天市场的判断：</p>
                <el-input v-model="userPrediction" type="textarea" :rows="3"
                    placeholder="例如：明天大盘可能回调，因为今日涨幅过大... 或某板块会延续涨势..." size="small" />
                <div class="prediction-footer">
                    <span v-if="userPredictionSaved && userPrediction === training.user_prediction" class="saved-hint">✅ 预测已提交</span>
                    <span v-else-if="userPrediction && userPrediction !== training.user_prediction" class="dirty-hint">⏳ 未保存</span>
                    <el-button size="small" type="primary"
                        @click="saveUserPrediction" :loading="predictionSaving"
                        :disabled="!userPrediction || userPrediction === training.user_prediction">
                        💾 提交预测
                    </el-button>
                </div>
            </div>

            <!-- 预测评价（次日自动反思后显示） -->
            <div v-if="training.accuracy" class="evaluation-section">
                <el-divider content-position="left">📊 预测评价</el-divider>
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
                    <el-tag :type="training.accuracy === '准确' ? 'success' : training.accuracy === '部分准确' ? 'warning' : 'danger'" size="medium" effect="dark">
                        {{ training.accuracy === '准确' ? '✅ 准确' : training.accuracy === '部分准确' ? '🟡 部分准确' : '❌ 不准确' }}
                    </el-tag>
                    <span style="font-size:12px;color:#909399;">{{ training.next_day_result || '' }}</span>
                </div>
                <div v-if="training.reflection" class="reflect-content" v-html="renderMarkdown(training.reflection)"></div>
            </div>
        </el-card>

        <el-empty v-else description="暂无今日训练数据" />

        <!-- 昨日反思结果 -->
        <el-card v-if="yesterdayReflection" style="margin-top:16px;" class="reflect-card">
            <template #header>
                <div class="card-header">
                    <b>📋 昨日训练反思</b>
                    <el-tag size="small" type="warning" v-if="yesterdayReflection.accuracy === '准确'">✅ 准确</el-tag>
                    <el-tag size="small" type="warning" v-else-if="yesterdayReflection.accuracy === '部分准确'">🟡 部分准确</el-tag>
                    <el-tag size="small" type="danger" v-else>❌ {{ yesterdayReflection.accuracy }}</el-tag>
                </div>
            </template>
            <div class="markdown-body" v-html="renderMarkdown(yesterdayReflection.reflection)"></div>
        </el-card>

        <!-- 待反思提醒 -->
        <el-alert v-if="pendingReflectCount > 0" type="info" show-icon :closable="false" style="margin-top:16px;">
            <template #title>
                <span>有 {{ pendingReflectCount }} 条训练记录待反思</span>
                <el-button size="small" type="primary" style="margin-left:12px;" @click="runAutoReflect" :loading="reflecting">
                    🪄 一键自动反思
                </el-button>
            </template>
        </el-alert>

        <!-- 训练历史 -->
        <el-card style="margin-top:16px;">
            <template #header>
                <div class="card-header">
                    <b>📊 训练历史</b>
                    <el-button size="small" @click="runAutoReflect" :loading="reflecting" :disabled="pendingReflectCount === 0">
                        🪄 一键反思（{{ pendingReflectCount }}）
                    </el-button>
                </div>
            </template>
            <el-table :data="history" border size="small" style="width:100%;" v-if="history.length"
                @row-click="showHistoryDetail" :row-class-name="'clickable-row'">
                <el-table-column label="日期" width="90" prop="training_date" />
                <el-table-column label="模型" width="110" prop="model_name" />
                <el-table-column label="我的预测" min-width="220">
                    <template #default="{ row }">
                        <span class="pred-text">{{ row.user_prediction || row.prediction || '--' }}</span>
                    </template>
                </el-table-column>
                <el-table-column label="预测结果" width="80" align="center">
                    <template #default="{ row }">
                        <el-tag v-if="row.accuracy" size="mini"
                            :type="row.accuracy === '准确' ? 'success' : row.accuracy === '部分准确' ? 'warning' : 'danger'" effect="plain">
                            {{ row.accuracy === '准确' ? '✅' : row.accuracy === '部分准确' ? '🟡' : '❌' }}
                        </el-tag>
                        <span v-else style="color:#909399;font-size:12px;">待反思</span>
                    </template>
                </el-table-column>
                <el-table-column label="反思" min-width="250">
                    <template #default="{ row }">
                        <div v-if="row.reflection" class="reflect-preview">
                            <span>{{ extractReflectSummary(row.reflection) }}</span>
                        </div>
                        <span v-else style="color:#c0c4cc;font-size:12px;">--</span>
                    </template>
                </el-table-column>
            </el-table>
            <el-empty v-else description="暂无训练历史" />
        </el-card>

        <!-- 历史记录详情弹窗 -->
        <el-dialog v-model="detailVisible" title="📋 训练详情" width="750px" top="5vh" :close-on-click-modal="false">
            <div v-if="detailLoading" style="text-align:center;padding:30px;">
                <el-icon class="is-loading" size="24"><Loading /></el-icon>
                <p style="margin-top:10px;color:#909399;">加载中...</p>
            </div>
            <template v-else-if="detailRecord">
                <div style="margin-bottom:16px;display:flex;gap:6px;align-items:center;flex-wrap:wrap;">
                    <el-tag size="small" type="success">{{ detailRecord.model_name }}</el-tag>
                    <el-tag size="small" type="info">{{ detailRecord.training_date }}</el-tag>
                    <el-tag v-if="detailRecord.accuracy" size="small"
                        :type="detailRecord.accuracy === '准确' ? 'success' : detailRecord.accuracy === '部分准确' ? 'warning' : 'danger'">
                        {{ detailRecord.accuracy === '准确' ? '✅' : detailRecord.accuracy === '部分准确' ? '🟡' : '❌' }}
                        {{ detailRecord.accuracy }}
                    </el-tag>
                </div>

                <el-divider content-position="left">💬 训练内容</el-divider>
                <div class="markdown-body" v-html="renderMarkdown(detailRecord.training_answer)"></div>

                <div style="margin-top:16px;">
                    <el-divider content-position="left">✍️ 我的预测
                        <el-button v-if="detailRecord.user_prediction" size="mini" text type="primary" @click="editPredictMode = !editPredictMode" style="margin-left:8px;">
                            {{ editPredictMode ? '取消' : '✏️ 编辑' }}
                        </el-button>
                    </el-divider>
                    <template v-if="detailRecord.user_prediction">
                        <div v-if="!editPredictMode" class="prediction-box" style="margin-top:0;">
                            <p style="margin:0;">{{ detailRecord.user_prediction }}</p>
                        </div>
                        <div v-else style="display:flex;gap:8px;flex-direction:column;">
                            <el-input v-model="editPrediction" type="textarea" :rows="3" size="small" />
                            <div style="text-align:right;">
                                <el-button size="small" type="primary" @click="saveDetailPrediction" :loading="predictionSaving">💾 保存预测</el-button>
                            </div>
                        </div>
                    </template>
                    <div v-else style="display:flex;gap:8px;flex-direction:column;">
                        <el-input v-model="editPrediction" type="textarea" :rows="3" placeholder="输入你对明天的判断..." size="small" />
                        <div style="text-align:right;">
                            <el-button size="small" type="primary" @click="saveDetailPrediction" :loading="predictionSaving">💾 提交预测</el-button>
                        </div>
                    </div>
                </div>

                <!-- 模型参考预测（始终显示，不折叠） -->
                <div v-if="detailRecord.prediction" style="margin-top:16px;">
                    <el-divider content-position="left">💡 模型参考预测</el-divider>
                    <div class="ref-prediction-box">
                        <p style="margin:0;font-size:13px;color:#303133;line-height:1.7;">{{ detailRecord.prediction }}</p>
                    </div>
                </div>

                <!-- 预测评价 -->
                <template v-if="detailRecord.accuracy">
                    <el-divider content-position="left">📊 预测评价</el-divider>
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
                        <el-tag :type="detailRecord.accuracy === '准确' ? 'success' : detailRecord.accuracy === '部分准确' ? 'warning' : 'danger'" size="medium" effect="dark">
                            {{ detailRecord.accuracy === '准确' ? '✅ 准确' : detailRecord.accuracy === '部分准确' ? '🟡 部分准确' : '❌ 不准确' }}
                        </el-tag>
                        <span style="font-size:12px;color:#909399;">{{ detailRecord.next_day_result || '' }}</span>
                    </div>
                </template>

                <!-- 反思 -->
                <template v-if="detailRecord.reflection">
                    <el-divider content-position="left">💡 反思</el-divider>
                    <div class="reflect-content" v-html="renderMarkdown(detailRecord.reflection)"></div>
                </template>

                <!-- 可编辑区域 -->
                <el-divider content-position="left">📌 评价编辑</el-divider>
                <div style="display:flex;gap:8px;align-items:flex-start;flex-wrap:wrap;">
                    <el-select v-model="editAccuracy" placeholder="准确度" size="small" style="width:130px;">
                        <el-option label="准确 ✅" value="准确" />
                        <el-option label="部分准确" value="部分准确" />
                        <el-option label="不准确 ❌" value="不准确" />
                    </el-select>
                    <el-input v-model="editResult" placeholder="实际走势如何？" size="small" style="flex:1;min-width:200px;" />
                </div>

                <el-divider content-position="left">✍️ 反思编辑</el-divider>
                <el-input v-model="editReflection" type="textarea" :rows="5"
                    placeholder="对这次训练/预测的反思..." size="small" />

                <div style="text-align:right;margin-top:16px;display:flex;justify-content:space-between;">
                    <el-button size="small" type="danger" plain @click="deleteDetailRecord" :loading="deleting">🗑️ 删除</el-button>
                    <div>
                        <el-button size="small" @click="detailVisible = false">取消</el-button>
                        <el-button size="small" type="primary" @click="saveDetailEdit" :loading="detailSaving">
                            💾 保存
                        </el-button>
                    </div>
                </div>
            </template>
        </el-dialog>
    </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const API_BASE = '/api/v1/mental'

const training = ref(null)
const history = ref([])
const refreshing = ref(false)
const reflecting = ref(false)
const userPrediction = ref('')
const predictionSaving = ref(false)
const userPredictionSaved = ref(false)
const detailVisible = ref(false)
const detailRecord = ref(null)
const detailLoading = ref(false)
const detailSaving = ref(false)
const editResult = ref('')
const editAccuracy = ref('')
const editReflection = ref('')
const editPrediction = ref('')
const editPredictMode = ref(false)
const deleting = ref(false)

const pendingReflectCount = computed(() => {
    return history.value.filter(h => h.user_prediction && !h.reflection).length
})

const yesterdayReflection = computed(() => {
    // 找昨天的训练记录，如果有反思就显示
    const today = new Date()
    const yesterday = new Date(today)
    yesterday.setDate(yesterday.getDate() - 1)
    const ymd = yesterday.toISOString().slice(0, 10)
    const rec = history.value.find(h => h.training_date === ymd && h.reflection)
    return rec || null
})

onMounted(async () => {
    await loadTraining()
    await loadHistory()
    // 自动检查是否有待反思
    autoCheckReflect()
})

async function loadTraining() {
    try {
        const { data } = await axios.get(`${API_BASE}/daily-training`)
        training.value = data
        userPrediction.value = data.user_prediction || ''
        userPredictionSaved.value = !!data.user_prediction
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

async function saveUserPrediction() {
    if (!training.value?.id || !userPrediction.value) return
    predictionSaving.value = true
    try {
        // 保存用户预测，同时清除旧评价（等待次日重新反思）
        await axios.put(`${API_BASE}/daily-training/${training.value.id}/prediction`, null, {
            params: { user_prediction: userPrediction.value }
        })
        userPredictionSaved.value = true
        training.value.user_prediction = userPrediction.value
        training.value.accuracy = ''
        training.value.reflection = ''
        ElMessage.success('预测已提交 ✅ 明日收盘后自动反思')
        await loadHistory()
    } catch (e) {
        console.error('保存预测失败', e)
        ElMessage.error('保存失败')
    } finally {
        predictionSaving.value = false
    }
}

async function runAutoReflect() {
    reflecting.value = true
    try {
        const { data } = await axios.post(`${API_BASE}/daily-training/auto-reflect`)
        if (data.reflected > 0) {
            ElMessage.success(`已自动反思 ${data.reflected} 条 ✅`)
        } else {
            ElMessage.info(data.message || '无不需反思的记录')
        }
        await loadTraining()
        await loadHistory()
    } catch (e) {
        console.error('自动反思失败', e)
        ElMessage.error('自动反思失败')
    } finally {
        reflecting.value = false
    }
}

function showHistoryDetail(row) {
    detailVisible.value = true
    detailLoading.value = true
    detailRecord.value = null
    editPredictMode.value = false
    axios.get(`${API_BASE}/daily-training/${row.id}`).then(({ data }) => {
        detailRecord.value = data
        editResult.value = data.next_day_result || ''
        editAccuracy.value = data.accuracy || ''
        editReflection.value = data.reflection || ''
        editPrediction.value = data.user_prediction || ''
    }).catch(e => {
        console.error('加载训练详情失败', e)
    }).finally(() => {
        detailLoading.value = false
    })
}

async function saveDetailEdit() {
    if (!detailRecord.value?.id) return
    detailSaving.value = true
    try {
        await axios.put(`${API_BASE}/daily-training/${detailRecord.value.id}/verify`, null, {
            params: {
                next_day_result: editResult.value || '',
                accuracy: editAccuracy.value || '',
                reflection: editReflection.value || '',
            }
        })
        ElMessage.success('保存成功 ✅')
        const { data } = await axios.get(`${API_BASE}/daily-training/${detailRecord.value.id}`)
        detailRecord.value = data
        if (training.value?.id === detailRecord.value.id) {
            await loadTraining()
        }
        await loadHistory()
    } catch (e) {
        console.error('保存失败', e)
        ElMessage.error('保存失败')
    } finally {
        detailSaving.value = false
    }
}

async function saveDetailPrediction() {
    if (!detailRecord.value?.id) return
    predictionSaving.value = true
    try {
        await axios.put(`${API_BASE}/daily-training/${detailRecord.value.id}/prediction`, null, {
            params: { user_prediction: editPrediction.value }
        })
        detailRecord.value.user_prediction = editPrediction.value
        detailRecord.value.accuracy = ''
        detailRecord.value.reflection = ''
        editAccuracy.value = ''
        editReflection.value = ''
        editPredictMode.value = false
        ElMessage.success('预测已更新 ✅')
        await loadTraining()
        await loadHistory()
    } catch (e) {
        console.error('保存预测失败', e)
        ElMessage.error('保存失败')
    } finally {
        predictionSaving.value = false
    }
}

async function deleteDetailRecord() {
    if (!detailRecord.value?.id) return
    if (!confirm(`确定删除 ${detailRecord.value.training_date} 的「${detailRecord.value.model_name}」训练记录？`)) return
    deleting.value = true
    try {
        await axios.delete(`${API_BASE}/daily-training/${detailRecord.value.id}`)
        ElMessage.success('已删除 ✅')
        detailVisible.value = false
        await loadTraining()
        await loadHistory()
    } catch (e) {
        console.error('删除失败', e)
        ElMessage.error('删除失败')
    } finally {
        deleting.value = false
    }
}

function extractReflectSummary(text) {
    if (!text) return '--'
    // 提取第一行有意义的文字
    const lines = text.split('\n').filter(l => l.trim() && !l.startsWith('-') && !l.startsWith('*'))
    for (const line of lines) {
        const clean = line.replace(/[*#]/g, '').trim()
        if (clean.length > 5 && clean.length < 80) return clean
    }
    return text.slice(0, 80) + (text.length > 80 ? '...' : '')
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
.training-page { padding: 0; max-width: 950px; margin: 0 auto; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.markdown-body { font-size: 13px; line-height: 1.7; color: #606266; }
.markdown-body h1 { font-size: 18px; margin: 12px 0 8px; color: #303133; }
.markdown-body h2 { font-size: 16px; margin: 10px 0 6px; color: #303133; border-bottom: 1px solid #ebeef5; padding-bottom: 4px; }
.markdown-body h3 { font-size: 14px; margin: 8px 0 4px; color: #303133; }
.markdown-body strong { color: #303133; }
.markdown-body ul { padding-left: 20px; margin: 6px 0; }
.markdown-body li { margin: 3px 0; }
.markdown-body .table-cell { display: inline-block; padding: 2px 8px; margin: 1px; background: #f0f2f5; border-radius: 3px; font-size: 12px; }
.markdown-body p { margin: 6px 0; }
.markdown-body hr { border: none; border-top: 1px solid #dcdfe6; margin: 12px 0; }
.today-card { border-left: 3px solid #67c23a; }
.reflect-card { border-left: 3px solid #e6a23c; }
.section-label { font-size: 13px; font-weight: 600; color: #409eff; margin-bottom: 6px; }
.section-desc { font-size: 12px; color: #909399; margin: 0 0 8px; }
.hint-box { margin-top: 16px; padding: 12px; background: #f0f7ff; border-radius: 8px; border-left: 3px solid #409eff; }
.hint-box p { font-size: 13px; color: #606266; margin: 0; }
.prediction-section { margin-top: 16px; padding: 12px; background: #f5f7fa; border-radius: 8px; }
.prediction-footer { display: flex; justify-content: space-between; align-items: center; margin-top: 8px; }
.predict-section { margin-top: 16px; padding: 12px; background: #f5f7fa; border-radius: 8px; }
.prediction-box { margin-top: 0; padding: 12px; background: #fef7e0; border-radius: 8px; }
.prediction-box p { font-size: 13px; color: #b8860b; }
.ref-prediction-box { padding: 12px; background: #f0f5ff; border-radius: 8px; border-left: 3px solid #409eff; }
.verified-result { margin-top: 8px; display: flex; align-items: center; }
.pred-text { font-size: 12px; color: #606266; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: block; max-width: 350px; }
.clickable-row { cursor: pointer; }
.clickable-row:hover td { background-color: #f5f7fa; }
.reflect-preview { font-size: 12px; color: #606266; line-height: 1.5; }
.reflect-content { font-size: 13px; line-height: 1.7; color: #606266; background: #fef7e0; padding: 12px; border-radius: 6px; }
.reflect-content h2, .reflect-content h3 { margin: 6px 0; }
.answer-section { margin-top: 16px; padding: 12px; background: #f5f7fa; border-radius: 8px; }
.answer-footer { display: flex; justify-content: space-between; align-items: center; margin-top: 8px; }
.saved-hint { font-size: 12px; color: #67c23a; }
.dirty-hint { font-size: 12px; color: #e6a23c; }
</style>
