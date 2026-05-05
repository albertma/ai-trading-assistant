<template>
    <div class="kg-container">
        <!-- 顶部: 输入区域 -->
        <el-card class="input-card" shadow="never">
            <div class="input-row">
                <el-input v-model="articleTitle" placeholder="文章标题（可选）" style="width:250px;margin-right:12px" clearable />
                <el-input v-model="inputContent" type="textarea" :rows="2" placeholder="粘贴文章内容或输入URL..." style="flex:1;margin-right:12px"
                    @keydown.ctrl.enter="doExtract" />
                <el-button type="primary" @click="doExtract" :loading="extracting" :disabled="!inputContent.trim()">
                    <el-icon style="margin-right:4px"><MagicStick /></el-icon>提取图谱
                </el-button>
            </div>
            <div class="input-tip">💡 支持粘贴文本或输入 http(s) URL，按 Ctrl+Enter 快速提取</div>
        </el-card>

        <!-- 主区域 -->
        <div class="kg-body">
            <!-- 左侧: 文章列表 -->
            <el-card class="article-list" shadow="never">
                <template #header>
                    <div class="list-header">
                        <span>📚 文章库</span>
                        <el-button size="small" :type="showAggregated ? 'primary' : 'default'" @click="loadAggregated">
                            <el-icon><Connection /></el-icon> 聚合图谱
                        </el-button>
                    </div>
                </template>
                <div class="list-toolbar">
                    <el-input v-model="articleSearch" placeholder="搜索..." size="small" prefix-icon="Search" clearable />
                </div>
                <div class="article-items" v-loading="loadingArticles">
                    <div v-for="a in filteredArticles" :key="a.id"
                        class="article-item"
                        :class="{ active: currentArticleId === a.id }"
                        @click="loadArticle(a.id)">
                        <div class="article-title">{{ a.title || '(无标题)' }}</div>
                        <div class="article-meta">
                            <span>{{ a.entity_count }} 实体</span>
                            <span>{{ a.relation_count }} 关系</span>
                            <span class="article-date">{{ a.created_at?.slice(5,16) }}</span>
                        </div>
                    </div>
                    <el-empty v-if="!filteredArticles.length" description="暂无文章" :image-size="60" />
                </div>
            </el-card>

            <!-- 右侧: 图谱可视化 -->
            <el-card class="graph-card" shadow="never">
                <template #header>
                    <div class="graph-header">
                        <span>{{ graphTitle }}</span>
                        <div class="graph-actions">
                            <span class="stat-badge">实体: {{ currentEntities.length }}</span>
                            <span class="stat-badge">关系: {{ currentRelations.length }}</span>
                            <el-button v-if="currentArticleId && !showAggregated" size="small" type="danger" plain @click="deleteArticle">
                                <el-icon><Delete /></el-icon> 删除
                            </el-button>
                            <el-button v-if="!isSaved && currentEntities.length" size="small" type="success" @click="saveArticle">
                                <el-icon><Check /></el-icon> 保存
                            </el-button>
                        </div>
                    </div>
                </template>
                <div class="graph-main" v-loading="graphLoading">
                    <div ref="chartRef" class="chart-container"></div>
                    <el-empty v-if="!currentEntities.length && !graphLoading" description="粘贴文章后点击「提取图谱」" :image-size="80" />
                </div>
            </el-card>
        </div>

        <!-- 显示提取的实体列表 -->
        <el-card v-if="currentEntities.length" class="entity-detail" shadow="never">
            <template #header>
                <span>📋 实体详情</span>
            </template>
            <div class="entity-grid">
                <div v-for="e in currentEntities" :key="e.id" class="entity-tag" :style="{ borderLeftColor: typeColor(e.entity_type) }">
                    <span class="entity-type-badge" :class="e.entity_type">{{ typeLabel(e.entity_type) }}</span>
                    <span class="entity-name">{{ e.name }}</span>
                    <span v-if="e.code" class="entity-code">{{ e.code }}</span>
                </div>
            </div>
            <div v-if="currentRelations.length" class="relation-list">
                <div v-for="(r, i) in currentRelations.slice(0,30)" :key="i" class="relation-item">
                    {{ r.source }} <span class="rel-arrow">→</span> {{ r.target }}
                    <span class="rel-type">({{ r.relation }})</span>
                </div>
            </div>
        </el-card>
    </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MagicStick, Connection, Delete, Check, Search } from '@element-plus/icons-vue'
