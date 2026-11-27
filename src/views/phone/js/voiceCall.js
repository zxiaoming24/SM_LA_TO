import { WebSocketClient } from './websocket.js'
import { WebRTCManager } from './webrtc.js'
import { getUserInfoApi } from '@/api/mainApi/index.js'

// WebSocket 配置
const WS_CONFIG = {
  notifyUrl: '/wsJava2Api/ws/notify?userId=',
  signalUrl: '/wsJava1Api/ws/signal?userId='
}

// 语音通话状态
const CALL_STATE = {
  IDLE: 'idle',
  CALLING: 'calling',
  WAITING: 'waiting',
  CONNECTED: 'connected',
  HANGUP: 'hangup'
}

// 语音通话服务单例
class VoiceCallService {
  constructor() {
    this.userId = null
    this.targetUserId = null
    this.notifyWs = null
    this.signalWs = null
    this.webrtc = null
    this.callState = CALL_STATE.IDLE
    this.isMuted = false
    this.localVolume = 0
    this.remoteVolume = 0
    this.callDuration = '00:00'
    this.callSeconds = 0
    this.callTimer = null
    this.incomingCaller = ''

    // 音频元素引用
    this.remoteAudio = null
    this.localAudio = null

    // 视频状态
    this.enableVideo = false
    this.isVideoEnabled = false
    this.localVideoStream = null
    this.remoteVideoStream = null

    // 视频元素引用
    this.remoteVideoEl = null
    this.localVideoEl = null

    // 事件回调
    this.onIncomingCall = null
    this.onCallRejected = null
    this.onCallCanceled = null
    this.onCallAccepted = null
    this.onCallConnected = null
    this.onRemoteHangup = null
    this.onCallTimeout = null
    this.onUserOffline = null
    this.onVolumeChange = null
    this.onMuteChange = null
    this.onNotifyConnected = null
    this.onSignalConnected = null
    this.onDurationChange = null
    this.onSelfReject = null  // 用户主动拒绝来电
    this.onLocalVideoStream = null   // 本地视频流变化
    this.onRemoteVideoStream = null  // 远端视频流变化
    this.onVideoToggle = null        // 视频开关状态变化

    this.waitingForOffer = false
    this.isCaller = false
    this.isHangupByRemote = false

    // 用户名缓存
    this.userNameCache = {}
  }

  // 设置用户ID
  setUserId(userId) {
    this.userId = userId
  }

  // 设置事件回调
  setCallbacks(callbacks) {
    if (callbacks.onIncomingCall) this.onIncomingCall = callbacks.onIncomingCall
    if (callbacks.onCallRejected) this.onCallRejected = callbacks.onCallRejected
    if (callbacks.onCallCanceled) this.onCallCanceled = callbacks.onCallCanceled
    if (callbacks.onCallAccepted) this.onCallAccepted = callbacks.onCallAccepted
    if (callbacks.onCallConnected) this.onCallConnected = callbacks.onCallConnected
    if (callbacks.onRemoteHangup) this.onRemoteHangup = callbacks.onRemoteHangup
    if (callbacks.onCallTimeout) this.onCallTimeout = callbacks.onCallTimeout
    if (callbacks.onUserOffline) this.onUserOffline = callbacks.onUserOffline
    if (callbacks.onVolumeChange) this.onVolumeChange = callbacks.onVolumeChange
    if (callbacks.onMuteChange) this.onMuteChange = callbacks.onMuteChange
    if (callbacks.onNotifyConnected) this.onNotifyConnected = callbacks.onNotifyConnected
    if (callbacks.onSignalConnected) this.onSignalConnected = callbacks.onSignalConnected
    if (callbacks.onDurationChange) this.onDurationChange = callbacks.onDurationChange
    if (callbacks.onSelfReject) this.onSelfReject = callbacks.onSelfReject
    if (callbacks.onLocalVideoStream) this.onLocalVideoStream = callbacks.onLocalVideoStream
    if (callbacks.onRemoteVideoStream) this.onRemoteVideoStream = callbacks.onRemoteVideoStream
    if (callbacks.onVideoToggle) this.onVideoToggle = callbacks.onVideoToggle
  }

