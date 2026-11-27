<!-- 图片解析/解答 组件 -->
<script setup>
import { ref, onUnmounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { analyzeImageApi } from '@/api/mainApi/photoAnalysis'

const props = defineProps({
  visible: Boolean,
  userId: { type: String, required: true }
})

const emit = defineEmits(['close'])

const activeView = ref('upload')
const inputText = ref('')
const selectedFile = ref(null)
const previewUrl = ref('')
const isDragging = ref(false)
const fileInputRef = ref(null)
const resultContent = ref('')
const resultImageUrl = ref('')
const errorMessage = ref('')
const imageLoadError = ref(false)
const imageZoomVisible = ref(false)
const followUpQuestion = ref('')
const isFollowUpLoading = ref(false)
const sessionId = ref('')
const resultContentRef = ref(null)
const isAnimating = ref(false)

watch(() => props.visible, (val) => {
  if (val) {
    resetState()
    document.body.style.overflow = 'hidden'
  } else {
    document.body.style.overflow = ''
  }
})

onUnmounted(() => {
  document.body.style.overflow = ''
})

const resetState = () => {
  activeView.value = 'upload'
  inputText.value = ''
  selectedFile.value = null
  previewUrl.value = ''
  resultContent.value = ''
  resultImageUrl.value = ''
  errorMessage.value = ''
  imageLoadError.value = false
  sessionId.value = ''
  followUpQuestion.value = ''
  isFollowUpLoading.value = false
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
}

const onFileChange = (event) => {
  const file = event.target.files[0]
  if (file) handleFile(file)
}

const onDrop = (event) => {
  event.preventDefault()
  isDragging.value = false
  const file = event.dataTransfer.files[0]
  if (file) handleFile(file)
}

const onDragOver = (event) => {
  event.preventDefault()
  isDragging.value = true
}

const onDragLeave = () => {
  isDragging.value = false
}

const handleFile = (file) => {
  if (!file.type.startsWith('image/')) {
    ElMessage.warning('请选择图片文件')
    return
  }
  if (file.size > 20 * 1024 * 1024) {
    ElMessage.warning('图片大小不能超过 20MB')
    return
  }
  selectedFile.value = file
  const reader = new FileReader()
  reader.onload = (e) => {
    previewUrl.value = e.target.result
  }
  reader.readAsDataURL(file)
}

const removeImage = () => {
  selectedFile.value = null
  previewUrl.value = ''
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
}

const submitAnalysis = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请上传图片')
    return
  }

  activeView.value = 'analyzing'
  errorMessage.value = ''
  resultContent.value = ''
  resultImageUrl.value = ''
  imageLoadError.value = false

  const minDelay = new Promise(resolve => setTimeout(resolve, 2000))

  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    formData.append('user_id', props.userId)
    formData.append('question', inputText.value || '请分析这张图片')
    formData.append('session_id', Date.now() + '_' + Math.random().toString(36).substring(2, 10))

    const apiCall = analyzeImageApi(formData)
    const [res] = await Promise.all([apiCall, minDelay])

    if (res.success) {
      resultContent.value = res.analysis || res.answer || ''
      resultImageUrl.value = res.oss_url || previewUrl.value
      sessionId.value = res.session_id || ''
      activeView.value = 'result'
    } else {
      errorMessage.value = `分析失败：${res.detail || res.message || '未知错误'}`
      activeView.value = 'result'
    }
  } catch (err) {
    await minDelay
    errorMessage.value = `网络错误：${err.message || '请检查网络连接'}`
    activeView.value = 'result'
  }
}

const submitFollowUp = async () => {
  if (!followUpQuestion.value.trim()) {
    ElMessage.warning('请输入问题')
    return
  }

  isFollowUpLoading.value = true

  try {
    const formData = new FormData()
    formData.append('user_id', props.userId)
    formData.append('question', followUpQuestion.value)
    formData.append('session_id', sessionId.value)

    const res = await analyzeImageApi(formData)

    if (res.success) {
      // 触发动画
      isAnimating.value = true
      setTimeout(() => {
        isAnimating.value = false
      }, 500)
      
      resultContent.value = res.analysis || res.answer || ''
      followUpQuestion.value = ''
      
      // 滚动到顶部
      if (resultContentRef.value) {
        resultContentRef.value.scrollTop = 0
      }
    } else {
      ElMessage.error(`追问失败：${res.detail || res.message || '未知错误'}`)
    }
  } catch (err) {
    ElMessage.error(`网络错误：${err.message || '请检查网络连接'}`)
  } finally {
    isFollowUpLoading.value = false
  }
}