import * as echarts from 'echarts'

const API = '/api/v1/kg'

// ─── 状态 ────────────────────────────────────
const inputContent = ref('')
const articleTitle = ref('')
const extracting = ref(false)
const loadingArticles = ref(false)
const graphLoading = ref(false)

const articles = ref([])
const articleSearch = ref('')
const currentArticleId = ref(null)
const currentEntities = ref([])
const currentRelations = ref([])
const graphTitle = ref('知识图谱')
const isSaved = ref(false)
const showAggregated = ref(false)

const chartRef = ref(null)
let chartInstance = null

// ─── 计算属性 ────────────────────────────────
const filteredArticles = computed(() => {
    if (!articleSearch.value) return articles.value
    const q = articleSearch.value.toLowerCase()
    return articles.value.filter(a => (a.title || '').toLowerCase().includes(q))
})

// ─── 生命周期 ────────────────────────────────
onMounted(() => {
    loadArticleList()
})

onUnmounted(() => {
    if (chartInstance) chartInstance.dispose()
})

// ─── 方法 ────────────────────────────────────

function typeColor(entityType) {
    const map = {
        'company': '#409eff',
        'product': '#e6a23c',
        'industry_link': '#67c23a',
        'concept': '#f56c6c',
        'industry': '#909399',
    }
    return map[entityType] || '#909399'
}

function typeLabel(entityType) {
    const map = { 'company': '公司', 'product': '产品', 'industry_link': '环节', 'concept': '概念', 'industry': '行业' }
    return map[entityType] || '其他'
}

async function doExtract() {
    const text = inputContent.value.trim()
    if (!text) return
    extracting.value = true
    isSaved.value = false
    showAggregated.value = false

    const isUrl = text.startsWith('http://') || text.startsWith('https://')
    try {
        const resp = await fetch(`${API}/extract`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(isUrl ? { url: text, title: articleTitle.value } : { content: text, title: articleTitle.value })
        })
        const data = await resp.json()
        if (!data.success) {
            ElMessage.error(data.detail || '提取失败')
            return
        }
        const d = data.data
        currentEntities.value = d.entities || []
        currentRelations.value = d.relations || []
        graphTitle.value = d.title || '知识图谱'
        inputContent.value = d.content_preview || text

        ElMessage.success(`提取到 ${d.entity_count} 个实体, ${d.relation_count} 个关系`)
        currentArticleId.value = null
        await nextTick()
        renderGraph()
    } catch (e) {
        ElMessage.error('请求失败: ' + e.message)
    } finally {
        extracting.value = false
    }
}

async function saveArticle() {
    try {
        const resp = await fetch(`${API}/articles`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: graphTitle.value,
                source: inputContent.value.startsWith('http') ? 'url' : 'text',
                content: inputContent.value,
                entities: currentEntities.value,
                relations: currentRelations.value
            })
        })
        const data = await resp.json()
        if (data.success) {
            ElMessage.success(data.msg)
            isSaved.value = true
            await loadArticleList()
        }
    } catch (e) {
        ElMessage.error('保存失败: ' + e.message)
    }
}

async function loadArticleList() {
    loadingArticles.value = true
    try {
        const resp = await fetch(`${API}/articles`)
        const data = await resp.json()
        articles.value = data.data || []
    } catch (e) {
        console.error(e)
    } finally {
        loadingArticles.value = false
    }
}

async function loadArticle(id) {
    currentArticleId.value = id
    showAggregated.value = false
    graphLoading.value = true
    try {
        const resp = await fetch(`${API}/articles/${id}`)
        const data = await resp.json()
        if (!data.success) { ElMessage.error('加载失败'); return }
        const d = data.data
        currentEntities.value = d.entities || []
        currentRelations.value = d.relations || []
        graphTitle.value = d.title || '知识图谱'
        inputContent.value = d.content || ''
        isSaved.value = true
        await nextTick()
        renderGraph()
    } catch (e) {
        ElMessage.error('加载失败: ' + e.message)
    } finally {
        graphLoading.value = false
    }
}

