<!-- aiAnswer.vue -->
<script setup>
import { ref, onMounted, onUnmounted, onBeforeUnmount, nextTick, watch, inject } from 'vue'
import { ElMessage, ElNotification } from 'element-plus'
import { findString } from '@/utils/findString.js'// 导入文本匹配封装类
import { saveSkip,isSkip,removeSkip } from '@/utils/skip.js'// 导入跳转封装类
import { createTypewriter } from '@/utils/typewriter.js'// 导入流式输出封装类
import { postTextApi, getProgressApi, reCreateApi, aiHistoryApi,conflictApi } from '@/api/mainApi/aiAnswer.js'
import PlanSelector from '@/components/PlanSelector.vue'// 导入学习方案选择组件
import { useRouter, useRoute } from 'vue-router'
import { ASR } from '@/utils/asr.js'// 导入ASR语音识别封装类
import { DigitalHuman } from '@/utils/digitalHuman.js' // 导入数字人封装类
import emitter from '@/utils/emitter'// 导入事件总线封装类（子->父传递数据）
const router = useRouter()
const route = useRoute()


// ==================== 配置常量（由Vue提供） ====================
const AVATAR_CONFIG = {
  serverUrl: import.meta.env.VITE_AVATAR_SERVER_URL,
  appId: import.meta.env.VITE_AVATAR_APP_ID,
  apiKey: import.meta.env.VITE_AVATAR_API_KEY,
  apiSecret: import.meta.env.VITE_AVATAR_API_SECRET,
  sceneId: import.meta.env.VITE_AVATAR_SCENE_ID,
}

// ==================== 选项数据（由Vue提供） ====================
const avatarOptions = [
  { value: '110332017', label: '女老师' },
  { value: '111286001', label: '男老师' },
]

const voiceOptions = [
  { value: 'x4_lingxiaoyue_oral', label: '聆小媛' },
  { value: 'x4_yuexiaoni_assist', label: '月小妮' },
  { value: 'x4_chaoge', label: '超哥' },
]

const backgroundOptions = [
  { value: 'https://java-web-project-13859154338.oss-cn-beijing.aliyuncs.com/CollectStudySystem/bg1.jpg', label: '办公室' },
  { value: 'https://java-web-project-13859154338.oss-cn-beijing.aliyuncs.com/CollectStudySystem/bg4.jpg', label: '室内' },
  { value: 'https://java-web-project-13859154338.oss-cn-beijing.aliyuncs.com/CollectStudySystem/bg3.jpg', label: '书房' },
  { value: 'https://all-tame-max-oss.oss-cn-beijing.aliyuncs.com/et/1699420292376169.png', label: '古典' },
]




// ==================== 响应式状态 ====================
const avatarContainer = ref(null)
const scrollbarRef = ref(null)

// 设置选项（默认）
const selectedAvatar = ref('110332017')
const selectedVoice = ref('x4_lingxiaoyue_oral')
const selectedBackground = ref('https://java-web-project-13859154338.oss-cn-beijing.aliyuncs.com/CollectStudySystem/bg1.jpg')

// 数字人相关
const subtitle = ref('')
const isAvatarReady = ref(false)
const isAvatarSpeaking = ref(false)
const isAvatarLoading = ref(false)
const avatarStartFailed = ref(false)
const humanAction = ref(['A_RH_hello_O','A_RLH_emphasize_O','A_U_No_pointing_O'])

// 数字人实例
let digitalHuman = null

// 对话相关
const conversation = ref([])
const userInput = ref('')
const agentUserId = ref('')
const isAgentLoading = ref(false)

// 历史记录相关
const hasMoreHistory = ref(false)
const isLoadingHistory = ref(false)
const firstChatId = ref(null)

// 冲突弹窗相关
const showConflictDialog = ref(false)
const conflictData = ref({
  createTime: '',
  suggestionWarning: '',
  rsType: null,
  taskId: null
})

// 语音录制相关
const isRecording = ref(false)
const recordingDuration = ref(0)
let recordingTimer = null
let asrInstance = null

// 语音模式相关
const isVoiceMode = ref(false)
let audioContext = null
let analyser = null
let mediaStream = null
let dataArray = null
let animationId = null
let mediaRecorder = null
let audioChunks = []
const waveformCanvas = ref(null)

const showPlanDialog = ref(false)

const handlePlanSelect = (plan) => {
  console.log('选择了学习方案:', plan)
}

// 是否禁用输入
const isInputDisabled = ref(false)

// 保存最后一条AI消息的内容
const lastAiMessageContent = ref('')

// 打字机实例
const typewriterInstance = createTypewriter({
  speed: 50,
  minSpeed: 10,
  maxSpeed: 50
})

const currentTypingIndex = ref(-1)// 当前打字索引

const skipInfo = ref()//跳转信息

// ==================== 数字人初始化 ====================
const initDigitalHuman = () => {
  if (digitalHuman) {
    digitalHuman.destroy()
    digitalHuman = null
  }

  digitalHuman = new DigitalHuman(AVATAR_CONFIG)

  // 设置当前参数
  digitalHuman.setAvatar(selectedAvatar.value)
  digitalHuman.setVoice(selectedVoice.value)
  digitalHuman.setBackground(selectedBackground.value)

  // 事件监听
  digitalHuman
    .on('connected', (resp) => {
      console.log('数字人已连接', resp)
      isAvatarReady.value = true
      isAvatarLoading.value = false
    })
    .on('disconnected', (e) => {
      console.log('数字人已断开', e)
      isAvatarReady.value = false
      isAvatarLoading.value = false
      if (e) {
        ElMessage.error('连接已断开')
      }
    })
    .on('subtitle', (text) => {
      subtitle.value = text
    })
    .on('error', (error) => {
      console.error('数字人错误:', error)
      isAvatarLoading.value = false
      ElMessage.error('数字人错误: ' + error?.message)
    })
    .on('playing', () => {
      isAvatarSpeaking.value = true
    })
    .on('play', () => {
      console.log('开始播放')
    })

  return digitalHuman
}

// 数字人安全调用包装：仅在数字人就绪时执行，任何数字人内部错误只记日志、不抛出，避免影响主流程
const safeSpeak = async (text, options = {}) => {
  if (!digitalHuman || !isAvatarReady.value) return false
  try {
    return await digitalHuman.speak(text, options)
  } catch (e) {
    console.warn('数字人播报失败(已忽略):', e)
    return false
  }
}
const safeDoAction = async (actionTag) => {
  if (!digitalHuman || !isAvatarReady.value) return false
  try {
    return await digitalHuman.doAction(actionTag)
  } catch (e) {
    console.warn('数字人动作失败(已忽略):', e)
    return false
  }
}

// ==================== 启动数字人 ====================
const startAvatar = async () => {
  if (!digitalHuman) {
    initDigitalHuman()
  }

  if (isAvatarReady.value) return

  isAvatarLoading.value = true
  avatarStartFailed.value = false

  try {
    // 启动时传入 air: 1 开启自动动作
    await digitalHuman.start(avatarContainer.value, {
      avatarId: selectedAvatar.value,
      voiceId: selectedVoice.value,
      backgroundUrl: selectedBackground.value,
      air: 1, // 开启自动动作
    })

    ElMessage.success('数字人启动成功')
    isAvatarLoading.value = false


    await speakLastAiMessage()

  } catch (e) {
    console.error('启动数字人失败:', e)
    isAvatarLoading.value = false
    isAvatarReady.value = false
    avatarStartFailed.value = true
    // 启动失败后销毁并置空实例，使后续对话仅跳过数字人相关操作（播报/动作），不影响对话本身
    if (digitalHuman && isAvatarReady.value) {
      try {
        digitalHuman.destroy()
      } catch (err) {
        console.error('销毁数字人失败:', err)
      }
      digitalHuman = null
    }
    ElMessage.error('启动数字人失败: ' + e?.message)
  }
}

// ==================== 关闭数字人 ====================
const stopAvatar = async () => {
  if (!digitalHuman) return

  try {
    await digitalHuman.stop()
    isAvatarReady.value = false
    isAvatarLoading.value = false
    subtitle.value = ''
    ElMessage.success('数字人已关闭')
  } catch (e) {
    console.error('停止数字人失败:', e)
    ElMessage.error('关闭数字人失败: ' + e?.message)
  }
}

// ==================== 切换数字人状态 ====================
const toggleAvatar = async () => {
  if (isAvatarReady.value) {
    await stopAvatar()
  } else {
    await startAvatar()
  }
}

// ==================== 播报最后一条AI消息或问候语 ====================
const speakLastAiMessage = async () => {
  let lastAiMessage = null
  let j = null
  for (let i = conversation.value.length - 1; i >= 0; i--) {
    if (conversation.value[i].type === 'ai') {
      lastAiMessage = conversation.value[i]
      j = i
      break
    }
  }

  // 数字人未启动/启动失败时：仅恢复并直接显示最后一条消息文本，跳过播报与打字机
  if (!digitalHuman || !isAvatarReady.value) {
    if (lastAiMessage && j === conversation.value.length - 1
      && lastAiMessage.content === '' && lastAiMessageContent.value) {
      conversation.value[j] = {
        ...lastAiMessage,
        content: lastAiMessageContent.value,
        displayContent: lastAiMessageContent.value,
        isTyping: false
      }
      lastAiMessageContent.value = ''
      await nextTick()
      scrollToBottomSmooth()
    }
    return
  }

  if (lastAiMessage && j === conversation.value.length - 1) {
    const content = lastAiMessageContent.value || lastAiMessage.content

    if (!content || content.trim() === '') {
      console.log('AI消息内容为空，跳过播报')
      return
    }

    if (lastAiMessage.content === '' && lastAiMessageContent.value) {
      await Promise.all([
        digitalHuman.speak(content, { voiceId: selectedVoice.value }),
        await digitalHuman.doAction(humanAction.value[0]),
        typewriterUpdateMessage(j, content)
      ])
      lastAiMessageContent.value = ''
    } else {
      await digitalHuman.doAction(humanAction.value[0])
      await safeSpeak(content, { voiceId: selectedVoice.value })
    }
  } else {
    const greeting = '你好！我是你的智能学习小助手，请问有什么可以帮助你的？'

    const message = {
      type: 'ai',
      content: '',
      displayContent: '',
      isTyping: true
    }
    const index = conversation.value.length
    conversation.value.push(message)

    await Promise.all([
      await digitalHuman.doAction(humanAction.value[0]),
      await digitalHuman.speak(greeting, { voiceId: selectedVoice.value }),
      typewriterUpdateMessage(index, greeting)
    ])
    await nextTick()
    scrollToBottomSmooth()
  }
}

// ==================== 重新启动数字人 ====================
const restartAvatar = async () => {
  if (!digitalHuman) return

  try {
    await digitalHuman.restart(avatarContainer.value, {
      avatarId: selectedAvatar.value,
      voiceId: selectedVoice.value,
      backgroundUrl: selectedBackground.value,
    })
    await digitalHuman.doAction(humanAction.value[0])
  } catch (e) {
    console.error('重启数字人失败:', e)
    ElMessage.error('切换配置失败: ' + e?.message)
  }
}

// ==================== 设置变更处理 ====================
const onAvatarChange = () => {
  if (digitalHuman) {
    digitalHuman.setAvatar(selectedAvatar.value)
  }
  if (isAvatarReady.value) restartAvatar()
}

const onVoiceChange = () => {
  if (digitalHuman) {
    digitalHuman.setVoice(selectedVoice.value)
  }
  if (isAvatarReady.value) restartAvatar()
}

const onBackgroundChange = () => {
  if (digitalHuman) {
    digitalHuman.setBackground(selectedBackground.value)
  }
  if (isAvatarReady.value) restartAvatar()
}

