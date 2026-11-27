<!-- 移动端对话页：资源生成模式（默认）+ 答疑解惑模式 -->
<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { showToast, showSuccessToast, showFailToast, showImagePreview } from 'vant'
import { useRouter } from 'vue-router'
import { findString } from '@/utils/findString.js'
import { saveSkip, isSkip, removeSkip } from '@/utils/skip.js'
import { postTextApi, getProgressApi, reCreateApi, aiHistoryApi, conflictApi } from '@/api/mainApi/aiAnswer.js'
import { smartBallChatApi } from '@/api/mainApi/smartBall.js'
import { connectSSE, disconnectSSE } from '@/api/mainApi/floatWindow.js'
import { ASR } from '@/utils/asr.js'
import { DigitalHuman } from '@/utils/digitalHuman.js'

const router = useRouter()

// ==================== 配置常量 ====================
const AVATAR_CONFIG = {
  serverUrl: import.meta.env.VITE_AVATAR_SERVER_URL,
  appId: import.meta.env.VITE_AVATAR_APP_ID,
  apiKey: import.meta.env.VITE_AVATAR_API_KEY,
  apiSecret: import.meta.env.VITE_AVATAR_API_SECRET,
  sceneId: import.meta.env.VITE_AVATAR_SCENE_ID,
}

const avatarOptions = [
  { value: '111260002', label: '女老师' },
  { value: '111264001', label: '男老师' },
]
const voiceOptions = [
  { value: 'x4_lingyuyan_oral', label: '聆小言' },
  { value: 'x4_lingxiaoyue_oral', label: '聆小月' },
  { value: 'x4_mingge', label: '明哥' },
]
const selectedBackground = ref('https://java-web-project-13859154338.oss-cn-beijing.aliyuncs.com/CollectStudySystem/bg1.jpg')
const avatarActionMap = {
  '111260002': ['A_U_hello_O', 'A_LH_emphasize2_O', 'A_RH_Show_right_O'],
  '111264001': ['A_RH_sit_hello_O', 'A_LH_invite_O', 'A_RH_sit_good_O'],
}

// ==================== 响应式状态 ====================
const avatarContainer = ref(null)
const scrollbarRef = ref(null)

// 模式：resource（资源生成，默认）| qa（答疑解惑）
const chatMode = ref('resource')

// 数字人相关
const subtitle = ref('')
const isAvatarReady = ref(false)
const isAvatarLoading = ref(false)
const isAvatarSpeaking = ref(false)
const selectedAvatar = ref('111260002')
const selectedVoice = ref('x4_lingyuyan_oral')
const humanAction = ref(['A_U_hello_O', 'A_LH_emphasize2_O', 'A_RH_Show_right_O'])
const showAvatarSettings = ref(false)
let digitalHuman = null

// 对话相关
const conversation = ref([])
const userInput = ref('')
const agentUserId = ref('')
const isInputDisabled = ref(false)
const isAgentLoading = ref(false)
const lastAiMessageContent = ref('')

// SSE 思考过程（资源生成模式）
const sseEventSource = ref(null)
const sseConnected = ref(false)
const currentThinkingIndex = ref(-1)

// 历史记录
const hasMoreHistory = ref(false)
const isLoadingHistory = ref(false)
const firstChatId = ref(null)

// 答疑模式首次问候
const hasQAGreeting = ref(false)

// 冲突弹窗
const showConflictDialog = ref(false)
const conflictData = ref({ createTime: '', suggestionWarning: '', rsType: null, taskId: null })

// 复习预设消息
const skipInfo = ref(null)
const presetSessionId = ref('')
const lastProcessedMessage = ref('')

// 语音录制
const isRecording = ref(false)
const recordingDuration = ref(0)
let recordingTimer = null
let asrInstance = null
const isVoiceMode = ref(false)
const waveformCanvas = ref(null)
let audioContext = null
let analyser = null
let mediaStream = null
let dataArray = null
let animationId = null

// 打字机
const currentTypingIndex = ref(-1)

// 视频播放
const videoPlayUrl = ref('')
const showVideoPlayer = ref(false)

// ==================== 数字人 ====================
const initDigitalHuman = () => {
  if (digitalHuman) {
    digitalHuman.destroy()
    digitalHuman = null
  }
  digitalHuman = new DigitalHuman(AVATAR_CONFIG)
  digitalHuman.setAvatar(selectedAvatar.value)
  digitalHuman.setVoice(selectedVoice.value)
  digitalHuman.setBackground(selectedBackground.value)

  digitalHuman
    .on('connected', (resp) => {
      isAvatarReady.value = true
      isAvatarLoading.value = false
    })
    .on('disconnected', (e) => {
      isAvatarReady.value = false
      isAvatarLoading.value = false
      if (e) showToast('数字人连接已断开')
    })
    .on('subtitle', (text) => { subtitle.value = text })
    .on('error', (error) => {
      isAvatarLoading.value = false
      showFailToast('数字人错误: ' + (error?.message || '未知错误'))
    })
    .on('playing', () => { isAvatarSpeaking.value = true })

  return digitalHuman
}

const startAvatar = async () => {
  if (!digitalHuman) initDigitalHuman()
  if (isAvatarReady.value) return
  isAvatarLoading.value = true
  await nextTick()
  try {
    await digitalHuman.start(avatarContainer.value, {
      avatarId: selectedAvatar.value,
      voiceId: selectedVoice.value,
      backgroundUrl: selectedBackground.value,
      air: 1,
    })
    isAvatarLoading.value = false
    showSuccessToast('数字人启动成功')
    await speakLastAiMessage()
  } catch (e) {
    isAvatarLoading.value = false
    isAvatarReady.value = false
    // 启动失败后销毁并置空实例，使后续对话仅跳过数字人相关操作（播报/动作），不影响对话本身
    if (digitalHuman) {
      try {
        digitalHuman.destroy()
      } catch (err) {
        console.error('销毁数字人失败:', err)
      }
      digitalHuman = null
    }
    showFailToast('启动数字人失败: ' + (e?.message || '请检查网络'))
  }
}

const stopAvatar = async () => {
  if (!digitalHuman) return
  try {
    await digitalHuman.stop()
    isAvatarReady.value = false
    isAvatarLoading.value = false
    subtitle.value = ''
    showSuccessToast('数字人已关闭')
  } catch (e) {
    showFailToast('关闭失败: ' + (e?.message || ''))
  }
}

const toggleAvatar = async () => {
  if (isAvatarReady.value) await stopAvatar()
  else await startAvatar()
}

const interruptAvatar = async () => {
  if (!digitalHuman || !isAvatarReady.value) return
  try {
    await digitalHuman.interrupt()
    if (currentTypingIndex.value >= 0 && currentTypingIndex.value < conversation.value.length) {
      const item = conversation.value[currentTypingIndex.value]
      if (item && item.isTyping) {
        const full = item.content || item.displayContent || item.contentHtml || ''
        item.content = full
        item.displayContent = full
        item.contentHtml = full
        item.isTyping = false
        currentTypingIndex.value = -1
      }
    }
  } catch (e) {
    console.error('打断失败:', e)
  }
}

const speakLastAiMessage = async () => {
  if (!digitalHuman || !isAvatarReady.value) return
  let lastAiMessage = null
  let j = null
  for (let i = conversation.value.length - 1; i >= 0; i--) {
    if (conversation.value[i].type === 'ai') {
      lastAiMessage = conversation.value[i]
      j = i
      break
    }
  }
  if (lastAiMessage && j === conversation.value.length - 1) {
    const content = lastAiMessageContent.value || lastAiMessage.content
    if (!content || content.trim() === '') return
    if (lastAiMessage.content === '' && lastAiMessageContent.value) {
      await Promise.all([
        digitalHuman.speak(content, { voiceId: selectedVoice.value }),
        digitalHuman.doAction(humanAction.value[0]),
        typewriterUpdateMessage(j, content),
      ])
      lastAiMessageContent.value = ''
    } else {
      await digitalHuman.doAction(humanAction.value[0])
      await digitalHuman.speak(content, { voiceId: selectedVoice.value })
    }
  } else {
    const greeting = '你好！我是你的智能学习小助手，请问有什么可以帮助你的？'
    const message = { type: 'ai', mode: 'resource', content: '', displayContent: '', isTyping: true }
    const index = conversation.value.length
    conversation.value.push(message)
    await Promise.all([
      digitalHuman.doAction(humanAction.value[0]),
      digitalHuman.speak(greeting, { voiceId: selectedVoice.value }),
      typewriterUpdateMessage(index, greeting),
    ])
    await nextTick()
    scrollToBottom()
  }
}

// ==================== SSE 思考过程（资源生成模式） ====================
const setupSSE = () => {
  // 每次都重新建立连接：先关闭旧的
  teardownSSE()
  if (!agentUserId.value) return null
  const es = connectSSE(agentUserId.value)
  if (!es || typeof es.addEventListener !== 'function') return null
  sseEventSource.value = es

  // 等待连接建立的 Promise
  const connectPromise = new Promise((resolve) => {
    es.onopen = () => {
      console.log('✅ SSE连接成功')
      sseConnected.value = true
      resolve(true)
    }
    es.onerror = (err) => {
      console.error('❌ SSE错误:', err)
      sseConnected.value = false
      resolve(false)
    }
  })

  // 默认消息（无 event: 前缀的消息走这里）
  es.onmessage = (event) => {
    console.log('📨 [onmessage] 原始数据:', event.data)
    try {
      let data = JSON.parse(event.data)
      if (typeof data === 'string') data = JSON.parse(data)
      handleSSEMessage(data.type || 'message', data)
    } catch (e) {
      console.error('SSE onmessage 解析失败:', e, event.data)
    }
  }

  // 命名事件（与 FloatWindow.vue 对齐）
  const eventTypes = [
    'connection', 'disconnect', 'message', 'json', 'heartbeat',
    'thinking', 'node_status', 'done', 'task_result', 'chat_stream',
    'mindmap_stream', 'animation_stream', 'extension_stream',
    'paper_stream', 'practice_stream', 'video_stream', 'word_stream',
    'stream', 'study_plan_stream', 'super_agent_stream', 'ppt_stream',
  ]
  eventTypes.forEach(type => {
    es.addEventListener(type, (event) => {
      console.log(`📨 [${type}] 原始数据:`, event.data)
      try {
        let data = JSON.parse(event.data)
        if (typeof data === 'string') data = JSON.parse(data)
        handleSSEMessage(data.type || type, data)
      } catch (e) {
        console.error(`SSE [${type}] 解析失败:`, e)
      }
    })
  })

  return connectPromise
}

