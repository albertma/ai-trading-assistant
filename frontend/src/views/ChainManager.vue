<template>
  <div class="chain-page">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
      <h2 style="margin:0;">🔗 产业链配置管理</h2>
      <div>
        <el-tag type="info" style="margin-right:8px;">已配置 {{ chains.length }} 个行业</el-tag>
        <el-tag v-if="unmappedCount != null" type="warning">{{ unmappedCount }} 个行业待配置</el-tag>
        <el-button type="primary" size="small" @click="showAddDialog = true" style="margin-left:12px;">+ 新增</el-button>
      </div>
    </div>

    <!-- ══════ 智能提取卡片 ══════ -->
    <el-card shadow="hover" style="margin-bottom:16px;border:1px solid #334;">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <b>🤖 智能提取</b>
          <span style="font-size:12px;color:#909399;">粘贴文章或输入URL，自动提取产业链信息</span>
        </div>
      </template>
      <el-input v-model="extractText" type="textarea" :rows="4" placeholder="粘贴文章内容，或输入URL链接..." style="margin-bottom:8px;" />
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
        <el-input v-model="extractUrl" placeholder="或输入URL（如 https://...）" style="max-width:400px;" size="small" clearable />
        <el-button type="primary" size="small" :loading="extracting" @click="doExtract">🔍 提取</el-button>
        <el-button size="small" @click="extractText = ''; extractUrl = ''; extractResult = null">清空</el-button>
      </div>

      <!-- 提取结果预览 -->
      <template v-if="extractResult">
        <el-divider />
        <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:8px;">
          <span style="font-weight:bold;">📋 提取结果</span>
          <el-tag type="success" size="small">行业: {{ extractResult.industry || '待确认' }}</el-tag>
          <el-tag type="info" size="small">识别到 {{ extractResult.total_companies }} 家公司</el-tag>
          <el-tag v-if="extractResult.source === 'url'" type="warning" size="small">来源: URL</el-tag>
        </div>

        <el-form label-width="120px" size="small">
          <el-form-item label="行业名称">
            <el-input v-model="extractForm.industry" placeholder="确认行业名称" style="max-width:300px;" />
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="extractForm.notes" placeholder="可选备注（如来源链接）" />
          </el-form-item>
        </el-form>

        <div style="font-size:13px;font-weight:bold;margin-bottom:8px;">产业链环节</div>
        <div v-for="(stage, si) in extractForm.stages" :key="si" style="margin-bottom:8px;padding:8px;background:rgba(255,255,255,0.03);border-radius:4px;">
          <div style="display:flex;gap:8px;margin-bottom:4px;">
            <el-input v-model="stage.name" placeholder="环节名（如：上游-资源）" size="small" style="width:180px;" />
            <el-button size="small" type="danger" link @click="extractForm.stages.splice(si, 1)">删除</el-button>
          </div>
          <el-select v-model="stage.boards" multiple filterable allow-create default-first-option
            placeholder="选择或输入概念板块名" style="width:100%;" size="small">
            <el-option v-for="b in allBoards" :key="b.name" :label="b.name" :value="b.name" />
          </el-select>
          <div v-if="stage.matched_companies?.length" style="margin-top:4px;font-size:11px;color:#909399;">
            📌 匹配公司: {{ stage.matched_companies.join('、') }}
          </div>
        </div>
        <div style="display:flex;gap:8px;margin-bottom:8px;">
          <el-button type="info" size="small" plain @click="extractForm.stages.push({ name: '', boards: [], matched_companies: [] })">+ 添加环节</el-button>
        </div>

        <!-- 识别到的公司列表 -->
        <details v-if="extractResult.companies?.length" style="margin-top:8px;">
          <summary style="cursor:pointer;font-size:13px;color:#909399;">📊 识别到 {{ extractResult.companies.length }} 家公司（点击展开）</summary>
          <div style="margin-top:4px;">
            <el-tag v-for="c in extractResult.companies" :key="c.code" size="small" style="margin:2px;" effect="plain">
              {{ c.name }} ({{ c.code }}) <span v-if="c.industry" style="color:#909399;">· {{ c.industry }}</span>
            </el-tag>
          </div>
        </details>

        <div style="margin-top:12px;">
          <el-button type="primary" :loading="savingExtract" @click="saveExtract">💾 保存产业链</el-button>
          <el-button @click="extractResult = null">取消</el-button>
        </div>
      </template>
    </el-card>

    <!-- 搜索过滤 -->
    <el-input v-model="search" placeholder="搜索行业..." clearable prefix-icon="Search" style="max-width:300px;margin-bottom:12px;" />

    <!-- 已配置列表 -->
    <el-table :data="filteredChains" border size="small" style="width:100%;" row-key="industry">
      <el-table-column label="行业" width="160" prop="industry" />
      <el-table-column label="产业链环节" min-width="300">
        <template #default="{ row }">
          <div v-for="(boards, stage) in row.chains" :key="stage" style="margin:2px 0;">
            <el-tag size="small" type="info" effect="plain" style="margin-right:4px;">{{ stage }}</el-tag>
            <span style="font-size:12px;color:#b0b0b0;">{{ boards.join('、') }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="备注" width="150" prop="notes" />
      <el-table-column label="更新时间" width="160" prop="updated_at" />
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="primary" link @click="editChain(row)">编辑</el-button>
          <el-button size="small" type="danger" link @click="confirmDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="showAddDialog" :title="editingIndustry ? `编辑: ${editingIndustry}` : '新增产业链'" width="700px" destroy-on-close>
      <el-form label-width="100px" size="small">
        <el-form-item label="行业名称" required>
          <el-autocomplete v-model="formIndustry" :fetch-suggestions="searchUnmapped" placeholder="输入行业名" style="width:100%;"
            :disabled="!!editingIndustry" @select="(v) => formIndustry = v.value" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="formNotes" placeholder="可选备注" />
        </el-form-item>
      </el-form>
      <el-divider />
      <div style="font-size:13px;font-weight:bold;margin-bottom:8px;">产业链环节配置</div>
      <div v-for="(stage, si) in formStages" :key="si" style="margin-bottom:8px;padding:8px;background:rgba(255,255,255,0.03);border-radius:4px;">
        <div style="display:flex;gap:8px;margin-bottom:4px;">
          <el-input v-model="stage.name" placeholder="环节名称（如：上游-原材料）" size="small" style="width:200px;" />
          <el-button size="small" type="danger" link @click="formStages.splice(si, 1)">删除</el-button>
        </div>
        <el-select v-model="stage.boards" multiple filterable allow-create default-first-option
          :placeholder="`搜索概念板块（${allBoards.length}个可用）`" style="width:100%;" size="small">
          <el-option v-for="b in allBoards" :key="b.name" :label="b.name" :value="b.name" />
        </el-select>
      </div>
      <el-button type="info" size="small" plain @click="formStages.push({ name: '', boards: [] })">+ 添加环节</el-button>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveForm">保存</el-button>
      </template>
    </el-dialog>

    <!-- 删除确认 -->
    <el-dialog v-model="showDeleteDialog" title="确认删除" width="400px">
      <p>确定删除 <b>{{ deletingIndustry }}</b> 的产业链配置？</p>
      <template #footer>
        <el-button @click="showDeleteDialog = false">取消</el-button>
        <el-button type="danger" :loading="deleting" @click="doDelete">确认删除</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  listIndustryChains, saveIndustryChain, deleteIndustryChain,
  listConceptBoards, listUnmappedIndustries,
  extractChainFromArticle, saveExtractedChain
} from '../api/index.js'

