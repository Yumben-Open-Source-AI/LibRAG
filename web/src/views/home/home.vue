<template>
  <div class="lib-rag-app p-4 space-y-6">

    <el-header>
      <el-row>
        <el-col :span="24">
          <el-text class="mx-1" type="primary" size="large"
            style="display: flex; justify-content: center; font-size: 30px;">LibRAG
          </el-text>
        </el-col>
      </el-row>
    </el-header>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="知识库管理" name="kb">
        <el-container class="knowledge-container">
          <!-- ---------------- 左侧：知识库列表 ---------------- -->
          <el-aside width="25%" class="left-panel">
            <el-card shadow="hover">
              <template #header>
                <div class="card-header">
                  <span style="font-size: 15px;">知识库列表</span>
                  <el-button style="float: right;" @click="openCreateDialog" round>创建知识库</el-button>
                </div>
              </template>

              <!-- 卡片视图替换表格视图 -->
              <el-scrollbar :height=headerHeight>
                <el-card v-for="kb in kbTableData" :key="kb.kb_id"
                  :class="['kb-card', { selected: selectedKB && kb.kb_id === selectedKB.kb_id }]"
                  @click="handleKBRowClick(kb)" shadow="hover" style="margin-bottom:12px;cursor:pointer;">
                  <template #header>
                    <div class="flex justify-between items-center">
                      <span class="font-medium">{{ kb.kb_name }} (KB_ID:{{ kb.kb_id }})</span>
                    </div>
                  </template>

                  <p class="kb-desc">{{ kb.kb_description }}</p>

                  <template #footer>
                    <div class="grid grid-cols-2 gap-3">
                      <el-button type="primary" size="small" :disabled="kb !== selectedKB"
                        @click.stop="openAppendDialog" round>追加新文件
                      </el-button>
                      <el-button type="success" size="small" :disabled="kb !== selectedKB"
                        @click.stop="openUpdateIndexDialog" round>重构建索引
                      </el-button>
                      <el-button type="danger" size="small" :disabled="kb !== selectedKB"
                        @click.stop="openDeleteKBDialog" round>删除知识库
                      </el-button>
                    </div>
                  </template>
                </el-card>
              </el-scrollbar>
            </el-card>
          </el-aside>

          <el-main class="right-panel">
            <el-card shadow="hover">
              <template #header>
                <div class="card-header">
                  <div v-if="selectedKB" class="sub-title">
                    知识库：{{ selectedKB.kb_name }}
                    <el-tag type="info">{{ fileTableData.length }}篇文档</el-tag>
                  </div>
                </div>
              </template>

              <el-scrollbar v-if="selectedKB" :height=headerHeight class="doc-scroll">
                <el-card v-for="doc in fileTableData" :key="doc.document_id" class="mb-4" shadow="always">
                  <div v-if="doc.task">
                    <el-descriptions :title="'正在处理的文档: ' + doc.task.file_path" :column="3" size="small" border>
                      <el-descriptions-item label="状态" span="2">{{ doc['task']['status'] }}
                      </el-descriptions-item>
                      <el-descriptions-item label="切割策略">{{ doc.task.parse_strategy }}</el-descriptions-item>
                      <el-descriptions-item label="创建时间">{{ doc.task.created_at }}</el-descriptions-item>
                      <el-descriptions-item label="开始时间">{{ doc.task.started_at }}</el-descriptions-item>
                      <el-descriptions-item label="完成时间">{{ doc.task.completed_at }}</el-descriptions-item>
                      <el-descriptions-item label="进度条">
                        <el-steps style="margin-top: 10px; transform: scale(0.95); transform-origin: top; height: 55px;"
                          :active="doc.task.progress" finish-status="success" align-center>
                          <el-step title="解析段落" />
                          <el-step title="解析文档" />
                          <el-step title="解析类别" />
                          <el-step title="解析领域" />
                        </el-steps>
                      </el-descriptions-item>
                    </el-descriptions>
                  </div>
                  <div v-else>
                    <el-descriptions :title="doc['文档名称']" :column="3" size="small" border>
                      <template #extra>
                        <el-button type="info" size="small" @click="handleDocRowClick(null, doc)" round>查看段落
                        </el-button>
                        <el-button type="danger" size="small" style="margin-left:4px;"
                          @click="openDeleteDocDialog(null, doc)" round>删除文档
                        </el-button>
                      </template>
                      <el-descriptions-item width="70px" label="文档描述" :span="3">{{
                        doc['文档描述']
                      }}
                      </el-descriptions-item>
                      <el-descriptions-item label="文档ID">{{ doc.document_id }}</el-descriptions-item>
                      <el-descriptions-item label="切割策略">{{ doc['切割策略'] }}</el-descriptions-item>
                      <el-descriptions-item label="更新时间">{{
                        doc.meta_data?.['最后更新时间'] || '-'
                      }}
                      </el-descriptions-item>
                    </el-descriptions>
                  </div>
                </el-card>
              </el-scrollbar>

            </el-card>
          </el-main>
        </el-container>
      </el-tab-pane>

      <el-tab-pane label="召回测试" name="recall">
        <div class="flex flex-wrap items-center gap-2 mb-4">
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="请输入查询：">
                <el-input type="textarea" v-model="query" placeholder="请输入查询，建议陈述性语句" class="flex-1" />
              </el-form-item>
            </el-col>
            <el-col :span="4">
              <el-form-item label="知识库：">
                <el-select v-model="selectedKBOption" placeholder="选择知识库" style="width:220px">
                  <el-option v-for="opt in kbOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="4">
              <el-button type="primary" @click="doRecall" v-loading.fullscreen.lock="fullscreenLoading" round>测试召回
              </el-button>
              <el-button @click="resetRecall" round>重置查询</el-button>
            </el-col>
          </el-row>
        </div>

        <el-table :data="recallTableData" border height="650">
          <el-table-column prop="paragraph_id" label="段落ID" width="150" />
          <el-table-column prop="summary" label="段落摘要" />
          <el-table-column prop="content" label="段落内容" />
          <el-table-column prop="parent_description" label="来源描述" />
          <el-table-column prop="context_relevance" align="center" width="100" label="语境相关性" />
          <el-table-column prop="context_sufficiency" align="center" width="120" label="上下文充分性" />
          <el-table-column prop="context_clarity" align="center" width="100" label="语境清晰性" />
          <el-table-column prop="total_score" align="center" width="100" label="汇总得分" />
          <el-table-column prop="diagnosis" width="100" label="诊断信息" />
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 创建 KB & 提交文件 Dialog -->
    <el-dialog v-model="createDialogVisible" title="创建新知识库 & 提交文件" width="40%">
      <el-form :model="createForm" label-width="100px">
        <el-row>
          <el-col :span="24">
            <el-form-item label="知识库名称：">
              <el-input v-model="createForm.name" width="100%" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="知识库描述：">
              <el-input type="textarea" v-model="createForm.desc" width="100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="上传文件：">
          <el-upload multiple :auto-upload="false" :file-list="createFileList" :on-change="handleCreateUpload"
            :on-remove="handleCreateRemove" drag style="width: 100%;">
            <i class="el-icon-upload" />
            <div class="el-upload__text">拖拽文件到此或 <em>点击上传</em></div>
          </el-upload>
        </el-form-item>
      </el-form>

      <!-- Files preview & strategy table -->
      <el-table :data="createFileRows" border v-if="createFileRows.length" size="small" class="mb-4">
        <el-table-column prop="filename" label="文件名" />
        <el-table-column prop="size" label="大小(KB)" width="120" />
        <el-table-column prop="type" label="文件类型" width="120" />
        <el-table-column label="切割策略" width="200">
          <template #default="{ row }">
            <el-select v-model="row.strategy" placeholder="选择策略" size="small">
              <el-option v-for="(val, label) in ALL_STRATEGY" :key="label" :label="label" :value="label" />
            </el-select>
          </template>
        </el-table-column>
      </el-table>

      <template #footer>
        <el-button @click="createDialogVisible = false" round>取消</el-button>
        <el-button type="primary" @click="submitCreate" round>创建</el-button>
      </template>
    </el-dialog>

    <!-- 追加文件 Dialog -->
    <el-dialog v-model="appendDialogVisible" title="追加新文件" width="800px">
      <el-upload multiple :auto-upload="false" :file-list="appendFileList" :on-change="handleAppendUpload"
        :on-remove="handleAppendRemove" drag>
        <i class="el-icon-upload" />
        <div class="el-upload__text">拖拽文件到此或 <em>点击上传</em></div>
      </el-upload>

      <el-table :data="appendFileRows" v-if="appendFileRows.length" size="small" class="my-4">
        <el-table-column prop="filename" label="文件名" />
        <el-table-column prop="size" label="大小(KB)" width="120" />
        <el-table-column prop="type" label="文件类型" width="120" />
        <el-table-column label="切割策略" width="200">
          <template #default="{ row }">
            <el-select v-model="row.strategy" placeholder="选择策略" size="small">
              <el-option v-for="(val, label) in ALL_STRATEGY" :key="label" :label="label" :value="label" />
            </el-select>
          </template>
        </el-table-column>
      </el-table>

      <template #footer>
        <el-button @click="appendDialogVisible = false" round>取消</el-button>
        <el-button type="primary" @click="submitAppend" round>追加</el-button>
      </template>
    </el-dialog>

    <!-- 删除 KB Dialog -->
    <el-dialog v-model="deleteDialogVisible" title="删除知识库" width="400px">
      <span>确认删除选中的知识库？此操作无法撤销！</span>
      <template #footer>
        <el-button @click="deleteDialogVisible = false" round>取消</el-button>
        <el-button type="danger" @click="submitDeleteKB" round>确认删除</el-button>
      </template>
    </el-dialog>

    <!-- 删除文档 Dialog -->
    <el-dialog v-model="deleteDocDialogVisible" title="删除文档" width="400px">
      <span>确认删除选中的文档？此操作将无法撤销！</span>
      <template #footer>
        <el-button @click="deleteDocDialogVisible = false" round>取消</el-button>
        <el-button type="danger" @click="submitDeleteDoc" round>确认删除</el-button>
      </template>
    </el-dialog>

    <!-- 查看文档切割段落 Dialog -->
    <el-dialog v-model="showParDialogVisible" width="80%">
      <template #header="{ titleId }">
        <el-text :id="titleId"> 文档：{{ selectedDoc.document_name }}</el-text>
        <el-tag type="info">{{ parTableData.length }}个段落</el-tag>
      </template>

      <el-table :data="parTableData" border class="my-4" height="680">
        <el-table-column prop="paragraph_id" label="段落id" width="120" />
        <el-table-column prop="paragraph_name" label="段落名" width="120" />
        <el-table-column prop="summary" label="段落摘要" />
        <el-table-column prop="content" label="段落内容" />
        <el-table-column prop="position" label="段落位置" width="90" />
      </el-table>
    </el-dialog>

    <!-- 重构建索引 Dialog -->
    <el-dialog v-model="updateIndexDialogVisible" title="重构建索引" width="400px">
      <span>确认重新构建当前知识库所有文档的索引？此操作将需要一定时间后台运行</span>
      <template #footer>
        <el-button @click="updateIndexDialogVisible = false" round>取消</el-button>
        <el-button type="danger" @click="submitUpdateIndex" round>重构建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import { ref, reactive, computed, inject } from 'vue'