const teardownSSE = () => {
  if (sseEventSource.value) {
    sseEventSource.value.close()
    sseEventSource.value = null
  }
  sseConnected.value = false
}

// 断开后重连再断开，用于清缓存：close → 等1秒 → connect → 等1秒 → close
const teardownSSEWithCacheClear = async () => {
  teardownSSE()
  await new Promise(resolve => setTimeout(resolve, 1000))
  if (agentUserId.value) {
    const es = connectSSE(agentUserId.value)
    if (es && typeof es.addEventListener === 'function') {
      sseEventSource.value = es
      await new Promise(resolve => setTimeout(resolve, 1000))
      teardownSSE()
    }
  }
}

const handleSSEMessage = (type, data) => {
  console.log('🔄 SSE消息类型:', type, '数据:', data)
  if (type === 'connection') {
    sseConnected.value = true
    return
  }
  if (type === 'thinking' && data.content) {
    if (currentThinkingIndex.value >= 0 && currentThinkingIndex.value < conversation.value.length) {
      const msg = conversation.value[currentThinkingIndex.value]
      if (msg && msg.mode === 'resource' && msg.thinkingDone !== true) {
        // 显式替换对象以确保 Vue 响应式更新
        conversation.value[currentThinkingIndex.value] = {
          ...msg,
          thinkingContent: (msg.thinkingContent || '') + data.content,
        }
        scrollToBottom()
      }
    }
    return
  }
  if (type === 'done') {
    if (currentThinkingIndex.value >= 0 && currentThinkingIndex.value < conversation.value.length) {
      const msg = conversation.value[currentThinkingIndex.value]
      if (msg) {
        conversation.value[currentThinkingIndex.value] = {
          ...msg,
          thinkingDone: true,
          thinkingExpanded: false,
          thinkingStreaming: false,
        }
      }
      console.log('✅ SSE done: 思考过程已折叠')
    }
    currentThinkingIndex.value = -1
    return
  }
}

// ==================== 模式切换 ====================
const switchMode = async (mode) => {
  if (mode === chatMode.value) return
  if (isAgentLoading.value || isInputDisabled.value) {
    showToast('请等待当前对话完成')
    return
  }
  // 切换模式时打断数字人说话
  if (digitalHuman && isAvatarReady.value) {
    try { await digitalHuman.interrupt() } catch (e) { /* ignore */ }
  }
  chatMode.value = mode
  if (mode === 'resource') {
    nextTick(async () => {
      await nextTick()
      scrollToBottom()
    })
  } else {
    teardownSSE()
    // 首次切换到答疑模式，显示问候语
    if (!hasQAGreeting.value) {
      hasQAGreeting.value = true
      const greeting = '你好！我是你的答疑小助手，有什么不懂的问题都可以问我，我会尽力帮你解答~'
      if (digitalHuman && isAvatarReady.value) {
        await digitalHuman.doAction(humanAction.value[0])
        await digitalHuman.speak(greeting, { voiceId: selectedVoice.value })
        await new Promise(r => setTimeout(r, 500))
      }
      await addAiMessageWithTypewriter(greeting)
    }
  }
  showToast(mode === 'resource' ? '已切换到资源生成模式' : '已切换到答疑解惑模式')
}

// ==================== 打字机效果 ====================
const typewriterUpdateMessage = async (index, content) => {
  if (index < 0 || index >= conversation.value.length) return
  conversation.value[index] = {
    ...conversation.value[index],
    isTyping: true,
    content: '',
    displayContent: '',
  }
  currentTypingIndex.value = index
  await nextTick()
  scrollToBottom()
  return typewriterDisplayText(index, content)
}

const typewriterDisplayText = async (index, content) => {
  let currentIndex = 0
  return new Promise((resolve) => {
    const timer = setInterval(() => {
      currentIndex++
      const displayText = content.substring(0, currentIndex)
      if (conversation.value[index]) {
        conversation.value[index] = {
          ...conversation.value[index],
          displayContent: displayText,
          content: displayText,
        }
      }
      if (currentIndex % 10 === 0) scrollToBottom()
      if (currentIndex >= content.length) {
        clearInterval(timer)
        if (conversation.value[index]) {
          conversation.value[index] = {
            ...conversation.value[index],
            isTyping: false,
            displayContent: content,
            content: content,
          }
        }
        currentTypingIndex.value = -1
        resolve(content)
      }
    }, 30)
  })
}

const typewriterDisplayHtml = async (index, fullHtml) => {
  let currentIndex = 0
  const htmlLength = fullHtml.length
  return new Promise((resolve) => {
    const timer = setInterval(() => {
      if (currentIndex >= htmlLength) {
        clearInterval(timer)
        currentTypingIndex.value = -1
        resolve(fullHtml)
        return
      }
      let char = fullHtml[currentIndex]
      if (char === '<') {
        const tagEnd = fullHtml.indexOf('>', currentIndex)
        if (tagEnd !== -1) currentIndex = tagEnd + 1
        else currentIndex++
      } else {
        currentIndex++
      }
      if (conversation.value[index]) {
        conversation.value[index] = {
          ...conversation.value[index],
          contentHtml: fullHtml.substring(0, currentIndex),
          isTyping: currentIndex < htmlLength,
        }
      }
      if (currentIndex % 10 === 0) scrollToBottom()
    }, 25)
  })
}

const addAiMessageWithTypewriter = async (content, extraData = {}) => {
  const message = {
    type: 'ai',
    mode: chatMode.value,
    content: '',
    displayContent: '',
    isTyping: true,
    ...extraData,
  }
  const index = conversation.value.length
  conversation.value.push(message)
  currentTypingIndex.value = index
  await nextTick()
  scrollToBottom()
  return typewriterDisplayText(index, content)
}

// ==================== 格式化消息 ====================
const formatMessage = (text) => {
  if (!text) return ''
  return text
    .replace(/[#*]/g, '')
    .replace(/\\+n/g, '\n')
    .split('\n')
    .filter(line => line.trim() !== '')
    .join('<br>')
}

// ==================== Markdown 转 HTML（答疑模式） ====================
const getProxyUrl = (url) => url || ''

const markdownToHtml = (md) => {
  if (!md) return ''
  let html = md
  const imgPlaceholders = []
  html = html.replace(/!\[([^\]]*)\]\((\S+?)\s*=\s*(\d+)x\s*\)/g, (m, alt, url, w) => {
    const token = `__IMG_${imgPlaceholders.length}__`
    imgPlaceholders.push(`<img src="${getProxyUrl(url.trim())}" alt="${alt}" loading="lazy" referrerpolicy="no-referrer" style="width:${w}px;max-width:100%;border-radius:8px;margin:6px 0;">`)
    return token
  })
  html = html.replace(/!\[([^\]]*)\]\((\S+)\)/g, (m, alt, url) => {
    const token = `__IMG_${imgPlaceholders.length}__`
    imgPlaceholders.push(`<img src="${getProxyUrl(url)}" alt="${alt}" loading="lazy" referrerpolicy="no-referrer" style="max-width:100%;border-radius:8px;margin:6px 0;">`)
    return token
  })
  html = html.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
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
  html = html.replace(/__IMG_(\d+)__/g, (m, idx) => imgPlaceholders[parseInt(idx)] || '')
  const lines = html.split('\n')
  const out = []
  for (const line of lines) {
    const t = line.trim()
    if (!t) continue
    if (/^<(h[1-6]|ul|\/ul|li|blockquote|\/blockquote|hr|img|p|code|a)/.test(t)) out.push(t)
    else out.push('<p>' + t + '</p>')
  }
  html = out.join('\n')
  html = html.replace(/<p><ul>/g, '<ul>').replace(/<\/ul><\/p>/g, '</ul>')
  html = html.replace(/<p><li>/g, '<li>').replace(/<\/li><\/p>/g, '</li>')
  return html
}