const chains = ref([])
const allBoards = ref([])
const unmappedIndustries = ref([])
const unmappedCount = ref(null)
const search = ref('')
const loading = ref(false)

const filteredChains = computed(() => {
  if (!search.value) return chains.value
  const q = search.value.toLowerCase()
  return chains.value.filter(c => c.industry.toLowerCase().includes(q))
})

// 新增/编辑
const showAddDialog = ref(false)
const editingIndustry = ref('')
const formIndustry = ref('')
const formNotes = ref('')
const formStages = ref([])
const saving = ref(false)

// 删除
const showDeleteDialog = ref(false)
const deletingIndustry = ref('')
const deleting = ref(false)

// 智能提取
const extractText = ref('')
const extractUrl = ref('')
const extracting = ref(false)
const extractResult = ref(null)
const extractForm = ref({ industry: '', stages: [], notes: '' })
const savingExtract = ref(false)

async function loadData() {
  loading.value = true
  try {
    const [chainRes, boardRes, unmappedRes] = await Promise.all([
      listIndustryChains(),
      listConceptBoards(),
      listUnmappedIndustries()
    ])
    chains.value = chainRes.data?.data || []
    allBoards.value = boardRes.data?.data || []
    if (unmappedRes.data?.success) {
      unmappedIndustries.value = (unmappedRes.data.data || []).map(i => ({ value: i }))
      unmappedCount.value = unmappedRes.data.total
    }
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

function searchUnmapped(query, cb) {
  const q = query.toLowerCase()
  cb(unmappedIndustries.value.filter(i => i.value.toLowerCase().includes(q)))
}

function editChain(row) {
  editingIndustry.value = row.industry
  formIndustry.value = row.industry
  formNotes.value = row.notes || ''
  formStages.value = Object.entries(row.chains || {}).map(([name, boards]) => ({ name, boards: [...boards] }))
  showAddDialog.value = true
}

async function saveForm() {
  if (!formIndustry.value) { ElMessage.warning('请输入行业名称'); return }
  const chainData = {}
  for (const s of formStages.value) {
    if (!s.name) continue
    chainData[s.name] = s.boards
  }
  if (Object.keys(chainData).length === 0) { ElMessage.warning('至少配置一个环节'); return }
  saving.value = true
  try {
    await saveIndustryChain(formIndustry.value, chainData, formNotes.value)
    ElMessage.success('保存成功')
    showAddDialog.value = false
    await loadData()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally { saving.value = false }
}

function confirmDelete(row) {
  deletingIndustry.value = row.industry
  showDeleteDialog.value = true
}

async function doDelete() {
  deleting.value = true
  try {
    await deleteIndustryChain(deletingIndustry.value)
    ElMessage.success('已删除')
    showDeleteDialog.value = false
    await loadData()
  } catch (e) {
    ElMessage.error('删除失败')
  } finally { deleting.value = false }
}

// 智能提取
async function doExtract() {
  const content = extractText.value.trim()
  const url = extractUrl.value.trim()
  if (!content && !url) { ElMessage.warning('请粘贴文章或输入URL'); return }
  extracting.value = true
  extractResult.value = null
  try {
    const { data } = await extractChainFromArticle({ content: content || undefined, url: url || undefined })
    if (data.success) {
      extractResult.value = data.data
      extractForm.value = {
        industry: data.data.industry || '',
        notes: url ? `来源: ${url}` : '',
        stages: (data.data.stages || []).map(s => ({
          name: s.name,
          boards: s.boards || [],
          matched_companies: s.matched_companies || []
        }))
      }
      ElMessage.success(`提取完成！识别到 ${data.data.total_companies} 家公司`)
    } else {
      ElMessage.error(data.msg || '提取失败')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '提取失败')
  } finally { extracting.value = false }
}

async function saveExtract() {
  if (!extractForm.value.industry) { ElMessage.warning('请确认行业名称'); return }
  savingExtract.value = true
  try {
    await saveExtractedChain(extractForm.value)
    ElMessage.success(`✅ 产业链 [${extractForm.value.industry}] 保存成功`)
    extractResult.value = null
    extractText.value = ''
    extractUrl.value = ''
    await loadData()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally { savingExtract.value = false }
}

onMounted(loadData)
</script>

<style scoped>
.chain-page { max-width: 1200px; margin: 0 auto; padding: 20px; }
</style>
