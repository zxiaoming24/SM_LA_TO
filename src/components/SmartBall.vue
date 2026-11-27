<!-- 智能球/小数字人 -->

<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { smartBallChatApi, reportPageContextApi, onlineRemindApi } from '@/api/mainApi/smartBall.js'
import emitter from '@/utils/emitter'
import { DigitalHumanBall } from '@/utils/digitalHumanBall.js'
import { ASR } from '@/utils/asr.js'
import { DotLottieVue } from '@lottiefiles/dotlottie-vue'
import SiriLottie from '@/assets/icon/Siri.lottie'

const props = defineProps({
  userId: { type: String, required: true },
  currentPath: { type: String, default: '' },
  currentName: { type: String, default: '' }
})

const AVATAR_CONFIG = {
  serverUrl: import.meta.env.VITE_AVATAR_SERVER_URL,
  appId: import.meta.env.VITE_AVATAR_APP_ID,
  apiKey: import.meta.env.VITE_AVATAR_API_KEY,
  apiSecret: import.meta.env.VITE_AVATAR_API_SECRET,
  sceneId: import.meta.env.VITE_AVATAR_SCENE_ID,
}

const avatarOptions = [
  { value: '110332017', label: '女老师' },
  { value: '111286001', label: '男老师' },
]
const voiceOptions = [
  { value: 'x4_lingxiaoyue_oral', label: '聆小媛' },
  { value: 'x4_yuexiaoni_assist', label: '月小妮' },
  { value: 'x4_chaoge', label: '超哥' },
]
const pageNames = {
  index: '首页', draw: '个人画像', pathPlan: '学习计划', evaluate: '学习评估',
  userCenter: '个人中心', wrongQuestions: '错题本', partners: '学伴',
  aiAnswer: 'AI智能答疑', ppt: 'PPT', mindMap: '思维导图', word: '讲解文档',
  reading: '阅读', code: '代码练习', video: '视频', anima: '动画',
  paper: '试卷页', resource: '资源中心'
}

const mode = ref('ball')
const smartBallVisible = ref(false)
const smartBallMessages = ref([])
const smartBallInput = ref('')
const currentTypingIndex = ref(-1)

// 播放提示音（Web Audio API）
const playNotifySound = () => {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.type = 'sine'
    osc.frequency.setValueAtTime(880, ctx.currentTime)
    osc.frequency.setValueAtTime(660, ctx.currentTime + 0.1)
    gain.gain.setValueAtTime(0.3, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3)
    osc.start(ctx.currentTime)
    osc.stop(ctx.currentTime + 0.3)
  } catch (e) { /* 静默失败 */ }
}
const smartBallLoading = ref(false)
const isThinking = ref(false)
const currentContext = ref(null)
let lastReportedContext = ''
let onlineRemindTimer = null
const lastRemindText = ref('')

const fetchOnlineRemind = async () => {
  if (!props.userId) return
  try {
    const response = await onlineRemindApi(props.userId)
    if (response.code === 1 && response.data?.success && response.data?.message?.text) {
      const text = response.data.message.text
      lastRemindText.value = text
      playNotifySound()
      await showReplyBubble(text)
      await addAiMessageWithTypewriter(text)
      if (mode.value === 'human' && isAvatarReady.value && digitalHuman) {
        await digitalHuman.doAction(humanAction.value[0])
        await digitalHuman.speak(text, { voiceId: selectedVoice.value })
      }
    }
  } catch (error) {
    console.error('获取问候信息失败:', error)
  }
}

const avatarContainer = ref(null)
const selectedAvatar = ref('110332017')
const selectedVoice = ref('x4_lingxiaoyue_oral')
const isAvatarReady = ref(false)
const isAvatarLoading = ref(false)
const isAvatarSpeaking = ref(false)
const humanAction = ref(['A_RH_hello_O','A_RLH_emphasize_O','A_U_No_pointing_O'])
const showBallMenu = ref(false)
const showAvatarToolbar = ref(false)
const showAvatarSettings = ref(false)
const isRecording = ref(false)
const recordingDuration = ref(0)

const showGameInvitation = ref(false)
const showGameModal = ref(false)
const gameHtml = ref('')
const gameTitle = ref('')
const gameUrl = ref('')

// 工具栏延迟隐藏
let toolbarHideTimer = null

// 回复气泡（优先左侧）
const lastReply = ref('')
const bubbleVisible = ref(false)
const wrapperRef = ref(null)
const bubbleSide = ref('left')
let bubbleTimeout = null
let bubbleTypewriterTimer = null

// 工具栏方向（bottom/top）
const toolbarDirection = ref('bottom')

// 聊天面板方向（bottom-left 优先，然后 top-left / top-right / bottom-right）
const panelPosition = ref('bottom-left')

let hasDragged = false
let dragStartPos = { x: 0, y: 0 }

let recordingTimer = null
let asrInstance = null
let digitalHuman = null

// 初始位置：右下角
const posX = ref(window.innerWidth - 85)
const posY = ref(window.innerHeight - 180)
const isDragging = ref(false)
const dragOffset = ref({ x: 0, y: 0 })

const typewriterDisplayText = async (index, content) => {
  const fullText = content
  let currentIndex = 0

  return new Promise((resolve) => {
    const timer = setInterval(() => {
      currentIndex++
      const displayText = fullText.substring(0, currentIndex)

      if (smartBallMessages.value[index]) {
        smartBallMessages.value[index] = {
          ...smartBallMessages.value[index],
          content: displayText,
          isTyping: currentIndex < fullText.length
        }
      }

      if (currentIndex % 10 === 0) {
        nextTick(() => {
          const chatContainer = document.querySelector('.smart-ball-chat-container')
          if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight
        })
      }

      if (currentIndex >= fullText.length) {
        clearInterval(timer)
        if (smartBallMessages.value[index]) {
          smartBallMessages.value[index] = {
            ...smartBallMessages.value[index],
            isTyping: false,
            content: fullText
          }
        }
        currentTypingIndex.value = -1
        resolve(fullText)
      }
    }, 30)
  })
}

const typewriterDisplayHtml = async (index, fullHtml, originalContent) => {
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
        if (tagEnd !== -1) {
          currentIndex = tagEnd + 1
        } else {
          currentIndex++
        }
      } else {
        currentIndex++
      }

      const displayHtml = fullHtml.substring(0, currentIndex)

      if (smartBallMessages.value[index]) {
        smartBallMessages.value[index] = {
          ...smartBallMessages.value[index],
          contentHtml: displayHtml,
          isTyping: currentIndex < htmlLength
        }
      }

      if (currentIndex % 10 === 0) {
        nextTick(() => {
          const chatContainer = document.querySelector('.smart-ball-chat-container')
          if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight
        })
      }
    }, 25)
  })
}

const addAiMessageWithTypewriter = async (content, images = [], sources = [], toolResults = []) => {
  const message = {
    role: 'assistant',
    content: '',
    contentHtml: '',
    isTyping: true,
    images: images,
    sources: sources,
    toolResults: toolResults,
    showSources: false,
    showImages: false,
    showToolResults: false,
    showSourcesSection: false
  }

  const index = smartBallMessages.value.length
  smartBallMessages.value.push(message)
  currentTypingIndex.value = index

  await nextTick()
  const chatContainer = document.querySelector('.smart-ball-chat-container')
  if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight

  const fullHtml = markdownToHtml(content)
  await typewriterDisplayHtml(index, fullHtml, content)
  
  // 文字流式输出完成，直接修改属性（保持响应式）
  if (smartBallMessages.value[index]) {
    smartBallMessages.value[index].content = content
    smartBallMessages.value[index].contentHtml = fullHtml
    smartBallMessages.value[index].isTyping = false
  }

  // 依次显示：图片 → 视频 → 来源
  if (images && images.length > 0) {
    await new Promise(r => setTimeout(r, 300))
    if (smartBallMessages.value[index]) {
      smartBallMessages.value[index].showImages = true
    }
  }

  if (toolResults && toolResults.length > 0) {
    await new Promise(r => setTimeout(r, 300))
    if (smartBallMessages.value[index]) {
      smartBallMessages.value[index].showToolResults = true
    }
  }

  if (sources && sources.length > 0) {
    await new Promise(r => setTimeout(r, 300))
    if (smartBallMessages.value[index]) {
      smartBallMessages.value[index].showSourcesSection = true
    }
  }

  await nextTick()
  const container = document.querySelector('.smart-ball-chat-container')
  if (container) container.scrollTop = container.scrollHeight
  
  return content
}

const getPageContext = () => {
  const path = props.currentPath || '/'
  const segments = path.split('/').filter(s => s)
  const page = segments[0] || 'index'
  const title = pageNames[page] || page
  return { page, title, action: 'viewing', detail: '' }
}

const handleContextDetail = (detailData) => {
  if (!currentContext.value) currentContext.value = getPageContext()
  if (detailData.detail !== undefined) currentContext.value.detail = detailData.detail
  if (detailData.page) currentContext.value.page = detailData.page
  if (detailData.title) currentContext.value.title = detailData.title
  if (detailData.action) currentContext.value.action = detailData.action
  reportPageContext()
}

