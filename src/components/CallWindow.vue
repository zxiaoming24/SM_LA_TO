<script>
import { getUserInfoApi } from '@/api/mainApi/index.js'

export default {
  name: 'CallWindow',
  props: {
    showIncoming: {
      type: Boolean,
      default: false
    },
    showWaiting: {
      type: Boolean,
      default: false
    },
    showCalling: {
      type: Boolean,
      default: false
    },
    showHangup: {
      type: Boolean,
      default: false
    },
    targetUserId: {
      type: String,
      default: ''
    },
    incomingCaller: {
      type: String,
      default: ''
    },
    callDuration: {
      type: String,
      default: '00:00'
    },
    localVolume: {
      type: Number,
      default: 0
    },
    remoteVolume: {
      type: Number,
      default: 0
    },
    isMuted: {
      type: Boolean,
      default: false
    },
    isVideoEnabled: {
      type: Boolean,
      default: false
    },
    localVideoStream: {
      type: [MediaStream, Object],
      default: null
    },
    remoteVideoStream: {
      type: [MediaStream, Object],
      default: null
    },
    enableVideo: {
      type: Boolean,
      default: false
    }
  },
  data() {
    return {
      callerInfo: {
        userId: '',
        username: '',
        avatar: ''
      },
      videoSwapped: false,
      // 用响应式 data 追踪视频状态（computed 无法追踪 MediaStream 内部变化）
      _hasLocalVideo: false,
      _hasRemoteVideo: false
    }
  },
  computed: {
    // 视频模式: 'none' | 'both' | 'localOnly' | 'remoteOnly'
    videoMode() {
      if (this._hasLocalVideo && this._hasRemoteVideo) return 'both'
      if (this._hasLocalVideo) return 'localOnly'
      if (this._hasRemoteVideo) return 'remoteOnly'
      return 'none'
    }
  },
  emits: [
    'accept', 'reject', 'hangup', 'close', 'toggleMute', 'toggleVideo'
  ],
  watch: {
    // 只监听用户ID变化来获取用户信息
    targetUserId: {
      immediate: true,
      handler(newVal) {
        if (newVal) {
          this.fetchUserInfo(newVal)
        }
      }
    },
    localVideoStream: {
      handler(newStream) {
        // 检查 MediaStream 是否有视频轨道（Vue 无法自动追踪，需手动更新）
        this._hasLocalVideo = !!(newStream && newStream.getVideoTracks && newStream.getVideoTracks().length > 0)
        this.$nextTick(() => {
          this.attachLocalVideo()
        })
      }
    },
    remoteVideoStream: {
      handler(newStream) {
        this._hasRemoteVideo = !!(newStream && newStream.getVideoTracks && newStream.getVideoTracks().length > 0)
        this.$nextTick(() => {
          this.attachRemoteVideo()
        })
      }
    },
    // 监听 isVideoEnabled prop 变化（兜底：确保按钮开关状态与视频显示同步）
    isVideoEnabled: {
      handler(val) {
        if (val && this.localVideoStream) {
          this._hasLocalVideo = true
        } else if (!val) {
          this._hasLocalVideo = false
        }
      }
    },
    // 监听 videoMode 变化，确保在模式切换后正确绑定视频元素
    videoMode: {
      handler(newMode, oldMode) {
        // 从双方模式切换到单方模式时，重置 videoSwapped 状态
        if (oldMode === 'both' && newMode !== 'both') {
          this.videoSwapped = false
        }
        this.$nextTick(() => {
          this.attachLocalVideo()
          this.attachRemoteVideo()
        })
      }
    }
  },
  methods: {
    async fetchUserInfo(userId) {
      if (!userId) return
      try {
        const res = await getUserInfoApi({ userIdList: [userId] })
        if (res.code === 1 && res.data && res.data.length > 0) {
          this.callerInfo = {
            userId: res.data[0].userId,
            username: res.data[0].username,
            avatar: res.data[0].avatar || ''
          }
        }
      } catch (error) {
        console.warn('获取用户信息失败:', error)
      }
    },
    getInitial(name) {
      if (!name) return '👤'
      return name.charAt(0).toUpperCase()
    },
    handleAccept() {
      console.log('📞 接听按钮点击')
      this.$emit('accept')
    },
    handleReject() {
      console.log('❌ 拒绝按钮点击')
      this.$emit('reject')
    },
    handleHangUp() {
      console.log('📴 挂断按钮点击')
      this.$emit('hangup')
    },
    handleClose() {
      console.log('✅ 关闭按钮点击')
      this.$emit('close')
    },
    handleToggleMute() {
      console.log('🔇 静音切换')
      this.$emit('toggleMute')
    },
    handleToggleVideo() {
      console.log('📹 摄像头切换')
      this.$emit('toggleVideo')
    },
    handleSwapVideo() {
      this.videoSwapped = !this.videoSwapped
      // 切换后，重新设置 srcObject 并播放视频
      // 大框用 v-show，两个元素都在 DOM 中，都需要绑定
      // 小框用 v-if/v-else，只有当前显示的元素在 DOM 中，只需绑定一个
      this.$nextTick(() => {
        // 大框：重新绑定两个流（v-show 切换）
        const localVideoMain = this.$refs.localVideoMain
        const remoteVideoMain = this.$refs.remoteVideoMain
        if (localVideoMain && this.localVideoStream) {
          localVideoMain.srcObject = this.localVideoStream
          localVideoMain.play().catch(() => {})
        }
        if (remoteVideoMain && this.remoteVideoStream) {
          remoteVideoMain.srcObject = this.remoteVideoStream
          remoteVideoMain.play().catch(() => {})
        }

        // 小框：只绑定当前可见的那个（v-if/v-else 切换，DOM 中只有一个）
        const pipVideo = this.$refs.localVideoPip || this.$refs.remoteVideoPip
        if (pipVideo) {
          const stream = this.$refs.localVideoPip ? this.localVideoStream : this.remoteVideoStream
          if (stream) {
            pipVideo.srcObject = stream
            pipVideo.play().catch(() => {})
          }
        }
      })
    },
    attachLocalVideo() {
      if (!this.localVideoStream) return
      this.$nextTick(() => {
        // 大框：localVideoMain 在 both 模式下根据 videoSwapped 显示
        const localVideoMain = this.$refs.localVideoMain
        if (localVideoMain && localVideoMain.srcObject !== this.localVideoStream) {
          localVideoMain.srcObject = this.localVideoStream
          localVideoMain.play().catch(() => {})
        }
        // 小框：localVideoPip 只在 !videoSwapped 时存在于 DOM
        const localVideoPip = this.$refs.localVideoPip
        if (localVideoPip && localVideoPip.srcObject !== this.localVideoStream) {
          localVideoPip.srcObject = this.localVideoStream
          localVideoPip.play().catch(() => {})
        }
      })
    },
    attachRemoteVideo() {
      if (!this.remoteVideoStream) return
      this.$nextTick(() => {
        // 大框：remoteVideoMain 在 both 模式下根据 videoSwapped 显示
        const remoteVideoMain = this.$refs.remoteVideoMain
        if (remoteVideoMain && remoteVideoMain.srcObject !== this.remoteVideoStream) {
          remoteVideoMain.srcObject = this.remoteVideoStream
          remoteVideoMain.play().catch(() => {})
        }
        // 小框：remoteVideoPip 只在 videoSwapped 时存在于 DOM
        const remoteVideoPip = this.$refs.remoteVideoPip
        if (remoteVideoPip && remoteVideoPip.srcObject !== this.remoteVideoStream) {
          remoteVideoPip.srcObject = this.remoteVideoStream
          remoteVideoPip.play().catch(() => {})
        }
      })
    }
  }
}
</script>