  // 创建音频元素
  createAudioElements() {
    // 创建本地音频元素（静音播放）
    if (!this.localAudio) {
      this.localAudio = document.createElement('audio')
      this.localAudio.muted = true
      this.localAudio.autoplay = true
      this.localAudio.style.display = 'none'
      document.body.appendChild(this.localAudio)
    }

    // 创建远端音频元素
    if (!this.remoteAudio) {
      this.remoteAudio = document.createElement('audio')
      this.remoteAudio.autoplay = true
      this.remoteAudio.style.display = 'none'
      document.body.appendChild(this.remoteAudio)
    }
  }

  // 安全播放音频
  async safePlayAudio(audioElement, stream) {
    if (!audioElement || !stream) return false
    try {
      audioElement.srcObject = stream
      await audioElement.play()
      return true
    } catch (error) {
      console.warn('⚠️ 自动播放失败:', error.message)
      return false
    }
  }

  // 创建视频元素
  createVideoElements() {
    if (!this.localVideoEl) {
      this.localVideoEl = document.createElement('video')
      this.localVideoEl.muted = true
      this.localVideoEl.autoplay = true
      this.localVideoEl.playsInline = true
      this.localVideoEl.style.display = 'none'
      document.body.appendChild(this.localVideoEl)
    }
    if (!this.remoteVideoEl) {
      this.remoteVideoEl = document.createElement('video')
      this.remoteVideoEl.autoplay = true
      this.remoteVideoEl.playsInline = true
      this.remoteVideoEl.style.display = 'none'
      document.body.appendChild(this.remoteVideoEl)
    }
  }

  // 清理音频元素
  cleanupAudioElements() {
    if (this.localAudio) {
      this.localAudio.srcObject = null
      this.localAudio.remove()
      this.localAudio = null
    }
    if (this.remoteAudio) {
      this.remoteAudio.srcObject = null
      this.remoteAudio.remove()
      this.remoteAudio = null
    }
    if (this.localVideoEl) {
      this.localVideoEl.srcObject = null
      this.localVideoEl.remove()
      this.localVideoEl = null
    }
    if (this.remoteVideoEl) {
      this.remoteVideoEl.srcObject = null
      this.remoteVideoEl.remove()
      this.remoteVideoEl = null
    }
  }

  // ==================== 通知通道（常驻，退出登录时断开） ====================

  // 连接通知通道
  connectNotifyChannel() {
    if (!this.userId) {
      console.error('⚠️ 未设置用户ID')
      return
    }

    if (this.notifyWs) {
      this.notifyWs.close()
    }

    const url = `${WS_CONFIG.notifyUrl}${this.userId}`

    this.notifyWs = new WebSocketClient(
      url,
      this.handleNotifyMessage.bind(this),
      () => {
        console.log('✅ 通知通道已连接')
        if (this.onNotifyConnected) this.onNotifyConnected()
      },
      () => {
        console.log('❌ 通知通道已关闭')
      },
      (error) => {
        console.error('❌ 通知通道错误:', error)
      }
    )

    this.notifyWs.setUserId(this.userId)
    this.notifyWs.enableHeartbeat(20000)
    this.notifyWs.connect()
  }

  // 断开通知通道（退出登录时调用）
  disconnectNotifyChannel() {
    if (this.notifyWs) {
      this.notifyWs.close()
      this.notifyWs = null
    }
  }

  // 发送通知消息
  sendNotifyMessage(type, data = {}, to = '') {
    const message = {
      from: this.userId,
      to: to || this.targetUserId,
      type: type,
      data: data
    }
    if (this.notifyWs && this.notifyWs.isConnected()) {
      this.notifyWs.send(message)
    }
  }

  // 处理通知消息
  handleNotifyMessage(message) {
    const { from, to, type, data } = message
    if (type === 'pong') return
    if (to && to !== this.userId) return

    console.log('📨 [通知通道]', message)

    switch (type) {
      case 'VOICE_CALL_INVITE':
        this.handleIncomingCall(from, data)
        break
      case 'VOICE_CALL_REJECT':
        this.handleCallRejected(from)
        break
      case 'VOICE_CALL_CANCEL':
        this.handleCallCanceled(from)
        break
      case 'USER_OFFLINE':
        this.handleUserOffline(data)
        break
      case 'CALL_INVITE_TIMEOUT':
        this.handleCallTimeout(data)
        break
      default:
        console.warn('⚠️ 未知通知类型:', type)
    }
  }

