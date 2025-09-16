<template>
  <div class="lib-rag-app p-4 space-y-6">

    <el-header>
      <el-row>
        <el-col :span="24">
          <el-text class="mx-1" type="primary" size="large"
            style="display: flex; justify-content: center; font-size: 25px; padding-top: 20px;">LibRAG</el-text>
        </el-col>
      </el-row>
    </el-header>

    <el-tabs v-model="activeTab" class="custom-tabs">
      <el-tab-pane label="知识库管理" name="kb">
        <el-container class="knowledge-container" style="display: flex; align-items: stretch;">
          <!-- ---------------- 左侧：知识库列表 ---------------- -->
          <el-aside width="25%" class="left-panel" style="display: flex; flex-direction: column;">
            <el-card shadow="hover" class="custom-card" style="flex: 1;">
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

          <el-main class="right-panel" style="display: flex; flex-direction: column;">
            <el-card shadow="hover" class="custom-card" style="flex: 1;">
              <template #header>
                <div class="card-header">
                  <div v-if="selectedKB" class="sub-title">
                    知识库：{{ selectedKB.kb_name }}
                    <el-tag type="info">{{ documerntTotal }}篇文档</el-tag>

                    <div style="float: right; display: flex; gap: 8px; align-items: center;">
                      <el-input v-model="docFilterText" placeholder="筛选文档名称" style="width: 300px;" clearable />
                      <el-button type="info" @click="resetDocFilter">
                        重置
                      </el-button>

                      <el-button type="primary" @click="filteredFileTableData">
                        筛选
                      </el-button>
                    </div>
                  </div>
                </div>
              </template>

              <el-scrollbar v-if="selectedKB" :height=headerHeight class="doc-scroll">
                <el-card v-for="doc in fileTableData" :key="doc.document_id" class="mb-4" shadow="always">
                  <div v-if="doc.task">
                    <el-descriptions :column="3" size="small" border>
                      <template #title>
                        <el-text @click="handleFilePreview(doc.task.file_path)" class="mx-1" type="primary"
                          style="text-decoration: underline;">{{
                            '正在处理的文档: ' + doc.task.file_path }}</el-text>
                      </template>
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
                    <el-descriptions :column="3" size="small" border>
                      <template #title>
                        <el-text @click="handleFilePreview(doc['文件名'])" class="mx-1" type="primary"
                          style="text-decoration: underline;">{{ doc['文件名'] }}</el-text>
                      </template>
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

              <el-pagination v-if="selectedKB" style="float: right; margin-bottom: 5px;margin-top: 5px;"
                v-model:current-page="currentDocumentPage" v-model:page-size="documentPageSize"
                :page-sizes="[10, 20, 50, 100]" :background="true" :pager-count="5"
                layout="sizes, prev, pager, next, jumper" :total="documerntTotal" @size-change="handleSizeChange"
                @current-change="handleCurrentChange" />
            </el-card>
          </el-main>
        </el-container>
      </el-tab-pane>

      <el-tab-pane label="召回测试" name="recall">
        <div class="flex flex-wrap items-center gap-2 mb-4">
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="请输入查询：">
                <el-input type="textarea" v-model="query" placeholder="请输入查询，建议陈述性语句" :rows="1" class="flex-1"
                  @keydown.enter="handlerKeyDown($event)" />
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
              <el-switch v-model="has_score" active-text="开启打分" inactive-text="关闭打分" @change="handlerSwitch"
                inactive-color="#F04134"></el-switch>
            </el-col>
            <el-col :span="4">
              <el-button type="primary" @click="doRecall" v-loading.fullscreen.lock="fullscreenLoading" round>测试召回
              </el-button>
              <el-button type="info"  @click="aiAnswers" round>答案预览</el-button>
              <el-button @click="resetRecall" round>重置查询</el-button>
            </el-col>
          </el-row>
        </div>

        <el-table :data="recallTableData" border height="650" class="custom-table">
          <el-table-column prop="paragraph_id" label="段落ID" width="150" />
          <el-table-column prop="summary" label="段落摘要" />
          <el-table-column label="段落内容">
            <template #default="{ row }">
              <el-input v-model="row.content" style="width: 100%" :rows="18" type="textarea" />
            </template>
          </el-table-column>
          <el-table-column label="段落原文" v-if="parTableData.some(row => row.source_text)">
            <template #default="{ row }">
              <el-input v-model="row.source_text" style="width: 100%" :rows="18" type="textarea" />
            </template>
          </el-table-column>
          <el-table-column prop="parent_description" label="来源描述" />
          <el-table-column prop="document_name" label="来源文档" />
          <el-table-column prop="context_relevance" align="center" width="100" label="语境相关性" v-if="has_score" />
          <el-table-column prop="context_sufficiency" align="center" width="120" label="上下文充分性" v-if="has_score" />
          <el-table-column prop="context_clarity" align="center" width="100" label="语境清晰性" v-if="has_score" />
          <el-table-column prop="reliability" align="center" width="100" label="可信度" v-if="has_score" />
          <el-table-column prop="total_score" align="center" width="100" label="汇总得分" v-if="has_score" />
          <el-table-column prop="diagnosis" width="100" label="诊断信息" v-if="has_score" />
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 创建 KB & 提交文件 Dialog -->
    <el-dialog v-model="createDialogVisible" title="创建新知识库 & 提交文件" width="50%">
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
            :on-remove="handleCreateRemove" drag style="width: 100%;" :show-file-list="false">
            <i class="el-icon-upload" />
            <div class="el-upload__text">拖拽文件到此或 <em>点击上传</em></div>
          </el-upload>
        </el-form-item>
      </el-form>

      <el-table :data="currentCreateFileRows" border v-if="createFileRows.length" size="small">
        <el-table-column prop="filename" label="文件名" />
        <el-table-column prop="size" label="大小(KB)" width="80" />
        <el-table-column prop="type" label="文件类型" width="80" />
        <el-table-column label="切割策略" width="150">
          <template #default="{ row }">
            <el-select v-model="row.strategy" placeholder="选择策略" size="small">
              <el-option v-for="(val, label) in ALL_STRATEGY" :key="label" :label="label" :value="label" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button type="danger" size="small" text-color="#ff4d4f" @click="handleCreateRemoveFile(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <template #footer>
        <el-pagination style="float: left" v-model:current-page="createDocumentPage" :page-size="10" :background="true"
          :pager-count="5" layout="total, prev, pager, next, jumper" :total="createFileRows.length"
          @current-change="createCurrentChange" />
        <el-button @click="createDialogVisible = false" round>取消</el-button>
        <el-button type="primary" @click="submitCreate" round>创建</el-button>
      </template>
    </el-dialog>

    <!-- 追加文件 Dialog -->
    <el-dialog v-model="appendDialogVisible" title="追加新文件" width="800px">
      <!-- 上传区域 -->
      <el-upload multiple :auto-upload="false" :file-list="appendFileList" :on-change="handleAppendUpload"
        :on-remove="handleAppendRemove" drag style="margin-bottom: 20px;" :show-file-list="false">
        <i class="el-icon-upload" />
        <div class="el-upload__text">拖拽文件到此或 <em>点击上传</em></div>
      </el-upload>

      <el-table :data="currentAppendFileRows" v-if="currentAppendFileRows.length" size="small" border>
        <el-table-column prop="filename" label="文件名" />
        <el-table-column prop="size" label="大小(KB)" width="80" />
        <el-table-column prop="type" label="文件类型" width="80" />
        <el-table-column label="切割策略" width="150">
          <template #default="{ row }">
            <el-select v-model="row.strategy" placeholder="选择策略" size="small">
              <el-option v-for="(val, label) in ALL_STRATEGY" :key="label" :label="label" :value="label" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button type="danger" size="small" text-color="#ff4d4f" @click="handleRemoveFile(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-pagination style="float: left" v-model:current-page="appendDocumentPage" :page-size="10" :background="true"
          :pager-count="5" layout="total, prev, pager, next, jumper" :total="appendFileRows.length"
          @current-change="appendCurrentChange" />
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
        <el-table-column label="段落内容">
          <template #default="{ row }">
            <el-input v-model="row.content" style="width: 100%" :rows="10" type="textarea" placeholder="Please input" />
          </template>
        </el-table-column>
        <el-table-column label="段落原文" v-if="parTableData.some(row => row.source_text)">
          <template #default="{ row }">
            <el-input v-model="row.source_text" style="width: 100%" :rows="10" type="textarea" v-if="row.source_text"
              placeholder="Please input" />
          </template>
        </el-table-column>
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

    <!-- 文件预览 Dialog -->
    <el-dialog v-model="previewDialogVisible" style="bottom: 0; left: 0; overflow: auto; position: fixed; right: 0;">
      <template #header>
        文件预览
        <el-button @click="handleImagePreview" round v-if="previewFileType === 'image'">点击图片或按钮放大图片</el-button>
      </template>

      <div class="docx-preview-container" v-if="previewFileType === 'docx'">
        <div>
          <vue-office-docx :src="previewFileUrl" class="a4-docx" @rendered="renderedHandler" @error="errorHandler" />
        </div>

        <div v-if="previewFileType === 'unknown'">
          <el-alert title="不支持的文件类型" message="当前文件类型不支持在线预览" type="warning" show-icon />
        </div>
      </div>
      <div class="orther-preview-container" v-else>
        <div v-if="previewFileType === 'pdf'" class="pdf-container">
          <vue-office-pdf :style="{ height: `100% !important` }" :src="previewFileUrl" @rendered="renderedHandler"
            @error="errorHandler" />
        </div>
        <div v-else-if="previewFileType === 'image'">
          <el-image style="width: 100%;" :src="previewFileUrl" class="a4-image" ref="imageRef"
            :preview-src-list="[previewFileUrl]" show-progress fit="contain" @close="showPreview = false" />
        </div>

        <div v-if="previewFileType === 'unknown'">
          <el-alert title="不支持的文件类型" message="当前文件类型不支持在线预览" type="warning" show-icon />
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import {ElMessage, ElMessageBox} from 'element-plus'
import { ref, reactive, computed, inject, onUnmounted } from 'vue'
import { ElImage, ElImageViewer } from 'element-plus'
import VueOfficeDocx from '@vue-office/docx'
import VueOfficePdf from '@vue-office/pdf'


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
const has_score = ref(true)

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
const createFileList = ref([]);
const createFileRows = ref([]);
const currentCreateFileRows = ref([]);
const createDocumentPage = ref(1);