const api = inject('$api')

/* 常量 */
const ALL_STRATEGY = {
  '按页切割': 'page_split',
  '按目录切割': 'catalog_split',
  '智能上下文切割': 'automate_judgment_split',
  '智能语义分块切割': 'agentic_chunking'
}
const headerHeight = ref('680')
/* 全局状态 */
const activeTab = ref('kb')
const kbTableData = ref([])
const parTableData = ref([])
const fileTableData = ref([])
const selectedKB = ref(null)
const selectedDoc = ref(null)

/* recall */
const query = ref('')
const selectedKBOption = ref('')
const recallTableData = ref([])

/* dialogs */
const createDialogVisible = ref(false)
const appendDialogVisible = ref(false)
const deleteDialogVisible = ref(false)
const deleteDocDialogVisible = ref(false)
const showParDialogVisible = ref(false)
const updateIndexDialogVisible = ref(false)

/* loading */
const fullscreenLoading = ref(false)

/*  创建 KB 表单 */
const createForm = reactive({ name: '', desc: '' })
const createFileList = ref([]) // el-upload list 格式
const createFileRows = ref([]) // [{file,filename,size,type,strategy}]

/*  追加文件 */
const appendFileList = ref([])
const appendFileRows = ref([])

/* 计算属性 */
const kbOptions = computed(() =>
  kbTableData.value.map(k => ({
    label: `${k.kb_id}:${k.kb_name}`,
    value: `${k.kb_id}:${k.kb_name}`
  }))
)

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

