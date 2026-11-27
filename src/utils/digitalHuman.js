// @/utils/digitalHuman.js
// aiAnswer的数字人启动模块
import AvatarPlatform from '../../public/digitalman/avatar-sdk-web_demo/src/testSdk/3.1.2.1002/avatar-sdk-web_3.1.2.1002/index.js'

export class DigitalHuman {
  constructor(config) {
    if (!config) {
      throw new Error('DigitalHuman: 配置参数不能为空')
    }
    const required = ['serverUrl', 'appId', 'apiKey', 'apiSecret', 'sceneId']
    for (const key of required) {
      if (!config[key]) {
        throw new Error(`DigitalHuman: 缺少必要参数 ${key}`)
      }
    }

    this.config = { ...config }

    this.currentAvatar = null
    this.currentVoice = null
    this.currentBackground = null

    // 自动动作开关 (0: 关闭, 1: 开启)
    this.enableAir = 0

    this.avatarInstance = null
    this.playerInstance = null

    this.isReady = false
    this.isLoading = false
    this.isSpeaking = false
    this.isDestroyed = false

    this._listeners = {
      connected: [],
      disconnected: [],
      subtitle: [],
      error: [],
      playing: [],
      play: [],
      action_start: [],
      action_stop: [],
    }

    this._initSDK()
  }

  _initSDK() {
    try {
      this.avatarInstance = new AvatarPlatform({
        useInlinePlayer: true,
        binaryData: false,
      })

      this.avatarInstance.setApiInfo(this.config)

      this.avatarInstance
        .on('connected', (resp) => {
          this.isReady = true
          this.isLoading = false
          this._emit('connected', resp)
        })
        .on('disconnected', (e) => {
          this.isReady = false
          this.isLoading = false
          this.isSpeaking = false
          this._emit('disconnected', e)
        })
        .on('subtitle_info', (data) => {
          this._emit('subtitle', data?.text || '')
        })
        .on('error', (error) => {
          this.isLoading = false
          this._emit('error', error)
        })
        .on('action_start', (data) => {
          this._emit('action_start', data)
        })
        .on('action_stop', (data) => {
          this._emit('action_stop', data)
        })

      this.playerInstance = this.avatarInstance.createPlayer()
      this.playerInstance
        .on('error', (err) => {
          this._emit('error', err)
        })
        .on('playing', () => {
          this.isSpeaking = true
          this._emit('playing')
        })
        .on('play', () => {
          this._emit('play')
        })

      console.log('DigitalHuman: SDK初始化成功')
    } catch (e) {
      console.error('DigitalHuman: SDK初始化失败', e)
      throw e
    }
  }

  on(event, callback) {
    if (this._listeners[event]) {
      this._listeners[event].push(callback)
    }
    return this
  }

  off(event, callback) {
    if (this._listeners[event]) {
      this._listeners[event] = this._listeners[event].filter(cb => cb !== callback)
    }
    return this
  }

  _emit(event, data) {
    if (this._listeners[event]) {
      for (const cb of this._listeners[event]) {
        try {
          cb(data)
        } catch (e) {
          console.error('DigitalHuman: 事件回调执行失败', e)
        }
      }
    }
  }

  setAvatar(avatarId) {
    this.currentAvatar = avatarId
  }

  setVoice(voiceId) {
    this.currentVoice = voiceId
  }

  setBackground(backgroundUrl) {
    this.currentBackground = backgroundUrl
  }

  setAutoAction(enabled) {
    this.enableAir = enabled === 1 ? 1 : 0
    console.log(`DigitalHuman: 自动动作已${this.enableAir ? '开启' : '关闭'}`)
  }

  setParams({ avatarId, voiceId, backgroundUrl, air }) {
    if (avatarId !== undefined) this.currentAvatar = avatarId
    if (voiceId !== undefined) this.currentVoice = voiceId
    if (backgroundUrl !== undefined) this.currentBackground = backgroundUrl
    if (air !== undefined) this.enableAir = air === 1 ? 1 : 0
  }

  getState() {
    return {
      isReady: this.isReady,
      isLoading: this.isLoading,
      isSpeaking: this.isSpeaking,
      isDestroyed: this.isDestroyed,
      currentAvatar: this.currentAvatar,
      currentVoice: this.currentVoice,
      currentBackground: this.currentBackground,
      enableAir: this.enableAir,
    }
  }

