<template>
    <div class="news-page">
        <!-- 顶部：地区选择 + 分类选择 -->
        <el-card shadow="never" class="news-toolbar">
            <div class="toolbar-row">
                <el-radio-group v-model="region" size="small" @change="loadNews">
                    <el-radio-button value="">🌍 全部</el-radio-button>
                    <el-radio-button v-for="(info, r) in regions" :key="r" :value="r">
                        {{ info.icon }} {{ r }}
                    </el-radio-button>
                </el-radio-group>
                <span class="toolbar-spacer"></span>
                <el-radio-group v-model="category" size="small" @change="loadNews">
                    <el-radio-button value="">📋 全部</el-radio-button>
                    <el-radio-button value="产业">🏭 产业</el-radio-button>
                    <el-radio-button value="财经">💰 财经</el-radio-button>
                    <el-radio-button value="政治">🏛️ 政治</el-radio-button>
                    <el-radio-button value="市场">📊 市场</el-radio-button>
                    <el-radio-button value="生态">🔗 生态</el-radio-button>
                    <el-radio-button value="监管">⚖️ 监管</el-radio-button>
                </el-radio-group>
                <el-button size="small" style="margin-left:12px" @click="loadNews" :loading="loading" icon="Refresh">刷新</el-button>
            </div>
            <div class="toolbar-meta">
                <span v-if="lastUpdated">🕐 更新于 {{ lastUpdated }}</span>
                <span style="color:#909399;font-size:12px;margin-left:auto">数据来源：Google News</span>
            </div>
        </el-card>

        <!-- 新闻内容 -->
        <div v-loading="loading" class="news-content">

            <!-- 按地区分组 -->
            <template v-for="(regData, regName) in filteredData" :key="regName">
                <div class="region-section">
                    <div class="region-header">
                        <span class="region-icon">{{ regData.icon }}</span>
                        <span class="region-name">{{ regName }}</span>
                    </div>

                    <!-- 地区内按分类 -->
                    <div v-for="(newsList, catName) in regData.categories" :key="catName" class="category-section">
                        <div class="category-header" v-if="newsList.length">
                            <el-tag :type="catTagType(catName)" size="small" effect="dark">{{ catIcon(catName) }} {{ catName }}</el-tag>
                            <span class="category-count">{{ newsList.length }} 条</span>
                        </div>

                        <!-- 新闻卡片 -->
                        <div v-if="newsList.length" class="news-grid">
                            <a v-for="(item, i) in newsList" :key="i"
                                :href="item.link" target="_blank" rel="noopener"
                                class="news-card"
                                @click.prevent="openLink(item.link)">
                                <div class="news-title">{{ item.title }}</div>
                                <div class="news-meta">
                                    <span class="news-source">{{ item.source || '未知来源' }}</span>
                                    <span class="news-date">{{ formatDate(item.published) }}</span>
                                </div>
                                <div v-if="item.summary" class="news-summary">{{ item.summary }}</div>
                            </a>
                        </div>

                        <div v-else-if="!loading" class="category-empty">
                            <span style="color:#909399;font-size:13px;">暂无 {{ regName }} {{ catName }} 新闻</span>
                        </div>
                    </div>
                </div>
            </template>

            <el-empty v-if="!hasData && !loading" description="点击「刷新」获取最新新闻" :image-size="80" />
        </div>
    </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

const API = '/api/v1'

const region = ref('')
const category = ref('')
const loading = ref(false)
const newsData = ref(null)
const lastUpdated = ref('')

const regions = {
    '中国': { icon: '🇨🇳' },
    '美国': { icon: '🇺🇸' },
    '欧洲': { icon: '🇪🇺' },
    '日本': { icon: '🇯🇵' },
    '加密': { icon: '🪙' },
}

const hasData = computed(() => {
    if (!newsData.value) return false
    return Object.values(newsData.value).some(r =>
        Object.values(r.categories).some(c => c.length > 0)
    )
})

const filteredData = computed(() => {
    if (!newsData.value) return {}
    const entries = Object.entries(newsData.value)
    if (region.value) {
        return Object.fromEntries(entries.filter(([k]) => k === region.value))
    }
    return newsData.value
})

function catTagType(cat) {
    const map = { '产业': 'success', '财经': 'warning', '政治': 'danger' }
    return map[cat] || 'info'
}

function catIcon(cat) {
    const map = { '产业': '🏭', '财经': '💰', '政治': '🏛️' }
    return map[cat] || '📰'
}

function formatDate(pubDate) {
    if (!pubDate) return ''
    try {
        const d = new Date(pubDate)
        const now = new Date()
        const diff = (now - d) / 1000
        if (diff < 3600) return `${Math.round(diff / 60)}分钟前`
        if (diff < 86400) return `${Math.round(diff / 3600)}小时前`
        return `${d.getMonth() + 1}/${d.getDate()}`
    } catch {
        return pubDate.slice(0, 10)
    }
}

function openLink(url) {
    window.open(url, '_blank', 'noopener,noreferrer')
}

async function loadNews() {
    loading.value = true
    try {
        const params = new URLSearchParams()
        if (region.value) params.set('region', region.value)
        if (category.value) params.set('category', category.value)
        const resp = await fetch(`${API}/news/overview?${params}`)
        const data = await resp.json()
        if (data.success) {
            newsData.value = data.data
            lastUpdated.value = data.updated_at
        } else {
            ElMessage.error('获取新闻失败')
        }
    } catch (e) {
        ElMessage.error('网络错误: ' + e.message)
    } finally {
        loading.value = false
    }
}

onMounted(() => {
    loadNews()
})
</script>

<style scoped>
.news-page {
    display: flex;
    flex-direction: column;
    height: 100%;
    gap: 12px;
}
.news-toolbar { flex-shrink: 0; }
.toolbar-row {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0;
}
.toolbar-spacer { width: 24px; }
.toolbar-meta {
    display: flex;
    align-items: center;
    margin-top: 8px;
    font-size: 12px;
    color: #909399;
}

.news-content {
    flex: 1;
    overflow-y: auto;
}

/* 地区 */
.region-section {
    margin-bottom: 20px;
}
.region-header {
    font-size: 16px;
    font-weight: 700;
    margin-bottom: 8px;
    padding-bottom: 6px;
    border-bottom: 2px solid #ebeef5;
}
.region-icon { margin-right: 6px; }

/* 分类 */
.category-section {
    margin-bottom: 12px;
}
.category-header {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 6px;
    padding-left: 8px;
}
.category-count { font-size: 11px; color: #909399; }

/* 新闻网格 */
.news-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 8px;
    padding-left: 8px;
}
.news-card {
    display: block;
    padding: 10px 12px;
    border: 1px solid #ebeef5;
    border-radius: 6px;
    text-decoration: none;
    color: #303133;
    transition: all 0.2s;
    cursor: pointer;
    background: #fff;
}
.news-card:hover {
    border-color: #409eff;
    box-shadow: 0 2px 8px rgba(64,158,255,0.1);
    transform: translateY(-1px);
}
.news-title {
    font-size: 13px;
    font-weight: 600;
    line-height: 1.5;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    margin-bottom: 4px;
}
.news-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    margin-bottom: 4px;
}
.news-source { color: #409eff; font-weight: 500; }
.news-date { color: #c0c4cc; }
.news-summary {
    font-size: 11px;
    color: #909399;
    line-height: 1.5;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}
.category-empty { padding: 8px 0 8px 8px; }
</style>