async function fetchParagraphs(documentId) {
  const { data } = await api.get(`paragraphs/${documentId}`)
  parTableData.value = data
}

/* 事件处理 */
function handleKBRowClick(row) {
  selectedKB.value = row
  selectedKBOption.value = `${row.kb_id}:${row.kb_name}`
  fetchDocuments(row.kb_id)
}

function handleDocRowClick(index, row) {
  selectedDoc.value = row
  showParDialogVisible.value = true
  fetchParagraphs(row.document_id)
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

function openUpdateIndexDialog() {
  updateIndexDialogVisible.value = true
}

function openDeleteKBDialog() {
  deleteDialogVisible.value = true
}

function openDeleteDocDialog(index, row) {
  selectedDoc.value = row
  deleteDocDialogVisible.value = true;
}

/*  上传 change  */
function fileInfoFromRawFile(raw) {
  return {
    file: raw,
    filename: raw.name,
    size: (raw.size / 1024).toFixed(2),
    type: raw.name.split('.').pop(),
    strategy: '智能上下文切割'
  }
}

/*  创建知识库时删除文件  */
function handleCreateRemove(file, fileList) {
  handleCreateUpload(file, fileList)
}

/*  创建知识库时文件发生变更  */
function handleCreateUpload(file, fileList) {
  createFileRows.value = fileList.map(f => fileInfoFromRawFile(f.raw))
  createFileList.value = fileList

  let strategies = {}
  if (createFileRows.value.length > 0) {
    createFileRows.value.forEach(item => strategies[item.file.uid] = item.strategy)
  }

  createFileRows.value = fileList.map(f => fileInfoFromRawFile(f.raw))
  createFileList.value = fileList

  if (Reflect.ownKeys(strategies).length > 0) {
    createFileRows.value.forEach(f => {
      if (f.file.uid in strategies) {
        f.strategy = strategies[f.file.uid]
      }
    })
  }
}

/*  追加文件时删除文件  */
function handleAppendRemove(file, fileList) {
  handleAppendUpload(file, fileList)
}

/*  追加文件时文件发生变更  */
function handleAppendUpload(file, fileList) {
  let strategies = {}
  if (appendFileList.value.length > 0) {
    appendFileRows.value.forEach(item => strategies[item.file.uid] = item.strategy)
  }

  appendFileRows.value = fileList.map(f => fileInfoFromRawFile(f.raw))
  appendFileList.value = fileList

  if (Reflect.ownKeys(strategies).length > 0) {
    appendFileRows.value.forEach(f => {
      if (f.file.uid in strategies) {
        f.strategy = strategies[f.file.uid]
      }
    })
  }
}

/*  创建 KB & 提交文件  */
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

  // 创建 KB
  const { data: newKB } = await api.post('knowledge_bases', {
    kb_name: createForm.name,
    kb_description: createForm.desc,
    keywords: ''
  })
  // 增加上传文件
  const formData = new FormData()
  createFileRows.value.forEach(row => {
    formData.append('files', row.file)
  })
  // 组装 items
  const items = createFileRows.value.map(row => ({
    kb_id: newKB.kb_id,
    policy_type: ALL_STRATEGY[row.strategy]
  }))
  formData.append('items', JSON.stringify(items))
  api.post('upload', formData)

  ElMessage.success(`知识库『${createForm.name}』创建成功，共 ${createFileRows.value.length} 个文件后台解析中`)
  createDialogVisible.value = false
  await fetchKnowledgeBases()
  activeTab.value = kb
}