  // ==================== 信令通道（通话时建立，挂断时断开） ====================

  // 连接信令通道
  connectSignalChannel() {
    if (!this.userId) {
      console.error('⚠️ 未设置用户ID')
      return
    }

    if (this.signalWs) {
      this.signalWs.close()
    }

    const url = `${WS_CONFIG.signalUrl}${this.userId}`

    this.signalWs = new WebSocketClient(
      url,
      this.handleSignalMessage.bind(this),
      () => {
        console.log('✅ 信令通道已连接')
        if (this.onSignalConnected) this.onSignalConnected()
      },
      () => {
        console.log('❌ 信令通道已关闭')
        this.callState = CALL_STATE.IDLE
        if (this.webrtc) {
          this.webrtc.hangUp()
          this.webrtc = null
        }
      },
      (error) => {
        console.error('❌ 信令通道错误:', error)
      }
    )

    this.signalWs.connect()
  }

  // 断开信令通道（通话结束时调用）
  disconnectSignalChannel() {
    if (this.signalWs) {
      this.signalWs.close()
      this.signalWs = null
    }
  }

  // 发送信令消息
  sendSignalMessage(type, data = {}, to = '') {
    const message = {
      from: this.userId,
      to: to || this.targetUserId,
      type: type,
      data: data
    }
    if (this.signalWs && this.signalWs.isConnected()) {
      this.signalWs.send(message)
    }
  }

  // 处理信令消息
  handleSignalMessage(message) {
    const { from, to, type, data } = message
    if (to && to !== this.userId) return

    console.log('📨 [信令通道]', message)

    if (from && !this.targetUserId && type !== 'hangup') {
      this.targetUserId = from
    }

    switch (type) {
      case 'accept':
        this.handleAccept(from)
        break
      case 'offer':
        this.handleOffer(data)
        break
      case 'answer':
        this.handleAnswer(data)
        break
      case 'candidate':
        this.handleIceCandidate(data)
        break
      case 'hangup':
        this.handleRemoteHangup(from)
        break
      default:
        console.warn('⚠️ 未知信令类型:', type)
    }
  }

  // ==================== 呼叫流程 ====================

  // 发起呼叫
  async startCall(targetUserId, enableVideo = false) {
    if (!targetUserId) {
      console.error('⚠️ 目标用户ID为空')
      return
    }
    if (targetUserId === this.userId) {
      console.error('⚠️ 不能呼叫自己')
      return
    }

    this.targetUserId = targetUserId
    this.enableVideo = enableVideo
    this.callState = CALL_STATE.WAITING
    this.isCaller = true
    this.isHangupByRemote = false
    this.waitingForOffer = false
    this.localVolume = 0
    this.remoteVolume = 0

    // 创建音频/视频元素
    this.createAudioElements()
    if (this.enableVideo) this.createVideoElements()

    // 连接信令通道
    this.connectSignalChannel()

    // 等待信令通道连接
    await this.waitForSignalConnected()

    try {
      this.webrtc = new WebRTCManager({
        onIceCandidate: (candidate) => {
          this.sendSignalMessage('candidate', {
            candidate: candidate.candidate,
            sdpMid: candidate.sdpMid,
            sdpMLineIndex: candidate.sdpMLineIndex
          })
        },
        onRemoteStream: (stream) => {
          this.handleRemoteStream(stream)
        },
        onLocalStream: (stream) => {
          this.handleLocalStream(stream)
        },
        onConnectionStateChange: (type, state) => {
          console.log(`🔗 状态变化 [${type}]:`, state)
          if (type === 'connection' && state === 'failed') {
            if (this.onCallTimeout) this.onCallTimeout('连接失败')
            this.hangUp()
          }
        },
        onAudioLevel: (level) => {
          this.remoteVolume = Math.round(level * 100)
          if (this.onVolumeChange) this.onVolumeChange({ local: this.localVolume, remote: this.remoteVolume })
        },
        onError: (error) => {
          if (this.onCallTimeout) this.onCallTimeout(error)
          this.hangUp()
        }
      })

      this.isVideoEnabled = false  // 默认本地摄像头关闭（可手动开启）
      this.isMuted = false         // 默认麦克风开启
      await this.webrtc.getLocalStream()
      // 注意：不自动开启本地摄像头。enableVideo 仅用于 SDP offerToReceiveVideo，
      // 确保能接收对方视频。用户可手动点击"摄像头"按钮开启。
      this.webrtc.createPeerConnection(true, { enableVideo: this.enableVideo })
      this.webrtc.addLocalTracks({ enableVideo: false })

      // 发送 invite（后端会转发到通知通道）
      this.sendSignalMessage('invite', { enableVideo: this.enableVideo })
      console.log('📤 发送 invite', { enableVideo: this.enableVideo, localVideo: false })

      this.startCallTimer()
      this.startLocalVolumeMonitor()

      // 后端负责超时逻辑，前端不做自动超时挂断

    } catch (error) {
      console.error('❌ 发起呼叫失败:', error)
      if (this.onCallTimeout) this.onCallTimeout('呼叫失败')
      this.hangUp()
    }
  }