// ==================== 资源生成模式发送（基于 aiAnswer.vue） ====================
const sendToAgent = async (text, rsType = null, sessionId = 'none') => {
  if (!text?.trim()) { showToast('请输入内容'); return }

  isInputDisabled.value = true
  isAgentLoading.value = true
  await interruptAvatar()

  // 添加用户消息
  conversation.value.push({ type: 'user', mode: 'resource', content: text.trim() })
  await nextTick()
  scrollToBottom()

  // 添加 AI 消息占位（含 SSE 思考过程）
  const loadingIndex = conversation.value.length
  conversation.value.push({
    type: 'ai',
    mode: 'resource',
    content: '',
    displayContent: '',
    isTyping: false,
    isLoading: true,
    thinkingContent: '',
    thinkingDone: false,
    thinkingExpanded: true,
    thinkingStreaming: true,
    resource: null,
    rsType: null,
  })
  currentThinkingIndex.value = loadingIndex
  await nextTick()
  scrollToBottom()

  // 每次发消息都重新建立 SSE 连接
  await setupSSE()

  // 学习计划单独生成提示
  if (rsType === 'cancel') {
    conversation.value.splice(loadingIndex, 1)
    currentThinkingIndex.value = -1
    const tipText = '学习计划只能单独生成哦~'
    if (digitalHuman) {
      await digitalHuman.doAction(humanAction.value[1])
      await digitalHuman.speak(tipText, { voiceId: selectedVoice.value })
    }
    await addAiMessageWithTypewriter(tipText)
    isAgentLoading.value = false
    isInputDisabled.value = false
    return
  }

  let skipSSETeardown = false
  try {
    if (sessionId?.isTrusted) sessionId = 'none'
    const result = await postTextApi({
      userId: agentUserId.value,
      text: text.trim(),
      rsType: Array.isArray(rsType) ? 99 : rsType,
      sessionId: sessionId,
      rsArray: Array.isArray(rsType) ? rsType : [],
    })

    // API 已返回，停止流式光标（但不折叠思考过程，等 SSE done 事件）
    if (conversation.value[loadingIndex]) {
      conversation.value[loadingIndex].thinkingStreaming = false
    }
    // 注意：不设置 thinkingDone=true 和 currentThinkingIndex=-1
    // 让 SSE thinking 事件继续被接收，直到 done 事件到达才折叠

    // 超时兜底：如果 15 秒后 SSE done 事件仍未到达，强制折叠
    setTimeout(() => {
      if (currentThinkingIndex.value === loadingIndex && conversation.value[loadingIndex]) {
        console.warn('⚠️ SSE done 超时，强制折叠思考过程')
        conversation.value[loadingIndex] = {
          ...conversation.value[loadingIndex],
          thinkingDone: true,
          thinkingExpanded: false,
          thinkingStreaming: false,
        }
        currentThinkingIndex.value = -1
      }
    }, 120000)

    if (result.code !== 1) throw new Error('Agent返回错误: ' + JSON.stringify(result))

    console.log('🔍 Agent返回数据:', JSON.stringify(result.data, null, 2))

    // 多资源生成
    if (result.data?.detail && result.data.rsType === 99) {
      const resourcePromises = []
      for (let i = 0; i < result.data.detail.length; i++) {
        const item = result.data.detail[i]
        const content = (item.content && item.content.trim() !== '') ? item.content : '出错：AI 返回内容为空，请稍后重试'
        if (digitalHuman) {
          await digitalHuman.doAction(humanAction.value[1])
          await digitalHuman.speak(content, { voiceId: selectedVoice.value })
        }
        if (i === 0) {
          // 第一个资源：更新占位消息（保留思考过程）
          conversation.value[loadingIndex] = {
            ...conversation.value[loadingIndex],
            isLoading: false,
            content: '',
            displayContent: '',
            isTyping: true,
            resource: item.resource,
            rsType: item.rsType,
            isBatchGenerate: true,
          }
          currentTypingIndex.value = loadingIndex
          await typewriterDisplayText(loadingIndex, content)
        } else {
          // 后续资源：添加新消息
          await addAiMessageWithTypewriter(content, {
            resource: item.resource,
            rsType: item.rsType,
            isBatchGenerate: true,
          })
        }
        const index = conversation.value.findIndex(m =>
          ((m?.resource?.taskId || null) === (item.resource?.taskId || null) && (m?.rsType || null) === (item.rsType || null))
        )
        if (item.resource?.status === 1) {
          resourcePromises.push(isRsSuccess(index, item.rsType, item.resource.taskId))
        } else {
          conversation.value[index] = { ...conversation.value[index], ...item }
        }
        await nextTick()
        scrollToBottom()
      }
      // 资源生成完成后才断开 SSE 并清缓存
      if (resourcePromises.length > 0) {
        Promise.all(resourcePromises).finally(() => teardownSSEWithCacheClear())
      } else {
        await teardownSSEWithCacheClear()
      }
      return
    }

    // 单资源生成
    if (result.data?.resource) {
      const content = result.data.content
      if (!content || content.trim() === '') {
        // 内容为空，显示出错提示
        if (conversation.value[loadingIndex]) {
          conversation.value[loadingIndex] = {
            ...conversation.value[loadingIndex],
            isLoading: false,
            content: '',
            displayContent: '',
            isTyping: true,
          }
        }
        currentTypingIndex.value = loadingIndex
        await typewriterDisplayText(loadingIndex, '出错：AI 返回内容为空，请稍后重试')
        showFailToast('AI 返回内容为空')
      } else {
        if (digitalHuman) {
          await digitalHuman.doAction(humanAction.value[1])
          await digitalHuman.speak(content, { voiceId: selectedVoice.value })
        }
        // 将占位消息转为结果消息（保留思考过程）
        conversation.value[loadingIndex] = {
          ...conversation.value[loadingIndex],
          isLoading: false,
          content: '',
          displayContent: '',
          isTyping: true,
          resource: result.data.resource,
          rsType: result.data.rsType,
        }
        currentTypingIndex.value = loadingIndex
        await typewriterDisplayText(loadingIndex, content)

        if (result.data.resource.status === 1) {
          // 资源生成完成后才断开 SSE 并清缓存
          isRsSuccess(loadingIndex, result.data.rsType, result.data.resource.taskId).finally(() => teardownSSEWithCacheClear())
          skipSSETeardown = true
        }
      }
    } else {
      // 普通文本回复
      const agentData = result.data?.data || result.data
      const status = agentData?.status || result.data?.status || 0
      const followUpQuestions = agentData?.follow_up_questions
      const guidance = agentData?.guidance || result.data?.guidance || ''
      let speakText = ''

      if (status === 'need_more_info' && followUpQuestions?.length > 0) {
        speakText = Array.isArray(followUpQuestions) ? followUpQuestions[0] : (typeof followUpQuestions === 'string' ? followUpQuestions : '抱歉，我遇到了一些问题，请稍后再试。')
      } else if (guidance && guidance !== '0') {
        speakText = guidance
        if (agentData?.des_stage === 'registration_complete') {
          speakText = `初次画像构建成功！\n${guidance.replaceAll('###', '')}`
          const loginUserStr = localStorage.getItem('loginUser')
          if (loginUserStr) {
            const loginUser = JSON.parse(loginUserStr)
            loginUser.isBuildProfile = 1
            localStorage.setItem('loginUser', JSON.stringify(loginUser))
          }
        }
      } else if (agentData?.content && agentData.content.trim() !== '') {
        speakText = agentData.content
      } else {
        // 所有条件都不满足或内容为空，显示出错提示
        speakText = '出错：AI 返回内容为空，请稍后重试'
      }

      if (speakText) {
        if (digitalHuman) {
          await digitalHuman.doAction(humanAction.value[2])
          await digitalHuman.speak(speakText, { voiceId: selectedVoice.value })
        }
        conversation.value[loadingIndex] = {
          ...conversation.value[loadingIndex],
          isLoading: false,
          content: '',
          displayContent: '',
          isTyping: true,
        }
        currentTypingIndex.value = loadingIndex
        await typewriterDisplayText(loadingIndex, speakText)
      }
    }

    // 安全兜底：如果 loading 占位消息仍未更新，说明走了未预期的分支
    if (conversation.value[loadingIndex] && conversation.value[loadingIndex].isLoading) {
      console.warn('⚠️ Loading消息未被更新，执行兜底处理')
      conversation.value[loadingIndex] = {
        ...conversation.value[loadingIndex],
        isLoading: false,
        content: '',
        displayContent: '',
        isTyping: true,
      }
      currentTypingIndex.value = loadingIndex
      await typewriterDisplayText(loadingIndex, '出错：AI 返回内容为空，请稍后重试')
      showFailToast('AI 返回内容为空')
    }
  } catch (e) {
    console.error('Agent请求失败:', e)
    if (conversation.value[loadingIndex]) {
      conversation.value[loadingIndex].thinkingDone = true
      conversation.value[loadingIndex].thinkingExpanded = false
      conversation.value[loadingIndex].isLoading = false
    }
    currentThinkingIndex.value = -1
    const errorText = '抱歉，我遇到了一些问题，请稍后再试。'
    if (digitalHuman) {
      await digitalHuman.doAction(humanAction.value[1])
      await digitalHuman.speak(errorText, { voiceId: selectedVoice.value })
    }
    conversation.value[loadingIndex] = {
      ...conversation.value[loadingIndex],
      isLoading: false,
      content: '',
      displayContent: '',
      isTyping: true,
    }
    currentTypingIndex.value = loadingIndex
    await typewriterDisplayText(loadingIndex, errorText)
    showFailToast('请求失败')
  } finally {
    isAgentLoading.value = false
    isInputDisabled.value = false
    // 注意：不在这里清除 currentThinkingIndex
    // SSE thinking 事件会继续被接收，直到 done 事件或 15 秒超时才折叠
    // 资源生成模式下，SSE 在资源生成完成后才断开（见 isRsSuccess 的 .finally）
    if (!skipSSETeardown) {
      await teardownSSEWithCacheClear()
    }
    await nextTick()
    scrollToBottom()
  }
}