<template>
  <!-- ===== 右上角来电弹窗 ===== -->
  <div v-if="showIncoming" class="call-window incoming">
    <div class="call-window-header">
      <div class="caller-info">
        <div class="caller-avatar-wrapper">
          <img v-if="callerInfo.avatar" :src="callerInfo.avatar" class="caller-avatar-img" alt="avatar" />
          <span v-else class="caller-avatar-placeholder">{{ getInitial(callerInfo.username) }}</span>
        </div>
        <span class="caller-name">{{ callerInfo.username || incomingCaller || '未知用户' }}</span>
      </div>
      <span class="call-status">{{ enableVideo ? '视频邀请' : '邀请你通话' }}</span>
    </div>
    <div class="call-window-body">
      <div class="ringing-animation-small">
        <span class="ringing-icon">📞</span>
      </div>
      <span class="ringing-text">正在呼叫...</span>
    </div>
    <div class="call-window-actions">
      <button @click="handleAccept" class="btn-accept-small">
        ✅ 接听
      </button>
      <button @click="handleReject" class="btn-reject-small">
        ❌ 拒绝
      </button>
    </div>
  </div>

  <!-- ===== 右上角等待接听（呼叫中） ===== -->
  <div v-if="showWaiting" class="call-window waiting">
    <div class="call-window-header">
      <div class="caller-info">
        <div class="caller-avatar-wrapper">
          <img v-if="callerInfo.avatar" :src="callerInfo.avatar" class="caller-avatar-img" alt="avatar" />
          <span v-else class="caller-avatar-placeholder">{{ getInitial(callerInfo.username) }}</span>
        </div>
        <span class="caller-name">{{ callerInfo.username || targetUserId || '对方' }}</span>
      </div>
      <span class="call-status">呼叫中...</span>
    </div>
    <div class="call-window-body">
      <div class="waiting-spinner"></div>
      <span class="waiting-time">等待接听 {{ callDuration }}</span>
    </div>
    <div class="call-window-actions">
      <button @click="handleHangUp" class="btn-hangup-small">
        📴 取消
      </button>
    </div>
  </div>

  <!-- ===== 右上角通话中 ===== -->
  <div v-if="showCalling" class="call-window calling" :class="{ 'call-window-video': videoMode !== 'none' }">
    <div class="call-window-header">
      <div class="caller-info">
        <div class="caller-avatar-wrapper">
          <img v-if="callerInfo.avatar" :src="callerInfo.avatar" class="caller-avatar-img" alt="avatar" />
          <span v-else class="caller-avatar-placeholder">{{ getInitial(callerInfo.username) }}</span>
        </div>
        <span class="caller-name">{{ callerInfo.username || targetUserId || '对方' }}</span>
      </div>
      <span class="call-status">{{ videoMode !== 'none' ? '视频通话中' : '通话中' }}</span>
    </div>

    <!-- 视频模式（至少一方开启摄像头） -->
    <template v-if="videoMode !== 'none'">
      <div class="video-container">
        <!-- 大视频框 -->
        <div class="video-main-box">
          <!-- 双方都有视频 -->
          <template v-if="videoMode === 'both'">
            <video
              ref="remoteVideoMain"
              v-show="!videoSwapped"
              autoplay playsinline
              class="video-remote-main"
            ></video>
            <video
              ref="localVideoMain"
              v-show="videoSwapped"
              autoplay playsinline muted
              class="video-local-main"
            ></video>
          </template>
          <!-- 只有远端有视频（对方开摄像头，自己没开） -->
          <template v-else-if="videoMode === 'remoteOnly'">
            <video
              ref="remoteVideoMain"
              autoplay playsinline
              class="video-remote-main"
            ></video>
          </template>
          <!-- 只有本地有视频（自己开摄像头，对方没开）：大框显示对方占位 -->
          <template v-else-if="videoMode === 'localOnly'">
            <!-- 大框不显示本地视频，显示"对方未开摄像头"占位 -->
          </template>
          <!-- 对方未开摄像头提示（localOnly 或 both 模式下翻转后远端无视频时显示） -->
          <div v-if="videoMode === 'localOnly' || (videoMode === 'both' && videoSwapped && !_hasRemoteVideo)" class="no-video-placeholder">
            <span class="no-video-icon">📷</span>
            <span class="no-video-text">对方未开摄像头</span>
          </div>
          <!-- 通话时长标签 -->
          <div class="video-timer-label">⏱ {{ callDuration }}</div>
        </div>
        <!-- 小视频框（PIP，localOnly 或 both 模式时显示） -->
        <div
          v-if="videoMode === 'both' || videoMode === 'localOnly'"
          class="video-pip-box"
          :class="{ 'pip-clickable': videoMode === 'both' }"
          @click="videoMode === 'both' && handleSwapVideo()"
          :title="videoMode === 'both' ? '点击切换画面' : ''"
        >
          <!-- 使用 v-if/v-else 确保每次只有一个 video 元素存在于 DOM 中，避免 display:none 导致解码停止 -->
          <template v-if="videoMode === 'both'">
            <video
              v-if="!videoSwapped"
              key="pip-local"
              ref="localVideoPip"
              autoplay playsinline muted
            ></video>
            <video
              v-else
              key="pip-remote"
              ref="remoteVideoPip"
              autoplay playsinline
            ></video>
          </template>
          <video
            v-else
            ref="localVideoPip"
            autoplay playsinline muted
          ></video>
          <div v-if="videoMode === 'both'" class="pip-swap-hint">点击切换</div>
        </div>
      </div>
    </template>

    <!-- 语音模式（双方都没开启摄像头） -->
    <div v-else class="call-window-body">
      <div class="volume-indicator">
        <span>🎤 麦克风</span>
        <div class="volume-bar">
          <div class="volume-fill" :style="{ width: localVolume + '%' }"></div>
        </div>
        <span class="volume-value">{{ localVolume }}%</span>
      </div>
      <div class="volume-indicator">
        <span>🔊 扬声器</span>
        <div class="volume-bar">
          <div class="volume-fill remote" :style="{ width: remoteVolume + '%' }"></div>
        </div>
        <span class="volume-value">{{ remoteVolume }}%</span>
      </div>
      <span class="call-time">⏱ {{ callDuration }}</span>
    </div>

    <div class="call-window-actions">
      <button @click="handleToggleMute" class="btn-mute-small" :class="{ active: isMuted }">
        {{ isMuted ? '🔇 静音' : '🎙️ 麦克风' }}
      </button>
      <button @click="handleToggleVideo" class="btn-video-small" :class="{ active: isVideoEnabled }">
        {{ isVideoEnabled ? '📹 摄像头' : '📷 开摄像头' }}
      </button>
      <button @click="handleHangUp" class="btn-hangup-small">
        📴 挂断
      </button>
    </div>
  </div>

  <!-- ===== 右上角对方已挂断 ===== -->
  <div v-if="showHangup" class="call-window hangup">
    <div class="call-window-header">
      <div class="caller-info">
        <div class="caller-avatar-wrapper">
          <img v-if="callerInfo.avatar" :src="callerInfo.avatar" class="caller-avatar-img" alt="avatar" />
          <span v-else class="caller-avatar-placeholder">{{ getInitial(callerInfo.username) }}</span>
        </div>
        <span class="caller-name">{{ callerInfo.username || targetUserId || '对方' }}</span>
      </div>
      <span class="call-status">已挂断</span>
    </div>
    <div class="call-window-body">
      <span class="hangup-icon">📴</span>
      <span class="hangup-text">对方已挂断</span>
      <span class="call-time">通话时长 {{ callDuration }}</span>
    </div>
    <div class="call-window-actions">
      <button @click="handleClose" class="btn-close-small">
        ✅ 确定
      </button>
    </div>
  </div>
