<script setup>
import { ref, watch, nextTick, onMounted, computed, provide, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast, showSuccessToast, showFailToast } from 'vant'
import { exitApi } from '@/api/login.js'
import { reviewRemindApi, getEvaluateReportNotifyApi } from '@/api/mainApi/layout.js'
import { colearningNoticeApi } from '@/api/mainApi/partners.js'
import voiceCallService from './js/voiceCall.js'
import MobileCallWindow from '@/views/phone/components/MobileCallWindow.vue'

const route = useRoute()
const router = useRouter()

// 底部导航激活项
const activeTab = ref(0)
const contentRef = ref(null)

// ==================== 通知数量轮询 ====================
const reviewCount = ref(0)
const colearnCount = ref(0)
const evaluateUnreadCount = ref(0)
const totalNotificationCount = computed(() =>
  reviewCount.value + colearnCount.value + evaluateUnreadCount.value
)

let notifyPollingTimer = null
let isNotifyPollingActive = false

const fetchNotificationCounts = async () => {
  if (!userId.value) return
  try {
    const [reviewRes, colearnRes, evalRes] = await Promise.all([
      reviewRemindApi(userId.value),
      colearningNoticeApi(userId.value),
      getEvaluateReportNotifyApi(userId.value)
    ])
    if (reviewRes.code === 1 && reviewRes.data && reviewRes.data.reminder) {
      reviewCount.value = reviewRes.data.reminder.today_due_count || 0
    }
    if (colearnRes.code === 1 && colearnRes.data) {
      colearnCount.value = (colearnRes.data.accepted || []).length
    }
    if (evalRes.code === 1 && evalRes.data) {
      evaluateUnreadCount.value = evalRes.data.unread_count || 0
    }
  } catch (e) {}
}

const startNotifyPolling = () => {
  isNotifyPollingActive = true
  fetchNotificationCounts()
  notifyPollingTimer = setTimeout(() => {
    if (isNotifyPollingActive) notifyPollingLoop()
  }, 5000)
}

const notifyPollingLoop = async () => {
  if (!isNotifyPollingActive) return
  await fetchNotificationCounts()
  if (isNotifyPollingActive) {
    notifyPollingTimer = setTimeout(notifyPollingLoop, 30000)
  }
}

const stopNotifyPolling = () => {
  isNotifyPollingActive = false
  if (notifyPollingTimer) {
    clearTimeout(notifyPollingTimer)
    notifyPollingTimer = null
  }
}

// 当前用户
const userId = ref('')
const loginUser = ref(null)
let voiceInited = false  // 语音通话是否已初始化

// 导航项
const tabs = [
  { name: '首页', icon: 'home-o', path: '/phone/index' },
  { name: '对话', icon: 'smile-o', path: '/phone/chat' },
  { name: '功能', icon: 'apps-o', path: '/phone/function' },
  { name: '通知', icon: 'envelop-o', path: '/phone/notification' },
  { name: '我的', icon: 'user-o', path: '/phone/userCenter' }
]

// 检测用户登录状态
const checkLogin = () => {
  const userStr = localStorage.getItem('loginUser')
  if (!userStr) return false
  try {
    const user = JSON.parse(userStr)
    if (user && user.id && user.token) {
      loginUser.value = user
      userId.value = typeof user.id === 'string' ? user.id : String(user.id)
      return true
    }
    return false
  } catch (e) {
    return false
  }
}

const redirectToLogin = () => {
  showToast('请先登录')
  router.replace('/phone/login')
}

// ==================== 语音通话相关 ====================
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

const isInCall = computed(() => {
  return showIncoming.value || showWaiting.value || showCalling.value
})

const initVoiceCall = () => {
  if (!userId.value) return
  if (voiceInited) return
  voiceInited = true
  voiceCallService.setUserId(userId.value)
  voiceCallService.setCallbacks({
    onIncomingCall: (from, username, hasVideo) => {
      incomingCaller.value = username
      targetUserId.value = from
      enableVideo.value = hasVideo || false
      showIncoming.value = true
      showWaiting.value = false
      showCalling.value = false
      showHangup.value = false
    },
    onCallRejected: (username) => {
      showFailToast(`${username} 拒绝了通话`)
      hideAllCallWindows()
    },
    onCallCanceled: (username) => {
      showToast(`${username} 取消了呼叫`)
      hideAllCallWindows()
    },
    onSelfReject: () => {
      showToast('你取消了通话')
      hideAllCallWindows()
    },
    onCallAccepted: () => {
      showIncoming.value = false
      showWaiting.value = true
    },
    onCallConnected: () => {
      showWaiting.value = false
      showCalling.value = true
    },
    onRemoteHangup: () => {
      showIncoming.value = false
      showWaiting.value = false
      showCalling.value = false
      showHangup.value = true
    },
    onCallTimeout: (msg) => {
      showToast(msg)
    },
    onUserOffline: (msg) => {
      showToast(msg)
    },
    onVolumeChange: (volumes) => {
      localVolume.value = volumes.local
      remoteVolume.value = volumes.remote
    },
    onMuteChange: (muted) => {
      isMuted.value = muted
    },
    onNotifyConnected: () => {},
    onSignalConnected: () => {},
    onDurationChange: (duration) => {
      callDuration.value = duration
    },
    onLocalVideoStream: (stream) => {
      localVideoStream.value = stream
      if (stream) isVideoEnabled.value = true
    },
    onRemoteVideoStream: (stream) => {
      remoteVideoStream.value = stream
    },
    onVideoToggle: (enabled) => {
      isVideoEnabled.value = enabled
    }
  })
  voiceCallService.connectNotifyChannel()
}