// ==================== 答疑解惑模式发送（基于 SmartBall.vue） ====================
const sendQAMessage = async (inputText) => {
  const text = (inputText ?? userInput.value ?? '').trim()
  if (!text) { showToast('请输入内容'); return }
  if (isInputDisabled.value) return

  userInput.value = ''

  await interruptAvatar()

  conversation.value.push({ type: 'user', mode: 'qa', content: text })
  await nextTick()
  scrollToBottom()

  isInputDisabled.value = true
  isAgentLoading.value = true

  // 添加 AI 加载占位
  const loadingIndex = conversation.value.length
  conversation.value.push({
    type: 'ai',
    mode: 'qa',
    content: '',
    contentHtml: '',
    isTyping: false,
    isLoading: true,
    images: [],
    sources: [],
    toolResults: [],
    showImages: false,
    showSources: false,
    showToolResults: false,
    showSourcesSection: false,
  })
  await nextTick()
  scrollToBottom()

  try {
    const response = await smartBallChatApi({
      user_id: agentUserId.value,
      user_input: text,
      enable_tts: true,
    })

    conversation.value.splice(loadingIndex, 1)

    if (response.success && response.data) {
      const reply = response.data.reply || response.data.message || '嗯？'
      const images = response.data.images || []
      const sources = response.data.sources || []
      const toolResults = response.data.tool_results || []

      // 添加 AI 消息并打字机输出
      const message = {
        type: 'ai',
        mode: 'qa',
        content: '',
        contentHtml: '',
        isTyping: true,
        images,
        sources,
        toolResults,
        showImages: false,
        showSources: false,
        showToolResults: false,
        showSourcesSection: false,
      }
      const index = conversation.value.length
      conversation.value.push(message)
      currentTypingIndex.value = index
      await nextTick()
      scrollToBottom()

      // 先让数字人说话，再显示文字
      if (digitalHuman && isAvatarReady.value) {
        await digitalHuman.doAction(humanAction.value[0])
        await digitalHuman.speak(reply, { voiceId: selectedVoice.value })
        await new Promise(r => setTimeout(r, 500))
      }

      const fullHtml = markdownToHtml(reply)
      await typewriterDisplayHtml(index, fullHtml)

      if (conversation.value[index]) {
        conversation.value[index].content = reply
        conversation.value[index].contentHtml = fullHtml
        conversation.value[index].isTyping = false
      }

      // 依次显示图片 → 视频 → 来源
      if (images && images.length > 0) {
        await new Promise(r => setTimeout(r, 300))
        if (conversation.value[index]) conversation.value[index].showImages = true
        scrollToBottom()
      }
      if (toolResults && toolResults.length > 0) {
        await new Promise(r => setTimeout(r, 300))
        if (conversation.value[index]) conversation.value[index].showToolResults = true
        scrollToBottom()
      }
      if (sources && sources.length > 0) {
        await new Promise(r => setTimeout(r, 300))
        if (conversation.value[index]) conversation.value[index].showSourcesSection = true
        scrollToBottom()
      }
    } else {
      await addAiMessageWithTypewriter('网络有点问题，稍后再试吧')
    }
  } catch (error) {
    console.error('答疑请求失败:', error)
    conversation.value.splice(loadingIndex, 1)
    await addAiMessageWithTypewriter('网络有点问题，稍后再试吧')
  } finally {
    isAgentLoading.value = false
    isInputDisabled.value = false
    await nextTick()
    scrollToBottom()
  }
}

// ==================== 发送消息 ====================
const sendMessage = (sessionId = 'none') => {
  if (isInputDisabled.value) return
  if (!userInput.value?.trim()) return
  const text = userInput.value
  userInput.value = ''
  if (chatMode.value === 'resource') {
    sendToAgent(text, findString(text), sessionId)
  } else {
    sendQAMessage(text)
  }
}

// ==================== 复习预设消息 ====================
const handlePresetMessage = async () => {
  skipInfo.value = isSkip(10)
  let presetMessage = ''
  let sessionId = ''
  if (skipInfo.value) {
    try {
      presetMessage = skipInfo.value.message
      sessionId = skipInfo.value.sessionId
      removeSkip(10)
    } catch (e) {
      console.error('解析复习数据失败:', e)
    }
  }
  presetSessionId.value = sessionId
  if (presetMessage && presetMessage !== lastProcessedMessage.value) {
    lastProcessedMessage.value = presetMessage
    try {
      userInput.value = decodeURIComponent(presetMessage)
      // 确保处于资源生成模式
      if (chatMode.value !== 'resource') {
        switchMode('resource')
      }
      await new Promise(resolve => setTimeout(resolve, 2000))
      sendMessage(presetSessionId.value)
    } catch (e) {
      console.error('解码预设消息失败:', e)
    }
  }
}

// ==================== 滚动 ====================
const scrollToBottom = () => {
  nextTick(() => {
    if (scrollbarRef.value) {
      scrollbarRef.value.scrollTop = scrollbarRef.value.scrollHeight
    }
  })
}

// ==================== 资源相关 ====================
const getResourceTypeName = (type) => {
  const map = { 0: 'PPT', 1: '思维导图', 2: '讲解文档', 3: '拓展阅读', 4: '编程题', 5: '视频搜索', 6: '学习动画', 7: '题库试卷', 8: '智学路径' }
  return map[type] || '资源'
}

const getResourceColor = (type) => {
  const map = { 0: '#f34832', 1: '#61c886', 2: '#004198', 3: '#ea9518', 4: '#82529d', 5: '#f6ef37', 6: '#17abe3', 7: '#8a8a8a', 8: '#e8989a' }
  return map[type] || '#2D7DDB'
}

const openResource = (item) => {
  saveSkip(item.rsType, item.resource.taskId)
  showToast('正在跳转打开')
  const routeMap = {
    0: '/phone/resource/ppt', 1: '/phone/resource/mindmap', 2: '/phone/resource/word',
    3: '/phone/resource/reading', 4: '/phone/resource/code', 5: '/phone/resource/video',
    6: '/phone/resource/anima', 7: '/phone/resource/paper', 8: '/phone/pathPlan',
  }
  const path = routeMap[item.rsType]
  if (path) router.push(path)
  else showToast('不存在该资源，无法跳转')
}

// 获取进度（轮询）
const isRsSuccess = async (index, rsType, taskId) => {
  try {
    let progressRes = await getProgressApi(agentUserId.value, rsType, taskId)

    // 冲突弹窗检测
    if (progressRes.data.resource?.suggestionWarning && progressRes.data.resource.suggestionWarning != 1 && progressRes.data.resource.suggestionWarning != null) {
      if (!showConflictDialog.value) {
        conflictData.value = {
          createTime: progressRes.data.resource.createTime,
          suggestionWarning: progressRes.data.resource.suggestionWarning,
          rsType: progressRes.data.rsType,
          taskId: progressRes.data.resource?.taskId || taskId,
        }
        showConflictDialog.value = true
      }
    }

    if (progressRes.data.resource.status === 1) {
      let nowNum = 0
      while (nowNum < 100 && progressRes.data.resource.status === 1) {
        nowNum++
        await new Promise(resolve => setTimeout(resolve, 10000))
        progressRes = await getProgressApi(agentUserId.value, rsType, taskId)
        if (progressRes.data.resource?.suggestionWarning && progressRes.data.resource.suggestionWarning != 1 && progressRes.data.resource.suggestionWarning != null) {
          if (!showConflictDialog.value) {
            conflictData.value = {
              createTime: progressRes.data.resource.createTime,
              suggestionWarning: progressRes.data.resource.suggestionWarning,
              rsType: progressRes.data.rsType,
              taskId: progressRes.data.resource?.taskId || taskId,
            }
            showConflictDialog.value = true
          }
        }
      }
    }

    let indexTrue = index
    for (let i = 0; i < conversation.value.length; i++) {
      if (conversation.value[i]?.resource?.taskId && conversation.value[i].resource.taskId == taskId) indexTrue = i
    }

    if (progressRes.data.resource.status === 1) {
      showFailToast('生成超时')
      if (conversation.value[indexTrue]) {
        conversation.value[indexTrue].resource = { ...conversation.value[indexTrue].resource, status: 3 }
        conversation.value[indexTrue].content = '生成超时'
      }
      if (digitalHuman) await digitalHuman.speak('生成超时', { voiceId: selectedVoice.value })
    } else if (progressRes.data.resource.status === 2) {
      showSuccessToast(progressRes.data.content || '生成成功')
      const wasBatch = conversation.value[indexTrue]?.isBatchGenerate
      conversation.value[indexTrue] = { ...conversation.value[indexTrue], ...progressRes.data }
      if (wasBatch) conversation.value[indexTrue].isBatchGenerate = true
      conversation.value[indexTrue].content = '生成成功!'
      conversation.value[indexTrue].displayContent = '生成成功!'
      if (digitalHuman) await digitalHuman.speak(progressRes.data.content || '生成成功', { voiceId: selectedVoice.value })
    } else if (progressRes.data.resource.status === 3) {
      showFailToast(progressRes.data.content || '生成失败')
      if (conversation.value[indexTrue]) {
        conversation.value[indexTrue].content = progressRes.data.content || '生成失败'
        conversation.value[indexTrue].resource = { ...conversation.value[indexTrue].resource, status: 3 }
      }
      if (digitalHuman) await digitalHuman.speak(progressRes.data.content || '生成失败', { voiceId: selectedVoice.value })
    }
  } catch (e) {
    console.error('轮询进度失败', e)
    let indexTrue = index
    for (let i = 0; i < conversation.value.length; i++) {
      if (conversation.value[i]?.resource?.taskId && conversation.value[i].resource.taskId == taskId) indexTrue = i
    }
    if (conversation.value[indexTrue]) {
      conversation.value[indexTrue] = {
        ...conversation.value[indexTrue],
        content: '抱歉，我遇到了一些问题，请稍后再试。',
      }
    }
  }
}

const reCreate = async (rsType, taskId) => {
  if (isInputDisabled.value) return
  isInputDisabled.value = true
  try {
    const result = await reCreateApi(agentUserId.value, rsType, taskId)
    if (result.code !== 1) throw new Error('重新生成失败')
    showSuccessToast('重新生成成功')
    const content = result.data.content
    if (digitalHuman) await digitalHuman.speak(content, { voiceId: selectedVoice.value })
    await addAiMessageWithTypewriter(content, { resource: result.data.resource, rsType: result.data.rsType })
    const index = conversation.value.findIndex(m =>
      ((m?.resource?.taskId || null) === (result?.data?.resource?.taskId || null) && (m?.rsType || null) === (result?.data?.rsType || null))
    )
    if (result.data.resource.status === 1) {
      isRsSuccess(index, result.data.rsType, result.data.resource.taskId)
    }
  } catch (e) {
    showToast('重新生成异常')
  } finally {
    isInputDisabled.value = false
  }
}

// 检查未完成任务
const checkTask = async () => {
  for (let i = 0; i < conversation.value.length; i++) {
    const item = conversation.value[i]
    if (item.resource && item.resource.status === 1) {
      isRsSuccess(i, item.rsType, item.resource.taskId)
    }
  }
}

