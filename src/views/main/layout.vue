<script setup>
import { useRouter, useRoute } from 'vue-router'
import { ref, onMounted, onUnmounted, computed, provide, nextTick } from 'vue'
import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'
import { Compass } from '@element-plus/icons-vue'
import { getInvitedApi } from '@/api/mainApi/partners.js'//获取邀请信息
import { useThemeStore } from '@/stores/theme.js'//主题
import emitter from '@/utils/emitter'// 导入事件总线封装类（子->父传递数据）
import FloatWindow from '@/components/FloatWindow.vue'//悬浮折叠窗
import { colearningNoticeApi } from '@/api/mainApi/partners.js'//获取学习通知信息
import { reviewRemindApi, getEvaluateReportNotifyApi, markEvaluateReportNotifyAsReadApi,closeTourApi } from '@/api/mainApi/layout.js'
import { getPostSTApi } from '@/api/mainApi/partners.js'//获取被邀请信息
import { exitApi } from '@/api/login.js'//登出
import voiceCallService from '@/api/mainApi/voiceCall.js'//语音通话
import CallWindow from '@/components/CallWindow.vue'//语音通话弹窗
import CollectDialog from '@/components/CollectDialog.vue'//收藏弹窗
import ReviewDialog from '@/components/ReviewDialog.vue'//复习提醒弹窗
import Notification from '@/components/Notification.vue'//消息通知弹窗
import SmartBall from '@/components/SmartBall.vue'//智能小球
import CameraFloatWindow from '@/components/CameraFloatWindow.vue'//相机悬浮窗
import NoteBook from '@/components/NoteBook.vue'//笔记
import KnowledgeMap from '@/components/KnowledgeMap.vue'//知识图谱
import GlobalAiExplain from '@/components/GlobalAiExplain.vue'//全局ai解析
import PhotoAnalysis from '@/components/PhotoAnalysis.vue'//图片解析
import { toggleDigitalTwinApi } from '@/api/mainApi/digitalTwins.js'//数字孪生开关
import DigitalTwins from '@/components/DigitalTwins.vue'//数字孪生

const router = useRouter()
const route = useRoute()
const themeStore = useThemeStore()

const partnerUserId = ref('')//学伴部分要用的该用户id
const loginName = ref('')//用户名
const loginAvatar = ref('')//头像
const isBuildProfile = ref(0)//用户画像是否构建
let loginUser = null//登录用户

// 数字孪生相关
const digitalTwinVisible = ref(false)
const opendigitalTwin = () => {
  if (!currentUserId.value) {
    ElMessage.warning('请先登录')
    return
  }
  digitalTwinVisible.value = true
}
const digitalTwinPopupVisible = ref(false)
const digitalTwinEnabled = ref(false)//数字孪生是否开启

const onDigitalTwinToggle = async (val) => {
  // TODO: 调用数字孪生开启/关闭接口
  console.log('数字生:', val ? '开启' : '关闭')
  if(val){
    try{
      const res = await toggleDigitalTwinApi(loginUser.id, true)
      if(res.success){
        digitalTwinEnabled.value = true
        emitter.emit('digitalTwinToggle', true)
      }
    }catch(e){
      console.error('数字孪生开启失败', e)
      ElMessage.error('请先构建孪生再开启')
      digitalTwinEnabled.value = false
      emitter.emit('digitalTwinToggle', false)
    }
  }else{
    toggleDigitalTwinApi(loginUser.id, false)
    digitalTwinEnabled.value = false
    emitter.emit('digitalTwinToggle', false)
  }
}

// 收藏弹窗相关
const collectDialogVisible = ref(false)
const currentUserId = ref('')//收藏用的当前用户id

// 复习提醒弹窗相关
const reviewDialogVisible = ref(false)
const reviewCount = ref(0)

// 复习消息传递
const reviewMessageData = ref({
  message: '',
  sessionId: '',
  timestamp: 0
})

provide('reviewMessageData', reviewMessageData)

// 共学通知相关
const notificationVisible = ref(false)
const notificationList = ref([])
const notificationCount = ref(0)
let notificationPollingTimer = null
let isNotificationPollingActive = true

// 评估报告通知相关
const evaluateNotifyList = ref([])
const evaluateUnreadCount = ref(0)
let evaluateNotifyPollingTimer = null
let isEvaluateNotifyPollingActive = true

const smartBallRef = ref(null)
const cameraFloatWindowRef = ref(null)

// 语音通话相关状态
const callState = ref('idle')
const showIncoming = ref(false)
const showWaiting = ref(false)
const showCalling = ref(false)
const showHangup = ref(false)
const targetUserId = ref('')
const incomingCaller = ref('')
const callDuration = ref('00:00')
const localVolume = ref(0)
const remoteVolume = ref(0)
const isMuted = ref(false)
const isVideoEnabled = ref(false)
const localVideoStream = ref(null)
const remoteVideoStream = ref(null)
const enableVideo = ref(false)

// 是否正在通话中（来电、呼叫中、通话中）
const isInCall = computed(() => {
  return showIncoming.value || showWaiting.value || showCalling.value
})

// 漫游式引导
const tourVisible = ref(false)
const tourCurrent = ref(0)

const tourSteps = [
  { target: 'float-window-target', title: 'Agent思维链悬浮窗', content: '左侧悬浮窗展示Agent思维链，点击展开可实时查看后台Agent详细思考过程以及Agent调用历程。' },
  { target: 'note-btn-target', title: '笔记', content: '笔记功能，随时记录学习心得和重要知识点。包含AI整理笔记内容、笔记思维导图、笔记知识点、笔记图谱等等功能' },
  { target: 'digitalTwins', title: 'AI智构孪生', content: '数字孪生功能，基于您的个人画像，AI生成数字孪生模型，孪生模型将会做出预测，便于您更好的了解自身情况' },
  { target: 'photoAnalysis', title: 'AI图片解释/解答', content: '上传图片，AI自动识别并解析，最后提炼核心答案或解题关键' },
  { target: 'knowledgeMap', title: '知识图谱', content: '知识图谱功能，上传文件，AI梳理文件内容，形成知识图谱，对于图谱中的每个知识点可以生成学习计划' },
  { target: 'menu-index', title: '首页', content: '根据您的使用情况 智推资源 帮助你快速跳转指定资源库、总排行榜激发学习动力和帖子评论区可与他人互动分享交流。' },
  { target: 'menu-aiAnswer', title: '智能答疑', content: 'AI智能答疑助手，支持对话式学习和生成资源。' },
  { target: 'menu-draw', title: '学情画像', content: '查看个人学情画像，多维度图像展示，帮助您了解自身学习情况。' },
  { target: 'menu-pathPlan', title: '智学路径', content: '智能学习路径规划和资源整合化学习，可根据主题和每一阶段学习情况实时化推荐最优学习路线。' },
  { target: 'menu-evaluate', title: '智评优化', content: '学习评估和优化建议，在本模块您可选择是否采纳系统建议，生成更符合您的学习资源，帮助提升学习效果。' },
  { target: 'menu-resource', title: '智创资源', content: '展示各类资源，您可根据喜好快速生成对应资源。' },
  { target: 'menu-wrongQuestions', title: '错题本', content: '收集学习过程中的错题并提供再次多次错题后的针对性推荐练习。' },
  { target: 'menu-partners', title: '学伴助学', content: '发现志同道合的学习伙伴，与学伴共同学习，共享资源，交流探讨，互相帮助，提升学习效率。' },
  { target: 'nav-icon-collect', title: '我的收藏', content: '收藏重要、需要的学习资源，方便随时跳转查看。' },
  { target: 'nav-icon-review', title: '复习提醒', content: '帮助您按时复习智学路径学习计划中已学的知识点。' },
  { target: 'nav-icon-message', title: '消息', content: '查看共学通知和评估报告通知，不错过重要内容。' },
  { target: 'camera-float-target', title: '摄像监测及实时画像悬浮窗', content: '右侧悬浮窗展示摄像监测和实时画像，高效监督学习，帮助您了解学习专注度和状态。' },
  { target: 'smart-ball-target', title: '智能球', content: '智能球助手，提供智能球模式与数字人模式，实时检测学习情况，随时提供可视化学习帮助和答疑服务。' }
]

const tourTargetRefs = {}
const setTourTargetRef = (key) => (el) => {
  if (el) tourTargetRefs[key] = el
}

const getTourTarget = (targetId) => {
  return () => {
    if (targetId === 'float-window-target' && floatWindowRef.value) {
      const el = floatWindowRef.value.getTargetElement?.()
      if (el) return el
    }
    if (targetId === 'camera-float-target' && cameraFloatWindowRef.value) {
      const el = cameraFloatWindowRef.value.getTargetElement?.()
      if (el) return el
    }
    if (targetId === 'smart-ball-target' && smartBallRef.value) {
      const el = smartBallRef.value.getTargetElement?.()
      if (el) return el
    }
    if (targetId === 'note-btn-target' && tourTargetRefs['note-btn-target']) {
      return tourTargetRefs['note-btn-target']
    }
    if (tourTargetRefs[targetId]) {
      return tourTargetRefs[targetId].$el || tourTargetRefs[targetId]
    }
    const el = document.getElementById(targetId)
    if (el) return el
    return document.body
  }
}

