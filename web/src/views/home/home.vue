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
        <!-- 查询参数区域 -->
        <div class="flex flex-wrap items-center gap-2 mt-4">
          <el-row :gutter="20">
            <el-col :span="10">
              <el-form-item label="请输入查询：">
                <el-input type="textarea" v-model="query" placeholder="请输入查询，建议陈述性语句" :rows="1" class="flex-1"
                  @keydown.enter="handlerKeyDown($event)" />
              </el-form-item>
            </el-col>
            <el-col :span="4">
              <el-form-item label="知识库：">
                <el-select v-model="selectedKBOption" placeholder="选择知识库" style="width:100%">
                  <el-option v-for="opt in kbOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="4">
              <el-switch v-model="has_score" active-text="开启打分" inactive-text="关闭打分" @change="handlerSwitch"
                inactive-color="#F04134" />
            </el-col>
            <el-col :span="5">
              <el-button type="primary" @click="doRecall" :loading="recallButtonLoading" round
                :disabled="!!eventSource?.value">
                开始召回
              </el-button>
              <el-button type="info" @click="aiAnswers" round :disabled="!recallTableData.length">
                答案预览
              </el-button>
              <el-button @click="resetRecall" round>重置查询</el-button>
            </el-col>
          </el-row>
        </div>

        <!-- 水平展示的三层结果 -->
        <div class="stages-horizontal-container mb-6">
          <el-collapse v-model="activeStages" class="stages-collapse-container" @change="handleCollapseChange">
            <!-- 领域筛选 -->
            <el-collapse-item name="domain" :class="{ active: activeStages.includes('domain') }"
              class="stage-collapse-item">
              <template #title>
                <div class="card-header">
                  <span>领域筛选</span>
                  <el-tag v-if="stageResults.domain.data.length" type="primary" size="small" class="time-gap">
                    {{ stageResults.domain.data.length }} 个
                  </el-tag>
                  <el-tag v-if="stageResults.domain.data.length" type="primary" size="small" class="time-gap">
                    耗时: {{ stageResults.domain.elapsed_time }}秒
                  </el-tag>
                  <el-icon v-if="stageResults.domain.loading" class="is-loading">
                    <Loading />
                  </el-icon>
                </div>
              </template>
              <div class="stage-content">
                <el-skeleton v-if="stageResults.domain.loading" :rows="2" animated />
                <template v-else>
                  <div v-if="stageResults.domain.data.length" class="tag-group">
                    <el-tooltip v-for="domain in stageResults.domain.data" :key="domain.domain_id || domain"
                      :content="domain.domain_id ? `领域ID: ${domain.domain_id}` : ''" placement="top">
                      <el-tag type="primary" size="small" class="mb-1 hover:scale-105 transition-transform">
                        {{ domain.domain_name || domain }}
                      </el-tag>
                    </el-tooltip>
                  </div>
                  <el-empty v-else-if="activeStages.includes('domain')" :image-size="50" description="无匹配领域" />
                  <div v-else class="stage-tip">等待领域筛选...</div>
                </template>
              </div>
            </el-collapse-item>

            <!-- 分类筛选 -->
            <el-collapse-item name="category" :class="{ active: activeStages.includes('category') }"
              class="stage-collapse-item">
              <template #title>
                <div class="card-header">
                  <span>分类筛选</span>
                  <el-tag v-if="stageResults.category.data.length" type="success" size="small" class="time-gap">
                    {{ stageResults.category.data.length }} 个
                  </el-tag>
                  <el-tag v-if="stageResults.category.data.length" type="success" size="small" class="time-gap">耗时: {{
                    stageResults.category.elapsed_time }}秒
                  </el-tag>
                  <el-icon v-if="stageResults.category.loading" class="is-loading">
                    <Loading />
                  </el-icon>
                </div>
              </template>
              <div class="stage-content">
                <el-skeleton v-if="stageResults.category.loading" :rows="2" animated />
                <template v-else>
                  <div v-if="stageResults.category.data.length" class="tag-group">
                    <el-tooltip v-for="category in stageResults.category.data" :key="category.category_id || category"
                      :content="category.parent_name ? `所属领域: ${category.parent_name};分类ID: ${category.category_id}` : ''"
                      placement="top">
                      <el-tag type="success" size="small" class="mb-1 hover:scale-105 transition-transform">
                        {{ category.category_name }}
                      </el-tag>
                    </el-tooltip>
                  </div>
                  <el-empty v-else-if="activeStages.includes('category')" :image-size="50" description="无匹配分类" />
                  <div v-else class="stage-tip">等待分类筛选...</div>
                </template>
              </div>
            </el-collapse-item>

            <!-- 文档筛选 -->
            <el-collapse-item name="document" :class="{ active: activeStages.includes('document') }"
              class="stage-collapse-item">
              <template #title>
                <div class="card-header">
                  <span>文档筛选</span>
                  <el-tag v-if="stageResults.document.data.length" type="info" size="small" class="time-gap">
                    {{ stageResults.document.data.length }} 个
                  </el-tag>
                  <el-tag v-if="stageResults.document.data.length" type="info" size="small" class="time-gap">耗时: {{
                    stageResults.document.elapsed_time }}秒
                  </el-tag>
                  <el-icon v-if="stageResults.document.loading" class="is-loading">
                    <Loading />
                  </el-icon>
                </div>
              </template>
              <div class="stage-content">
                <el-skeleton v-if="stageResults.document.loading" :rows="2" animated />
                <template v-else>
                  <div v-if="stageResults.document.data.length" class="doc-card-group">
                    <el-tooltip v-for="doc in stageResults.document.data" :key="doc.document_id || doc"
                      :content="doc.parent_name ? `所属分类: ${doc.parent_name};文档ID: ${doc.document_id}` : ''"
                      placement="top">
                      <el-tag type="info" size="small" class="mb-1 hover:scale-105 transition-transform">
                        {{ doc.document_name }}
                      </el-tag>
                    </el-tooltip>
                  </div>
                  <el-empty v-else-if="activeStages.includes('document')" :image-size="50" description="无匹配文档" />
                  <div v-else class="stage-tip">等待文档筛选...</div>
                </template>
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>

        <!-- 段落召回结果 -->
        <el-card shadow="hover" class="paragraph-results-card">
          <template #header>
            <div class="card-header">
              <span>段落召回结果（{{ recallTableData.length }} 条）</span>
              <span v-if="stageResults.paragraph.elapsed_time">召回总耗时:{{ stageResults.paragraph.elapsed_time }}秒</span>
              <div class="progress-group">
                <span v-if="recallProgress">召回进度{{ recallProgress }}%</span>
                <el-progress :percentage="recallProgress" :stroke-width="20" :format="() => ''" text-inside
                  class="center-progress" style="width: 200px;" />
              </div>
            </div>
          </template>

          <el-table :data="recallTableData" border height="650" class="custom-table"
            v-loading="stageResults.paragraph.loading">
            <el-table-column prop="paragraph_id" label="段落ID" width="150" />
            <el-table-column prop="summary" label="段落摘要" />
            <el-table-column label="段落内容">
              <template #default="{ row }">
                <el-input v-model="row.content" style="width: 100%" :rows="15" type="textarea" />
              </template>
            </el-table-column>
            <el-table-column label="段落原文" v-if="recallTableData.some(row => row.source_text)" width="250">
              <template #default="{ row }">
                <el-input v-model="row.source_text" style="width:  100%" :rows="15" type="textarea" resize="none"
                  v-if="row.source_text" placeholder="无原文内容" />
              </template>
            </el-table-column>
            <el-table-column prop="parent_description" label="来源描述" width="150" />
            <el-table-column prop="document_name" label="来源文档" width="150">
              <template #default="{ row }">
                <el-text @click="handleFilePreview(row.document_name)" class="mx-1" type="primary"
                  style="text-decoration: underline;">{{
                    row.document_name }}</el-text>
              </template>
            </el-table-column>
            <el-table-column prop="context_relevance" align="center" width="100" label="语境相关性" v-if="has_score" />
            <el-table-column prop="context_sufficiency" align="center" width="120" label="上下文充分性" v-if="has_score" />
            <el-table-column prop="context_clarity" align="center" width="100" label="语境清晰性" v-if="has_score" />
            <el-table-column prop="reliability" align="center" width="100" label="可信度" v-if="has_score" />
            <el-table-column prop="total_score" align="center" width="100" label="汇总得分" v-if="has_score" />
            <el-table-column prop="diagnosis" width="100" label="诊断信息" v-if="has_score" />
          </el-table>
        </el-card>
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
import { ElMessage, ElMessageBox, ElLoading } from 'element-plus'
import { ref, reactive, computed, inject, onUnmounted, watch } from 'vue'
import { ElImage, ElImageViewer } from 'element-plus'
import { useAuthStore } from '@/store/modules/auth';
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