// ==================== 历史记录 ====================
const loadHistory = async () => {
  if (isLoadingHistory.value) return
  if (chatMode.value !== 'resource') return
  isLoadingHistory.value = true
  try {
    const lastId = firstChatId.value || null
    const response = await aiHistoryApi(agentUserId.value, lastId)
    if (response.code !== 1) throw new Error(response.msg || '加载历史记录失败')
    const historyData = response.data || []
    if (historyData.length === 0) { hasMoreHistory.value = false; return }
    hasMoreHistory.value = historyData.length === 10
    const reversed = historyData.reverse()
    if (reversed.length > 0) firstChatId.value = reversed[0].id
    const processed = historyData.map(item => {
      if (item.type === 'ai' && (!item.content || (typeof item.content === 'string' && item.content.trim() === ''))) {
        return { ...item, mode: 'resource', content: '出错：AI 返回内容为空，请稍后重试', displayContent: '出错：AI 返回内容为空，请稍后重试', isLoading: false, isTyping: false }
      }
      return { ...item, mode: 'resource', isLoading: false, isTyping: false }
    })
    conversation.value = [...processed, ...conversation.value]
    if (historyData.length > 0) firstChatId.value = historyData[0].id
    await nextTick()
    if (scrollbarRef.value) scrollbarRef.value.scrollTop = 0
  } catch (e) {
    showFailToast('加载历史记录失败')
  } finally {
    isLoadingHistory.value = false
  }
}

// ==================== 语音输入（基于 aiAnswer.vue） ====================
const switchToVoiceMode = () => {
  if (isInputDisabled.value) {
    return
  }
  isVoiceMode.value = true
}

const switchToInputMode = () => {
  if (isRecording.value) {
    stopNativeRecording()
  }
  isVoiceMode.value = false
}

const toggleNativeRecording = async () => {
  if (isInputDisabled.value) {
    return
  }
  if (isRecording.value) {
    await interruptAvatar()
    stopNativeRecording()
  } else {
    await interruptAvatar()
    startNativeRecording()
  }
}

const startNativeRecording = async () => {
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true })

    audioContext = new (window.AudioContext || window.webkitAudioContext)()
    analyser = audioContext.createAnalyser()
    const source = audioContext.createMediaStreamSource(mediaStream)
    source.connect(analyser)

    analyser.fftSize = 256
    const bufferLength = analyser.frequencyBinCount
    dataArray = new Uint8Array(bufferLength)

    isRecording.value = true
    recordingDuration.value = 0
    recordingTimer = setInterval(() => {
      recordingDuration.value++
    }, 1000)

    asrInstance = new ASR()
    await asrInstance.startRecording()

    setTimeout(() => {
      drawWaveform()
    }, 100)

    showToast('开始录音，点击按钮停止')
  } catch (error) {
    console.error('录音启动失败:', error)
    showFailToast('无法访问麦克风，请检查权限')
  }
}

const stopNativeRecording = async () => {
  if (animationId) {
    cancelAnimationFrame(animationId)
    animationId = null
  }

  if (recordingTimer) {
    clearInterval(recordingTimer)
    recordingTimer = null
  }

  isRecording.value = false
  recordingDuration.value = 0

  if (audioContext && audioContext.state !== 'closed') {
    audioContext.close()
    audioContext = null
  }

  if (mediaStream) {
    mediaStream.getTracks().forEach(track => track.stop())
    mediaStream = null
  }

  if (asrInstance) {
    try {
      const recognizedText = await asrInstance.stopAndRecognize()

      if (recognizedText && recognizedText.trim()) {
        userInput.value = recognizedText
        await sendMessage()
      } else {
        showToast('未识别到语音内容')
      }
    } catch (error) {
      console.error('语音识别失败:', error)
      showFailToast('语音识别失败，请重试')
    } finally {
      asrInstance = null
    }
  }
}

const drawWaveform = () => {
  if (!waveformCanvas.value || !analyser || !dataArray) return

  const canvas = waveformCanvas.value
  const ctx = canvas.getContext('2d')

  const rect = canvas.getBoundingClientRect()
  if (rect.width === 0 || rect.height === 0) {
    setTimeout(() => {
      drawWaveform()
    }, 100)
    return
  }

  canvas.width = rect.width * window.devicePixelRatio
  canvas.height = rect.height * window.devicePixelRatio
  ctx.scale(window.devicePixelRatio, window.devicePixelRatio)

  const width = rect.width
  const height = rect.height

  const animate = () => {
    if (!isRecording.value) return

    animationId = requestAnimationFrame(animate)

    analyser.getByteFrequencyData(dataArray)

    ctx.clearRect(0, 0, width, height)

    const centerY = height / 2
    const barCount = 64
    const gap = 1

    for (let i = 0; i < barCount; i++) {
      const value = dataArray[i] || 0
      let barHeight = (value / 255) * (height * 0.9)
      if (barHeight < 2) barHeight = 2

      const x = (width / barCount) * i
      const y = centerY - barHeight / 2

      ctx.fillStyle = '#2D7DDB'
      ctx.fillRect(x, y, (width / barCount) - gap, barHeight)
    }
  }

  animate()
}

// ==================== 图片/视频预览 ====================
const previewImage = (url) => {
  showImagePreview([url])
}

const playVideo = (url) => {
  videoPlayUrl.value = url
  showVideoPlayer.value = true
}

const closeVideoPlayer = () => {
  videoPlayUrl.value = ''
  showVideoPlayer.value = false
}

// ==================== 思考过程展开/折叠 ====================
const toggleThinking = (index) => {
  const msg = conversation.value[index]
  if (msg) msg.thinkingExpanded = !msg.thinkingExpanded
}

// ==================== 冲突弹窗 ====================
const formatConflictMessage = (message) => {
  if (!message) return ''
  return message.replace(/\n/g, '<br/>')
}

const handleConflictOption = async (option) => {
  try {
    let conflictTaskId = conflictData.value.taskId
    if (conflictData.value.rsType === 8) conflictTaskId = conflictData.value.createTime
    const response = await conflictApi(agentUserId.value, {
      id: conflictTaskId,
      rsType: conflictData.value.rsType,
      option: option,
    })
    showToast(option ? '已接受，处理中...' : '已拒绝，处理中...')
    if (response.code === 1) showSuccessToast('操作完成')
    else showFailToast(response.msg || '操作失败')
  } catch (error) {
    showFailToast('网络异常，操作失败')
  } finally {
    showConflictDialog.value = false
    conflictData.value = { createTime: '', suggestionWarning: '', rsType: null, taskId: null }
  }
}

// ==================== 设置变更 ====================
const onAvatarChange = async () => {
  const actions = avatarActionMap[selectedAvatar.value]
  if (actions) humanAction.value = actions
  if (digitalHuman) {
    digitalHuman.setAvatar(selectedAvatar.value)
    if (isAvatarReady.value) {
      try {
        await digitalHuman.restart(avatarContainer.value, {
          avatarId: selectedAvatar.value,
          voiceId: selectedVoice.value,
          backgroundUrl: selectedBackground.value,
        })
        await digitalHuman.doAction(humanAction.value[0])
      } catch (e) {
        showFailToast('切换配置失败')
      }
    }
  }
}

const onVoiceChange = () => {
  if (digitalHuman) digitalHuman.setVoice(selectedVoice.value)
}

// ==================== 生命周期 ====================
let loginUser = null
onMounted(async () => {
  const userStr = localStorage.getItem('loginUser')
  if (userStr) {
    try {
      loginUser = JSON.parse(userStr)
      agentUserId.value = typeof loginUser.id === 'string' ? loginUser.id : String(loginUser.id)
    } catch (e) {
      console.error('用户信息解析失败', e)
    }
  }

  // 1. 加载历史记录（仅资源生成模式）
  if (agentUserId.value && chatMode.value === 'resource') {
    try {
      const response = await aiHistoryApi(agentUserId.value, 0)
      if (response.code === 1 && response.data && response.data.length > 0) {
        let historyData = response.data
        hasMoreHistory.value = historyData.length === 10
        if (historyData.length > 0) firstChatId.value = historyData[0].id
        const processed = historyData.map(item => {
          if (item.type === 'ai' && (!item.content || (typeof item.content === 'string' && item.content.trim() === ''))) {
            return { ...item, mode: 'resource', content: '出错：AI 返回内容为空，请稍后重试', displayContent: '出错：AI 返回内容为空，请稍后重试', isLoading: false, isTyping: false }
          }
          return { ...item, mode: 'resource', isLoading: false, isTyping: false }
        })
        const firstMsg = processed[0]
        if (firstMsg && firstMsg.type === 'ai' && firstMsg.content) {
          if (firstMsg.content.length > 150) {
            lastAiMessageContent.value = firstMsg.content
          } else {
            lastAiMessageContent.value = firstMsg.content
            processed[0] = { ...firstMsg, content: '', displayContent: '', isTyping: true }
          }
        }
        conversation.value = processed.reverse()
        await nextTick()
        scrollToBottom()
      }
    } catch (e) {
      console.error('加载初始历史记录失败:', e)
    }
  }

  // 2. 初始化数字人
  initDigitalHuman()

  // 3. 启动数字人
  await startAvatar()

  // 4. 处理复习预设消息（数字人已启动）
  if (isSkip(10) !== false) {
    try {
      handlePresetMessage()
    } catch (e) {
      showToast('复习内容打开失败')
      console.error('复习预设消息处理失败:', e)
    }
  }

  // 5. 检查未完成任务（SSE 在发消息时按需建立）
  await checkTask()
})

onBeforeUnmount(() => {
  if (recordingTimer) { clearInterval(recordingTimer); recordingTimer = null }
  if (animationId) { cancelAnimationFrame(animationId); animationId = null }
  if (audioContext && audioContext.state !== 'closed') {
    try { audioContext.close() } catch (e) { /* ignore */ }
    audioContext = null
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach(track => track.stop())
    mediaStream = null
  }
  if (asrInstance) {
    try { asrInstance.cleanup() } catch (e) { /* ignore */ }
    asrInstance = null
  }
  isRecording.value = false
  recordingDuration.value = 0
  if (currentTypingIndex.value >= 0) currentTypingIndex.value = -1

  teardownSSE()

  if (digitalHuman && !digitalHuman.isDestroyed) {
    try { digitalHuman.destroy() } catch (e) { /* ignore */ }
    digitalHuman = null
  }
})
</script>

