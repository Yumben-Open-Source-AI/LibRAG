<template>
  <div class="lib-rag-app p-4 space-y-6">
    <!-- Title -->
    <h1 class="text-3xl font-bold text-center">LibRAG</h1>

    <!-- Tabs -->
    <el-tabs v-model="activeTab" type="border-card">
      <!-- ---------------- 知识库管理 TAB ---------------- -->
      <el-tab-pane label="知识库管理" name="kb">
        <!-- Toolbar -->
        <div class="flex flex-wrap gap-2 mb-4">
          <el-button type="primary" @click="openCreateDialog">创建知识库</el-button>
          <el-button @click="openAppendDialog" :disabled="!selectedKB">追加新文件</el-button>
          <el-button type="danger" plain @click="openDeleteDialog" :disabled="!selectedKB">删除知识库</el-button>
        </div>

        <!-- All KB Table -->
        <el-table
          :data="kbTableData"
          height="260"
          highlight-current-row
          @row-click="handleKBRowClick"
        >
          <el-table-column prop="kb_id" label="知识库ID" width="120"/>
          <el-table-column prop="kb_name" label="知识库名称"/>
          <el-table-column prop="kb_description" label="知识库描述"/>
        </el-table>

        <!-- File list of selected KB -->
        <el-table
          v-if="selectedKB"
          :data="fileTableData"
          height="650"
          class="mt-6"
        >
          <el-table-column prop="document_id" label="文档ID" width="120"/>
          <el-table-column prop="文档名称" label="文档名称"/>
          <el-table-column prop="文档描述" label="文档描述"/>
          <el-table-column prop="切割策略" label="切割策略" width="160"/>
        </el-table>
      </el-tab-pane>

      <!-- ---------------- 召回测试 TAB ---------------- -->
      <el-tab-pane label="召回测试" name="recall">
        <!-- Query bar -->
        <div class="flex flex-wrap items-center gap-2 mb-4">
          <el-input
            v-model="query"
            placeholder="请输入查询，建议陈述性语句"
            class="flex-1"
          />
          <el-select v-model="selectedKBOption" placeholder="选择知识库" style="width:220px">
            <el-option
              v-for="opt in kbOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
          <el-button type="primary" @click="doRecall">测试召回</el-button>
          <el-button @click="resetRecall">重置查询</el-button>
        </div>

        <!-- Recall result table -->
        <el-table :data="recallTableData" height="650">
          <el-table-column prop="paragraph_id" label="段落ID" width="150"/>
          <el-table-column prop="summary" label="段落摘要"/>
          <el-table-column prop="content" label="段落内容"/>
          <el-table-column prop="parent_description" label="来源描述"/>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- ---------------- 创建 KB Dialog ---------------- -->
    <el-dialog v-model="createDialogVisible" title="创建新知识库" width="800px">
      <el-form :model="createForm" label-width="120px">
        <el-form-item label="知识库名称">
          <el-input v-model="createForm.name"/>
        </el-form-item>
        <el-form-item label="知识库描述">
          <el-input v-model="createForm.desc"/>
        </el-form-item>
        <el-form-item label="上传文件">
          <el-upload
            multiple
            :auto-upload="false"
            :file-list="createFileList"
            :on-change="handleCreateUpload"
            drag
          >
            <i class="el-icon-upload"/>
            <div class="el-upload__text">拖拽文件到此或 <em>点击上传</em></div>
          </el-upload>
        </el-form-item>
      </el-form>

      <!-- Files preview & strategy table -->
      <el-table :data="createFileRows" v-if="createFileRows.length" size="small" class="mb-4">
        <el-table-column prop="filename" label="文件名"/>
        <el-table-column prop="size" label="大小(KB)" width="120"/>
        <el-table-column prop="type" label="文件类型" width="120"/>
        <el-table-column label="切割策略" width="200">
          <template #default="{ row }">
            <el-select v-model="row.strategy" placeholder="选择策略" size="small">
              <el-option
                v-for="(val,label) in ALL_STRATEGY"
                :key="label"
                :label="label"
                :value="label"
              />
            </el-select>
          </template>
        </el-table-column>
      </el-table>

      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- ---------------- 追加文件 Dialog ---------------- -->
    <el-dialog v-model="appendDialogVisible" title="追加新文件" width="800px">
      <el-upload
        multiple
        :auto-upload="false"
        :file-list="appendFileList"
        :on-change="handleAppendUpload"
        drag
      >
        <i class="el-icon-upload"/>
        <div class="el-upload__text">拖拽文件到此或 <em>点击上传</em></div>
      </el-upload>

      <!-- Files & strategy -->
      <el-table :data="appendFileRows" v-if="appendFileRows.length" size="small" class="my-4">
        <el-table-column prop="filename" label="文件名"/>
        <el-table-column prop="size" label="大小(KB)" width="120"/>
        <el-table-column prop="type" label="文件类型" width="120"/>
        <el-table-column label="切割策略" width="200">
          <template #default="{ row }">
            <el-select v-model="row.strategy" placeholder="选择策略" size="small">
              <el-option
                v-for="(val,label) in ALL_STRATEGY"
                :key="label"
                :label="label"
                :value="label"
              />
            </el-select>
          </template>
        </el-table-column>
      </el-table>

      <template #footer>
        <el-button @click="appendDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAppend">追加</el-button>
      </template>
    </el-dialog>

    <!-- ---------------- 删除 KB Dialog ---------------- -->
    <el-dialog v-model="deleteDialogVisible" title="删除知识库" width="400px">
      <span>确认删除选中的知识库？此操作无法撤销！</span>
      <template #footer>
        <el-button @click="deleteDialogVisible = false">取消</el-button>
        <el-button type="danger" @click="submitDelete">删除</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

