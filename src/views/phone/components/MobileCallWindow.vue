<script setup>
import { ref, reactive, computed, watch, onUnmounted, nextTick } from 'vue'
import { getUserInfoApi } from '@/api/mainApi/index.js'

const props = defineProps({
  showIncoming: { type: Boolean, default: false },
  showWaiting: { type: Boolean, default: false },
  showCalling: { type: Boolean, default: false },
  showHangup: { type: Boolean, default: false },
  targetUserId: { type: String, default: '' },
  incomingCaller: { type: String, default: '' },
  callDuration: { type: String, default: '00:00' },
  localVolume: { type: Number, default: 0 },
  remoteVolume: { type: Number, default: 0 },
  isMuted: { type: Boolean, default: false },
  isVideoEnabled: { type: Boolean, default: false },
  localVideoStream: { type: [MediaStream, Object], default: null },
  remoteVideoStream: { type: [MediaStream, Object], default: null },
  enableVideo: { type: Boolean, default: false }
})

const emit = defineEmits(['accept', 'reject', 'hangup', 'close', 'toggleMute', 'toggleVideo', 'flipCamera'])

const callerInfo = reactive({
  userId: '',
  username: '',
  avatar: ''
})

const videoSwapped = ref(false)
// 用响应式 ref 追踪视频状态（computed 无法追踪 MediaStream 内部变化）
const hasLocalVideo = ref(false)
const hasRemoteVideo = ref(false)

// 模板视频元素引用
const localVideoMain = ref(null)
const remoteVideoMain = ref(null)
const localVideoPip = ref(null)
const remoteVideoPip = ref(null)

// 视频模式: 'none' | 'both' | 'localOnly' | 'remoteOnly'
const videoMode = computed(() => {
  if (hasLocalVideo.value && hasRemoteVideo.value) return 'both'
  if (hasLocalVideo.value) return 'localOnly'
  if (hasRemoteVideo.value) return 'remoteOnly'
  return 'none'
})

// 是否有任何通话界面显示
const isVisible = computed(
  () => props.showIncoming || props.showWaiting || props.showCalling || props.showHangup
)

// 获取用户信息
async function fetchUserInfo(userId) {
  if (!userId) return
  try {
    const res = await getUserInfoApi({ userIdList: [userId] })
    if (res.code === 1 && res.data && res.data.length > 0) {
      callerInfo.userId = res.data[0].userId
      callerInfo.username = res.data[0].username
      callerInfo.avatar = res.data[0].avatar || ''
    }
  } catch (error) {
    console.warn('获取用户信息失败:', error)
  }
}

function getInitial(name) {
  if (!name) return '👤'
  return name.charAt(0).toUpperCase()
}

// ===== 事件处理 =====
function handleAccept() {
  emit('accept')
}
function handleReject() {
  emit('reject')
}
function handleHangUp() {
  emit('hangup')
}
function handleClose() {
  emit('close')
}
function handleToggleMute() {
  emit('toggleMute')
}
function handleToggleVideo() {
  emit('toggleVideo')
}
function handleFlipCamera() {
  emit('flipCamera')
}

// ===== 视频绑定逻辑 =====
function attachLocalVideo() {
  if (!props.localVideoStream) return
  nextTick(() => {
    // 大框：localVideoMain 在 both 模式下根据 videoSwapped 显示
    const mainEl = localVideoMain.value
    if (mainEl && mainEl.srcObject !== props.localVideoStream) {
      mainEl.srcObject = props.localVideoStream
      mainEl.play().catch(() => {})
    }
    // 小框：localVideoPip 只在 !videoSwapped（both）或 localOnly 时存在于 DOM
    const pipEl = localVideoPip.value
    if (pipEl && pipEl.srcObject !== props.localVideoStream) {
      pipEl.srcObject = props.localVideoStream
      pipEl.play().catch(() => {})
    }
  })
}

