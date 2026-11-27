/**
 * WebSocket 封装类 - 支持自动重连 + 心跳
 */
export class WebSocketClient {
  constructor(url, onMessage, onOpen, onClose, onError) {
    this.url = url;
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 3000;
    this.isManualClose = false;

    this.heartbeatTimer = null;
    this.heartbeatInterval = 20000;
    this.userId = null;
    this.heartbeatEnabled = false;

    this.onMessage = onMessage || (() => { });
    this.onOpen = onOpen || (() => { });
    this.onClose = onClose || (() => { });
    this.onError = onError || (() => { });
  }

  setUserId(userId) {
    this.userId = userId;
  }

  enableHeartbeat(interval = 20000) {
    this.heartbeatEnabled = true;
    this.heartbeatInterval = interval;
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.startHeartbeat();
    }
  }

  disableHeartbeat() {
    this.heartbeatEnabled = false;
    this.stopHeartbeat();
  }

  connect() {
    try {
      this.isManualClose = false;
      this.ws = new WebSocket(this.url);

      this.ws.onopen = (event) => {
        console.log('✅ WebSocket 连接成功:', this.url);
        this.reconnectAttempts = 0;
        if (this.heartbeatEnabled && this.userId) {
          this.startHeartbeat();
        }
        this.onOpen(event);
      };

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.type !== 'pong') {
            console.log('📨 收到消息:', message);
          }
          this.onMessage(message);
        } catch (error) {
          console.error('❌ 解析消息失败:', error);
        }
      };

      this.ws.onclose = (event) => {
        console.log('🔌 WebSocket 连接关闭');
        this.stopHeartbeat();
        this.onClose(event);

        if (!this.isManualClose && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts++;
          console.log(`🔄 尝试重连 (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
          setTimeout(() => this.connect(), this.reconnectDelay);
        }
      };

      this.ws.onerror = (error) => {
        console.error('❌ WebSocket 错误:', error);
        this.onError(error);
      };
    } catch (error) {
      console.error('❌ 创建 WebSocket 失败:', error);
    }
  }

  startHeartbeat() {
    this.stopHeartbeat();
    if (!this.userId) {
      console.warn('⚠️ 未设置 userId，无法发送心跳');
      return;
    }
    console.log('💓 心跳已启动，间隔:', this.heartbeatInterval / 1000, '秒');

    this.heartbeatTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        try {
          this.ws.send(JSON.stringify({
            from: this.userId,
            to: this.userId,
            type: 'ping',
            data: {}
          }));
          console.log('💓 发送心跳 ping');
        } catch (error) {
          console.error('❌ 发送心跳失败:', error);
        }
      }
    }, this.heartbeatInterval);
  }

  stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
      console.log('💓 心跳已停止');
    }
  }

  send(message) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
      return true;
    }
    console.warn('⚠️ WebSocket 未连接');
    return false;
  }

  close() {
    this.isManualClose = true;
    this.stopHeartbeat();
    if (this.ws) {
      this.ws.close();
    }
  }

  isConnected() {
    return this.ws && this.ws.readyState === WebSocket.OPEN;
  }
}