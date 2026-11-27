import { requestPythonAll } from '@/utils/request'

// 获取知识点列表
export const getKnowledgePointsApi = (userId) =>
  requestPythonAll.get(`/api/knowledge-points/${userId}`)

// 开始盘问
export const startInterrogationApi = (data) =>
  requestPythonAll.post('/api/interrogation/start', data)

// 提交回答
export const submitAnswerApi = (data) =>
  requestPythonAll.post('/api/interrogation/answer', data)