function attachRemoteVideo() {
  if (!props.remoteVideoStream) return
  nextTick(() => {
    // 大框：remoteVideoMain 在 both 模式下根据 videoSwapped 显示
    const mainEl = remoteVideoMain.value
    if (mainEl && mainEl.srcObject !== props.remoteVideoStream) {
      mainEl.srcObject = props.remoteVideoStream
      mainEl.play().catch(() => {})
    }
    // 小框：remoteVideoPip 只在 videoSwapped 时存在于 DOM
    const pipEl = remoteVideoPip.value
    if (pipEl && pipEl.srcObject !== props.remoteVideoStream) {
      pipEl.srcObject = props.remoteVideoStream
      pipEl.play().catch(() => {})
    }
  })
}

function handleSwapVideo() {
  videoSwapped.value = !videoSwapped.value
  // 切换后，重新设置 srcObject 并播放视频
  // 大框用 v-show，两个元素都在 DOM 中，都需要绑定
  // 小框用 v-if/v-else，只有当前显示的元素在 DOM 中，只需绑定一个
  nextTick(() => {
    // 大框：重新绑定两个流（v-show 切换）
    const localMain = localVideoMain.value
    const remoteMain = remoteVideoMain.value
    if (localMain && props.localVideoStream) {
      localMain.srcObject = props.localVideoStream
      localMain.play().catch(() => {})
    }
    if (remoteMain && props.remoteVideoStream) {
      remoteMain.srcObject = props.remoteVideoStream
      remoteMain.play().catch(() => {})
    }

    // 小框：只绑定当前可见的那个（v-if/v-else 切换，DOM 中只有一个）
    const pipVideo = localVideoPip.value || remoteVideoPip.value
    if (pipVideo) {
      const stream = localVideoPip.value ? props.localVideoStream : props.remoteVideoStream
      if (stream) {
        pipVideo.srcObject = stream
        pipVideo.play().catch(() => {})
      }
    }
  })
}

// ===== 监听器 =====
// 只监听用户ID变化来获取用户信息
watch(
  () => props.targetUserId,
  (newVal) => {
    if (newVal) fetchUserInfo(newVal)
  },
  { immediate: true }
)

watch(
  () => props.localVideoStream,
  (newStream) => {
    // 检查 MediaStream 是否有视频轨道（Vue 无法自动追踪，需手动更新）
    hasLocalVideo.value = !!(
      newStream &&
      newStream.getVideoTracks &&
      newStream.getVideoTracks().length > 0
    )
    nextTick(() => {
      attachLocalVideo()
    })
  }
)

watch(
  () => props.remoteVideoStream,
  (newStream) => {
    hasRemoteVideo.value = !!(
      newStream &&
      newStream.getVideoTracks &&
      newStream.getVideoTracks().length > 0
    )
    nextTick(() => {
      attachRemoteVideo()
    })
  }
)

// 监听 isVideoEnabled prop 变化（兜底：确保按钮开关状态与视频显示同步）
watch(
  () => props.isVideoEnabled,
  (val) => {
    if (val && props.localVideoStream) {
      hasLocalVideo.value = true
    } else if (!val) {
      hasLocalVideo.value = false
    }
  }
)

// 监听 videoMode 变化，确保在模式切换后正确绑定视频元素
watch(
  videoMode,
  (newMode, oldMode) => {
    // 从双方模式切换到单方模式时，重置 videoSwapped 状态
    if (oldMode === 'both' && newMode !== 'both') {
      videoSwapped.value = false
    }
    nextTick(() => {
      attachLocalVideo()
      attachRemoteVideo()
    })
  }
)

// 阻止 body 滚动
watch(
  isVisible,
  (val) => {
    if (val) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
  },
  { immediate: true }
)

onUnmounted(() => {
  document.body.style.overflow = ''
})
</script>

