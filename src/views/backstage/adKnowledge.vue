<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getKnowledgeFiles, uploadKnowledgeFile, deleteKnowledgeFile, syncKnowledge, getKnowledgeStats } from '@/api/backstage/adKnowledge.js'

const knowledgeFiles = ref([])
const knowledgeStats = ref({})
const totalFiles = ref(0)
const syncing = ref(false)
const uploading = ref(false)
const fileInputRef = ref(null)

const route = useRoute()

const triggerUpload = () => {
  fileInputRef.value?.click()
}

const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

const formatDateTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp * 1000)
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  const h = String(date.getHours()).padStart(2, '0')
  const min = String(date.getMinutes()).padStart(2, '0')
  const s = String(date.getSeconds()).padStart(2, '0')
  return `${y}-${m}-${d} ${h}:${min}:${s}`
}

const getFileIconType = (ext) => {
  const extLower = (ext || '').toLowerCase().replace('.', '')
  const iconMap = {
    'pdf': 'pdf',
    'doc': 'word',
    'docx': 'word',
    'md': 'markdown',
    'markdown': 'markdown',
    'xmind': 'xmind'
  }
  return iconMap[extLower] || 'file'
}

const tableHeaderStyle = {
  background: 'linear-gradient(135deg, #f8f9fc 0%, #eef1f7 100%)',
  color: '#2c3e50',
  fontWeight: '600',
  fontSize: '13px',
  padding: '14px 16px',
  borderBottom: '2px solid #e8ecf3'
}

const tableRowClassName = ({ rowIndex }) => {
  return rowIndex % 2 === 0 ? 'el-table__row--striped' : ''
}

const loadKnowledgeFiles = async () => {
  try {
    const res = await getKnowledgeFiles()
    if (res.success) {
      knowledgeFiles.value = res.data || []
      totalFiles.value = res.total || 0
    }
  } catch (e) {
    ElMessage.error('加载文件列表失败')
  }
}

const loadKnowledgeStats = async () => {
  try {
    const res = await getKnowledgeStats()
    if (res.success) {
      knowledgeStats.value = res.data || {}
    }
  } catch (e) {
    console.error('加载统计信息失败', e)
  }
}

const handleUpload = async (event) => {
  const files = event.target.files
  if (!files || files.length === 0) return

  uploading.value = true
  const loadingMsg = ElMessage({
    message: `正在上传 ${files.length} 个文件...`,
    type: 'info',
    duration: 0
  })

  let successCount = 0
  let failCount = 0
  let failMessages = []

  for (const file of files) {
    try {
      const res = await uploadKnowledgeFile(file)
      if (res.success) {
        successCount++
      } else {
        failCount++
        failMessages.push(`${file.name}: ${res.detail || '上传失败'}`)
      }
    } catch (e) {
      failCount++
      failMessages.push(`${file.name}: ${e.message || '上传失败'}`)
    }
  }

  loadingMsg.close()
  uploading.value = false
  event.target.value = ''

  if (successCount > 0 && failCount === 0) {
    ElMessage.success(`成功上传 ${successCount} 个文件`)
  } else if (successCount > 0 && failCount > 0) {
    ElMessage.warning(`成功上传 ${successCount} 个文件，${failCount} 个文件上传失败`)
    console.warn('上传失败的文件:', failMessages)
  } else if (failCount > 0) {
    ElMessage.error(`${failCount} 个文件上传失败`)
    console.error('上传失败的文件:', failMessages)
  }

  if (successCount > 0) {
    loadKnowledgeFiles()
    loadKnowledgeStats()
  }
}