/*  追加文件  */
async function submitAppend() {
  if (!appendFileRows.value.length) {
    ElMessage.warning('请选择至少一个文件')
    return
  }
  if (!selectedKB.value) return

  const formData = new FormData()

  // 增加上传文件
  appendFileRows.value.forEach(row => {
    formData.append('files', row.file)
  })

  // 组装 items
  const items = appendFileRows.value.map(row => ({
    kb_id: selectedKB.value.kb_id,
    policy_type: ALL_STRATEGY[row.strategy]
  }))
  formData.append('items', JSON.stringify(items))
  api.post('upload', formData)

  ElMessage.success(`成功追加 ${appendFileRows.value.length} 个文件`)
  appendDialogVisible.value = false
  await fetchDocuments(selectedKB.value.kb_id)
}

/*  删除 KB  */
async function submitDeleteKB() {
  if (!selectedKB.value) return
  await api.delete(`knowledge_base/${selectedKB.value.kb_id}`)
  ElMessage.success('知识库删除成功')
  deleteDialogVisible.value = false
  selectedKB.value = null
  fileTableData.value = []
  await fetchKnowledgeBases()
}

/*  删除 文档  */
async function submitDeleteDoc() {
  if (!selectedDoc.value) return

  await api.delete(`document/${selectedDoc.value.document_id}`)
  ElMessage.success('文档删除成功')
  deleteDocDialogVisible.value = false
  selectedDoc.value = null
  fetchDocuments(selectedKB.value.kb_id)
}