/*  追加文件 */
const appendFileList = ref([])
const appendFileRows = ref([])
const currentAppendFileRows = ref([]);
const appendDocumentPage = ref(1)

/* 分页 */
const documentPageSize = ref(10)
const currentDocumentPage = ref(1)
const documerntTotal = ref(100)

/* 文档筛选相关 */
const docFilterText = ref('') // 文档名筛选

/* 定时器 */
const intervalId = ref(null);

/* 文件预览 */
const previewDialogVisible = ref(false)
const previewFileUrl = ref('')
const previewFileType = ref('')
const imageRef = ref(null)
const showPreview = ref(false)
const filePreviewBaseUrl = `${import.meta.env.VITE_APP_API_URL}files/`

// 处理回车事件
function handlerKeyDown(event) {
  if (event.keyCode == 13) {
    event.preventDefault();
    doRecall();
  }
}

async function filteredFileTableData() {
  const { data } = await api.get('filter_documents', {
    params: {
      kb_id: selectedKB.value.kb_id,
      document_name: docFilterText.value,
      page: 1,
      size: documentPageSize.value
    }
  })
  documerntTotal.value = data.total;

  fileTableData.value = data.items.map(d => ({
    ...d,
    文件名: d.file_path ? d.file_path.split("/").pop() || '' : '',
    文档名称: d.document_name,
    文档描述: d.document_description,
    切割策略: d.parse_strategy || ''
  }))
}