const reportPageContext = async () => {
  const context = currentContext.value || getPageContext()
  const contextStr = JSON.stringify(context)
  if (contextStr === lastReportedContext) return
  lastReportedContext = contextStr
  try {
    await reportPageContextApi({
      user_id: props.userId, page: context.page, title: context.title,
      action: context.action, detail: context.detail
    })
    currentContext.value = context
  } catch (error) {
    console.error('上报页面上下文失败:', error)
  }
}

const initDigitalHuman = () => {
  if (digitalHuman) { digitalHuman.destroy(); digitalHuman = null }
  digitalHuman = new DigitalHumanBall(AVATAR_CONFIG)
  digitalHuman.setAvatar(selectedAvatar.value)
  digitalHuman.setVoice(selectedVoice.value)
  digitalHuman
    .on('connected', () => { isAvatarReady.value = true; isAvatarLoading.value = false })
    .on('disconnected', () => { isAvatarReady.value = false; isAvatarLoading.value = false })
    .on('error', () => { isAvatarLoading.value = false })
    .on('playing', () => { isAvatarSpeaking.value = true })
  return digitalHuman
}

const startAvatar = async () => {
  if (!digitalHuman) initDigitalHuman()
  if (isAvatarReady.value) return
  isAvatarLoading.value = true
  try {
    await digitalHuman.start(avatarContainer.value, {
      avatarId: selectedAvatar.value, voiceId: selectedVoice.value, air: 1,
    })
    isAvatarLoading.value = false
  } catch (e) {
    isAvatarLoading.value = false; isAvatarReady.value = false
  }
}

const stopAvatar = async () => {
  if (!digitalHuman) return
  try { await digitalHuman.stop(); isAvatarReady.value = false; isAvatarLoading.value = false }
  catch (e) { console.error('停止数字人失败:', e) }
}

const interruptAvatar = async () => {
  if (!digitalHuman || !isAvatarReady.value) return
  try { await digitalHuman.interrupt() } catch (e) { console.error('打断失败:', e) }
  
  if (currentTypingIndex.value >= 0 && currentTypingIndex.value < smartBallMessages.value.length) {
    const item = smartBallMessages.value[currentTypingIndex.value]
    if (item && item.isTyping) {
      item.isTyping = false
      currentTypingIndex.value = -1
    }
  }
  
  if (bubbleTypewriterTimer) {
    clearInterval(bubbleTypewriterTimer)
    bubbleTypewriterTimer = null
  }
}

// 显示回复气泡
const showReplyBubble = async (text) => {
  if (bubbleTypewriterTimer) {
    clearInterval(bubbleTypewriterTimer)
    bubbleTypewriterTimer = null
  }
  
  lastReply.value = ''
  bubbleVisible.value = true
  
  nextTick(() => {
    const ballWidth = mode.value === 'human' ? 260 : 60
    const spaceLeft = posX.value
    const spaceRight = window.innerWidth - posX.value - ballWidth
    bubbleSide.value = spaceLeft > 200 ? 'left' : (spaceRight > 200 ? 'right' : 'left')
  })
  
  if (bubbleTimeout) clearTimeout(bubbleTimeout)
  
  const fullText = text
  let currentIndex = 0
  
  bubbleTypewriterTimer = setInterval(() => {
    currentIndex++
    const displayText = fullText.substring(0, currentIndex)
    lastReply.value = displayText
    
    if (currentIndex >= fullText.length) {
      clearInterval(bubbleTypewriterTimer)
      bubbleTypewriterTimer = null
      bubbleTimeout = setTimeout(() => { bubbleVisible.value = false }, 60000)
    }
  }, 30)
}

// 检测工具栏方向
const updateToolbarDirection = () => {
  const spaceBottom = window.innerHeight - posY.value - 260
  toolbarDirection.value = spaceBottom > 180 ? 'bottom' : 'top'
}

// 检测聊天面板方向（优先左下，然后左上、右上、右下）
const PANEL_W = 380, PANEL_H = 480, BALL_SIZE = 60, GAP = 10
const updatePanelDirection = () => {
  const x = posX.value, y = posY.value
  const vw = window.innerWidth, vh = window.innerHeight
  const spaceLeft = x + BALL_SIZE / 2
  const spaceRight = vw - x - BALL_SIZE / 2
  const spaceBottom = vh - y - BALL_SIZE - GAP
  const spaceTop = y

  // 优先 bottom-left
  if (spaceLeft >= PANEL_W && spaceBottom >= PANEL_H) {
    panelPosition.value = 'bottom-left'
  } else if (spaceLeft >= PANEL_W && spaceTop >= PANEL_H) {
    // top-left
    panelPosition.value = 'top-left'
  } else if (spaceRight >= PANEL_W && spaceTop >= PANEL_H) {
    // top-right
    panelPosition.value = 'top-right'
  } else if (spaceRight >= PANEL_W && spaceBottom >= PANEL_H) {
    // bottom-right
    panelPosition.value = 'bottom-right'
  } else {
    panelPosition.value = 'bottom-left'
  }
}

const sendSmartBallMessage = async () => {
  if (!smartBallInput.value.trim()) return
  const userMessage = { role: 'user', content: smartBallInput.value.trim() }
  smartBallMessages.value.push(userMessage)
  smartBallInput.value = ''
  smartBallLoading.value = true
  
  // 显示思考气泡
  if (mode.value === 'human') {
    isThinking.value = true
    await interruptAvatar()
  }

  try {
    const response = await smartBallChatApi({
      user_id: props.userId,
      user_input: userMessage.content,
      page_context: currentContext.value || getPageContext(),
      enable_tts: mode.value === 'human'
    })
    if (response.success && response.data) {
      const reply = response.data.reply || response.data.message || '嗯？'
      const images = response.data.images || []
      const sources = response.data.sources || []
      const toolResults = response.data.tool_results || []
      
      await addAiMessageWithTypewriter(reply, images, sources, toolResults)
      
      playNotifySound()
      if (mode.value === 'human' && isAvatarReady.value) {
        isThinking.value = false
        await digitalHuman.doAction(humanAction.value[0])
        await digitalHuman.speak(reply, { voiceId: selectedVoice.value })
        showReplyBubble(reply)
      } else if (mode.value === 'ball' && !smartBallVisible.value) {
        showReplyBubble(reply)
      }
    }
  } catch (error) {
    await addAiMessageWithTypewriter('网络有点问题，稍后再试吧')
  } finally {
    smartBallLoading.value = false
    isThinking.value = false
    nextTick(() => {
      const chatContainer = document.querySelector('.smart-ball-chat-container')
      if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight
    })
  }
}

const handleSmartBallKeydown = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendSmartBallMessage() }
}

const toggleRecording = async () => {
  if (mode.value === 'human') await interruptAvatar()
  try {
    if (isRecording.value) {
      if (asrInstance) {
        await asrInstance.stopAndRecognize()
      } else {
        if (recordingTimer) { clearInterval(recordingTimer); recordingTimer = null }
        isRecording.value = false; recordingDuration.value = 0
      }
      return
    }
    if (!ASR.isSupported()) { alert('当前浏览器不支持录音功能'); return }
    asrInstance = new ASR({
      sampleRate: 16000, echoCancellation: true, noiseSuppression: true, convertToSimplified: true,
      onStart: () => {
        isRecording.value = true; recordingDuration.value = 0
        recordingTimer = setInterval(() => { recordingDuration.value++ }, 1000)
      },
      onStop: () => {
        if (recordingTimer) { clearInterval(recordingTimer); recordingTimer = null }
        isRecording.value = false
      },
      onResult: (text) => { if (text && text.trim()) smartBallInput.value = text },
      onError: (error) => {
        console.error('ASR 错误:', error)
        if (recordingTimer) { clearInterval(recordingTimer); recordingTimer = null }
        isRecording.value = false; recordingDuration.value = 0
      }
    })
    await asrInstance.startRecording()
  } catch (e) {
    console.error('语音识别失败:', e)
    if (recordingTimer) { clearInterval(recordingTimer); recordingTimer = null }
    isRecording.value = false; recordingDuration.value = 0
    if (asrInstance) { try { asrInstance.cancel() } catch (ce) { console.error('清理ASR失败:', ce) }; asrInstance = null }
  }
}

const switchMode = (newMode) => {
  if (newMode === mode.value) return
  if (mode.value === 'human' && digitalHuman) stopAvatar()
  mode.value = newMode
  showBallMenu.value = false
  showAvatarToolbar.value = false
  smartBallVisible.value = false
  showAvatarSettings.value = false
  bubbleVisible.value = false
  clampPosition()
  if (newMode === 'human') {
    nextTick(() => { if (!isAvatarReady.value) { initDigitalHuman(); startAvatar() } })
  }
}

// 限制位置不超出视口
const clampPosition = () => {
  const w = mode.value === 'human' ? 220 : 60
  const h = mode.value === 'human' ? 280 : 60
  posX.value = Math.max(0, Math.min(window.innerWidth - w, posX.value))
  posY.value = Math.max(0, Math.min(window.innerHeight - h, posY.value))
}