</template>


<style scoped>
/* ===== 浮窗容器 ===== */
.call-window {
  position: fixed;
  top: 70px;
  right: 20px;
  width: 320px;
  background: var(--bg-card);
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15), 0 2px 8px rgba(0, 0, 0, 0.1);
  padding: 16px 20px;
  z-index: 9999;
  animation: slideInRight 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  border: 1px solid var(--border-color);
  min-height: 100px;
  backdrop-filter: blur(10px);
}

/* 视频模式加宽弹窗 */
.call-window.call-window-video {
  width: 380px;
}

@keyframes slideInRight {
  from {
    transform: translateX(120%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

/* ===== 不同状态边框 ===== */
.call-window.incoming {
  border-left: 4px solid var(--primary);
  background: linear-gradient(135deg, var(--bg-card) 0%, var(--primary-light) 100%);
  box-shadow: 0 8px 32px rgba(45, 125, 219, 0.2), 0 2px 8px rgba(45, 125, 219, 0.1);
}

.call-window.waiting {
  border-left: 4px solid var(--warning);
  background: linear-gradient(135deg, var(--bg-card) 0%, var(--coming-bg-color) 100%);
  box-shadow: 0 8px 32px rgba(243, 156, 18, 0.2), 0 2px 8px rgba(243, 156, 18, 0.1);
}

.call-window.calling {
  border-left: 4px solid var(--success);
  background: linear-gradient(135deg, var(--bg-card) 0%, var(--pass-bg-color) 100%);
  box-shadow: 0 8px 32px rgba(0, 184, 148, 0.2), 0 2px 8px rgba(0, 184, 148, 0.1);
}

.call-window.hangup {
  border-left: 4px solid var(--main-delete);
  background: linear-gradient(135deg, var(--bg-card) 0%, var(--main-fail-status) 100%);
  box-shadow: 0 8px 32px rgba(245, 108, 108, 0.2), 0 2px 8px rgba(245, 108, 108, 0.1);
}

/* ===== 头部 ===== */
.call-window-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.caller-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* ===== 头像样式 ===== */
.caller-avatar-wrapper {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  overflow: hidden;
  flex-shrink: 0;
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
  border: 2px solid var(--border-color);
}

.caller-avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.caller-avatar-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  font-size: 16px;
  font-weight: 600;
  color: white;
}

.caller-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-title);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 150px;
}