// 重置筛选条件
async function resetDocFilter() {
  docFilterText.value = '';
  await fetchDocuments(selectedKB.value.kb_id);
}

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
  const { data } = await api.get(`knowledge_base/${kbId}`, {
    params: {
      page: currentDocumentPage.value,
      size: documentPageSize.value
    }
  })

  documerntTotal.value = data.total;

  fileTableData.value = data.items.map(d => ({
    ...d,
    文件名: d.file_path ? d.file_path.split("/").pop() || '' : '',
    文档名称: d.document_name,
    文档描述: d.document_description,
    切割策略: d.parse_strategy || ''
  }))
}

async function checkDocuments() {
  const processTask = fileTableData.value.filter(
    document => document.task && document.task.status === 'processing'
  );

  if (processTask.length > 0) {
    // 存在处理中的任务时
    intervalId.value = setInterval(() => {
      // 定时刷新文档状态
      fetchDocuments(selectedKB.value.kb_id);
    }, 3000); // 3秒刷新一次
  }
}


async function fetchParagraphs(documentId) {
  const { data } = await api.get(`paragraphs/${documentId}`)
  parTableData.value = data
}

/* 事件处理 */
async function handleKBRowClick(row) {
  if (intervalId.value) {
    clearInterval(intervalId.value);
    intervalId.value = null;
  }

  selectedKB.value = row
  selectedKBOption.value = `${row.kb_id}:${row.kb_name}`
  await fetchDocuments(selectedKB.value.kb_id)
  checkDocuments()
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
  appendDialogVisible.value = true;
  appendFileList.value = [];
  appendFileRows.value = [];
  currentAppendFileRows.value = [];
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
    strategy: '按页切割'
  }
}