const handleDelete = async (filename) => {
  try {
    await ElMessageBox.confirm(`确定要删除文件 "${filename}" 吗？`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    const res = await deleteKnowledgeFile(filename)
    if (res.success) {
      ElMessage.success('删除成功')
      loadKnowledgeFiles()
      loadKnowledgeStats()
    }
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const handleSync = async () => {
  try {
    await ElMessageBox.confirm('确定要同步知识库到向量库吗？这将重新导入所有文档。', '提示', {
      confirmButtonText: '确定同步',
      cancelButtonText: '取消',
      type: 'warning'
    })
    syncing.value = true
    const loadingMsg = ElMessage({
      message: '正在同步到向量库，请稍候...',
      type: 'info',
      duration: 0
    })

    const res = await syncKnowledge()
    loadingMsg.close()

    if (res.success) {
      // 优先显示 data.message，然后是顶层 message
      const message = res.data?.message || res.message || '同步成功'
      ElMessage({
        message: message,
        type: 'success',
        duration: 5000
      })
      loadKnowledgeFiles()
      loadKnowledgeStats()
    } else {
      const message = res.data?.message || res.message || res.detail || '同步失败'
      ElMessage.error(message)
    }
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(`同步失败: ${e.message || '未知错误'}`)
    }
  } finally {
    syncing.value = false
  }
}

const processToolParams = async () => {
  const tool = route.query.tool
  if (!tool) {
    await loadKnowledgeFiles()
    await loadKnowledgeStats()
    return
  }

  let args = null
  try {
    args = route.query.args ? JSON.parse(route.query.args) : null
  } catch (e) {
    args = null
  }

  switch (tool) {
    case 'list_knowledge_files': {
      await loadKnowledgeFiles()
      await loadKnowledgeStats()
      break
    }
    case 'sync_knowledge_base': {
      await loadKnowledgeFiles()
      await loadKnowledgeStats()
      handleSync()
      break
    }
    case 'delete_knowledge_file': {
      await loadKnowledgeFiles()
      await loadKnowledgeStats()
      const filename = args?.filename
      if (filename) {
        handleDelete(filename)
      }
      break
    }
    default:
      await loadKnowledgeFiles()
      await loadKnowledgeStats()
      break
  }
}

onMounted(() => {
  processToolParams()
})

watch(() => route.query, () => {
  processToolParams()
}, { deep: true })
</script>

<template>
  <div class="container">
    <div class="header-section">
      <div class="stats-cards">
        <div class="stat-card">
          <div class="stat-icon file"></div>
          <div class="stat-content">
            <div class="stat-value">{{ totalFiles }}</div>
            <div class="stat-label">知识库文件</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon brain"></div>
          <div class="stat-content">
            <div class="stat-value">{{ knowledgeStats.total_chunks || 0 }}</div>
            <div class="stat-label">向量块数</div>
          </div>
        </div>
      </div>
    </div>

    <div class="toolbar">
      <el-button type="primary" @click="loadKnowledgeFiles">刷新</el-button>
      <el-button type="success" @click="triggerUpload" :disabled="uploading">上传文件</el-button>
      <input 
        ref="fileInputRef"
        type="file" 
        multiple 
        style="display:none" 
        @change="handleUpload"
        accept=".md,.markdown,.pdf,.docx,.doc,.xmind"
      >
      <el-button :disabled="syncing || totalFiles === 0" @click="handleSync" type="warning">同步到向量库</el-button>
      <span class="stats-info">
        {{ totalFiles }} 个文件 | {{ knowledgeStats.total_chunks || 0 }} 个向量块
      </span>
    </div>

    <div class="table-container">
      <el-table :data="knowledgeFiles" fit style="width: 100%" :header-cell-style="tableHeaderStyle" :row-class-name="tableRowClassName">
        <el-table-column label="文件名" min-width="300">
          <template #default="{ row }">
            <div class="file-name-cell">
              <!-- PDF 图标 -->
              <svg v-if="getFileIconType(row.ext) === 'pdf'" class="file-icon pdf" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <text x="7" y="17" font-size="6" fill="currentColor" stroke="none" font-weight="bold">PDF</text>
              </svg>
              <!-- Word 图标 -->
              <svg v-else-if="getFileIconType(row.ext) === 'word'" class="file-icon word" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <line x1="8" y1="13" x2="16" y2="13"/>
                <line x1="8" y1="17" x2="13" y2="17"/>
              </svg>
              <!-- Markdown 图标 -->
              <svg v-else-if="getFileIconType(row.ext) === 'markdown'" class="file-icon markdown" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <text x="5" y="18" font-size="7" fill="currentColor" stroke="none" font-weight="bold">M↓</text>
              </svg>
              <!-- XMind 图标 -->
              <svg v-else-if="getFileIconType(row.ext) === 'xmind'" class="file-icon xmind" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="3"/>
                <circle cx="5" cy="6" r="2"/>
                <circle cx="19" cy="6" r="2"/>
                <circle cx="5" cy="18" r="2"/>
                <circle cx="19" cy="18" r="2"/>
                <line x1="9.5" y1="10" x2="6.5" y2="7.5"/>
                <line x1="14.5" y1="10" x2="17.5" y2="7.5"/>
                <line x1="9.5" y1="14" x2="6.5" y2="16.5"/>
                <line x1="14.5" y1="14" x2="17.5" y2="16.5"/>
              </svg>
              <!-- 通用文件图标 -->
              <svg v-else class="file-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <line x1="16" y1="13" x2="8" y2="13"/>
                <line x1="16" y1="17" x2="8" y2="17"/>
              </svg>
              <span class="file-name">{{ row.filename }}</span>
              <span v-if="!row.supported" class="unsupported-tag">不支持</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="文件类型" width="150" align="center">
          <template #default="{ row }">
            <span :class="['type-tag', { supported: row.supported, unsupported: !row.supported }]">
              {{ row.ext.replace('.', '').toUpperCase() }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="文件大小" width="150" align="center">
          <template #default="{ row }">{{ formatFileSize(row.size) }}</template>
        </el-table-column>
        <el-table-column label="修改时间" width="180" align="center">
          <template #default="{ row }">{{ formatDateTime(row.modified) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120" align="center">
          <template #default="{ row }">
            <el-button type="danger" size="small" @click="handleDelete(row.filename)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="knowledgeFiles.length === 0" class="empty-state">
        <svg class="empty-icon" viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="16" y1="13" x2="8" y2="13"/>
          <line x1="16" y1="17" x2="8" y2="17"/>
          <polyline points="10 9 9 9 8 9"/>
        </svg>
        <div class="empty-text">暂无知识库文件</div>
        <div class="empty-hint">点击上方"上传文件"按钮添加文档</div>
      </div>
    </div>

    <div class="supported-formats">
      <div class="format-title">支持的文件格式</div>
      <div class="format-list">
        <span class="format-item">.md</span>
        <span class="format-item">.markdown</span>
        <span class="format-item">.pdf</span>
        <span class="format-item">.docx</span>
        <span class="format-item">.doc</span>
        <span class="format-item">.xmind</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.container {
  padding: 20px;
  min-height: 100%;
  background-color: var(--bg-page);
}

.header-section {
  margin-bottom: 20px;
}

.stats-cards {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 22px;
  background: linear-gradient(135deg, #fff 0%, #fafbfc 100%);
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  min-width: 200px;
  border: 1px solid rgba(0, 0, 0, 0.04);
  transition: all 0.25s ease;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}

.stat-icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--primary-light) 0%, rgba(45, 125, 219, 0.12) 100%);
  border-radius: 12px;
}

.stat-icon svg {
  width: 24px;
  height: 24px;
  color: var(--primary);
}

.stat-icon.file::before {
  content: '';
  width: 20px;
  height: 24px;
  border: 2px solid var(--primary);
  border-radius: 4px;
  position: relative;
}

.stat-icon.file::after {
  content: '';
  width: 12px;
  height: 0;
  border-bottom: 2px solid var(--primary);
  position: absolute;
  transform: rotate(-45deg);
  top: 16px;
  right: 14px;
}

.stat-icon.brain::before {
  content: '';
  width: 20px;
  height: 18px;
  border: 2px solid var(--primary);
  border-radius: 50% 50% 40% 40%;
  position: relative;
}

.stat-icon.brain::after {
  content: '';
  width: 16px;
  height: 14px;
  border: 2px solid var(--primary);
  border-radius: 50% 50% 40% 40%;
  position: absolute;
  top: 24px;
  right: 16px;
}

.stat-content {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 26px;
  font-weight: 700;
  background: linear-gradient(135deg, var(--primary) 0%, #5b9bd5 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  line-height: 1.2;
}

.stat-label {
  font-size: 12px;
  color: var(--text-gray);
  margin-top: 4px;
  font-weight: 500;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding: 14px 18px;
  background: linear-gradient(135deg, #fff 0%, #fafbfc 100%);
  border-radius: 10px;
  flex-wrap: wrap;
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.04);
  border: 1px solid rgba(0, 0, 0, 0.04);
}

.stats-info {
  margin-left: auto;
  font-size: 12px;
  color: var(--text-gray);
  padding: 4px 12px;
  background: var(--bgc-light);
  border-radius: 12px;
  font-weight: 500;
}

.table-container {
  background-color: var(--bg-card);
  border-radius: 12px;
  padding: 0;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  overflow: hidden;
}

.table-container :deep(.el-table) {
  border-radius: 12px;
  overflow: hidden;
}

.table-container :deep(.el-table th.el-table__cell) {
  background: linear-gradient(135deg, #f8f9fc 0%, #eef1f7 100%);
  color: #2c3e50;
  font-weight: 600;
  font-size: 13px;
  padding: 14px 16px;
  border-bottom: 2px solid #e8ecf3;
}

.table-container :deep(.el-table td.el-table__cell) {
  padding: 12px 16px;
  border-bottom: 1px solid #f0f2f7;
  font-size: 13px;
  transition: all 0.2s ease;
}

.table-container :deep(.el-table tr:hover > td.el-table__cell) {
  background-color: rgba(45, 125, 219, 0.04);
}

.table-container :deep(.el-table .el-table__row--striped td.el-table__cell) {
  background-color: #fafbfd;
}

.table-container :deep(.el-table .el-table__row--striped:hover td.el-table__cell) {
  background-color: rgba(45, 125, 219, 0.04);
}

.table-container :deep(.el-table::before) {
  display: none;
}

.table-container :deep(.el-table__inner-wrapper::before) {
  display: none;
}

.file-name-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.file-icon {
  flex-shrink: 0;
}

.file-icon.pdf {
  color: #e74c3c;
}

.file-icon.word {
  color: #2980b9;
}

.file-icon.markdown {
  color: #34495e;
}

.file-icon.xmind {
  color: #f39c12;
}

.file-name {
  flex: 1;
  font-size: 13px;
  color: var(--text-title);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
}

.unsupported-tag {
  font-size: 11px;
  color: var(--main-delete);
  background-color: var(--main-fail-status);
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
}

.type-tag {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 12px;
  font-weight: 500;
  display: inline-block;
}

.type-tag.supported {
  background-color: var(--pass-bg-color);
  color: var(--pass);
}

.type-tag.unsupported {
  background-color: var(--main-fail-status);
  color: var(--main-delete);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  background: linear-gradient(135deg, #fafbfc 0%, #f5f7fa 100%);
  border-radius: 0 0 12px 12px;
}

.empty-icon {
  margin-bottom: 16px;
  color: #c0c4cc;
  opacity: 0.6;
}

.empty-text {
  font-size: 15px;
  color: var(--text-title);
  margin-bottom: 6px;
  font-weight: 500;
}

.empty-hint {
  font-size: 13px;
  color: var(--text-gray);
}

.supported-formats {
  margin-top: 16px;
  padding: 14px 18px;
  background-color: var(--bg-card);
  border-radius: 10px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.format-title {
  font-size: 12px;
  color: var(--text-gray);
  margin-bottom: 10px;
  font-weight: 500;
}

.format-list {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.format-item {
  font-size: 12px;
  padding: 5px 12px;
  background: linear-gradient(135deg, var(--primary-light) 0%, rgba(45, 125, 219, 0.08) 100%);
  color: var(--primary);
  border-radius: 14px;
  font-weight: 500;
  border: 1px solid rgba(45, 125, 219, 0.15);
  transition: all 0.2s ease;
}

.format-item:hover {
  background: var(--primary-light);
  border-color: var(--primary);
  transform: translateY(-1px);
}

:deep(.el-button--primary) {
  background: var(--grad-primary);
  border: none;
  box-shadow: 0 2px 6px rgba(45, 125, 219, 0.25);
}

:deep(.el-button--primary:hover) {
  background: var(--primary-hv);
  box-shadow: 0 4px 12px rgba(45, 125, 219, 0.35);
  transform: translateY(-1px);
}

:deep(.el-button--primary:active) {
  transform: translateY(0);
}

:deep(.el-button--success) {
  background: var(--pass);
  border: none;
  box-shadow: 0 2px 6px rgba(34, 197, 94, 0.25);
}

:deep(.el-button--success:hover) {
  background: var(--pass-hover);
  box-shadow: 0 4px 12px rgba(34, 197, 94, 0.35);
  transform: translateY(-1px);
}

:deep(.el-button--warning) {
  background: linear-gradient(135deg, #8e44ad, #9b59b6);
  border: none;
  color: #fff;
  box-shadow: 0 2px 6px rgba(142, 68, 173, 0.25);
}

:deep(.el-button--warning:hover) {
  background: linear-gradient(135deg, #9b59b6, #a66bbe);
  box-shadow: 0 4px 12px rgba(142, 68, 173, 0.35);
  transform: translateY(-1px);
}

:deep(.el-button--danger) {
  background: linear-gradient(135deg, var(--main-delete) 0%, #f78a8a 100%);
  border: none;
  box-shadow: 0 2px 6px rgba(245, 108, 108, 0.25);
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

:deep(.el-button--danger:hover) {
  background: linear-gradient(135deg, var(--main-delete-hover) 0%, #ff9999 100%);
  box-shadow: 0 4px 12px rgba(245, 108, 108, 0.35);
  transform: translateY(-1px);
}

:deep(.el-button--default) {
  border-color: var(--border-color);
  color: var(--text-body);
}

:deep(.el-button--default:hover) {
  border-color: var(--primary);
  color: var(--primary);
  background-color: var(--primary-light);
}

:deep(.el-button--small) {
  padding: 6px 14px;
  font-size: 12px;
  border-radius: 6px;
  font-weight: 500;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

:deep(.el-button.is-disabled),
:deep(.el-button.is-disabled:hover),
:deep(.el-button.is-disabled:focus) {
  background-color: var(--bgc-light) !important;
  border-color: var(--border-color) !important;
  color: #fff !important;
  box-shadow: none !important;
  opacity: 0.6;
  cursor: not-allowed;
}

:deep(.el-button--primary.is-disabled),
:deep(.el-button--primary.is-disabled:hover),
:deep(.el-button--primary.is-disabled:focus) {
  background-color: var(--bgc-light) !important;
  border-color: var(--border-color) !important;
  color: #fff !important;
  box-shadow: none !important;
}

:deep(.el-button--danger.is-disabled),
:deep(.el-button--danger.is-disabled:hover),
:deep(.el-button--danger.is-disabled:focus) {
  background-color: var(--bgc-light) !important;
  border-color: var(--border-color) !important;
  color: #fff !important;
  box-shadow: none !important;
}

:deep(.el-button--success.is-disabled),
:deep(.el-button--success.is-disabled:hover),
:deep(.el-button--success.is-disabled:focus) {
  background-color: var(--bgc-light) !important;
  border-color: var(--border-color) !important;
  color: #fff !important;
  box-shadow: none !important;
}

:deep(.el-button--warning.is-disabled),
:deep(.el-button--warning.is-disabled:hover),
:deep(.el-button--warning.is-disabled:focus) {
  background-color: var(--bgc-light) !important;
  border-color: var(--border-color) !important;
  color: #fff !important;
  box-shadow: none !important;
}

:deep(.el-table .el-button + .el-button) {
  margin-left: 6px;
}

:deep(.el-message-box__wrapper) {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 2001;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: rgba(0, 0, 0, 0.5);
  overflow: hidden;
}

:deep(.el-message-box) {
  position: relative;
  width: 420px;
  max-height: 80vh;
  background-color: var(--bg-card);
  border-radius: var(--radius-lg);
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
  overflow: hidden;
}

:deep(.el-message-box__content) {
  max-height: calc(80vh - 120px);
  overflow-y: auto;
  padding: 20px;
}

:deep(.el-message-box__header) {
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
  background: linear-gradient(180deg, var(--primary-light) 0%, rgba(239, 246, 255, 0.3) 100%);
}

:deep(.el-message-box__title) {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-title);
}

:deep(.el-message-box__btns) {
  padding: 16px 20px;
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>