const escapeHtml = (str = '') => str
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#39;')

const escapeAttribute = (str = '') => str
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#39;')

const inlineMarkdown = (text = '') => {
  const placeholders = []
  const createPlaceholder = (html) => {
    const token = `__MDPLACEHOLDER_${placeholders.length}__`
    placeholders.push({ token, html })
    return token
  }

  let working = text

  working = working.replace(/`([^`]+)`/g, (_, code = '') =>
    createPlaceholder(`<code>${escapeHtml(code)}</code>`))

  working = working.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_, alt = '', url = '') =>
    createPlaceholder(`<img src="${escapeAttribute(url)}" alt="${escapeHtml(alt)}" loading="lazy" />`))

  working = working.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, label = '', url = '') =>
    createPlaceholder(`<a href="${escapeAttribute(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`))

  let result = escapeHtml(working)

  result = result.replace(/\*\*([^*]+)\*\*/g, (_, content = '') => `<strong>${content}</strong>`)
  result = result.replace(/\*([^*]+)\*/g, (_, content = '') => `<em>${content}</em>`)
  result = result.replace(/~~([^~]+)~~/g, (_, content = '') => `<del>${content}</del>`)

  for (const { token, html } of placeholders) {
    result = result.replaceAll(token, html)
  }

  return result
}