// ==================== 打断数字人播报 ====================
const interruptAvatar = async () => {
  if (!digitalHuman || !isAvatarReady.value) return

  try {
    await digitalHuman.interrupt()
    console.log('已打断数字人播报')

    if (currentTypingIndex.value >= 0 && currentTypingIndex.value < conversation.value.length) {
      const item = conversation.value[currentTypingIndex.value]
      if (item && item.isTyping) {
        const fullContent = item.content || item.displayContent || ''
        item.content = fullContent
        item.displayContent = fullContent
        item.isTyping = false
        currentTypingIndex.value = -1
      }
    }
  } catch (e) {
    console.error('打断失败:', e)
  }
}

// ==================== 打字机效果 ====================
const typewriterUpdateMessage = async (index, content) => {
  if (index < 0 || index >= conversation.value.length) {
    return
  }

  const updatedMessage = {
    ...conversation.value[index],
    isTyping: true,
    content: '',
    displayContent: ''
  }
  conversation.value[index] = updatedMessage
  currentTypingIndex.value = index

  await nextTick()
  scrollToBottomSmooth()

  return typewriterDisplayText(index, content)
}

const typewriterDisplayText = async (index, content) => {
  const fullText = content
  let currentIndex = 0

  return new Promise((resolve) => {
    const timer = setInterval(() => {
      currentIndex++
      const displayText = fullText.substring(0, currentIndex)

      if (conversation.value[index]) {
        conversation.value[index] = {
          ...conversation.value[index],
          displayContent: displayText,
          content: displayText
        }
      }

      if (currentIndex % 10 === 0) {
        scrollToBottomSmooth()
      }

      if (currentIndex >= fullText.length) {
        clearInterval(timer)
        if (conversation.value[index]) {
          conversation.value[index] = {
            ...conversation.value[index],
            isTyping: false,
            displayContent: fullText,
            content: fullText
          }
        }
        currentTypingIndex.value = -1
        resolve(fullText)
      }
    }, 30)
  })
}

// ==================== 添加AI消息（带打字机） ====================
const addAiMessageWithTypewriter = async (content, extraData = {}) => {
  const message = {
    type: 'ai',
    content: '',
    displayContent: '',
    isTyping: true,
    ...extraData
  }

  const index = conversation.value.length
  conversation.value.push(message)
  currentTypingIndex.value = index

  await nextTick()
  scrollToBottomSmooth()

  return typewriterDisplayText(index, content)
}

// ==================== 语音输入 ====================
const toggleVoiceInput = async () => {
  // 检查是否禁用输入
  if (isInputDisabled.value) {
    return
  }

  try {
    // 打断当前数字人播报
    await interruptAvatar()

    // 如果正在录音，则停止录音并识别
    if (isRecording.value) {
      if (asrInstance) {
        // 关键修正：调用 stopAndRecognize() 触发识别
        await asrInstance.stopAndRecognize()
        // onResult 回调会自动处理识别结果并发送消息
      } else {
        // 如果 asrInstance 不存在，直接清理状态
        if (recordingTimer) {
          clearInterval(recordingTimer)
          recordingTimer = null
        }
        isRecording.value = false
        recordingDuration.value = 0
        ElMessage.info('录音已停止')
      }
      return
    }

    // 检查浏览器是否支持录音
    if (!ASR.isSupported()) {
      ElMessage.error('当前浏览器不支持录音功能，请使用 Chrome、Edge 或 Safari 浏览器')
      return
    }

    // 创建 ASR 实例
    asrInstance = new ASR({
      sampleRate: 16000,
      echoCancellation: true,
      noiseSuppression: true,
      convertToSimplified: true,
      
      onStart: () => {
        isRecording.value = true
        recordingDuration.value = 0
        recordingTimer = setInterval(() => {
          recordingDuration.value++
        }, 1000)
        ElMessage.success('开始录音，点击按钮停止')
      },
      
      onStop: () => {
        if (recordingTimer) {
          clearInterval(recordingTimer)
          recordingTimer = null
        }
        isRecording.value = false
      },
      
      onResult: (text) => {
        if (text && text.trim()) {
          userInput.value = text
          ElMessage.success('识别成功！')
          console.log('识别成功: ' + text)

          // 自动发送消息
          // nextTick(() => {
          //   sendMessage()
          // })
        } else {
          ElMessage.warning('未识别到有效内容，请重试')
        }
      },
      
      onError: (error) => {
        const errorMsg = ASR.getErrorMessage(error)
        console.error('ASR 错误:', error)
        ElMessage.error(errorMsg)
        
        if (recordingTimer) {
          clearInterval(recordingTimer)
          recordingTimer = null
        }
        isRecording.value = false
        recordingDuration.value = 0
      }
    })

    await asrInstance.startRecording()

  } catch (e) {
    console.error('语音识别失败:', e)
    const errorMsg = ASR.getErrorMessage(e)
    ElMessage.error(errorMsg)

    if (recordingTimer) {
      clearInterval(recordingTimer)
      recordingTimer = null
    }
    isRecording.value = false
    recordingDuration.value = 0
    
    if (asrInstance) {
      try {
        asrInstance.cancel()
      } catch (cleanupError) {
        console.error('清理 ASR 实例失败:', cleanupError)
      }
      asrInstance = null
    }
  }
}

// ==================== 语音模式切换 ====================
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

