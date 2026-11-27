import { requestPythonAll } from '@/utils/request'

// 获取知识点列表
export const getKnowledgeListApi = (userId) => {
  return requestPythonAll.get('/knowledge-comparison/list', { params: { user_id: userId } })
}

// 添加自定义知识点
export const addCustomKnowledgeApi = (data) => {
  return requestPythonAll.post('/knowledge-comparison/custom/add', data)
}

// 删除自定义知识点
export const removeCustomKnowledgeApi = (data) => {
  return requestPythonAll.post('/knowledge-comparison/custom/remove', data)
}

// 获取推荐对比组合
export const getRecommendationsApi = () => {
  return requestPythonAll.get('/knowledge-comparison/recommendations')
}

// 知识点对比分析
export const compareKnowledgeApi = (data) => {
  return requestPythonAll.post('/knowledge-comparison/compare', data)
}