  // 等待信令通道连接
  waitForSignalConnected() {
    return new Promise((resolve) => {
      if (this.signalWs && this.signalWs.isConnected()) {
        resolve()
        return
      }

      const checkInterval = setInterval(() => {
        if (this.signalWs && this.signalWs.isConnected()) {
          clearInterval(checkInterval)
          resolve()
        }
      }, 100)

      setTimeout(() => {
        clearInterval(checkInterval)
        resolve()
      }, 5000)
    })
  }

  // 处理来电
  async handleIncomingCall(from, data = {}) {
    if (this.callState !== CALL_STATE.IDLE) {
      // 正在通话中，拒绝来电
      this.sendNotifyMessage('VOICE_CALL_REJECT', {}, from)
      return
    }

    const username = await this.getUserName(from)

    this.incomingCaller = username
    this.targetUserId = from
    this.enableVideo = data.enableVideo || false
    this.callState = CALL_STATE.CALLING

    console.log('📞 收到来电:', from, '视频:', this.enableVideo)

    if (this.onIncomingCall) this.onIncomingCall(from, username, this.enableVideo)

    // 播放铃声
    this.playRingtone()
  }

  // 接听来电
  async acceptCall() {
    if (this.callState !== CALL_STATE.CALLING) return

    this.callState = CALL_STATE.WAITING
    this.isCaller = false
    this.isHangupByRemote = false
    this.waitingForOffer = true
    this.localVolume = 0
    this.remoteVolume = 0

    // 创建音频/视频元素
    this.createAudioElements()
    if (this.enableVideo) this.createVideoElements()

    this.stopRingtone()

    // 通知界面切换到等待状态（关闭来电框）
    if (this.onCallAccepted) this.onCallAccepted(this.incomingCaller)

    // 连接信令通道
    this.connectSignalChannel()

    // 等待信令通道连接
    await this.waitForSignalConnected()

    try {
      this.webrtc = new WebRTCManager({
        onIceCandidate: (candidate) => {
          this.sendSignalMessage('candidate', {
            candidate: candidate.candidate,
            sdpMid: candidate.sdpMid,
            sdpMLineIndex: candidate.sdpMLineIndex
          })
        },
        onRemoteStream: (stream) => {
          this.handleRemoteStream(stream)
        },
        onLocalStream: (stream) => {
          this.handleLocalStream(stream)
        },
        onConnectionStateChange: (type, state) => {
          console.log(`🔗 状态变化 [${type}]:`, state)
          if (type === 'connection' && state === 'failed') {
            if (this.onCallTimeout) this.onCallTimeout('连接失败')
            this.hangUp()
          }
        },
        onAudioLevel: (level) => {
          this.remoteVolume = Math.round(level * 100)
          if (this.onVolumeChange) this.onVolumeChange({ local: this.localVolume, remote: this.remoteVolume })
        },
        onError: (error) => {
          if (this.onCallTimeout) this.onCallTimeout(error)
          this.hangUp()
        }
      })

      this.isVideoEnabled = false  // 默认本地摄像头关闭（可手动开启）
      this.isMuted = false         // 默认麦克风开启
      await this.webrtc.getLocalStream()
      // 注意：不自动开启本地摄像头。enableVideo 仅用于 SDP offerToReceiveVideo，
      // 确保能接收对方视频。用户可手动点击"摄像头"按钮开启。
      this.webrtc.createPeerConnection(false, { enableVideo: this.enableVideo })
      this.webrtc.addLocalTracks({ enableVideo: false })

      // 发送 accept
      this.sendSignalMessage('accept', {})
      console.log('📤 发送 accept (默认本地视频关闭)')

      this.startCallTimer()
      this.startLocalVolumeMonitor()

      // 后端负责超时逻辑，前端不做自动超时挂断

    } catch (error) {
      console.error('❌ 接听失败:', error)
      if (this.onCallTimeout) this.onCallTimeout('接听失败')
      this.hangUp()
    }
  }