/*  创建知识库时删除文件  */
function handleCreateRemove(file, fileList) {
  handleCreateUpload(file, fileList)
}

/*  创建知识库时文件发生变更  */
function handleCreateUpload(file, fileList) {
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

  // 重新计算当前页数据
  createCurrentChange(createDocumentPage.value);
}

function createCurrentChange(val) {
  createDocumentPage.value = val;
  // 起始索引
  const startIndex = (val - 1) * 10;
  // 结束索引
  const endIndex = startIndex + 10;
  // 截取对应范围数据
  currentCreateFileRows.value = createFileRows.value.slice(startIndex, endIndex);
}

function handleCreateRemoveFile(row) {
  // 找到文件在列表中的索引
  const index = createFileRows.value.findIndex(item => item.file.uid === row.file.uid);

  if (index !== -1) {
    // 从数据列表中移除
    createFileRows.value.splice(index, 1);
    // 同步更新上传组件的文件列表
    createFileList.value.splice(index, 1);
    createCurrentChange(createDocumentPage.value);
  }
}

async function handleSizeChange(val) {
  documentPageSize.value = val
  await fetchDocuments(selectedKB.value.kb_id)
}

async function handleCurrentChange(val) {
  currentDocumentPage.value = val
  await fetchDocuments(selectedKB.value.kb_id)
}

function appendCurrentChange(val) {
  appendDocumentPage.value = val;
  // 起始索引
  const startIndex = (val - 1) * 10;
  // 结束索引
  const endIndex = startIndex + 10;
  // 截取对应范围数据
  currentAppendFileRows.value = appendFileRows.value.slice(startIndex, endIndex);
}

/*  追加文件时删除文件  */
function handleAppendRemove(file, fileList) {
  handleAppendUpload(file, fileList)
}

function handleRemoveFile(row) {
  // 找到文件在列表中的索引
  const index = appendFileRows.value.findIndex(item => item.file.uid === row.file.uid);

  if (index !== -1) {
    // 从数据列表中移除
    appendFileRows.value.splice(index, 1);
    // 同步更新上传组件的文件列表
    appendFileList.value.splice(index, 1);
    appendCurrentChange(appendDocumentPage.value);
  }
}

/*  追加文件时文件发生变更  */
function handleAppendUpload(file, fileList) {
  let strategies = {};
  if (appendFileList.value.length > 0) {
    appendFileRows.value.forEach(item => strategies[item.file.uid] = item.strategy);
  }

  appendFileRows.value = fileList.map(f => fileInfoFromRawFile(f.raw));
  appendFileList.value = fileList;

  if (Reflect.ownKeys(strategies).length > 0) {
    appendFileRows.value.forEach(f => {
      if (f.file.uid in strategies) {
        f.strategy = strategies[f.file.uid];
      }
    });
  }

  // 重新计算当前页数据
  appendCurrentChange(appendDocumentPage.value);
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
  const { data } = await api.post('upload', formData)

  ElMessage.success(`知识库『${createForm.name}』创建成功，${data.message}`)
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
  const { data } = await api.post('upload', formData)

  ElMessage.success(`${data.message}`)
  appendDialogVisible.value = false
  await fetchDocuments(selectedKB.value.kb_id)
  checkDocuments()
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

async function aiAnswers() {
  if (!query.value.trim()) {
    ElMessage.warning('请输入查询内容')
    return
  }
  if (!selectedKBOption.value) {
    ElMessage.warning('请选择知识库')
    return
  }
  if (recallTableData.value.length === 0) {
    ElMessage.warning('请先执行召回测试获取相关段落')
    return
  }

  fullscreenLoading.value = true
  try {
    // 保持传递数组格式
    const formData = new FormData()
    formData.append('question', query.value)
    formData.append('context', JSON.stringify(recallTableData.value)) // 将数组转为JSON字符串
    formData.append('kb_id', selectedKBOption.value.split(':')[0])

    const { data } = await api.post('chat', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })

    // 显示AI回答
    ElMessageBox.alert(data.answer, 'AI回答', {
      confirmButtonText: '确定',
      customClass: 'ai-answer-message-box',
      dangerouslyUseHTMLString: true,
      showClose: false
    })

  } catch (error) {
    console.error('获取AI回答失败:', error)
    ElMessage.error('获取AI回答失败: ' + (error.response?.data?.message || error.message))
  } finally {
    fullscreenLoading.value = false
  }
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
      question: query.value,
      has_source_text: true,
      score_threshold: 0.0,
      has_score: has_score.value
    }
  })
  fullscreenLoading.value = false
  recallTableData.value = data.map(par => ({
    paragraph_id: par.paragraph_id,
    summary: par.summary,
    content: par.content,
    document_name: par.document_name,
    source_text: par.source_text,
    parent_description: par.parent_description,
    context_relevance: par.context_relevance,
    context_sufficiency: par.context_sufficiency,
    context_clarity: par.context_clarity,
    reliability: par.reliability,
    total_score: par.total_score,
    diagnosis: par.diagnosis
  }))
}