const waitForElement = async (targetId, maxWait = 3000) => {
  const startTime = Date.now()
  return new Promise(resolve => {
    const check = () => {
      if (tourTargetRefs[targetId]) {
        resolve(tourTargetRefs[targetId])
        return
      }
      const el = document.getElementById(targetId)
      if (el) {
        resolve(el)
        return
      }
      if (Date.now() - startTime >= maxWait) {
        resolve(null)
        return
      }
      setTimeout(check, 100)
    }
    check()
  })
}

const startTour = async () => {
  tourCurrent.value = 0
  
  // 第一步跳转首页
  // const firstStep = tourSteps[0]
  // if (firstStep && firstStep.route) {
  //   await router.push(firstStep.route)
  //   await nextTick()
  // }
  
  // 等待目标元素渲染完成（最多等待3秒）
  const firstTarget = tourSteps[0]?.target
  if (firstTarget) {
    await waitForElement(firstTarget)
  }
  
  await new Promise(resolve => setTimeout(resolve, 500))
  
  tourVisible.value = true
}

const onTourChange = async (current) => {
  const step = tourSteps[current]
  
  // 如果是智能球步骤且当前在aiAnswer页面，自动跳过
  if (step && step.target === 'smart-ball-target' && route.name === 'aiAnswer') {
    tourCurrent.value = current + 1
    return
  }
  
  // 等待目标元素渲染完成
  if (step && step.target) {
    await waitForElement(step.target)
    await new Promise(resolve => setTimeout(resolve, 300))
  }
  
  tourCurrent.value = current
}

const showCelebration = ref(false)

const onTourClose = async () => {
  tourVisible.value = false
  showCelebration.value = true
  setTimeout(() => {
    showCelebration.value = false
    // 导览完成后询问是否跳转智能问答页
    // ElMessageBox.confirm(
    //   '您已完成系统导览，是否要前往智能问答页面开始学习？',
    //   '导览完成',
    //   {
    //     confirmButtonText: '去智能问答',
    //     cancelButtonText: '暂不需要',
    //     type: 'success'
    //   }
    // ).then(() => {
    //   router.push('/aiAnswer')
    // }).catch(() => {
    //   // 用户取消，不做任何操作
    // })
  }, 3000)
  
  const loginUserStr = localStorage.getItem('loginUser')
  if (loginUserStr) {
    const loginUser = JSON.parse(loginUserStr)
    if (loginUser.tour === 1) {
      try {
        const res = await closeTourApi(loginUser.id)
        if (res.code === 1) {
          loginUser.tour = 0
          localStorage.setItem('loginUser', JSON.stringify(loginUser))
        }
      } catch (err) {
        console.error('关闭漫游引导异常', err)
      }
    }
  }
}

// 计算徽章显示数量（学伴邀请 + 被邀请 + 共学通知）
const totalBadgeCount = computed(() => {
  return invitedNum.value + postSTNum.value
})

// 消息徽章总数（共学通知 + 评估报告未读通知）
const messageBadgeCount = computed(() => {
  return notificationCount.value + evaluateUnreadCount.value
})

// ========== 资源类型映射 ==========
const getResourceTypeLabel = (type) => {
  const map = {
    'doc': '讲解文档',
    'document': '讲解文档',
    'practice': '编程题',
    'mindmap': '思维导图',
    'extension': '拓展阅读',
    'video': '视频',
    'animation': '动画',
    'ppt': 'PPT',
    'question': '试卷'
  }
  return map[type] || type || '未知'
}

onMounted(async () => {
  // 监听aiAnswer子组件更新数据事件
  emitter.on('profileUpdated', (data) => {
    // 执行父组件逻辑
    console.log('更新了:', data)
    isBuildProfile.value = data.isBuildProfile
  })
  // 监听启动漫游引导事件
  emitter.on('startTour', () => {
    startTour()
  })
  // 获取用户名
  const userStr = localStorage.getItem('loginUser')
  if (userStr) {
    try {
      loginUser = JSON.parse(userStr)

      if(loginUser && loginUser.username){
        partnerUserId.value = typeof loginUser.id === 'string' ? loginUser.id : String(loginUser.id)
        currentUserId.value = partnerUserId.value
        isBuildProfile.value = loginUser.isBuildProfile
        loginName.value = loginUser.username
        loginAvatar.value = loginUser.avatar
        if(isBuildProfile.value === 0){
          ElNotification({
            title: '小提示',
            message: '为了更好地初次构建起您的人物画像，请配合Agent助手回答问题，构建是为了给您提供更好的学习体验，请您耐心等待~',
            position: 'bottom-left',
            duration: 15000, // 15秒
            showClose: false, // 隐藏关闭按钮
          });
        }
        // 开启全局（java）websocket监听语音通话
        initVoiceCall()
        
      }else{
        ElMessage.error('非法闯入！')
        router.push('/login')
      }
      
    }catch (e) {
      console.error('用户信息解析失败', e)
    }

    // 异步延迟2秒
    // await new Promise(resolve => setTimeout(resolve, 5000))
    // 判断用户类型
    if(loginUser && loginUser.isNew && loginUser.type == -3){
      localStorage.removeItem('loginUser')
      ElMessage.info('已申请为管理员，请等待管理员审核')
      router.push('/login')
    }else if(loginUser.isNew == false && loginUser.type == 0){ 
      ElMessage.success('管理员您好，为您跳转管理端首页~')
      router.push('/admin/index')
    }else if(loginUser.isNew && loginUser.type == -2){
      ElMessage.info('请完善信息')
      router.push('/info')
    }
  } 



  // 徽章-学伴(轮询)// 在组件挂载时开始
  startPolling()
  // 启动共学通知轮询
  startNotificationPolling()
  // 启动评估报告通知轮询
  startEvaluateNotifyPolling()
  // 获取复习提醒数量
  fetchReviewCount()
})

// 跳转用户中心
const toUserCenter = () => {
  router.push('/userCenter')
}
// 退出登录
const exitLogin = async () => {
  try{
    // 断开语音通话通知通道（退出登录时才断开）
    voiceCallService.disconnectNotifyChannel()
    
    const res = await exitApi(partnerUserId.value)
    if(res.code){
      localStorage.removeItem('loginUser')
      ElMessage.success('退出登录成功')
      router.push('/login')
    }else{
      ElMessage.error(res.msg)
    }
  }catch(error){
    ElMessage.error('退出登录失败')
  }
}

// ==================== 语音通话相关 ====================

// 初始化语音通话服务
const initVoiceCall = () => {
  if (!partnerUserId.value) return
  
  // 设置用户ID
  voiceCallService.setUserId(partnerUserId.value)
  
  // 设置事件回调
  voiceCallService.setCallbacks({
    onIncomingCall: (from, username, hasVideo) => {
      console.log('📞 收到来电:', from, username, '视频:', hasVideo)
      incomingCaller.value = username  // 使用用户名显示
      targetUserId.value = from        // 用户ID用于接口调用
      enableVideo.value = hasVideo || false
      showIncoming.value = true
      showWaiting.value = false
      showCalling.value = false
      showHangup.value = false
    },
    onCallRejected: (username) => {
      console.log('❌ 用户', username, '拒绝了通话')
      ElMessage.warning(`${username} 拒绝了通话`)
      hideAllCallWindows()
    },
    onCallCanceled: (username) => {
      console.log('📭 用户', username, '取消了呼叫')
      ElMessage.info(`${username} 取消了呼叫`)
      hideAllCallWindows()
    },
    onSelfReject: () => {
      console.log('📭 你取消了通话')
      ElMessage.info('你取消了通话')
      hideAllCallWindows()
    },
    onCallAccepted: (username) => {
      console.log('✅ 对方已接受通话:', username)
      showIncoming.value = false
      showWaiting.value = true
    },
    onCallConnected: () => {
      console.log('📞 通话已连接')
      showWaiting.value = false
      showCalling.value = true
    },
    onRemoteHangup: (username) => {
      console.log('📴 用户', username, '已挂断')
      showIncoming.value = false
      showWaiting.value = false
      showCalling.value = false
      showHangup.value = true
    },
    onCallTimeout: (msg) => {
      console.log('⏰ 呼叫超时:', msg)
      ElMessage.warning(msg)
      // 后端通知的超时不自动挂断，由用户手动挂断
    },
    onUserOffline: (msg) => {
      console.log('⚠️ 用户离线:', msg)
      ElMessage.warning(msg)
      // 后端通知的离线不自动挂断，由用户手动挂断
    },
    onVolumeChange: (volumes) => {
      localVolume.value = volumes.local
      remoteVolume.value = volumes.remote
    },
    onMuteChange: (muted) => {
      isMuted.value = muted
    },
    onNotifyConnected: () => {
      console.log('✅ 语音通知通道已连接')
    },
    onSignalConnected: () => {
      console.log('✅ 语音信令通道已连接')
    },
    onDurationChange: (duration) => {
      callDuration.value = duration
    },
    onLocalVideoStream: (stream) => {
      console.log('📹 本地视频流变化:', stream ? '有' : '无')
      localVideoStream.value = stream
      if (stream) isVideoEnabled.value = true
    },
    onRemoteVideoStream: (stream) => {
      console.log('📹 远端视频流变化:', stream ? '有' : '无')
      remoteVideoStream.value = stream
    },
    onVideoToggle: (enabled) => {
      console.log('📹 视频开关:', enabled)
      isVideoEnabled.value = enabled
    }
  })
  
  // 连接通知通道（常驻，退出登录时断开）
  voiceCallService.connectNotifyChannel()
}

