<template>
    <div class="reports-page">
        <el-row :gutter="16">
            <el-col :span="8">
                <el-card shadow="hover">
                    <template #header><b>📋 报告列表</b></template>
                    <el-table :data="reportList" stripe size="small" style="width:100%" v-loading="loadingList"
                        highlight-current-row @row-click="loadReport">
                        <el-table-column prop="date" label="日期" width="120" />
                        <el-table-column prop="size" label="大小" width="80">
                            <template #default="{ row }">{{ (row.size / 1024).toFixed(1) }}KB</template>
                        </el-table-column>
                    </el-table>
                    <el-empty v-if="!loadingList && !reportList.length" description="暂无报告" />
                </el-card>
            </el-col>
            <el-col :span="16">
                <el-card shadow="hover">
                    <template #header><b>📄 {{ currentTitle }}</b></template>
                    <div class="report-content" v-loading="loadingContent">
                        <div v-if="reportContent" v-html="renderedContent" class="markdown-body"></div>
                        <el-empty v-else description="选择左侧报告查看" />
                    </div>
                </el-card>
            </el-col>
        </el-row>
    </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getReportList, getDailyReport, getReportByDate } from '../api/index.js'
import { ElMessage } from 'element-plus'

const loadingList = ref(true)
const loadingContent = ref(false)
const reportList = ref([])
const reportContent = ref('')
const currentTitle = ref('请选择报告')

function renderMarkdown(md) {
    // 简单 markdown 转 HTML
    let html = md
        // 标题
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        .replace(/^# (.+)$/gm, '<h1>$1</h1>')
        // 粗体
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        // 列表
        .replace(/^- (.+)$/gm, '<li>$1</li>')
        .replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
        // 表格
        .replace(/\|(.+)\|/g, (match) => {
            if (match.includes('---')) return ''
            const cells = match.split('|').filter(c => c.trim())
            return '<tr><td>' + cells.join('</td><td>') + '</td></tr>'
        })
        // 换行
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>')
    return '<p>' + html + '</p>'
}

const renderedContent = computed(() => {
    if (!reportContent.value) return ''
    return renderMarkdown(reportContent.value)
})

async function loadReport(row) {
    loadingContent.value = true
    reportContent.value = ''
    currentTitle.value = `${row.date} 复盘报告`
    try {
        const { data } = row.date
            ? await getReportByDate(row.date)
            : await getDailyReport()
        reportContent.value = data.content || ''
    } catch (e) {
        ElMessage.warning('加载报告失败: ' + (e.response?.data?.detail || e.message))
    } finally {
        loadingContent.value = false
    }
}

onMounted(async () => {
    try {
        const { data } = await getReportList()
        reportList.value = data.reports || []
        if (reportList.value.length) {
            await loadReport(reportList.value[0])
        }
    } catch (e) {
        // ignore
    } finally {
        loadingList.value = false
    }
})
</script>

<style scoped>
.reports-page { max-width: 1400px; margin: 0 auto; }
.report-content {
    min-height: 400px;
    padding: 10px;
    font-size: 14px;
    line-height: 1.8;
}
.report-content :deep(h1),
.report-content :deep(h2),
.report-content :deep(h3) {
    margin-top: 16px;
    margin-bottom: 8px;
    color: #303133;
}
.report-content :deep(table) {
    width: 100%;
    border-collapse: collapse;
    margin: 8px 0;
    font-size: 13px;
}
.report-content :deep(td) {
    border: 1px solid #e4e7ed;
    padding: 4px 8px;
}
.report-content :deep(strong) { color: #409eff; }
</style>