const renderMarkdown = (markdown = '') => {
  const lines = markdown.replace(/\r\n/g, '\n').split('\n')
  const html = []
  let inCodeBlock = false
  let codeBuffer = []
  let codeLang = ''
  let listType = null
  let listBuffer = []
  let paragraphBuffer = []

  const flushParagraph = () => {
    if (!paragraphBuffer.length) return
    html.push(`<p>${paragraphBuffer.join(' ')}</p>`)
    paragraphBuffer = []
  }

  const flushList = () => {
    if (!listType || !listBuffer.length) return
    html.push(`<${listType}>${listBuffer.join('')}</${listType}>`)
    listType = null
    listBuffer = []
  }

  const flushCode = () => {
    if (!inCodeBlock) return
    const codeContent = escapeHtml(codeBuffer.join('\n'))
    const langAttr = codeLang ? ` class="language-${escapeAttribute(codeLang)}"` : ''
    html.push(`<pre><code${langAttr}>${codeContent}</code></pre>`)
    inCodeBlock = false
    codeBuffer = []
    codeLang = ''
  }

  for (const rawLine of lines) {
    const trimmed = rawLine.trim()

    if (trimmed.startsWith('```')) {
      if (inCodeBlock) {
        flushCode()
      } else {
        flushParagraph()
        flushList()
        inCodeBlock = true
        codeLang = trimmed.slice(3).trim()
      }
      continue
    }

    if (inCodeBlock) {
      codeBuffer.push(rawLine)
      continue
    }

    if (!trimmed) {
      flushParagraph()
      flushList()
      continue
    }

    const headingMatch = trimmed.match(/^(#{1,6})\s+(.*)$/)
    if (headingMatch) {
      const level = headingMatch[1].length
      const content = headingMatch[2]
      flushParagraph()
      flushList()
      html.push(`<h${level}>${inlineMarkdown(content)}</h${level}>`)
      continue
    }

    if (trimmed.startsWith('>')) {
      const content = trimmed.replace(/^>\s?/, '')
      flushParagraph()
      flushList()
      html.push(`<blockquote>${inlineMarkdown(content)}</blockquote>`)
      continue
    }

    const orderedMatch = trimmed.match(/^(\d+)\.\s+(.*)$/)
    if (orderedMatch) {
      const content = orderedMatch[2]
      flushParagraph()
      if (listType !== 'ol') {
        flushList()
        listType = 'ol'
      }
      listBuffer.push(`<li>${inlineMarkdown(content)}</li>`)
      continue
    }

    const unorderedMatch = trimmed.match(/^[-*+]\s+(.*)$/)
    if (unorderedMatch) {
      const content = unorderedMatch[1]
      flushParagraph()
      if (listType !== 'ul') {
        flushList()
        listType = 'ul'
      }
      listBuffer.push(`<li>${inlineMarkdown(content)}</li>`)
      continue
    }

    if (paragraphBuffer.length) {
      paragraphBuffer.push('<br />' + inlineMarkdown(trimmed))
    } else {
      paragraphBuffer.push(inlineMarkdown(trimmed))
    }
  }

  flushCode()
  flushParagraph()
  flushList()

  if (!html.length) {
    return '<p></p>'
  }

  return html.join('\n')
}

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
const eventSource = ref(null)
const scoreThreshold = ref(null)
const recallStatus = ref('')
const recallButtonLoading = ref(false)

const recallStages = ref([
  { name: 'domain', desc: '筛选与问题匹配的知识领域' },
  { name: 'category', desc: '筛选领域下的细分分类' },
  { name: 'document', desc: '筛选分类下的相关文档' },
  { name: 'paragraph', desc: '从文档中召回相关段落' }
])
const activeStages = ref([]);
const currentStageIndex = ref(0)
const recallProgress = ref(0)
const stageResults = reactive({
  domain: { loading: false, data: [], elapsed_time: '' }, // data=选中的领域列表
  category: { loading: false, data: [], elapsed_time: '' }, // data=选中的分类列表
  document: { loading: false, data: [], elapsed_time: '' }, // data=选中的文档列表
  paragraph: { loading: false, data: [], elapsed_time: '' } // data=召回的段落列表（最终表格数据）
})

/* dialogs */
const createDialogVisible = ref(false)
const appendDialogVisible = ref(false)
const deleteDialogVisible = ref(false)
const deleteDocDialogVisible = ref(false)
const showParDialogVisible = ref(false)
const updateIndexDialogVisible = ref(false)

/* loading */
const loadingInstance = ref(null)

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

function handleCollapseChange(event) {
  if (activeStages.value.length == 1) {
    activeStages.value = ['domain', 'category', 'document']
  } else {
    activeStages.value = []
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

  loadingInstance.value = ElLoading.service({
    lock: true, // 锁定滚动
    text: '正在生成AI答案...', // 加载文本
  })

  try {
    const formData = new FormData()
    formData.append('question', query.value)
    formData.append('context', JSON.stringify(recallTableData.value))
    formData.append('kb_id', selectedKBOption.value.split(':')[0])

    const { data } = await api.post('chat', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })

    const markdownAnswer = data.answer || ''
    const htmlContent = `<div class="markdown-body">${renderMarkdown(markdownAnswer)}</div>`

    ElMessageBox.alert(htmlContent, 'AI回答', {
      confirmButtonText: '确定',
      customClass: 'ai-answer-message-box',
      dangerouslyUseHTMLString: true,
      showClose: false
    })

  } catch (error) {
    console.error('获取AI回答失败:', error)
    ElMessage.error('获取AI回答失败: ' + (error.response?.data?.message || error.message))
  } finally {
    if (loadingInstance.value) {
      loadingInstance.value.close()
      loadingInstance.value = null
    }
  }
}

function copyToClipboard(documentId) {
  if (!documentId || documentId === '') {
    ElMessage.warning('文档ID为空，无法复制');
    return;
  }

  // 使用浏览器原生剪贴板API实现复制
  navigator.clipboard.writeText(String(documentId))
    .then(() => {
      // 复制成功提示
      ElMessage.success('文档ID已复制到剪贴板');
    })
    .catch((error) => {
      ElMessage.error('复制失败，请手动复制');
      console.error('剪贴板复制错误：', error);
      const tempInput = document.createElement('input');
      tempInput.value = String(documentId);
      document.body.appendChild(tempInput);
      tempInput.select();
      document.execCommand('copy');
      document.body.removeChild(tempInput);
    });
}

/*  召回测试  */
async function doRecall() {
  if (!query.value.trim()) {
    ElMessage.warning('请输入查询内容');
    return;
  }
  if (!selectedKBOption.value) {
    ElMessage.warning('请选择知识库');
    return;
  }
  recallButtonLoading.value = true;
  resetRecall(false);

  const [kb_id] = selectedKBOption.value.split(':');
  const authStore = useAuthStore();
  const token = authStore.token || '';
  const baseApiUrl = import.meta.env.VITE_APP_API_URL;

  // 构建 SSE 请求参数
  const urlParams = new URLSearchParams();
  urlParams.append('kb_id', kb_id);
  urlParams.append('question', query.value);
  urlParams.append('has_source_text', 'true');
  urlParams.append('has_score', has_score.value.toString());
  urlParams.append('streaming', 'true');
  if (scoreThreshold.value !== null && scoreThreshold.value !== '') {
    urlParams.append('score_threshold', parseFloat(scoreThreshold.value).toString());
  }
  const sseUrl = `${baseApiUrl}recall?${urlParams.toString()}`;

  try {
    // 用 Fetch 发起请求
    const response = await fetch(sseUrl, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Accept': 'text/event-stream',
        'Cache-Control': 'no-cache'
      },
      credentials: 'same-origin'
    });

    // 检查请求是否成功
    if (!response.ok) {
      throw new Error(`身份验证失败或请求错误：${response.status} ${response.statusText}`);
    }

    // 解析 SSE 响应流
    const reader = response.body.getReader(); // 获取流读取器
    const decoder = new TextDecoder('utf-8'); // 解码二进制流为字符串
    let partialMessage = ''; // 存储分块到达的不完整消息

    // 标记 SSE 连接状态
    eventSource.value = {
      reader,
      closed: false,
      close: () => { // 自定义关闭方法
        reader.cancel('主动关闭 SSE 流');
        eventSource.value.closed = true;
      }
    };

    // 循环读取流数据
    while (!eventSource.value.closed) {
      const { done, value } = await reader.read();

      // 流结束
      if (done) {
        ElMessage.success('流式召回全流程完成！');
        break;
      }

      // 解码二进制数据 + 拼接之前的不完整消息
      const chunk = decoder.decode(value, { stream: true });
      partialMessage += chunk;

      // 分割 SSE 消息
      const messages = partialMessage.split('\n\n');
      partialMessage = messages.pop() || ''; // 最后一个可能是不完整消息，留到下次处理

      // 处理SSE 消息
      for (const msg of messages) {
        if (!msg.trim()) continue; // 跳过空消息

        try {
          const dataLine = msg.split('\n').find(line => line.startsWith('data:'));
          if (!dataLine) continue;

          // 解析 JSON 数据
          const dataStr = dataLine.slice(5).trim();
          const { stage, data, message: sseMsg } = JSON.parse(dataStr);

          // 原有阶段更新逻辑
          const stageMap = { domain: 0, category: 1, document: 2, paragraph: 3 };
          const currentIdx = stageMap[stage] || 0;

          currentStageIndex.value = currentIdx + 1;
          recallProgress.value = (currentIdx + 1) * 25;
          // ElMessage.success(`[${recallStages.value[currentIdx].label}] ${sseMsg}`);

          // 阶段数据处理
          switch (stage) {
            case 'domain':
              stageResults.domain.loading = false;

              stageResults.domain.data = data.selected_domains || [];
              stageResults.domain.elapsed_time = data.elapsed_time || '';
              stageResults.category.loading = true;
              break;

            case 'category':
              stageResults.category.loading = false;
              stageResults.category.data = data.selected_categories || [];
              stageResults.category.elapsed_time = data.elapsed_time || '';
              stageResults.document.loading = true;
              break;

            case 'document':
              stageResults.document.loading = false;
              stageResults.document.data = data.selected_documents || [];
              if (!data.selected_documents?.length) {
                currentStageIndex.value = 4;
                recallProgress.value = 100;
                stageResults.paragraph.loading = false;
                ElMessage.warning('无匹配文档，段落召回终止');
                eventSource.value.close(); // 关闭流
                return;
              }
              stageResults.document.elapsed_time = data.elapsed_time || '';
              stageResults.paragraph.loading = true;
              break;

            case 'paragraph':
              stageResults.paragraph.loading = false;
              recallTableData.value = data.target_paragraphs.map(par => ({
                paragraph_id: par.paragraph_id,
                summary: par.summary || '-',
                content: par.content || '-',
                document_name: par.document_name || '-',
                source_text: par.source_text || '-',
                parent_description: par.parent_description || '-', // 修复表格字段缺失
                context_relevance: par.context_relevance ?? '-',
                context_sufficiency: par.context_sufficiency ?? '-', // 补充评分字段
                context_clarity: par.context_clarity ?? '-', // 补充评分字段
                reliability: par.reliability, // 置信度
                total_score: par.total_score ?? '-',
                diagnosis: par.diagnosis ?? '-' // 补充诊断字段
              }));
              stageResults.paragraph.elapsed_time = data.elapsed_time || '';
              break;

            case 'error':
              currentStageIndex.value = stageMap[stage] || 0;
              recallProgress.value = (stageMap[stage] + 1) * 25;
              ElMessage.error(`[${recallStages.value[stageMap[stage]].label}] ${sseMsg}`);
              Object.keys(stageResults).forEach(key => {
                stageResults[key].loading = false;
              });
              eventSource.value.close();
              break;

            case 'complete':
              ElMessage.success('流式召回全流程完成！');
              recallProgress.value = 100;
              eventSource.value.close();
              break;
          }
        } catch (parseError) {
          ElMessage.error('召回数据解析失败，请重试');
          console.error('SSE 消息解析错误：', parseError, '原始消息：', msg);
          eventSource.value.close();
          resetRecall(true);
          break;
        }
      }
    }
  } catch (initError) {
    ElMessage.error(`流式召回初始化失败：${initError.message}`);
    console.error('SSE 初始化错误：', initError);
    resetRecall(true);
  }
  finally {
    recallButtonLoading.value = false;
  }
}

