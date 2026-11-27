<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const userId = defineProps({
  userId: { type: String, default: '' }
})

const explainBtnVisible = ref(false)
const explainBtnLeft = ref(0)
const explainBtnTop = ref(0)
const lifeCaseBtnVisible = ref(false)
const lifeCaseBtnLeft = ref(0)
const lifeCaseBtnTop = ref(0)
const popoverVisible = ref(false)
const popoverLeft = ref(0)
const popoverTop = ref(0)
const explanation = ref('')
const keywords = ref([])
const isLoading = ref(false)
const selectedText = ref('')
const isStreaming = ref(false)
const popoverTitle = ref('AI 解释')

const markdownToHtml = (md) => {
  if (!md) return ''
  let html = md
  html = html.replace(/&/g, '&amp;')
  html = html.replace(/</g, '&lt;')
  html = html.replace(/>/g, '&gt;')
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>')
  html = html.replace(/^---$/gm, '<hr>')
  html = html.replace(/^&gt;\s+(.*)$/gm, '<blockquote>$1</blockquote>')
  html = html.replace(/^######\s+(.*)$/gm, '<h6>$1</h6>')
  html = html.replace(/^#####\s+(.*)$/gm, '<h5>$1</h5>')
  html = html.replace(/^####\s+(.*)$/gm, '<h4>$1</h4>')
  html = html.replace(/^###\s+(.*)$/gm, '<h3>$1</h3>')
  html = html.replace(/^##\s+(.*)$/gm, '<h2>$1</h2>')
  html = html.replace(/^#\s+(.*)$/gm, '<h1>$1</h1>')
  html = html.replace(/^[\s]*[-*]\s+(.*)$/gm, '<li>$1</li>')
  html = html.replace(/^\d+\.\s+(.*)$/gm, '<li>$1</li>')
  html = html.replace(/((?:<li>.*?<\/li>\n?)+)/g, '<ul>$1</ul>')
  const lines = html.split('\n')
  const out = []
  for (const line of lines) {
    const t = line.trim()
    if (!t) continue
    if (/^<(h[1-6]|ul|\/ul|li|blockquote|\/blockquote|hr|img|p|code|a)/.test(t)) {
      out.push(t)
    } else {
      out.push('<p>' + t + '</p>')
    }
  }
  html = out.join('\n')
  html = html.replace(/<p><ul>/g, '<ul>')
  html = html.replace(/<\/ul><\/p>/g, '</ul>')
  html = html.replace(/<p><li>/g, '<li>')
  html = html.replace(/<\/li><\/p>/g, '</li>')
  return html
}

const explanationHtml = computed(() => {
  return markdownToHtml(explanation.value)
})

const checkSelection = () => {
  const sel = window.getSelection()
  const text = sel.toString().trim()
  if (!text || text.length < 2) {
    explainBtnVisible.value = false
    lifeCaseBtnVisible.value = false
    popoverVisible.value = false
    return
  }
  selectedText.value = text
  const range = sel.getRangeAt(0)
  const rect = range.getBoundingClientRect()
  const btnWidth = 90
  const btnHeight = 30
  const gap = 8
  const totalWidth = btnWidth * 2 + gap
  const startX = Math.max(4, Math.min(rect.left + rect.width / 2 - totalWidth / 2, window.innerWidth - totalWidth - 4))
  const topY = rect.top - btnHeight - 8
  explainBtnLeft.value = startX
  explainBtnTop.value = topY
  explainBtnVisible.value = true
  lifeCaseBtnLeft.value = startX + btnWidth + gap
  lifeCaseBtnTop.value = topY
  lifeCaseBtnVisible.value = true
}

const handleMouseUp = () => {
  setTimeout(checkSelection, 100)
}

const readSSEStream = async (response) => {
  isLoading.value = false
  isStreaming.value = true
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let fullText = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n')
    buffer = parts.pop() || ''

    for (const line of parts) {
      if (line.startsWith('data: ')) {
        let data
        try {
          data = JSON.parse(line.slice(6))
        } catch {
          continue
        }
        if (data.type === 'chunk') {
          explanation.value += data.text
          fullText += data.text
        } else if (data.type === 'done') {
          explanation.value = data.text || fullText
          if (data.keywords && data.keywords.length) {
            keywords.value = data.keywords
          }
          isStreaming.value = false
        } else if (data.type === 'error') {
          explanation.value = data.text || '生成失败'
          isStreaming.value = false
        }
      }
    }
  }
  isStreaming.value = false
}

const openExplain = async () => {
  if (!selectedText.value || !userId.userId) return
  explainBtnVisible.value = false
  lifeCaseBtnVisible.value = false
  isLoading.value = true
  isStreaming.value = false
  explanation.value = ''
  keywords.value = []
  popoverVisible.value = true
  popoverTitle.value = 'AI 解释'

  const sel = window.getSelection()
  if (sel.rangeCount > 0) {
    const range = sel.getRangeAt(0)
    const rect = range.getBoundingClientRect()
    popoverLeft.value = Math.max(4, Math.min(rect.left, window.innerWidth - 420))
    popoverTop.value = rect.top - 10
  }

  const dummyNoteId = 'global'

  try {
    const response = await fetch(`/py/notes/${userId.userId}/${dummyNoteId}/explain-selection`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ selected_text: selectedText.value })
    })

    if (!response.ok) {
      throw new Error('请求失败')
    }

    await readSSEStream(response)
  } catch (e) {
    isLoading.value = false
    isStreaming.value = false
    explanation.value = '解释生成失败: ' + e.message
    console.error('AI解释失败:', e)
  }
}

const openLifeCase = async () => {
  if (!selectedText.value || !userId.userId) return
  explainBtnVisible.value = false
  lifeCaseBtnVisible.value = false
  isLoading.value = true
  isStreaming.value = false
  explanation.value = ''
  keywords.value = []
  popoverVisible.value = true
  popoverTitle.value = '生活案例'

  const sel = window.getSelection()
  if (sel.rangeCount > 0) {
    const range = sel.getRangeAt(0)
    const rect = range.getBoundingClientRect()
    popoverLeft.value = Math.max(4, Math.min(rect.left, window.innerWidth - 420))
    popoverTop.value = rect.top - 10
  }

  const lifeNoteId = 'globalLife'

  try {
    const response = await fetch(`/py/notes/${userId.userId}/${lifeNoteId}/life-case`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ selected_text: selectedText.value })
    })

    if (!response.ok) {
      throw new Error('请求失败')
    }

    await readSSEStream(response)
  } catch (e) {
    isLoading.value = false
    isStreaming.value = false
    explanation.value = '生活案例生成失败: ' + e.message
    console.error('生活案例失败:', e)
  }
}