const startDrag = (e) => {
  isDragging.value = true
  showBallMenu.value = false; showAvatarToolbar.value = false
  const clientX = e.clientX || e.touches?.[0]?.clientX || 0
  const clientY = e.clientY || e.touches?.[0]?.clientY || 0
  dragOffset.value = { x: clientX - posX.value, y: clientY - posY.value }
  dragStartPos = { x: clientX, y: clientY }
  hasDragged = false
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
  document.addEventListener('touchmove', onDrag)
  document.addEventListener('touchend', stopDrag)
}

const onDrag = (e) => {
  if (!isDragging.value) return
  const clientX = e.clientX || e.touches?.[0]?.clientX || 0
  const clientY = e.clientY || e.touches?.[0]?.clientY || 0
  const w = mode.value === 'human' ? 220 : 60
  const h = mode.value === 'human' ? 280 : 60
  posX.value = Math.max(0, Math.min(window.innerWidth - w, clientX - dragOffset.value.x))
  posY.value = Math.max(0, Math.min(window.innerHeight - h, clientY - dragOffset.value.y))
  
  const dx = Math.abs(clientX - dragStartPos.x)
  const dy = Math.abs(clientY - dragStartPos.y)
  if (dx > 5 || dy > 5) {
    hasDragged = true
  }
}

const stopDrag = () => {
  isDragging.value = false
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
  document.removeEventListener('touchmove', onDrag)
  document.removeEventListener('touchend', stopDrag)
}

const handleBallClick = () => {
  if (!hasDragged) {
    smartBallVisible.value = !smartBallVisible.value
    updatePanelDirection()
  }
  hasDragged = false
}

const onAvatarMouseEnter = () => {
  if (toolbarHideTimer) {
    clearTimeout(toolbarHideTimer)
    toolbarHideTimer = null
  }
  showAvatarToolbar.value = true
  updateToolbarDirection()
}

const onAvatarMouseLeave = () => {
  if (toolbarHideTimer) clearTimeout(toolbarHideTimer)
  toolbarHideTimer = setTimeout(() => {
    showAvatarToolbar.value = false
  }, 5000)
}

watch(() => props.currentPath, () => { reportPageContext() }, { immediate: true })

watch(selectedAvatar, async (newValue) => {
  const avatarActionMap = {
    '110332017': ['A_RH_hello_O', 'A_RLH_emphasize_O', 'A_U_No_pointing_O'],
    '111286001': ['A_U_hello_O', 'A_RH_emphasize2_O', 'A_RLH_applaud_C'],
  }
  const actions = avatarActionMap[newValue]
  if (actions) humanAction.value = actions
  if (digitalHuman && isAvatarReady.value) {
    // 先停止，再重建并重启
    await stopAvatar()
    initDigitalHuman()
    startAvatar()
  }
})

watch(selectedVoice, (newValue) => { if (digitalHuman) digitalHuman.setVoice(newValue) })

watch(mode, (newMode) => {
  if (newMode === 'human') {
    nextTick(() => { if (avatarContainer.value && !isAvatarReady.value) { initDigitalHuman(); startAvatar() } })
  }
})

watch(isAvatarReady, (ready) => {
  if (ready && mode.value === 'human') {
    updateToolbarDirection()
  }
})

// 监听用户ID变化，重新获取问候
watch(() => props.userId, (newUserId) => {
  if (newUserId) {
    fetchOnlineRemind()
  }
})

const scrollToBottom = () => {
  nextTick(() => {
    const chatContainer = document.querySelector('.smart-ball-chat-container')
    if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight
  })
}
const messageCount = ref(0)
watch(() => smartBallMessages.value.length, (newLen, oldLen) => {
  if (newLen > oldLen) {
    scrollToBottom()
  }
})

// 处理游戏邀请事件
const handleGameInvitation = () => {
  showGameInvitation.value = false
  if (bubbleTimeout) clearTimeout(bubbleTimeout)
  bubbleVisible.value = false
  
  const ballWidth = mode.value === 'human' ? 260 : 60
  const spaceLeft = posX.value
  const spaceRight = window.innerWidth - posX.value - ballWidth
  bubbleSide.value = spaceLeft > 200 ? 'left' : (spaceRight > 200 ? 'right' : 'left')
  
  showGameInvitation.value = true
  playNotifySound()
  if (mode.value === 'human' && isAvatarReady.value && digitalHuman) {
    digitalHuman.speak('生成时间过长，要不要玩点游戏消遣消遣~', { voiceId: selectedVoice.value })
  }
}

const closeGameInvitation = () => {
  showGameInvitation.value = false
}

const openGame = (gameType) => {
  gameTitle.value = gameType === 1 ? '喵星叠叠乐' : '迷宫算法导航'
  gameUrl.value = gameType === 1 ? '/games/cat-stack.html' : '/games/path-finder.html'
  showGameInvitation.value = false
  showGameModal.value = true
  document.body.style.overflow = 'hidden'
}

const closeGameModal = () => {
  showGameModal.value = false
  gameHtml.value = ''
  gameTitle.value = ''
  gameUrl.value = ''
  document.body.style.overflow = ''
}

const formatFileSize = (bytes) => {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const getProxyUrl = (url) => {
  if (!url) return ''
  return url
}

const markdownToHtml = (md) => {
  if (!md) return ''
  let html = md
  const imgPlaceholders = []
  html = html.replace(/!\[([^\]]*)\]\((\S+?)\s*=\s*(\d+)x\s*\)/g, (m, alt, url, w) => {
    const token = `__IMG_${imgPlaceholders.length}__`
    imgPlaceholders.push(`<img src="${getProxyUrl(url.trim())}" alt="${alt}" loading="lazy" crossorigin="anonymous" referrerpolicy="no-referrer" onerror="this.onerror=null;this.src='data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 width=%27200%27 height=%27150%27 viewBox=%270 0 200 150%27%3E%3Crect fill=%27%23f3f4f6%27 width=%27200%27 height=%27150%27/%3E%3Ctext fill=%27%239ca3af%27 font-family=%27sans-serif%27 font-size=%2712px%27 x=%2750%25%27 y=%2750%25%27 text-anchor=%27middle%27 dominant-baseline=%27middle%27%3E图片加载失败%3C/text%3E%3C/svg%3E';" style="width:${w}px;max-width:100%;border-radius:6px;margin:8px 0;box-shadow:0 2px 8px rgba(0,0,0,0.1)">`)
    return token
  })
  html = html.replace(/!\[([^\]]*)\]\((\S+)\)/g, (m, alt, url) => {
    const token = `__IMG_${imgPlaceholders.length}__`
    imgPlaceholders.push(`<img src="${getProxyUrl(url)}" alt="${alt}" loading="lazy" crossorigin="anonymous" referrerpolicy="no-referrer" onerror="this.onerror=null;this.src='data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 width=%27200%27 height=%27150%27 viewBox=%270 0 200 150%27%3E%3Crect fill=%27%23f3f4f6%27 width=%27200%27 height=%27150%27/%3E%3Ctext fill=%27%239ca3af%27 font-family=%27sans-serif%27 font-size=%2712px%27 x=%2750%25%27 y=%2750%25%27 text-anchor=%27middle%27 dominant-baseline=%27middle%27%3E图片加载失败%3C/text%3E%3C/svg%3E';" style="max-width:100%;border-radius:6px;margin:8px 0;box-shadow:0 2px 8px rgba(0,0,0,0.1)">`)
    return token
  })
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
  html = html.replace(/__IMG_(\d+)__/g, (m, idx) => imgPlaceholders[parseInt(idx)] || '')
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

const disableBodyScroll = () => {
  document.body.style.overflow = 'hidden'
}

const enableBodyScroll = () => {
  document.body.style.overflow = ''
}