// 接听来电
const acceptCall = () => {
  voiceCallService.acceptCall()
}

// 拒绝来电
const rejectCall = () => {
  voiceCallService.rejectCall()
  showIncoming.value = false
}

// 挂断通话
const hangUp = () => {
  voiceCallService.hangUp()
  hideAllCallWindows()
}

// 关闭挂断状态弹窗
const closeHangupStatus = () => {
  showHangup.value = false
  callDuration.value = '00:00'
}

// 切换静音
const toggleMute = () => {
  voiceCallService.toggleMute()
}

// 切换摄像头
const toggleVideo = () => {
  voiceCallService.toggleVideo()
}

// 隐藏所有通话窗口
const hideAllCallWindows = () => {
  showIncoming.value = false
  showWaiting.value = false
  showCalling.value = false
  showHangup.value = false
  // 重置视频状态
  isVideoEnabled.value = false
  localVideoStream.value = null
  remoteVideoStream.value = null
  enableVideo.value = false
}

// 发起通话（供其他组件调用）
const startVoiceCall = (targetId, withVideo = false) => {
  if (!targetId) {
    ElMessage.warning('请选择要通话的用户')
    return
  }
  if (targetId === partnerUserId.value) {
    ElMessage.warning('不能呼叫自己')
    return
  }
  
  targetUserId.value = targetId
  enableVideo.value = withVideo
  showIncoming.value = false
  showWaiting.value = true
  showCalling.value = false
  showHangup.value = false
  
  voiceCallService.startCall(targetId, withVideo)
}

// 暴露给子组件调用
provide('startVoiceCall', startVoiceCall)
provide('isInCall', isInCall)

// 打开收藏弹窗
const openCollectDialog = () => {
  if (!currentUserId.value) {
    ElMessage.warning('请先登录')
    return
  }
  collectDialogVisible.value = true
}

// 打开复习提醒弹窗
const openReviewDialog = () => {
  if (!currentUserId.value) {
    ElMessage.warning('请先登录')
    return
  }
  reviewDialogVisible.value = true
}

// 获取复习提醒数量
const fetchReviewCount = async () => {
  if (!currentUserId.value) return
  try {
    const res = await reviewRemindApi(currentUserId.value)
    if (res.code === 1 && res.data && res.data.reminder) {
      reviewCount.value = res.data.reminder.today_due_count || 0
    } else {
      reviewCount.value = 0
    }
  } catch (e) {
    console.error('获取复习提醒数量失败:', e)
    reviewCount.value = 0
  }
}

// 刷新收藏列表（取消收藏后回调）
const refreshCollectList = () => {
  console.log('收藏列表已刷新')
}

// ========== 打开消息弹窗 ==========
const openNotificationDialog = () => {
  if (!currentUserId.value) {
    ElMessage.warning('请先登录')
    return
  }
  // 获取最新数据再打开
  fetchNotifications()
  fetchEvaluateNotifications()
  notificationVisible.value = true
}

// ========== 获取共学通知 ==========
const fetchNotifications = async () => {
  if (!partnerUserId.value) return
  
  try {
    const res = await colearningNoticeApi(partnerUserId.value)
    if (res.code === 1 && res.data) {
      // 只显示 accepted 状态的通知
      const acceptedList = res.data.accepted || []
      notificationList.value = acceptedList
      notificationCount.value = acceptedList.length
      console.log('共学通知数量：', notificationCount.value)
    }
  } catch (e) {
    console.error('获取共学通知失败：', e)
  }
}

// ========== 获取评估报告通知 ==========
const fetchEvaluateNotifications = async () => {
  if (!partnerUserId.value) return
  
  try {
    const res = await getEvaluateReportNotifyApi(partnerUserId.value)
    if (res.code === 1 && res.data) {
      evaluateNotifyList.value = res.data.notifications || []
      evaluateUnreadCount.value = res.data.unread_count || 0
      console.log('评估报告通知数量：', evaluateNotifyList.value.length, '未读：', evaluateUnreadCount.value)
    }
  } catch (e) {
    console.error('获取评估报告通知失败：', e)
  }
}

// ========== 评估报告通知轮询 ==========
const startEvaluateNotifyPolling = () => {
  isEvaluateNotifyPollingActive = true
  fetchEvaluateNotifications()
  evaluateNotifyPollingTimer = setTimeout(() => {
    if (isEvaluateNotifyPollingActive) {
      evaluateNotifyPolling()
    }
  }, 10000)
}

const evaluateNotifyPolling = async () => {
  if (!isEvaluateNotifyPollingActive) return
  
  await fetchEvaluateNotifications()
  
  if (isEvaluateNotifyPollingActive) {
    evaluateNotifyPollingTimer = setTimeout(() => {
      evaluateNotifyPolling()
    }, 30000)
  }
}

const stopEvaluateNotifyPolling = () => {
  isEvaluateNotifyPollingActive = false
  if (evaluateNotifyPollingTimer) {
    clearTimeout(evaluateNotifyPollingTimer)
    evaluateNotifyPollingTimer = null
  }
}

// ========== 标记评估报告通知为已读 ==========
const markEvaluateNotifyAsRead = async (assessmentId) => {
  if (!partnerUserId.value) return
  
  try {
    const res = await markEvaluateReportNotifyAsReadApi(partnerUserId.value, { assessment_id: assessmentId })
    if (res.code === 1 && res.data?.success) {
      await fetchEvaluateNotifications()
      return true
    }
  } catch (e) {
    console.error('标记评估报告通知为已读失败：', e)
  }
  return false
}

// ========== 共学通知轮询（20秒） ==========
const startNotificationPolling = () => {
  isNotificationPollingActive = true
  // 立即获取一次
  fetchNotifications()
  // 开始轮询
  notificationPollingTimer = setTimeout(() => {
    if (isNotificationPollingActive) {
      notificationPolling()
    }
  }, 10000)
}
// 轮询
const notificationPolling = async () => {
  if (!isNotificationPollingActive) return
  
  await fetchNotifications()
  
  if (isNotificationPollingActive) {
    notificationPollingTimer = setTimeout(() => {
      notificationPolling()
    }, 20000)
  }
}
// 停止轮询
const stopNotificationPolling = () => {
  isNotificationPollingActive = false
  if (notificationPollingTimer) {
    clearTimeout(notificationPollingTimer)
    notificationPollingTimer = null
  }
}

// ===================徽章-学伴邀请（添加学伴 + 邀请题目）===================
const invitedNum = ref(0)//待处理的邀请数量
const postSTNum = ref(0)//待处理的被邀请数量
let pollingTimer = null// 轮询定时器
let isPollingActive = true// 轮询状态

// 获取待处理的邀请数量
const getNumInvited = async () => {
  if (!isPollingActive) return
  
  try {
    const [inviteRes, postSTRes] = await Promise.all([
      getInvitedApi(partnerUserId.value),
      getPostSTApi(partnerUserId.value)
    ])
    
    // 处理邀请数量
    if (inviteRes.code && inviteRes.data.invites) {
      invitedNum.value = inviteRes.data.invites.filter(
        invite => invite.status === 'pending'
      ).length
    }
    
    // 处理被邀请数量
    if (postSTRes.code && postSTRes.data?.success && postSTRes.data.invites) {
      postSTNum.value = postSTRes.data.invites.filter(
        invite => invite.status === 'pending'
      ).length
    }
    
    console.log('待处理的邀请数量：', invitedNum.value)
    console.log('待处理的被邀请数量：', postSTNum.value)
    
    // 继续轮询
    if (isPollingActive) {
      pollingTimer = setTimeout(() => {
        getNumInvited()
      }, 5000)
    }
  } catch (e) {
    console.error('获取邀请列表失败：', e)
  }
}

// 开始轮询
const startPolling = () => {
  isPollingActive = true
  getNumInvited()
}

// 停止轮询
const stopPolling = () => {
  isPollingActive = false
  if (pollingTimer) {
    clearTimeout(pollingTimer)
    pollingTimer = null
  }
}


//====================左侧折叠框====================
// 监听折叠状态变化
function handleToggle(isCollapsed) {
  console.log('窗口折叠状态:', isCollapsed)
}

function handleCollapsedChange(value) {
  console.log('折叠状态更新:', value)
}

function doSomething() {
  console.log('执行自定义操作')
}

// 通过 ref 控制组件
const floatWindowRef = ref(null)//左侧悬浮窗

// 手动切换折叠
function toggleWindow() {
  floatWindowRef.value?.toggleCollapse()
}

// 手动重置位置
function resetWindow() {
  floatWindowRef.value?.resetPosition()
}



// ======================笔记相关====================
const noteBookVisible = ref(false)

const openNoteBook = () => {
  if (!currentUserId.value) {
    ElMessage.warning('请先登录')
    return
  }
  noteBookVisible.value = true
}

// ======================知识图谱相关====================
const knowledgeMapVisible = ref(false)

const openKnowledgeMap = () => {
  if (!currentUserId.value) {
    ElMessage.warning('请先登录')
    return
  }
  knowledgeMapVisible.value = true
}

// ======================图片解析相关====================
const photoAnalysisVisible = ref(false)

const openphotoAnalysis = () => {
  if (!currentUserId.value) {
    ElMessage.warning('请先登录')
    return
  }
  photoAnalysisVisible.value = true
}

