import { requestPythonAll } from '@/utils/request.js'

// 获取智能体监控统计信息
export const getAgentStats = () => {
  return requestPythonAll.get('/admin/agent-monitor/stats')
}
// 获取智能体监控历史记录
export const getAgentHistory = (limit = 50) => {
  return requestPythonAll.get(`/admin/agent-monitor/history?limit=${limit}`)
}
// 重置智能体监控统计信息
export const resetAgentStats = () => {
  return requestPythonAll.post('/admin/agent-monitor/reset')
}