<template>
  <div class="chat-page">
    <!-- 数字人全屏背景层 -->
    <div class="avatar-bg">
      <div ref="avatarContainer" class="avatar-container" :class="{ hidden: !isAvatarReady && !isAvatarLoading }"></div>

      <!-- 未启动占位 -->
      <div v-if="!isAvatarReady && !isAvatarLoading" class="avatar-placeholder" @click="startAvatar">
        <svg viewBox="0 0 24 24" width="40" height="40" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
        </svg>
        <span>若显示<i style="font-weight: bold; text-decoration: underline; font-style: normal;">数字人启动失败</i>，可能是由于数字人被占用，请稍后再试</span>
        <h2>点击再次启动数字人</h2>
      </div>

      <!-- 加载中 -->
      <div v-else-if="isAvatarLoading" class="avatar-loading">
        <div class="loading-spinner"></div>
        <span>正在加载数字人...</span>
      </div>

      <!-- 字幕 -->
      <!-- <div class="subtitle" v-if="subtitle && isAvatarReady">{{ subtitle }}</div> -->
    </div>

    <!-- 顶部栏 -->
    <div class="chat-header">
      <div class="mode-tabs">
        <div
          :class="['mode-tab', { active: chatMode === 'resource' }]"
          @click="switchMode('resource')"
        >
          <span class="mode-icon">✨</span>
          <span>资源生成</span>
        </div>
        <div
          :class="['mode-tab', { active: chatMode === 'qa' }]"
          @click="switchMode('qa')"
        >
          <span class="mode-icon">💬</span>
          <span>答疑解惑</span>
        </div>
      </div>
      <div class="header-actions">
        <div class="avatar-status" @click="toggleAvatar">
          <span :class="['status-dot', { ready: isAvatarReady, loading: isAvatarLoading }]"></span>
          <span class="status-text">{{ isAvatarReady ? '在线' : (isAvatarLoading ? '加载中' : '离线') }}</span>
        </div>
        <div class="settings-btn" @click="showAvatarSettings = !showAvatarSettings">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
        </div>
      </div>
    </div>

    <!-- 设置面板 -->
    <Transition name="slide-down">
      <div v-if="showAvatarSettings" class="settings-panel">
        <div class="setting-row">
          <label>形象</label>
          <select v-model="selectedAvatar" @change="onAvatarChange" class="setting-select">
            <option v-for="item in avatarOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
        </div>
        <div class="setting-row">
          <label>语音</label>
          <select v-model="selectedVoice" @change="onVoiceChange" class="setting-select">
            <option v-for="item in voiceOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
        </div>
      </div>
    </Transition>

    <!-- 聊天区域 -->
    <div class="chat-area">
      <div ref="scrollbarRef" class="chat-scroll">
        <!-- 加载更多（仅资源生成模式） -->
        <div v-if="hasMoreHistory && chatMode === 'resource'" class="load-more" @click="loadHistory">
          {{ isLoadingHistory ? '加载中...' : '点击加载更多历史记录' }}
        </div>

        <!-- 消息列表（按当前模式过滤显示） -->
        <div
          v-for="(item, index) in conversation"
          v-show="!item.mode || item.mode === chatMode"
          :key="index"
          :class="['message-item', item.type === 'user' ? 'msg-user' : 'msg-ai']"
        >
          <!-- AI 消息 -->
          <template v-if="item.type === 'ai'">
            <!-- 加载动画（仅在没有思考内容时显示） -->
            <div v-if="item.isLoading && !item.thinkingContent" class="ai-loading">
              <div class="loading-dots"><span></span><span></span><span></span></div>
              <span class="loading-text">AI正在思考...</span>
            </div>

            <div v-else>
              <!-- SSE 思考过程（资源生成模式，流式显示） -->
              <div
                v-if="item.mode === 'resource' && item.thinkingContent"
                class="thinking-section"
                :class="{ collapsed: !item.thinkingExpanded }"
              >
                <div class="thinking-header" @click="toggleThinking(index)">
                  <span class="thinking-label">
                    <span v-if="item.thinkingStreaming" class="thinking-spinner"></span>
                    {{ item.thinkingStreaming ? '思考中...' : '思考过程' }}
                  </span>
                  <span class="thinking-toggle">{{ item.thinkingExpanded ? '收起' : '展开' }}</span>
                </div>
                <div
                  v-if="item.thinkingExpanded"
                  class="thinking-content markdown-body"
                  :class="{ streaming: item.thinkingStreaming }"
                >
                  <div v-html="markdownToHtml(item.thinkingContent)"></div>
                  <span v-if="item.thinkingStreaming" class="thinking-cursor"></span>
                </div>
              </div>

              <!-- 文本内容（仅在结果返回后显示） -->
              <!-- 资源生成模式 -->
              <div
                v-if="item.mode === 'resource' && !item.isLoading"
                class="message-text"
                :class="{ typing: item.isTyping }"
                v-html="formatMessage(item.displayContent || item.content)"
              ></div>

              <!-- 答疑模式（Markdown HTML） -->
              <div
                v-else-if="item.mode === 'qa' && !item.isLoading"
                class="message-text markdown-body"
                :class="{ typing: item.isTyping }"
                v-html="item.contentHtml || item.content"
              ></div>

              <!-- 资源卡片（资源生成模式） -->
              <div v-if="item.resource && !item.isLoading" class="resource-card">
                <!-- 加载中 -->
                <div v-if="item.resource.status !== 2 && item.resource.status !== 3" class="resource-loading">
                  <div class="resource-spinner"></div>
                  <span>智能生成中</span>
                </div>
                <!-- 失败 -->
                <div v-else-if="item.resource.status === 3" class="resource-fail">
                  <span class="fail-icon">✕</span>
                  <span>生成失败，再尝试一次吧~</span>
                </div>
                <!-- 成功 -->
                <div v-else-if="item.resource.status === 2" class="resource-success">
                  <div class="resource-icon-box" :style="{ background: getResourceColor(item.rsType) + '22', color: getResourceColor(item.rsType) }">
                    {{ getResourceTypeName(item.rsType).charAt(0) }}
                  </div>
                  <div class="resource-info">
                    <div class="resource-type">{{ getResourceTypeName(item.rsType) }}</div>
                    <div class="resource-title">{{ item.resource.text }}</div>
                    <div class="resource-time">{{ item.resource.createTime }}</div>
                  </div>
                  <div class="resource-open" @click="openResource(item)">打开</div>
                </div>
              </div>

              <!-- 重新生成 -->
              <div
                v-if="item.resource && item.resource.status === 2 && item.isBatchGenerate !== true"
                class="recreate-btn"
                @click="reCreate(item.rsType, item.resource.taskId)"
              >
                重新生成
              </div>

              <!-- 图片（答疑模式） -->
              <div v-if="item.mode === 'qa' && item.showImages && item.images && item.images.length > 0" class="qa-images">
                <div
                  v-for="(img, imgIndex) in item.images"
                  :key="imgIndex"
                  class="qa-image-item"
                  @click="previewImage(getProxyUrl(img.image_url))"
                >
                  <img :src="getProxyUrl(img.image_url)" :alt="img.title" loading="lazy" referrerpolicy="no-referrer">
                </div>
              </div>

              <!-- 视频（答疑模式） -->
              <div v-if="item.mode === 'qa' && item.showToolResults && item.toolResults && item.toolResults.length > 0" class="qa-videos">
                <template v-for="(result, rIndex) in item.toolResults" :key="rIndex">
                  <template v-if="result.result && result.result.data">
                    <div
                      v-for="(video, vIndex) in result.result.data"
                      :key="vIndex"
                      class="qa-video-card"
                      @click="playVideo(video.url)"
                    >
                      <div class="video-preview">
                        <div class="video-play-icon">▶</div>
                        <span class="video-type-badge">{{ video.ext }}</span>
                      </div>
                      <div class="video-info">
                        <div class="video-title">{{ video.title }}</div>
                      </div>
                    </div>
                  </template>
                </template>
              </div>

              <!-- 来源（答疑模式） -->
              <div v-if="item.mode === 'qa' && item.showSourcesSection && item.sources && item.sources.length > 0" class="qa-sources">
                <div class="sources-toggle" @click="item.showSources = !item.showSources">
                  {{ item.showSources ? '收起来源' : '查看来源' }} ({{ item.sources.length }})
                </div>
                <Transition name="slide">
                  <div v-if="item.showSources" class="sources-list">
                    <a
                      v-for="(source, sIndex) in item.sources"
                      :key="sIndex"
                      :href="source.url"
                      target="_blank"
                      class="source-item"
                    >
                      <div class="source-title">{{ source.title }}</div>
                      <div class="source-snippet">{{ source.snippet }}</div>
                      <div class="source-type">{{ source.source_type }}</div>
                    </a>
                  </div>
                </Transition>
              </div>
            </div>
          </template>

          <!-- 用户消息 -->
          <div v-else class="user-text">{{ item.content }}</div>
        </div>
      </div>
    </div>

    <!-- 输入区域 -->
    <div class="input-area">
      <!-- 录音波形弹窗 -->
      <Transition name="waveform-slide">
        <div v-if="isRecording && isVoiceMode" class="waveform-popup">
          <canvas ref="waveformCanvas" class="waveform-canvas"></canvas>
          <div class="waveform-timer">
            <span class="recording-dot"></span>
            录音中 {{ recordingDuration }}s
          </div>
        </div>
      </Transition>

      <!-- 文本输入模式 -->
      <div v-if="!isVoiceMode" class="input-box">
        <input
          v-model="userInput"
          type="text"
          class="text-input"
          :placeholder="chatMode === 'resource' ? '输入想生成的内容...' : '输入您的问题...'"
          @keydown.enter="sendMessage"
          :disabled="isInputDisabled"
        />
        <button
          class="input-btn mic-btn"
          @click="switchToVoiceMode"
          :disabled="isInputDisabled"
        >
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
            <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
            <line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/>
          </svg>
        </button>
        <button
          class="input-btn send-btn"
          @click="sendMessage"
          :disabled="isInputDisabled || !userInput.trim()"
        >
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        </button>
      </div>

      <!-- 语音模式 -->
      <div v-else class="input-box voice-input-box">
        <button
          class="voice-record-btn"
          :class="{ recording: isRecording }"
          @click="toggleNativeRecording"
          :disabled="isInputDisabled"
        >
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
            <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
            <line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/>
          </svg>
          <span>{{ isRecording ? '点击停止录音' : '点击开始录音' }}</span>
        </button>
        <button
          class="input-btn keyboard-btn"
          @click="switchToInputMode"
        >
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="2" y="4" width="20" height="16" rx="2"/>
            <path d="M6 8h.01M10 8h.01M14 8h.01M18 8h.01M6 12h.01M10 12h.01M14 12h.01M18 12h.01M7 16h10"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- 视频播放器 -->
    <Transition name="fade">
      <div v-if="showVideoPlayer" class="video-player-mask" @click="closeVideoPlayer">
        <div class="video-player-content" @click.stop>
          <button class="video-close" @click="closeVideoPlayer">
            <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
          <video :src="videoPlayUrl" controls autoplay class="video-element"></video>
        </div>
      </div>
    </Transition>

    <!-- 冲突弹窗 -->
    <Transition name="fade">
      <div v-if="showConflictDialog" class="conflict-mask" @click="showConflictDialog = false">
        <div class="conflict-dialog" @click.stop>
          <div class="conflict-header">
            <span>⚠️ 温馨提示</span>
          </div>
          <div class="conflict-content" v-html="formatConflictMessage(conflictData.suggestionWarning)"></div>
          <div class="conflict-footer">
            <button class="conflict-btn reject" @click="handleConflictOption(false)">拒绝</button>
            <button class="conflict-btn accept" @click="handleConflictOption(true)">接受</button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.chat-page {
  position: relative;
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  box-sizing: border-box;
  overflow: hidden;
}

