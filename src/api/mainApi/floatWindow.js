// @/api/mainApi/floatWindow.js

import sseClient from '@/utils/sseClient.js'

// ============================================================
// SSE连接管理
// ============================================================

/**
 * 建立SSE连接
 * @param {string} userId - 用户ID
 * @returns {EventSource} EventSource实例
 */
export const connectSSE = (userId) => {
  const id = userId
  if (!id) {
    console.warn('⚠️ 用户ID为空，请检查')
    return null
  }
  const url = `/sseApi/sse/connect/${id}`
  console.log(' 创建SSE连接:', url)
  return new EventSource(url)
}

/**
 * 断开SSE连接
 * @param {boolean} notifyServer - 是否通知服务器
 * @param {string} userId - 用户ID
 */
export const disconnectSSE = async (notifyServer = true, userId = null) => {
  if (notifyServer && userId) {
    try {
      await fetch(`/sseApi/sse/disconnect/${userId}`, {
        method: 'DELETE'
      })
      console.log('📤 已通知服务器断开连接')
    } catch (error) {
      console.warn('️ 通知服务器断开失败:', error)
    }
  }
  console.log(' 连接已断开')
}

export { sseClient }