// ==================== ASR语音识别 ====================
const toggleNativeRecording = async () => {
  if (isInputDisabled.value) {
    return
  }

  if (isRecording.value) {
    // 打断当前数字人播报
    await interruptAvatar()
    stopNativeRecording()
  } else {
    // 打断当前数字人播报
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
    
    ElMessage.success('开始录音，点击按钮停止')
  } catch (error) {
    console.error('录音启动失败:', error)
    ElMessage.error('无法访问麦克风，请检查权限')
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
        ElMessage.warning('未识别到语音内容')
      }
    } catch (error) {
      console.error('语音识别失败:', error)
      ElMessage.error('语音识别失败，请重试')
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
    const barCount = 128
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

// ==================== Agent API 调用 ====================
const sendToAgent = async (text, rsType = null, sessionId = 'none') => {
  if (!text?.trim()) {
    ElMessage.warning('请输入内容')
    return
  }

  isInputDisabled.value = true
  isAgentLoading.value = true

  await interruptAvatar()

  // 添加用户消息
  conversation.value.push({
    type: 'user',
    content: text.trim(),
  })

  await nextTick()
  scrollToBottomSmooth()

  // 添加加载中的AI消息占位（显示加载动画）
  const loadingIndex = conversation.value.length
  conversation.value.push({
    type: 'ai',
    content: '',// 气泡显示打字机流式输出的片段
    displayContent: '',// 显示打字机流式输出的完整内容
    isTyping: false,// 标记是否为打字机流式输出状态
    isLoading: true  // 标记是否为ai加载状态
  })
  await nextTick()
  scrollToBottomSmooth()

  // 判断是否学习计划与其它资源一同生成
  if(rsType === 'cancel'){
    // 移除加载占位
    conversation.value.splice(loadingIndex, 1)
    const tipText = '学习计划只能单独生成哦~'
    if (digitalHuman && isAvatarReady.value) {
      await safeDoAction(humanAction.value[1])
      await safeSpeak(tipText, { voiceId: selectedVoice.value })
    }
    await addAiMessageWithTypewriter(tipText)
    isAgentLoading.value = false
    isInputDisabled.value = false
    await nextTick()
    scrollToBottomSmooth()
    return
  }

  try {
    if(sessionId?.isTrusted){
      sessionId = 'none'
    }
    const result = await postTextApi({
      userId: agentUserId.value,
      text: text.trim(),
      // 判断如果是数组则赋值99，否则使用原值
      rsType: Array.isArray(rsType) ? 99 : rsType,
      sessionId: sessionId,
      // 如果为rsType为数组，说明是多种资源生成
      rsArray: Array.isArray(rsType) ? rsType : []
    })
    presetSessionId.value = ''// 清空获取到的复习会话ID

    // 移除加载占位
    conversation.value.splice(loadingIndex, 1)

    if (result.code !== 1) {
      throw new Error('Agent返回错误: ' + JSON.stringify(result))
    }

    // 判断是否为多个资源生成
    if(result.data?.detail && result.data.rsType === 99){
      // 遍历多个资源生成
      for (const item of result.data.detail) {
        const content = item.content || '资源生成中...'
        const rsType = item.rsType
        const resource = item.resource
        
        if (digitalHuman && isAvatarReady.value) {
          await safeDoAction(humanAction.value[1])
          await safeSpeak(content, { voiceId: selectedVoice.value })
        }
        
        await addAiMessageWithTypewriter(content, {
          resource: resource,
          rsType: rsType,
          isBatchGenerate: true
        })
        
        const index = conversation.value.findIndex(item =>
          ((item?.resource?.taskId || null) === (resource?.taskId || null) &&
            (item?.rsType || null) === (rsType || null))
        )
        
        if (resource?.status === 1) {
          isRsSuccess(index, rsType, resource.taskId)
        } else {
          conversation.value[index] = item
        }
        
        await nextTick()
        scrollToBottomSmooth()
      }
      isAgentLoading.value = false
      isInputDisabled.value = false
      return
    }

    //其他情况
    if (result.data?.resource) {
      const content = result.data.content

      if (digitalHuman && isAvatarReady.value) {
        await safeDoAction(humanAction.value[1])
        await safeSpeak(content, { voiceId: selectedVoice.value })
      }

      await addAiMessageWithTypewriter(content, {
        resource: result.data.resource,
        rsType: result.data.rsType
      })

      const index = conversation.value.findIndex(item =>
        ((item?.resource?.taskId || null) === (result?.data?.resource?.taskId || null) &&
          (item?.rsType || null) === (result?.data?.rsType || null))
      )

      if (result.data.resource.status === 1) {
        isRsSuccess(index, result.data.rsType, result.data.resource.taskId)
        console.log('轮询结果：', result.data)
      } else {
        conversation.value[index] = result.data
      }
    } else {
      const agentData = result.data?.data || result.data
      const status = agentData?.status || result.data?.status || 0
      const followUpQuestions = agentData?.follow_up_questions
      const guidance = agentData?.guidance || result.data?.guidance || ''

      if (status === 'need_more_info' && followUpQuestions?.length > 0) {
        let question;
        if (Array.isArray(followUpQuestions) && followUpQuestions.length > 0) {
          question = followUpQuestions[0];
        } else if (typeof followUpQuestions === 'string') {
          question = followUpQuestions;
        } else {
          question = '抱歉，我遇到了一些问题，请稍后再试。';
        }
        if (digitalHuman && isAvatarReady.value) {
          await safeDoAction(humanAction.value[1])
          await safeSpeak(question, { voiceId: selectedVoice.value })
        }
        await addAiMessageWithTypewriter(question)
      } else if (guidance && guidance !== '0') {
        let speakTextContent = guidance;

        if (agentData?.des_stage === 'registration_complete') {
          speakTextContent = `初次画像构建成功！\n${guidance.replaceAll('###', '')}`;
          // 1. 从 localStorage 获取现有数据
          const loginUserStr = localStorage.getItem('loginUser');
          if (loginUserStr) {
            // 2. 解析为对象
            const loginUser = JSON.parse(loginUserStr);

            // 3. 修改 isBuildProfile 为 1
            loginUser.isBuildProfile = 1;

            // 4. 重新存入 localStorage
            localStorage.setItem('loginUser', JSON.stringify(loginUser));

            // 5. 更新 localStorage 后
            emitter.emit('profileUpdated', { isBuildProfile: 1 })

            // 6.检测loginUser.tour是否为1，是的话就打开layout.vue的漫游式引导
            // if (loginUser.tour === 1) {
            //   emitter.emit('startTour')
            // }

          }
        }

        if (digitalHuman && isAvatarReady.value) {
          await safeDoAction(humanAction.value[2])
          await safeSpeak(speakTextContent, { voiceId: selectedVoice.value })
        }
        await addAiMessageWithTypewriter(speakTextContent)
      } else if (agentData?.content) {
        const contentText = agentData.content
        if (digitalHuman && isAvatarReady.value) {
          await safeDoAction(humanAction.value[1])
          await safeSpeak(contentText, { voiceId: selectedVoice.value })
        }
        await addAiMessageWithTypewriter(contentText)
      } else if (status === 0 || status === '0') {
        const fallbackText = agentData?.content || '抱歉，我遇到了一些问题，请稍后再试。';
        if (digitalHuman && isAvatarReady.value) {
          await safeDoAction(humanAction.value[1])
          await safeSpeak(fallbackText, { voiceId: selectedVoice.value })
        }
        await addAiMessageWithTypewriter(fallbackText)
      }
    }

  } catch (e) {
    console.error('Agent请求失败:', e)
    ElMessage.error('请求失败: ' + e?.message)
    
    // 移除加载占位
    conversation.value.splice(loadingIndex, 1)
    
    const errorText = '抱歉，我遇到了一些问题，请稍后再试。'
    if (digitalHuman && isAvatarReady.value) {
      await safeDoAction(humanAction.value[1])
      await safeSpeak(errorText, { voiceId: selectedVoice.value })
    }
    await addAiMessageWithTypewriter(errorText)
  } finally {
    isAgentLoading.value = false
    isInputDisabled.value = false
    await nextTick()
    scrollToBottomSmooth()
  }
}

// ==================== 发送消息 ====================
const sendMessage = (sessionId = 'none') => {
  if (isInputDisabled.value) return
  if (!userInput.value?.trim()) return
  const text = userInput.value
  userInput.value = ''
  sendToAgent(text, findString(text), sessionId)
}

// ==================== 滚动 ====================
const scrollToBottomSmooth = () => {
  if (scrollbarRef.value) {
    const wrapEl = scrollbarRef.value.$el?.querySelector?.('.el-scrollbar__wrap')
    if (wrapEl) {
      wrapEl.scrollTo({
        top: wrapEl.scrollHeight,
        behavior: 'smooth'
      })
    }
  }
}

const scrollToTop = () => {
  if (scrollbarRef.value) {
    const wrapEl = scrollbarRef.value.$el?.querySelector?.('.el-scrollbar__wrap')
    if (wrapEl) {
      wrapEl.scrollTo({
        top: 0,
        behavior: 'smooth'
      })
    }
  }
}

// ==================== 资源相关 ====================
// 获取资源类型名称
const getResourceTypeName = (type) => {
  const map = {
    0: 'PPT',
    1: '思维导图',
    2: '讲解文档',
    3: '拓展阅读',
    4: '编程题',
    5: '视频搜索',
    6: '学习动画',
    7: '题库试卷',
    8: '智学路径',
  }
  return map[type] || '资源'
}

// 打开资源
const openResource = (item) => {
  saveSkip(item.rsType, item.resource.taskId)
  ElMessage.success('正在跳转打开')
  switch (item.rsType) {
    case 0:
      router.push('/ppt')
      break
    case 1:
      router.push('/mindMap')
      break
    case 2:
      router.push('/word')
      break
    case 3:
      router.push('/reading')
      break
    case 4:
      router.push('/code')
      break
    case 5:
      router.push('/video')
      break
    case 6:
      router.push('/anima')
      break
    case 7:
      router.push('/paper')
      break
    case 8:
      router.push('/pathPlan')
      break
    default:
      console.log('不存在该资源，无法跳转')
  }

  ElNotification({
    title: '操作提示',
    message: `正在跳转打开 ${getResourceTypeName(item.rsType)}`,
    type: 'success',
    position: 'bottom-left',
    duration: 3000,
    showClose: true,
  })
}

// 获取进度(并发，轮询)
const isRsSuccess = async (index, rsType, taskId) => {
  console.log('开始轮询进度')
  try {
    let progressRes = await getProgressApi(agentUserId.value, rsType, taskId)
    // 判断是否冲突弹窗
    if(progressRes.data.resource?.suggestionWarning && progressRes.data.resource.suggestionWarning != 1 && progressRes.data.resource.suggestionWarning != null){
      console.log('有冲突弹窗')
      if (showConflictDialog.value) {
        console.log('冲突弹窗已打开，跳过')
      } else {
        conflictData.value = {
          createTime: progressRes.data.resource.createTime,
          suggestionWarning: progressRes.data.resource.suggestionWarning,
          rsType: progressRes.data.rsType,
          taskId: progressRes.data.resource?.taskId || taskId
        }
        showConflictDialog.value = true
        console.log('打开冲突弹窗')
      }
    }

    console.log(progressRes)
    if (progressRes.data.resource.status === 1) {
      let nowNum = 0
      let maxNum = 100
      while (nowNum < maxNum && progressRes.data.resource.status === 1) {
        nowNum++
        console.log(`rsType${rsType}的任务 ${taskId}：轮询中...${nowNum}/${maxNum}次`)
        await new Promise(resolve => setTimeout(resolve, 10000))

        console.log('再获取进度次数：', nowNum)
        progressRes = await getProgressApi(agentUserId.value, rsType, taskId)
        // 判断是否冲突弹窗
        if(progressRes.data.resource?.suggestionWarning && progressRes.data.resource.suggestionWarning != 1 && progressRes.data.resource.suggestionWarning != null){
          console.log('有冲突弹窗')
          if (showConflictDialog.value) {
            console.log('冲突弹窗已打开，跳过')
          } else {
            conflictData.value = {
              createTime: progressRes.data.resource.createTime,
              suggestionWarning: progressRes.data.resource.suggestionWarning,
              rsType: progressRes.data.rsType,
              taskId: progressRes.data.resource?.taskId || taskId
            }
            showConflictDialog.value = true
            console.log('打开冲突弹窗')
          }
        }
      }
    }
    
    let indexTrue = index
    for (let i = 0; i < conversation.value.length; i++) {
      const item = conversation.value[i]
      if (item?.resource?.taskId && (item.resource.taskId == taskId)) {
        indexTrue = i
      }
    }

    if (progressRes.data.resource.status === 1) {
      ElMessage.error('生成超时')
      conversation.value[indexTrue].resource.status = 3
      conversation.value[indexTrue].content = '生成超时'
      if (digitalHuman && isAvatarReady.value) {
        await safeSpeak('生成超时', { voiceId: selectedVoice.value })
      }
    } else if (progressRes.data.resource.status === 2) {
      ElMessage.success(progressRes.data.content || '生成成功')
      const wasBatchGenerate = conversation.value[indexTrue]?.isBatchGenerate
      conversation.value[indexTrue] = progressRes.data
      if (wasBatchGenerate) {
        conversation.value[indexTrue].isBatchGenerate = true
      }
      if (digitalHuman && isAvatarReady.value) {
        await safeSpeak(progressRes.data.content || '生成成功', { voiceId: selectedVoice.value })
      }
    } else if (progressRes.data.resource.status === 3) {
      ElMessage.error(progressRes.data.content || '生成失败')
      conversation.value[indexTrue].content = progressRes.data.content || '生成失败'
      conversation.value[indexTrue].resource.status = 3
      if (digitalHuman && isAvatarReady.value) {
        await safeSpeak(progressRes.data.content || '生成失败', { voiceId: selectedVoice.value })
      }
    }

    
  } catch (e) {
    console.error('轮询进度失败', e)
    let indexTrue = index
    for (let i = 0; i < conversation.value.length; i++) {
      const item = conversation.value[i]
      if (item?.resource?.taskId && (item.resource.taskId == taskId)) {
        indexTrue = i
      }
    }
    conversation.value[indexTrue] = {
      type: 'ai',
      content: '抱歉，我遇到了一些问题，请稍后再试。',
    }
    if (digitalHuman && isAvatarReady.value) {
      await safeDoAction(humanAction.value[1])
      await safeSpeak('抱歉，我遇到了一些问题，请稍后再试。', { voiceId: selectedVoice.value })
    }
  } finally {
    console.log('轮询结束')
  }
}

const checkTask = async () => {
  console.log('开始检查任务')
  for (let i = 0; i < conversation.value.length; i++) {
    const item = conversation.value[i]
    if (item.resource && (item.resource.status === 1)) {
      await isRsSuccessTask(i, item.rsType, item.resource.taskId)
    }
  }
  console.log('检查任务结束')
}
// 【检查任务专用】获取进度（轮询）
const progressResTask = ref({})
const isRsSuccessTask = async (index, rsType, taskId) => {
  console.log('开始轮询进度')
  try {
    progressResTask.value = await getProgressApi(agentUserId.value, rsType, taskId)
    
    let indexTrue = index
    if (progressResTask.value.data.resource.status === 1) {
      let nowNum = 0
      let maxNum = 100
      while (nowNum < maxNum && progressResTask.value.data.resource.status === 1) {
        nowNum++
        console.log(`rsType${rsType}的任务 ${taskId}：轮询中...${nowNum}/${maxNum}次`)
        await new Promise(resolve => setTimeout(resolve, 10000))

        console.log('再获取进度次数：', nowNum)
        progressResTask.value = await getProgressApi(agentUserId.value, rsType, taskId)
      }

      for (let i = 0; i < conversation.value.length; i++) {
        const item = conversation.value[i]
        if (item?.resource?.taskId && (item.resource.taskId == taskId)) {
          indexTrue = i
        }
      }
    }

    if (progressResTask.value.data.resource.status === 1) {
      ElMessage.success('生成超时')
      conversation.value[indexTrue].resource.status = 3
    } else if (progressResTask.value.data.resource.status === 2) {
      ElMessage.success('生成成功')
      conversation.value[indexTrue] = progressResTask.value.data
    } else if (progressResTask.value.data.resource.status === 3) {
      conversation.value[indexTrue].content = '生成失败'
      conversation.value[indexTrue].resource.status = 3
    }

    
  } catch (e) {
    console.error('轮询进度失败', e)
    conversation.value[index] = {
      type: 'ai',
      content: '抱歉，我遇到了一些问题，请稍后再试。',
    }
  } finally {
    progressResTask.value = {}
    console.log('轮询结束')
  }
}

const reCreate = async (rsType, taskId) => {
  isInputDisabled.value = true

  try {
    const result = await reCreateApi(agentUserId.value, rsType, taskId)
    if (result.code !== 1) {
      throw new Error('重新生成失败: ' + JSON.stringify(result))
    }
    ElMessage.success('重新生成成功')

    const content = result.data.content
    if (digitalHuman && isAvatarReady.value) {
      await safeSpeak(content, { voiceId: selectedVoice.value })
    }

    await addAiMessageWithTypewriter(content, {
      resource: result.data.resource,
      rsType: result.data.rsType
    })

    scrollToBottomSmooth()
    const index = conversation.value.findIndex(item =>
      ((item?.resource?.taskId || null) === (result?.data?.resource?.taskId || null) &&
        (item?.rsType || null) === (result?.data?.rsType || null))
    )

    if (result.data.resource.status === 1) {
      isRsSuccess(index, result.data.rsType, result.data.resource.taskId)
      console.log('轮询结果：', result.data)
    } else {
      conversation.value[index] = result.data
    }
  } catch (e) {
    console.log('重新生成异常')
  } finally {
    isInputDisabled.value = false
  }
}

// ==================== 加载历史记录 ====================
const loadHistory = async () => {
  if (isLoadingHistory.value) return

  isLoadingHistory.value = true
  try {
    const lastId = firstChatId.value || null

    const response = await aiHistoryApi(agentUserId.value, lastId)

    if (response.code !== 1) {
      throw new Error(response.msg || '加载历史记录失败')
    }

    const historyData = response.data || []

    if (historyData.length === 0) {
      hasMoreHistory.value = false
      return
    }

    hasMoreHistory.value = historyData.length === 10

    const reversedHistory = historyData.reverse()

    if (reversedHistory.length > 0) {
      firstChatId.value = reversedHistory[0].id
    }

    const processedHistory = historyData.map(item => {
      if (item.type === 'ai' && (!item.content || item.content === null || item.content === '')) {
        return {
          ...item,
          content: '抱歉，我遇到了一些问题，请稍后再试。',
          displayContent: '抱歉，我遇到了一些问题，请稍后再试。'
        }
      }
      return item
    })

    conversation.value = [...processedHistory, ...conversation.value]

    if (historyData.length > 0) {
      firstChatId.value = historyData[0].id
    }

    await nextTick()
    scrollToTop()

  } catch (e) {
    console.error('加载历史记录失败:', e)
    ElMessage.error('加载历史记录失败: ' + e.message)
  } finally {
    isLoadingHistory.value = false
  }
}

// ==================== 生命周期 ====================
//监听数字人形象
// 动作配置映射表
const avatarActionMap = {
  '110332017': ['A_RH_hello_O', 'A_RLH_emphasize_O', 'A_U_No_pointing_O'],
  '111286001': ['A_U_hello_O', 'A_RH_emphasize2_O', 'A_RLH_applaud_C'],
  // 可以继续添加更多数字人配置
}
watch(selectedAvatar, (newValue, oldValue) => {
  console.log(`数字人从 "${oldValue}" 变为 "${newValue}"`)
  const actions = avatarActionMap[newValue]
  if (actions) {
    humanAction.value = actions
  }

})
let loginUser = null
onMounted(async () => {
  // 获取用户ID
  const userStr = localStorage.getItem('loginUser')
  if (userStr) {
    try {
      loginUser = JSON.parse(userStr)
      agentUserId.value = typeof loginUser.id === 'string' ? loginUser.id : String(loginUser.id)
    } catch (e) {
      console.error('用户信息解析失败', e)
    }
  }

  // 1. 加载历史记录
  if (agentUserId.value) {
    try {
      const response = await aiHistoryApi(agentUserId.value, 0)

      if (response.code === 1 && response.data && response.data.length > 0) {
        let historyData = response.data

        hasMoreHistory.value = historyData.length === 10

        if (historyData.length > 0) {
          firstChatId.value = historyData[0].id
        }

        const processedHistory = historyData.map((item, index) => {
          if (item.type === 'ai' && (!item.content || item.content === null || item.content === '')) {
            return {
              ...item,
              content: '抱歉，我遇到了一些问题，请稍后再试。',
              displayContent: '抱歉，我遇到了一些问题，请稍后再试。'
            }
          }
          return item
        })

        const firstMessageIndex = 0
        const firstMessage = processedHistory[firstMessageIndex]
        const isFirstAiMessage = firstMessage && firstMessage.type === 'ai'

        if (isFirstAiMessage) {
          if (firstMessage.content && firstMessage.content.length > 150) {
            // 超过150字不使用打字机效果，直接显示
            lastAiMessageContent.value = firstMessage.content
          } else {
            // 150字以内使用打字机效果
            lastAiMessageContent.value = firstMessage.content
            processedHistory[firstMessageIndex] = {
              ...firstMessage,
              content: '',
              displayContent: '',
              isTyping: true
            }
          }
        }

        conversation.value = processedHistory.reverse()

        await nextTick()
        scrollToBottomSmooth()
      }
    } catch (e) {
      console.error('加载初始历史记录失败:', e)
    }
  }

  // 2. 初始化数字人
  initDigitalHuman()

  // 3. 启动数字人（等待启动完成）
  await toggleAvatar()

  // 3.1 数字人未启动/启动失败时，恢复显示被清空的最后一条历史消息
  if (!isAvatarReady.value) {
    await speakLastAiMessage()
  }

  // 4. 处理预设消息（数字人已启动完成）
  // 检查 应用 中是否有要打开的复习操作
  if(isSkip(10) === false){
    console.log('没有复习操作需要提前打开')
  }else{
    console.log('【复习】跳转信息:', skipInfo.value)
    try{
      handlePresetMessage()//添加复习预设消息
    }catch(e){
      ElMessage.error('该编程题不存在，可能已经被删除了')
      console.log('打开失败')
    }
  }
  

  // 5. 启动任务检查
  await checkTask()

  
})

onUnmounted(() => {
})

const reviewMessageData = inject('reviewMessageData', ref({
  message: '',
  sessionId: '',
  timestamp: 0
}))

// 处理预设消息
const presetSessionId = ref('')
const lastProcessedMessage = ref('')
const handlePresetMessage = async () => {
  skipInfo.value = isSkip(10)//获取复习跳转信息

  let presetMessage = ''
  let sessionId = ''
  
  if (skipInfo.value) {
    try {
      console.log('复习预设数据:', skipInfo.value)
      presetMessage = skipInfo.value.message
      sessionId = skipInfo.value.sessionId
      removeSkip(10)//删除跳转信息
    } catch (e) {
      console.error('解析复习数据失败:', e)
    }
  }
  
  presetSessionId.value = sessionId
  if (presetMessage && presetMessage !== lastProcessedMessage.value) {
    lastProcessedMessage.value = presetMessage
    try {
      userInput.value = decodeURIComponent(presetMessage)
      await new Promise(resolve => setTimeout(resolve, 2000))
      sendMessage(presetSessionId.value)
    } catch (e) {
      console.error('解码预设消息失败:', e)
    }
  }
}

// 格式化冲突消息
const formatConflictMessage = (message) => {
  if (!message) return ''
  return message.replace(/\n/g, '<br/>')
}

// 处理冲突弹窗选择
const handleConflictOption = async (option) => {
  try {
    let conflictTaskId = conflictData.value.taskId
    if(conflictData.value.rsType === 8){
      conflictTaskId = conflictData.value.createTime
    }
    const response = await conflictApi(agentUserId.value, {
      id: conflictTaskId,
      rsType: conflictData.value.rsType,
      option: option
    })
    ElMessage.success(option ? '已接受，处理中...' : '已拒绝，处理中...')
    if (response.code === 1) {
      ElMessage.success('操作完成')
    } else {
      ElMessage.error(response.msg || '操作失败')
    }
  } catch (error) {
    console.error('冲突弹窗操作失败:', error)
    ElMessage.error('网络异常，操作失败')
  } finally {
    showConflictDialog.value = false
    conflictData.value = {
      createTime: '',
      suggestionWarning: '',
      rsType: null,
      taskId: null
    }
  }
}

onBeforeUnmount(() => {
  // 1. 先清理录音计时器
  if (recordingTimer) {
    clearInterval(recordingTimer)
    recordingTimer = null
  }

  // 2. 清理录音实例（取消录音，释放麦克风资源）
  if (asrInstance) {
    try {
      // 直接清理流，避免触发 onStop 回调
      asrInstance.cleanup()
    } catch (e) {
      console.error('清理 ASR 实例失败:', e)
    }
    asrInstance = null
  }

  // 3. 重置录音状态
  isRecording.value = false
  recordingDuration.value = 0

  // 4. 清理打字机效果
  if (currentTypingIndex.value >= 0) {
    currentTypingIndex.value = -1
  }

  // 5. 清理数字人（先检查是否已被销毁）
  if (digitalHuman && !digitalHuman.isDestroyed) {
    try {
      digitalHuman.destroy()
    } catch (e) {
      console.error('销毁数字人失败:', e)
    }
    digitalHuman = null
  }
})
</script>

<template>
  <div class="container">
    <!-- 左侧 - 数字人显示区域 -->
    <div class="left">
      <!-- 数字人容器（始终存在于DOM中） -->
      <div ref="avatarContainer" class="avatar-wrapper" :class="{ 'hidden': !isAvatarReady && !isAvatarLoading }"></div>

      <!-- 数字人未启动时显示占位图 -->
      <div v-if="!isAvatarReady && !isAvatarLoading && !avatarStartFailed" class="avatar-placeholder">
        <svg t="1781934467390" class="placeholder-icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="6275"><path class="placeholder-text" d="M512 0C228.693333 0 0 228.693333 0 512c0 282.453333 228.693333 512 512 512 282.453333 0 512-229.546667 512-512 0-283.306667-229.546667-512-512-512z m-34.133333 186.88h81.066666v230.4H477.866667v-230.4z m40.106666 637.44a302.250667 302.250667 0 0 1-298.666666-342.186667c2.56-12.8 5.12-26.453333 8.533333-39.253333 3.413333-12.8 7.68-25.6 12.8-38.4 5.973333-11.946667 11.946667-23.893333 18.773333-35.84 6.826667-11.093333 14.506667-22.186667 23.04-33.28 8.533333-10.24 17.066667-20.48 27.306667-29.866667 9.386667-9.386667 19.626667-17.92 30.72-25.6 11.093333-8.533333 22.186667-15.36 34.133333-22.186666l38.4 71.68c-8.533333 5.12-16.213333 10.24-24.746666 16.213333-7.68 5.973333-15.36 11.946667-22.186667 18.773333-6.826667 6.826667-13.653333 14.506667-19.626667 22.186667-6.826667 7.68-11.946667 15.36-17.066666 23.893333-5.12 8.533333-9.386667 17.066667-13.653334 26.453334-3.413333 8.533333-6.826667 17.92-9.386666 27.306666-2.56 9.386667-4.266667 19.626667-5.973334 29.013334-0.853333 10.24-1.706667 19.626667-1.706666 29.866666A219.306667 219.306667 0 0 0 517.973333 742.4c121.173333 0 220.16-98.133333 220.16-219.306667 0-10.24-0.853333-19.626667-1.706666-29.866666-1.706667-9.386667-3.413333-19.626667-5.973334-29.013334-2.56-9.386667-5.973333-18.773333-10.24-27.306666-3.413333-9.386667-7.68-17.92-12.8-26.453334s-11.093333-16.213333-17.066666-23.893333c-5.973333-7.68-12.8-15.36-19.626667-22.186667-6.826667-6.826667-14.506667-12.8-23.04-18.773333-7.68-5.973333-16.213333-11.093333-24.746667-16.213333l39.253334-71.68c11.946667 6.826667 23.04 13.653333 34.133333 22.186666 11.093333 7.68 21.333333 16.213333 30.72 25.6a297.813333 297.813333 0 0 1 68.266667 98.986667c5.12 12.8 10.24 25.6 13.653333 38.4a318.72 318.72 0 0 1 10.24 80.213333c0 165.546667-134.826667 301.226667-301.226667 301.226667z" fill="var(--primary)"  p-id="6276"></path></svg>
        <span class="placeholder-text">数字人未启动</span>
        <span class="placeholder-text subText">点击右侧按钮启动数字人开始对话</span>
      </div>

      <!-- 数字人加载中 -->
      <div v-else-if="isAvatarLoading" class="avatar-loading">
        <div class="loading-spinner"></div>
        <span class="loading-text">正在加载数字人...</span>
      </div>

      <!-- 数字人启动失败时显示示例图 -->
      <div v-else-if="avatarStartFailed" class="avatar-failed">
        <img src="@/assets/image/digitalmanOUTSample.png" alt="数字人启动失败" class="avatar-fail-image" />
      </div>

      <div class="subtitle" v-if="subtitle && isAvatarReady">{{ subtitle }}</div>
    </div>

    <!-- 右侧 - 对话面板 -->
    <div class="right">
      <div class="chat-card">
        <!-- 顶部 -->
        <div class="top">
          <div class="top-left">
            <img src="@/assets/logo/Logo.png" alt="logo" />
          </div>
          <el-button 
            size="small" 
            type="primary" 
            plain 
            @click="showPlanDialog = true"
            class="plan-btn"
          >
            查看方案
          </el-button>
          <div class="title">Agent智能对话答疑</div>
          <div class="top-right">
            <!-- 启动/关闭数字人按钮 -->
            <div class="avatar-toggle">
              <el-button
                :type="isAvatarReady ? 'danger' : 'primary'"
                size="small"
                @click="toggleAvatar"
                :loading="isAvatarLoading"
              >
                {{ isAvatarReady ? '关闭数字人' : '启动数字人' }}
              </el-button>
            </div>
            <div class="setting">
              <el-icon><Setting /></el-icon>
              <a href="javascript:void(0)">设置</a>
              <div class="dropdown">
                <div class="content">
                  <div class="setting-item">
                    <div class="setting-label">形象选择：</div>
                    <el-radio-group
                      v-model="selectedAvatar"
                      size="default"
                      @change="onAvatarChange"
                    >
                      <el-radio
                        v-for="item in avatarOptions"
                        :key="item.value"
                        :value="item.value"
                      >
                        {{ item.label }}
                      </el-radio>
                    </el-radio-group>
                  </div>

                  <div class="setting-item">
                    <div class="setting-label">语音选择：</div>
                    <el-radio-group
                      v-model="selectedVoice"
                      size="default"
                      @change="onVoiceChange"
                    >
                      <el-radio
                        v-for="item in voiceOptions"
                        :key="item.value"
                        :value="item.value"
                      >
                        {{ item.label }}
                      </el-radio>
                    </el-radio-group>
                  </div>

                  <div class="setting-item">
                    <div class="setting-label">背景选择：</div>
                    <el-radio-group
                      v-model="selectedBackground"
                      size="default"
                      @change="onBackgroundChange"
                    >
                      <el-radio
                        v-for="item in backgroundOptions"
                        :key="item.value"
                        :value="item.value"
                      >
                        {{ item.label }}
                      </el-radio>
                    </el-radio-group>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 聊天展示区域 -->
        <div class="showChat">
          <el-scrollbar ref="scrollbarRef" class="scrollbar">
            <!-- 加载更多历史记录按钮 -->
            <div class="load-more-wrapper" v-if="hasMoreHistory">
              <el-button
                type="primary"
                link
                @click="loadHistory"
                :loading="isLoadingHistory"
                class="load-more-btn"
              >
                <el-icon><Top /></el-icon>
                点击加载更多历史记录
              </el-button>
            </div>

            <div
              class="chatBox"
              v-for="(item, index) in conversation"
              :key="index"
            >
              <!-- AI回复 -->
              <div class="ai" v-if="item.type === 'ai'">
                <!-- 加载动画 -->
                <div v-if="item.isLoading" class="ai-loading">
                  <div class="loading-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                  <span class="loading-text">AI正在思考...</span>
                </div>
                <!-- 正常内容 -->
                <div v-else>
                  <!-- 文本 -->
                  <div class="text" :class="{ 'typing': item.isTyping }" v-html="formatMessage(item.content)"></div>
                  <!-- 资源展示 -->
                  <div class="resource" v-if="item.resource">
                    <!-- 加载中 -->
                    <div
                      class="loading"
                      v-if="item.resource.status !== 2 && item.resource.status !== 3"
                    >
                      <el-icon class="is-loading" :size="40" color="var(--el-color-primary)">
                        <Loading />
                      </el-icon>
                      <span class="loading-text">智能生成中</span>
                    </div>

                    <!-- 失败 -->
                    <div class="fail" v-else-if="item.resource.status === 3">
                      <el-icon class="shake-icon" :size="50"><CloseBold /></el-icon>
                      <div class="fail-text">生成失败 >_<</div>
                      <div class="fail-text">再尝试一次吧~</div>
                    </div>

                    <!-- 成功 -->
                    <div class="success" v-else-if="item.resource.status === 2">
                      <div class="rsBox" @click="openResource(item)">
                        <div class="iconBox">
                          <svg
                            v-if="item.rsType === 0"
                            viewBox="0 0 1024 1024"
                            width="50"
                            height="50"
                          >
                            <path
                              d="M874.660373 301.651825L597.328427 21.333227a77.226281 77.226281 0 0 0-14.506594-11.519943l-4.266646-2.133322h-2.986652A71.679642 71.679642 0 0 0 546.128683 0H200.957075A72.959635 72.959635 0 0 0 127.99744 72.106306v879.782268A72.959635 72.959635 0 0 0 200.957075 1023.99488h622.930219a71.252977 71.252977 0 0 0 72.106306-72.106306V352.424905a71.679642 71.679642 0 0 0-21.333227-50.77308z m-225.705538 308.905122a136.959315 136.959315 0 0 1-146.772599 110.506114h-37.546479l-18.77324 119.039405H368.636237L426.662613 506.024137h111.359444c70.826313 0 125.012708 25.173207 110.932778 104.53281z m-65.706338-298.665173V110.506114l200.958995 201.812324z"
                              fill="#f34832"
                            />
                            <path
                              d="M523.515462 567.037165h-31.573175l-16.213252 93.012868h33.706498c57.599712 0 64.426344-32.426505 64.426344-49.493086 0-32.426505-13.226601-43.519782-50.346415-43.519782z"
                              fill="#f34832"
                            />
                          </svg>
                          <svg
                            v-else-if="item.rsType === 1"
                            viewBox="0 0 1024 1024"
                            width="50"
                            height="50"
                          >
                            <path
                              d="M656.506875 185.088a151.872 151.872 0 0 0 151.68 151.68 151.872 151.872 0 0 0 151.808-151.68 151.872 151.872 0 0 0-151.744-151.68 151.872 151.872 0 0 0-151.68 151.68zM452.858875 95.744q-3.328 0-6.592 0.64-3.2 0.64-6.272 1.92-3.072 1.28-5.76 3.136-2.816 1.856-5.12 4.16-2.368 2.368-4.224 5.12-1.792 2.752-3.072 5.76-1.28 3.072-1.92 6.336-0.64 3.2-0.64 6.528 0 2.496 0.32 4.928a45.248 45.248 0 0 0-0.064 2.88v341.376h-56.192c-16-62.976-76.096-109.952-147.584-109.952-83.648 0-151.68 64.32-151.68 143.36 0 79.104 68.032 143.424 151.68 143.424 71.36 0 131.392-46.784 147.52-109.632h56.256v342.4a44.8 44.8 0 0 0 0 2.176q-0.256 2.304-0.256 4.608 0 3.264 0.64 6.528 0.64 3.2 1.92 6.336 1.28 3.008 3.072 5.76 1.92 2.752 4.224 5.12 2.304 2.368 5.12 4.16 2.688 1.856 5.76 3.136 3.072 1.28 6.272 1.92 3.264 0.64 6.592 0.64h141.632q3.328 0 6.592-0.64 3.2-0.64 6.272-1.92 3.072-1.28 5.824-3.136 2.752-1.792 5.12-4.16 2.304-2.368 4.16-5.12 1.856-2.752 3.072-5.76 1.28-3.072 1.92-6.336 0.64-3.2 0.64-6.528 0-3.328-0.64-6.592-0.64-3.2-1.92-6.272-1.28-3.072-3.072-5.76-1.856-2.816-4.16-5.12-2.368-2.368-5.12-4.224-2.752-1.856-5.76-3.072-3.072-1.28-6.4-1.92-3.2-0.64-6.528-0.64H490.618875v-315.52h103.872q3.328 0 6.592-0.704 3.2-0.64 6.272-1.92 3.072-1.28 5.824-3.072 2.752-1.92 5.12-4.224 2.304-2.304 4.16-5.12 1.856-2.688 3.072-5.76 1.28-3.072 1.92-6.336 0.64-3.2 0.64-6.528 0-3.328-0.64-6.528-0.64-3.264-1.92-6.336-1.28-3.072-3.072-5.76-1.856-2.816-4.16-5.12-2.368-2.368-5.12-4.16-2.752-1.92-5.76-3.136-3.136-1.28-6.4-1.92-3.2-0.64-6.528-0.64H490.618875v-315.52h103.872q3.328 0 6.592-0.64 3.2-0.64 6.272-1.92 3.072-1.28 5.824-3.2 2.752-1.792 5.12-4.096 2.304-2.368 4.16-5.12 1.856-2.752 3.072-5.76 1.28-3.136 1.92-6.4 0.64-3.2 0.64-6.528 0-3.264-0.64-6.528-0.64-3.2-1.92-6.336-1.28-3.008-3.072-5.76-1.856-2.752-4.16-5.12-2.368-2.304-5.12-4.16-2.752-1.856-5.76-3.136-3.072-1.28-6.4-1.92-3.2-0.64-6.528-0.64H452.858875z m274.688 89.344a80.704 80.704 0 0 1 161.408 0 80.768 80.768 0 0 1-161.408 0z m-71.04 335.168a151.872 151.872 0 0 0 151.68 151.68 151.872 151.872 0 0 0 151.808-151.68 151.872 151.872 0 0 0-151.744-151.68 151.872 151.872 0 0 0-151.68 151.68zM135.098875 512c0-41.984 36.16-76.16 80.64-76.16 44.48 0 80.64 34.176 80.64 76.16 0 42.112-36.16 76.288-80.64 76.288-44.48 0-80.64-34.176-80.64-76.224z m592.448 8.32a80.768 80.768 0 0 1 161.408 0c0 44.48-36.224 80.64-80.704 80.64s-80.64-36.16-80.64-80.64z m-71.04 335.168a151.808 151.808 0 0 0 151.68 151.68 151.872 151.872 0 0 0 151.808-151.68 151.872 151.872 0 0 0-151.744-151.68 151.872 151.872 0 0 0-151.68 151.68z m71.04 0c0-44.416 36.224-80.64 80.64-80.64 44.544 0 80.768 36.224 80.768 80.64 0 44.48-36.224 80.64-80.704 80.64s-80.64-36.16-80.64-80.64z"
                              fill="#61c886"
                            />
                          </svg>
                          <svg
                            v-else-if="item.rsType === 2"
                            viewBox="0 0 1024 1024"
                            width="50"
                            height="50"
                          >
                            <path
                              d="M854.6 288.7c6 6 9.4 14.1 9.4 22.6V928c0 17.7-14.3 32-32 32H192c-17.7 0-32-14.3-32-32V96c0-17.7 14.3-32 32-32h424.7c8.5 0 16.7 3.4 22.7 9.4l215.2 215.3zM790.2 326L602 137.8V326h188.2zM512 566.095l52.814 197.012a12 12 0 0 0 11.59 8.893h31.78a12 12 0 0 0 11.587-8.878l74.375-276a12 12 0 0 0 0.413-3.122c0-6.627-5.373-12-12-12h-35.576a12 12 0 0 0-11.695 9.31l-45.79 199.105-49.76-199.321A12 12 0 0 0 528.097 472h-32.192a12 12 0 0 0-11.643 9.094l-49.66 198.927-46.096-198.732a12 12 0 0 0-11.69-9.289h-35.381a12 12 0 0 0-3.115 0.411c-6.4 1.72-10.194 8.303-8.474 14.703l74.173 276A12 12 0 0 0 415.606 772h31.99a12 12 0 0 0 11.59-8.893L512 566.095z"
                              fill="#004198"
                            />
                          </svg>
                          <svg
                            v-else-if="item.rsType === 3"
                            viewBox="0 0 1024 1024"
                            width="50"
                            height="50"
                          >
                            <path
                              d="M908.8 153.6c-12.8 0-120.32-12.8-209.92-12.8-79.36 0-133.12 15.36-151.04 25.6-7.68 5.12-23.04 12.8-35.84 23.04-12.8-12.8-28.16-17.92-33.28-23.04-20.48-10.24-71.68-25.6-151.04-25.6-92.16 0-199.68 12.8-212.48 12.8-38.4 2.56-69.12 33.28-69.12 71.68v570.88c0 38.4 30.72 69.12 69.12 71.68h2.56c10.24-2.56 64-7.68 122.88-12.8 104.96-7.68 145.92 0 161.28 2.56 7.68 0 17.92 5.12 28.16 7.68 23.04 7.68 48.64 15.36 76.8 15.36 23.04 0 48.64-7.68 71.68-15.36 17.92-5.12 35.84-10.24 43.52-10.24 2.56 0 5.12 0 7.68-2.56 120.32-17.92 263.68 10.24 263.68 10.24h5.12c38.4 0 71.68-30.72 71.68-71.68V225.28c7.68-38.4-23.04-69.12-61.44-71.68zM143.36 376.32c28.16-7.68 84.48-20.48 174.08-20.48 53.76 0 89.6 10.24 128 30.72 12.8 7.68 15.36 23.04 10.24 33.28-5.12 7.68-12.8 12.8-23.04 12.8-5.12 0-7.68 0-12.8-2.56-30.72-17.92-58.88-23.04-104.96-23.04-84.48 0-135.68 12.8-161.28 20.48-12.8 2.56-28.16-5.12-30.72-17.92 0-17.92 7.68-30.72 20.48-33.28zM460.8 622.08c-5.12 10.24-12.8 15.36-23.04 15.36-2.56 0-7.68 0-10.24-2.56 0 0-58.88-25.6-107.52-25.6-81.92 0-112.64 7.68-143.36 15.36-5.12 2.56-10.24 2.56-15.36 5.12-12.8 2.56-28.16-5.12-30.72-17.92-2.56-12.8 5.12-28.16 17.92-30.72 5.12-2.56 10.24-2.56 15.36-5.12 33.28-7.68 66.56-17.92 156.16-17.92 61.44 0 125.44 28.16 130.56 30.72 10.24 7.68 15.36 20.48 10.24 33.28z m435.2-222.72c-2.56 12.8-15.36 23.04-30.72 20.48-64-12.8-110.08-20.48-168.96-17.92-56.32 0-94.72 20.48-97.28 20.48-2.56 2.56-7.68 2.56-12.8 2.56-7.68 0-17.92-5.12-23.04-12.8-7.68-12.8-2.56-28.16 10.24-33.28 2.56 0 51.2-28.16 120.32-28.16 64-5.12 112.64 5.12 181.76 17.92 15.36 2.56 23.04 17.92 20.48 30.72z"
                              fill="#ea9518"
                            />
                          </svg>
                          <svg
                            v-else-if="item.rsType === 4"
                            viewBox="0 0 1024 1024"
                            width="50"
                            height="50"
                          >
                            <path
                              d="M0 0v1024h1024V0H0z m950.857143 73.142857v146.285714H73.142857V73.142857h877.714286zM73.142857 950.857143V292.571429h877.714286v658.285714H73.142857z"
                              fill="#82529d"
                            />
                            <path
                              d="M358.4 446.171429c-14.628571-7.314286-43.885714-7.314286-58.514286 0L131.657143 621.714286l175.542857 175.542857c0 7.314286 14.628571 7.314286 21.942857 7.314286s21.942857 0 29.257143-7.314286c14.628571-14.628571 14.628571-36.571429 0-51.2L234.057143 621.714286l117.028571-117.028572c14.628571-14.628571 14.628571-43.885714 7.314286-58.514285zM665.6 446.171429c-7.314286 14.628571-7.314286 43.885714 0 58.514285l117.028571 117.028572-117.028571 117.028571c-14.628571 14.628571-14.628571 36.571429 0 51.2 7.314286 14.628571 21.942857 14.628571 29.257143 14.628572s21.942857 0 29.257143-7.314286l175.542857-175.542857-175.542857-175.542857c-14.628571-7.314286-43.885714-7.314286-58.514286 0zM555.885714 438.857143c-14.628571-7.314286-36.571429 7.314286-43.885714 29.257143l-73.142857 292.571428c-7.314286 21.942857 7.314286 36.571429 29.257143 43.885715h7.314285c14.628571 0 29.257143-14.628571 36.571429-29.257143l73.142857-292.571429c7.314286-14.628571-7.314286-36.571429-29.257143-43.885714z"
                              fill="#82529d"
                            />
                          </svg>
                          <svg
                            v-else-if="item.rsType === 5"
                            viewBox="0 0 1024 1024"
                            width="50"
                            height="50"
                          >
                            <path
                              d="M64 511.99984C64 264.584462 264.584462 64 511.99984 64 759.415218 64 959.99968 264.584462 959.99968 511.99984 959.99968 759.415218 759.415218 959.99968 511.99984 959.99968 264.584462 959.99968 64 759.415218 64 511.99984M414.843608 309.742846C386.052152 293.883651 362.66656 307.56258 362.66656 340.415901L362.66656 683.553912C362.66656 716.1683 386.022285 730.116029 414.843608 714.226968L729.070696 540.791296C757.802419 524.902235 757.862152 499.097445 729.070696 483.178517L414.843608 309.742846Z"
                              fill="#f6ef37"
                            />
                          </svg>
                          <svg
                            v-else-if="item.rsType === 6"
                            viewBox="0 0 1024 1024"
                            width="50"
                            height="50"
                          >
                            <path
                              d="M480 96l128.576 273.92L896 413.76l-208 213.12 49.088 301.056L480 785.92 222.912 928l49.088-300.992L64 413.824l287.424-43.968L480 96z m448 672v64H768v-64h160z m-448-521.408L394.88 427.968l-198.144 30.272 143.616 147.2-33.152 202.752 172.8-95.424 172.736 95.424-33.088-202.816 143.552-147.136-198.08-30.272L480 246.592zM928 576v64H768V576h160z m0-320v64H768V256h160z"
                              fill="#17abe3"
                            />
                          </svg>
                          <svg
                            v-else-if="item.rsType === 7"
                            viewBox="0 0 1024 1024"
                            width="50"
                            height="50"
                          >
                            <path
                              d="M864 96H256c-35.346 0-64 28.654-64 64v640H96v64c0 35.347 28.654 64 64 64h608c35.346 0 64-28.653 64-64V224h96v-64c0-35.346-28.654-64-64-64zM160 896c-17.673 0-32-14.327-32-32v-32h544v32a63.692 63.692 0 0 0 8.583 32H160z m640-736v704c0 17.673-14.327 32-32 32h-32c-17.673 0-32-14.327-32-32v-64H224V160c0-17.673 14.327-32 32-32h552.584A63.682 63.682 0 0 0 800 160z m96 32h-64v-32c0-17.673 14.327-32 32-32s32 14.327 32 32v32z m-560 96h160c8.836 0 16-7.164 16-16s-7.164-16-16-16H336c-8.836 0-16 7.164-16 16s7.164 16 16 16z m0 128h352c8.837 0 16-7.164 16-16s-7.163-16-16-16H336c-8.836 0-16 7.164-16 16s7.164 16 16 16z m0 128h224c8.837 0 16-7.163 16-16s-7.163-16-16-16H336c-8.836 0-16 7.163-16 16s7.164 16 16 16z m0 128h352c8.837 0 16-7.163 16-16s-7.163-16-16-16H336c-8.836 0-16 7.163-16 16s7.164 16 16 16z"
                              fill="#8a8a8a"
                            />
                          </svg>
                          <svg
                            v-else-if="item.rsType === 8"
                            viewBox="0 0 1024 1024"
                            width="50"
                            height="50"
                          >
                            <path
                              d="M779.7 549.5c49.8-69.2 88.1-128.1 88.1-194.6 0-108-84.4-195.5-188.7-195.5-104.2 0-188.7 87.6-188.7 195.5 0 59.7 32.8 116.7 75.7 178.3L514.5 551l-100-34c12.4-22.2 20.3-43.8 20.3-67 0-61.3-46.2-111-103-111-56.9 0-103 49.7-103 111 0 25.6 10.4 50.4 25.5 76.1l-0.5 0.1-140.5 338.4 212.6-86.3 193.4 86.3 181.5-86.3 209.8 86.3-130.9-315.1zM679.2 260c50.6 0 91.6 42.5 91.6 95 0 52.4-41 95-91.6 95s-91.6-42.6-91.6-95c0.1-52.6 40.9-95 91.6-95zM331.9 396.1c27.5 0 50 24.1 50 53.9s-22.5 53.9-50 53.9c-27.6 0-50-24.2-50-53.9 0-29.8 22.4-53.9 50-53.9z m365.3 331l-178 83-189.8-82.9-141.5 69.2L269 571.3l13.2-2.6c16.1 23.1 33.7 47.6 49.8 74.7 20-34.3 41-62.9 59-89.1l124 42.8 77.5-27.1c28.3 39.1 58.9 80.4 86.9 126 26.2-43.4 53.4-81.3 78.9-116.3L840 799.4l-142.8-72.3z"
                              fill="#e8989a"
                            />
                          </svg>
                        </div>
                        <div class="rsContent">
                          <div class="rsTitle">{{ getResourceTypeName(item.rsType) }}</div>
                          <div class="itemTitle">{{ item.resource.text }}</div>
                          <div class="itemContent">{{ item.resource.createTime }}</div>
                        </div>
                        <div class="openItem">
                          <div class="openText">
                            <svg viewBox="0 0 1117 1024" width="40" height="40">
                              <path
                                d="M1108.945455 470.109091C1099.636364 453.818182 915.781818 93.090909 559.709091 93.090909S19.781818 453.818182 10.472727 470.109091c-13.963636 25.6-13.963636 58.181818 0 83.781818 9.309091 16.290909 193.163636 377.018182 549.236364 377.018182s539.927273-360.727273 549.236364-377.018182c11.636364-25.6 11.636364-58.181818 0-83.781818zM559.709091 837.818182C257.163636 837.818182 94.254545 512 94.254545 512S257.163636 186.181818 559.709091 186.181818s465.454545 325.818182 465.454545 325.818182-162.909091 325.818182-465.454545 325.818182z"
                                fill="#ffffff"
                              />
                              <path
                                d="M559.709091 325.818182c-102.4 0-186.181818 83.781818-186.181818 186.181818s83.781818 186.181818 186.181818 186.181818 186.181818-83.781818 186.181818-186.181818-83.781818-186.181818-186.181818-186.181818z m0 279.272727c-51.2 0-93.090909-41.890909-93.090909-93.090909s41.890909-93.090909 93.090909-93.090909 93.090909 41.890909 93.090909 93.090909-41.890909 93.090909-93.090909 93.090909z"
                                fill="#ffffff"
                              />
                            </svg>
                            <div>跳转预览</div>
                          </div>
                        </div>
                      </div>

                    </div>

                    <!-- 重新生成 -->
                    <div v-if="item.resource.status === 2 && item.isBatchGenerate !== true" class="againCreate" @click.stop="reCreate(item.rsType, item.resource.taskId)">重新生成</div>
                  </div>
                </div>
              </div>

              <!-- 用户消息 -->
              <div class="user" v-else-if="item.type === 'user'">
                <div class="text">{{ item.content }}</div>
              </div>
            </div>
          </el-scrollbar>
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

          <!-- 输入模式 -->
          <div v-if="!isVoiceMode" class="input-box">
            <el-input
              class="input"
              v-model="userInput"
              placeholder="输入您想对Agent说的话..."
              @keydown.enter="sendMessage"
              :disabled="isInputDisabled"
            />
            <div class="btn">
              <el-tooltip effect="dark" content="语音模式" placement="bottom">
                <a href="#" @click.prevent="switchToVoiceMode" :class="{ 'disabled': isInputDisabled }">
                  <el-icon class="btn-icon"><Microphone /></el-icon>
                </a>
              </el-tooltip>
            </div>
            <div class="btn">
              <el-tooltip effect="dark" content="发送" placement="bottom">
                <a href="#" @click.prevent="sendMessage" :class="{ 'disabled': isInputDisabled }">
                  <el-icon class="btn-icon"><Promotion /></el-icon>
                </a>
              </el-tooltip>
            </div>
          </div>

          <!-- 语音模式 -->
          <div v-else class="input-box voice-input-box">
            <button 
              class="voice-record-btn"
              :class="{ 'recording': isRecording }"
              @click="toggleNativeRecording"
              :disabled="isInputDisabled"
            >
              <el-icon :size="24"><Microphone /></el-icon>
              <span>{{ isRecording ? '点击停止录音' : '点击开始录音' }}</span>
            </button>
            <div class="btn">
              <el-tooltip effect="dark" content="输入模式" placement="bottom">
                <a href="#" @click.prevent="switchToInputMode">
                  <el-icon class="btn-icon"><Edit /></el-icon>
                </a>
              </el-tooltip>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- 学习方案 -->
  <Transition name="fade">
    <div v-if="showPlanDialog" class="plan-dialog-mask" @click="showPlanDialog = false">
      <div class="plan-dialog" @click.stop>
        <button class="plan-dialog-close" @click.stop="showPlanDialog = false">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
        <PlanSelector 
          :user-id="agentUserId"
          :is-view-mode="true"
          @select="(plan) => { handlePlanSelect(plan); showPlanDialog = false; }"
          @close="showPlanDialog = false"
        />
      </div>
    </div>
  </Transition>

  <!-- 冲突弹窗 -->
  <Transition name="fade">
    <div v-if="showConflictDialog" class="conflict-dialog-mask">
      <div class="conflict-dialog">
        <div class="conflict-dialog-header">
          <svg t="1783932506294" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="1708" width="24" height="24"><path d="M512 958.016611c-245.919634 0-446.016611-200.064292-446.016611-446.016611 0-245.919634 200.095256-446.016611 446.016611-446.016611 245.952318 0 446.016611 200.064292 446.016611 446.016611S757.952318 958.016611 512 958.016611zM512 129.983389c-210.655557 0-382.016611 171.359333-382.016611 382.016611 0 210.624593 171.359333 382.016611 382.016611 382.016611 210.624593 0 382.016611-171.359333 382.016611-382.016611S722.624593 129.983389 512 129.983389z" fill="#fb722e" p-id="1709"></path><path d="M463.99957 304.00043c0 26.509985 21.490445 48.00043 48.00043 48.00043s48.00043-21.490445 48.00043-48.00043-21.490445-48.00043-48.00043-48.00043S463.99957 277.490445 463.99957 304.00043z" fill="#fb722e" p-id="1710"></path><path d="M512 768c-17.664722 0-32.00086-14.303454-32.00086-32.00086L479.99914 448c0-17.664722 14.336138-32.00086 32.00086-32.00086s32.00086 14.336138 32.00086 32.00086l0 287.99914C544.00086 753.696546 529.664722 768 512 768z" fill="#fb722e" p-id="1711"></path></svg>
          <span>温馨提示</span>
        </div>
        <div class="conflict-dialog-content" v-html="formatConflictMessage(conflictData.suggestionWarning)"></div>
        <div class="conflict-dialog-footer">
          <button class="conflict-btn conflict-btn-reject" @click="handleConflictOption(false)">
            拒绝
          </button>
          <button class="conflict-btn conflict-btn-accept" @click="handleConflictOption(true)">
            接受
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
/* ===== 布局 ===== */
.container {
  padding-top: 20px;
  min-width: 1314px;
  width: 100%;
  height: 90vh;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  background: transparent;
}

.left {
  width: 30%;
  height: 100%;
  position: relative;
  overflow: hidden;
  background: transparent;
  margin-left: 100px;
  display: flex;
  justify-content: center;
  align-items: center;
}

.avatar-wrapper {
  z-index: 1;
  width: 100%;
  height: 100%;
}
.avatar-wrapper.hidden {
  visibility: hidden;
  opacity: 0;
}

/* ===== 数字人占位图 ===== */
.avatar-placeholder {
  z-index: 2;
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  background: transparent;
}

.placeholder-icon {
  width: 80px;
  height: 80px;
}

.placeholder-text {
  margin-top: 20px;
  font-size: 18px;
  color: var(--el-text-color-secondary);
  letter-spacing: 2px;
}
.placeholder-text.subText {
  margin-top: 10px;
  font-size: 14px;
}

/* ===== 数字人加载动画 ===== */
.avatar-loading {
  z-index: 2;
  position: absolute;
  top: 0;
  left: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  width: 100%;
  height: 100%;
  background: transparent;
}

.loading-spinner {
  width: 60px;
  height: 60px;
  border: 4px solid var(--el-border-color);
  border-top: 4px solid var(--primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.avatar-loading .loading-text {
  margin-top: 20px;
  font-size: 16px;
  color: var(--el-text-color-secondary);
  animation: pulse 1.5s infinite ease-in-out;
}

/* ===== 数字人启动失败示例图 ===== */
.avatar-failed {
  z-index: 2;
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  background: transparent;
}

.avatar-fail-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.subtitle {
  z-index: 2;
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  color: #ffffff;
  font-size: 18px;
  background: rgba(0, 0, 0, 0.5);
  padding: 2px 10px;
  border-radius: 20px;
  max-width: 80%;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.right {
  width: 60%;
  height: 100%;
}

/* ===== 聊天卡片 ===== */
.chat-card {
  position: relative;
  overflow: hidden;
  width: 100%;
  height: 100%;
  border: 2px solid var(--border-color);
  border-radius: 12px;
  background: var(--grad-light);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
  padding: 20px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

/* 流动渐变色（平滑过渡） */
.chat-card::before {
  content: '';
  position: absolute;
  inset: -40%;
  background: linear-gradient(
    135deg,
    rgba(45, 125, 219, 0.08) 0%,
    rgba(45, 125, 219, 0.03) 20%,
    rgba(45, 125, 219, 0.06) 40%,
    rgba(45, 125, 219, 0.02) 60%,
    rgba(45, 125, 219, 0.07) 80%,
    rgba(45, 125, 219, 0.03) 100%
  );
  animation: flowGradient 12s ease-in-out infinite alternate;
  z-index: 0;
}

@keyframes flowGradient {
  0% {
    transform: rotate(0deg) scale(0.9);
    opacity: 0.5;
  }
  50% {
    transform: rotate(180deg) scale(1.2);
    opacity: 0.9;
  }
  100% {
    transform: rotate(360deg) scale(0.9);
    opacity: 0.5;
  }
}

/* ===== 顶部 ===== */
.chat-card .top {
  position: absolute;
  z-index: 2;
  top: 0;
  left: 0;
  width: 100%;
  height: 70px;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(45, 125, 219, 0.15);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 20px;
}

.dark .chat-card .top {
  background: rgba(30, 41, 59, 0.95);
  border-bottom: 1px solid rgba(59, 130, 246, 0.2);
}

.chat-card .top .top-left {
  position: absolute;
  left: 25px;
  top: 0;
  display: flex;
  align-items: center;
  height: 100%;
  gap: 5px;
}

.chat-card .top .top-left img {
  width: 70px;
}

.chat-card .top .top-right {
  position: absolute;
  right: 25px;
  top: 0;
  height: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
}

.chat-card .top .title {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 1px;
  color: var(--el-text-color-primary);
  background: linear-gradient(45deg, var(--el-color-primary), #409eff);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

/* ===== 启动/关闭数字人按钮 ===== */
.avatar-toggle {
  display: flex;
  align-items: center;
}

.avatar-toggle .el-button {
  font-size: 13px;
  padding: 8px 16px;
}

/* ===== 设置下拉菜单 ===== */
.top-right .setting {
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  position: relative;
}

.setting a {
  font-size: 16px;
  color: var(--el-text-color-regular);
}

.setting:hover > a,
.setting:hover .el-icon {
  cursor: pointer;
  color: var(--el-color-primary);
  text-decoration: none;
}

.setting .el-icon {
  font-size: 20px;
  transition: all 0.3s ease-in-out;
}

.setting:hover .el-icon {
  transform: rotate(180deg);
}

.dropdown {
  padding: 16px 20px;
  min-width: 420px;
  background-color: var(--el-bg-color);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  border: 1.5px solid var(--el-border-color);
  border-radius: 8px;
  position: absolute;
  top: 100%;
  right: -20px;
  margin-top: 5px;
  opacity: 0;
  visibility: hidden;
  transform: translateY(-10px);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 100;
  overflow: hidden;
}

.setting:hover .dropdown {
  opacity: 1;
  visibility: visible;
  transform: translateY(0);
}

.dropdown .content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.setting-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 6px 0;
}

.setting-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-primary);
  min-width: 80px;
  flex-shrink: 0;
}

.setting-item :deep(.el-radio-group) {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 16px;
}

.setting-item :deep(.el-radio) {
  margin-right: 0;
  height: 32px;
  display: flex;
  align-items: center;
}

.setting-item :deep(.el-radio__label) {
  font-size: 14px;
  padding-left: 6px;
}

/* ===== 聊天区域 ===== */
.showChat {
  height: 90%;
  padding-top: 50px;
}

.scrollbar {
  height: 100%;
}

.chatBox {
  display: flex;
  padding: 12px 16px;
  width: 100%;
  animation: messageIn 0.4s ease-out;
}

@keyframes messageIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ===== 加载更多历史记录按钮 ===== */
.load-more-wrapper {
  display: flex;
  justify-content: center;
  padding: 12px 0 8px 0;
}

.load-more-btn {
  font-size: 14px;
  color: var(--el-color-primary);
  display: flex;
  align-items: center;
  gap: 4px;
}

.load-more-btn:hover {
  color: var(--el-color-primary-dark-2);
}

/* ===== AI消息 ===== */
.showChat .chatBox .ai {
  padding: 14px 18px;
  border-radius: 20px 20px 20px 6px;
  max-width: 75%;
  margin-right: auto;
  background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid #e2e8f0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  transition: all 0.3s ease;
}

.dark .showChat .chatBox .ai {
  background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
  border: 1px solid #475569;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.showChat .chatBox .ai:hover {
  box-shadow: 0 4px 16px rgba(45, 125, 219, 0.08);
  border-color: rgba(45, 125, 219, 0.2);
}

.dark .showChat .chatBox .ai:hover {
  box-shadow: 0 4px 16px rgba(59, 130, 246, 0.2);
  border-color: rgba(59, 130, 246, 0.3);
}

.ai .text {
  font-size: 15px;
  font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
  word-break: break-word;
  line-height: 1.7;
  color: #334155;
}

.dark .ai .text {
  color: #e2e8f0;
}

/* ===== AI加载动画 ===== */
.ai-loading {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 4px;
}

.loading-dots {
  display: flex;
  gap: 6px;
  align-items: center;
}

.loading-dots span {
  width: 10px;
  height: 10px;
  background: var(--el-color-primary);
  border-radius: 50%;
  animation: dotBounce 1.4s infinite ease-in-out both;
}

.loading-dots span:nth-child(1) {
  animation-delay: -0.32s;
}

.loading-dots span:nth-child(2) {
  animation-delay: -0.16s;
}

.loading-dots span:nth-child(3) {
  animation-delay: 0s;
}

@keyframes dotBounce {
  0%, 80%, 100% {
    transform: scale(0);
    opacity: 0.4;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

.ai-loading .loading-text {
  font-size: 16px;
  color: var(--el-text-color-secondary);
  font-weight: 500;
}

/* 打字机效果 - 闪烁光标 */
.ai .text.typing::after {
  content: '|';
  animation: blink 1s infinite;
  color: var(--el-color-primary);
  font-weight: bold;
  margin-left: 2px;
}

@keyframes blink {
  0%, 50% {
    opacity: 1;
  }
  51%, 100% {
    opacity: 0;
  }
}

/* ===== 用户消息 ===== */
.showChat .chatBox .user {
  padding: 14px 18px;
  border-radius: 20px 20px 6px 20px;
  max-width: 75%;
  margin-left: auto;
  background: linear-gradient(135deg, #2D7DDB 0%, #1a6cd9 100%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: 0 4px 12px rgba(45, 125, 219, 0.25);
  transition: all 0.3s ease;
}

.showChat .chatBox .user:hover {
  box-shadow: 0 6px 20px rgba(45, 125, 219, 0.35);
  transform: translateY(-1px);
}

.user .text {
  color: #ffffff;
  font-size: 15px;
  font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
  word-break: break-word;
  line-height: 1.7;
}

/* ===== 资源卡片 ===== */
.ai .resource {
  margin-top: 12px;
}

.ai .resource .loading,
.ai .resource .fail,
.ai .resource .success {
  margin: 8px 0;
  background-color: #ffffff;
  border-radius: 14px;
  width: 500px;
  height: 120px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 8px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  transition: all 0.3s ease;
}

.dark .ai .resource .loading,
.dark .ai .resource .fail,
.dark .ai .resource .success {
  background-color: #1e293b;
  border: 1px solid #475569;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.loading-text {
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 1px;
  animation: pulse 1.5s infinite ease-in-out;
}

.loading-text::after {
  content: '...';
  animation: dots 1.5s steps(5, end) infinite;
}

.el-icon.is-loading {
  animation: rotating 2s linear infinite;
}

.ai .resource .fail {
  background-color: #fef0f0;
  color: #f56c6c;
}

.dark .ai .resource .fail {
  background-color: rgba(239, 68, 68, 0.15);
  color: #f87171;
}

.fail .shake-icon {
  color: #f56c6c;
  animation: shake 0.82s cubic-bezier(.36, .07, .19, .97) both;
  transform: translate3d(0, 0, 0);
  backface-visibility: hidden;
}

.dark .fail .shake-icon {
  color: #f87171;
}

.fail .fail-text {
  font-size: 14px;
  font-weight: 500;
  opacity: 0;
  animation: fade-in-up 0.5s ease-out forwards;
  animation-delay: 0.3s;
}

/* ===== 资源成功展示 ===== */
.ai .resource .success {
  width: 500px;
  height: 88px;
  overflow: hidden;
}

.success .rsBox {
  position: relative;
  width: 100%;
  height: 100%;
  padding: 12px 16px;
  display: flex;
  justify-content: flex-start;
  align-items: center;
  gap: 14px;
  cursor: pointer;
  border-radius: 14px;
  transition: all 0.3s ease;
}

.success .rsBox:hover {
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  transform: translateY(4px);
  box-shadow: 0 8px 24px rgba(45, 125, 219, 0.15);
}

.dark .success .rsBox:hover {
  background: linear-gradient(135deg, #334155 0%, #475569 100%);
  box-shadow: 0 8px 24px rgba(59, 130, 246, 0.25);
}

.success .rsBox::after {
  content: '';
  position: absolute;
  inset: 0;
  background: rgba(45, 125, 219, 0.05);
  opacity: 0;
  transition: opacity 0.3s ease;
  border-radius: 14px;
}

.success .rsBox:hover::after {
  opacity: 1;
}

.success .rsBox .iconBox {
  display: flex;
  justify-content: center;
  align-items: center;
  flex-shrink: 0;
}

.success .rsBox .iconBox svg {
  width: 50px;
  height: 50px;
}

.success .rsBox .rsContent {
  width: 100%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.success .rsBox .rsTitle {
  font-size: 15px;
  font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
}

.success .itemTitle {
  width: 100%;
  font-size: 18px;
  font-weight: 500;
  color: var(--el-text-color-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.dark .success .itemTitle {
  color: #e2e8f0;
}

.success .itemContent {
  font-size: 12px;
  font-weight: 500;
  color: var(--el-text-color-secondary);
}

.success .openItem {
  position: absolute;
  top: 0;
  right: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.6);
  display: flex;
  justify-content: center;
  align-items: center;
  visibility: hidden;
  opacity: 0;
  transition: opacity 0.3s ease-out;
  border-radius: 12px;
}

.openItem .openText {
  font-weight: 700;
  font-size: 20px;
  color: #ffffff;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  visibility: hidden;
  opacity: 0;
  transition: opacity 0.3s ease-out;
}

.success .rsBox:hover .openItem,
.success .rsBox:hover .openItem .openText {
  opacity: 1;
  visibility: visible;
}

.againCreate {
  width: 60px;
  margin: 0 auto;
  color: var(--text-gray);
}
.againCreate:hover {
  cursor: pointer;
  text-decoration: underline;
  color: var(--primary);
}

/* ===== 输入区域 ===== */
.input-area {
  width: 100%;
  flex-shrink: 0;
  position: relative;
}

/* ===== 录音状态 ===== */
.recording-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 3px 14px;
  background: #fef2f2;
  border-radius: 20px;
  color: #dc2626;
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 4px;
  align-self: flex-start;
}

.recording-dot {
  width: 10px;
  height: 10px;
  background: #dc2626;
  border-radius: 50%;
  animation: pulse-dot 1s infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.3; transform: scale(0.8); }
}

/* ===== 输入框 ===== */
.input-box {
  min-height: 60px;
  width: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--el-border-color);
}

.input-box .btn,
.input-box .btn a {
  display: inline-block;
  width: 40px;
  height: 40px;
  box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
  background: linear-gradient(to right, var(--el-color-primary), #409eff);
  border-radius: 50%;
  display: flex;
  justify-content: center;
  align-items: center;
  transition: all 0.3s cubic-bezier(0.68, -0.55, 0.265, 1.55);
}

.input-box .btn a:hover:not(.disabled) {
  transform: scale(1.08);
}

.input-box .btn a.disabled {
  opacity: 0.5;
  cursor: not-allowed;
  pointer-events: none;
}

.input-box .input {
  width: 689px;
  height: 40px;
  --el-input-focus-border-color: var(--el-color-primary);
  --el-input-hover-border-color: #409eff;
}

.input-box .input :deep(.el-input__wrapper.is-disabled) {
  opacity: 0.6;
}

.input-box .btn-icon {
  color: #ffffff;
  font-size: 20px;
  transition: all 0.3s cubic-bezier(0.68, -0.55, 0.265, 1.55);
}

.input-box .btn-icon.talk {
  animation: pulse 1.5s infinite ease-in-out;
}

.input-box .input:deep(.el-input__wrapper) {
  border-radius: 25px !important;
}

.input-box .input:deep(.el-input__wrapper.is-focus) {
  border-radius: 25px !important;
  box-shadow: 0 0 0 2px #409eff !important;
  border: 0.5px solid var(--el-input-focus-border-color) !important;
}

/* ===== 录音波形弹窗 ===== */
.waveform-popup {
  width: 100%;
  background: var(--bg-card);
  border-radius: 16px 16px 0 0;
  padding: 16px 20px;
  box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.1);
  position: absolute;
  bottom: 100%;
  left: 0;
  right: 0;
  z-index: 10;
}

.waveform-canvas {
  width: 100%;
  height: 60px;
  background: rgba(45, 125, 219, 0.1);
  border-radius: 12px;
  border: 1px solid rgba(45, 125, 219, 0.2);
}

.waveform-timer {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 8px;
  color: var(--text-gray);
  font-size: 14px;
  font-weight: 500;
}

.waveform-timer .recording-dot {
  width: 8px;
  height: 8px;
  background: var(--main-delete);
  border-radius: 50%;
  animation: pulse 1s infinite ease-in-out;
}

/* ===== 语音输入框模式 ===== */
.voice-input-box {
  min-height: 60px;
  width: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  background: transparent;
  border-radius: 25px;
  padding: 0 20px;
  border-top: 1px solid var(--el-border-color);
}

.voice-input-box .btn {
  margin-left: 10px;
}

.voice-record-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 32px;
  background: var(--primary);
  border: none;
  border-radius: 20px;
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
}

.voice-record-btn:hover:not(:disabled) {
  background: var(--primary-hv);
  transform: scale(1.02);
}

.voice-record-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.voice-record-btn.recording {
  background: var(--main-delete);
  animation: pulse 1.5s infinite ease-in-out;
}

.voice-record-btn.recording:hover {
  background: var(--main-delete-hover);
}

/* ===== 波形动画 ===== */
@keyframes waveform-slide-enter-active {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes waveform-slide-leave-active {
  from {
    opacity: 1;
    transform: translateY(0);
  }
  to {
    opacity: 0;
    transform: translateY(20px);
  }
}

.waveform-slide-enter-active {
  animation: waveform-slide-enter-active 0.3s ease-out;
}

.waveform-slide-leave-active {
  animation: waveform-slide-leave-active 0.2s ease-in;
}

/* ===== 动画 ===== */
@keyframes rotating {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}

@keyframes dots {
  0%, 20% { content: '.'; }
  40% { content: '..'; }
  60%, 100% { content: '...'; }
}

@keyframes shake {
  10%, 90% { transform: translate3d(-1px, 0, 0); }
  20%, 80% { transform: translate3d(2px, 0, 0); }
  30%, 50%, 70% { transform: translate3d(-4px, 0, 0); }
  40%, 60% { transform: translate3d(4px, 0, 0); }
}

@keyframes fade-in-up {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.plan-btn {
  position: absolute;
  right: 220px;
  top: 50%;
  transform: translateY(-50%);
  z-index: 10;
}

.dark .plan-btn :deep(.el-button--primary.is-plain) {
  background-color: rgba(59, 130, 246, 0.15);
  border-color: rgba(59, 130, 246, 0.4);
  color: #60a5fa;
}

.dark .plan-btn :deep(.el-button--primary.is-plain:hover) {
  background-color: rgba(59, 130, 246, 0.25);
  border-color: rgba(59, 130, 246, 0.6);
}

.plan-dialog-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  animation: fadeIn 0.2s ease;
}

.plan-dialog {
  background: #fff;
  border-radius: 16px;
  padding: 24px;
  max-width: 900px;
  width: 90%;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  position: relative;
  animation: slideUp 0.3s ease;
}

.plan-dialog-close {
  z-index: 12;
  position: absolute;
  top: 16px;
  right: 16px;
  width: 32px;
  height: 32px;
  border: none;
  background: rgba(0, 0, 0, 0.05);
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
  transition: all 0.2s;
}

.plan-dialog-close:hover {
  background: rgba(0, 0, 0, 0.1);
  color: #1f2a3f;
}

.plan-dialog-close svg {
  width: 18px;
  height: 18px;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* ===== 冲突弹窗 ===== */
.conflict-dialog-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  animation: fadeIn 0.2s ease;
}

.conflict-dialog {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  max-width: 480px;
  width: 90%;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  position: relative;
  animation: slideUp 0.3s ease;
}

.conflict-dialog-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.conflict-dialog-header span {
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.conflict-dialog-content {
  font-size: 15px;
  color: #666;
  line-height: 1.6;
  margin-bottom: 24px;
  padding: 16px;
  background: #fafafa;
  border-radius: 8px;
}

.conflict-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.conflict-btn {
  padding: 10px 24px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.conflict-btn-reject {
  background: #f5f5f5;
  color: #666;
}

.conflict-btn-reject:hover {
  background: #e8e8e8;
  color: #333;
}

.conflict-btn-accept {
  background: #2D7DDB;
  color: #fff;
}

.conflict-btn-accept:hover {
  background: #1a6cd9;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(45, 125, 219, 0.3);
}

/* ============ 夜间模式适配 ============ */

/* 输入框 */
.dark .input-box .input:deep(.el-input__wrapper) {
  background: var(--bg-card);
  border-color: var(--border-color);
}

.dark .input-box .input:deep(.el-input__inner) {
  color: var(--text-body);
}

.dark .input-box .input:deep(.el-input__placeholder) {
  color: var(--text-gray);
}

.dark .input-box .input:deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.5) !important;
  border-color: var(--primary) !important;
}

/* 冲突弹窗 */
.dark .conflict-dialog {
  background: var(--bg-card);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

.dark .conflict-dialog-header span {
  color: var(--text-title);
}

.dark .conflict-dialog-content {
  background: var(--bg-page);
  color: var(--text-body);
}

.dark .conflict-btn-reject {
  background: rgba(71, 85, 105, 0.3);
  color: var(--text-gray);
}

.dark .conflict-btn-reject:hover {
  background: rgba(71, 85, 105, 0.4);
  color: var(--text-body);
}

.dark .conflict-btn-accept {
  background: rgba(59, 130, 246, 0.8);
}

/* 方案弹窗 */
.dark .plan-dialog {
  background: var(--bg-card);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

</style>