<template>
  <div v-if="isVisible" class="mobile-call-overlay">
    <!-- ===== 来电界面 ===== -->
    <div v-if="showIncoming" class="call-screen">
      <!-- 顶部：来电者信息 -->
      <div class="screen-top">
        <div class="incoming-status">{{ enableVideo ? '视频来电' : '语音来电' }}</div>
        <div class="caller-avatar-large">
          <img
            v-if="callerInfo.avatar"
            :src="callerInfo.avatar"
            class="avatar-img"
            alt="avatar"
          />
          <span v-else class="avatar-placeholder">{{ getInitial(callerInfo.username) }}</span>
          <!-- 来电呼吸圈 -->
          <span class="ring-pulse"></span>
          <span class="ring-pulse delay"></span>
        </div>
        <div class="caller-name-large">
          {{ callerInfo.username || incomingCaller || '未知用户' }}
        </div>
        <div class="caller-sub-text">{{ enableVideo ? '邀请你视频通话' : '邀请你语音通话' }}</div>
      </div>

      <!-- 底部：接听/拒绝按钮 -->
      <div class="screen-bottom">
        <div class="action-group">
          <button class="action-btn action-btn-reject" @click="handleReject">
            <van-icon name="phone" class="icon-hangup" size="32" />
          </button>
          <span class="action-label">拒绝</span>
        </div>
        <div class="action-group">
          <button class="action-btn action-btn-accept" @click="handleAccept">
            <van-icon name="phone" size="32" />
          </button>
          <span class="action-label">接听</span>
        </div>
      </div>
    </div>

    <!-- ===== 等待接听界面 ===== -->
    <div v-else-if="showWaiting" class="call-screen">
      <div class="screen-top">
        <div class="incoming-status">呼叫中</div>
        <div class="caller-avatar-large">
          <img
            v-if="callerInfo.avatar"
            :src="callerInfo.avatar"
            class="avatar-img"
            alt="avatar"
          />
          <span v-else class="avatar-placeholder">{{ getInitial(callerInfo.username) }}</span>
          <span class="ring-pulse"></span>
        </div>
        <div class="caller-name-large">
          {{ callerInfo.username || targetUserId || '对方' }}
        </div>
        <div class="caller-sub-text">等待接听 {{ callDuration }}</div>
      </div>

      <div class="screen-bottom">
        <div class="action-group">
          <button class="action-btn action-btn-reject" @click="handleHangUp">
            <van-icon name="phone" class="icon-hangup" size="32" />
          </button>
          <span class="action-label">取消</span>
        </div>
      </div>
    </div>

    <!-- ===== 通话中界面 ===== -->
    <div v-else-if="showCalling" class="call-screen">
      <!-- 视频模式：全屏视频 + PIP -->
      <template v-if="videoMode !== 'none'">
        <div class="video-fullscreen">
          <!-- 大视频框 -->
          <div class="video-main-box">
            <!-- 双方都有视频 -->
            <template v-if="videoMode === 'both'">
              <video
                ref="remoteVideoMain"
                v-show="!videoSwapped"
                autoplay
                playsinline
                class="video-main"
              ></video>
              <video
                ref="localVideoMain"
                v-show="videoSwapped"
                autoplay
                playsinline
                muted
                class="video-main"
              ></video>
            </template>
            <!-- 只有远端有视频 -->
            <template v-else-if="videoMode === 'remoteOnly'">
              <video
                ref="remoteVideoMain"
                autoplay
                playsinline
                class="video-main"
              ></video>
            </template>
            <!-- 只有本地有视频：大框显示对方占位 -->
            <div
              v-if="videoMode === 'localOnly' || (videoMode === 'both' && videoSwapped && !hasRemoteVideo)"
              class="no-video-placeholder"
            >
              <van-icon name="video-o" size="56" />
              <span class="no-video-text">对方未开摄像头</span>
            </div>
          </div>

          <!-- 顶部信息层 -->
          <div class="video-top-bar">
            <div class="video-caller">
              {{ callerInfo.username || targetUserId || '对方' }}
            </div>
            <div class="video-timer">{{ callDuration }}</div>
          </div>

          <!-- PIP 小视频框 -->
          <div
            v-if="videoMode === 'both' || videoMode === 'localOnly'"
            class="video-pip-box"
            :class="{ 'pip-clickable': videoMode === 'both' }"
            @click="videoMode === 'both' && handleSwapVideo()"
          >
            <template v-if="videoMode === 'both'">
              <video
                v-if="!videoSwapped"
                key="pip-local"
                ref="localVideoPip"
                autoplay
                playsinline
                muted
              ></video>
              <video
                v-else
                key="pip-remote"
                ref="remoteVideoPip"
                autoplay
                playsinline
              ></video>
            </template>
            <video
              v-else
              ref="localVideoPip"
              autoplay
              playsinline
              muted
            ></video>
            <div v-if="videoMode === 'both'" class="pip-swap-hint">点击切换</div>
          </div>
        </div>
      </template>

      <!-- 语音模式：占位 + 音量指示 -->
      <template v-else>
        <div class="screen-top">
          <div class="incoming-status">语音通话中</div>
          <div class="caller-avatar-large">
            <img
              v-if="callerInfo.avatar"
              :src="callerInfo.avatar"
              class="avatar-img"
              alt="avatar"
            />
            <span v-else class="avatar-placeholder">{{ getInitial(callerInfo.username) }}</span>
            <span class="ring-pulse"></span>
          </div>
          <div class="caller-name-large">
            {{ callerInfo.username || targetUserId || '对方' }}
          </div>
          <div class="caller-sub-text">{{ callDuration }}</div>

          <!-- 音量指示 -->
          <div class="volume-panel">
            <div class="volume-indicator">
              <van-icon name="phone-o" size="16" />
              <div class="volume-bar">
                <div class="volume-fill" :style="{ width: localVolume + '%' }"></div>
              </div>
              <span class="volume-value">{{ localVolume }}%</span>
            </div>
            <div class="volume-indicator">
              <van-icon name="volume-o" size="16" />
              <div class="volume-bar">
                <div class="volume-fill remote" :style="{ width: remoteVolume + '%' }"></div>
              </div>
              <span class="volume-value">{{ remoteVolume }}%</span>
            </div>
          </div>
        </div>
      </template>

      <!-- 底部：通话控制按钮 -->
      <div class="screen-bottom screen-bottom-calling">
        <div class="action-group">
          <button
            class="action-btn action-btn-toggle"
            :class="{ active: isMuted }"
            @click="handleToggleMute"
          >
            <van-icon :name="isMuted ? 'volume-o' : 'volume-o'" size="28" />
          </button>
          <span class="action-label">{{ isMuted ? '已静音' : '麦克风' }}</span>
        </div>
        <div class="action-group">
          <button
            class="action-btn action-btn-reject"
            @click="handleHangUp"
          >
            <van-icon name="phone" class="icon-hangup" size="32" />
          </button>
          <span class="action-label">挂断</span>
        </div>
        <div class="action-group">
          <button
            class="action-btn action-btn-toggle"
            :class="{ active: isVideoEnabled }"
            @click="handleToggleVideo"
          >
            <van-icon name="video-o" size="28" />
          </button>
          <span class="action-label">{{ isVideoEnabled ? '关闭' : '摄像头' }}</span>
        </div>
        <div v-if="isVideoEnabled" class="action-group">
          <button
            class="action-btn action-btn-toggle"
            @click="handleFlipCamera"
          >
            <van-icon name="replay" size="28" />
          </button>
          <span class="action-label">翻转</span>
        </div>
      </div>
    </div>

    <!-- ===== 对方已挂断界面 ===== -->
    <div v-else-if="showHangup" class="call-screen">
      <div class="screen-top">
        <div class="incoming-status">通话结束</div>
        <div class="caller-avatar-large ended">
          <img
            v-if="callerInfo.avatar"
            :src="callerInfo.avatar"
            class="avatar-img"
            alt="avatar"
          />
          <span v-else class="avatar-placeholder">{{ getInitial(callerInfo.username) }}</span>
        </div>
        <div class="caller-name-large">
          {{ callerInfo.username || targetUserId || '对方' }}
        </div>
        <div class="caller-sub-text">对方已挂断</div>
        <div class="caller-sub-text small">通话时长 {{ callDuration }}</div>
      </div>

      <div class="screen-bottom">
        <div class="action-group">
          <button class="action-btn action-btn-close" @click="handleClose">
            <van-icon name="cross" size="30" />
          </button>
          <span class="action-label">关闭</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ===== 全屏遮罩 ===== */