// 在组件卸载时清理
onUnmounted(() => {
  stopPolling()
  stopNotificationPolling()
  stopEvaluateNotifyPolling()
  // 移除事件监听（aiAnswer）
  emitter.off('profileUpdated')
  // 移除漫游引导事件监听
  emitter.off('startTour')
  // 恢复页面滚动
  document.body.style.overflow = ''
})

</script>

<template>
  <!-- 顶部导航栏 -->
  <div class="topNav">
    <div class="logo" title="知行优课">
      <img src="@/assets/logo/Logo.png" alt="知行优课logo"></img>
      <h1>知行优课</h1>
      
    </div>
    <div class="nav">
      <ul>
        <li v-if="isBuildProfile === 1" :ref="setTourTargetRef('menu-index')"><router-link to="/index"><el-icon><House /></el-icon>&nbsp;首页</router-link></li>
        <li :ref="setTourTargetRef('menu-aiAnswer')"><router-link to="/aiAnswer"><el-icon><ChatRound /></el-icon>&nbsp;智能答疑</router-link></li> 
        <li v-if="isBuildProfile === 1" :ref="setTourTargetRef('menu-draw')"><router-link to="/draw"><el-icon><Location /></el-icon>&nbsp;学情画像</router-link></li>
        <li v-if="isBuildProfile === 1" :ref="setTourTargetRef('menu-pathPlan')"><router-link to="/pathPlan"><el-icon><DataLine /></el-icon>&nbsp;智学路径</router-link></li>
        <li v-if="isBuildProfile === 1" :ref="setTourTargetRef('menu-evaluate')"><router-link to="/evaluate"><el-icon><Trophy /></el-icon>&nbsp;智评优化</router-link></li>
        <li v-if="isBuildProfile === 1" :ref="setTourTargetRef('menu-resource')"><router-link to="/resource"><el-icon><Memo /></el-icon>&nbsp;智创资源</router-link></li>
        <li v-if="isBuildProfile === 1" :ref="setTourTargetRef('menu-wrongQuestions')"><router-link to="/wrongQuestions"><el-icon><Notebook /></el-icon>&nbsp;错题本</router-link></li>
        <li v-if="isBuildProfile === 1" :ref="setTourTargetRef('menu-partners')">
          <!-- 使用总徽章数量（学伴邀请 + 共学通知） -->
          <el-badge v-if="totalBadgeCount !== 0" :value="totalBadgeCount" class="huizhang"></el-badge>
          <router-link to="/partners"><el-icon><User /></el-icon>&nbsp;学伴助学</router-link>
        </li>
      </ul>
    </div>
    <div class="user" v-if="loginName != ''">
      
      <!-- 我的收藏 -->
      <div class="mes" v-if="isBuildProfile === 1" @click="openCollectDialog" :ref="setTourTargetRef('nav-icon-collect')">
        <el-tooltip
          class="box-item"
          effect="dark"
          content="我的收藏"
          placement="bottom"
        >
          <el-icon><Star /></el-icon>
        </el-tooltip>
      </div>
      <!-- 提醒 -->
      <div class="mes" v-if="isBuildProfile === 1" @click="openReviewDialog" :ref="setTourTargetRef('nav-icon-review')">
        <el-badge v-if="reviewCount > 0" :value="reviewCount" :max="99" class="huizhang review-badge"></el-badge>
        <el-tooltip
          class="box-item"
          effect="dark"
          content="提醒"
          placement="bottom"
        >
          <el-icon><Bell /></el-icon>
        </el-tooltip>
      </div>
      <!-- 消息（共学通知 + 评估报告通知） -->
      <div class="mes" v-if="isBuildProfile === 1" @click="openNotificationDialog" :ref="setTourTargetRef('nav-icon-message')">
        <el-badge v-if="messageBadgeCount > 0" :value="messageBadgeCount" :max="99" class="huizhang notice-badge"></el-badge>
        <el-tooltip
          class="box-item"
          effect="dark"
          content="消息"
          placement="bottom"
        >
          <el-icon><Message /></el-icon>
        </el-tooltip>
      </div>
      <!-- 头像 -->
      <div class="avatar">
        <el-tooltip
          class="box-item"
          effect="dark"
          :content="'id：' + partnerUserId"
          placement="bottom"
        >
          <el-avatar :src="loginAvatar">User</el-avatar>
        </el-tooltip>
      </div>
      <!-- 用户信息 -->
      <div class="username">
        <a href="javascript:void(0)" :title="'id：' + partnerUserId">{{ loginName }}</a>
        <el-icon><arrow-down /></el-icon>
        <ul class="dropdown">
          <li>
            <a href="javascript:void(0)" @click="themeStore.toggleTheme()">
              <span v-if="themeStore.isDark">☀️</span>
              <span v-else>🌙</span>
              <span style="margin-left: 5px;">{{ themeStore.isDark ? '日间' : '夜间' }}</span>
            </a>
          </li>
          <li v-if="isBuildProfile === 1">
            <a href="javascript:void(0)" @click="startTour()" title="漫游引导">
              <el-icon><Compass /></el-icon>
              <span style="margin-left: 5px;">引导</span>
            </a>
          </li>
          <li v-if="isBuildProfile === 1"><a href="javascript:void(0)" @click="toUserCenter()">用户中心</a></li>
          <li><a href="javascript:void(0)" @click="exitLogin()">退出登录</a></li>
        </ul>
      </div>   
    </div>
    <div class="pleaseLogin" v-else>
      <a href="javascript:void(0)">
        <router-link to="/login">登录/注册</router-link>
      </a>
    </div>
  </div>
  <!-- 内容 -->
  <div class="content">
    <router-view></router-view>
  </div>
  
  <!-- 收藏弹窗 -->
  <CollectDialog
    v-model:visible="collectDialogVisible"
    :userId="currentUserId"
    @refresh="refreshCollectList"
  />

  <!-- 复习提醒弹窗 -->
  <ReviewDialog
    v-model:visible="reviewDialogVisible"
    :userId="currentUserId"
  />

  <!-- 消息通知弹窗 -->
  <Notification
    v-model:visible="notificationVisible"
    :notifications="notificationList"
    :evaluateNotifications="evaluateNotifyList"
    @markEvaluateRead="markEvaluateNotifyAsRead"
  />

  <!-- 左侧折叠窗口组件 -->
  <FloatWindow 
    ref="floatWindowRef"
    title="Agent思维链"
    :defaultCollapsed="true"
    :userId="currentUserId"
    @toggle="handleToggle"
    @update:collapsed="handleCollapsedChange"
  ></FloatWindow>

  <!-- 智能球组件 -->
  <SmartBall 
    ref="smartBallRef"
    v-if="route.name !== 'aiAnswer'"
    :userId="currentUserId"
    :currentPath="route.fullPath"
    :currentName="route.name || ''"
  />

  <!-- 摄像头监控组件 -->
  <CameraFloatWindow
    ref="cameraFloatWindowRef"
    :userId="currentUserId"
  />

  <!-- 笔记悬浮按钮（固定左上角） -->
  <el-tooltip
    class="box-item"
    effect="dark"
    content="笔记"
    placement="right"
  >
    <div 
      v-if="!noteBookVisible"
      class="note-float-btn"
      @click="openNoteBook"
      :ref="setTourTargetRef('note-btn-target')"
    >
      <svg t="1782723357609" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="9229" width="20" height="20"><path d="M208.896 788.48l152.576-48.128c8.192-3.072 16.384-7.168 22.528-14.336l403.456-433.152c50.176-53.248 47.104-136.192-6.144-186.368-53.248-49.152-136.192-46.08-186.368 7.168L191.488 545.792c-6.144 7.168-10.24 15.36-12.288 23.552L142.336 727.04c-9.216 38.912 27.648 73.728 66.56 61.44z m423.936-640c29.696-31.744 80.896-33.792 112.64-4.096 31.744 29.696 33.792 80.896 4.096 112.64l-29.696 31.744-112.64-112.64 25.6-27.648zM229.376 581.632l343.04-367.616 112.64 112.64-338.944 363.52-152.576 48.128 35.84-156.672zM857.088 877.568H124.928c-14.336 0-25.6 11.264-25.6 25.6s11.264 25.6 25.6 25.6h732.16c14.336 0 25.6-11.264 25.6-25.6s-11.264-25.6-25.6-25.6z" fill="#ffffff" p-id="9230"></path></svg>
    </div>
  </el-tooltip> 
  

  <!-- 知识图谱悬浮按钮（固定左上角） -->
  <el-tooltip
    class="box-item"
    effect="dark"
    content="知识图谱"
    placement="right"
  >
    <div 
      class="map-float-btn"
      @click="openKnowledgeMap"
      :ref="setTourTargetRef('knowledgeMap')"
    >
      <svg t="1784964216992" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="6588" width="20" height="20"><path d="M870.4 711.111111c-28.444444 0-56.888889 8.533333-79.644444 22.755556l-162.133334-156.444445c25.6-34.133333 42.666667-76.8 42.666667-122.311111 0-42.666667-14.222222-82.488889-36.977778-113.777778l93.866667-99.555555c17.066667 8.533333 36.977778 17.066667 56.888889 17.066666 62.577778 0 113.777778-51.2 113.777777-113.777777s-51.2-113.777778-113.777777-113.777778-113.777778 51.2-113.777778 113.777778c0 22.755556 5.688889 39.822222 17.066667 56.888889l-93.866667 99.555555c-31.288889-28.444444-73.955556-45.511111-122.311111-45.511111-48.355556 0-93.866667 17.066667-130.844445 48.355556L258.844444 227.555556c8.533333-17.066667 14.222222-36.977778 14.222223-56.888889 0-62.577778-51.2-113.777778-113.777778-113.777778s-113.777778 51.2-113.777778 113.777778 51.2 113.777778 113.777778 113.777777c22.755556 0 42.666667-5.688889 59.733333-17.066666l88.177778 79.644444c-22.755556 31.288889-34.133333 68.266667-34.133333 108.088889 0 51.2 19.911111 96.711111 51.2 130.844445l-59.733334 62.577777c-22.755556-14.222222-48.355556-22.755556-76.8-22.755555-79.644444 0-142.222222 62.577778-142.222222 142.222222s62.577778 142.222222 142.222222 142.222222 142.222222-62.577778 142.222223-142.222222c0-28.444444-8.533333-56.888889-25.6-79.644444l59.733333-65.422223c31.288889 19.911111 68.266667 31.288889 105.244444 31.288889 42.666667 0 82.488889-14.222222 113.777778-36.977778l164.977778 156.444445c-11.377778 22.755556-19.911111 51.2-19.911111 79.644444 0 79.644444 62.577778 142.222222 142.222222 142.222223s142.222222-62.577778 142.222222-142.222223-62.577778-142.222222-142.222222-142.222222z m-85.333333-625.777778c31.288889 0 56.888889 25.6 56.888889 56.888889s-25.6 56.888889-56.888889 56.888889-56.888889-25.6-56.888889-56.888889 25.6-56.888889 56.888889-56.888889z m-682.666667 85.333334c0-31.288889 25.6-56.888889 56.888889-56.888889s56.888889 25.6 56.888889 56.888889-25.6 56.888889-56.888889 56.888889-56.888889-25.6-56.888889-56.888889z m85.333333 682.666666c-48.355556 0-85.333333-36.977778-85.333333-85.333333s36.977778-85.333333 85.333333-85.333333c14.222222 0 25.6 2.844444 36.977778 8.533333l39.822222 36.977778c5.688889 11.377778 8.533333 25.6 8.533334 39.822222 0 48.355556-36.977778 85.333333-85.333334 85.333333z m284.444445-256c-79.644444 0-142.222222-62.577778-142.222222-142.222222s62.577778-142.222222 142.222222-142.222222 142.222222 62.577778 142.222222 142.222222-62.577778 142.222222-142.222222 142.222222z m398.222222 341.333334c-48.355556 0-85.333333-36.977778-85.333333-85.333334s36.977778-85.333333 85.333333-85.333333 85.333333 36.977778 85.333333 85.333333-36.977778 85.333333-85.333333 85.333334z" p-id="6589" fill="#ffffff"></path></svg>
    </div>
  </el-tooltip>

  <!-- 图片解析悬浮按钮（固定左上角） -->
  <el-tooltip
    class="box-item"
    effect="dark"
    content="AI图片解析/解答"
    placement="right"
  >
    <div 
      class="photo-float-btn"
      @click="openphotoAnalysis"
      :ref="setTourTargetRef('photoAnalysis')"
    >
      <svg t="1785328737700" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="6843" width="20" height="20"><path d="M85.333333 727.466667a32 32 0 0 1 32 32c0 60.842667 12.373333 95.146667 32.213334 114.986666 17.365333 17.365333 45.824 29.013333 93.44 31.616l21.546666 0.597334 3.242667 0.170666a32 32 0 0 1 0 63.658667l-3.242667 0.170667-12.458666-0.170667c-61.525333-1.578667-112.384-15.402667-147.797334-50.773333C66.56 881.92 53.333333 826.624 53.333333 759.466667a32 32 0 0 1 32-32zM938.666667 727.466667a32 32 0 0 1 32 32c0 67.157333-13.226667 122.496-50.944 160.256-37.76 37.717333-93.098667 50.944-160.256 50.944a32 32 0 0 1 0-64c60.842667 0 95.146667-12.373333 114.986666-32.213334 19.882667-19.84 32.213333-54.186667 32.213334-114.986666a32 32 0 0 1 32-32zM801.322667 653.056a109.909333 109.909333 0 0 1-10.026667 106.794667A115.285333 115.285333 0 0 1 695.424 810.666667h-367.36A114.602667 114.602667 0 0 1 230.4 756.949333a111.530667 111.530667 0 0 1-4.906667-110.165333L261.546667 576h506.410666l33.365334 77.056zM981.333333 480a32 32 0 0 1 0 64H42.666667a32 32 0 0 1 0-64h938.666666zM642.474667 384.085333c27.904 1.450667 52.352 22.997333 68.778666 61.013334l1.28 2.901333h-150.613333l5.674667-9.941333c20.437333-36.352 47.232-55.381333 74.88-53.973334zM373.333333 213.333333a96 96 0 1 1 0 192 96 96 0 0 1 0-192zM264.533333 53.333333a32 32 0 0 1 0 64c-60.842667 0-95.146667 12.373333-114.986666 32.213334-19.882667 19.84-32.213333 54.186667-32.213334 114.986666a32 32 0 0 1-64 0c0-67.157333 13.226667-122.496 50.944-160.256C142.08 66.56 197.376 53.333333 264.533333 53.333333zM759.466667 53.333333c67.157333 0 122.496 13.226667 160.256 50.944 37.717333 37.76 50.944 93.098667 50.944 160.256a32 32 0 0 1-64 0c0-60.842667-12.373333-95.146667-32.213334-114.986666-19.84-19.882667-54.186667-32.213333-114.986666-32.213334a32 32 0 0 1 0-64z" fill="#ffffff" p-id="6844"></path></svg>
    </div>
  </el-tooltip>
  
  <!-- 数字孪生浮按钮 + hover弹出框 -->
  <div class="digital-twin-wrapper" :ref="setTourTargetRef('digitalTwins')">
    <div 
      class="digital-twin-float-btn"
      @click="opendigitalTwin"
      @mouseenter="digitalTwinPopupVisible = true"
      @mouseleave="digitalTwinPopupVisible = false"
    >
      <svg t="1785386077255" class="icon" viewBox="0 0 1640 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="7457" width="20" height="20"><path d="M893.221289 835.226891c-143.865546 184.560224-391.887955 206.162465-524.817928 166.812325A513.882353 513.882353 0 0 1 21.422969 363.742297C99.226891 99.67507 377.72549-52.616246 656.22409 16.761905c217.546218 53.781513 350.47619 221.759104 406.319327 512.896358l0.896359 2.59944c0.806723 3.316527 56.64986 364.817927 263.170868 364.817927a187.159664 187.159664 0 0 0 0-374.229692 212.885154 212.885154 0 0 0-126.924369 39.887956l-73.680673-183.753502c98.59944 8.963585 141.355742 12.728291 200.605042 16.941177 178.644258 14.431373 313.72549 140.54902 313.72549 313.72549a313.72549 313.72549 0 0 1-313.72549 313.72549c-309.781513 0-383.462185-437.602241-388.481792-471.484594C878.431373 237.714286 730.711485 166.543417 625.747899 140.280112c-212.436975-53.781513-424.87395 60.952381-483.316526 260.7507a387.406162 387.406162 0 0 0 261.557423 480.806723c116.526611 34.689076 352.089636 4.212885 445.221288-219.2493" fill="#ffffff" p-id="7458" data-spm-anchor-id="a313x.search_index.0.i9.2c6e3a815QvNoF" class="selected"></path></svg>
    </div>
    <!-- hover弹出框 -->
    <transition name="dt-popup">
      <div 
        v-show="digitalTwinPopupVisible" 
        class="digital-twin-popup"
        @mouseenter="digitalTwinPopupVisible = true"
        @mouseleave="digitalTwinPopupVisible = false"
      >
        <div class="dt-popup-title">智构孪生</div>
        <div class="dt-popup-row">
          <span class="dt-popup-label">{{ digitalTwinEnabled ? '孪生开启' : '孪生关闭' }}</span>
          <el-switch
            v-model="digitalTwinEnabled"
            active-text="开"
            inactive-text="关"
            @change="onDigitalTwinToggle"
          />
        </div>
      </div>
    </transition>
  </div>


  <!-- 笔记组件 -->
  <NoteBook
    v-model:visible="noteBookVisible"
    :userId="currentUserId"
    @close="noteBookVisible = false"
  />

  <!-- 知识图谱组件 -->
  <KnowledgeMap
    :visible="knowledgeMapVisible"
    :userId="currentUserId"
    @close="knowledgeMapVisible = false"
  />

  <!-- 图片解析组件 -->
  <PhotoAnalysis
    :visible="photoAnalysisVisible"
    :userId="currentUserId"
    @close="photoAnalysisVisible = false"
  />

  <!-- 数字孪生组件 -->
  <DigitalTwins
    :visible="digitalTwinVisible"
    :userId="currentUserId"
    @close="digitalTwinVisible = false"
  />

  <!-- 全局AI解释选中文本组件 -->
  <GlobalAiExplain :userId="currentUserId" />

  <!-- 漫游式引导 -->
  <el-tour
    v-model="tourVisible"
    :current="tourCurrent"
    @change="onTourChange"
    @close="onTourClose"
  >
    <el-tour-step
      v-for="(step, index) in tourSteps"
      :key="index"
      :target="getTourTarget(step.target)"
      :title="step.title"
      :description="step.content"
    />
  </el-tour>

  <!-- 通话弹窗 -->
  <CallWindow
    :show-incoming="showIncoming"
    :show-waiting="showWaiting"
    :show-calling="showCalling"
    :show-hangup="showHangup"
    :target-user-id="targetUserId"
    :incoming-caller="incomingCaller"
    :call-duration="callDuration"
    :local-volume="localVolume"
    :remote-volume="remoteVolume"
    :is-muted="isMuted"
    :is-video-enabled="isVideoEnabled"
    :local-video-stream="localVideoStream"
    :remote-video-stream="remoteVideoStream"
    :enable-video="enableVideo"
    @accept="acceptCall"
    @reject="rejectCall"
    @hangup="hangUp"
    @close="closeHangupStatus"
    @toggle-mute="toggleMute"
    @toggle-video="toggleVideo"
  />

  <!-- 导览结束庆祝动画 -->
  <Transition name="celebration">
    <div v-if="showCelebration" class="celebration-overlay">
      <div class="celebration-content">
        <div class="celebration-icon">
          <svg t="1784181824604" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="1819" width="60" height="60"><path d="M625.354383 160.869061a24.666733 24.666733 0 0 0 25.280843-25.332018 23.284986 23.284986 0 0 0-21.698537-21.647361 24.666733 24.666733 0 0 0-25.280842 25.280842c0 10.849268 7.215787 21.698537 21.698536 21.698537z m-177.068246 361.198753c-7.164611 18.065055 3.633481 36.13011 25.332018 39.763592 10.849268 0 18.065055-3.582306 21.64736-7.215787 28.914324-28.914324 57.828647-57.828647 83.10949-86.691795l137.253479-137.304655c7.266963-7.215787 10.849268-10.849268 10.849268-21.647361 0-14.48275-7.215787-25.280842-21.647361-28.914323-14.48275-3.582306-21.698537 0-28.914323 7.215787-104.75685 104.75685-115.606118 119.2396-220.362969 223.996449-3.582306 3.582306-7.215787 7.164611-7.215787 10.798093z m104.808025-191.397469c10.849268 0 18.065055-3.633481 21.647361-10.900444 14.48275-32.496629 28.914324-64.993258 39.763592-97.489887 3.582306-10.849268 0-21.698537-10.849268-28.914324-10.849268-3.582306-25.280842 0-28.914324 10.849268-14.431574 32.496629-28.863148 64.993258-39.712416 97.541063-7.215787 14.431574 3.582306 28.863148 18.065055 28.863148z m231.212237 64.993258c-32.547805 10.849268-61.410953 25.280842-90.325276 39.712416a24.410854 24.410854 0 0 0-14.48275 21.698537c0 14.431574 14.48275 25.280842 28.914324 18.065055 32.496629-10.849268 61.410953-25.280842 93.907582-39.763592 14.48275-7.164611 18.065055-18.065055 10.849268-28.863148-3.582306-10.849268-14.431574-18.065055-28.863148-10.849268z m-50.61286-173.383589c7.215787 3.582306 18.065055 3.582306 25.280842 7.164611 10.849268 3.633481 14.48275 7.266963 18.065055 18.116231 3.582306 10.798093 3.582306 18.065055 7.266963 28.863147 3.582306 7.266963 7.164611 14.48275 18.01388 14.48275 7.266963 0 14.48275-7.215787 18.065055-14.48275 3.633481-10.798093 7.266963-18.065055 7.266962-28.863147 3.582306-10.849268 7.164611-14.48275 18.065056-18.065056 10.798093-3.582306 21.647361-7.215787 28.863147-10.849268 7.215787-3.582306 10.849268-10.849268 14.48275-18.065055 0-10.849268-7.266963-14.431574-14.48275-18.065055-7.215787 0-18.065055-3.582306-25.280842-7.215787-10.849268-3.582306-18.065055-7.215787-18.065055-18.065055-3.582306-7.215787-3.582306-18.065055-7.215787-25.280843-3.582306-10.849268-7.215787-14.431574-18.065055-14.431573s-14.431574 7.164611-18.065055 14.431573c-3.582306 7.215787-3.582306 14.431574-7.215787 25.280843-7.215787 10.849268-14.431574 18.065055-25.280842 18.065055-7.215787 3.582306-14.48275 3.582306-21.698537 7.215787-10.798093 3.582306-18.065055 7.215787-18.065055 18.065055 0 14.431574 7.266963 18.065055 18.065055 21.698537z m-314.219374-46.979379c-14.48275 7.215787-21.698537 21.647361-14.48275 36.13011 39.712416 101.123369 21.647361 162.534321-36.13011 242.061505-7.215787 14.431574-7.215787 28.863148 7.215787 39.712416 3.582306 3.582306 10.849268 3.582306 14.431573 3.582306 7.266963 0 18.065055-3.582306 21.698537-10.798093 64.993258-90.325276 93.907582-173.434765 43.345897-296.25667-3.582306-14.431574-21.698537-21.647361-36.13011-14.431574z m451.524029 184.232858c-14.48275 0-25.280842 10.849268-25.280842 21.64736 0 14.48275 10.798093 21.698537 21.64736 21.698537 14.431574 0 25.280842-10.849268 21.698537-25.280842 3.582306-7.215787-7.266963-18.065055-18.065055-18.065055z m-93.958758 364.88341c-10.798093 0-25.280842 10.798093-25.280842 21.647361s10.849268 21.647361 21.698537 25.280842c10.849268 0 25.280842-10.849268 25.280842-21.698537 0-14.431574-10.849268-25.280842-21.698537-25.280842z m43.345898-169.801284c-122.821905-50.61286-205.880219-21.698537-296.205495 43.345897-14.431574 7.164611-14.431574 25.280842-7.215787 39.712416 7.215787 7.215787 14.431574 10.849268 21.698537 10.849269 7.164611 0 10.798093 0 14.431573-3.582306 79.476008-57.828647 140.88696-79.527184 242.061505-36.130111 14.431574 7.164611 32.496629 0 36.078935-14.482749 10.849268-18.065055 3.582306-36.13011-10.849268-39.712416z m-122.821906 137.253479c-7.164611-3.582306-18.065055-7.215787-25.280842-10.849268-14.431574-3.582306-25.280842-10.798093-39.712416-14.431574-14.48275-3.582306-25.280842 3.582306-28.914323 14.431574-3.582306 14.48275 0 25.280842 14.431574 28.914323l65.044434 21.698537c14.431574 3.582306 28.914324-7.266963 28.914323-18.065055 0-10.849268-3.582306-18.065055-14.48275-21.698537z m-426.243186-245.643811c-7.215787-7.215787-21.698537-10.849268-32.49663-10.849268-10.849268 3.582306-21.698537 10.849268-28.914323 21.698537l-205.931395 491.287621c-7.164611 14.431574-3.582306 28.914324 7.266963 39.712416 10.798093 10.849268 25.280842 14.48275 39.712416 7.215787l494.869927-205.880219c10.849268-3.582306 18.116231-14.431574 21.698536-28.914324a29.170202 29.170202 0 0 0-10.849268-32.496629L271.320242 446.225287z m-90.325277 419.0274l-72.209045 28.914324 83.058314-198.664432-10.849269 169.750108z m122.821906-54.195165l-64.993259 28.914323 21.647361-292.572013v-7.266963l61.410953 61.410953-18.065055 209.5137z m57.828647-25.280842l10.798092-133.619998 93.958758 93.907582-104.75685 39.712416z m646.606155-184.232858a19.856208 19.856208 0 0 0-18.065055-10.798093h-28.914324a32.752508 32.752508 0 0 1-25.280842-10.849268c-3.582306-7.215787-10.849268-14.48275-14.431574-21.698537-7.215787-7.164611-14.431574-14.431574-21.698536-10.798092-10.798093 3.582306-10.798093 10.798093-10.798093 21.647361v25.280842a32.752508 32.752508 0 0 1-10.849268 25.280842c-7.215787 3.582306-14.48275 10.849268-21.698537 14.48275-7.164611 7.164611-14.431574 14.431574-10.798092 25.280842 3.582306 10.849268 10.798093 10.849268 21.64736 10.849268h25.280843a32.752508 32.752508 0 0 1 25.280842 10.798093c7.215787 7.215787 10.849268 14.48275 18.065055 25.280842 3.582306 7.266963 10.849268 7.266963 21.698537 7.266963 7.164611-3.633481 14.431574-7.266963 14.431574-18.065056v-32.547805c0-10.798093 3.582306-14.431574 10.849268-21.64736 7.215787-7.215787 18.065055-10.849268 25.280842-18.065056 0-7.215787 3.582306-14.431574 0-21.698536zM264.104455 319.821077c7.215787 21.698537 14.431574 39.763592 21.64736 61.410952 7.266963 14.48275 18.065055 21.698537 28.914324 14.48275 10.849268-3.582306 18.065055-18.065055 14.431574-32.496629-7.164611-21.698537-14.431574-39.763592-21.647361-61.410953-3.582306-10.849268-10.849268-14.48275-21.698537-14.482749-14.431574 3.582306-25.280842 18.065055-21.64736 32.496629z m61.410952-238.376848a32.752508 32.752508 0 0 1 10.849269 25.280842c0 10.849268-3.633481 18.065055-3.633482 28.863148 0 10.849268 0 18.065055 10.849268 21.698536 7.164611 3.582306 14.431574 0 21.647361-7.215787l21.698537-21.698536c7.215787-7.164611 14.431574-10.798093 21.647361-7.164611 10.849268 0 21.698537 3.582306 32.547805 3.582305 7.164611 0 14.431574-3.582306 18.065055-10.849268 3.582306-7.215787 3.582306-14.431574-3.633482-21.698537-7.215787-7.164611-14.431574-10.798093-21.698536-18.065055-7.164611-7.164611-14.431574-14.431574-10.798093-25.280842 0-7.164611 3.582306-18.065055 3.582306-25.280842 0-10.849268 0-18.065055-10.798093-21.647361-10.849268-3.582306-18.065055 0-21.698536 7.164611-7.215787 7.266963-10.849268 14.48275-18.065055 18.116231-7.215787 10.849268-14.431574 14.431574-28.914324 10.849268-10.798093-7.266963-21.647361-7.266963-28.863148-7.266962-10.849268 0-18.065055 3.633481-21.698536 10.849268-3.582306 7.215787 0 14.48275 7.215787 21.698537 7.215787 7.164611 14.48275 10.798093 21.698536 18.065055zM253.255186 254.776643a23.284986 23.284986 0 0 0 21.698537-21.698537c0-10.798093-10.849268-25.280842-21.698537-25.280842s-25.280842 10.849268-25.280842 21.698536c3.582306 14.431574 10.849268 25.280842 25.280842 25.280843z" fill="#FE746C" p-id="1820"></path></svg>
        </div>
        <h2 class="celebration-title">导览完成</h2>
        <p class="celebration-text">恭喜您完成了系统导览！</p>
        <div class="celebration-stars">
          <span v-for="i in 5" :key="i" class="star" :style="{ animationDelay: i * 0.2 + 's' }">
            <svg t="1784182064325" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="10871" width="35" height="35"><path d="M602.88 987.648a254.336 254.336 0 0 0 256.32-62.784l76.544-76.544a254.4 254.4 0 0 0 0-359.744l-198.272-198.336a92.032 92.032 0 0 0-140.672 12.48l-12.416-12.416a92.032 92.032 0 0 0-140.608 12.416l-88.96-88.96a92.032 92.032 0 0 0-144.448 18.368 92.096 92.096 0 0 0-120.384 120.448 92.224 92.224 0 0 0-18.368 144.384l12.416 12.48a92.032 92.032 0 0 0-12.416 140.608l274.816 274.816a254.4 254.4 0 0 0 256.384 62.72zM163.456 328.512a16.192 16.192 0 0 1 22.848-22.848l37.952 37.952 0.32 0.32 133.888 133.952a37.952 37.952 0 1 0 53.696-53.696L278.656 290.624l-0.384-0.32a16.192 16.192 0 0 1 22.912-22.912L454.208 420.48a37.952 37.952 0 0 0 53.696-53.696 16.192 16.192 0 0 1 22.848-22.848l76.096 76.16 0.384 0.384 121.792 121.792a178.56 178.56 0 0 1 0 252.416l-76.48 76.544a178.496 178.496 0 0 1-252.48 0L125.248 596.352a16.192 16.192 0 0 1 22.848-22.848l0.64 0.576 95.04 95.104a37.952 37.952 0 0 0 53.632-53.696L163.52 481.6l-0.64-0.64-37.632-37.632a16.192 16.192 0 0 1 22.848-22.848l0.512 0.448 133.44 133.44a37.952 37.952 0 1 0 53.632-53.632L201.792 366.72l-0.512-0.448-37.76-37.76z m497.28 38.08a16.192 16.192 0 0 1 22.976-22.656l198.336 198.272a178.56 178.56 0 0 1 0 252.48l-76.544 76.48c-26.944 26.944-60.416 43.52-95.36 49.6l72.512-72.448a254.4 254.4 0 0 0 0-359.744l-121.984-121.984z" fill="#efb336" p-id="10872" data-spm-anchor-id="a313x.search_index.0.i3.20a53a81vnJGFY" class="selected"></path><path d="M656.256 55.872a37.952 37.952 0 1 0-75.904 0v153.088a37.952 37.952 0 0 0 75.904 0V55.872zM823.296 79.36a37.952 37.952 0 0 0-50.944 16.96L734.08 172.8a37.952 37.952 0 0 0 67.904 33.92l38.272-76.544a37.952 37.952 0 0 0-16.96-50.88zM464.192 96.32a37.952 37.952 0 1 0-67.84 33.92l38.208 76.544a37.952 37.952 0 0 0 67.84-33.92l-38.208-76.544z" fill="#efb336" p-id="10873" data-spm-anchor-id="a313x.search_index.0.i4.20a53a81vnJGFY" class="selected"></path></svg>
          </span>
        </div>
      </div>
      <div class="celebration-confetti">
        <span v-for="i in 20" :key="i" class="confetti" :style="{ 
          left: Math.random() * 100 + '%', 
          animationDelay: Math.random() * 2 + 's',
          animationDuration: (2 + Math.random() * 2) + 's'
        }"></span>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