.call-status {
  font-size: 12px;
  padding: 4px 12px;
  border-radius: 16px;
  background: var(--bgc-light);
  color: var(--text-gray);
  font-weight: 500;
  flex-shrink: 0;
}

/* ===== 不同状态的状态标签颜色 ===== */
.call-window.incoming .call-status {
  background: var(--primary);
  color: white;
}

.call-window.waiting .call-status {
  background: var(--warning);
  color: var(--text-title);
}

.call-window.calling .call-status {
  background: var(--success);
  color: white;
}

.call-window.hangup .call-status {
  background: var(--main-delete);
  color: white;
}

/* ===== 主体（语音模式） ===== */
.call-window-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 8px 0;
  min-height: 50px;
}

/* ===== 来电铃声动画 ===== */
.ringing-animation-small {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 40px;
  height: 40px;
}

.ringing-icon {
  font-size: 32px;
  animation: shake-small 0.5s ease-in-out infinite;
}

@keyframes shake-small {
  0%, 100% { transform: rotate(0deg); }
  25% { transform: rotate(-15deg); }
  75% { transform: rotate(15deg); }
}

.ringing-text {
  font-size: 14px;
  color: var(--primary);
  font-weight: 500;
}

/* ===== 等待动画 ===== */
.waiting-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border-color);
  border-top-color: var(--warning);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.waiting-time {
  font-size: 13px;
  color: var(--text-gray);
}