const previewImage = (url) => {
  const existingOverlay = document.querySelector('.image-preview-overlay')
  if (existingOverlay) existingOverlay.remove()
  
  disableBodyScroll()
  
  const overlay = document.createElement('div')
  overlay.className = 'image-preview-overlay'
  overlay.style.cssText = 'position: fixed; inset: 0; background: rgba(0, 0, 0, 0.9); display: flex; align-items: center; justify-content: center; z-index: 9999; animation: fade-in 0.2s ease;'
  
  const content = document.createElement('div')
  content.className = 'image-preview-content'
  content.style.cssText = 'position: relative; max-width: 90%; max-height: 90%; animation: scale-in 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);'
  
  const img = document.createElement('img')
  img.crossOrigin = 'anonymous'
  img.referrerPolicy = 'no-referrer'
  img.className = 'preview-image'
  img.style.cssText = 'max-width: 100%; max-height: 80vh; border-radius: 12px;'
  img.src = url
  img.onerror = async function() {
    try {
      const proxyUrl = '/py/api/stream?url=' + encodeURIComponent(url)
      const response = await fetch(proxyUrl)
      if (response.ok) {
        const blob = await response.blob()
        img.src = URL.createObjectURL(blob)
      } else {
        throw new Error('Proxy request failed')
      }
    } catch(e) {
      img.src = 'data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 width=%27400%27 height=%27300%27 viewBox=%270 0 400 300%27%3E%3Crect fill=%27%23f3f4f6%27 width=%27400%27 height=%27300%27/%3E%3Ctext fill=%27%239ca3af%27 font-family=%27sans-serif%27 font-size=%2714px%27 x=%2750%25%27 y=%2750%25%27 text-anchor=%27middle%27 dominant-baseline=%27middle%27%3E图片加载失败%3C/text%3E%3C/svg%3E'
    }
  }
  
  const closeBtn = document.createElement('button')
  closeBtn.className = 'preview-close'
  closeBtn.innerHTML = '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>'
  closeBtn.style.cssText = 'position: absolute; top: -40px; right: -40px; width: 36px; height: 36px; background: rgba(255, 255, 255, 0.2); border: none; border-radius: 50%; color: #fff; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s ease;'
  
  const closeHandler = () => {
    overlay.remove()
    enableBodyScroll()
  }
  
  closeBtn.addEventListener('click', closeHandler)
  
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) {
      closeHandler()
    }
  })
  
  content.appendChild(img)
  content.appendChild(closeBtn)
  overlay.appendChild(content)
  document.body.insertBefore(overlay, document.body.firstChild)
}

const playVideo = (url) => {
  const existingOverlay = document.querySelector('.video-play-overlay')
  if (existingOverlay) existingOverlay.remove()
  
  disableBodyScroll()
  
  const overlay = document.createElement('div')
  overlay.className = 'video-play-overlay'
  overlay.style.cssText = 'position: fixed; inset: 0; background: rgba(0, 0, 0, 0.9); display: flex; align-items: center; justify-content: center; z-index: 9999; animation: fade-in 0.2s ease;'
  
  const content = document.createElement('div')
  content.className = 'video-play-content'
  content.style.cssText = 'position: relative; width: 95%; max-width: 1200px; animation: scale-in 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);'
  
  const video = document.createElement('video')
  video.src = url
  video.controls = true
  video.preload = 'metadata'
  video.className = 'play-video'
  video.style.cssText = 'width: 100%; max-height: 90vh; border-radius: 12px;'
  video.referrerPolicy = 'no-referrer'
  
  const closeBtn = document.createElement('button')
  closeBtn.className = 'play-close'
  closeBtn.innerHTML = '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>'
  closeBtn.style.cssText = 'position: absolute; top: -40px; right: -40px; width: 36px; height: 36px; background: rgba(255, 255, 255, 0.2); border: none; border-radius: 50%; color: #fff; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s ease;'
  
  const closeHandler = () => {
    video.pause()
    overlay.remove()
  }
  
  closeBtn.addEventListener('click', closeHandler)
  
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) {
      closeHandler()
    }
  })
  
  content.appendChild(video)
  content.appendChild(closeBtn)
  overlay.appendChild(content)
  document.body.insertBefore(overlay, document.body.firstChild)
}

// 处理摄像头警告弹窗事件
const handleCameraWarning = (data) => {
  if (!data) return
  const { message, onMode } = data
  if (typeof onMode === 'function') {
    onMode(mode.value)
  }
  // 数字人模式：先打断当前说话，再播报警告内容
  if (mode.value === 'human' && isAvatarReady.value && digitalHuman) {
    interruptAvatar()
    digitalHuman.speak(message, { voiceId: selectedVoice.value })
  }
}

onMounted(() => {
  emitter.on('contextDetail', handleContextDetail)
  emitter.on('cameraWarning', handleCameraWarning)
  emitter.on('gameInvitation', handleGameInvitation)
  fetchOnlineRemind()
  onlineRemindTimer = setInterval(fetchOnlineRemind, 3600000)
})

onUnmounted(() => {
  smartBallMessages.value = []
  emitter.off('contextDetail', handleContextDetail)
  emitter.off('cameraWarning', handleCameraWarning)
  emitter.off('gameInvitation', handleGameInvitation)
  if (bubbleTimeout) clearTimeout(bubbleTimeout)
  if (toolbarHideTimer) clearTimeout(toolbarHideTimer)
  if (recordingTimer) { clearInterval(recordingTimer); recordingTimer = null }
  if (onlineRemindTimer) { clearInterval(onlineRemindTimer); onlineRemindTimer = null }
  if (asrInstance) { try { asrInstance.cleanup() } catch (e) { console.error('清理ASR失败:', e) }; asrInstance = null }
  isRecording.value = false; recordingDuration.value = 0
  if (digitalHuman && !digitalHuman.isDestroyed) { digitalHuman.destroy(); digitalHuman = null }
})

const getTargetElement = () => {
  return wrapperRef.value
}

defineExpose({
  getTargetElement
})
</script>