/* ---------------- 常量 & 基础 ---------------- */
const BASE_URL = 'http://127.0.0.1:13113/ai/'
const ALL_STRATEGY = {
  '按页切割': 'page_split',
  '按目录切割': 'catalog_split',
  '智能上下文切割': 'automate_judgment_split',
  '智能语义分块切割': 'agentic_chunking'
}

/* ---------------- 全局状态 ---------------- */
const activeTab = ref('kb')
const kbTableData = ref([])
const fileTableData = ref([])
const selectedKB = ref(null) // { kb_id, kb_name }

// recall
const query = ref('')
const selectedKBOption = ref('')
const recallTableData = ref([])

// dialogs
const createDialogVisible = ref(false)
const appendDialogVisible = ref(false)
const deleteDialogVisible = ref(false)

/* ----- 创建 KB 表单 ---- */
const createForm = reactive({ name: '', desc: '' })
const createFileList = ref([]) // el-upload list 格式
const createFileRows = ref([]) // [{file,filename,size,type,strategy}]

/* ----- 追加文件 ---- */
const appendFileList = ref([])
const appendFileRows = ref([])

/* ---------------- 计算属性 ---------------- */
const kbOptions = computed(() =>
  kbTableData.value.map(k => ({
    label: `${k.kb_id}:${k.kb_name}`,
    value: `${k.kb_id}:${k.kb_name}`
  }))
)

/* ---------------- API ---------------- */
const api = axios.create({ baseURL: BASE_URL })

async function fetchKnowledgeBases() {
  const { data } = await api.get('knowledge_bases')
  kbTableData.value = data
}

async function fetchDocuments(kbId) {
  const { data } = await api.get(`knowledge_base/${kbId}`)
  fileTableData.value = data.documents.map(d => ({
    ...d,
    文档名称: d.document_name,
    文档描述: d.document_description,
    切割策略: d.parse_strategy || ''
  }))
}

/* ---------------- 事件处理 ---------------- */
function handleKBRowClick(row) {
  selectedKB.value = row
  selectedKBOption.value = `${row.kb_id}:${row.kb_name}`
  fetchDocuments(row.kb_id)
}

function openCreateDialog() {
  createDialogVisible.value = true
  Object.assign(createForm, { name: '', desc: '' })
  createFileList.value = []
  createFileRows.value = []
}
function openAppendDialog() {
  appendDialogVisible.value = true
  appendFileList.value = []
  appendFileRows.value = []
}
function openDeleteDialog() {
  deleteDialogVisible.value = true
}

