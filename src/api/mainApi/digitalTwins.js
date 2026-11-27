import { requestPythonAll } from '@/utils/request'

// 加载数字孪生数据
export const getDigitalTwinApi = (userId) =>
  requestPythonAll.get(`/digital-twin/${encodeURIComponent(userId)}`)

// 切换孪生开关
export const toggleDigitalTwinApi = (userId, enabled) =>
  requestPythonAll.post(`/digital-twin/${encodeURIComponent(userId)}/toggle`, { enabled })

// 构建孪生（SSE 流式）
export const buildDigitalTwinStream = (userId) =>
  fetch(`/py/digital-twin/${encodeURIComponent(userId)}/build-stream`, {
    headers: {
      'token': JSON.parse(localStorage.getItem('loginUser') || 'null')?.token || ''
    }
  })

// 获取对比历史
export const getComparisonApi = (userId, params = {}) => {
  const query = new URLSearchParams()
  if (params.limit) query.set('limit', params.limit)
  if (params.result_type) query.set('result_type', params.result_type)
  const qs = query.toString()
  return requestPythonAll.get(`/digital-twin/${encodeURIComponent(userId)}/comparison${qs ? '?' + qs : ''}`)
}

// 分析单条记录
export const analyzeRecordApi = (userId, recordIdx) =>
  requestPythonAll.get(`/digital-twin/${encodeURIComponent(userId)}/comparison/${recordIdx}/analyze`)

// 清空对比历史
export const clearHistoryApi = (userId) =>
  requestPythonAll.delete(`/digital-twin/${encodeURIComponent(userId)}/history`)