<template>
  <div
    ref="wrapperRef"
    class="smart-ball-wrapper"
    :style="{ left: posX + 'px', top: posY + 'px' }"
  >
    <!-- ==================== 球模式 ==================== -->
    <div v-if="mode === 'ball'" class="smart-ball-container">
      <!-- 回复气泡（球模式） -->
      <Transition name="fade">
        <div v-if="bubbleVisible && lastReply" :class="['reply-bubble', 'bubble-' + bubbleSide]">
          <button class="bubble-close" @click.stop="bubbleVisible = false; clearTimeout(bubbleTimeout)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
          <div class="bubble-text">{{ lastReply }}</div>
          <div class="bubble-arrow"></div>
        </div>
      </Transition>
      <!-- 游戏邀请气泡 -->
      <Transition name="fade">
        <div v-if="showGameInvitation" :class="['game-invitation-bubble', 'bubble-' + bubbleSide]">
          <div class="game-invitation-text">生成时间过长，要不要玩点游戏消遣消遣~</div>
          <div class="game-invitation-btns">
            <button class="game-btn" @click.stop="openGame(1)">喵星叠叠乐</button>
            <button class="game-btn" @click.stop="openGame(2)">迷宫算法导航</button>
            <button class="game-btn cancel-btn" @click.stop="closeGameInvitation()">不用了</button>
          </div>
          <div class="bubble-arrow"></div>
        </div>
      </Transition>
      <div class="smart-ball" :class="{ 'ball-loading': smartBallLoading }" @mousedown="startDrag" @touchstart="startDrag" @click="handleBallClick()">
        <DotLottieVue class="ball-lottie" autoplay loop :src="SiriLottie" />
        <!-- 发送消息时：思考动画覆盖层 -->
        <div v-if="smartBallLoading" class="ball-thinking-overlay">
          <svg class="ball-thinking" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
            <path d="M12 2a10 10 0 0 1 10 10" />
            <path d="M12 2a10 10 0 0 0-10 10" opacity="0.4"/>
            <path d="M12 22a10 10 0 0 1-10-10" opacity="0.4"/>
            <path d="M12 22a10 10 0 0 0 10-10" opacity="0.6"/>
          </svg>
        </div>
      </div>
    </div>

    <!-- ==================== 数字人模式 ==================== -->
    <div v-else class="digital-human-container" @mouseenter="onAvatarMouseEnter" @mouseleave="onAvatarMouseLeave">
      <div class="digital-human">
        <!-- 思考气泡 -->
        <Transition name="fade">
          <div v-if="isThinking" :class="['thinking-bubble', 'bubble-' + bubbleSide]">
            <div class="thinking-dots">
              <div class="dot"></div>
              <div class="dot"></div>
              <div class="dot"></div>
            </div>
            <div class="bubble-arrow"></div>
          </div>
        </Transition>

        <!-- 回复气泡（左上角或右上角） -->
        <Transition name="fade">
          <div v-if="bubbleVisible && lastReply" :class="['reply-bubble', 'bubble-' + bubbleSide]">
            <button class="bubble-close" @click.stop="bubbleVisible = false; clearTimeout(bubbleTimeout)">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
            <div class="bubble-text">{{ lastReply }}</div>
            <div class="bubble-arrow"></div>
          </div>
        </Transition>

        <!-- 游戏邀请气泡 -->
        <Transition name="fade">
          <div v-if="showGameInvitation" :class="['game-invitation-bubble', 'bubble-' + bubbleSide]">
            <div class="game-invitation-text">生成时间过长，要不要玩点游戏消遣消遣~</div>
            <div class="game-invitation-btns">
              <button class="game-btn" @click.stop="openGame(1)">喵星叠叠乐</button>
              <button class="game-btn" @click.stop="openGame(2)">迷宫算法导航</button>
              <button class="game-btn cancel-btn" @click.stop="closeGameInvitation()">不用了</button>
            </div>
            <div class="bubble-arrow"></div>
          </div>
        </Transition>

        <!-- 数字人容器 -->
        <div ref="avatarContainer" class="avatar-wrapper" @mousedown="startDrag" @touchstart="startDrag">
          <div v-if="!isAvatarReady && !isAvatarLoading" class="avatar-placeholder">
            <svg viewBox="0 0 24 24" class="placeholder-icon" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
            </svg>
            <span class="placeholder-text">数字人未启动</span>
          </div>
          <div v-else-if="isAvatarLoading" class="avatar-loading">
            <div class="loading-spinner"></div>
            <span class="loading-text">正在加载...</span>
          </div>
        </div>

        <!-- hover工具栏（智能方向） -->
        <Transition name="fade">
          <div v-if="showAvatarToolbar" :class="['avatar-toolbar', 'toolbar-' + toolbarDirection]">
            <!-- 输入区 -->
            <div class="toolbar-input-row">
              <textarea
                v-model="smartBallInput"
                @keydown="handleSmartBallKeydown"
                placeholder="输入您的问题..."
                class="toolbar-textarea"
                @mousedown.stop
              ></textarea>
              <button
                class="toolbar-btn mic-btn"
                :class="{ recording: isRecording }"
                @click.stop="toggleRecording"
                :title="isRecording ? '停止录音' : '语音转文字'"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                  <line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/>
                </svg>
              </button>
              <button
                class="toolbar-btn send-btn"
                @click.stop="sendSmartBallMessage"
                :disabled="!smartBallInput.trim() || smartBallLoading"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
                </svg>
              </button>
            </div>
            <!-- 操作区 -->
            <div class="toolbar-action-row">
              <button class="toolbar-action-btn" @click.stop="switchMode('ball')">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="17 1 21 5 17 9"/>
                  <path d="M3 11V9a4 4 0 0 1 4-4h14"/>
                  <polyline points="7 23 3 19 7 15"/>
                  <path d="M21 13v2a4 4 0 0 1-4 4H3"/>
                </svg>
                <span>智能球</span>
              </button>
              <button class="toolbar-action-btn" @click.stop="showAvatarSettings = !showAvatarSettings">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="3"/>
                  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
                </svg>
                <span>设置数字人</span>
              </button>
            </div>
          </div>
        </Transition>
      </div>

      <!-- 设置面板 -->
      <Transition name="fade">
        <div v-if="showAvatarSettings" class="avatar-settings">
          <div class="settings-header">
            <span>数字人设置</span>
            <button @click.stop="showAvatarSettings = false" class="close-btn">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
          <div class="settings-content">
            <div class="setting-item">
              <label>选择形象</label>
              <select v-model="selectedAvatar" class="avatar-select" @mousedown.stop>
                <option v-for="item in avatarOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
              </select>
            </div>
            <div class="setting-item">
              <label>选择语音</label>
              <select v-model="selectedVoice" class="avatar-select" @mousedown.stop>
                <option v-for="item in voiceOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
              </select>
            </div>
          </div>
        </div>
      </Transition>
    </div>

    <!-- ==================== 球模式聊天框 ==================== -->
    <Transition name="slide-up">
      <div v-if="mode === 'ball' && smartBallVisible" :class="['smart-ball-panel', 'panel-' + panelPosition]">
        <div class="smart-ball-header">
          <span class="panel-title">智能球</span>
          <div class="smart-ball-header-btns">
            <button class="switch-human-btn" @click="switchMode('human'); smartBallVisible = false" title="切换数字人">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
              </svg>
              <span>切换数字人</span>
            </button>
            <button class="header-icon-btn" @click="smartBallVisible = false" title="关闭">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
        </div>
        <div class="smart-ball-chat-container">
          <div v-for="(msg, index) in smartBallMessages" :key="index" :class="['smart-ball-message', msg.role]">
            <div v-if="msg.role === 'user'" class="message-content">{{ msg.content }}</div>
            <div v-else class="message-content" :class="{ 'typing': msg.isTyping }">
              <div v-html="msg.contentHtml || msg.content"></div>

              <div v-if="msg.showImages && msg.images && msg.images.length > 0" class="message-images">
                <div class="image-grid">
                  <div v-for="(img, imgIndex) in msg.images" :key="imgIndex" class="image-item" @click="previewImage(getProxyUrl(img.image_url))">
                    <img :src="getProxyUrl(img.image_url)" :alt="img.title" class="image-thumb" loading="lazy" crossorigin="anonymous" referrerpolicy="no-referrer" @error="(e) => { e.target.src = 'data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 width=%27200%27 height=%27150%27 viewBox=%270 0 200 150%27%3E%3Crect fill=%27%23f3f4f6%27 width=%27200%27 height=%27150%27/%3E%3Ctext fill=%27%239ca3af%27 font-family=%27sans-serif%27 font-size=%2712px%27 x=%2750%25%27 y=%2750%25%27 text-anchor=%27middle%27 dominant-baseline=%27middle%27%3E图片加载失败%3C/text%3E%3C/svg%3E'; }">
                    <div class="image-overlay">
                      <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7"/>
                        <circle cx="12" cy="12" r="3"/>
                      </svg>
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="msg.showToolResults && msg.toolResults && msg.toolResults.length > 0" class="message-videos">
                <div v-for="(result, rIndex) in msg.toolResults" :key="rIndex" class="video-item">
                  <div v-if="result.result && result.result.data && result.result.data.length > 0">
                    <div v-for="(video, vIndex) in result.result.data" :key="vIndex" class="video-card" @click="playVideo(video.url)">
                      <div class="video-preview">
                        <div class="video-icon-bg"></div>
                        <div class="video-play-btn">
                          <svg viewBox="0 0 24 24" width="32" height="32" fill="currentColor">
                            <polygon points="5 3 19 12 5 21 5 3"/>
                          </svg>
                        </div>
                        <div class="video-type-badge">{{ video.ext }}</div>
                      </div>
                      <div class="video-info">
                        <div class="video-title">{{ video.title }}</div>
                        <div class="video-meta">{{ formatFileSize(video.size) }}</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="msg.showSourcesSection && msg.sources && msg.sources.length > 0" class="message-sources">
                <button class="sources-toggle" @click="msg.showSources = !msg.showSources">
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                    <path d="m9 12 2 2 4-4"/>
                  </svg>
                  <span>{{ msg.showSources ? '收起来源' : '查看来源' }} ({{ msg.sources.length }})</span>
                </button>
                <Transition name="slide">
                  <div v-if="msg.showSources" class="sources-list">
                    <div v-for="(source, sIndex) in msg.sources" :key="sIndex" class="source-item">
                      <a :href="source.url" target="_blank" class="source-link">
                        <div class="source-icon">
                          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M12 2L2 7l10 5 10-5-10-5z"/>
                            <path d="M2 17l10 5 10-5"/>
                            <path d="M2 12l10 5 10-5"/>
                          </svg>
                        </div>
                        <div class="source-content">
                          <div class="source-title">{{ source.title }}</div>
                          <div class="source-snippet">{{ source.snippet }}</div>
                        </div>
                        <div class="source-type">{{ source.source_type }}</div>
                      </a>
                    </div>
                  </div>
                </Transition>
              </div>
            </div>
          </div>
          <div v-if="smartBallLoading" class="smart-ball-thinking">
            <div class="thinking-label">思考中...</div>
            <div class="smart-ball-loading">
              <div class="loading-dot"></div><div class="loading-dot"></div><div class="loading-dot"></div>
            </div>
          </div>
        </div>
        <div class="smart-ball-input-area">
          <textarea v-model="smartBallInput" @keydown="handleSmartBallKeydown" placeholder="输入您的问题..." class="smart-ball-textarea" @mousedown.stop></textarea>
          <button
            class="smart-ball-mic"
            :class="{ recording: isRecording }"
            @click.stop="toggleRecording"
            :title="isRecording ? '停止录音' : '语音转文字'"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
              <line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/>
            </svg>
          </button>
          <button class="smart-ball-send" @click="sendSmartBallMessage" :disabled="!smartBallInput.trim() || smartBallLoading">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
            </svg>
          </button>
        </div>
      </div>
    </Transition>

    <!-- ==================== 游戏模态框 ==================== -->
    <Transition name="fade">
      <div v-if="showGameModal" class="game-modal-mask" @click="closeGameModal()">
        <div class="game-modal" @click.stop>
          <div class="game-modal-header">
            <span class="game-modal-title">{{ gameTitle }}</span>
            <button class="game-modal-close" @click.stop="closeGameModal()">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
          <div class="game-modal-body">
            <iframe :src="gameUrl" frameborder="0" width="100%" height="100%"></iframe>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.smart-ball-wrapper {
  
  position: fixed;
  z-index: 100;
}

/* ===== 球模式 ===== */
.smart-ball-container { position: relative; display: inline-block; }
.smart-ball {
  width: 60px; height: 60px; border-radius: 50%;
  background: transparent;
  display: flex; align-items: center; justify-content: center;
  cursor: move;
  transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
  color: #fff;
  position: relative;
  animation: ball-breathe 3s ease-in-out infinite;
  overflow: hidden;
}
.smart-ball::before {
  content: '';
  position: absolute;
  top: 50%; left: 50%;
  width: 100%; height: 100%;
  border-radius: 50%;
  background: var(--primary);
  transform: translate(-50%, -50%);
  opacity: 0;
  animation: ball-glow 3s ease-in-out infinite;
  z-index: -1;
}
.smart-ball:hover {
  transform: scale(1.15);
  box-shadow: 0 8px 30px rgba(45, 125, 219, 0.5), 0 0 0 10px rgba(45, 125, 219, 0.1);
}
.smart-ball svg { width: 32px; height: 32px; transition: transform 0.3s ease; }
.smart-ball:hover svg { transform: scale(1.1); }
.smart-ball .ball-lottie {
  width: 60px; height: 60px;
  border-radius: 50%;
  object-fit: cover;
}
.smart-ball .ball-thinking-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.3);
}
.smart-ball .ball-thinking-overlay svg {
  width: 36px; height: 36px;
}