  // 拒绝来电（用户主动拒绝，不触发onCallRejected）
  rejectCall() {
    if (this.callState !== CALL_STATE.CALLING) return

    this.stopRingtone()
    // 使用用户ID作为接收方，不是用户名
    this.sendNotifyMessage('VOICE_CALL_REJECT', {}, this.targetUserId)
    this.incomingCaller = ''
    this.callState = CALL_STATE.IDLE

    // 设置标志，用于在handleCallCanceled中判断是否是自己刚刚拒绝的来电
    this.justRejected = true
    setTimeout(() => { this.justRejected = false }, 2000)

    // 用户主动拒绝来电，不触发onCallRejected回调（那是对方拒绝时用的）
    // 通过onSelfReject通知界面显示"你取消了通话"
    if (this.onSelfReject) this.onSelfReject()
  }

  // 处理对方接受
  async handleAccept(from) {
    const username = await this.getUserName(from)
    console.log('✅ 对方已接受通话:', username)
    if (this.onCallAccepted) this.onCallAccepted(username)
    this.sendOffer()
  }

  // 发送 Offer
  async sendOffer() {
    try {
      if (!this.webrtc) return
      const offer = await this.webrtc.createOffer()
      this.sendSignalMessage('offer', {
        type: 'offer',
        sdp: offer.sdp
      })
      console.log('📤 Offer 已发送')
    } catch (error) {
      console.error('❌ 发送 Offer 失败:', error)
      this.hangUp()
    }
  }

  // 处理 Offer
  async handleOffer(data) {
    console.log('📥 收到 Offer')
    this.waitingForOffer = false
    if (!this.webrtc) return

    try {
      // 从 SDP 检测是否包含视频（只用于设置 answer 的 offerToReceiveVideo）
      const offerSdp = data && data.sdp ? data.sdp : ''
      const hasVideo = /m=video/.test(offerSdp)
      console.log('🔍 Offer SDP 视频检测:', hasVideo)

      // 注意：不在这里自动开启本地摄像头
      // 微信逻辑：一方开摄像头，另一方只接收对方视频，不会自动开启自己的
      // 接收方想开摄像头需要手动点击"开摄像头"按钮

      const answer = await this.webrtc.createAnswer(data)
      this.sendSignalMessage('answer', {
        type: 'answer',
        sdp: answer.sdp
      })
      console.log('📤 Answer 已发送')
    } catch (error) {
      console.error('❌ 处理 Offer 失败:', error)
      this.hangUp()
    }
  }

  // 处理 Answer
  async handleAnswer(data) {
    console.log('📥 收到 Answer')
    if (!this.webrtc) return
    try {
      await this.webrtc.handleAnswer(data)
      console.log('✅ Answer 处理完成')
    } catch (error) {
      console.error('❌ 处理 Answer 失败:', error)
      this.hangUp()
    }
  }

  // 处理 ICE 候选
  async handleIceCandidate(data) {
    if (!this.webrtc) return
    await this.webrtc.addIceCandidate(data)
  }

  // ==================== 通话处理 ====================

