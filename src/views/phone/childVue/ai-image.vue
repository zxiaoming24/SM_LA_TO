<!-- 移动端 AI 图解页面 -->
<script setup>
import { ref, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { analyzeImageApi } from '@/api/mainApi/photoAnalysis'

const router = useRouter()

const activeView = ref('upload')
const inputText = ref('')
const selectedFile = ref(null)
const previewUrl = ref('')
const resultContent = ref('')
const resultImageUrl = ref('')
const errorMessage = ref('')
const imageLoadError = ref(false)
const followUpQuestion = ref('')
const isFollowUpLoading = ref(false)
const sessionId = ref('')
const resultContentRef = ref(null)
const isAnimating = ref(false)
const fileInputRef = ref(null)
const cameraInputRef = ref(null)
const showActionSheet = ref(false)
const imageZoomVisible = ref(false)

const getUserId = () => {
  try {
    const user = JSON.parse(localStorage.getItem('loginUser') || '{}')
    return user.user_id || user.id || ''
  } catch {
    return ''
  }
}

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
  if (fileInputRef.value) fileInputRef.value.value = ''
  if (cameraInputRef.value) cameraInputRef.value.value = ''
}

const goBack = () => {
  router.back()
}

const onChooseSource = () => {
  showActionSheet.value = true
}

const onActionSelect = (action) => {
  showActionSheet.value = false
  if (action.name === '拍照') {
    cameraInputRef.value?.click()
  } else if (action.name === '从相册选择') {
    fileInputRef.value?.click()
  }
}

const onFileChange = (event) => {
  const file = event.target.files[0]
  if (file) handleFile(file)
}

const handleFile = (file) => {
  if (!file.type.startsWith('image/')) {
    showToast('请选择图片文件')
    return
  }
  if (file.size > 20 * 1024 * 1024) {
    showToast('图片大小不能超过 20MB')
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
  if (fileInputRef.value) fileInputRef.value.value = ''
  if (cameraInputRef.value) cameraInputRef.value.value = ''
}

const submitAnalysis = async () => {
  if (!selectedFile.value) {
    showToast('请上传图片')
    return
  }
  const userId = getUserId()
  if (!userId) {
    showToast('请先登录')
    return
  }

  activeView.value = 'analyzing'
  errorMessage.value = ''
  resultContent.value = ''
  resultImageUrl.value = ''
  imageLoadError.value = false
  await nextTick()
  window.scrollTo({ top: 0, behavior: 'smooth' })

  const minDelay = new Promise(resolve => setTimeout(resolve, 2000))

  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    formData.append('user_id', userId)
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
    showToast('请输入问题')
    return
  }
  isFollowUpLoading.value = true
  resultContent.value = ''
  try {
    const formData = new FormData()
    formData.append('user_id', getUserId())
    formData.append('question', followUpQuestion.value)
    formData.append('session_id', sessionId.value)
    const res = await analyzeImageApi(formData)
    if (res.success) {
      isAnimating.value = true
      setTimeout(() => { isAnimating.value = false }, 500)
      resultContent.value = res.analysis || res.answer || ''
      followUpQuestion.value = ''
      if (resultContentRef.value) resultContentRef.value.scrollTop = 0
    } else {
      showToast(`追问失败：${res.detail || res.message || '未知错误'}`)
    }
  } catch (err) {
    showToast(`网络错误：${err.message || '请检查网络连接'}`)
  } finally {
    isFollowUpLoading.value = false
  }
}

const onImageError = () => { imageLoadError.value = true }