const acceptCall = () => { voiceCallService.acceptCall() }
const rejectCall = () => { voiceCallService.rejectCall(); showIncoming.value = false }
const hangUp = () => { voiceCallService.hangUp(); hideAllCallWindows() }
const closeHangupStatus = () => { showHangup.value = false; callDuration.value = '00:00' }
const toggleMute = () => { voiceCallService.toggleMute() }
const toggleVideo = () => { voiceCallService.toggleVideo() }
const flipCamera = () => { voiceCallService.flipCamera() }
const hideAllCallWindows = () => {
  showIncoming.value = false
  showWaiting.value = false
  showCalling.value = false
  showHangup.value = false
  isVideoEnabled.value = false
  localVideoStream.value = null
  remoteVideoStream.value = null
  enableVideo.value = false
}

const startVoiceCall = (targetId, withVideo = false) => {
  if (!targetId) { showToast('请选择要通话的用户'); return }
  if (targetId === userId.value) { showToast('不能呼叫自己'); return }
  targetUserId.value = targetId
  enableVideo.value = withVideo
  showIncoming.value = false
  showWaiting.value = true
  showCalling.value = false
  showHangup.value = false
  voiceCallService.startCall(targetId, withVideo)
}

provide('startVoiceCall', startVoiceCall)
provide('isInCall', isInCall)
provide('flipCamera', flipCamera)

// 退出登录
const exitLogin = async () => {
  try {
    voiceCallService.disconnectNotifyChannel()
    voiceInited = false
    if (userId.value) {
      try { await exitApi(userId.value) } catch (e) {}
    }
    localStorage.removeItem('loginUser')
    showSuccessToast('退出登录成功')
    router.replace('/phone/login')
  } catch (e) {
    localStorage.removeItem('loginUser')
    router.replace('/phone/login')
  }
}

// 切换导航
const onTabChange = (index) => {
  router.push(tabs[index].path)
}

// 挂载时检测 + 初始化语音通话（与 PC 端一致，仅在 onMounted 中初始化）
onMounted(() => {
  if (checkLogin()) {
    initVoiceCall()
    startNotifyPolling()
  } else {
    redirectToLogin()
  }
})

onUnmounted(() => {
  stopNotifyPolling()
})

// 组件卸载时不断开语音通道（与 PC 端一致，仅退出登录时断开）
// 这样在路由切换时通知通道保持连接，来电通知不会丢失

// 路由切换时：检测登录 + 高亮对应导航项（不在 tabs 则全部不高亮）+ 滚动到顶部
watch(() => route.path, (path) => {
  if (!checkLogin()) {
    redirectToLogin()
    return
  }
  const idx = tabs.findIndex(tab => tab.path === path)
  activeTab.value = idx !== -1 ? idx : -1
  nextTick(() => {
    if (contentRef.value) contentRef.value.scrollTop = 0
  })
}, { immediate: true, flush: 'sync' })
</script>

<template>
  <div class="phone-layout">
    <div class="phone-content" ref="contentRef">
      <router-view />
    </div>
    <van-tabbar v-model="activeTab" @change="onTabChange" fixed placeholder>
      <van-tabbar-item
        v-for="(tab, index) in tabs"
        :key="index"
        :icon="tab.icon"
        :class="{ 'tab-highlight': index === 2 }"
      >
        {{ index === 2 ? '' : tab.name }}
        <span
          v-if="index === 3 && totalNotificationCount > 0"
          class="notification-badge"
        >{{ totalNotificationCount > 99 ? '99+' : totalNotificationCount }}</span>
      </van-tabbar-item>
    </van-tabbar>

    <!-- 通话弹窗 -->
    <MobileCallWindow
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
      @flip-camera="flipCamera"
    />
  </div>
</template>

<style scoped>
.phone-layout {
  height: 100vh;
  height: 100dvh;
  background: var(--bg-page);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.phone-content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}

:deep(.van-tabbar) {
  background: var(--bg-card);
  border-top: none;
  z-index: 9999;
  box-shadow: 0 -2px 12px var(--shadow-color);
}

:deep(.van-tabbar-item) {
  color: var(--text-gray);
  transition: color 0.3s;
  position: relative;
}

.notification-badge {
  position: absolute;
  top: -33px;
  right: calc(50% - 24px);
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  background: var(--main-delete, #f56c6c);
  color: #fff;
  font-size: 10px;
  font-weight: 600;
  line-height: 16px;
  text-align: center;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(245, 108, 108, 0.4);
  z-index: 10;
}

:deep(.van-tabbar-item--active) {
  color: var(--primary);
}

:deep(.van-tabbar-item--active:not(.tab-highlight) .van-icon) {
  animation: tab-pop 0.35s ease;
}

@keyframes tab-pop {
  0% { transform: scale(0.8); }
  55% { transform: scale(1.15); }
  100% { transform: scale(1); }
}

:deep(.van-tabbar-item.tab-highlight) {
  position: relative;
  z-index: 1;
}

:deep(.van-tabbar-item.tab-highlight .van-icon) {
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--grad-primary);
  color: var(--btn-text) !important;
  font-size: 28px;
  margin-bottom: 4px;
  box-shadow: var(--shadow-brand);
  transform: translateY(-5px);
  transition: transform 0.25s, box-shadow 0.25s;
  border: 4px solid var(--bg-card);
}

:deep(.van-tabbar-item.tab-highlight:active .van-icon) {
  transform: translateY(-2px) scale(0.95);
}

:deep(.van-tabbar-item.tab-highlight .van-tabbar-item__text) {
  display: none;
}
</style>