/*  重置召回 */
function resetRecall(fullReset = true) {
  // 关闭 SSE 流
  if (eventSource.value) {
    if (eventSource.value.close) {
      eventSource.value.close(); // Fetch 流的自定义关闭方法
    } else {
      eventSource.value.close(); // EventSource 关闭方法
    }
    eventSource.value = null;
  }

  currentStageIndex.value = 0;
  recallProgress.value = 0;
  Object.keys(stageResults).forEach(key => {
    stageResults[key] = { loading: false, data: [] };
  });
  recallTableData.value = [];
  recallStatus.value = '';
  recallButtonLoading.value = false;

  if (fullReset) {
    query.value = '';
    selectedKBOption.value = '';
    scoreThreshold.value = null;
  }
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

.horizontal-collapse {
  display: flex;
  gap: 16px;
  width: 100%;
  overflow: hidden;
}

.collapse-item {
  flex: 1;
  min-width: 280px;
}

:deep(.el-collapse-item__wrap) {
  width: 100%;
}

:deep(.stage-collapse .el-collapse-item__wrap) {
  will-change: height;
  background-color: #fff;
  border-bottom: none;
}

.stage-collapse.active {
  border-top-color: var(--el-color-primary);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

:deep(.stage-collapse .el-collapse-item__header) {
  height: auto;
  padding: 16px;
  font-weight: bold;
  border-bottom: none;
  background-color: #f9f9f9;
}

.time-gap {
  margin-left: 15px;
}

.recall-steps {
  margin-bottom: 30px;
}

:deep(.stage-collapse .el-collapse-item__content) {
  padding-bottom: 16px;
}

.stages-horizontal-container .stages-collapse-container {
  display: flex;
  width: 100%;
  gap: 16px;
  border: none;
}

.stage-collapse-item.active {
  border-top-color: var(--el-color-primary) !important;
  /* 选中时顶部蓝色边框 */
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15) !important;
  /* 增强阴影 */
}

:deep(.stages-collapse-container .el-collapse-item__wrap) {
  border: none !important;
  border-radius: 8px !important;
  overflow: hidden;
}

:deep(.stage-collapse-item .el-collapse-item__header) {
  height: auto;
  padding: 16px;
  font-weight: bold;
  border-bottom: none !important;
  background-color: #f9f9f9 !important;
  border-radius: 8px 8px 0 0 !important;
}

.stage-collapse-item {
  flex: 1;
  /* 3个项平分宽度 */
  min-width: 0;
  /* 防止内容溢出 */
  border-radius: 8px !important;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1) !important;
  transition: all 0.3s ease;
  border-top: 3px solid #f0f0f0 !important;
  /* 默认顶部边框色 */
}