/* ===== 数字人全屏背景 ===== */
.avatar-bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  background: var(--bg-page);
}

.avatar-container {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  margin-top: 35px;
}

.avatar-container.hidden {
  visibility: hidden;
  opacity: 0;
}

.avatar-placeholder {
  position: absolute;
  top: 150px;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: var(--text-gray);
  font-size: 13px;
  cursor: pointer;
}

.avatar-loading {
  position: absolute;
  top: 150px;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  color: var(--text-gray);
  font-size: 13px;
}

.loading-spinner {
  width: 36px;
  height: 36px;
  border: 3px solid var(--border-color);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.subtitle {
  position: absolute;
  bottom: 60px;
  left: 50%;
  transform: translateX(-50%);
  max-width: 90%;
  padding: 4px 12px;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  font-size: 13px;
  border-radius: 16px;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  z-index: 1;
}

/* ===== 顶部栏（半透明覆盖） ===== */
.chat-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.75);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.3);
  flex-shrink: 0;
}

.mode-tabs {
  display: flex;
  gap: 6px;
  background: var(--bg-hover);
  border-radius: 20px;
  padding: 3px;
}

.mode-tab {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 14px;
  border-radius: 18px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-gray);
  cursor: pointer;
  transition: all 0.25s ease;
  white-space: nowrap;
}

.mode-tab.active {
  background: var(--grad-primary);
  color: #fff;
  box-shadow: 0 2px 8px rgba(45, 125, 219, 0.3);
}

.mode-icon {
  font-size: 14px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.avatar-status {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-gray);
  cursor: pointer;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #94a3b8;
}

.status-dot.ready {
  background: #22c55e;
  box-shadow: 0 0 6px rgba(34, 197, 94, 0.5);
  animation: pulse 2s infinite;
}

.status-dot.loading {
  background: #f59e0b;
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.settings-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  color: var(--text-gray);
  cursor: pointer;
  transition: all 0.2s;
}

.settings-btn:active {
  background: var(--bg-hover);
}

/* ===== 设置面板（半透明覆盖） ===== */
.settings-panel {
  position: fixed;
  top: 55px;
  left: 0;
  right: 0;
  z-index: 10;
  background: rgba(255, 255, 255, 0.75);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.3);
  padding: 12px 16px;
  display: flex;
  gap: 12px;
  flex-shrink: 0;
}

.setting-row {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.setting-row label {
  font-size: 12px;
  color: var(--text-gray);
}

.setting-select {
  padding: 6px 10px;
  border: 1px solid rgba(255, 255, 255, 0.4);
  border-radius: 8px;
  font-size: 13px;
  background: rgba(255, 255, 255, 0.6);
  color: var(--text-body);
}

/* ===== 聊天区域（透明背景，覆盖数字人下半部分） ===== */
.chat-area {
  position: fixed;
  bottom: 110px;
  left: 0;
  right: 0;
  z-index: 5;
  /* flex: 0 1 45vh; */
  max-height: 45vh;
  /* margin-top: auto; */
  /* margin-bottom: 50px; */
  min-height: 0;
  overflow: hidden;
  padding: 8px 0;
  background: transparent;
  /* border: 1px solid red; */
}


.chat-scroll {
  height: 45vh;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: 0 12px;
  background: transparent;
  /* 上下渐变消失 */
  -webkit-mask-image: linear-gradient(to bottom, rgba(0,0,0,0.5) 0, #000 16px, #000 calc(100% - 16px), rgba(0,0,0,0.5) 100%);
  mask-image: linear-gradient(to bottom, rgba(0,0,0,0.5) 0, #000 16px, #000 calc(100% - 16px), rgba(0,0,0,0.5) 100%);
}

/* 自定义滚动条 */
.chat-scroll::-webkit-scrollbar {
  width: 3px;
}
.chat-scroll::-webkit-scrollbar-track {
  background: transparent;
}
.chat-scroll::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.12);
  border-radius: 3px;
}
.chat-scroll::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.2);
}

.load-more {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin: 0 auto 12px;
  padding: 8px 20px;
  font-size: 13px;
  font-weight: 500;
  color: var(--primary);
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.5);
  border-radius: 20px;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  width: fit-content;
}

.load-more:active {
  transform: scale(0.96);
  box-shadow: 0 4px 12px rgba(45, 125, 219, 0.15);
}

.message-item {
  margin-bottom: 14px;
  animation: msgIn 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes msgIn {
  from { opacity: 0; transform: translateY(10px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.msg-ai {
  display: flex;
  justify-content: flex-start;
}

.msg-user {
  display: flex;
  justify-content: flex-end;
}

/* AI 消息气泡 */
.msg-ai > template,
.msg-ai > div {
  max-width: 85%;
}

.ai-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-radius: 16px 16px 16px 4px;
  border: 1px solid rgba(255, 255, 255, 0.5);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.loading-dots {
  display: flex;
  gap: 4px;
}

.loading-dots span {
  width: 7px;
  height: 7px;
  background: var(--primary);
  border-radius: 50%;
  animation: dotBounce 1.4s infinite ease-in-out both;
}

.loading-dots span:nth-child(1) { animation-delay: -0.32s; }
.loading-dots span:nth-child(2) { animation-delay: -0.16s; }

@keyframes dotBounce {
  0%, 80%, 100% { transform: scale(0); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

.loading-text {
  font-size: 13px;
  color: var(--text-gray);
}

/* 思考过程 */
.thinking-section {
  margin-bottom: 8px;
  background: rgba(255, 255, 255, 0.5);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.4);
}

.thinking-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  cursor: pointer;
  transition: background 0.2s;
}

.thinking-header:active {
  background: rgba(0, 0, 0, 0.03);
}

.thinking-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-gray);
  font-weight: 500;
}

.thinking-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid var(--border-color);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.thinking-toggle {
  font-size: 12px;
  color: var(--primary);
}

.thinking-content {
  padding: 0 12px 10px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-gray);
  word-break: break-word;
  /* 思考结束后：固定高度 + 滚动条 */
  max-height: 200px;
  overflow-y: auto;
}

/* 思考内容 markdown 段落间距压缩 */
.thinking-content.markdown-body p {
  margin: 2px 0;
}
.thinking-content.markdown-body h1,
.thinking-content.markdown-body h2,
.thinking-content.markdown-body h3,
.thinking-content.markdown-body h4,
.thinking-content.markdown-body h5,
.thinking-content.markdown-body h6 {
  margin: 6px 0 2px;
}
.thinking-content.markdown-body ul,
.thinking-content.markdown-body li {
  margin: 1px 0;
}

/* 流式输出中：无固定高度，无滚动条，自然增长 */
.thinking-content.streaming {
  max-height: none;
  overflow-y: visible;
}

/* 思考内容滚动条 */
.thinking-content::-webkit-scrollbar {
  width: 3px;
}
.thinking-content::-webkit-scrollbar-track {
  background: transparent;
}
.thinking-content::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.1);
  border-radius: 3px;
}

/* 流式光标 */
.thinking-cursor {
  display: inline-block;
  width: 2px;
  height: 14px;
  background: var(--primary);
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: thinking-blink 1s infinite;
}

@keyframes thinking-blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

/* 消息文本 */
.message-text {
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-radius: 16px 16px 16px 4px;
  border: 1px solid rgba(255, 255, 255, 0.5);
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-body);
  word-break: break-word;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.message-text.typing::after {
  content: '|';
  animation: blink 1s infinite;
  color: var(--primary);
  font-weight: bold;
  margin-left: 2px;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

/* Markdown 样式 */
.markdown-body :deep(p) { margin: 4px 0; }
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) { margin: 8px 0 4px; font-weight: 600; }
.markdown-body :deep(h1) { font-size: 16px; }
.markdown-body :deep(h2) { font-size: 15px; }
.markdown-body :deep(h3) { font-size: 14px; }
.markdown-body :deep(ul) { padding-left: 18px; margin: 4px 0; }
.markdown-body :deep(li) { margin: 2px 0; }
.markdown-body :deep(code) {
  background: var(--bgc-light);
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 12px;
}
.markdown-body :deep(strong) { font-weight: 600; }
.markdown-body :deep(a) { color: var(--primary); text-decoration: none; }
.markdown-body :deep(blockquote) {
  border-left: 3px solid var(--primary);
  padding-left: 8px;
  margin: 4px 0;
  color: var(--text-gray);
}
.markdown-body :deep(img) { max-width: 100%; border-radius: 8px; margin: 6px 0; }