const goToUpload = () => {
  resetState()
}

const handleClose = () => {
  emit('close')
}

const onImageError = () => {
  imageLoadError.value = true
}

const openImageZoom = () => {
  imageZoomVisible.value = true
}

const closeImageZoom = () => {
  imageZoomVisible.value = false
}

const renderMarkdown = (text) => {
  if (!text) return ''
  let html = text

  // 1. 代码块（最先处理，避免换行被替换）
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="pa-code-block"><code>$2</code></pre>')

  // 2. 行内代码
  html = html.replace(/`([^`]+)`/g, '<code class="pa-inline-code">$1</code>')

  // 3. 标题
  html = html.replace(/^### (.+)$/gm, '<h4>$1</h4>')
  html = html.replace(/^## (.+)$/gm, '<h3>$1</h3>')
  html = html.replace(/^# (.+)$/gm, '<h2>$1</h2>')

  // 4. 加粗和斜体
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')

  // 5. 分割线
  html = html.replace(/^---$/gm, '<hr>')

  // 6. 无序列表（在换行替换之前）
  html = html.replace(/^- (.+)$/gm, '<li>$1</li>')
  html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>')

  // 7. 有序列表
  html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
  html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ol>$1</ol>')

  // 8. 段落和换行（最后处理）
  html = html.replace(/\n\n/g, '</p><p>')
  html = html.replace(/\n/g, '<br>')

  return `<div class="pa-md-content"><p>${html}</p></div>`
}
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="photo-analysis-overlay">
      <div class="photo-analysis-container">
        <!-- 顶部标题栏 -->
        <div class="pa-header">
          <div class="pa-header-left">
            <div class="pa-logo">
              <svg viewBox="0 0 1024 1024" width="22" height="22"><path d="M85.333333 727.466667a32 32 0 0 1 32 32c0 60.842667 12.373333 95.146667 32.213334 114.986666 17.365333 17.365333 45.824 29.013333 93.44 31.616l21.546666 0.597334 3.242667 0.170666a32 32 0 0 1 0 63.658667l-3.242667 0.170667-12.458666-0.170667c-61.525333-1.578667-112.384-15.402667-147.797334-50.773333C66.56 881.92 53.333333 826.624 53.333333 759.466667a32 32 0 0 1 32-32zM938.666667 727.466667a32 32 0 0 1 32 32c0 67.157333-13.226667 122.496-50.944 160.256-37.76 37.717333-93.098667 50.944-160.256 50.944a32 32 0 0 1 0-64c60.842667 0 95.146667-12.373333 114.986666-32.213334 19.882667-19.84 32.213333-54.186667 32.213334-114.986666a32 32 0 0 1 32-32zM801.322667 653.056a109.909333 109.909333 0 0 1-10.026667 106.794667A115.285333 115.285333 0 0 1 695.424 810.666667h-367.36A114.602667 114.602667 0 0 1 230.4 756.949333a111.530667 111.530667 0 0 1-4.906667-110.165333L261.546667 576h506.410666l33.365334 77.056zM981.333333 480a32 32 0 0 1 0 64H42.666667a32 32 0 0 1 0-64h938.666666zM642.474667 384.085333c27.904 1.450667 52.352 22.997333 68.778666 61.013334l1.28 2.901333h-150.613333l5.674667-9.941333c20.437333-36.352 47.232-55.381333 74.88-53.973334zM373.333333 213.333333a96 96 0 1 1 0 192 96 96 0 0 1 0-192zM264.533333 53.333333a32 32 0 0 1 0 64c-60.842667 0-95.146667 12.373333-114.986666 32.213334-19.882667 19.84-32.213333 54.186667-32.213334 114.986666a32 32 0 0 1-64 0c0-67.157333 13.226667-122.496 50.944-160.256C142.08 66.56 197.376 53.333333 264.533333 53.333333zM759.466667 53.333333c67.157333 0 122.496 13.226667 160.256 50.944 37.717333 37.76 50.944 93.098667 50.944 160.256a32 32 0 0 1-64 0c0-60.842667-12.373333-95.146667-32.213334-114.986666-19.84-19.882667-54.186667-32.213333-114.986666-32.213334a32 32 0 0 1 0-64z" fill="currentColor"/></svg>
            </div>
            <div class="pa-title">图片解析</div>
          </div>
          <div class="pa-header-right">
            <button v-if="activeView !== 'upload'" class="pa-btn pa-btn-text" @click="goToUpload">
              <svg viewBox="0 0 1024 1024" width="16" height="16"><path d="M85.333333 727.466667a32 32 0 0 1 32 32c0 60.842667 12.373333 95.146667 32.213334 114.986666 17.365333 17.365333 45.824 29.013333 93.44 31.616l21.546666 0.597334 3.242667 0.170666a32 32 0 0 1 0 63.658667l-3.242667 0.170667-12.458666-0.170667c-61.525333-1.578667-112.384-15.402667-147.797334-50.773333C66.56 881.92 53.333333 826.624 53.333333 759.466667a32 32 0 0 1 32-32zM938.666667 727.466667a32 32 0 0 1 32 32c0 67.157333-13.226667 122.496-50.944 160.256-37.76 37.717333-93.098667 50.944-160.256 50.944a32 32 0 0 1 0-64c60.842667 0 95.146667-12.373333 114.986666-32.213334 19.882667-19.84 32.213333-54.186667 32.213334-114.986666a32 32 0 0 1 32-32zM801.322667 653.056a109.909333 109.909333 0 0 1-10.026667 106.794667A115.285333 115.285333 0 0 1 695.424 810.666667h-367.36A114.602667 114.602667 0 0 1 230.4 756.949333a111.530667 111.530667 0 0 1-4.906667-110.165333L261.546667 576h506.410666l33.365334 77.056zM981.333333 480a32 32 0 0 1 0 64H42.666667a32 32 0 0 1 0-64h938.666666zM642.474667 384.085333c27.904 1.450667 52.352 22.997333 68.778666 61.013334l1.28 2.901333h-150.613333l5.674667-9.941333c20.437333-36.352 47.232-55.381333 74.88-53.973334zM373.333333 213.333333a96 96 0 1 1 0 192 96 96 0 0 1 0-192zM264.533333 53.333333a32 32 0 0 1 0 64c-60.842667 0-95.146667 12.373333-114.986666 32.213334-19.882667 19.84-32.213333 54.186667-32.213334 114.986666a32 32 0 0 1-64 0c0-67.157333 13.226667-122.496 50.944-160.256C142.08 66.56 197.376 53.333333 264.533333 53.333333zM759.466667 53.333333c67.157333 0 122.496 13.226667 160.256 50.944 37.717333 37.76 50.944 93.098667 50.944 160.256a32 32 0 0 1-64 0c0-60.842667-12.373333-95.146667-32.213334-114.986666-19.84-19.882667-54.186667-32.213333-114.986666-32.213334a32 32 0 0 1 0-64z" fill="currentColor"/></svg>
              重新上传
            </button>
            <button class="pa-btn pa-btn-close" @click="handleClose">
              <svg viewBox="0 0 1024 1024" width="18" height="18"><path d="M563.8 512l262.5-312.9c4.4-5.2.7-13.1-6.1-13.1h-79.8c-4.7 0-9.2 2.1-12.3 5.7L511.6 449.8 295.1 191.7c-3-3.6-7.5-5.7-12.3-5.7H203c-6.8 0-10.5 7.9-6.1 13.1L459.4 512 196.9 824.9A7.95 7.95 0 0 0 203 838h79.8c4.7 0 9.2-2.1 12.3-5.7l216.5-258.1 216.6 258.1c3 3.6 7.5 5.7 12.3 5.7h79.8c6.8 0 10.5-7.9 6.1-13.1L563.8 512z" fill="currentColor"/></svg>
              关闭
            </button>
          </div>
        </div>

        <!-- 上传视图 -->
        <div v-if="activeView === 'upload'" class="pa-upload-view">
          <div class="pa-upload-content">
            <div class="pa-upload-title">上传题目图片</div>
            <div class="pa-upload-subtitle">支持代码截图、手写笔记、题目照片等格式，最大 20MB</div>

            <div
              v-if="!previewUrl"
              class="pa-dropzone"
              :class="{ 'is-dragging': isDragging }"
              @drop="onDrop"
              @dragover="onDragOver"
              @dragleave="onDragLeave"
              @click="fileInputRef?.click()"
            >
              <div class="pa-dropzone-icon">
                <svg viewBox="0 0 1024 1024" width="64" height="64"><path d="M85.333333 727.466667a32 32 0 0 1 32 32c0 60.842667 12.373333 95.146667 32.213334 114.986666 17.365333 17.365333 45.824 29.013333 93.44 31.616l21.546666 0.597334 3.242667 0.170666a32 32 0 0 1 0 63.658667l-3.242667 0.170667-12.458666-0.170667c-61.525333-1.578667-112.384-15.402667-147.797334-50.773333C66.56 881.92 53.333333 826.624 53.333333 759.466667a32 32 0 0 1 32-32zM938.666667 727.466667a32 32 0 0 1 32 32c0 67.157333-13.226667 122.496-50.944 160.256-37.76 37.717333-93.098667 50.944-160.256 50.944a32 32 0 0 1 0-64c60.842667 0 95.146667-12.373333 114.986666-32.213334 19.882667-19.84 32.213333-54.186667 32.213334-114.986666a32 32 0 0 1 32-32zM801.322667 653.056a109.909333 109.909333 0 0 1-10.026667 106.794667A115.285333 115.285333 0 0 1 695.424 810.666667h-367.36A114.602667 114.602667 0 0 1 230.4 756.949333a111.530667 111.530667 0 0 1-4.906667-110.165333L261.546667 576h506.410666l33.365334 77.056zM981.333333 480a32 32 0 0 1 0 64H42.666667a32 32 0 0 1 0-64h938.666666zM642.474667 384.085333c27.904 1.450667 52.352 22.997333 68.778666 61.013334l1.28 2.901333h-150.613333l5.674667-9.941333c20.437333-36.352 47.232-55.381333 74.88-53.973334zM373.333333 213.333333a96 96 0 1 1 0 192 96 96 0 0 1 0-192zM264.533333 53.333333a32 32 0 0 1 0 64c-60.842667 0-95.146667 12.373333-114.986666 32.213334-19.882667 19.84-32.213333 54.186667-32.213334 114.986666a32 32 0 0 1-64 0c0-67.157333 13.226667-122.496 50.944-160.256C142.08 66.56 197.376 53.333333 264.533333 53.333333zM759.466667 53.333333c67.157333 0 122.496 13.226667 160.256 50.944 37.717333 37.76 50.944 93.098667 50.944 160.256a32 32 0 0 1-64 0c0-60.842667-12.373333-95.146667-32.213334-114.986666-19.84-19.882667-54.186667-32.213333-114.986666-32.213334a32 32 0 0 1 0-64z" fill="currentColor"/></svg>
              </div>
              <div class="pa-dropzone-text">点击上传 或 拖拽图片到此处</div>
              <div class="pa-dropzone-hint">支持 JPG、PNG、GIF、BMP、WebP 等格式</div>
            </div>

            <div v-else class="pa-preview-area">
              <div class="pa-preview-container">
                <img :src="previewUrl" class="pa-preview-img" alt="preview" />
                <div class="pa-preview-remove" @click.stop="removeImage">
                  <svg viewBox="0 0 1024 1024" width="14" height="14"><path d="M563.8 512l262.5-312.9c4.4-5.2.7-13.1-6.1-13.1h-79.8c-4.7 0-9.2 2.1-12.3 5.7L511.6 449.8 295.1 191.7c-3-3.6-7.5-5.7-12.3-5.7H203c-6.8 0-10.5 7.9-6.1 13.1L459.4 512 196.9 824.9A7.95 7.95 0 0 0 203 838h79.8c4.7 0 9.2-2.1 12.3-5.7l216.5-258.1 216.6 258.1c3 3.6 7.5 5.7 12.3 5.7h79.8c6.8 0 10.5-7.9 6.1-13.1L563.8 512z" fill="#fff"/></svg>
                </div>
              </div>
              <div class="pa-preview-info">
                <span class="pa-file-name">{{ selectedFile?.name }}</span>
                <span class="pa-file-size">{{ (selectedFile?.size / 1024 / 1024).toFixed(2) }} MB</span>
              </div>
            </div>

            <input
              ref="fileInputRef"
              type="file"
              accept="image/*"
              class="pa-file-input"
              @change="onFileChange"
            />

            <div class="pa-input-section">
              <textarea
                v-model="inputText"
                class="pa-textarea"
                placeholder="请输入对图片的补充说明或具体问题（可选）..."
                rows="3"
              ></textarea>
            </div>

            <div class="pa-submit-area">
              <button
                class="pa-btn pa-btn-primary"
                :disabled="!selectedFile"
                @click="submitAnalysis"
              >
                <span>开始解析</span>
              </button>
            </div>
          </div>
        </div>

        <!-- 解析中视图 -->
        <div v-else-if="activeView === 'analyzing'" class="pa-analyzing-view">
          <div class="pa-analyzing-stage">
            <!-- 图片居中显示，动效层仅覆盖图片区域 -->
            <div class="pa-analyzing-image-wrap">
              <img :src="previewUrl" class="pa-analyzing-image" alt="analyzing" />
              <!-- 点阵动效层：玻璃质感 -->
              <div class="pa-dot-layer"></div>
              <!-- 闪光文字层 -->
              <div class="pa-shimmer-text">✨ AI 正在解析图片...</div>
            </div>
            <!-- 底部输入文本展示 -->
            <div v-if="inputText" class="pa-analyzing-question">
              <span class="pa-question-label">补充说明：</span>
              <span class="pa-question-text">{{ inputText }}</span>
            </div>
          </div>
        </div>

        <!-- 结果视图 -->
        <div v-else class="pa-result-view">
          <!-- 错误提示 -->
          <div v-if="errorMessage" class="pa-error-box">
            <div class="pa-error-icon">⚠️</div>
            <div class="pa-error-text">{{ errorMessage }}</div>
            <button class="pa-btn pa-btn-primary" @click="goToUpload">返回重新上传</button>
          </div>
          <!-- 正常结果：左图右文 -->
          <template v-else>
            <div class="pa-result-left">
              <div class="pa-result-image-wrap" @click="openImageZoom">
                <img
                  v-if="resultImageUrl && !imageLoadError"
                  :src="resultImageUrl"
                  class="pa-result-image"
                  alt="result"
                  @error="onImageError"
                />
                <div v-else class="pa-result-image-fallback">
                  <img
                    v-if="previewUrl"
                    :src="previewUrl"
                    class="pa-result-image"
                    alt="fallback"
                  />
                  <div v-else class="pa-result-image-placeholder">
                    <span>📷</span>
                    <p>图片加载失败</p>
                  </div>
                </div>
              </div>
              <!-- 补充说明 -->
              <div v-if="inputText" class="pa-result-question">
                <span class="pa-question-label">补充说明：</span>
                <span class="pa-question-text">{{ inputText }}</span>
              </div>
              <div class="pa-result-image-info">已解析图片</div>
            </div>
            <div class="pa-result-right">
              <div v-if="isFollowUpLoading" class="pa-loading-overlay">
                <div class="pa-loading-spinner"></div>
                <p>正在思考中...</p>
              </div>
              <div class="pa-result-header">
                <span class="pa-result-title">📋 解析结果</span>
              </div>
              <div 
                ref="resultContentRef" 
                class="pa-result-content" 
                :class="{ 'content-animate': isAnimating }"
              >
                <div v-html="renderMarkdown(resultContent)"></div>
              </div>
              <!-- 追问输入框 -->
              <div class="pa-followup-box">
                <input
                  v-model="followUpQuestion"
                  type="text"
                  placeholder="输入追问内容..."
                  class="pa-followup-input"
                  @keyup.enter="submitFollowUp"
                />
                <button
                  class="pa-btn pa-btn-primary"
                  :disabled="isFollowUpLoading"
                  @click="submitFollowUp"
                >
                  {{ isFollowUpLoading ? '回答中...' : '再次询问' }}
                </button>
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>

    <!-- 图片放大预览 -->
    <Teleport to="body">
      <div v-if="imageZoomVisible" class="pa-image-zoom-overlay" @click="closeImageZoom">
        <img
          :src="resultImageUrl || previewUrl"
          class="pa-image-zoom-img"
          alt="zoom"
          @click.stop
        />
        <div class="pa-image-zoom-close" @click="closeImageZoom">×</div>
      </div>
    </Teleport>
  </Teleport>
</template>

<style scoped>
.photo-analysis-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(15, 23, 42, 0.5);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: pa-fade-in 0.25s ease;
}

@keyframes pa-fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

.photo-analysis-container {
  width: 92vw;
  max-width: 1200px;
  height: 92vh;
  max-height: 860px;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-brand);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: pa-slide-up 0.3s ease;
}

@keyframes pa-slide-up {
  from { transform: translateY(20px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

/* ===== 顶部标题栏 ===== */
.pa-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  border-bottom: 1px solid var(--border-color);
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-hv) 100%);
  color: #fff;
  flex-shrink: 0;
}

.pa-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.pa-logo {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: var(--radius-md);
  color: #fff;
}

.pa-title {
  font-size: 18px;
  font-weight: 600;
  color: #fff;
}

.pa-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pa-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: none;
  border-radius: var(--radius-md);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  font-weight: 500;
}

.pa-btn-close {
  background: rgba(255, 255, 255, 0.2);
  color: #fff;
}

.pa-btn-close:hover {
  background: rgba(255, 77, 79, 0.8);
}

.pa-btn-text {
  background: rgba(255, 255, 255, 0.2);
  color: #fff;
}

.pa-btn-text:hover {
  background: rgba(255, 255, 255, 0.3);
}

/* ===== 上传视图 ===== */
.pa-upload-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px 24px;
  overflow-y: auto;
}

.pa-upload-content {
  width: 100%;
  max-width: 520px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.pa-upload-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-title);
  text-align: center;
}

.pa-upload-subtitle {
  font-size: 14px;
  color: var(--text-gray);
  text-align: center;
}

.pa-dropzone {
  border: 2px dashed var(--border-color);
  border-radius: var(--radius-lg);
  padding: 48px 24px;
  text-align: center;
  cursor: pointer;
  transition: all 0.25s;
  background: var(--bg-page);
}

.pa-dropzone:hover {
  border-color: var(--primary);
  background: var(--primary-light);
}

.pa-dropzone.is-dragging {
  border-color: var(--primary);
  background: var(--primary-light);
  transform: scale(1.02);
}

.pa-dropzone-icon {
  color: var(--primary);
  margin-bottom: 16px;
  display: flex;
  justify-content: center;
}

.pa-dropzone-text {
  font-size: 16px;
  font-weight: 500;
  color: var(--text-title);
  margin-bottom: 8px;
}

.pa-dropzone-hint {
  font-size: 13px;
  color: var(--text-gray);
}

.pa-preview-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.pa-preview-container {
  position: relative;
  display: inline-block;
  border-radius: var(--radius-md);
  overflow: hidden;
  box-shadow: var(--shadow-normal);
}

.pa-preview-img {
  max-width: 320px;
  max-height: 240px;
  display: block;
  object-fit: contain;
  background: var(--bg-page);
}

.pa-preview-remove {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 24px;
  height: 24px;
  background: rgba(0, 0, 0, 0.6);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.2s;
}

.pa-preview-remove:hover {
  background: rgba(245, 108, 108, 0.9);
}

.pa-preview-info {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  color: var(--text-gray);
}

.pa-file-name {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pa-file-input {
  display: none;
}

.pa-input-section {
  width: 100%;
}

.pa-textarea {
  width: 100%;
  padding: 12px 16px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 14px;
  font-family: inherit;
  background: var(--bg-input);
  color: var(--text-body);
  resize: vertical;
  outline: none;
  transition: border-color 0.2s;
  line-height: 1.6;
}

.pa-textarea:focus {
  border-color: var(--primary);
}

.pa-textarea::placeholder {
  color: var(--text-gray);
}

.pa-submit-area {
  display: flex;
  justify-content: center;
}

.pa-btn-primary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 48px;
  background: var(--grad-primary);
  color: #fff;
  font-size: 15px;
  font-weight: 500;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.2s;
  min-width: 160px;
}

.pa-btn-primary:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
  box-shadow: var(--shadow-brand);
}

.pa-btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ===== 解析中视图 ===== */
.pa-analyzing-view {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-page);
  overflow: hidden;
}

.pa-analyzing-stage {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 28px;
  max-width: 560px;
  width: 100%;
  padding: 20px;
}

/* 点阵动效层：玻璃质感，仅覆盖图片区域（来自 1.html） */
.pa-dot-layer {
  position: absolute;
  inset: 0;
  background-image: radial-gradient(rgba(184, 184, 184, 0.7) 2px, transparent 2px);
  background-size: 24px 24px;
  mask-image: linear-gradient(90deg, #000 0%, #000 45%, rgba(0, 0, 0, 0.12) 85%, transparent 100%);
  -webkit-mask-image: linear-gradient(90deg, #000 0%, #000 45%, rgba(0, 0, 0, 0.12) 85%, transparent 100%);
  animation: pa-dot-wave 3s ease-in-out infinite;
  pointer-events: none;
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(2px);
  z-index: 1;
}

@keyframes pa-dot-wave {
  0%, 100% {
    opacity: 0.4;
  }
  50% {
    opacity: 1;
  }
}

/* 闪光文字层：居中显示在图片区域 */
.pa-shimmer-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 1.5rem;
  font-weight: bold;
  background: linear-gradient(90deg, #00f, #0ff, #00f);
  background-size: 200% auto;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  animation: pa-shimmer 2s linear infinite;
  white-space: nowrap;
  pointer-events: none;
  text-shadow: 0 0 30px rgba(0, 255, 255, 0.6);
  z-index: 2;
}

@keyframes pa-shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.pa-analyzing-image-wrap {
  position: relative;
  display: inline-block;
  border-radius: var(--radius-lg);
  overflow: hidden;
  box-shadow: var(--shadow-normal);
  max-width: 480px;
  max-height: 380px;
  background: var(--bg-card);
}

.pa-analyzing-image {
  display: block;
  max-width: 480px;
  max-height: 380px;
  object-fit: contain;
  filter: brightness(0.65);
}

.pa-analyzing-question {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 12px 20px;
  background: rgba(255, 255, 255, 0.85);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  max-width: 480px;
  width: 100%;
  backdrop-filter: blur(4px);
}

.dark .pa-analyzing-question {
  background: rgba(30, 30, 30, 0.85);
}

.pa-question-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--primary);
  flex-shrink: 0;
}

.pa-question-text {
  font-size: 14px;
  color: var(--text-body);
  line-height: 1.6;
  word-break: break-word;
}

/* ===== 结果视图 ===== */
.pa-result-view {
  flex: 1;
  display: flex;
  overflow: hidden;
  background: var(--bg-page);
}

.pa-error-box {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 40px;
}

.pa-error-icon {
  font-size: 48px;
}

.pa-error-text {
  font-size: 16px;
  color: var(--main-delete);
  text-align: center;
  line-height: 1.6;
}

.pa-result-left {
  width: 42%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px;
  border-right: 1px solid var(--border-color);
  background: var(--bg-card);
  flex-shrink: 0;
  gap: 12px;
}

.pa-result-image-wrap {
  position: relative;
  cursor: zoom-in;
  border-radius: var(--radius-md);
  overflow: hidden;
  transition: transform 0.2s ease;
}

.pa-result-image-wrap:hover {
  transform: scale(1.02);
}

.pa-result-image {
  max-width: 100%;
  max-height: calc(100% - 60px);
  object-fit: contain;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-normal);
  display: block;
}

.pa-result-image-fallback {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.pa-result-image-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: var(--text-gray);
  gap: 12px;
}

.pa-result-image-placeholder span {
  font-size: 48px;
}

.pa-result-image-placeholder p {
  font-size: 14px;
  margin: 0;
}

.pa-result-image-info {
  font-size: 13px;
  color: var(--text-gray);
}

.pa-result-question {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 16px;
  background: var(--bg-page);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  max-width: 100%;
  width: 100%;
}

.pa-result-right {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}

.pa-result-header {
  padding: 16px 24px;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-card);
  flex-shrink: 0;
}

.pa-result-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--primary);
}

.pa-result-content {
  flex: 1;
  padding: 20px 24px;
  overflow-y: auto;
  min-height: 0;
}

.pa-result-content::-webkit-scrollbar {
  width: 6px;
}

.pa-result-content::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 3px;
}

/* 内容更新动画 */
.content-animate {
  animation: fadeInUp 0.5s ease-out;
}

@keyframes fadeInUp {
  0% {
    opacity: 0;
    transform: translateY(10px);
  }
  100% {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 加载动画 */
.pa-loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.9);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 10;
}

.dark .pa-loading-overlay {
  background: rgba(30, 41, 59, 0.9);
}

.pa-loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--border-color);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-bottom: 12px;
}

.pa-loading-overlay p {
  color: var(--text-gray);
  font-size: 14px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* ===== 追问输入框样式 ===== */
.pa-followup-box {
  display: flex;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid var(--border-color);
  background: var(--bg-card);
  flex-shrink: 0;
}

.pa-followup-input {
  flex: 1;
  padding: 10px 16px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 14px;
  background: var(--bg-input);
  color: var(--text-body);
  outline: none;
  transition: border-color 0.2s;
}

.pa-followup-input:focus {
  border-color: var(--primary);
}

.pa-followup-input::placeholder {
  color: var(--text-gray);
}

/* ===== Markdown 内容样式 ===== */
.pa-md-content {
  font-size: 14px;
  line-height: 1.75;
  color: var(--text-body);
  word-break: break-word;
}

.pa-md-content h2,
.pa-md-content h3,
.pa-md-content h4 {
  margin: 12px 0 8px;
  font-weight: 600;
  color: var(--text-title);
}

.pa-md-content h2 { font-size: 16px; }
.pa-md-content h3 { font-size: 15px; }
.pa-md-content h4 { font-size: 14px; }

.pa-md-content p {
  margin: 8px 0;
}

.pa-md-content strong {
  color: var(--primary);
  font-weight: 600;
}

.pa-md-content em {
  font-style: italic;
}

.pa-md-content ul,
.pa-md-content ol {
  padding-left: 20px;
  margin: 8px 0;
}

.pa-md-content li {
  margin: 4px 0;
}

.pa-code-block {
  background: var(--bg-page);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 12px 16px;
  margin: 12px 0;
  overflow-x: auto;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre;
  color: var(--text-body);
}

.pa-inline-code {
  background: var(--primary-light);
  color: var(--primary);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
}

.pa-md-content hr {
  border: none;
  border-top: 1px solid var(--border-color);
  margin: 16px 0;
}

/* ===== 夜间模式适配 ===== */
.dark .pa-dropzone {
  background: var(--primary-light);
}

.dark .pa-code-block {
  background: var(--primary-light);
  color: var(--text-body);
}

.dark .pa-inline-code {
  background: var(--primary-light);
  color: var(--primary);
}

.dark .pa-dot-layer {
  background-image: radial-gradient(rgba(85, 85, 85, 0.7) 2px, transparent 2px);
}

.dark .pa-analyzing-image-wrap {
  background: #2a2a2a;
}

/* ===== 图片放大预览 ===== */
.pa-image-zoom-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.85);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  z-index: 99999;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: pa-fade-in 0.2s ease;
  cursor: zoom-out;
}

.pa-image-zoom-img {
  max-width: 90vw;
  max-height: 90vh;
  object-fit: contain;
  border-radius: var(--radius-md);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
  cursor: default;
}

.pa-image-zoom-close {
  position: absolute;
  top: 24px;
  right: 24px;
  width: 40px;
  height: 40px;
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
  font-size: 28px;
  line-height: 40px;
  text-align: center;
  border-radius: 50%;
  cursor: pointer;
  transition: background 0.2s ease;
}

.pa-image-zoom-close:hover {
  background: rgba(255, 255, 255, 0.3);
}
</style>