  // ===== 修正：air 放在 avatar 配置中 =====
  async start(container, options = {}) {
    if (this.isDestroyed) {
      throw new Error('DigitalHuman: 实例已销毁')
    }

    if (!container) {
      throw new Error('DigitalHuman: 容器元素不能为空')
    }

    // 安全上下文前置检测：数字人 XRTC 播放器内部依赖 navigator.mediaDevices（麦克风），
    // 该 API 仅在 HTTPS 或 localhost 下存在，HTTP 页面会导致 SDK 内部抛出无法捕获的异常
    if (typeof window !== 'undefined' && window.isSecureContext === false) {
      throw new Error('当前为非安全上下文(HTTP)，请使用 HTTPS 访问后再启动数字人')
    }
    if (typeof navigator === 'undefined' || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error('当前浏览器不支持媒体设备访问(navigator.mediaDevices 不可用)，请使用 HTTPS 访问或更换浏览器')
    }

    if (!this.avatarInstance) {
      throw new Error('DigitalHuman: SDK未初始化')
    }

    if (this.isReady) {
      console.warn('DigitalHuman: 数字人已启动')
      return
    }

    this.isLoading = true

    const avatarId = options.avatarId || this.currentAvatar
    const voiceId = options.voiceId || this.currentVoice
    const backgroundUrl = options.backgroundUrl || this.currentBackground
    const air = options.air !== undefined ? options.air : this.enableAir

    if (!avatarId) {
      this.isLoading = false
      throw new Error('DigitalHuman: 未设置形象ID，请调用 setAvatar() 或在 options 中传入')
    }

    if (!voiceId) {
      this.isLoading = false
      throw new Error('DigitalHuman: 未设置语音ID，请调用 setVoice() 或在 options 中传入')
    }

    const width = options.width || 720
    const height = options.height || 1280

    try {
      const backgroundConfig = this.currentBackground
        ? {
          enabled: true,
          type: 'url',
          data: this.currentBackground,
        }
        : {}

      await this.avatarInstance.setGlobalParams({
        avatar_dispatch: {
          interactive_mode: 0,
          content_analysis: 0,
        },
        stream: {
          protocol: 'xrtc',
          alpha: 0,
          bitrate: 1000000,
          fps: 25,
        },
        avatar: {
          avatar_id: avatarId,
          width: width,
          height: height,
          mask_region: '[0, 0, 1080, 1920]',
          scale: 1,
          move_h: 0,
          move_v: 0,
          audio_format: 1,
          air: air,
        },
        tts: {
          vcn: voiceId,
          speed: 50,
          pitch: 50,
          volume: 100,
        },
        // 关闭字幕
        subtitle: {
          // subtitle: 1,
          // font_color: '#ffffff',
          subtitle: 0,
        },
        ...(Object.keys(backgroundConfig).length > 0 && { background: backgroundConfig }),
      })

      await this.avatarInstance.start({
        wrapper: container,
        preRes: {
          image: [
            {
              url: '22SLM2teIw+aqR6Xsm2JbH6Ng310kDam2NiCY/RQ9n6s3nYJXloZWW1l64/g32vrn7d2lJQR7m9xD5EHYkVs1+bLdJQ42I5SCCMphdtQC/KdIR9lQZl6Ryymh/CEiDdSSRND1SuiX8pjrFjxk/WMtJ+pDS5JT7P/8c0lxcMB6+IjTLQvgz41Fdhb1/sAGtES7HCMZepV5nNwisTvd8PhztpmXX+lIS1LQcPHJy2HW4/XrrKKf4AI8nj2lbocKniDJDk5cQtsOjY7raVi6fSp/9Zmz0eVr0UXa/wA65nxXD+I6VF6TxI1Er4wvKVTlpItpT2RDIDaanYWDZ3hyMDupH4MJcEev3sE9Tfl8tDtZ2c=',
            },
          ],
        },
      })

      this.isReady = true
      this.isLoading = false
      console.log(`DigitalHuman: 启动成功，自动动作: ${air ? '开启' : '关闭'}`)

    } catch (e) {
      this.isLoading = false
      this.isReady = false
      console.error('DigitalHuman: 启动失败', e)
      throw e
    }
  }