@keyframes ball-breathe {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.05); }
}
@keyframes ball-glow {
  0%, 100% { width: 100%; height: 100%; opacity: 0; }
  50% { width: 140%; height: 140%; opacity: 0.2; }
}

.ball-thinking {
  animation: ball-think-spin 1.5s linear infinite, ball-think-pulse 1s ease-in-out infinite;
}
@keyframes ball-think-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
@keyframes ball-think-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}
.ball-menu {
  position: absolute; right: 70px; top: 0;
  background: #fff; border-radius: 8px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.15);
  padding: 6px 0; min-width: 140px;
}

/* ===== 数字人模式 ===== */
.digital-human-container { position: relative; display: inline-block; }
.digital-human { position: relative; width: 220px; }

.avatar-wrapper {
  height: 280px; border-radius: 12px; overflow: hidden;
  position: relative; background: transparent !important;
  cursor: move;
}

.avatar-placeholder {
  position: absolute; top: 0; left: 0; right: 0; bottom: 0;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  color: #999; background: transparent;
}
.placeholder-icon { width: 48px; height: 48px; margin-bottom: 8px; }
.placeholder-text { font-size: 12px; }

.avatar-loading {
  position: absolute; top: 0; left: 0; right: 0; bottom: 0;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  background: transparent;
}
.loading-spinner {
  width: 32px; height: 32px;
  border: 3px solid var(--primary-fade);
  border-top-color: var(--primary); border-radius: 50%;
  animation: spin 1s linear infinite; margin-bottom: 8px;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ===== 思考气泡 ===== */
.thinking-bubble {
  position: absolute;
  top: -10px;
  background: #fff; border-radius: 20px;
  padding: 12px 18px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
  z-index: 200; pointer-events: none;
}
.thinking-bubble.bubble-right { left: 225px; }
.thinking-bubble.bubble-left { right: 225px; }
.thinking-bubble .thinking-dots {
  display: flex; gap: 4px; align-items: center;
}
.thinking-bubble .dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--primary);
  animation: thinking-bounce 1.4s infinite ease-in-out both;
}
.thinking-bubble .dot:nth-child(1) { animation-delay: -0.32s; }
.thinking-bubble .dot:nth-child(2) { animation-delay: -0.16s; }
.thinking-bubble .bubble-arrow {
  position: absolute; top: 7px;
  width: 16px; height: 16px;
  background: #fff;
}
.thinking-bubble.bubble-right .bubble-arrow {
  left: -8px;
  transform: rotate(45deg);
  box-shadow: -2px 2px 4px rgba(0,0,0,0.05);
}
.thinking-bubble.bubble-left .bubble-arrow {
  right: -3px;
  transform: rotate(45deg);
  box-shadow: 2px -2px 4px rgba(0,0,0,0.05);
}
@keyframes thinking-bounce {
  0%, 80%, 100% { transform: scale(0); opacity: 0.5; }
  40% { transform: scale(1); opacity: 1; }
}

/* ===== 回复气泡 ===== */
.reply-bubble {
  position: absolute;
  top: -10px;
  background: #fff; border-radius: 12px;
  padding: 10px 30px 10px 14px; max-width: 380px; min-width: 200px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
  font-size: 13px; color: #333; line-height: 1.5;
  z-index: 200; pointer-events: auto;
  max-height: calc(260px - 20px); overflow-y: auto;
}
.bubble-right { left: 225px; }
.bubble-left { right: 225px; }
.smart-ball-container .bubble-right { left: 70px; }
.smart-ball-container .bubble-left { right: 70px; }
.reply-bubble .bubble-arrow {
  position: absolute; top: 20px;
  width: 0; height: 0;
  border-top: 8px solid transparent;
  border-bottom: 8px solid transparent;
}
.bubble-right .bubble-arrow {
  left: -8px;
  border-right: 8px solid #fff;
}
.bubble-left .bubble-arrow {
  right: -8px;
  border-left: 8px solid #fff;
}
.bubble-text {
  word-wrap: break-word;
  white-space: pre-wrap;
}

.bubble-close {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 20px;
  height: 20px;
  background: rgba(0, 0, 0, 0.1);
  border: none;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  transition: background 0.2s ease;
  z-index: 1;
}

.bubble-close:hover {
  background: rgba(0, 0, 0, 0.2);
}

.bubble-close svg {
  width: 12px;
  height: 12px;
  color: #666;
}

/* ===== hover工具栏 ===== */
.avatar-toolbar {
  position: absolute; left: -10px; right: -10px;
  background: #fff; border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  padding: 10px; z-index: 102;
}
.toolbar-bottom { bottom: -120px; }
.toolbar-top { top: -120px; }

.toolbar-input-row {
  display: flex; gap: 6px; align-items: flex-end; margin-bottom: 8px;
}
.toolbar-textarea {
  flex: 1; padding: 6px 10px; border: 1px solid var(--border-color);
  border-radius: 8px; font-size: 13px; resize: none; outline: none;
  min-height: 28px; max-height: 40px; line-height: 1.4;
}
.toolbar-textarea:focus { border-color: var(--primary); }

.toolbar-btn {
  width: 36px; height: 36px; border-radius: 8px; border: none;
  cursor: pointer; display: flex; align-items: center; justify-content: center;
  transition: all 0.2s ease; flex-shrink: 0;
}
.toolbar-btn svg { width: 18px; height: 18px; }
.mic-btn { background: var(--primary-light); color: var(--primary); }
.mic-btn:hover { background: var(--primary-fade); }
.mic-btn.recording { background: #ff4757; color: #fff; animation: pulse 1s infinite; }
@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(255, 71, 87, 0.4); }
  50% { box-shadow: 0 0 0 8px rgba(255, 71, 87, 0); }
}
.send-btn { background: var(--grad-primary); color: #fff; }
.send-btn:hover:not(:disabled) { transform: scale(1.05); }
.send-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.toolbar-action-row { display: flex; gap: 4px; }
.toolbar-action-btn {
  flex: 1; display: flex; align-items: center; justify-content: center; gap: 4px;
  padding: 7px 4px; background: var(--bgc-light); border: none; border-radius: 8px;
  cursor: pointer; font-size: 12px; color: #555; transition: all 0.2s ease;
}
.toolbar-action-btn:hover { background: var(--primary-fade); color: var(--primary); }
.toolbar-action-btn svg { width: 16px; height: 16px; flex-shrink: 0; }

/* ===== 设置面板（优先左侧） ===== */
.avatar-settings {
  position: absolute; right: 230px; top: 0;
  background: #fff; border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  min-width: 220px; overflow: hidden; z-index: 103;
}
.settings-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px;
  background: var(--grad-primary);
  color: #fff; font-size: 14px;
}
.close-btn {
  background: none; border: none; color: #fff; cursor: pointer;
  width: 24px; height: 24px; display: flex; align-items: center; justify-content: center;
}
.close-btn svg { width: 100%; height: 100%; }
.settings-content { padding: 16px; }
.setting-item { margin-bottom: 16px; }
.setting-item:last-child { margin-bottom: 0; }
.setting-item label { display: block; font-size: 12px; color: #666; margin-bottom: 6px; }
.avatar-select {
  width: 100%; padding: 8px 12px; border: 1px solid var(--border-color);
  border-radius: 6px; font-size: 13px; background: #fff; cursor: pointer;
}

/* ===== 球模式聊天框 ===== */
.smart-ball-wrapper > .smart-ball-panel {
  position: absolute;
  width: 380px; height: 480px;
  background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
  border-radius: 20px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15), 0 0 0 1px rgba(0, 0, 0, 0.05);
  overflow: hidden; display: flex; flex-direction: column;
}
.panel-bottom-left { top: 70px; right: 30px; }
.panel-top-left { bottom: 70px; right: 30px; }
.panel-bottom-right { top: 70px; left: 30px; }
.panel-top-right { bottom: 70px; left: 30px; }
.smart-ball-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px;
  background: var(--grad-primary); color: #fff;
  flex-shrink: 0;
  position: relative;
  overflow: hidden;
}
.smart-ball-header::before {
  content: '';
  position: absolute;
  top: -50%; right: -50%;
  width: 100%; height: 100%;
  background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
  animation: header-shimmer 4s ease-in-out infinite;
}
@keyframes header-shimmer {
  0%, 100% { transform: translateX(0) rotate(0deg); }
  50% { transform: translateX(-20%) rotate(10deg); }
}
.panel-title { font-size: 15px; font-weight: 700; letter-spacing: 0.5px; }
.smart-ball-header-btns {
  display: flex; gap: 8px; align-items: center;
}
.header-icon-btn {
  background: rgba(255,255,255,0.15); border: none; color: #fff; cursor: pointer;
  width: 32px; height: 32px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  backdrop-filter: blur(10px);
}
.header-icon-btn:hover { 
  background: rgba(255,255,255,0.25); 
  transform: scale(1.1);
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}
.header-icon-btn svg { width: 18px; height: 18px; }