  // 处理远端流（音频+视频）
  handleRemoteStream(stream) {
    console.log('📡 处理远端流，音频轨道:', stream.getAudioTracks().length, '视频轨道:', stream.getVideoTracks().length)

    stream.getAudioTracks().forEach(track => {
      track.enabled = true
    })

    // 使用 audio 元素播放远端音频
    if (this.remoteAudio) {
      this.safePlayAudio(this.remoteAudio, stream).then(() => {
        console.log('🔊 远端音频开始播放')
      })
    }

    // 处理远端视频
    if (stream.getVideoTracks().length > 0) {
      this.remoteVideoStream = stream
      if (this.remoteVideoEl) {
        this.remoteVideoEl.srcObject = stream
        this.remoteVideoEl.play().catch(() => { })
      }
      if (this.onRemoteVideoStream) this.onRemoteVideoStream(stream)
    }

    this.callState = CALL_STATE.CONNECTED

    // 重启计时器（确保从通话真正连接时开始计时）
    this.startCallTimer()

    if (this.onCallConnected) this.onCallConnected()
  }

  // 处理本地流（音频+视频）
  handleLocalStream(stream) {
    console.log('🎤 处理本地流，音频轨道:', stream.getAudioTracks().length, '视频轨道:', stream.getVideoTracks().length)

    // 使用 audio 元素播放本地音频（静音）
    if (this.localAudio) {
      this.localAudio.srcObject = stream
      this.localAudio.play().catch(e => console.warn('本地音频播放失败:', e))
    }

    // 处理本地视频
    if (stream.getVideoTracks().length > 0) {
      this.localVideoStream = stream
      this.isVideoEnabled = true
      if (this.localVideoEl) {
        this.localVideoEl.srcObject = stream
        this.localVideoEl.play().catch(() => { })
      }
      if (this.onLocalVideoStream) this.onLocalVideoStream(stream)
    }
  }

  // 处理对方挂断
  async handleRemoteHangup(from) {
    const username = await this.getUserName(from)
    console.log(`📴 用户 ${username} 已挂断`)
    this.stopRingtone()

    this.isHangupByRemote = true
    this.callState = CALL_STATE.HANGUP

    if (this.onRemoteHangup) this.onRemoteHangup(username)

    this.stopCallTimer()

    if (this.webrtc) {
      this.webrtc.hangUp()
      this.webrtc = null
    }

    // 清理音频元素
    this.cleanupAudioElements()

    // 断开信令通道（通知通道保持连接）
    this.disconnectSignalChannel()
  }

  // 挂断通话
  hangUp() {
    if (this.isHangupByRemote) {
      // 对方已挂断，直接清理状态
      this.cleanupCallState()
      return
    }

    this.stopRingtone()

    // 发送挂断消息到信令通道（如果已建立连接）
    if (this.callState !== CALL_STATE.IDLE && this.targetUserId && this.signalWs && this.signalWs.isConnected()) {
      this.sendSignalMessage('hangup', {})
    }

    // 如果是呼叫者且处于等待状态，通过通知通道发送取消通知
    // 因为对方可能还没有建立信令通道，无法收到信令通道的hangup消息
    if (this.isCaller && this.callState === CALL_STATE.WAITING && this.targetUserId && this.notifyWs && this.notifyWs.isConnected()) {
      this.sendNotifyMessage('VOICE_CALL_CANCEL', { reason: '对方已取消呼叫' }, this.targetUserId)
      console.log('📤 通过通知通道发送取消呼叫通知')
    }

    if (this.webrtc) {
      this.webrtc.hangUp()
      this.webrtc = null
    }

    // 清理音频元素
    this.cleanupAudioElements()

    this.stopCallTimer()
    this.disconnectSignalChannel()
    this.cleanupCallState()

    console.log('📴 通话已结束')
  }

  // 清理通话状态
  cleanupCallState() {
    this.callState = CALL_STATE.IDLE
    this.isCaller = false
    this.isHangupByRemote = false
    this.waitingForOffer = false
    this.targetUserId = ''
    this.incomingCaller = ''
    this.callDuration = '00:00'
    this.callSeconds = 0
    this.localVolume = 0
    this.remoteVolume = 0
    // 清理视频状态
    this.enableVideo = false
    this.isVideoEnabled = false
    this.localVideoStream = null
    this.remoteVideoStream = null
  }

  // ==================== 铃声 ====================

  playRingtone() {
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)()
      const oscillator = audioCtx.createOscillator()
      const gainNode = audioCtx.createGain()
      oscillator.connect(gainNode)
      gainNode.connect(audioCtx.destination)
      oscillator.frequency.value = 440
      oscillator.type = 'sine'