  async stop() {
    if (this.isDestroyed) return

    if (!this.avatarInstance) return

    try {
      if (this.isReady) {
        await this.avatarInstance.stop()
      }
      this.isReady = false
      this.isLoading = false
      this.isSpeaking = false
      console.log('DigitalHuman: 已停止')
    } catch (e) {
      console.error('DigitalHuman: 停止失败', e)
      throw e
    }
  }

  async speak(text, options = {}) {
    if (this.isDestroyed) {
      console.warn('DigitalHuman: 实例已销毁')
      return false
    }

    if (!this.isReady) {
      console.warn('DigitalHuman: 数字人未就绪')
      return false
    }

    if (!text || text.trim() === '') {
      console.warn('DigitalHuman: 播报文本为空')
      return false
    }

    const voiceId = options.voiceId || this.currentVoice
    if (!voiceId) {
      console.warn('DigitalHuman: 未设置语音ID')
      return false
    }

    try {
      const maxLength = 1800
      const speakText = text.length > maxLength ? text.slice(0, maxLength) + '...' : text

      await this.avatarInstance.writeText(speakText, {
        tts: {
          vcn: voiceId,
          speed: options.speed || 50,
          pitch: options.pitch || 50,
          volume: options.volume || 100,
        },
        interactive_mode: options.interactiveMode !== undefined ? options.interactiveMode : 0,
      })
      return true
    } catch (e) {
      console.error('DigitalHuman: 播报失败', e)
      throw e
    }
  }

  async interrupt() {
    if (this.isDestroyed) return

    if (!this.isReady || !this.avatarInstance) return

    try {
      await this.avatarInstance.interrupt()
      console.log('DigitalHuman: 已打断播报')
    } catch (e) {
      console.error('DigitalHuman: 打断失败', e)
      throw e
    }
  }

  async doAction(actionTag) {
    if (this.isDestroyed) {
      throw new Error('DigitalHuman: 实例已销毁')
    }

    if (!this.isReady || !this.avatarInstance) {
      throw new Error('DigitalHuman: 数字人未就绪，无法执行动作')
    }

    if (!actionTag || actionTag.trim() === '') {
      throw new Error('DigitalHuman: 动作标签不能为空')
    }

    try {
      const requestId = await this.avatarInstance.writeCmd('action', actionTag.trim())
      console.log(`DigitalHuman: 执行动作 ${actionTag}，请求ID: ${requestId}`)
      return requestId
    } catch (e) {
      console.error(`DigitalHuman: 执行动作 ${actionTag} 失败`, e)
      throw e
    }
  }

  async getActionList() {
    console.warn('DigitalHuman: getActionList 方法需要根据平台API具体实现')
    return []
  }

  async restart(container, options = {}) {
    if (this.isDestroyed) {
      throw new Error('DigitalHuman: 实例已销毁')
    }

    await this.stop()
    await new Promise(resolve => setTimeout(resolve, 500))
    await this.start(container, options)
  }

  destroy() {
    if (this.isDestroyed) return

    this.isDestroyed = true

    try {
      this.stop()
    } catch (e) {
      console.error('DigitalHuman: 停止时出错', e)
    }

    if (this.avatarInstance) {
      try {
        this.avatarInstance.destroy()
      } catch (e) {
        console.error('DigitalHuman: 销毁SDK失败', e)
      }
      this.avatarInstance = null
      this.playerInstance = null
    }

    this._listeners = {
      connected: [],
      disconnected: [],
      subtitle: [],
      error: [],
      playing: [],
      play: [],
      action_start: [],
      action_stop: [],
    }

    this.isReady = false
    this.isLoading = false
    this.isSpeaking = false

    console.log('DigitalHuman: 已销毁')
  }

  async reconnect(container) {
    if (this.isDestroyed) {
      throw new Error('DigitalHuman: 实例已销毁')
    }

    if (this.isReady) {
      console.warn('DigitalHuman: 数字人已连接，无需重连')
      return
    }

    const state = this.getState()
    await this.start(container, {
      avatarId: state.currentAvatar,
      voiceId: state.currentVoice,
      backgroundUrl: state.currentBackground,
      air: state.enableAir,
    })
  }
}

export function createDigitalHuman(config) {
  return new DigitalHuman(config)
}