.mobile-call-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: linear-gradient(160deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
  display: flex;
  flex-direction: column;
  animation: overlayFadeIn 0.3s ease;
  overflow: hidden;
  user-select: none;
  -webkit-user-select: none;
}

@keyframes overlayFadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

/* ===== 通话界面通用 ===== */
.call-screen {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: center;
  padding: env(safe-area-inset-top, 24px) 20px calc(env(safe-area-inset-bottom, 20px) + 20px);
  box-sizing: border-box;
  color: #fff;
}

/* ===== 顶部 ===== */
.screen-top {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding-top: 40px;
  flex: 1;
  width: 100%;
}

.incoming-status {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.7);
  letter-spacing: 1px;
  margin-bottom: 8px;
}

/* ===== 头像 ===== */
.caller-avatar-large {
  position: relative;
  width: 110px;
  height: 110px;
  border-radius: 50%;
  overflow: visible;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 10px 0;
}

.avatar-img,
.avatar-placeholder {
  position: relative;
  z-index: 2;
  width: 110px;
  height: 110px;
  border-radius: 50%;
  object-fit: cover;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 44px;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, #2d7ddb 0%, #4aa3ff 100%);
  border: 3px solid rgba(255, 255, 255, 0.3);
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.4);
}

/* 来电呼吸圈 */
.ring-pulse {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.4);
  animation: ringPulse 2s ease-out infinite;
  pointer-events: none;
}