      const now = audioCtx.currentTime
      for (let i = 0; i < 6; i++) {
        const startTime = now + i * 0.6
        gainNode.gain.setValueAtTime(0.2, startTime)
        gainNode.gain.setValueAtTime(0, startTime + 0.3)
      }
      oscillator.start(now)
      oscillator.stop(now + 3.6)
      this.ringtoneCtx = audioCtx
    } catch (error) {
      console.warn('播放铃声失败:', error)
    }
  }

  stopRingtone() {
    if (this.ringtoneCtx) {
      try {
        this.ringtoneCtx.close()
        this.ringtoneCtx = null
      } catch (error) {
        console.warn('停止铃声失败:', error)
      }
    }
  }

  // ==================== 音量监控 ====================

  startLocalVolumeMonitor() {
    if (!this.webrtc || !this.webrtc.localStream) return
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)()
      const analyser = audioCtx.createAnalyser()
      analyser.fftSize = 256
      const source = audioCtx.createMediaStreamSource(this.webrtc.localStream)
      source.connect(analyser)
      const dataArray = new Uint8Array(analyser.frequencyBinCount)

      const checkVolume = () => {
        if (this.callState === CALL_STATE.IDLE) {
          audioCtx.close()
          return
        }
        analyser.getByteFrequencyData(dataArray)
        let sum = 0
        for (let i = 0; i < dataArray.length; i++) {
          sum += dataArray[i]
        }
        const avg = sum / dataArray.length
        this.localVolume = Math.min(Math.round(avg / 128 * 100), 100)
        if (this.onVolumeChange) this.onVolumeChange({ local: this.localVolume, remote: this.remoteVolume })
        requestAnimationFrame(checkVolume)
      }
      checkVolume()
    } catch (error) {
      console.warn('本地音量监控失败:', error)
    }
  }

  // 切换静音
  toggleMute() {
    if (this.webrtc) {
      const unmuted = this.webrtc.toggleMute()
      this.isMuted = !unmuted
      if (this.onMuteChange) this.onMuteChange(this.isMuted)
    }
  }

  // 切换摄像头
  async toggleVideo() {
    if (!this.webrtc || this.callState !== CALL_STATE.CONNECTED) return

    try {
      if (this.isVideoEnabled) {
        // 关闭摄像头
        await this.webrtc.updateLocalStream(false)
        this.isVideoEnabled = false
        this.localVideoStream = null
        if (this.localVideoEl) this.localVideoEl.srcObject = null
        if (this.onLocalVideoStream) this.onLocalVideoStream(null)
        // 重新协商（通知对方本地视频已关闭）
        await this._renegotiate()
      } else {
        // 开启摄像头
        if (!this.localVideoEl) this.createVideoElements()
        this.enableVideo = true
        await this.webrtc.updateLocalStream(true)
        this.isVideoEnabled = true
        // 显式更新本地视频流（updateLocalStream 内部 onLocalStream 回调可能因引用相同不触发 Vue 响应式更新）
        if (this.webrtc.localStream && this.webrtc.localStream.getVideoTracks().length > 0) {
          this.localVideoStream = this.webrtc.localStream
          if (this.localVideoEl) {
            this.localVideoEl.srcObject = this.webrtc.localStream
            this.localVideoEl.play().catch(() => { })
          }
          if (this.onLocalVideoStream) this.onLocalVideoStream(this.webrtc.localStream)
        }
        // 重新协商（通知对方本地视频已开启）
        await this._renegotiate()
      }
      if (this.onVideoToggle) this.onVideoToggle(this.isVideoEnabled)
    } catch (error) {
      console.error('❌ 切换摄像头失败:', error)
    }
  }

  // 翻转摄像头（前/后置切换）
  async flipCamera() {
    if (!this.webrtc || !this.isVideoEnabled) return false

    try {
      const success = await this.webrtc.flipCamera()
      if (success) {
        // 更新本地视频流引用（确保 Vue 响应式更新）
        if (this.webrtc.localStream && this.webrtc.localStream.getVideoTracks().length > 0) {
          this.localVideoStream = this.webrtc.localStream
          if (this.localVideoEl) {
            this.localVideoEl.srcObject = this.webrtc.localStream
            this.localVideoEl.play().catch(() => { })
          }
          if (this.onLocalVideoStream) this.onLocalVideoStream(this.webrtc.localStream)
        }
      }
      return success
    } catch (error) {
      console.error('❌ 翻转摄像头失败:', error)
      return false
    }
  }

  // 重新协商（用于通话中开启/关闭摄像头）
  async _renegotiate() {
    if (!this.webrtc || !this.webrtc.peerConnection) return
    try {
      const offer = await this.webrtc.createOffer()
      this.sendSignalMessage('offer', {
        type: 'offer',
        sdp: offer.sdp
      })
      console.log('📤 重新协商 Offer 已发送')
    } catch (error) {
      console.error('❌ 重新协商失败:', error)
    }
  }

  // 获取视频状态
  getVideoState() {
    return {
      enableVideo: this.enableVideo,
      isVideoEnabled: this.isVideoEnabled,
      localVideoStream: this.localVideoStream,
      remoteVideoStream: this.remoteVideoStream
    }
  }

  // ==================== 计时器 ====================

  startCallTimer() {
    this.callSeconds = 0
    this.callDuration = '00:00'
    if (this.callTimer) clearInterval(this.callTimer)
    this.callTimer = setInterval(() => {
      this.callSeconds++
      const mins = String(Math.floor(this.callSeconds / 60)).padStart(2, '0')
      const secs = String(this.callSeconds % 60).padStart(2, '0')
      this.callDuration = `${mins}:${secs}`

      // 通知外部更新通话时长
      if (this.onDurationChange) this.onDurationChange(this.callDuration)
    }, 1000)
  }

  stopCallTimer() {
    if (this.callTimer) {
      clearInterval(this.callTimer)
      this.callTimer = null
    }
  }

  // ==================== 辅助方法 ====================

  // 处理对方拒绝
  async handleCallRejected(from) {
    const username = await this.getUserName(from)
    console.log(`❌ 用户 ${username} 拒绝了通话`)
    if (this.onCallRejected) this.onCallRejected(username)
    this.hangUp()
  }

  // 处理对方取消呼叫
  async handleCallCanceled(from) {
    // 如果用户刚刚拒绝了来电，忽略对方的取消通知（避免重复提示）
    if (this.justRejected) {
      console.log('📭 忽略对方取消通知（用户刚刚拒绝了来电）')
      return
    }

    const username = await this.getUserName(from)
    console.log(`📭 用户 ${username} 取消了呼叫`)
    if (this.onCallCanceled) this.onCallCanceled(username)
    this.hangUp()
  }

  // 处理用户离线
  handleUserOffline(data) {
    const msg = typeof data === 'string' ? data : '对方尚未登录，暂时无法发起语音通话'
    if (this.onUserOffline) this.onUserOffline(msg)
  }

  // 处理呼叫超时（后端通知，不自动挂断）
  handleCallTimeout(data) {
    const msg = typeof data === 'string' ? data : '对方可能在忙，请等会再通话'
    if (this.onCallTimeout) this.onCallTimeout(msg)
    // 后端通知的超时不自动挂断，由用户手动挂断
  }

  // 获取当前状态
  getState() {
    return {
      callState: this.callState,
      targetUserId: this.targetUserId,
      incomingCaller: this.incomingCaller,
      isMuted: this.isMuted,
      localVolume: this.localVolume,
      remoteVolume: this.remoteVolume,
      callDuration: this.callDuration,
      isNotifyConnected: this.notifyWs && this.notifyWs.isConnected(),
      isSignalConnected: this.signalWs && this.signalWs.isConnected()
    }
  }

  // 获取用户名（带缓存）
  async getUserName(userId) {
    if (!userId) return ''

    // 先查缓存
    if (this.userNameCache[userId]) {
      return this.userNameCache[userId]
    }

    // 调用接口获取
    try {
      const res = await getUserInfoApi({ userIdList: [userId] })
      if (res.code === 1 && res.data && res.data.length > 0) {
        const username = res.data[0].username || userId
        this.userNameCache[userId] = username
        return username
      }
    } catch (error) {
      console.warn('获取用户名失败:', error)
    }

    return userId
  }
}

// 创建单例实例
const voiceCallService = new VoiceCallService()

export default voiceCallService

// 导出常量
export { CALL_STATE }

// 导出类（用于扩展）
export { VoiceCallService }