async function loadAggregated() {
    showAggregated.value = true
    currentArticleId.value = null
    graphLoading.value = true
    try {
        const resp = await fetch(`${API}/graph/aggregated?min_count=1`)
        const data = await resp.json()
        if (!data.success) { ElMessage.error('加载失败'); return }
        const d = data.data
        currentEntities.value = d.entities || []
        currentRelations.value = d.relations || []
        graphTitle.value = `📊 聚合知识图谱 (${d.entity_count}实体, ${d.relation_count}关系)`
        await nextTick()
        renderGraph()
    } catch (e) {
        ElMessage.error('加载失败: ' + e.message)
    } finally {
        graphLoading.value = false
    }
}

async function deleteArticle() {
    if (!currentArticleId.value) return
    try {
        await ElMessageBox.confirm('确定删除这篇文章?', '确认', { type: 'warning' })
        const resp = await fetch(`${API}/articles/${currentArticleId.value}`, { method: 'DELETE' })
        const data = await resp.json()
        if (data.success) {
            ElMessage.success('已删除')
            currentArticleId.value = null
            currentEntities.value = []
            currentRelations.value = []
            graphTitle.value = '知识图谱'
            if (chartInstance) chartInstance.clear()
            await loadArticleList()
        }
    } catch (e) {
        if (e !== 'cancel') ElMessage.error('删除失败')
    }
}

function renderGraph() {
    if (!chartRef.value) return
    if (chartInstance) chartInstance.dispose()
    chartInstance = echarts.init(chartRef.value)

    const entities = currentEntities.value
    const relations = currentRelations.value

    if (!entities.length) {
        chartInstance.clear()
        return
    }

    // 构建节点
    const nodes = entities.map(e => ({
        id: e.id || e.name,
        name: e.name,
        symbolSize: Math.max(18, Math.min(45, 50 - (entities.indexOf(e) * 0.05))),
        itemStyle: { color: typeColor(e.entity_type) },
        category: e.category || '其他',
        attributes: { code: e.code || '', entity_type: e.entity_type || '' }
    }))

    // 构建边
    const links = []
    const seenLinks = new Set()
    for (const r of relations) {
        const srcNode = nodes.find(n => n.name === r.source)
        const tgtNode = nodes.find(n => n.name === r.target)
        if (srcNode && tgtNode) {
            const key = `${srcNode.id}|${tgtNode.id}`
            if (!seenLinks.has(key)) {
                seenLinks.add(key)
                links.push({
                    source: srcNode.id,
                    target: tgtNode.id,
                    label: { show: true, formatter: r.relation, fontSize: 10, color: '#909399' },
                    lineStyle: { color: '#ddd', width: r.weight ? Math.min(r.weight, 5) : 1.5, curveness: 0.2 }
                })
            }
        }
    }

    // 分类
    const categories = [...new Set(entities.map(e => e.category || '其他'))].map(c => ({ name: c }))

    const option = {
        title: { show: false },
        tooltip: {
            formatter: (p) => {
                if (p.dataType === 'node') {
                    const e = p.data
                    const typeLabels = { 'company': '公司', 'product': '产品/服务', 'industry_link': '产业链环节', 'concept': '概念板块', 'industry': '行业分类' }
                    const typeLabel = typeLabels[e.attributes?.entity_type] || e.category || '其他'
                    return `<b>${e.name}</b><br/>类型: ${typeLabel}${e.attributes?.code ? `<br/>代码: ${e.attributes.code}` : ''}${e.category && e.category !== typeLabel ? `<br/>行业: ${e.category}` : ''}`
                }
                const relLabels = {
                    '属于行业': '属于行业', '属于概念': '属于概念', '主营产品': '主营产品',
                    '上游供应': '上游供应', '下游需求': '下游需求', '处于': '处于',
                    '包含': '包含', '相关': '相关', '属于': '属于'
                }
                const label = relLabels[p.data.label?.formatter] || p.data.label?.formatter || '-'
                return `${p.data.source} → ${p.data.target}<br/>关系: ${label}`
            }
        },
        series: [{
            type: 'graph',
            layout: 'force',
            force: { repulsion: 500, edgeLength: [80, 200], gravity: 0.1, friction: 0.1 },
            roam: true,
            draggable: true,
            data: nodes,
            links: links,
            categories: categories,
            focusNodeAdjacency: true,
            edgeSymbol: ['none', 'arrow'],
            edgeSymbolSize: [0, 10],
            label: {
                show: true,
                position: 'right',
                fontSize: 11,
                color: '#333',
                formatter: (p) => p.name.length > 8 ? p.name.slice(0, 8) + '..' : p.name
            },
            lineStyle: { color: 'source', opacity: 0.6 }
        }]
    }

    chartInstance.setOption(option)
    window.addEventListener('resize', () => chartInstance?.resize())
}
</script>