const closePopover = () => {
  popoverVisible.value = false
  explainBtnVisible.value = false
  lifeCaseBtnVisible.value = false
  explanation.value = ''
  keywords.value = []
  isStreaming.value = false
}

onMounted(() => {
  document.addEventListener('mouseup', handleMouseUp)
})

onUnmounted(() => {
  document.removeEventListener('mouseup', handleMouseUp)
})
</script>

<template>
  <button
    v-if="explainBtnVisible"
    class="ai-explain-btn"
    :style="{ left: explainBtnLeft + 'px', top: explainBtnTop + 'px' }"
    @click="openExplain"
  >
    <img src="@/assets/logo/Logo.png" class="btn-logo" />
    AI 解释
  </button>

  <button
    v-if="lifeCaseBtnVisible"
    class="ai-explain-btn life-case-btn"
    :style="{ left: lifeCaseBtnLeft + 'px', top: lifeCaseBtnTop + 'px' }"
    @click="openLifeCase"
  >
    <svg class="btn-icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>
      <polyline points="9 22 9 12 15 12 15 22"/>
    </svg>
    生活案例
  </button>

  <div
    v-if="popoverVisible"
    class="ai-explain-popover"
    :style="{ left: popoverLeft + 'px', top: popoverTop + 'px' }"
  >
    <div class="pop-header" :class="{ 'life-case-header': popoverTitle === '生活案例' }">
      <div class="pop-header-left">
        <template v-if="popoverTitle === '生活案例'">
          <svg class="header-logo" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>
            <polyline points="9 22 9 12 15 12 15 22"/>
          </svg>
        </template>
        <template v-else>
          <img src="@/assets/logo/Logo.png" class="header-logo" />
        </template>
        <span>{{ popoverTitle }}</span>
      </div>
      <button class="close-btn" @click="closePopover">
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </button>
    </div>
    <div class="pop-body">
      <div v-if="isLoading" class="loading">
        <span class="spinner"></span>
        <span>AI 思考中...</span>
      </div>
      <template v-else>
        <div class="explanation-text" :class="{ streaming: isStreaming }">
        <span v-html="explanationHtml"></span><span v-if="isStreaming" class="cursor"></span>
      </div>
        <div v-if="keywords.length" class="keywords">
          <span v-for="kw in keywords" :key="kw" class="keyword" :class="{ 'keyword-life': popoverTitle === '生活案例' }">{{ kw }}</span>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.ai-explain-btn {
  position: fixed;
  z-index: 10000;
  background: var(--grad-primary);
  color: #fff;
  border: none;
  border-radius: 20px;
  padding: 6px 14px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: var(--shadow-brand);
  display: flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
  transition: all .2s;
}
.btn-logo {
  width: 18px;
  height: 18px;
}
.btn-icon {
  width: 16px;
  height: 16px;
}
.ai-explain-btn:hover {
  background: var(--primary-hv);
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(45, 125, 219, 0.45);
}
.ai-explain-btn:active {
  background: var(--primary-act);
}
.life-case-btn {
  background: linear-gradient(135deg, #E6A23C, #F97316);
}
.life-case-btn:hover {
  background: linear-gradient(135deg, #c77c0c, #E6A23C);
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(230, 162, 60, 0.45);
}
.life-case-btn:active {
  background: linear-gradient(135deg, #c77c0c, #c77c0c);
}

.ai-explain-popover {
  position: fixed;
  z-index: 10001;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  box-shadow: 0 8px 32px rgba(0,0,0,0.15);
  border: 1px solid var(--border-color);
  max-width: 420px;
  min-width: 260px;
  overflow: hidden;
}

.pop-header {
  background: var(--grad-primary);
  color: #fff;
  padding: 10px 14px;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.life-case-header {
  background: linear-gradient(135deg, #E6A23C, #F97316);
}

.pop-header-left {
  display: flex;
  align-items: center;
  gap: 6px;
}
.header-logo {
  width: 18px;
  height: 18px;
}

.pop-header .close-btn {
  background: none;
  border: none;
  color: rgba(255,255,255,0.8);
  cursor: pointer;
  padding: 2px;
  display: flex;
  align-items: center;
  border-radius: var(--radius-sm);
  transition: all 0.2s;
}
.pop-header .close-btn:hover {
  color: #fff;
  background: rgba(255,255,255,0.2);
}

.pop-body {
  padding: 14px;
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-body);
  max-height: 300px;
  overflow-y: auto;
}

.loading {
  text-align: center;
  padding: 20px 0;
  color: var(--text-gray);
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.spinner {
  display: inline-block;
  width: 18px;
  height: 18px;
  border: 2px solid var(--border-color);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin .6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.keywords {
  margin-top: 10px;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.keyword {
  background: var(--primary-light);
  color: var(--primary);
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
}

.keyword-life {
  background: rgba(230, 162, 60, 0.15);
  color: #E6A23C;
}

.explanation-text {
  white-space: pre-wrap;
}
.explanation-text.streaming {
  color: var(--text-body);
}
.explanation-text h1,
.explanation-text h2,
.explanation-text h3,
.explanation-text h4,
.explanation-text h5,
.explanation-text h6 {
  font-weight: 600;
  margin-top: 12px;
  margin-bottom: 6px;
  line-height: 1.4;
}
.explanation-text h1 { font-size: 18px; color: var(--text-title); }
.explanation-text h2 { font-size: 16px; color: var(--text-title); }
.explanation-text h3 { font-size: 15px; color: var(--text-body); }
.explanation-text h4 { font-size: 14px; color: var(--text-body); }
.explanation-text h5,
.explanation-text h6 { font-size: 13px; color: var(--text-body); }
.explanation-text p {
  margin: 4px 0;
  line-height: 1.7;
}
.explanation-text strong {
  font-weight: 600;
  color: var(--text-title);
}
.explanation-text em {
  font-style: italic;
}
.explanation-text code {
  background: var(--bg-card);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
  font-family: 'Monaco', 'Menlo', monospace;
  color: var(--primary);
  border: 1px solid var(--border-color);
}
.explanation-text ul {
  padding-left: 20px;
  margin: 6px 0;
}
.explanation-text li {
  margin: 4px 0;
  line-height: 1.6;
}
.explanation-text blockquote {
  border-left: 3px solid var(--primary);
  padding-left: 10px;
  margin: 8px 0;
  color: var(--text-gray);
  font-style: italic;
}
.explanation-text a {
  color: var(--primary);
  text-decoration: none;
}
.explanation-text a:hover {
  text-decoration: underline;
}
.explanation-text hr {
  border: none;
  border-top: 1px solid var(--border-color);
  margin: 12px 0;
}
.cursor {
  display: inline-block;
  width: 2px;
  height: 14px;
  background: var(--primary);
  margin-left: 2px;
  vertical-align: middle;
  animation: blink 0.8s infinite;
}
@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}
</style>