/* 资源卡片 */
.resource-card {
  margin-top: 8px;
}

.resource-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px;
  background: var(--bg-card);
  border-radius: 12px;
  border: 1px solid var(--border-color);
}

.resource-spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--border-color);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  flex-shrink: 0;
}

.resource-loading span {
  font-size: 13px;
  color: var(--text-gray);
}

.resource-fail {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 16px;
  background: var(--main-shadow);
  border-radius: 12px;
  color: var(--main-delete-hover);
  font-size: 13px;
}

.fail-icon {
  font-size: 24px;
  font-weight: bold;
}

.resource-success {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.5);
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.resource-success:active {
  transform: scale(0.97);
  border-color: var(--primary);
  box-shadow: 0 4px 16px rgba(45, 125, 219, 0.15);
}

.resource-icon-box {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 700;
  flex-shrink: 0;
}

.resource-info {
  flex: 1;
  min-width: 0;
}

.resource-type {
  font-size: 12px;
  color: var(--text-gray);
}

.resource-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-title);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.resource-time {
  font-size: 11px;
  color: var(--text-gray);
}

.resource-open {
  padding: 4px 10px;
  background: var(--grad-primary);
  color: #fff;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  flex-shrink: 0;
}

.recreate-btn {
  text-align: center;
  margin-top: 6px;
  font-size: 12px;
  color: white;
  cursor: pointer;
}

.recreate-btn:active {
  color: var(--primary);
}

/* 答疑模式：图片 */
.qa-images {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.qa-image-item {
  width: calc(50% - 3px);
  aspect-ratio: 1;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
}

.qa-image-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* 答疑模式：视频 */
.qa-videos {
  margin-top: 8px;
}

.qa-video-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.5);
  margin-bottom: 6px;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.qa-video-card:active {
  border-color: var(--primary);
}

.video-preview {
  position: relative;
  width: 64px;
  height: 40px;
  background: #000;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.video-play-icon {
  color: #fff;
  font-size: 18px;
}

.video-type-badge {
  position: absolute;
  top: 2px;
  left: 2px;
  padding: 1px 4px;
  background: rgba(45, 125, 219, 0.9);
  color: #fff;
  font-size: 9px;
  border-radius: 3px;
}

.video-info {
  flex: 1;
  min-width: 0;
}

.video-title {
  font-size: 13px;
  color: var(--text-title);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 答疑模式：来源 */
.qa-sources {
  margin-top: 8px;
}

.sources-toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 12px;
  background: rgba(45, 125, 219, 0.15);
  border: 1px solid rgba(45, 125, 219, 0.3);
  border-radius: 14px;
  font-size: 12px;
  font-weight: 500;
  color: var(--primary-fade);
  cursor: pointer;
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
}

.sources-list {
  margin-top: 6px;
}

.source-item {
  display: block;
  padding: 8px;
  background: var(--bg-card);
  border-radius: 8px;
  border: 1px solid var(--border-color);
  margin-bottom: 4px;
  text-decoration: none;
}

.source-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-title);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.source-snippet {
  font-size: 11px;
  color: var(--text-gray);
  display: -webkit-box;
  line-clamp: 2;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin-top: 2px;
}

.source-type {
  display: inline-block;
  margin-top: 4px;
  padding: 1px 6px;
  background: var(--bgc-light);
  color: var(--text-gray);
  font-size: 10px;
  border-radius: 4px;
}

/* 用户消息 */
.user-text {
  max-width: 80%;
  padding: 10px 14px;
  background: var(--grad-primary);
  color: #fff;
  border-radius: 16px 16px 4px 16px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
  box-shadow: 0 3px 12px rgba(45, 125, 219, 0.3);
}

/* ===== 输入区域（半透明覆盖） ===== */
.input-area {
  position: fixed;
  bottom: 50px;
  left: 0;
  right: 0;
  z-index: 10;
  flex-shrink: 0;
  padding: 8px 12px;
  padding-bottom: calc(8px + env(safe-area-inset-bottom, 0px));
  background: rgba(255, 255, 255, 0.75);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-top: 1px solid rgba(255, 255, 255, 0.3);
}

/* ===== 录音波形弹窗 ===== */
.waveform-popup {
  width: 100%;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-radius: 12px 12px 0 0;
  padding: 12px 16px;
  box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.08);
  position: absolute;
  bottom: 100%;
  left: 0;
  right: 0;
  z-index: 10;
}

.waveform-canvas {
  width: 100%;
  height: 50px;
  background: rgba(45, 125, 219, 0.08);
  border-radius: 10px;
  border: 1px solid rgba(45, 125, 219, 0.15);
}

.waveform-timer {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin-top: 6px;
  color: var(--text-gray);
  font-size: 13px;
  font-weight: 500;
}

.recording-dot {
  width: 8px;
  height: 8px;
  background: var(--main-delete);
  border-radius: 50%;
  animation: pulse 1s infinite ease-in-out;
}

/* ===== 语音输入框模式 ===== */
.voice-input-box {
  justify-content: center;
  gap: 10px;
}

.voice-record-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 24px;
  background: var(--grad-primary);
  border: none;
  border-radius: 22px;
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 2px 8px rgba(45, 125, 219, 0.3);
}

.voice-record-btn:active:not(:disabled) {
  transform: scale(0.96);
}

.voice-record-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.voice-record-btn.recording {
  background: var(--main-delete);
  animation: pulse 1.5s infinite ease-in-out;
  box-shadow: 0 2px 8px rgba(245, 108, 108, 0.3);
}

.keyboard-btn {
  background: var(--bg-hover);
  color: var(--text-gray);
}

/* ===== 波形动画 ===== */
.waveform-slide-enter-active {
  animation: waveform-slide-in 0.3s ease-out;
}

.waveform-slide-leave-active {
  animation: waveform-slide-in 0.2s ease-in reverse;
}

@keyframes waveform-slide-in {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

.input-box {
  display: flex;
  align-items: center;
  gap: 8px;
}

.text-input {
  flex: 1;
  height: 40px;
  padding: 0 14px;
  border: 1px solid rgba(255, 255, 255, 0.4);
  border-radius: 20px;
  font-size: 14px;
  background: rgba(255, 255, 255, 0.6);
  color: var(--text-body);
  outline: none;
  transition: border-color 0.2s;
}

.text-input:focus {
  border-color: var(--primary);
}

.text-input:disabled {
  opacity: 0.5;
}

.input-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 50%;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.2s;
}

.input-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.input-btn:active:not(:disabled) {
  transform: scale(0.92);
}

.mic-btn {
  background: var(--primary-fade);
  color: var(--primary);
}

.mic-btn.recording {
  background: var(--main-delete);
  color: #fff;
  animation: pulse 1s infinite;
}

.send-btn {
  background: var(--grad-primary);
  color: #fff;
  box-shadow: 0 2px 8px rgba(45, 125, 219, 0.3);
}

.avatar-required-tip {
  text-align: center;
  padding: 8px;
  font-size: 12px;
  color: var(--text-gray);
}

/* ===== 视频播放器 ===== */
.video-player-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.video-player-content {
  position: relative;
  width: 95%;
  max-width: 800px;
}

.video-close {
  position: absolute;
  top: -40px;
  right: 0;
  width: 36px;
  height: 36px;
  background: rgba(255, 255, 255, 0.2);
  border: none;
  border-radius: 50%;
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.video-element {
  width: 100%;
  max-height: 80vh;
  border-radius: 12px;
}

/* ===== 冲突弹窗 ===== */
.conflict-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: 20px;
}

.conflict-dialog {
  background: var(--bg-card);
  border-radius: 12px;
  padding: 20px;
  width: 100%;
  max-width: 360px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.conflict-header {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-title);
  margin-bottom: 12px;
}

.conflict-content {
  font-size: 14px;
  color: var(--text-body);
  line-height: 1.6;
  margin-bottom: 16px;
  padding: 12px;
  background: var(--bg-page);
  border-radius: 8px;
}

.conflict-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.conflict-btn {
  padding: 8px 20px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
}

.conflict-btn.reject {
  background: var(--bg-hover);
  color: var(--text-gray);
}

.conflict-btn.accept {
  background: var(--primary);
  color: #fff;
}

/* ===== 过渡动画 ===== */
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.25s ease;
  overflow: hidden;
}

.slide-down-enter-from,
.slide-down-leave-to {
  max-height: 0;
  opacity: 0;
  padding-top: 0;
  padding-bottom: 0;
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.25s ease;
  overflow: hidden;
}

.slide-up-enter-from,
.slide-up-leave-to {
  max-height: 0;
  opacity: 0;
}

.slide-enter-active,
.slide-leave-active {
  transition: all 0.25s ease;
  overflow: hidden;
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  max-height: 0;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* ===== 夜间模式 ===== */
.dark .chat-header,
.dark .settings-panel,
.dark .input-area {
  background: rgba(30, 30, 30, 0.75);
  border-color: rgba(255, 255, 255, 0.1);
}

.dark .text-input {
  background: rgba(60, 60, 60, 0.6);
  border-color: rgba(255, 255, 255, 0.15);
}

.dark .chat-area::before {
  background: linear-gradient(to bottom, rgba(20, 20, 20, 0.5), transparent);
}

.dark .message-text,
.dark .ai-loading,
.dark .resource-success,
.dark .qa-video-card,
.dark .source-item {
  background: rgba(40, 40, 40, 0.72);
  border-color: rgba(255, 255, 255, 0.1);
}

.dark .thinking-section {
  background: rgba(40, 40, 40, 0.5);
  border-color: rgba(255, 255, 255, 0.08);
}

.dark .chat-scroll::-webkit-scrollbar-thumb,
.dark .thinking-content::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.15);
}
</style>