<style scoped>
.kg-container {
    display: flex;
    flex-direction: column;
    height: 100%;
    gap: 12px;
}
.input-card { flex-shrink: 0; }
.input-row { display: flex; align-items: flex-start; gap: 0; }
.input-tip { font-size: 12px; color: #909399; margin-top: 6px; }
.kg-body { display: flex; gap: 12px; flex: 1; min-height: 0; }
.article-list { width: 280px; flex-shrink: 0; display: flex; flex-direction: column; }
.article-list :deep(.el-card__body) { flex: 1; overflow: hidden; display: flex; flex-direction: column; padding: 12px; }
.list-header { display: flex; justify-content: space-between; align-items: center; font-weight: 600; }
.list-toolbar { margin-bottom: 8px; }
.article-items { flex: 1; overflow-y: auto; }
.article-item {
    padding: 8px 10px;
    border-radius: 6px;
    cursor: pointer;
    margin-bottom: 4px;
    transition: background 0.2s;
    border: 1px solid transparent;
}
.article-item:hover { background: #f5f7fa; }
.article-item.active { background: #ecf5ff; border-color: #409eff; }
.article-title { font-size: 13px; font-weight: 500; color: #303133; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.article-meta { font-size: 11px; color: #909399; margin-top: 3px; display: flex; gap: 8px; }
.article-date { margin-left: auto; }

.graph-card { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.graph-card :deep(.el-card__body) { flex: 1; padding: 8px; overflow: hidden; }
.graph-header { display: flex; justify-content: space-between; align-items: center; font-weight: 600; }
.graph-actions { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.stat-badge {
    background: #f0f2f5;
    padding: 2px 10px;
    border-radius: 10px;
    color: #606266;
    font-weight: normal;
    font-size: 12px;
}
.graph-main { height: 100%; position: relative; }
.chart-container { width: 100%; height: 100%; min-height: 400px; }

.entity-detail { flex-shrink: 0; max-height: 200px; overflow-y: auto; }
.entity-grid { display: flex; flex-wrap: wrap; gap: 8px; }
.entity-tag {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 8px;
    background: #f5f7fa;
    border-radius: 4px;
    border-left: 3px solid #409eff;
    font-size: 12px;
}
.entity-type-badge {
    display: inline-block;
    padding: 0 5px;
    border-radius: 3px;
    font-size: 10px;
    font-weight: 600;
    color: #fff;
    line-height: 16px;
}
.entity-type-badge.company { background: #409eff; }
.entity-type-badge.product { background: #e6a23c; }
.entity-type-badge.industry_link { background: #67c23a; }
.entity-type-badge.concept { background: #f56c6c; }
.entity-type-badge.industry { background: #909399; }
.entity-name { font-weight: 500; color: #303133; }
.entity-cat { color: #909399; font-size: 11px; }
.entity-code { color: #409eff; font-size: 11px; font-family: monospace; }
.relation-list { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 4px; }
.relation-item { font-size: 12px; color: #606266; padding: 2px 6px; background: #f9f9f9; border-radius: 3px; }
.rel-arrow { color: #409eff; margin: 0 2px; font-weight: bold; }
.rel-type { color: #909399; font-size: 11px; }
</style>