const renderMarkdown = (text) => {
  if (!text) return ''
  let html = text
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="pa-code-block"><code>$2</code></pre>')
  html = html.replace(/`([^`]+)`/g, '<code class="pa-inline-code">$1</code>')
  html = html.replace(/^### (.+)$/gm, '<h4>$1</h4>')
  html = html.replace(/^## (.+)$/gm, '<h3>$1</h3>')
  html = html.replace(/^# (.+)$/gm, '<h2>$1</h2>')
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')
  html = html.replace(/^---$/gm, '<hr>')
  html = html.replace(/^- (.+)$/gm, '<li>$1</li>')
  html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>')
  html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
  html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ol>$1</ol>')
  html = html.replace(/\n\n/g, '</p><p>')
  html = html.replace(/\n/g, '<br>')
  return `<div class="pa-md-content"><p>${html}</p></div>`
}
</script>

<template>
  <div class="phone-ai-image">
    <!-- 顶部导航栏 -->
    <div class="mobile-header">
      <div class="header-left" @click="goBack">
        <van-icon name="arrow-left" size="20" />
      </div>
      <div class="header-title">AI 图解</div>
      <div class="header-right">
        <van-icon
          v-if="activeView !== 'upload'"
          name="replay"
          size="20"
          @click="resetState"
        />
      </div>
    </div>

    <!-- ========== 上传视图 ========== -->
    <div v-if="activeView === 'upload'" class="upload-view">
      <!-- 顶部装饰 -->
      <div class="upload-hero">
        <div class="hero-icon-wrap">
          <van-icon name="photograph" size="40" />
        </div>
        <div class="hero-title">上传题目图片</div>
        <div class="hero-subtitle">拍照或从相册选择，AI 为你智能解析</div>
      </div>

      <!-- 图片预览 -->
      <div v-if="previewUrl" class="preview-area">
        <div class="preview-container">
          <img :src="previewUrl" class="preview-img" alt="preview" />
          <div class="preview-remove" @click.stop="removeImage">
            <van-icon name="cross" size="12" color="#fff" />
          </div>
          <div class="preview-badge">
            <van-icon name="success" size="12" color="#fff" />
            <span>已选择</span>
          </div>
        </div>
        <div class="preview-info">
          <span class="file-name">{{ selectedFile?.name }}</span>
          <span class="file-size">{{ (selectedFile?.size / 1024 / 1024).toFixed(2) }} MB</span>
        </div>
      </div>

      <!-- 上传按钮 -->
      <div v-else class="upload-buttons">
        <div class="upload-btn" @click="onChooseSource">
          <div class="upload-btn-icon">
            <van-icon name="photo-o" size="44" />
          </div>
          <span class="upload-btn-text">拍照 / 选择图片</span>
          <span class="upload-btn-hint">支持 JPG、PNG 等格式，最大 20MB</span>
        </div>
      </div>

      <!-- 补充说明 -->
      <div class="input-section">
        <div class="input-label">
          <van-icon name="edit" size="14" />
          <span>补充说明</span>
        </div>
        <textarea
          v-model="inputText"
          class="mobile-textarea"
          placeholder="对图片的补充说明或具体问题（可选）..."
          rows="2"
        ></textarea>
      </div>

      <!-- 开始解析 -->
      <div class="submit-area">
        <van-button
          type="primary"
          block
          round
          :disabled="!selectedFile"
          @click="submitAnalysis"
          class="submit-btn"
        >
          <van-icon name="search" size="18" />
          开始解析
        </van-button>
      </div>

      <!-- 隐藏的文件输入 -->
      <input ref="fileInputRef" type="file" accept="image/*" style="display: none" @change="onFileChange" />
      <input ref="cameraInputRef" type="file" accept="image/*" capture="environment" style="display: none" @change="onFileChange" />
    </div>

    <!-- ========== 解析中视图 ========== -->
    <div v-else-if="activeView === 'analyzing'" class="analyzing-view">
      <div class="analyzing-stage">
        <div class="analyzing-image-wrap">
          <img :src="previewUrl" class="analyzing-image" alt="analyzing" />
          <div class="dot-layer"></div>
          <div class="shimmer-text">AI 正在解析图片...</div>
        </div>
        <div class="analyzing-tips">
          <div class="tip-dot"></div>
          <span>正在识别图片内容并生成解析...</span>
        </div>
        <div v-if="inputText" class="analyzing-question">
          <span class="question-label">补充说明</span>
          <span class="question-text">{{ inputText }}</span>
        </div>
      </div>
    </div>

    <!-- ========== 结果视图 ========== -->
    <div v-else class="result-view">
      <!-- 错误提示 -->
      <div v-if="errorMessage" class="error-box">
        <div class="error-icon-wrap">
          <van-icon name="warning-o" size="48" />
        </div>
        <div class="error-text">{{ errorMessage }}</div>
        <van-button type="primary" round @click="resetState">返回重新上传</van-button>
      </div>

      <!-- 正常结果 -->
      <template v-else>
        <!-- 图片区域 -->
        <div class="result-image-section">
          <div class="result-image-label">
            <van-icon name="photo-o" size="14" />
            <span>已解析图片</span>
          </div>
          <div class="result-image-wrap" @click="imageZoomVisible = true">
            <img
              v-if="resultImageUrl && !imageLoadError"
              :src="resultImageUrl"
              class="result-image"
              alt="result"
              @error="onImageError"
            />
            <img
              v-else-if="previewUrl"
              :src="previewUrl"
              class="result-image"
              alt="fallback"
            />
            <div v-else class="image-placeholder">
              <van-icon name="photo-o" size="48" color="var(--text-gray)" />
              <p>图片加载失败</p>
            </div>
          </div>
          <div v-if="inputText" class="result-question">
            <span class="question-label">补充说明</span>
            <span class="question-text">{{ inputText }}</span>
          </div>
        </div>

        <!-- 解析结果 -->
        <div class="result-content-section">
          <div class="result-header">
            <div class="result-header-icon">
              <van-icon name="notes-o" size="16" />
            </div>
            <span class="result-title">解析结果</span>
          </div>

          <!-- 加载遮罩 -->
          <div v-if="isFollowUpLoading" class="loading-overlay">
            <van-loading type="spinner" color="var(--primary)" />
            <p>正在思考中...</p>
          </div>

          <div
            ref="resultContentRef"
            class="result-content"
            :class="{ 'content-animate': isAnimating }"
          >
            <div v-html="renderMarkdown(resultContent)"></div>
          </div>
        </div>
      </template>
    </div>

    <!-- 追问输入（固定底部） -->
    <div v-if="activeView === 'result' && !errorMessage" class="followup-box">
      <van-icon name="comment-o" size="18" color="var(--text-gray)" />
      <input
        v-model="followUpQuestion"
        type="text"
        placeholder="输入追问内容..."
        class="followup-input"
        @keyup.enter="submitFollowUp"
      />
      <van-button
        type="primary"
        round
        :disabled="isFollowUpLoading"
        @click="submitFollowUp"
        class="followup-btn"
      >
        {{ isFollowUpLoading ? '回答中' : '追问' }}
      </van-button>
    </div>

    <!-- 选择图片来源 -->
    <van-action-sheet
      v-model:show="showActionSheet"
      :actions="[
        { name: '拍照', icon: 'photograph' },
        { name: '从相册选择', icon: 'photo-o' }
      ]"
      cancel-text="取消"
      @select="onActionSelect"
    />

    <!-- 图片放大预览 -->
    <van-image-preview
      v-model:show="imageZoomVisible"
      :images="[resultImageUrl || previewUrl]"
      closeable
    />
  </div>
</template>

<style scoped>
.phone-ai-image {
  min-height: 100vh;
  background: var(--bg-page);
  padding-bottom: calc(70px + env(safe-area-inset-bottom));
}

/* ===== 顶部导航栏 ===== */
.mobile-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-left,
.header-right {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border-radius: 50%;
  transition: background 0.2s;
  color: var(--text-title);
}

.header-left:active,
.header-right:active {
  background: var(--bg-hover);
}

.header-title {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-title);
  letter-spacing: 0.5px;
}

/* ===== 上传视图 ===== */
.upload-view {
  padding: 20px 16px;
}

/* 顶部装饰区域 */
.upload-hero {
  text-align: center;
  padding: 15px 0 20px;
}

.hero-icon-wrap {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 72px;
  height: 72px;
  border-radius: 20px;
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-hv, var(--primary)) 100%);
  color: #fff;
  margin-bottom: 16px;
  box-shadow: 0 8px 24px rgba(45, 125, 219, 0.25);
}

.hero-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-title);
  margin-bottom: 3px;
}

.hero-subtitle {
  font-size: 13px;
  color: var(--text-gray);
}

/* 上传按钮 */
.upload-buttons {
  margin-bottom: 20px;
}

.upload-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 36px 24px;
  border: 2px dashed var(--border-color);
  border-radius: 16px;
  background: var(--bg-card);
  cursor: pointer;
  transition: all 0.3s;
  position: relative;
  overflow: hidden;
}

.upload-btn::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, var(--primary-light), transparent 60%);
  opacity: 0;
  transition: opacity 0.3s;
}

.upload-btn:active {
  border-color: var(--primary);
  transform: scale(0.98);
}

.upload-btn:active::before {
  opacity: 1;
}

.upload-btn-icon {
  color: var(--primary);
  position: relative;
  z-index: 1;
}

.upload-btn-text {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-title);
  position: relative;
  z-index: 1;
}

.upload-btn-hint {
  font-size: 12px;
  color: var(--text-gray);
  position: relative;
  z-index: 1;
}

/* 预览区域 */
.preview-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.preview-container {
  position: relative;
  display: inline-block;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}

.preview-img {
  max-width: 100%;
  max-height: 240px;
  display: block;
  object-fit: contain;
  background: var(--bg-page);
}

.preview-remove {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 26px;
  height: 26px;
  background: rgba(0, 0, 0, 0.55);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.2s;
}

.preview-remove:active {
  background: rgba(245, 108, 108, 0.9);
}

.preview-badge {
  position: absolute;
  bottom: 8px;
  left: 8px;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: rgba(45, 125, 219, 0.85);
  border-radius: 12px;
  font-size: 11px;
  color: #fff;
}

.preview-info {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: var(--text-gray);
  padding: 6px 12px;
  background: var(--bg-card);
  border-radius: 8px;
  border: 1px solid var(--border-color);
}

.file-name {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 输入区域 */
.input-section {
  margin-bottom: 20px;
}

.input-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-title);
  margin-bottom: 8px;
}

.input-label .van-icon {
  color: var(--primary);
}

.mobile-textarea {
  width: 100%;
  padding: 12px 16px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  font-size: 16px;
  font-family: inherit;
  background: var(--bg-card);
  color: var(--text-body);
  resize: none;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
  line-height: 1.6;
  box-sizing: border-box;
}

.mobile-textarea:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(45, 125, 219, 0.1);
}

.mobile-textarea::placeholder {
  color: var(--text-gray);
}

.submit-area {
  margin-top: 4px;
}

.submit-btn {
  font-weight: 600;
  font-size: 16px;
  height: 48px;
  letter-spacing: 1px;
}

/* ===== 解析中视图 ===== */
.analyzing-view {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 70vh;
  padding: 20px 16px;
}

.analyzing-stage {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  width: 100%;
  max-width: 400px;
}

.analyzing-image-wrap {
  position: relative;
  display: inline-block;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
  max-width: 100%;
  background: var(--bg-card);
}

.analyzing-image {
  display: block;
  width: 100%;
  max-height: 50vh;
  object-fit: contain;
  filter: brightness(0.65);
}


.dot-layer {
  position: absolute;
  inset: 0;
  background-image: radial-gradient(rgba(184, 184, 184, 0.7) 2px, transparent 2px);
  background-size: 24px 24px;
  mask-image: linear-gradient(90deg, #000 0%, #000 45%, rgba(0, 0, 0, 0.12) 85%, transparent 100%);
  -webkit-mask-image: linear-gradient(90deg, #000 0%, #000 45%, rgba(0, 0, 0, 0.12) 85%, transparent 100%);
  animation: dot-wave 3s ease-in-out infinite;
  pointer-events: none;
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(2px);
  z-index: 1;
}

@keyframes dot-wave {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}

.shimmer-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 1.2rem;
  font-weight: bold;
  background: linear-gradient(90deg, #00f, #0ff, #00f);
  background-size: 200% auto;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  animation: shimmer 2s linear infinite;
  white-space: nowrap;
  pointer-events: none;
  text-shadow: 0 0 30px rgba(0, 255, 255, 0.6);
  z-index: 2;
}

@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.analyzing-tips {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-gray);
}

.tip-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--primary);
  animation: tip-pulse 1.5s ease-in-out infinite;
}

@keyframes tip-pulse {
  0%, 100% { opacity: 0.3; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1.2); }
}

.analyzing-question {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px 16px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  width: 100%;
}

.question-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--primary);
}

.question-text {
  font-size: 14px;
  color: var(--text-body);
  line-height: 1.6;
  word-break: break-word;
}

/* ===== 结果视图 ===== */
.result-view {
  display: flex;
  flex-direction: column;
}

.error-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 60px 24px;
}

.error-icon-wrap {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: rgba(245, 108, 108, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
}

.error-text {
  font-size: 15px;
  color: var(--main-delete);
  text-align: center;
  line-height: 1.6;
}

.result-image-section {
  padding: 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  background: var(--bg-card);
  border-radius: 0 0 16px 16px;
  margin: 0 0 12px;
}

.result-image-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-gray);
  align-self: flex-start;
  padding: 4px 10px;
  background: var(--bg-page);
  border-radius: 6px;
}

.result-image-wrap {
  cursor: zoom-in;
  border-radius: 10px;
  overflow: hidden;
}

.result-image {
  max-width: 100%;
  max-height: 200px;
  object-fit: contain;
  border-radius: 10px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  display: block;
}

.image-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px;
  color: var(--text-gray);
  gap: 8px;
}

.image-placeholder p {
  font-size: 13px;
  margin: 0;
}

.result-question {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 14px;
  background: var(--bg-page);
  border-radius: 10px;
  width: 100%;
}

.result-content-section {
  position: relative;
  background: var(--bg-card);
  margin: 0 16px 12px;
  border-radius: 16px;
  border: 1px solid var(--border-color);
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.result-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border-color);
  background: linear-gradient(135deg, var(--primary-light), transparent);
}

.result-header-icon {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: var(--primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
}

.result-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-title);
}

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.92);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 10;
  gap: 12px;
  backdrop-filter: blur(2px);
}

.dark .loading-overlay {
  background: rgba(30, 41, 59, 0.92);
}

.loading-overlay p {
  color: var(--text-gray);
  font-size: 14px;
  margin: 0;
}

.result-content {
  padding: 16px;
  min-height: 200px;
}

.content-animate {
  animation: fadeInUp 0.5s ease-out;
}

@keyframes fadeInUp {
  0% { opacity: 0; transform: translateY(10px); }
  100% { opacity: 1; transform: translateY(0); }
}

/* 追问输入 */
.followup-box {
  position: fixed;
  bottom: 50px;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: var(--bg-card);
  border-top: 1px solid var(--border-color);
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.06);
  z-index: 100;
}

.followup-input {
  flex: 1;
  padding: 8px 4px;
  border: none;
  font-size: 16px;
  background: transparent;
  color: var(--text-body);
  outline: none;
}

.followup-input::placeholder {
  color: var(--text-gray);
}

.followup-btn {
  flex-shrink: 0;
  min-width: 72px;
  height: 36px;
  font-size: 14px;
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
  border-radius: 10px;
  padding: 12px;
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

/* 夜间模式 */
.dark .dot-layer {
  background-image: radial-gradient(rgba(85, 85, 85, 0.7) 2px, transparent 2px);
}
</style>