/* ----- 上传 change ----- */
function fileInfoFromRawFile(raw) {
  return {
    file: raw,
    filename: raw.name,
    size: (raw.size / 1024).toFixed(2),
    type: raw.name.split('.').pop(),
    strategy: '智能上下文切割'
  }
}
function handleCreateUpload(file, fileList) {
  createFileRows.value = fileList.map(f => fileInfoFromRawFile(f.raw))
  createFileList.value = fileList
}
function handleAppendUpload(file, fileList) {
  appendFileRows.value = fileList.map(f => fileInfoFromRawFile(f.raw))
  appendFileList.value = fileList
}

/* ----- 提交创建 KB ----- */
async function submitCreate() {
  if (!createForm.name.trim()) {
    ElMessage.warning('知识库名称不能为空')
    return
  }
  if (!createForm.desc.trim()) {
    ElMessage.warning('知识库描述不能为空')
    return
  }
  if (!createFileRows.value.length) {
    ElMessage.warning('请选择至少一个文件')
    return
  }

  // 1. 创建 KB
  const { data: newKB } = await api.post('knowledge_bases', {
    kb_name: createForm.name,
    kb_description: createForm.desc,
    keywords: ''
  })
  // 2. 上传文件
  const formData = new FormData()
  createFileRows.value.forEach(row => {
    formData.append('files', row.file)
  })
  // 组装 items json
  const items = createFileRows.value.map(row => ({
    kb_id: newKB.kb_id,
    policy_type: ALL_STRATEGY[row.strategy]
  }))
  formData.append('items', new Blob([JSON.stringify(items)], { type: 'application/json' }))
  await api.post('upload', formData)

  ElMessage.success(`知识库『${createForm.name}』创建成功，共 ${createFileRows.value.length} 个文件`)
  createDialogVisible.value = false
  await fetchKnowledgeBases()
}

/* ----- 追加文件 ----- */
async function submitAppend() {
  if (!appendFileRows.value.length) {
    ElMessage.warning('请选择至少一个文件')
    return
  }
  if (!selectedKB.value) return

  const formData = new FormData()
  appendFileRows.value.forEach(row => {
    formData.append('files', row.file)
  })
  const items = appendFileRows.value.map(row => ({
    kb_id: selectedKB.value.kb_id,
    policy_type: ALL_STRATEGY[row.strategy]
  }))
  formData.append('items', new Blob([JSON.stringify(items)], { type: 'application/json' }))
  await api.post('upload', formData)

  ElMessage.success(`成功追加 ${appendFileRows.value.length} 个文件`)
  appendDialogVisible.value = false
  await fetchDocuments(selectedKB.value.kb_id)
}

/* ----- 删除 KB ----- */
async function submitDelete() {
  if (!selectedKB.value) return
  await api.delete(`knowledge_base/${selectedKB.value.kb_id}`)
  ElMessage.success('知识库删除成功')
  deleteDialogVisible.value = false
  selectedKB.value = null
  fileTableData.value = []
  await fetchKnowledgeBases()
}

/* ----- 召回测试 ----- */
async function doRecall() {
  if (!query.value.trim()) {
    ElMessage.warning('请输入查询内容')
    return
  }
  if (!selectedKBOption.value) {
    ElMessage.warning('请选择知识库')
    return
  }
  const [kb_id] = selectedKBOption.value.split(':')
  const { data } = await api.get('recall', {
    params: {
      kb_id,
      question: query.value
    }
  })
  recallTableData.value = data.map(par => ({
    paragraph_id: par.paragraph_id,
    summary: par.summary,
    content: par.content,
    parent_description: par.parent_description
  }))
}
function resetRecall() {
  query.value = ''
  selectedKBOption.value = ''
  recallTableData.value = []
}

/* ---------------- 初始化 ---------------- */
fetchKnowledgeBases()
</script>

<style scoped>
.lib-rag-app {
  max-width: 1600px;
  margin: 0 auto;
}
</style>