/* 顶部导航栏 */
.topNav {
  z-index: 3;
  width: 100%;
  /* position: fixed; */
  /* 粘性定位，黏在顶部 */
  position: sticky;
  top: 0;
  left: 0;
  min-width: 1580px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 100px;
  height: 60px;
  background-color: var(--bg-card);
  box-shadow: var(--shadow-normal);
  transition: all 0.3s ease-in-out;
}
/* logo部分 */
.logo {
  width: 200px;
  gap: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.logo:hover {
  cursor: pointer;
}
.logo img {
  width: 70px;
  height: 70px;
  margin-left: 3px;
  transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.logo:hover img {
  transform: rotate(10deg) scale(1.08);
}

.logo h1 {
  color: var(--text-title);
  font-size: 25px;
  font-family: "抖音美好体","三极行楷简体-粗",sans-serif;
  transition: color 0.3s ease;
  /* 行间距 */
  line-height: 1.2;
}
.logo:hover h1 {
  color: var(--primary);
}
/* 导航 */
.nav {
  height: 100%;
  display: flex;
  align-items: center;
}
.nav ul,
li,
a {
  height: 100%;
  display: block;
  transition: all 0.3s ease-in-out;
}
.nav ul {
  display: flex;
  flex-wrap: nowrap;
  gap: 40px;
}
.nav ul>li {
  font-size: 17px;
  border-bottom: 2px solid transparent;
  position: relative;
  transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}
/* 滑动下划线指示器 */
.nav ul>li::after {
  content: '';
  position: absolute;
  bottom: -2px;
  left: 50%;
  width: 0;
  height: 2px;
  background: var(--grad-primary);
  border-radius: 1px;
  transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
  transform: translateX(-50%);
}
.nav ul>li a {
  display: flex;
  align-items: center;
  color: var(--text-body);
  text-decoration: none;
  padding: 0 4px;
  transition: color 0.3s ease;

  /* 关键：文本溢出处理 */
  white-space: nowrap; /* 强制不换行 */
  overflow: hidden;    /* 隐藏溢出部分 */
  text-overflow: ellipsis; /* 显示省略号 (...) */
}
/* 图标悬停弹跳动画 */
.nav ul>li a .el-icon {
  transition: transform 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.nav ul>li:hover a .el-icon {
  transform: scale(1.2) translateY(-2px);
}
.nav ul>li a:hover {
  color: var(--primary);
}
.nav ul>li:hover{
  border-bottom-color: transparent;
}
.nav ul>li:hover::after {
  width: 100%;
}
.nav ul > li:has(a.router-link-active) {
  border-bottom-color: transparent;
}
.nav ul > li:has(a.router-link-active)::after {
  width: 100%;
}
.nav ul > li a.router-link-active {
  color: var(--primary);
}
.nav ul > li a.router-link-active .el-icon {
  transform: scale(1.1);
}

.nav :deep(.el-icon),
.mes :deep(.el-icon) {
  font-size: 20px;
}

/* 内容 */
.content {
  /* margin-top: 60px; */
  padding: 0 100px;
  min-height: calc(100vh - 60px);
  position: relative;
}
.content::before {
  content: '';
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: url('@/assets/image/mainbgcImg.png') no-repeat center center;
  background-size: cover;
  background-attachment: fixed;
  opacity: 0.4;
  z-index: 0;
}

/* 用户信息 */
.user {
  width: 220px;
  display: flex;
  align-items: center;
}
/* 用户区域 */
.user .mes { 
  cursor: pointer;
  margin-right: 20px;
  display: flex;
  align-items: center;
  position: relative;
}
/* 消息提醒 */
.mes .el-icon { 
  font-size: 18px;
  transition: all 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.mes:hover .el-icon {
  transform: scale(1.25);
  color: var(--primary);
}
/* 头像 */
.user .avatar { 
  margin-right: 10px;
  padding-top: 7px;
  transition: transform 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.user .avatar:hover {
  transform: scale(1.1);
}
/* 用户信息 */
.username { 
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
}
.username a {
  color: var(--text-body);
  transition: color 0.3s ease;
}
.username:hover>a,
.username:hover .el-icon,
.mes:hover .el-icon {
  color: var(--primary);
  text-decoration: none;
}
/* 下拉菜单 */
.dropdown {
  min-width: 100px;
  background-color: var(--bg-card);
  box-shadow: var(--shadow-normal);
  border: 1.5px solid var(--border-color);
  border-radius: 8px;
  position: absolute;
  top: 100%; /* 确保位于触发元素正下方 */
  right: -10px;
  margin-top: 8px;
  opacity: 0;
  visibility: hidden;
  /* 动画效果：淡入 + 轻微上浮 */
  transform: translateY(-10px) scale(0.95);
  transition: opacity 0.3s cubic-bezier(0.4, 0, 0.2, 1), visibility 0.3s, transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 2; /* 确保层级足够高 */
  overflow: hidden; /* 防止圆角溢出 */
  padding: 4px 0;
}
.dropdown li {
  list-style: none;
}
.dropdown li a { 
  text-decoration: none;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 16px;
  width: 100%;
  height: 40px;
  color: var(--text-body);
  font-size: 14px;
  border-radius: 4px;
  margin: 0 4px;
  transition: background-color 0.2s ease, color 0.2s ease;
}
.dropdown li a:hover {
  color: var(--primary);
}
/* 显示下拉菜单时的状态 */
.username:hover .dropdown {
  opacity: 1;
  visibility: visible;
  /* 确保动画效果 */
  transform: translateY(0) scale(1);
}
.username .el-icon {
  transition: transform 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.username:hover .el-icon {
  /* 确保图标旋转 */
  transform: rotate(180deg);
}


/* 登录按钮 */
.pleaseLogin {
  width: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.pleaseLogin a { 
  background-color: var(--primary-light);
  text-decoration: none;
  display: block;
  width: 90px;
  height: 33px;
  border: 1px solid var(--primary);
  border-radius: 15px;
  font-size: 16px;
  color: var(--primary);

  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
}
.pleaseLogin a:hover { 
  background-color: var(--primary);
  color: var(--primary-light);
  transform: scale(1.05);
  box-shadow: var(--shadow-brand);
}
.pleaseLogin a:active {
  transform: scale(0.97);
}

/* 徽章 */
.huizhang {
  z-index: 4;
  position: absolute;
  top: 7px;
  right: -15px;
}

/* 通知徽章样式 */
.notice-badge {
  top: -10px;
}

/* 复习徽章样式 */
.review-badge {
  top: -10px;
}

/* 徽章脉冲动画 */
.notice-badge :deep(.el-badge__content) {
  animation: badge-pulse 2s ease-in-out infinite;
}

.review-badge :deep(.el-badge__content) {
  animation: badge-pulse 2s ease-in-out infinite;
}

@keyframes badge-pulse {
  0%, 100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.15);
  }
}

/* 笔记悬浮按钮（固定右下角） */
.note-float-btn {
  position: fixed;
  left: 20px;
  top: 230px;
  padding: 10px 10px;
  border-radius: var(--radius-lg);
  background: var(--primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  cursor: pointer;
  z-index: 3;
  box-shadow: var(--shadow-brand);
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s ease;
}
.note-float-btn:hover {
  background: var(--primary-hv);
  box-shadow: 0 4px 16px rgba(45, 125, 219, 0.35);
  transform: translateY(-2px);
}
.note-float-btn:active {
  background: var(--primary-act);
  transform: translateY(0);
}

/* 知识图谱按钮 */
.map-float-btn {
  position: fixed;
  left: 20px;
  top: 80px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
  padding: 10px 10px;
  border-radius: var(--radius-lg);
  background: var(--primary);
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
  z-index: 3;
  box-shadow: var(--shadow-brand);
}

.map-float-btn:hover {
  background: var(--primary-hv);
  box-shadow: 0 4px 16px rgba(45, 125, 219, 0.35);
  transform: translateY(-2px);
}

.map-float-btn:active {
  background: var(--primary-act);
  transform: translateY(0);
}

.map-float-btn .el-icon {
  font-size: 20px;
}

/* 图片解析 */
.photo-float-btn {
  position: fixed;
  left: 20px;
  top: 130px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
  padding: 10px 10px;
  border-radius: var(--radius-lg);
  background: var(--primary);
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
  z-index: 3;
  box-shadow: var(--shadow-brand);
}

.photo-float-btn:hover {
  background: var(--primary-hv);
  box-shadow: 0 4px 16px rgba(45, 125, 219, 0.35);
  transform: translateY(-2px);
}

.photo-float-btn:active {
  background: var(--primary-act);
  transform: translateY(0);
}

.photo-float-btn .el-icon {
  font-size: 20px;
}

/* 数字孪生按钮 */
.digital-twin-wrapper {
  position: fixed;
  left: 20px;
  top: 180px;
  z-index: 3;
}

.digital-twin-float-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
  padding: 10px 10px;
  border-radius: var(--radius-lg);
  background: var(--primary);
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
  box-shadow: var(--shadow-brand);
}

.digital-twin-float-btn:hover {
  background: var(--primary-hv);
  box-shadow: 0 4px 16px rgba(45, 125, 219, 0.35);
  transform: translateY(-2px);
}

.digital-twin-float-btn:active {
  background: var(--primary-act);
  transform: translateY(0);
}

.digital-twin-float-btn .el-icon {
  font-size: 20px;
}

/* 数字孪生 hover 弹出框 */
.digital-twin-popup {
  position: absolute;
  left: calc(100% + 12px);
  top: 50%;
  transform: translateY(-50%);
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 14px 18px;
  box-shadow: 0 4px 20px var(--shadow-color);
  min-width: 160px;
  z-index: 91;
}

.dt-popup-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-title);
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-color);
}

.dt-popup-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.dt-popup-label {
  font-size: 13px;
  color: var(--text-body);
  white-space: nowrap;
}

/* 弹出框过渡动画 */
.dt-popup-enter-active,
.dt-popup-leave-active {
  transition: all 0.2s ease;
}

.dt-popup-enter-from {
  opacity: 0;
  transform: translateY(-50%) translateX(-8px);
}

.dt-popup-leave-to {
  opacity: 0;
  transform: translateY(-50%) translateX(-8px);
}

/* 漫游式引导样式 */
:deep(.el-tour__content) {
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
}

:deep(.el-tour__header) {
  padding: 16px 20px 8px;
}

:deep(.el-tour__title) {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-title);
}

:deep(.el-tour__body) {
  padding: 8px 20px 16px;
}

:deep(.el-tour__description) {
  font-size: 14px;
  color: var(--text-body);
  line-height: 1.6;
}

:deep(.el-tour__footer) {
  padding: 8px 20px 16px;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

:deep(.el-tour__close-btn) {
  color: var(--text-body);
  transition: color 0.2s;
}

:deep(.el-tour__close-btn:hover) {
  color: var(--primary);
}

:deep(.el-tour__btn) {
  border-radius: 6px;
  font-weight: 500;
}

:deep(.el-tour__btn--primary) {
  background: var(--primary);
  border-color: var(--primary);
}

:deep(.el-tour__btn--primary:hover) {
  background: var(--primary-act);
  border-color: var(--primary-act);
}

/* 导览结束庆祝动画 */
.celebration-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  overflow: hidden;
}

.celebration-content {
  background: #fff;
  border-radius: 20px;
  padding: 40px 60px;
  text-align: center;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  animation: popIn 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.celebration-icon {
  font-size: 80px;
  animation: bounce 1s ease-in-out infinite;
}

.celebration-title {
  font-size: 28px;
  font-weight: 700;
  color: var(--primary);
  margin: 20px 0 10px;
  animation: slideUp 0.5s ease-out 0.2s both;
}

.celebration-text {
  font-size: 16px;
  color: var(--text-body);
  animation: slideUp 0.5s ease-out 0.3s both;
}

.celebration-stars {
  display: flex;
  justify-content: center;
  gap: 15px;
  margin-top: 20px;
}

.star {
  font-size: 30px;
  color: #fbbf24;
  opacity: 0;
  animation: starPop 0.4s ease-out forwards;
}

.celebration-confetti {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.confetti {
  position: absolute;
  top: -20px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  animation: confettiFall linear forwards;
}

.confetti:nth-child(odd) {
  background: #ef4444;
}

.confetti:nth-child(even) {
  background: #3b82f6;
}

.confetti:nth-child(3n) {
  background: #22c55e;
}

.confetti:nth-child(4n) {
  background: #eab308;
}

@keyframes popIn {
  0% {
    transform: scale(0);
    opacity: 0;
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}

@keyframes bounce {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-20px);
  }
}

@keyframes slideUp {
  0% {
    transform: translateY(20px);
    opacity: 0;
  }
  100% {
    transform: translateY(0);
    opacity: 1;
  }
}

@keyframes starPop {
  0% {
    transform: scale(0) rotate(-30deg);
    opacity: 0;
  }
  100% {
    transform: scale(1) rotate(0);
    opacity: 1;
  }
}

@keyframes confettiFall {
  0% {
    transform: translateY(0) rotate(0deg);
    opacity: 1;
  }
  100% {
    transform: translateY(100vh) rotate(720deg);
    opacity: 0;
  }
}

/* 过渡动画 */
.celebration-enter-active {
  transition: opacity 0.3s ease;
}

.celebration-leave-active {
  transition: opacity 0.5s ease;
}

.celebration-enter-from,
.celebration-leave-to {
  opacity: 0;
}
</style>