function resetRecall() {
  query.value = ''
  selectedKBOption.value = ''
  recallTableData.value = []
}

function handleImagePreview() {
  imageRef.value?.showPreview()
}

async function handleFilePreview(fileName) {
  if (!fileName) {
    ElMessage.warning('文件名称不存在')
    return
  }


  // 提取文件名
  let fileNameOnly = fileName.split('\\').pop()
  if (fileName.indexOf('/') != -1) {
    fileNameOnly = fileName.split('/').pop()
  }
  const fileType = fileNameOnly.toLowerCase().split('.').pop();

  if (fileType === 'doc') {
    previewFileType.value = 'docx'
    console.log(previewFileType.value);
  } else if (fileType === 'docx') {
    previewFileType.value = 'docx'
  } else if (fileType === 'pdf') {
    previewFileType.value = 'pdf'
  } else if (['jpg', 'jpeg', 'png', 'gif', 'bmp'].some(ext =>
    fileType === ext
  )) {
    previewFileType.value = 'image'
  } else {
    previewFileType.value = 'unknown'
  }

  // 设置文件URL
  previewFileUrl.value = `${filePreviewBaseUrl}${fileNameOnly}`
  previewDialogVisible.value = true
}

// 预览相关回调
function renderedHandler() {
  console.log("文件渲染完成")
}

function errorHandler(error) {
  console.error("文件预览错误:", error)
  ElMessage.error('文件预览失败')
}

onUnmounted(() => {
  // 组件销毁时同步检查定时器
  if (intervalId.value) {
    clearInterval(intervalId.value);
    intervalId.value = null;
  }
})

/* 初始化 */
fetchKnowledgeBases()
</script>

<style scoped>
.lib-rag-app {
  max-width: 1850px;
  margin: 0 auto;
  padding: 0px;
}

.knowledge-container {
  height: auto;
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

/* 全局样式 */
.custom-tabs {
  border-radius: 8px;
  overflow: hidden;
}

/* 卡片样式 */
.custom-card {
  border-radius: 8px !important;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1) !important;
}

/* 表格样式 */
.custom-table {
  border-radius: 8px !important;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1) !important;
}

.custom-table th {
  border-radius: 8px 8px 0 0 !important;
}

.kb-card {
  transition: all 0.3s ease;
}

.kb-card:hover {
  transform: translateY(-3px);
}

.docx-preview-container {
  width: 100%;
  height: calc(100vh - 160px);
  overflow: auto;
  padding: 0;
  margin: 0;
  display: flex;
  justify-content: center;
}

.orther-preview-container {
  width: 100%;
  height: calc(100vh - 160px);
  overflow: hidden;
  padding: 10px 0;
  margin: 0;
  display: flex;
  justify-content: center;
}

.a4-docx {
  height: 100%;
  box-shadow: 0 0 8px rgba(0, 0, 0, 0.1);
  background: gray;
  transform: scale(0.9);
  transform-origin: top center;
  margin: 0 auto;
}

.a4-image {
  height: 100%;
  box-shadow: 0 0 8px rgba(0, 0, 0, 0.1);
  background: gray;
  transform-origin: top center;
  margin: 0 auto;
}

.pdf-container {
  width: 90%;
  height: 100%;
  box-shadow: 0 0 8px rgba(0, 0, 0, 0.1);
  background: #fff;
  margin: 0 auto;
  overflow: auto;
  transform-origin: top center;
}

.pdf-container canvas {
  width: 100% !important;
  height: auto !important;
}

.ai-answer-message-box {
  width: 80%;
  max-width: 800px;
}

.ai-answer-message-box .el-message-box__content {
  white-space: pre-wrap;
  line-height: 1.6;
  max-height: 70vh;
  overflow-y: auto;
  padding: 20px;
}
:deep(.el-dialog__body) {
  padding: 0 !important;
  margin: 0;
}

:deep(.el-dialog__header) {
  padding: 16px 20px;
  border-bottom: 1px solid #eee;
}
</style>