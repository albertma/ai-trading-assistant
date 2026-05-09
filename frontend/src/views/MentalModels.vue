<template>
    <div class="models-page">
        <el-row :gutter="16">
            <!-- 左侧：模型列表 -->
            <el-col :span="8">
                <el-card class="list-card">
                    <template #header>
                        <div class="card-header">
                            <b>🧠 思维模型库</b>
                            <el-select v-model="categoryFilter" placeholder="全部分类" size="small" clearable style="width:130px;">
                                <el-option v-for="c in categories" :key="c.category" :label="`${c.category} (${c.count})`" :value="c.category" />
                            </el-select>
                        </div>
                    </template>
                    <div class="model-list" v-if="filteredModels.length">
                        <div v-for="m in filteredModels" :key="m.id"
                            class="model-item"
                            :class="{ 'active': selected?.id === m.id }"
                            @click="selectModel(m)">
                            <span class="model-icon">{{ m.icon }}</span>
                            <div class="model-info">
                                <div class="model-name">{{ m.name }}</div>
                                <div class="model-category">{{ m.category }}</div>
                            </div>
                            <el-tag size="mini" type="info" plain>{{ m.tags ? JSON.parse(m.tags).length : 0 }}</el-tag>
                        </div>
                    </div>
                    <el-empty v-else description="暂无模型" />
                </el-card>
            </el-col>

            <!-- 右侧：模型详情 -->
            <el-col :span="16">
                <el-card v-if="selected" class="detail-card">
                    <template #header>
                        <div class="card-header">
                            <span><b>{{ selected.icon }} {{ selected.name }}</b></span>
                            <el-tag>{{ selected.category }}</el-tag>
                        </div>
                    </template>

                    <div class="detail-section">
                        <div class="desc-box">
                            <div class="section-label">📖 核心描述</div>
                            <p>{{ selected.description }}</p>
                        </div>

                        <div class="section-row">
                            <div class="section-box">
                                <div class="section-label">🎯 应用场景</div>
                                <p>{{ selected.application }}</p>
                            </div>
                            <div class="section-box">
                                <div class="section-label">🔄 何时使用</div>
                                <p>{{ selected.scenario }}</p>
                            </div>
                        </div>

                        <div class="desc-box">
                            <div class="section-label">💡 实战案例</div>
                            <p>{{ selected.example }}</p>
                        </div>

                        <div class="desc-box" v-if="selected.detail">
                            <div class="section-label">📚 深度解析</div>
                            <div class="markdown-body" v-html="renderMarkdown(selected.detail)"></div>
                        </div>

                        <div class="tags-box" v-if="selected.tags">
                            <el-tag v-for="t in getTags(selected.tags)" :key="t" size="small" type="warning" effect="plain">{{ t }}</el-tag>
                        </div>
                    </div>
                </el-card>

                <el-card v-else class="empty-card">
                    <el-empty description="选择一个思维模型查看详情" />
                </el-card>
            </el-col>
        </el-row>
    </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const API_BASE = '/api/v1/mental'

const models = ref([])
const categories = ref([])
const selected = ref(null)
const categoryFilter = ref('')

onMounted(async () => {
    await Promise.all([loadModels(), loadCategories()])
})

async function loadModels() {
    try {
        const { data } = await axios.get(`${API_BASE}/models`)
        models.value = data
    } catch { /* ignore */ }
}

async function loadCategories() {
    try {
        const { data } = await axios.get(`${API_BASE}/categories`)
        categories.value = data
    } catch { /* ignore */ }
}

const filteredModels = computed(() => {
    if (!categoryFilter.value) return models.value
    return models.value.filter(m => m.category === categoryFilter.value)
})

function selectModel(m) {
    selected.value = m
}

function getTags(tagsStr) {
    try {
        return JSON.parse(tagsStr || '[]')
    } catch { return [] }
}

function renderMarkdown(text) {
    if (!text) return ''
    // 简单 markdown 渲染
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
.models-page { padding: 0; }
.list-card { height: calc(100vh - 100px); overflow-y: auto; }
.card-header { display: flex; justify-content: space-between; align-items: center; }

.model-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 8px;
    cursor: pointer;
    border-radius: 6px;
    margin-bottom: 4px;
    transition: all 0.2s;
}
.model-item:hover { background: rgba(64,158,255,0.08); }
.model-item.active { background: rgba(64,158,255,0.15); border-left: 3px solid #409eff; }
.model-icon { font-size: 20px; width: 30px; text-align: center; }
.model-info { flex: 1; }
.model-name { font-size: 14px; font-weight: 600; color: #303133; }
.model-category { font-size: 11px; color: #909399; }

.detail-card { height: calc(100vh - 100px); overflow-y: auto; }
.detail-section { display: flex; flex-direction: column; gap: 16px; }
.section-label { font-size: 13px; font-weight: 600; color: #409eff; margin-bottom: 6px; }
.section-row { display: flex; gap: 12px; }
.section-box { flex: 1; background: #f5f7fa; padding: 12px; border-radius: 8px; }
.section-box p, .desc-box p { font-size: 13px; color: #606266; line-height: 1.6; }
.desc-box { background: #f5f7fa; padding: 12px; border-radius: 8px; }
.tags-box { display: flex; gap: 6px; flex-wrap: wrap; }
.empty-card { height: calc(100vh - 100px); display: flex; align-items: center; justify-content: center; }

.markdown-body { font-size: 13px; line-height: 1.7; color: #606266; }
.markdown-body h1 { font-size: 18px; margin: 12px 0 8px; color: #303133; }
.markdown-body h2 { font-size: 16px; margin: 10px 0 6px; color: #303133; }
.markdown-body h3 { font-size: 14px; margin: 8px 0 4px; color: #303133; }
.markdown-body strong { color: #303133; }
.markdown-body ul { padding-left: 20px; margin: 6px 0; }
.markdown-body li { margin: 3px 0; }
.markdown-body .table-cell { display: inline-block; padding: 2px 8px; margin: 1px; background: #f0f2f5; border-radius: 3px; font-size: 12px; }
.markdown-body p { margin: 6px 0; }
</style>