.ring-pulse.delay {
  animation-delay: 1s;
}

@keyframes ringPulse {
  0% {
    transform: scale(1);
    opacity: 0.8;
  }
  100% {
    transform: scale(1.8);
    opacity: 0;
  }
}

.caller-name-large {
  font-size: 22px;
  font-weight: 600;
  color: #fff;
  text-align: center;
  max-width: 80%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.caller-sub-text {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.65);
}

.caller-sub-text.small {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}

/* ===== 底部按钮区 ===== */
.screen-bottom {
  display: flex;
  align-items: flex-start;
  justify-content: center;
  gap: 48px;
  padding: 24px 0 16px;
  width: 100%;
}
.screen-bottom-calling{
  gap: 20px;
}

.action-group {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.action-btn {
  width: 68px;
  height: 68px;
  border-radius: 50%;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #fff;
  transition: transform 0.15s ease, box-shadow 0.2s ease, background 0.2s ease;
  -webkit-tap-highlight-color: transparent;
  outline: none;
}

.action-btn:active {
  transform: scale(0.92);
}

.action-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.8);
}

/* 接听按钮（绿色） */
.action-btn-accept {
  background: linear-gradient(135deg, #00b894 0%, #00cec9 100%);
  box-shadow: 0 6px 20px rgba(0, 184, 148, 0.45);
  animation: acceptBounce 1.5s ease-in-out infinite;
}

@keyframes acceptBounce {
  0%, 100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.06);
  }
}

/* 拒绝/挂断按钮（红色） */
.action-btn-reject {
  background: linear-gradient(135deg, #f56c6c 0%, #e74c3c 100%);
  box-shadow: 0 6px 20px rgba(245, 108, 108, 0.45);
}

/* 挂断图标旋转（经典挂断电话图标） */
.icon-hangup {
  transform: rotate(135deg);
  display: inline-block;
}

/* 功能切换按钮（半透明圆） */
.action-btn-toggle {
  background: rgba(255, 255, 255, 0.18);
  backdrop-filter: blur(6px);
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);
}