.switch-human-btn {
  display: flex; align-items: center; gap: 5px;
  background: rgba(255,255,255,0.95); color: var(--primary); border: none; cursor: pointer;
  padding: 6px 14px; border-radius: 20px; font-size: 12px; font-weight: 600;
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}
.switch-human-btn:hover { 
  background: #fff; 
  transform: scale(1.08); 
  box-shadow: 0 4px 16px rgba(0,0,0,0.15);
}
.switch-human-btn svg { width: 16px; height: 16px; }

.smart-ball-chat-container {
  flex: 1; min-height: 0; overflow-y: auto; padding: 16px; 
  background: linear-gradient(180deg, var(--bgc-light) 0%, #f1f5f9 100%);
}
.smart-ball-message { 
  display: flex; margin-bottom: 16px; 
  animation: message-fade-in 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}
@keyframes message-fade-in {
  from { opacity: 0; transform: translateY(10px) scale(0.95); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
.smart-ball-message.user { justify-content: flex-end; }
.smart-ball-message.assistant { justify-content: flex-start; }
.message-content {
  max-width: 75%; padding: 10px 14px; border-radius: 18px;
  font-size: 14px; line-height: 1.6;
  position: relative;
  overflow: hidden;
  word-break: break-word;
}
.smart-ball-message.user .message-content {
  background: var(--grad-primary);
  color: #fff; border-radius: 20px 20px 6px 20px;
  box-shadow: 0 4px 12px rgba(45, 125, 219, 0.3);
}
.smart-ball-message.assistant .message-content {
  background: #fff; color: #333; border-radius: 20px 20px 20px 6px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
}
/* .smart-ball-message.user .message-content::after {
  content: '';
  position: absolute;
  right: -6px; bottom: 8px;
  width: 10px; height: 10px;
  background: var(--primary);
  border-radius: 0 0 10px 0;
}
.smart-ball-message.assistant .message-content::after {
  content: '';
  position: absolute;
  left: -6px; bottom: 8px;
  width: 10px; height: 10px;
  background: #fff;
  border-radius: 0 0 0 10px;
  box-shadow: 2px 2px 4px rgba(0,0,0,0.05);
} */
.smart-ball-loading { display: flex; gap: 6px; padding: 8px; }
.loading-dot {
  width: 8px; height: 8px; border-radius: 50%; background: var(--primary);
  animation: bounce 1.4s infinite ease-in-out both;
}
.loading-dot:nth-child(1) { animation-delay: -0.32s; }
.loading-dot:nth-child(2) { animation-delay: -0.16s; }
@keyframes bounce { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1); } }

.smart-ball-thinking {
  display: flex; align-items: center; gap: 8px; padding: 8px 12px;
}
.thinking-label {
  font-size: 12px; color: var(--primary);
}

.message-images, .message-videos, .message-sources {
  margin-top: 12px;
  animation: fadeInUp 0.4s ease;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.image-grid {
  display: flex; flex-wrap: wrap; gap: 6px;
}

.image-item {
  width: calc(50% - 3px); aspect-ratio: 1; border-radius: 8px;
  overflow: hidden; position: relative; cursor: pointer;
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.image-item:hover {
  transform: scale(1.03);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.image-thumb {
  width: 100%; height: 100%; object-fit: cover;
}

.image-overlay {
  position: absolute; inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex; align-items: center; justify-content: center;
  opacity: 0; color: #fff;
  transition: opacity 0.2s ease;
}

.image-item:hover .image-overlay {
  opacity: 1;
}

.video-card {
  background: var(--bg-card); border-radius: 12px;
  overflow: hidden; margin-bottom: 10px;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: all 0.3s ease;
}

.video-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(45, 125, 219, 0.15);
}

.video-preview {
  position: relative; aspect-ratio: 16/9;
  background: black;
  display: flex; align-items: center; justify-content: center;
  overflow: hidden;
}

.video-icon-bg {
  color: rgba(255, 255, 255, 0.3);
  transition: transform 0.3s ease;
}

.video-card:hover .video-icon-bg {
  transform: scale(1.1);
}

.video-play-btn {
  position: absolute; top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  width: 56px; height: 56px;
  background: rgba(45, 125, 219, 0.95); border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  color: #fff;
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  box-shadow: 0 4px 20px rgba(45, 125, 219, 0.4);
}

.video-card:hover .video-play-btn {
  transform: translate(-50%, -50%) scale(1.2);
  box-shadow: 0 8px 30px rgba(45, 125, 219, 0.6);
}

.video-duration {
  position: absolute; bottom: 8px; right: 8px;
  padding: 3px 7px; background: rgba(0, 0, 0, 0.75);
  color: #fff; font-size: 11px; border-radius: 4px;
  font-weight: 500;
}

.video-type-badge {
  position: absolute; top: 8px; left: 8px;
  padding: 3px 8px; background: rgba(45, 125, 219, 0.9);
  color: #fff; font-size: 10px; border-radius: 4px;
  font-weight: 600;
  text-transform: uppercase;
}

.video-info {
  padding: 10px 12px;
}

.video-title {
  font-size: 13px; font-weight: 600; color: var(--text-title);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

.video-meta {
  font-size: 11px; color: var(--text-gray);
  margin-top: 4px;
}

.sources-toggle {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 12px; background: var(--bgc-light);
  border: none; border-radius: 20px; font-size: 12px;
  color: var(--primary); cursor: pointer;
  transition: all 0.2s ease;
}

.sources-toggle:hover {
  background: var(--primary-fade);
  transform: scale(1.02);
}

.sources-list {
  margin-top: 10px;
  background: var(--bgc-light);
  border-radius: 10px; padding: 8px;
}

.source-item {
  margin-bottom: 6px;
}

.source-item:last-child {
  margin-bottom: 0;
}

.source-link {
  display: flex; align-items: flex-start; gap: 8px;
  padding: 8px; background: #fff;
  border-radius: 8px; text-decoration: none;
  transition: all 0.2s ease;
}

.source-link:hover {
  background: var(--primary-fade);
  transform: translateX(4px);
}

.source-icon {
  width: 20px; height: 20px;
  display: flex; align-items: center; justify-content: center;
  color: var(--primary); flex-shrink: 0;
}

.source-content {
  flex: 1; min-width: 0;
}

.source-title {
  font-size: 12px; font-weight: 500; color: var(--text-title);
  margin-bottom: 2px; white-space: nowrap; overflow: hidden;
  text-overflow: ellipsis;
}

.source-snippet {
  font-size: 11px; color: var(--text-gray);
  display: -webkit-box; 
  line-clamp: 2;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical; overflow: hidden;
}

.source-type {
  padding: 2px 6px; background: var(--bgc-light);
  color: var(--text-gray); font-size: 10px; border-radius: 4px;
  flex-shrink: 0;
}

.image-preview-overlay {
  position: fixed; inset: 0;
  background: rgba(0, 0, 0, 0.85);
  display: flex; align-items: center; justify-content: center;
  z-index: 2000;
  animation: fade-in 0.2s ease;
}

@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

.image-preview-content {
  position: relative; max-width: 90%; max-height: 90%;
  animation: scale-in 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes scale-in {
  from { opacity: 0; transform: scale(0.8); }
  to { opacity: 1; transform: scale(1); }
}

.preview-image {
  max-width: 100%; max-height: 80vh;
  border-radius: 12px;
}

.preview-close {
  position: absolute; top: -40px; right: 0;
  width: 36px; height: 36px;
  background: rgba(255, 255, 255, 0.2);
  border: none; border-radius: 50%;
  color: #fff; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.2s ease;
}

.preview-close:hover {
  background: rgba(255, 255, 255, 0.3);
  transform: scale(1.1);
}

.video-play-overlay {
  position: fixed; inset: 0;
  background: rgba(0, 0, 0, 0.9);
  display: flex; align-items: center; justify-content: center;
  z-index: 2000;
  animation: fade-in 0.2s ease;
}

.video-play-content {
  position: relative; width: 90%; max-width: 800px;
  animation: scale-in 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.play-video {
  width: 100%; max-height: 80vh;
  border-radius: 12px;
}

.play-close {
  position: absolute; top: -40px; right: 0;
  width: 36px; height: 36px;
  background: rgba(255, 255, 255, 0.2);
  border: none; border-radius: 50%;
  color: #fff; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.2s ease;
}

.play-close:hover {
  background: rgba(255, 255, 255, 0.3);
  transform: scale(1.1);
}

.smart-ball-input-area {
  display: flex; gap: 10px; padding: 12px 16px; align-items: center;
  background: #fff; border-top: 1px solid var(--border-color); 
  flex-shrink: 0;
  position: relative;
}
.smart-ball-input-area::before {
  content: '';
  position: absolute;
  top: 0; left: 50%;
  width: 0; height: 2px;
  background: var(--grad-primary);
  transform: translateX(-50%);
  transition: width 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.smart-ball-input-area:focus-within::before {
  width: 100%;
}
.smart-ball-textarea {
  flex: 1; padding: 10px 16px; border: 2px solid var(--border-color);
  border-radius: 24px; font-size: 14px; resize: none; outline: none;
  min-height: 42px; max-height: 70px; line-height: 1.5;
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  background: #fafafa;
}
.smart-ball-textarea:focus { 
  border-color: var(--primary); 
  background: #fff;
  box-shadow: 0 0 0 4px rgba(45, 125, 219, 0.1), 0 4px 12px rgba(45, 125, 219, 0.1);
  transform: scale(1.02);
}
.smart-ball-textarea::placeholder { color: #9ca3af; }
.smart-ball-mic {
  width: 40px; height: 40px; border-radius: 50%;
  background: var(--primary-light); color: var(--primary);
  border: 2px solid transparent; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1); 
  flex-shrink: 0;
}
.smart-ball-mic:hover { 
  background: var(--primary-fade); 
  transform: scale(1.1);
}
.smart-ball-mic.recording { 
  background: #ff4757; 
  color: #fff; 
  animation: pulse 1s infinite;
  border-color: rgba(255, 71, 87, 0.3);
}
.smart-ball-mic svg { width: 18px; height: 18px; }
.smart-ball-send {
  width: 40px; height: 40px; border-radius: 50%;
  background: var(--grad-primary);
  border: none; color: #fff; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1); 
  flex-shrink: 0;
  box-shadow: 0 4px 12px rgba(45, 125, 219, 0.3);
}
.smart-ball-send:hover:not(:disabled) { 
  transform: scale(1.15); 
  box-shadow: 0 6px 20px rgba(45, 125, 219, 0.4);
}
.smart-ball-send:active:not(:disabled) {
  transform: scale(0.95);
}
.smart-ball-send:disabled { opacity: 0.5; cursor: not-allowed; }
.smart-ball-send svg { width: 20px; height: 20px; }

/* ===== 菜单项 ===== */
.menu-item {
  display: flex; align-items: center; gap: 8px; width: 100%;
  padding: 10px 16px; background: none; border: none;
  cursor: pointer; font-size: 13px; color: #333; transition: background 0.2s ease;
}
.menu-item:hover { background: var(--bgc-light); }
.menu-item svg { width: 18px; height: 18px; color: var(--primary); }

/* ===== 过渡动画 ===== */
.fade-enter-active, .fade-leave-active { 
  transition: opacity 0.2s ease; 
}
.fade-enter-from, .fade-leave-to { opacity: 0; }

.slide-up-enter-active {
  transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.slide-up-leave-active {
  transition: all 0.3s cubic-bezier(0.55, 0, 1, 0.45);
}
.slide-up-enter-from {
  opacity: 0;
  transform: translateX(20px) translateY(20px) scale(0.95);
}
.slide-up-leave-to {
  opacity: 0;
  transform: translateX(-10px) translateY(10px) scale(0.98);
}

.slide-enter-active, .slide-leave-active {
  transition: all 0.3s ease;
}
.slide-enter-from, .slide-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* ===== 游戏邀请气泡 ===== */
.game-invitation-bubble {
  position: absolute;
  top: -10px;
  width: 320px;
  background: #fff; border-radius: 12px;
  padding: 14px 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
  font-size: 13px; color: #333; line-height: 1.5;
  z-index: 200; pointer-events: auto;
}
.game-invitation-bubble.bubble-right { left: 225px; }
.game-invitation-bubble.bubble-left { right: 225px; }
.smart-ball-container .game-invitation-bubble.bubble-right { left: 70px; }
.smart-ball-container .game-invitation-bubble.bubble-left { right: 70px; }
.digital-human-container .game-invitation-bubble.bubble-right { left: 225px; }
.digital-human-container .game-invitation-bubble.bubble-left { right: 225px; }
.game-invitation-text {
  margin-bottom: 12px;
}
.game-invitation-btns {
  display: flex; gap: 8px; flex-wrap: wrap;
}
.game-btn {
  padding: 6px 14px; background: var(--grad-primary);
  color: #fff; border: none; border-radius: 20px;
  font-size: 12px; cursor: pointer;
  transition: all 0.2s ease;
}
.game-btn:hover {
  transform: scale(1.05);
  box-shadow: 0 2px 8px rgba(45, 125, 219, 0.3);
}
.game-btn.cancel-btn {
  background: #f0f0f0;
  color: #666;
}
.game-btn.cancel-btn:hover {
  background: #e0e0e0;
  box-shadow: none;
}
.game-invitation-bubble .bubble-arrow {
  position: absolute; top: 20px;
  width: 0; height: 0;
  border-top: 8px solid transparent;
  border-bottom: 8px solid transparent;
}
.game-invitation-bubble.bubble-right .bubble-arrow {
  left: -8px;
  border-right: 8px solid #fff;
}
.game-invitation-bubble.bubble-left .bubble-arrow {
  right: -8px;
  border-left: 8px solid #fff;
}

/* ===== 游戏模态框 ===== */
.game-modal-mask {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000;
  overflow: hidden;
}
.game-modal {
  width: auto;
  min-width: 1200px;
  max-width: 90vw;
  height: 95vh;
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
  display: flex;
  flex-direction: column;
}
.game-modal-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 20px;
  background: var(--grad-primary);
  color: #fff;
  flex-shrink: 0;
}
.game-modal-title {
  font-size: 16px; font-weight: 600;
}
.game-modal-close {
  width: 32px; height: 32px;
  background: rgba(255, 255, 255, 0.2);
  border: none; border-radius: 8px;
  color: #fff; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: background 0.2s ease;
}
.game-modal-close:hover {
  background: rgba(255, 255, 255, 0.3);
}
.game-modal-close svg {
  width: 18px; height: 18px;
}
.game-modal-body {
  flex: 1;
  overflow: hidden;
  width: 100%;
}

/* ============ 夜间模式适配 ============ */

/* 球菜单 */
.dark .ball-menu {
  background: var(--bg-card);
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
}

/* 思考气泡 */
.dark .thinking-bubble {
  background: var(--bg-card);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.dark .thinking-bubble .bubble-arrow {
  background: var(--bg-card);
}

/* 回复气泡 */
.dark .reply-bubble {
  background: var(--bg-card);
  color: var(--text-body);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.dark .bubble-right .bubble-arrow {
  border-right-color: var(--bg-card);
}

.dark .bubble-left .bubble-arrow {
  border-left-color: var(--bg-card);
}

.dark .bubble-close {
  background: rgba(255, 255, 255, 0.1);
}

.dark .bubble-close:hover {
  background: rgba(255, 255, 255, 0.2);
}

.dark .bubble-close svg {
  color: var(--text-gray);
}

/* hover工具栏 */
.dark .avatar-toolbar {
  background: var(--bg-card);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.dark .toolbar-textarea {
  background: var(--bg-page);
  color: var(--text-body);
  border-color: var(--border-color);
}

.dark .toolbar-textarea::placeholder {
  color: var(--text-gray);
}

/* 切换按钮 */
.dark .switch-human-btn {
  background: rgba(51, 65, 85, 0.95);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.dark .switch-human-btn:hover {
  background: var(--bg-card);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
}

/* 球模式聊天框面板 */
.dark .smart-ball-chat-container {
  background: var(--bg-page);
}

/* 助手消息气泡 */
.dark .smart-ball-message.assistant .message-content {
  background: var(--bg-card);
  color: var(--text-body);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
}

/* 用户消息气泡保持不变（渐变背景） */

/* 输入区域 */
.dark .smart-ball-input-area {
  background: var(--bg-card);
  border-top-color: var(--border-color);
}

/* 文本框 */
.dark .smart-ball-textarea {
  background: var(--bg-page);
  color: var(--text-body);
}

.dark .smart-ball-textarea::placeholder {
  color: var(--text-gray);
}

/* 游戏邀请气泡 */
.dark .game-invitation-bubble {
  background: var(--bg-card);
  color: var(--text-body);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.dark .game-invitation-bubble.bubble-right .bubble-arrow {
  border-right-color: var(--bg-card);
}

.dark .game-invitation-bubble.bubble-left .bubble-arrow {
  border-left-color: var(--bg-card);
}

.dark .game-btn.cancel-btn {
  background: rgba(71, 85, 105, 0.3);
  color: var(--text-gray);
}

.dark .game-btn.cancel-btn:hover {
  background: rgba(71, 85, 105, 0.4);
}

/* 游戏模态框 */
.dark .game-modal {
  background: var(--bg-card);
}

/* 文字颜色 */
.dark .smart-ball-textarea {
  color: var(--text-body);
}

.dark .send-btn-label {
  color: var(--text-body);
}

</style>
