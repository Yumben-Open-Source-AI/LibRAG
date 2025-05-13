<template>
  <div class="lib-rag-app p-4 space-y-6">

    <el-header>
      <el-row>
        <el-col :span="22">
          <el-text class="mx-1" type="primary" size="large"
            style="display: flex; justify-content: center; font-size: 30px;">LibRAG
          </el-text>
        </el-col>
        <el-col :span="2">
          <el-button type="primary" @click="openCreateDialog" size="large">创建知识库</el-button>
        </el-col>
      </el-row>
    </el-header>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="知识库管理" name="kb">
        <el-container class="knowledge-container">
          <el-aside width="30%" class="left-panel">
            <el-card shadow="hover">
              <template #header>
                <div class="card-header">
                  <span>知识库列表</span>
                  <!-- <el-button type="primary" icon="el-icon-plus" circle size="mini" /> -->
                </div>
              </template>
              <el-table :data="kbTableData" border highlight-current-row @row-click="handleKBRowClick">
                <el-table-column prop="kb_id" label="知识库id" />
                <el-table-column prop="kb_name" label="知识库名称" />
                <el-table-column prop="kb_description" label="知识库描述" width="180" />
                <el-table-column fixed="right" label="操作">
                  <template #default>
                    <div>
                      <el-button @click="openAppendDialog" :disabled="!selectedKB" type="primary">追加新文件</el-button>
                    </div>
                    <div style="margin-top: 5px;">
                      <el-button @click="openUpdateIndexDialog" :disabled="!selectedKB" type="success">重构建索引
                      </el-button>
                    </div>
                    <div style="margin-top: 5px;">
                      <el-button type="danger" @click.stop="openDeleteKBDialog" :disabled="!selectedKB">删除知识库
                      </el-button>
                    </div>
                  </template>
                </el-table-column>
              </el-table>
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
              <el-table v-if="selectedKB" border :data="fileTableData" class="mt-6" height="600">
                <el-table-column prop="document_id" label="文档id" width="100"/>
                <el-table-column prop="文档名称" label="文档名称" width="250" />
                <el-table-column prop="切割策略" label="切割策略" width="100" />
                <el-table-column prop="文档描述" label="文档描述" />
                <el-table-column prop="meta_data.最后更新时间" label="最后更新时间" width="100" />
                <el-table-column fixed="right" label="操作" width="110">
                  <template #default="scope">
                    <div>
                      <el-button type="info" @click="handleDocRowClick(scope.$index, scope.row)">查看段落</el-button>
                    </div>
                    <div style="margin-top: 5px;">
                      <el-button type="danger" @click="openDeleteDocDialog(scope.$index, scope.row)">删除文档
                      </el-button>
                    </div>
                  </template>
                </el-table-column>
              </el-table>
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
              <el-button type="primary" @click="doRecall" v-loading.fullscreen.lock="fullscreenLoading">测试召回
              </el-button>
              <el-button @click="resetRecall">重置查询</el-button>
            </el-col>
          </el-row>


        </div>

        <el-table :data="recallTableData" border height="650">
          <el-table-column prop="paragraph_id" label="段落ID" width="150" />
          <el-table-column prop="summary" label="段落摘要" />
          <el-table-column prop="content" label="段落内容" />
          <el-table-column prop="parent_description" label="来源描述" />
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 创建 KB & 提交文件 Dialog -->
    <el-dialog v-model="createDialogVisible" title="创建新知识库 & 提交文件" width="30%">
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
          <el-upload multiple :auto-upload="false" :file-list="createFileList" :on-change="handleCreateUpload" drag
            style="width: 100%;">
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
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 追加文件 Dialog -->
    <el-dialog v-model="appendDialogVisible" title="追加新文件" width="800px">
      <el-upload multiple :auto-upload="false" :file-list="appendFileList" :on-change="handleAppendUpload" drag>
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
        <el-button @click="appendDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAppend">追加</el-button>
      </template>
    </el-dialog>

    <!-- 删除 KB Dialog -->
    <el-dialog v-model="deleteDialogVisible" title="删除知识库" width="400px">
      <span>确认删除选中的知识库？此操作无法撤销！</span>
      <template #footer>
        <el-button @click="deleteDialogVisible = false">取消</el-button>
        <el-button type="danger" @click="submitDeleteKB">构建</el-button>
      </template>
    </el-dialog>

    <!-- 删除文档 Dialog -->
    <el-dialog v-model="deleteDocDialogVisible" title="删除文档" width="400px">
      <span>确认删除选中的文档？此操作将无法撤销！</span>
      <template #footer>
        <el-button @click="deleteDocDialogVisible = false">取消</el-button>
        <el-button type="danger" @click="submitDeleteDoc">删除</el-button>
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
        <el-table-column prop="position" label="段落位置" width="80" />
      </el-table>
    </el-dialog>

    <!-- 重构建索引 Dialog -->
    <el-dialog v-model="updateIndexDialogVisible" title="重构建索引" width="400px">
      <span>确认重新构建当前知识库所有文档的索引？此操作将需要一定时间后台运行</span>
      <template #footer>
        <el-button @click="updateIndexDialogVisible = false">取消</el-button>
        <el-button type="danger" @click="submitUpdateIndex">重构建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, inject } from 'vue'
import { ElMessage } from 'element-plus'

const api = inject('$api')

/* 常量 */
const ALL_STRATEGY = {
  '按页切割': 'page_split',
  '按目录切割': 'catalog_split',
  '智能上下文切割': 'automate_judgment_split',
  '智能语义分块切割': 'agentic_chunking'
}

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

function handleCreateUpload(file, fileList) {
  createFileRows.value = fileList.map(f => fileInfoFromRawFile(f.raw))
  createFileList.value = fileList
}

function handleAppendUpload(file, fileList) {
  appendFileRows.value = fileList.map(f => fileInfoFromRawFile(f.raw))
  appendFileList.value = fileList
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
  await api.post('upload', formData)

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
  await api.post('upload', formData)

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
    parent_description: par.parent_description
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
  max-width: 1700px;
  margin: 0 auto;
}

.knowledge-container {
  height: auto;
  /* background: #f5f7fa; */
}

.left-panel {
  padding: 16px;
  background: #f5f7fa;
}

.right-panel {
  padding: 16px;
  background: #fff1f1;
  margin-left: 5px;
}

.sub-title {
  font-size: 20px;
}
</style>