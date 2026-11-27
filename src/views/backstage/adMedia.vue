<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getMediaFilesApi, uploadMediaFileApi, deleteMediaFileApi } from '@/api/backstage/adMedia.js'

const route = useRoute()
const loading = ref(false)
const mediaFiles = ref([])
const fileStats = ref({ total: 0, totalSize: 0 })
const previewVisible = ref(false)
const previewFile = ref(null)
const fileInputRef = ref(null)

// 加载媒体文件列表
const loadMediaFiles = async () => {
  loading.value = true
  try {
    const response = await getMediaFilesApi()
    if (response.success) {
      mediaFiles.value = response.data || []
      fileStats.value.total = mediaFiles.value.length
      fileStats.value.totalSize = mediaFiles.value.reduce((sum, f) => sum + (f.size || 0), 0)
    } else {
      throw new Error(response.detail || '加载失败')
    }
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

// 触发文件选择
const triggerUpload = async () => {
  try {
    await ElMessageBox.confirm(
      '上传素材时，请务必将文件命名为对应的知识点名称，否则系统将无法正确关联！',
      '上传提示',
      {
        confirmButtonText: '我知道了，继续上传',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    fileInputRef.value?.click()
  } catch (e) {
    // 用户点击取消，不做任何处理
  }
}

// 上传文件
const handleFileUpload = async (event) => {
  const files = event.target.files
  if (!files || files.length === 0) return
  
  loading.value = true
  try {
    let successCount = 0
    for (const file of files) {
      const formData = new FormData()
      formData.append('file', file)
      const response = await uploadMediaFileApi(formData)
      if (response.success) {
        successCount++
      } else {
        throw new Error(response.detail || `上传 ${file.name} 失败`)
      }
    }
    ElMessage.success(`成功上传 ${successCount} 个文件`)
    loadMediaFiles()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
    if (fileInputRef.value) {
      fileInputRef.value.value = ''
    }
  }
}

// 预览视频
const previewVideo = (file) => {
  previewFile.value = file
  previewVisible.value = true
}

// 关闭预览
const closePreview = () => {
  previewVisible.value = false
  previewFile.value = null
}

// 删除文件
const deleteFile = async (file) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除文件「${file.filename}」吗？删除后无法恢复。`,
      '确认删除',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    loading.value = true
    const response = await deleteMediaFileApi(file.filename)
    if (response.success) {
      ElMessage.success(response.message || '删除成功')
      loadMediaFiles()
    } else {
      throw new Error(response.detail || '删除失败')
    }
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e.message || '删除失败')
    }
  } finally {
    loading.value = false
  }
}

// 格式化文件大小
const formatFileSize = (bytes) => {
  if (!bytes) return '0 B'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

// 获取视频URL
const getVideoUrl = (file) => {
  return file.url || `/video-data/${encodeURIComponent(file.filename)}`
}

// 处理工具参数
const processToolParams = async () => {
  const tool = route.query.tool
  
  let args = null
  try {
    args = route.query.args ? JSON.parse(route.query.args) : null
  } catch (e) {
    args = null
  }
  
  await loadMediaFiles()
  
  if (!tool) return
  
  switch (tool) {
    case 'list_video_files':
      // 列表已在 loadMediaFiles 中加载
      break
    case 'upload_video_file':
      // 触发上传
      triggerUpload()
      break
    case 'delete_video_file': {
      const filename = args?.filename
      if (filename) {
        const file = mediaFiles.value.find(f => f.filename === filename)
        if (file) {
          deleteFile(file)
        }
      }
      break
    }
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
    <div class="content">
      <div class="card">
        <div class="toolbar">
          <button class="btn btn-primary" @click="loadMediaFiles">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M23 4v6h-6M1 20v-6h6"/>
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
            </svg>
            刷新
          </button>
          <button class="btn btn-success" @click="triggerUpload">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/>
              <line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
            上传素材
          </button>
          <input 
            ref="fileInputRef"
            type="file" 
            accept=".mp4,.avi,.mov,.wmv,.flv,.mkv,.webm" 
            multiple 
            style="display: none" 
            @change="handleFileUpload"
          >
          <span style="flex:1"></span>
          <span class="file-stats" v-if="fileStats.total > 0">
            共 {{ fileStats.total }} 个文件，总大小 {{ formatFileSize(fileStats.totalSize) }}
          </span>
        </div>
        <div class="upload-warning">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          <span>上传素材时，请务必将文件命名为对应的<span class="upload-warning-keyword">知识点名称</span>，否则系统将无法正确关联！</span>
        </div>
        
        <div v-if="loading" class="loading">加载中...</div>
        
        <div v-else-if="mediaFiles.length === 0" class="empty">
          <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="var(--text-gray)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <rect x="2" y="2" width="20" height="20" rx="2"/>
            <circle cx="8.5" cy="8.5" r="1.5"/>
            <polyline points="21 15 16 10 5 21"/>
          </svg>
          <p>暂无媒体文件，点击「上传素材」添加</p>
        </div>
        
        <div v-else class="file-list">
          <div class="file-list-header">
            <span class="col-icon"></span>
            <span class="col-name">文件名</span>
            <span class="col-size">大小</span>
            <span class="col-ext">格式</span>
            <span class="col-actions">操作</span>
          </div>
          <div class="file-row" v-for="file in mediaFiles" :key="file.filename">
            <span class="col-icon">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="var(--primary)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polygon points="23 7 16 12 23 17 23 7"/>
                <rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>
              </svg>
            </span>
            <span class="col-name">
              <span class="td-filename">{{ file.filename }}</span>
              <span v-if="file.source === 'oss'" class="oss-badge">OSS</span>
            </span>
            <span class="col-size">{{ formatFileSize(file.size) }}</span>
            <span class="col-ext">{{ file.ext || '--' }}</span>
            <span class="col-actions">
              <button class="btn-sm btn-sm-primary" @click="previewVideo(file)">
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                预览
              </button>
              <button class="btn-sm btn-sm-danger" @click="deleteFile(file)">
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                删除
              </button>
            </span>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 预览弹窗 -->
    <div v-if="previewVisible" class="preview-overlay" @click.self="closePreview">
      <div class="preview-modal">
        <div class="preview-header">
          <span class="preview-title">{{ previewFile?.filename }}</span>
          <button class="preview-close" @click="closePreview">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="preview-body">
          <video 
            v-if="previewFile"
            controls 
            autoplay 
            preload="auto" 
            playsinline
            :src="getVideoUrl(previewFile)"
            class="preview-video"
          >
            您的浏览器不支持视频播放
          </video>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.container {
  min-height: 85vh;
  background: var(--bg-page);
}

.content {
  padding: 20px 32px;
}

.card {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  padding: 24px 28px;
  margin-bottom: 20px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.file-stats {
  font-size: 12px;
  color: var(--text-gray);
}

.upload-warning {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: #fff5f5;
  border: 1px solid #ffcccc;
  border-radius: 8px;
  margin-bottom: 16px;
  color: #d32f2f;
  font-size: 13px;
  font-weight: 500;
}

.upload-warning-keyword {
  color: #d32f2f;
  font-weight: 700;
  padding: 0 4px;
}

.btn {
  padding: 7px 18px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.2s;
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.btn-primary {
  background: var(--primary);
  color: #fff;
}

.btn-primary:hover {
  background: var(--primary-hv);
}

.btn-success {
  background: var(--pass);
  color: #fff;
}

.btn-success:hover {
  background: var(--pass-hover);
}

.loading {
  text-align: center;
  padding: 50px;
  color: var(--text-gray);
  font-size: 16px;
}

.empty {
  min-height: 200px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: var(--text-gray);
  font-size: 15px;
}

/* 文件列表 - 使用卡片行样式，与 adOpSetting 的 param-card 风格一致 */
.file-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.file-list-header {
  display: flex;
  align-items: center;
  padding: 10px 18px;
  background: var(--bgc-light);
  border-radius: 10px 10px 0 0;
  border: 1px solid var(--border-color);
  font-size: 13px;
  font-weight: 600;
  color: var(--text-body);
}

.file-row {
  display: flex;
  align-items: center;
  padding: 12px 18px;
  background: #fff;
  border: 1px solid var(--border-color);
  border-top: none;
  font-size: 13px;
  color: var(--text-body);
  transition: all 0.2s ease;
}

.file-row:last-child {
  border-radius: 0 0 10px 10px;
}

.file-row:hover {
  background: rgba(45, 125, 219, 0.03);
  transform: translateX(2px);
}

.col-icon {
  width: 40px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.col-name {
  flex: 1;
  min-width: 0;
  padding-right: 12px;
}

.col-size {
  width: 90px;
  flex-shrink: 0;
  font-size: 12px;
  color: var(--text-gray);
}

.col-ext {
  width: 60px;
  flex-shrink: 0;
  font-size: 12px;
  color: var(--text-gray);
}

.col-actions {
  width: 150px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
}

.td-filename {
  font-weight: 500;
  color: var(--text-title);
  word-break: break-all;
}

.oss-badge {
  display: inline-block;
  font-size: 10px;
  color: var(--primary);
  background: var(--primary-light);
  padding: 1px 6px;
  border-radius: 4px;
  margin-left: 6px;
  font-weight: 500;
  vertical-align: middle;
}

/* 小按钮 */
.btn-sm {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 4px 10px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  transition: all 0.2s;
  line-height: 1.4;
}

.btn-sm-primary {
  background: var(--primary);
  color: #fff;
}

.btn-sm-primary:hover {
  background: var(--primary-hv);
}

.btn-sm-danger {
  background: var(--main-fail-status);
  color: var(--main-delete);
}

.btn-sm-danger:hover {
  background: var(--main-fail-status-hover);
}

/* 预览弹窗 */
.preview-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.preview-modal {
  background: #fff;
  border-radius: 12px;
  width: 90%;
  max-width: 800px;
  max-height: 90vh;
  overflow: hidden;
  box-shadow: 0 12px 48px rgba(0, 0, 0, 0.3);
  animation: slideUp 0.2s ease;
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(20px) scale(0.96); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.preview-header {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 15px;
  font-weight: 600;
}

.preview-title {
  color: var(--text-title);
}

.preview-close {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-gray);
  padding: 0 4px;
  font-size: 20px;
  transition: all 0.2s;
}

.preview-close:hover {
  color: var(--text-title);
}

.preview-body {
  padding: 16px;
  text-align: center;
  background: #000;
}

.preview-video {
  width: 100%;
  max-height: 70vh;
  border-radius: 8px;
}
</style>