.action-btn-toggle.active {
  background: linear-gradient(135deg, #2d7ddb 0%, #4aa3ff 100%);
  box-shadow: 0 6px 20px rgba(45, 125, 219, 0.5);
}

/* 关闭按钮 */
.action-btn-close {
  background: rgba(255, 255, 255, 0.2);
  backdrop-filter: blur(6px);
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);
}

/* ===== 音量指示 ===== */
.volume-panel {
  width: 100%;
  max-width: 320px;
  margin-top: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.volume-indicator {
  display: flex;
  align-items: center;
  gap: 10px;
  color: rgba(255, 255, 255, 0.8);
}

.volume-bar {
  flex: 1;
  height: 6px;
  background: rgba(255, 255, 255, 0.15);
  border-radius: 3px;
  overflow: hidden;
}

.volume-fill {
  height: 100%;
  background: linear-gradient(90deg, #00b894, #4aa3ff);
  border-radius: 3px;
  transition: width 0.1s ease;
}

.volume-fill.remote {
  background: linear-gradient(90deg, #00cec9, #6c5ce7);
}

.volume-value {
  min-width: 36px;
  font-size: 12px;
  text-align: right;
  color: rgba(255, 255, 255, 0.6);
}

/* ===== 视频全屏 ===== */
.video-fullscreen {
  position: absolute;
  inset: 0;
  background: #000;
  z-index: 1;
}

.video-main-box {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: #1a1a2e;
}

.video-main {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* 视频顶部信息层 */
.video-top-bar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: calc(env(safe-area-inset-top, 16px) + 12px) 20px 24px;
  background: linear-gradient(180deg, rgba(0, 0, 0, 0.5) 0%, transparent 100%);
  z-index: 5;
  pointer-events: none;
}

.video-caller {
  font-size: 17px;
  font-weight: 600;
  color: #fff;
  max-width: 60%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.video-timer {
  font-size: 15px;
  color: rgba(255, 255, 255, 0.9);
  font-variant-numeric: tabular-nums;
  background: rgba(0, 0, 0, 0.35);
  padding: 4px 12px;
  border-radius: 12px;
}

/* 未开摄像头占位 */
.no-video-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background: linear-gradient(160deg, #1a1a2e 0%, #16213e 100%);
  color: rgba(255, 255, 255, 0.5);
}

.no-video-text {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.55);
}

/* PIP 小视频框 */
.video-pip-box {
  position: absolute;
  bottom: 130px;
  right: 16px;
  width: 90px;
  height: 120px;
  border-radius: 12px;
  overflow: hidden;
  border: 2px solid rgba(255, 255, 255, 0.4);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
  z-index: 10;
  transition: transform 0.2s ease, border-color 0.2s ease;
  background: #000;
}

.video-pip-box.pip-clickable {
  cursor: pointer;
}

.video-pip-box.pip-clickable:active {
  transform: scale(0.95);
  border-color: rgba(255, 255, 255, 0.8);
}

.video-pip-box video {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.pip-swap-hint {
  position: absolute;
  bottom: 4px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 9px;
  color: rgba(255, 255, 255, 0.9);
  background: rgba(0, 0, 0, 0.5);
  padding: 1px 6px;
  border-radius: 6px;
  white-space: nowrap;
  pointer-events: none;
}

/* 视频模式下底部按钮浮在视频上 */
.call-screen .screen-bottom {
  position: relative;
  z-index: 6;
}

/* 视频模式下底部按钮固定在底部 */
.video-fullscreen ~ .screen-bottom,
.call-screen:has(.video-fullscreen) .screen-bottom {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: linear-gradient(0deg, rgba(0, 0, 0, 0.5) 0%, transparent 100%);
  padding-bottom: calc(env(safe-area-inset-bottom, 20px) + 20px);
}

/* 结束状态头像无呼吸圈 */
.caller-avatar-large.ended .ring-pulse {
  display: none;
}

.caller-avatar-large.ended .avatar-img,
.caller-avatar-large.ended .avatar-placeholder {
  filter: grayscale(0.4);
  opacity: 0.85;
}
</style>