.stage-card {
  flex: 1;
  transition: all 0.3s ease;
  border-top: 3px solid #f0f0f0;
  min-height: 0px;
}

.stage-card.active {
  border-top-color: var(--el-color-primary);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.stage-card .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: bold;
}

.stage-content {
  height: 180px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  padding: 12px;
}

.tag-group {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.paragraph-results-card {
  margin-top: 20px;
}

.paragraph-results-card .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.paragraph-results-card .progress-group {
  display: flex;
  align-items: center;
  gap: 12px;
}

:deep(.stage-collapse-item .el-collapse-item__content) {
  padding: 0 16px 16px !important;
  border-top: none !important;
}

.stage-tip {
  color: var(--el-text-color-secondary);
  text-align: center;
  padding: 40px 0;
  font-size: 14px;
}

.tag-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px;
  background-color: var(--el-bg-color);
  border-radius: 4px;
}

:deep(.tag-group) {
  padding: 8px;
  gap: 6px;
}

:deep(.el-collapse-item__header) {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

:deep(.el-steps) {
  margin-bottom: 5px;
}

:deep(.el-step__description) {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

:deep(.el-table__empty-text) {
  padding: 60px 0;
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
  width: min(70vw, 960px);
  max-height: 80vh;
}

.ai-answer-message-box .el-message-box__content {
  max-height: calc(80vh - 120px);
  overflow-y: auto;
  padding: 0 24px 24px;
}

.ai-answer-message-box .el-message-box__content .markdown-body {
  padding-top: 12px;
}

.markdown-body {
  color: #1f2933;
  font-size: 14px;
  line-height: 1.7;
}

.markdown-body h1,
.markdown-body h2,
.markdown-body h3,
.markdown-body h4,
.markdown-body h5,
.markdown-body h6 {
  font-weight: 600;
  line-height: 1.3;
  margin: 16px 0 12px;
}

.markdown-body h1 {
  font-size: 26px;
}

.markdown-body h2 {
  font-size: 22px;
}

.markdown-body h3 {
  font-size: 18px;
}

.markdown-body p {
  margin: 12px 0;
}

.markdown-body ul,
.markdown-body ol {
  padding-left: 1.5em;
  margin: 12px 0;
}

.markdown-body li + li {
  margin-top: 4px;
}

.markdown-body blockquote {
  margin: 12px 0;
  padding: 12px 16px;
  border-left: 4px solid #2c7be5;
  background: #f1f5f9;
  color: #334155;
}

.markdown-body pre {
  background: #f6f8fa;
  border-radius: 6px;
  padding: 12px 16px;
  overflow: auto;
  font-size: 13px;
}

.markdown-body code {
  background: #f6f8fa;
  border-radius: 4px;
  padding: 2px 4px;
  font-size: 13px;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
}

.markdown-body pre code {
  background: transparent;
  padding: 0;
}

.markdown-body img {
  max-width: 100%;
  height: auto;
  display: block;
  margin: 12px auto;
}

.markdown-body table {
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0;
  font-size: 13px;
}

.markdown-body th,
.markdown-body td {
  border: 1px solid #e2e8f0;
  padding: 8px 12px;
  text-align: left;
}

.markdown-body th {
  background: #f8fafc;
}

.markdown-body a {
  color: #2563eb;
  text-decoration: underline;
  word-break: break-word;
}

:deep(.el-dialog__body) {
  padding: 0 !important;
  margin: 0;
}

:deep(.el-dialog__header) {
  padding: 16px 20px;
  border-bottom: 1px solid #eee;
}

:deep(.el-step.is-center .el-step__description) {
  padding-left: 20%;
  padding-right: 20%;
  padding-top: 5px;
}
</style>