/* ===== 音量指示 ===== */
.volume-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  font-size: 13px;
  color: var(--text-body);
}

.volume-indicator span:first-child {
  min-width: 50px;
}

.volume-bar {
  flex: 1;
  height: 4px;
  background: var(--bgc-light);
  border-radius: 2px;
  overflow: hidden;
}

.volume-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--success), var(--primary));
  border-radius: 2px;
  transition: width 0.1s ease;
}

.volume-fill.remote {
  background: linear-gradient(90deg, var(--success), var(--primary));
}

.volume-value {
  min-width: 36px;
  font-size: 12px;
  color: var(--text-gray);
}

.call-time {
  font-size: 14px;
  color: var(--text-body);
  font-weight: 500;
}

/* ===== 挂断样式 ===== */
.hangup-icon {
  font-size: 32px;
}

.hangup-text {
  font-size: 15px;
  color: var(--main-delete);
  font-weight: 600;
}

/* ===== 按钮 ===== */
.call-window-actions {
  display: flex;
  gap: 8px;
  justify-content: center;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-color);
}

.call-window-actions button {
  padding: 7px 14px;
  border: none;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.call-window-actions button:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
}

.call-window-actions button:active {
  transform: translateY(0);
}

.btn-accept-small {
  background: linear-gradient(135deg, var(--success) 0%, var(--success-hover) 100%);
  color: white;
}
.btn-accept-small:hover {
  background: linear-gradient(135deg, var(--success-hover) 0%, var(--success) 100%);
  box-shadow: 0 4px 16px rgba(0, 184, 148, 0.3);
}

