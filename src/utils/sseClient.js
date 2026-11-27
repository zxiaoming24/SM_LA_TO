// @/utils/sseClient.js（可能无用）
// SSE 客户端（vue-java端）

/**
 * SSE 客户端 - 只负责建立连接和断开连接
 */
class SSEClient {
  constructor() {
    // 走 Nginx 同源代理（/sseApi -> 127.0.0.1:8080），开发环境由 Vite 代理
    this.baseURL = '/sseApi'
    this.eventSource = null
    this.userId = null
    this.isConnected = false
    this.reconnectTimer = null
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 5
  }

  /**
   * 建立SSE连接
   * @param {string} userId - 用户ID
   * @param {Object} options - 配置选项
   * @param {Function} onMessage - 消息回调
   * @param {Function} onError - 错误回调
   * @param {Function} onOpen - 连接成功回调
   * @returns {Promise<EventSource>}
   */
  connect(userId, options = {}) {
    return new Promise((resolve, reject) => {
      this.userId = userId || 'user_' + Date.now()

      // 如果已有连接，先断开
      if (this.eventSource) {
        this.disconnect()
      }

      // 构建URL
      const url = `${this.baseURL}/sse/connect/${this.userId}`
      console.log('🔗 建立SSE连接:', url)

      // 创建EventSource
      this.eventSource = new EventSource(url)

      // ===== 连接打开 =====
      this.eventSource.onopen = () => {
        this.isConnected = true
        this.reconnectAttempts = 0
        console.log('✅ SSE连接成功')
        if (options.onOpen) options.onOpen(this.userId)
        resolve(this.eventSource)
      }

      // ===== 接收消息 =====
      this.eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (options.onMessage) options.onMessage(data)
        } catch (e) {
          if (options.onMessage) options.onMessage(event.data)
        }
      }

      // ===== 监听特定事件 =====
      const eventTypes = [
        'connection', 'disconnect', 'message', 'json', 'delay',
        'broadcast', 'loop', 'status', 'heartbeat', 'notification',
        'auto_stream', 'data', 'system_status'
      ]

      eventTypes.forEach(type => {
        this.eventSource.addEventListener(type, (event) => {
          try {
            const data = JSON.parse(event.data)
            if (options.onMessage) options.onMessage(data, type)
          } catch (e) {
            if (options.onMessage) options.onMessage(event.data, type)
          }
        })
      })

      // ===== 错误处理 =====
      this.eventSource.onerror = (error) => {
        console.error('❌ SSE错误:', error)
        this.isConnected = false

        if (options.onError) options.onError(error)

        // 自动重连
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts++
          const delay = Math.min(
            3000 * Math.pow(2, this.reconnectAttempts - 1),
            30000
          )
          console.log(`⏳ ${delay / 1000}秒后尝试第${this.reconnectAttempts}次重连`)

          clearTimeout(this.reconnectTimer)
          this.reconnectTimer = setTimeout(() => {
            this.connect(this.userId, options)
          }, delay)
        } else {
          console.error('❌ 达到最大重连次数')
          if (options.onError) options.onError(new Error('达到最大重连次数'))
        }

        reject(error)
      }
    })
  }

  /**
   * 断开连接
   * @param {boolean} notifyServer - 是否通知服务器
   * @param {string} userId - 用户ID（可选，默认使用当前userId）
   */
  async disconnect(notifyServer = true, userId = null) {
    // 关闭EventSource
    if (this.eventSource) {
      this.eventSource.close()
      this.eventSource = null
    }

    this.isConnected = false
    clearTimeout(this.reconnectTimer)

    // 通知服务器端断开
    const id = userId || this.userId
    if (notifyServer && id) {
      try {
        await fetch(`${this.baseURL}/sse/disconnect/${id}`, {
          method: 'DELETE'
        })
        console.log('📤 已通知服务器断开连接')
      } catch (error) {
        console.warn('⚠️ 通知服务器断开失败:', error)
      }
    }

    console.log('🔌 连接已断开')
  }

  /**
   * 获取连接状态
   */
  get isConnectedSync() {
    return this.isConnected && this.eventSource !== null
  }
}

// 创建单例实例
const sseClient = new SSEClient()

export default sseClient