/*  重构建 索引 */
async function submitUpdateIndex() {
  api.patch(`index/${selectedKB.value.kb_id}`)
  ElMessage.success('重构建成功')
  updateIndexDialogVisible.value = false
  await fetchKnowledgeBases()
}


/*  召回测试  */
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
  fullscreenLoading.value = true
  const { data } = await api.get('recall', {
    params: {
      kb_id,
      question: query.value
    }
  })
  fullscreenLoading.value = false
  recallTableData.value = data.map(par => ({
    paragraph_id: par.paragraph_id,
    summary: par.summary,
    content: par.content,
    parent_description: par.parent_description,
    context_relevance: par.context_relevance,
    context_sufficiency: par.context_sufficiency,
    context_clarity: par.context_clarity,
    total_score: par.total_score,
    diagnosis: par.diagnosis
  }))
}

function resetRecall() {
  query.value = ''
  selectedKBOption.value = ''
  recallTableData.value = []
}

/* 初始化 */
fetchKnowledgeBases()
</script>

<style scoped>
.lib-rag-app {
  max-width: 1850px;
  margin: 0 auto;
}

.knowledge-container {
  height: auto;
  /* background: #f5f7fa; */
}

.left-panel {
  padding: 0px;
  background: #fcfcfc;
}

.right-panel {
  padding: 0px;
  background: #fcfcfc;
  margin-left: 15px;
}

.sub-title {
  font-size: 20px;
}

/* 卡片样式 */
.kb-card.selected {
  border: 2px solid var(--el-color-primary);
}

.kb-desc {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

:deep .el-step.is-simple .el-step__head {
  font-size: 0;
  padding-right: 10px;
  width: auto;
  margin-top: 10px;
}

.el-step__title {
  font-size: 13px;
  line-height: 38px;
}
</style>