.btn-reject-small {
  background: linear-gradient(135deg, var(--main-delete) 0%, var(--main-delete-hover) 100%);
  color: white;
}
.btn-reject-small:hover {
  background: linear-gradient(135deg, var(--main-delete-hover) 0%, var(--main-delete) 100%);
  box-shadow: 0 4px 16px rgba(245, 108, 108, 0.3);
}

.btn-hangup-small {
  background: linear-gradient(135deg, var(--main-delete) 0%, var(--main-delete-hover) 100%);
  color: white;
}
.btn-hangup-small:hover {
  background: linear-gradient(135deg, var(--main-delete-hover) 0%, var(--main-delete) 100%);
  box-shadow: 0 4px 16px rgba(245, 108, 108, 0.3);
}

.btn-mute-small {
  background: var(--bgc-light);
  color: var(--text-body);
  border: 1px solid var(--border-color);
}
.btn-mute-small:hover {
  background: var(--bg-hover);
}
.btn-mute-small.active {
  background: linear-gradient(135deg, var(--main-delete) 0%, var(--main-delete-hover) 100%);
  color: white;
  border: none;
}

.btn-video-small {
  background: var(--bgc-light);
  color: var(--text-body);
  border: 1px solid var(--border-color);
}
.btn-video-small:hover {
  background: var(--bg-hover);
}
.btn-video-small.active {
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-hv) 100%);
  color: white;
  border: none;
}

.btn-close-small {
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-hv) 100%);
  color: white;
}
.btn-close-small:hover {
  background: linear-gradient(135deg, var(--primary-hv) 0%, var(--primary) 100%);
  box-shadow: 0 4px 16px rgba(45, 125, 219, 0.3);
}

/* ==================== 视频通话样式 ==================== */

.video-container {
  position: relative;
  width: 100%;
  border-radius: 12px;
  overflow: hidden;
  background: #1a1a2e;
  margin-bottom: 4px;
}

.video-main-box {
  position: relative;
  width: 100%;
  aspect-ratio: 4 / 3;
  overflow: hidden;
}

.video-main-box video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* 小视频框 (PIP) */
.video-pip-box {
  position: absolute;
  bottom: 8px;
  right: 8px;
  width: 100px;
  height: 75px;
  border-radius: 8px;
  overflow: hidden;
  border: 2px solid rgba(255, 255, 255, 0.4);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.3);
  cursor: pointer;
  z-index: 10;
  transition: transform 0.2s ease;
}

.video-pip-box:hover {
  transform: scale(1.05);
  border-color: rgba(255, 255, 255, 0.7);
}

.video-pip-box video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.pip-swap-hint {
  position: absolute;
  bottom: 2px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 10px;
  color: rgba(255, 255, 255, 0.8);
  background: rgba(0, 0, 0, 0.5);
  padding: 1px 6px;
  border-radius: 8px;
  white-space: nowrap;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.2s;
}

.video-pip-box:hover .pip-swap-hint {
  opacity: 1;
}

/* 未开摄像头提示 */
.no-video-placeholder {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #1a1a2e;
  gap: 8px;
}

.no-video-icon {
  font-size: 36px;
  opacity: 0.6;
}

.no-video-text {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.6);
}

/* 视频通话时长标签 */
.video-timer-label {
  position: absolute;
  top: 6px;
  left: 8px;
  background: rgba(0, 0, 0, 0.5);
  color: white;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
  z-index: 5;
}

/* ===== 响应式 ===== */
@media (max-width: 500px) {
  .call-window {
    top: 10px;
    right: 10px;
    left: 10px;
    width: auto;
    padding: 14px 16px;
    min-height: 80px;
  }

  .call-window.call-window-video {
    width: auto;
  }
  
  .caller-name {
    font-size: 14px;
  }
  
  .call-window-actions button {
    padding: 5px 10px;
    font-size: 11px;
  }

  .video-pip-box {
    width: 80px;
    height: 60px;
    bottom: 6px;
    right: 6px;
  }
}
</style>
